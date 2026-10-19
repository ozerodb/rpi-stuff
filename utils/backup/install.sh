#!/usr/bin/env bash
# install.sh — install restic and the rpi-backup systemd service + timer. Run as root.
# Re-runnable: never overwrites an existing /etc/rpi-backup.env.
set -euo pipefail

log() { echo "[backup/install] $*"; }

[[ "${EUID}" -eq 0 ]] || { log "Run as root: sudo $0"; exit 1; }

SRC_DIR="$(cd "$(dirname "$0")" && pwd)"
REPO_DIR="$(cd "${SRC_DIR}/../.." && pwd)"
ENV_FILE="/etc/rpi-backup.env"

if ! command -v restic &>/dev/null; then
    log "Installing restic..."
    apt-get install -y -qq restic
fi

if [[ -f "${ENV_FILE}" ]]; then
    log "${ENV_FILE} already exists — leaving it untouched."
else
    install -m 600 -o root -g root "${SRC_DIR}/rpi-backup.env.example" "${ENV_FILE}"
    log "Created ${ENV_FILE} from the example — fill it in."
fi

sed "s|@REPO_DIR@|${REPO_DIR}|g" "${SRC_DIR}/rpi-backup.service" > /etc/systemd/system/rpi-backup.service
install -m 644 "${SRC_DIR}/rpi-backup.timer" /etc/systemd/system/rpi-backup.timer
systemctl daemon-reload

if grep -qE '^RESTIC_PASSWORD=.+' "${ENV_FILE}"; then
    systemctl enable --now rpi-backup.timer
    log "Timer enabled. Run once now with: sudo systemctl start rpi-backup && journalctl -fu rpi-backup"
else
    log "RESTIC_PASSWORD is empty in ${ENV_FILE} — timer NOT enabled yet."
    log "After filling it in: sudo systemctl enable --now rpi-backup.timer"
fi
