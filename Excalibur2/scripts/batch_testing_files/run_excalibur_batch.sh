#!/usr/bin/env bash
#
# run_excalibur_batch.sh
#
# Loops through a list of Vulhub CVE directories, brings each one up via
# docker compose, runs the `excalibur` agent (inside its own persistent
# excalibur2 container) against it for a bounded time window, saves the
# real debug log, tears the vulhub environment down, and moves on.
#
# Usage:
#   ./run_excalibur_batch.sh
#
# Configure the variables in the CONFIG section below before running.

set -uo pipefail

# ---------------------------------------------------------------------------
# CONFIG — edit these for your environment
# ---------------------------------------------------------------------------

# Path to your local clone of vulhub (contains dirs like activemq/CVE-2015-5254)
VULHUB_DIR="${VULHUB_DIR:-/path/to/vulhub}"

# Plain text file, one CVE folder per line, optionally with :PORT appended
# to scope excalibur's scan to just that port instead of letting it
# nmap/masscan the whole VM. Examples:
#   activemq/CVE-2015-5254:61616
#   activemq/CVE-2016-3088:8161
#   electron/CVE-2018-1000006
# (no port -> excalibur scans DEFAULT_HOST with no port restriction)
CVE_LIST_FILE="${CVE_LIST_FILE:-./cve_list.txt}"

# Optional sidecar file for per-CVE overrides. Pipe-delimited, one line per
# CVE. See cve_overrides.example.txt for the full field layout.
OVERRIDES_FILE="${OVERRIDES_FILE:-./cve_overrides.txt}"

# Where logs/results get written (one subfolder per CVE)
OUTPUT_DIR="${OUTPUT_DIR:-./excalibur_results}"

# How long excalibur gets to run against each target, in seconds (20 min)
RUN_DURATION="${RUN_DURATION:-1200}"

# How often (seconds) to poll whether the excalibur run has finished
POLL_INTERVAL="${POLL_INTERVAL:-5}"

# Seconds to wait after `docker compose up -d` before probing ports/running
STARTUP_GRACE="${STARTUP_GRACE:-15}"

# Target host handed to excalibur (it does its own nmap/masscan discovery,
# so a bare host is enough — no need to pre-detect the specific published
# port). Since this all runs inside a VM, hardcode the VM's own IP here —
# excalibur (in its own container) reaches vulhub's published ports via the
# VM's IP, not 127.0.0.1 (which would just be the excalibur container
# itself) or host.docker.internal (not guaranteed to resolve in every VM
# networking setup). Since only one CVE's containers are ever up at a time
# in this script, scanning the whole VM is unambiguous.
DEFAULT_HOST="${DEFAULT_HOST:-CHANGE_ME_VM_IP}"

# Name of the already-running excalibur container (per docker-compose.yml's
# container_name), and the host-side path to that project's directory (the
# one containing its docker-compose.yml). The latter is used to read the
# real debug log out of the bind-mounted ./workspace directory.
EXCALIBUR_CONTAINER="${EXCALIBUR_CONTAINER:-excalibur2}"
EXCALIBUR_PROJECT_DIR="${EXCALIBUR_PROJECT_DIR:-/path/to/excalibur/project}"

# `docker exec` bypasses entrypoint.sh's root->pentester privilege drop (that
# only happens for the container's PID 1), so it defaults to root unless we
# tell it otherwise. Claude Code refuses to run with permission_mode
# "bypassPermissions" (--dangerously-skip-permissions) as root, so this must
# match the non-root user entrypoint.sh normally drops to (see the
# claude-config volume mount path in docker-compose.yml: /home/pentester/...).
EXCALIBUR_USER="${EXCALIBUR_USER:-pentester}"

# Directory holding optional per-CVE scripts that must run BEFORE
# `docker compose up -d`. Naming: pre_setup_scripts/<cve with '/' -> '_'>.sh
# Runs with CWD inside the CVE's compose directory. Env vars: CVE, RESULT_DIR.
# Exit non-zero to abort that CVE before anything is brought up.
PRE_SETUP_SCRIPTS_DIR="${PRE_SETUP_SCRIPTS_DIR:-./pre_setup_scripts}"

# Directory holding optional per-CVE setup scripts that run AFTER
# `docker compose up -d` but before excalibur is launched. Naming:
# setup_scripts/<cve with '/' -> '_'>.sh. Same env vars as above.
# Exit non-zero to abort that CVE (treated like a failed compose up).
SETUP_SCRIPTS_DIR="${SETUP_SCRIPTS_DIR:-./setup_scripts}"

