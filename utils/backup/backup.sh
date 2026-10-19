#!/usr/bin/env bash
# backup.sh — restic backup of this board's app data and user files. Run as root.
#
# Configured through environment variables (systemd loads /etc/rpi-backup.env, see
# rpi-backup.env.example). Dumps Paperless' Postgres first, since copying a live
# data directory is not a consistent backup.
#
# Reports failures to ntfy (NTFY_URL + NTFY_TOKEN) and, if HC_PING_URL is set, to a
# healthchecks.io-style dead-man's switch, which also catches "never ran at all".
set -Eeuo pipefail

REPO_DIR="$(cd "$(dirname "$0")/../.." && pwd)"
BOARD="$(hostname)"
BOARD_DIR="${REPO_DIR}/${BOARD}"
APPDATA="${APPDATA:-/opt/appdata}"
STORAGE="${STORAGE:-/opt/storage}"
DUMP_DIR="${APPDATA}/backup"
RESTIC_FORGET_ARGS="${RESTIC_FORGET_ARGS:---keep-daily 7 --keep-weekly 4 --keep-monthly 6}"

log() { echo "[backup] $*"; }

ping_hc() {  # ping_hc [/start|/fail] — best effort
    [[ -n "${HC_PING_URL:-}" ]] || return 0
    curl -fsS --max-time 10 --retry 3 -o /dev/null "${HC_PING_URL}${1:-}" || true
}

notify() {  # notify TITLE MESSAGE — best effort
    [[ -n "${NTFY_URL:-}" ]] || return 0
    local args=(-fsS --max-time 10 -o /dev/null -H "Title: $1" -H "Tags: warning" -d "$2")
    if [[ -n "${NTFY_TOKEN:-}" ]]; then
        args+=(-H "Authorization: Bearer ${NTFY_TOKEN}")
    fi
    curl "${args[@]}" "${NTFY_URL}" || true
}

on_error() {
    local rc=$?
    log "FAILED (exit ${rc}) at line ${BASH_LINENO[0]}."
    notify "Backup failed on ${BOARD}" "Exit ${rc}. See: journalctl -u rpi-backup"
    ping_hc /fail
    exit "${rc}"
}
trap on_error ERR

[[ "${EUID}" -eq 0 ]] || { log "Run as root."; exit 1; }
: "${RESTIC_REPOSITORY:?RESTIC_REPOSITORY is not set}"
if [[ -z "${RESTIC_PASSWORD:-}" && -z "${RESTIC_PASSWORD_FILE:-}" ]]; then
    log "RESTIC_PASSWORD or RESTIC_PASSWORD_FILE must be set."
    exit 1
fi

ping_hc /start

mkdir -p "${DUMP_DIR}"
chmod 700 "${DUMP_DIR}"

compose=(docker compose -f "${BOARD_DIR}/docker-compose.yml")
if "${compose[@]}" ps --status running --services 2>/dev/null | grep -qx paperless-postgres; then
    log "Dumping Paperless database..."
    "${compose[@]}" exec -T paperless-postgres \
        pg_dump -U paperless -d paperless --clean --if-exists > "${DUMP_DIR}/paperless.sql.tmp"
    mv "${DUMP_DIR}/paperless.sql.tmp" "${DUMP_DIR}/paperless.sql"
fi

paths=()
for p in "${APPDATA}" "${STORAGE}" "${BOARD_DIR}/config"; do
    if [[ -e "${p}" ]]; then
        paths+=("${p}")
    fi
done
[[ ${#paths[@]} -gt 0 ]] || { log "Nothing to back up."; exit 1; }

if ! restic cat config >/dev/null 2>&1; then
    log "Repository not initialised (or unreachable) — trying restic init..."
    restic init
fi

log "Backing up: ${paths[*]}"
restic backup \
    --tag "${BOARD}" \
    --exclude "${APPDATA}/postgres" \
    --exclude-caches \
    "${paths[@]}"

log "Applying retention: ${RESTIC_FORGET_ARGS}"
# shellcheck disable=SC2086  # intentional word splitting of the retention flags
restic forget --tag "${BOARD}" --prune ${RESTIC_FORGET_ARGS}

restic check

ping_hc
log "Backup complete."
