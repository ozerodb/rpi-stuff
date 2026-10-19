#!/usr/bin/env bash
# Usage: sudo provision.sh [USERNAME]   (default: owner of this checkout)
# Applies this repo's host configuration: docker group, UFW, SSH hardening, fail2ban.
# Idempotent — first boot runs it, and it is safe to re-run after every git pull.
# Starting the containers is separate: utils/scripts/update-stack.sh.
set -euo pipefail

SCRIPTS_DIR="$(cd "$(dirname "$0")" && pwd)"
USERNAME="${1:-$(stat -c %U "${SCRIPTS_DIR}")}"

log() { echo "[provision] $*"; }

[[ "${EUID}" -eq 0 ]] || { log "Run as root: sudo $0"; exit 1; }
id "${USERNAME}" &>/dev/null || { log "ERROR: user '${USERNAME}' does not exist."; exit 1; }

log "Provisioning $(hostname) for user '${USERNAME}'..."

usermod -aG docker "${USERNAME}"
log "User '${USERNAME}' is in the docker group."

bash "${SCRIPTS_DIR}/setup_ufw.sh"
bash "${SCRIPTS_DIR}/harden_ssh.sh" "${USERNAME}"
bash "${SCRIPTS_DIR}/setup_fail2ban.sh"

log "Done. Start or update the containers with: ${SCRIPTS_DIR}/update-stack.sh"