# Whether to wipe /tmp and /workspace inside the excalibur container before
# each run. Since EXCALIBUR_CONTAINER is one persistent container reused
# across every CVE (not a fresh one per run), scan output, downloaded
# payloads, and notes the agent writes to these scratch locations otherwise
# persist and can bias/mislead the *next* CVE's run. Set to "false" only if
# you specifically want cross-run continuity for some other reason.
CLEAN_STATE_BEFORE_RUN="${CLEAN_STATE_BEFORE_RUN:-true}"

# Extra seconds to wait after a per-CVE setup script finishes, on top of
# STARTUP_GRACE, before target detection / excalibur runs.
POST_SETUP_GRACE="${POST_SETUP_GRACE:-0}"

# Whether `docker compose down` also removes the images and volumes that
# CVE's stack used, instead of just stopping/removing containers+networks.
# Vulhub compose files typically `build:` a fresh image (or pull a pinned
# version) per CVE, and none of that gets reclaimed by a plain `down` — with
# 50 different CVEs this adds up fast. Set to "false" if you'd rather keep
# images cached (e.g. re-running the same list repeatedly) at the cost of
# disk space.
REMOVE_IMAGES_AFTER_DOWN="${REMOVE_IMAGES_AFTER_DOWN:-true}"

# Every N CVEs, run a full `docker system prune` as a catch-all for anything
# per-project `compose down` doesn't reach — build cache, dangling layers
# from failed/partial builds, unused networks. 0 disables this. This is
# VM-wide (not scoped to vulhub), but safe: images/containers still in use
# (like the running excalibur2 container) are never touched by prune.
PRUNE_EVERY_N_CVES="${PRUNE_EVERY_N_CVES:-5}"

# ---------------------------------------------------------------------------
# END CONFIG
# ---------------------------------------------------------------------------

timestamp() { date '+%Y-%m-%d %H:%M:%S'; }
log()       { echo "[$(timestamp)] $*"; }

mkdir -p "$OUTPUT_DIR"

if [[ ! -d "$VULHUB_DIR" ]]; then
    echo "ERROR: VULHUB_DIR '$VULHUB_DIR' does not exist." >&2
    exit 1
fi

if [[ ! -f "$CVE_LIST_FILE" ]]; then
    echo "ERROR: CVE_LIST_FILE '$CVE_LIST_FILE' not found." >&2
    exit 1
fi

if ! command -v docker >/dev/null 2>&1; then
    echo "ERROR: 'docker' not found on PATH." >&2
    exit 1
fi

if ! docker inspect -f '{{.State.Running}}' "$EXCALIBUR_CONTAINER" 2>/dev/null | grep -q true; then
    echo "ERROR: container '$EXCALIBUR_CONTAINER' is not running. Start it first (docker compose up -d in its project dir)." >&2
    exit 1
fi

if [[ "$DEFAULT_HOST" == "CHANGE_ME_VM_IP" ]]; then
    echo "ERROR: DEFAULT_HOST is still the placeholder. Hardcode the VM's IP at the top of this script (or export DEFAULT_HOST) before running." >&2
    exit 1
fi

DEBUG_LOG_HOST_PATH="${EXCALIBUR_PROJECT_DIR}/workspace/excalibur-debug.log"
if [[ ! -d "${EXCALIBUR_PROJECT_DIR}/workspace" ]]; then
    log "WARNING: '${EXCALIBUR_PROJECT_DIR}/workspace' not found — check EXCALIBUR_PROJECT_DIR. Debug log retrieval will be skipped/best-effort."
fi

# Resolve these to absolute paths up front. The loop below does `pushd` into
# each CVE's own directory to run docker compose, which changes the shell's
# CWD — any of these left as relative paths would then wrongly resolve
# relative to the CVE directory instead of where you started the script.
if [[ -d "$SETUP_SCRIPTS_DIR" ]]; then
    SETUP_SCRIPTS_DIR="$(cd "$SETUP_SCRIPTS_DIR" && pwd)"
fi
if [[ -d "$PRE_SETUP_SCRIPTS_DIR" ]]; then
    PRE_SETUP_SCRIPTS_DIR="$(cd "$PRE_SETUP_SCRIPTS_DIR" && pwd)"
