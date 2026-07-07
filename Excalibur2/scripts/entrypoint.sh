#!/usr/bin/env bash
# Excalibur Container Entrypoint
# Starts SSH, the web config UI, and authentication based on EXCALIBUR_AUTH_MODE.

set -e

AUTH_MODE="${EXCALIBUR_AUTH_MODE:-manual}"
CCR_CONFIG_DIR="/home/pentester/.claude-code-router"
CCR_CONFIG_FILE="${CCR_CONFIG_DIR}/config.json"
CCR_TEMPLATE_FILE="/app/scripts/ccr-config-template.json"
CCR_LOG_FILE="${EXCALIBUR_CCR_LOG:-/tmp/ccr.log}"
RUNTIME_CONFIG_FILE="${EXCALIBUR_RUNTIME_CONFIG:-/workspace/excalibur.yml}"
SSH_PASSWORD="${EXCALIBUR_SSH_PASSWORD:-excalibur}"
SSH_PORT="${EXCALIBUR_SSH_PORT:-22}"
WEB_HOST="${EXCALIBUR_WEB_HOST:-0.0.0.0}"
WEB_PORT="${EXCALIBUR_WEB_PORT:-8080}"

# Colors for output
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[0;33m'
NC='\033[0m'

# Router configurations for different modes
OPENROUTER_ROUTER='{"default":"openrouter,openai/gpt-5.1","background":"openrouter,openai/gpt-5.1","think":"openrouter,openai/gpt-5.1","longContext":"openrouter,openai/gpt-5.1","longContextThreshold":60000,"webSearch":"openrouter,google/gemini-3-pro-preview"}'

run_as_pentester() {
    gosu pentester "$@"
}

ensure_permissions() {
    mkdir -p /workspace "$CCR_CONFIG_DIR" /home/pentester/.claude /home/pentester/.ssh
    if [ ! -f /home/pentester/.claude.json ]; then
        echo '{}' > /home/pentester/.claude.json
    fi
    chown -R pentester:pentester /workspace "$CCR_CONFIG_DIR" /home/pentester/.claude /home/pentester/.ssh
    chown pentester:pentester /home/pentester/.claude.json
    chmod 700 /home/pentester/.ssh
    chmod 600 /home/pentester/.claude.json
}

ensure_ccr_activation() {
    run_as_pentester python3 - <<'PY'
from pathlib import Path

from excalibur.server.web_config import ensure_bashrc_activation

ensure_bashrc_activation(Path("/home/pentester/.bashrc"))
PY
}

start_ssh() {
    mkdir -p /run/sshd
    ssh-keygen -A >/dev/null 2>&1 || true

    if [ -n "$EXCALIBUR_SSH_AUTHORIZED_KEYS" ]; then
        printf '%s\n' "$EXCALIBUR_SSH_AUTHORIZED_KEYS" > /home/pentester/.ssh/authorized_keys
        chown pentester:pentester /home/pentester/.ssh/authorized_keys
        chmod 600 /home/pentester/.ssh/authorized_keys
    fi

    if [ -n "$SSH_PASSWORD" ]; then
        echo "pentester:${SSH_PASSWORD}" | chpasswd
    fi

    if ! pgrep -x sshd >/dev/null 2>&1; then
        echo -e "${BLUE}Starting SSH on port ${SSH_PORT}...${NC}"
        /usr/sbin/sshd -o "Port=${SSH_PORT}"
    fi
}

start_web_config() {
    if [ "${EXCALIBUR_WEB_ENABLED:-true}" != "true" ]; then
        return
    fi

    if pgrep -f "excalibur.server.web_config" >/dev/null 2>&1; then
        return
    fi

    echo -e "${BLUE}Starting config UI on port ${WEB_PORT}...${NC}"
    run_as_pentester env \
        EXCALIBUR_WEB_HOST="$WEB_HOST" \
        EXCALIBUR_WEB_PORT="$WEB_PORT" \
        EXCALIBUR_CCR_CONFIG="$CCR_CONFIG_FILE" \
        EXCALIBUR_CCR_TEMPLATE="$CCR_TEMPLATE_FILE" \
        EXCALIBUR_CCR_LOG="$CCR_LOG_FILE" \
        EXCALIBUR_RUNTIME_CONFIG="$RUNTIME_CONFIG_FILE" \
        nohup python3 -m excalibur.server.web_config > /tmp/excalibur-web.log 2>&1 &
}

start_ccr() {
    echo -e "${BLUE}Starting Claude Code Router...${NC}"

    run_as_pentester bash -lc "ccr stop >/tmp/ccr-stop.log 2>&1 || true"
    run_as_pentester bash -lc "nohup ccr start > '${CCR_LOG_FILE}' 2>&1 &"

    # Wait for CCR to be ready
    sleep 3

    # Check if CCR is running by testing the port
    if nc -z 127.0.0.1 3456 2>/dev/null; then
        echo -e "${GREEN}CCR daemon running on port 3456${NC}"
    else
        echo -e "${YELLOW}Warning: CCR may not have started properly. Check ${CCR_LOG_FILE}${NC}"
    fi
}

setup_ccr() {
    local mode="$1"
    local api_key="$2"

    # Create CCR config directory if needed
    mkdir -p "$CCR_CONFIG_DIR"

    # Check if template exists
    if [ ! -f "$CCR_TEMPLATE_FILE" ]; then
        echo -e "${YELLOW}Error: CCR config template not found at $CCR_TEMPLATE_FILE${NC}"
        exit 1
    fi

    if [ "$mode" = "openrouter" ]; then
        # Copy template and substitute placeholders for OpenRouter mode.
        cp "$CCR_TEMPLATE_FILE" "$CCR_CONFIG_FILE"
        if [ -n "$api_key" ]; then
            sed -i "s/__OPENROUTER_API_KEY__/${api_key}/g" "$CCR_CONFIG_FILE"
        fi
        sed -i "s|\"__ROUTER_CONFIG__\"|${OPENROUTER_ROUTER}|g" "$CCR_CONFIG_FILE"
        local display_model="openai/gpt-5.1"
    else
        if [ -f "$RUNTIME_CONFIG_FILE" ]; then
            if ! run_as_pentester excalibur-run \
                --config "$RUNTIME_CONFIG_FILE" \
                --ccr-config "$CCR_CONFIG_FILE" \
                --ccr-template "$CCR_TEMPLATE_FILE" \
                --ccr-log "$CCR_LOG_FILE" \
                --configure-only \
                --no-restart-router \
                --skip-mcp; then
                ensure_ccr_activation
                echo -e "${YELLOW}Could not apply ${RUNTIME_CONFIG_FILE}. Open the web UI and save a valid model config.${NC}"
                return
            fi
            local display_model="configured in ${RUNTIME_CONFIG_FILE}"
        elif [ -f "$CCR_CONFIG_FILE" ]; then
            if run_as_pentester env \
                CCR_CONFIG_FILE="$CCR_CONFIG_FILE" \
                RUNTIME_CONFIG_FILE="$RUNTIME_CONFIG_FILE" \
                python3 - <<'PY'
from pathlib import Path
import os

from excalibur.server.local_llm_config import load_config, settings_from_config
from excalibur.server.runtime_config import save_runtime_config

ccr_config = Path(os.environ["CCR_CONFIG_FILE"])
runtime_config = Path(os.environ["RUNTIME_CONFIG_FILE"])
settings = settings_from_config(load_config(ccr_config, None))
save_runtime_config(settings, runtime_config)
PY
            then
                local display_model="migrated from existing CCR config"
            else
                ensure_ccr_activation
                echo -e "${YELLOW}Could not load existing CCR config. Open the web UI, fetch models, then save.${NC}"
                echo -e "${BLUE}YAML config will be saved at ${RUNTIME_CONFIG_FILE}${NC}"
                return
            fi
        elif [ -n "${EXCALIBUR_LOCAL_LLM_MODEL:-}" ] || [ -n "${EXCALIBUR_LOCAL_LLM_MODELS:-}" ]; then
            local enforce_ssl_args=()
            if [ "${EXCALIBUR_LOCAL_LLM_ENFORCE_SSL:-false}" = "true" ]; then
                enforce_ssl_args=(--enforce-ssl)
            fi
            run_as_pentester python3 -m excalibur.server.local_llm_config init \
                --config "$CCR_CONFIG_FILE" \
                --template "$CCR_TEMPLATE_FILE" \
                --provider-type "${EXCALIBUR_LOCAL_LLM_PROVIDER_TYPE:-openai-compatible}" \
                --api-base-url "${EXCALIBUR_LOCAL_LLM_API_BASE_URL:-http://host.docker.internal:1234/v1/chat/completions}" \
                --models "${EXCALIBUR_LOCAL_LLM_MODELS:-${EXCALIBUR_LOCAL_LLM_MODEL}}" \
                --selected-model "${EXCALIBUR_LOCAL_LLM_MODEL:-}" \
                --context-window "${EXCALIBUR_LOCAL_LLM_CONTEXT_WINDOW:-60000}" \
                "${enforce_ssl_args[@]}"
            local display_model="localLLM (${EXCALIBUR_LOCAL_LLM_MODEL:-configured by env})"
        else
            ensure_ccr_activation
            echo -e "${YELLOW}No local model configured yet. Open the web UI, fetch models, then save.${NC}"
            echo -e "${BLUE}YAML config will be saved at ${RUNTIME_CONFIG_FILE}${NC}"
            return
        fi
    fi

    chown pentester:pentester "$CCR_CONFIG_FILE"
    ensure_ccr_activation
    start_ccr

    echo -e "${GREEN}CCR activated with ${mode} backend${NC}"
    echo -e "${BLUE}Default model: ${display_model}${NC}"
}

ensure_permissions
start_ssh
start_web_config

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
        echo -e "Configure models at http://127.0.0.1:${WEB_PORT}"
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
    exec gosu pentester /bin/bash --login
else
    # Filter to export/unset lines only: `ccr activate` prints stray status
    # text to stdout the first time it creates its config file, and eval'ing
    # that raw would try to run it as shell commands.
    exec gosu pentester /bin/bash -lc 'eval "$(ccr activate 2>/dev/null | grep -E "^(export|unset) ")" || true; exec "$@"' bash "$@"
fi
