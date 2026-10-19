#!/usr/bin/env bash
# Usage: harden_ssh.sh [USERNAME]   (default: dietpi) — run as root.
# Writes a drop-in instead of editing sshd_config, validates it, and refuses to
# enforce key-only auth if USERNAME has no authorized_keys (lockout guard).
set -euo pipefail

log() { echo "[harden_ssh] $*"; }
die() { log "ERROR: $*"; exit 1; }

USERNAME="${1:-dietpi}"
SSHD_CONFIG="/etc/ssh/sshd_config"
DROPIN_DIR="/etc/ssh/sshd_config.d"
# sshd uses the first value it reads for each keyword; "00-" sorts ahead of other drop-ins.
DROPIN="${DROPIN_DIR}/00-rpi-hardening.conf"

log "Hardening SSH..."

HOME_DIR="$(getent passwd "${USERNAME}" | cut -d: -f6)"
[[ -n "${HOME_DIR}" ]] || die "user '${USERNAME}' does not exist."
[[ -s "${HOME_DIR}/.ssh/authorized_keys" ]] \
    || die "no authorized_keys for '${USERNAME}' — refusing to disable password login."

mkdir -p "${DROPIN_DIR}"
if ! grep -qE '^[[:space:]]*Include[[:space:]]+/etc/ssh/sshd_config\.d/\*\.conf' "${SSHD_CONFIG}"; then
    log "Adding Include for ${DROPIN_DIR}..."
    sed -i "1i Include ${DROPIN_DIR}/*.conf" "${SSHD_CONFIG}"
fi

cat > "${DROPIN}" << EOF
# Managed by rpi-stuff/utils/scripts/harden_ssh.sh — local edits are overwritten.
PasswordAuthentication no
KbdInteractiveAuthentication no
PubkeyAuthentication yes
PermitRootLogin no
AllowUsers ${USERNAME}
X11Forwarding no
MaxAuthTries 3
LoginGraceTime 30
ClientAliveInterval 300
ClientAliveCountMax 2
EOF
chmod 644 "${DROPIN}"

mkdir -p /run/sshd
if ! sshd -t; then
    rm -f "${DROPIN}"
    die "sshd -t rejected the config — drop-in removed, SSH left unchanged."
fi

if systemctl is-active --quiet dropbear 2>/dev/null; then
    log "Disabling Dropbear..."
    systemctl stop dropbear
    systemctl disable dropbear
fi

systemctl enable ssh
systemctl restart ssh
log "SSH hardened and restarted."
