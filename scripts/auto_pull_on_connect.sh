#!/usr/bin/env bash
# ==============================================================================
# ELLA Auto-Pull on Internet Connection Script
# Automatically pulls latest git changes whenever internet connection is detected.
# ==============================================================================

set -u

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
LOG_DIR="${SCRIPT_DIR}/data/logs"
LOG_FILE="${LOG_DIR}/auto_pull.log"
CHECK_INTERVAL=${CHECK_INTERVAL:-15}

mkdir -p "${LOG_DIR}"

log_msg() {
    local msg="[$(date '+%Y-%m-%d %H:%M:%S')] $1"
    echo "${msg}"
    echo "${msg}" >> "${LOG_FILE}"
}

check_internet() {
    # Check DNS resolution & HTTP connection to github.com
    if command -v curl >/dev/null 2>&1; then
        curl -s --head --request GET --connect-timeout 4 --max-time 6 https://github.com >/dev/null 2>&1
        return $?
    else
        ping -c 1 -W 3 github.com >/dev/null 2>&1
        return $?
    fi
}

do_git_pull() {
    cd "${SCRIPT_DIR}" || return 1

    if ! git rev-parse --is-inside-work-tree >/dev/null 2>&1; then
        log_msg "ERROR: ${SCRIPT_DIR} is not a valid git repository."
        return 1
    fi

    local current_branch
    current_branch=$(git rev-parse --abbrev-ref HEAD 2>/dev/null)
    if [ -z "${current_branch}" ] || [ "${current_branch}" = "HEAD" ]; then
        log_msg "WARNING: Detached HEAD or invalid branch state. Skipping auto-pull."
        return 1
    fi

    log_msg "Internet connection detected. Checking for updates on branch '${current_branch}'..."

    # Check if working tree has local modifications
    local is_dirty=0
    if [ -n "$(git status --porcelain 2>/dev/null)" ]; then
        is_dirty=1
        log_msg "Local uncommitted changes detected. Stashing changes..."
        git stash save "auto-pull-stash-$(date +%s)" >> "${LOG_FILE}" 2>&1
    fi

    # Fetch and pull
    log_msg "Executing git fetch origin..."
    if git fetch origin >> "${LOG_FILE}" 2>&1; then
        local local_hash remote_hash
        local_hash=$(git rev-parse HEAD 2>/dev/null)
        remote_hash=$(git rev-parse "origin/${current_branch}" 2>/dev/null)

        if [ "${local_hash}" != "${remote_hash}" ]; then
            log_msg "New changes detected! Pulling origin/${current_branch}..."
            if git pull origin "${current_branch}" >> "${LOG_FILE}" 2>&1; then
                log_msg "SUCCESS: Repository updated to $(git rev-parse --short HEAD)."
            else
                log_msg "ERROR: git pull failed. Check ${LOG_FILE} for details."
            fi
        else
            log_msg "Repository is already up to date."
        fi
    else
        log_msg "WARNING: Unable to fetch from origin."
    fi

    # Restore stashed changes if any were saved
    if [ "${is_dirty}" -eq 1 ]; then
        log_msg "Restoring local stashed changes..."
        git stash pop >> "${LOG_FILE}" 2>&1
    fi
}

run_once() {
    if check_internet; then
        do_git_pull
    else
        log_msg "Offline: Internet connection not reachable."
    fi
}

run_daemon() {
    log_msg "Starting ELLA Auto-Pull daemon (polling every ${CHECK_INTERVAL}s)..."
    local was_online=0

    while true; do
        if check_internet; then
            if [ "${was_online}" -eq 0 ]; then
                log_msg "Network state changed: OFFLINE -> ONLINE."
                do_git_pull
                was_online=1
            fi
        else
            if [ "${was_online}" -eq 1 ]; then
                log_msg "Network state changed: ONLINE -> OFFLINE."
                was_online=0
            fi
        fi
        sleep "${CHECK_INTERVAL}"
    done
}

# Command line mode dispatch
case "${1:-daemon}" in
    --once|once)
        run_once
        ;;
    --daemon|daemon)
        run_daemon
        ;;
    *)
        echo "Usage: $0 [--once | --daemon]"
        exit 1
        ;;
esac