fi
OUTPUT_DIR="$(cd "$OUTPUT_DIR" && pwd)"

# --- Build de-duplicated CVE list, preserving first-seen order -------------
mapfile -t RAW_CVES < <(grep -vE '^\s*(#|$)' "$CVE_LIST_FILE" | sed 's/[[:space:]]*$//')
declare -A SEEN
CVES=()
for c in "${RAW_CVES[@]}"; do
    [[ -z "$c" ]] && continue
    if [[ -z "${SEEN[$c]:-}" ]]; then
        SEEN["$c"]=1
        CVES+=("$c")
    else
        log "Skipping duplicate entry: $c"
    fi
done

log "Loaded ${#CVES[@]} unique CVE targets."

# --- Load overrides, if present --------------------------------------------
# Format: cve/path|host:port override|extra info for -i|inline post-up setup command|inline pre-up setup command
declare -A OVERRIDE_TARGET
declare -A OVERRIDE_INFO
declare -A OVERRIDE_SETUP_CMD
declare -A OVERRIDE_PRE_SETUP_CMD
if [[ -f "$OVERRIDES_FILE" ]]; then
    while IFS='|' read -r cve target extra setup_cmd pre_setup_cmd; do
        [[ -z "$cve" || "$cve" =~ ^# ]] && continue
        OVERRIDE_TARGET["$cve"]="$target"
        OVERRIDE_INFO["$cve"]="$extra"
        OVERRIDE_SETUP_CMD["$cve"]="$setup_cmd"
        OVERRIDE_PRE_SETUP_CMD["$cve"]="$pre_setup_cmd"
    done < "$OVERRIDES_FILE"
    log "Loaded overrides from $OVERRIDES_FILE"
fi

# --- Helper: tear down a CVE's stack thoroughly, reclaiming disk -----------
compose_down_cleanup() {
    local log_target="$1"  # file to append output to, or "-" for /dev/null
    local down_flags=(-v)  # always drop volumes (DB state, etc.)
    if [[ "$REMOVE_IMAGES_AFTER_DOWN" == "true" ]]; then
        down_flags+=(--rmi all)
    fi
    if [[ "$log_target" == "-" ]]; then
        docker compose down "${down_flags[@]}" >/dev/null 2>&1
    else
        docker compose down "${down_flags[@]}" >>"$log_target" 2>&1
    fi
}

log_disk_usage() {
    log "Disk usage: $(df -h / | awk 'NR==2 {print $3" used / "$2" total ("$5" full)"}')"
}

maybe_prune_system() {
    if [[ "$PRUNE_EVERY_N_CVES" -gt 0 && $(( INDEX % PRUNE_EVERY_N_CVES )) -eq 0 ]]; then
        log "Running periodic 'docker system prune' (every ${PRUNE_EVERY_N_CVES} CVEs)..."
        log_disk_usage
        docker system prune -af --volumes >/dev/null 2>&1
        log "Prune complete."
        log_disk_usage
    fi
}

# --- Helper: wipe /tmp and /workspace inside the container ------------------
clean_container_state() {
    if [[ "$CLEAN_STATE_BEFORE_RUN" != "true" ]]; then
        return
    fi
    log "Cleaning /tmp and /workspace inside ${EXCALIBUR_CONTAINER} (avoid cross-run contamination)..."
    docker exec "$EXCALIBUR_CONTAINER" sh -c '
        rm -rf /tmp/* /tmp/.[!.]* 2>/dev/null
        find /workspace -mindepth 1 -delete 2>/dev/null
        true
    ' >/dev/null 2>&1
}

# --- Helper: run excalibur inside the container with a manual timeout ------
# We poll rather than trusting `timeout` on the local `docker exec` client,
# because killing that client does NOT guarantee the remote process inside
# the container dies — it can be left running (and billing) indefinitely.
# On timeout we explicitly pkill the process by name inside the container.
run_excalibur() {
    local target="$1"
    local extra_info="$2"
    local log_file="$3"

    local exec_cmd=(docker exec -i -u "$EXCALIBUR_USER" "$EXCALIBUR_CONTAINER" excalibur --raw -d -t "$target")
    if [[ -n "$extra_info" ]]; then
        exec_cmd+=(-i "$extra_info")
    fi

    "${exec_cmd[@]}" >"$log_file" 2>&1 &
    local pid=$!

    local elapsed=0
    local timed_out=0
    while kill -0 "$pid" 2>/dev/null; do
        sleep "$POLL_INTERVAL"
        elapsed=$((elapsed + POLL_INTERVAL))
        if (( elapsed >= RUN_DURATION )); then
            timed_out=1
            log "Time limit (${RUN_DURATION}s) reached — killing excalibur inside ${EXCALIBUR_CONTAINER}..." >&2
            # Best-effort: requires pgrep/pkill (procps) inside the container image.
            docker exec "$EXCALIBUR_CONTAINER" pkill -f "excalibur --raw -d -t ${target}" >/dev/null 2>&1
            sleep 3
            # Kill the local docker exec client too, in case it's still attached.
            kill "$pid" 2>/dev/null
            break
        fi
    done

    wait "$pid" 2>/dev/null
    local status=$?

    if [[ $timed_out -eq 1 ]]; then
        echo "TIMED_OUT"
    else
        echo "$status"
    fi
}

# --- Main loop ----------------------------------------------------------------
TOTAL=${#CVES[@]}
INDEX=0

for cve in "${CVES[@]}"; do
    INDEX=$((INDEX + 1))

    # Split "cve/path[:port]" into the folder path and optional port
    cve_folder="${cve%%:*}"
    if [[ "$cve_folder" == "$cve" ]]; then
        cve_port=""
    else
        cve_port="${cve#*:}"
    fi

    cve_path="${VULHUB_DIR}/${cve_folder}"
    safe_name="${cve_folder//\//_}"
    result_dir="${OUTPUT_DIR}/${safe_name}"
    mkdir -p "$result_dir"
    log_file="${result_dir}/debug.log"
    meta_file="${result_dir}/meta.txt"

    log "==== [$INDEX/$TOTAL] $cve ===="

    if [[ ! -d "$cve_path" ]]; then
        log "SKIP: directory not found: $cve_path"
        echo "status=missing_directory" > "$meta_file"
        continue
    fi

    pushd "$cve_path" >/dev/null || { log "SKIP: cannot cd into $cve_path"; continue; }

    # --- Pre-up setup step (optional) ---------------------------------------
    pre_setup_script="${PRE_SETUP_SCRIPTS_DIR}/${safe_name}.sh"
    pre_setup_failed=0

    if [[ -f "$pre_setup_script" ]]; then
        log "Running pre-up setup script: $pre_setup_script"
        CVE="$cve_folder" RESULT_DIR="$result_dir" \
            bash "$pre_setup_script" >>"${result_dir}/pre_setup.log" 2>&1
        pre_setup_status=$?
        echo "pre_setup_script=$pre_setup_script" >> "$meta_file"
        echo "pre_setup_script_exit=$pre_setup_status" >> "$meta_file"
        if [[ $pre_setup_status -ne 0 ]]; then
            log "Pre-up setup script for $cve exited non-zero ($pre_setup_status)."
            pre_setup_failed=1
        fi
    fi

    inline_pre_setup="${OVERRIDE_PRE_SETUP_CMD[$cve_folder]:-}"
    if [[ $pre_setup_failed -eq 0 && -n "$inline_pre_setup" ]]; then
        log "Running inline pre-up setup command: $inline_pre_setup"
        bash -c "$inline_pre_setup" >>"${result_dir}/pre_setup.log" 2>&1
        pre_setup_status=$?
        echo "inline_pre_setup_cmd=$inline_pre_setup" >> "$meta_file"
        echo "inline_pre_setup_exit=$pre_setup_status" >> "$meta_file"
        if [[ $pre_setup_status -ne 0 ]]; then
            log "Inline pre-up setup command for $cve exited non-zero ($pre_setup_status)."
            pre_setup_failed=1
        fi
    fi

    if [[ $pre_setup_failed -eq 1 ]]; then
        log "SKIP: pre-up setup failed for $cve, moving on (nothing to tear down yet)."
        echo "status=pre_setup_failed" >> "$meta_file"
        popd >/dev/null
        continue
    fi

    log "Bringing environment up..."
    if ! docker compose up -d >>"${result_dir}/compose_up.log" 2>&1; then
        log "SKIP: docker compose up failed for $cve"
        echo "status=compose_up_failed" >> "$meta_file"
        compose_down_cleanup "-"
        popd >/dev/null
        continue
    fi

    log "Waiting ${STARTUP_GRACE}s for services to settle..."
    sleep "$STARTUP_GRACE"

    # --- Per-CVE setup step (optional) --------------------------------------
    setup_script="${SETUP_SCRIPTS_DIR}/${safe_name}.sh"
    setup_failed=0

    if [[ -f "$setup_script" ]]; then
        log "Running setup script: $setup_script"
        CVE="$cve_folder" RESULT_DIR="$result_dir" \
            bash "$setup_script" >>"${result_dir}/setup.log" 2>&1
        setup_status=$?
        echo "setup_script=$setup_script" >> "$meta_file"
        echo "setup_script_exit=$setup_status" >> "$meta_file"
        if [[ $setup_status -ne 0 ]]; then
            log "Setup script for $cve exited non-zero ($setup_status)."
            setup_failed=1
        fi
    fi

    inline_setup="${OVERRIDE_SETUP_CMD[$cve_folder]:-}"
    if [[ $setup_failed -eq 0 && -n "$inline_setup" ]]; then
        log "Running inline setup command: $inline_setup"
        bash -c "$inline_setup" >>"${result_dir}/setup.log" 2>&1
        setup_status=$?
        echo "inline_setup_cmd=$inline_setup" >> "$meta_file"
        echo "inline_setup_exit=$setup_status" >> "$meta_file"
        if [[ $setup_status -ne 0 ]]; then
            log "Inline setup command for $cve exited non-zero ($setup_status)."
            setup_failed=1
        fi
    fi

    if [[ $setup_failed -eq 1 ]]; then
        log "SKIP: setup failed for $cve, tearing down and moving on."
        echo "status=setup_failed" >> "$meta_file"
        compose_down_cleanup "${result_dir}/compose_down.log"
        popd >/dev/null
        continue
    fi

    if [[ "$POST_SETUP_GRACE" -gt 0 ]]; then
        log "Waiting an extra ${POST_SETUP_GRACE}s after setup..."
        sleep "$POST_SETUP_GRACE"
    fi

    # Resolve target: override file wins (useful for URL-based web challenges
    # or when you want to hand excalibur a specific host:port), otherwise
    # just point it at the host and let it nmap/masscan for itself.
    target="${OVERRIDE_TARGET[$cve_folder]:-}"
    if [[ -z "$target" ]]; then
        if [[ -n "$cve_port" ]]; then
            target="${DEFAULT_HOST}:${cve_port}"
        else
            target="$DEFAULT_HOST"
        fi
    fi

    extra_info="${OVERRIDE_INFO[$cve_folder]:-}"

    clean_container_state

    log "Target resolved to $target. Running excalibur for up to ${RUN_DURATION}s..."
    {
        echo "cve=$cve_folder"
        echo "cve_port=$cve_port"
        echo "target=$target"
        echo "extra_info=$extra_info"
        echo "start_time=$(timestamp)"
    } >> "$meta_file"

    exit_marker="$(run_excalibur "$target" "$extra_info" "$log_file")"

    echo "end_time=$(timestamp)" >> "$meta_file"
    echo "exit_marker=$exit_marker" >> "$meta_file"
    log "Run finished for $cve (exit_marker=$exit_marker). Classification left to you."

    # --- Pull the real debug log out of the bind-mounted workspace ---------
    if [[ -f "$DEBUG_LOG_HOST_PATH" ]]; then
        cp "$DEBUG_LOG_HOST_PATH" "${result_dir}/excalibur-debug.log"
        log "Copied debug log from ${DEBUG_LOG_HOST_PATH}"
    else
        # Fallback path used when /workspace wasn't writable inside the container
        if docker exec "$EXCALIBUR_CONTAINER" test -f /tmp/excalibur-debug.log 2>/dev/null; then
            docker cp "${EXCALIBUR_CONTAINER}:/tmp/excalibur-debug.log" "${result_dir}/excalibur-debug.log" >/dev/null 2>&1
            log "Copied fallback debug log via docker cp from /tmp inside ${EXCALIBUR_CONTAINER}"
        else
            log "WARNING: no excalibur-debug.log found (checked ${DEBUG_LOG_HOST_PATH} and /tmp in container). Only console output (debug.log) is available for $cve."
        fi
    fi

    log "Tearing environment down..."
    compose_down_cleanup "${result_dir}/compose_down.log"

    popd >/dev/null

    maybe_prune_system

    log "Done with $cve. Console output: $log_file"
done

log "Batch complete. Results in $OUTPUT_DIR"
