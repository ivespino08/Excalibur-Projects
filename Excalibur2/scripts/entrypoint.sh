#!/usr/bin/env bash
# Excalibur Container Entrypoint
# Sets up authentication based on EXCALIBUR_AUTH_MODE environment variable

set -e

# The container now starts as root (see Dockerfile) specifically so this
# step can run: /workspace is a host bind mount, and whatever created that
# directory on the host (Docker Desktop on macOS/Windows, dockerd on
# Linux) typically leaves it owned by root from the container's point of
# view. Fix that here, every start, rather than relying on the host user
# to chown it manually -- this is what makes the fix portable across
# Linux/macOS/Windows hosts instead of depending on host UID matching.
if [ "$(id -u)" = "0" ]; then
    chown -R pentester:pentester /workspace

    # Re-exec this same script as pentester, then everything below runs
    # unprivileged as originally intended.
    exec gosu pentester "$0" "$@"
fi

AUTH_MODE="${EXCALIBUR_AUTH_MODE:-manual}"
CCR_CONFIG_DIR="/home/pentester/.claude-code-router"
CCR_CONFIG_FILE="${CCR_CONFIG_DIR}/config.json"
BASHRC_FILE="/home/pentester/.bashrc"

# Colors for output
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[0;33m'
NC='\033[0m'

# Router configurations for different modes
OPENROUTER_ROUTER='{"default":"openrouter,deepseek/deepseek-v4-pro","background":"openrouter,deepseek/deepseek-v4-pro","think":"openrouter,deepseek/deepseek-v4-pro","longContext":"openrouter,deepseek/deepseek-v4-pro","longContextThreshold":60000,"webSearch":"openrouter,deepseek/deepseek-v4-pro"}'
LOCAL_ROUTER='{"default":"localLLM,openai/gpt-oss-20b","background":"localLLM,openai/gpt-oss-20b","think":"localLLM,qwen/qwen3-coder-30b","longContext":"localLLM,qwen/qwen3-coder-30b","longContextThreshold":60000,"webSearch":"localLLM,openai/gpt-oss-20b"}'

setup_ccr() {
    local mode="$1"
    local api_key="$2"
    local template_file="/app/scripts/ccr-config-template.json"

    # Create CCR config directory if needed
    mkdir -p "$CCR_CONFIG_DIR"

    # Check if template exists
    if [ ! -f "$template_file" ]; then
        echo -e "${YELLOW}Error: CCR config template not found at $template_file${NC}"
        exit 1
    fi

    # Copy template and substitute placeholders
    cp "$template_file" "$CCR_CONFIG_FILE"

    # Substitute API key (for openrouter mode)
    if [ -n "$api_key" ]; then
        sed -i "s/__OPENROUTER_API_KEY__/${api_key}/g" "$CCR_CONFIG_FILE"
    fi

    # Substitute Router config based on mode (use | as delimiter to avoid conflicts with /)
    if [ "$mode" = "openrouter" ]; then
        sed -i "s|\"__ROUTER_CONFIG__\"|${OPENROUTER_ROUTER}|g" "$CCR_CONFIG_FILE"
        local display_model="deepseek/deepseek-v4-pro"
    else
        sed -i "s|\"__ROUTER_CONFIG__\"|${LOCAL_ROUTER}|g" "$CCR_CONFIG_FILE"
        local display_model="localLLM (qwen/qwen3-coder-30b, openai/gpt-oss-20b)"
    fi

    # Validate the generated config BEFORE starting CCR. A malformed config (bad
    # JSON, or a leftover placeholder because a substitution failed) makes CCR
    # die on every start — catching it here gives a clear error instead of an
    # endless crash-restart loop below.
    if command -v jq >/dev/null 2>&1; then
        if ! jq -e . "$CCR_CONFIG_FILE" >/dev/null 2>&1; then
            echo -e "${YELLOW}Error: generated CCR config is not valid JSON: $CCR_CONFIG_FILE${NC}"
            exit 1
        fi
    fi
    if grep -q "__OPENROUTER_API_KEY__\|__ROUTER_CONFIG__" "$CCR_CONFIG_FILE"; then
        echo -e "${YELLOW}Error: CCR config still has unsubstituted placeholders: $CCR_CONFIG_FILE${NC}"
        exit 1
    fi

    echo -e "${BLUE}Starting Claude Code Router...${NC}"

    local ccr_port="${CCR_PORT:-3456}"
    local ccr_ready_timeout="${CCR_READY_TIMEOUT:-60}"

    # Clear any stale daemon state before starting, so `ccr start` can't be
    # fooled by a leftover pid/endpoint file from a previous run into thinking a
    # (now-dead) daemon is still up.
    ccr stop >/dev/null 2>&1 || true
    rm -f "${CCR_CONFIG_DIR}/.claude-code-router.pid" \
          "${CCR_CONFIG_DIR}/.pid" \
          /tmp/ccr-supervisor.pid 2>/dev/null || true

    # Start CCR daemon under a supervised restart loop instead of a bare
    # nohup+&. A bare background process that crashes is gone for the rest
    # of the container's life with nothing to restart it; this loop
    # restarts it automatically and appends a timestamped marker each time
    # it exits, so /tmp/ccr.log becomes a timeline of crashes instead of
    # just the one-time startup banner.
    (
        while true; do
            ccr start >> /tmp/ccr.log 2>&1
            exit_code=$?
            echo "$(date '+%F %T'): CCR exited (code ${exit_code}), restarting in 2s..." >> /tmp/ccr.log
            sleep 2
        done
    ) &
    echo $! > /tmp/ccr-supervisor.pid

    # Block until CCR is actually SERVING, not just until a fixed sleep elapses.
    # We require a real HTTP response on the proxy port (curl returns 0 on any
    # HTTP reply; non-zero only on connection refused / no server). An open TCP
    # port can precede the HTTP server being ready, so this is stricter than a
    # plain nc port check and eliminates the race where work starts too early.
    ccr_is_serving() {
        if command -v curl >/dev/null 2>&1; then
            curl -s -o /dev/null -m 4 "http://127.0.0.1:${ccr_port}/" >/dev/null 2>&1
        else
            nc -z 127.0.0.1 "${ccr_port}" >/dev/null 2>&1
        fi
    }

    local waited=0
    until ccr_is_serving; do
        if [ "$waited" -ge "$ccr_ready_timeout" ]; then
            echo -e "${YELLOW}Warning: CCR did not become ready on port ${ccr_port} within ${ccr_ready_timeout}s. Check /tmp/ccr.log${NC}"
            break
        fi
        sleep 2; waited=$((waited+2))
    done

    if ccr_is_serving; then
        echo -e "${GREEN}CCR daemon serving on port ${ccr_port} (ready after ${waited}s)${NC}"
    fi

    # Add CCR activation to .bashrc so it persists in interactive shells
    # Remove any existing ccr activation lines first
    sed -i '/# CCR activation/d' "$BASHRC_FILE" 2>/dev/null || true
    sed -i '/eval "$(ccr activate)"/d' "$BASHRC_FILE" 2>/dev/null || true

    # Add ccr activation to bashrc
    echo "# CCR activation for ${mode}" >> "$BASHRC_FILE"
    echo 'eval "$(ccr activate 2>/dev/null)" || true' >> "$BASHRC_FILE"

    # Also export for the current session (will be inherited by exec'd shell)
    eval "$(ccr activate 2>/dev/null)" || true

    echo -e "${GREEN}CCR activated with ${mode} backend${NC}"
    echo -e "${BLUE}Default model: ${display_model}${NC}"
}

echo ""
echo -e "${BLUE}=== Excalibur Authentication ===${NC}"

case "$AUTH_MODE" in
    openrouter)
        if [ -z "$OPENROUTER_API_KEY" ]; then
            echo -e "${YELLOW}Error: OPENROUTER_API_KEY not set${NC}"
            echo "Please run 'make config' and select OpenRouter option"
            exit 1
        fi
        setup_ccr "openrouter" "$OPENROUTER_API_KEY"
        ;;
    local)
        echo -e "${GREEN}Local LLM mode${NC}"
        echo -e "Ensure your local LLM server is running on host.docker.internal:1234"
        setup_ccr "local" ""
        ;;
    anthropic)
        if [ -z "$ANTHROPIC_API_KEY" ]; then
            echo -e "${YELLOW}Warning: ANTHROPIC_API_KEY not set${NC}"
            echo "Please run 'make config' and select Anthropic option"
        else
            echo -e "${GREEN}Using Anthropic API key${NC}"
        fi
        ;;
    manual)
        echo -e "${YELLOW}Manual login mode${NC}"
        echo -e "Run ${GREEN}claude login${NC} to authenticate"
        ;;
    *)
        echo -e "${YELLOW}Unknown auth mode: $AUTH_MODE${NC}"
        echo "Defaulting to manual login mode"
        echo -e "Run ${GREEN}claude login${NC} to authenticate"
        ;;
esac

echo -e "${BLUE}=================================${NC}"
echo ""

# Execute the passed command or start bash
# Use bash -l to ensure .bashrc is sourced (for ccr activation)
if [ "$1" = "/bin/bash" ]; then
    exec /bin/bash --login
else
    exec "$@"
fi
