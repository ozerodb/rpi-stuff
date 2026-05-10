#!/usr/bin/env bash
set -euo pipefail

log() { echo "[harden_ssh] $*"; }

SSHD_CONFIG="/etc/ssh/sshd_config"

log "Hardening SSH..."

sed -i 's/^#\?PasswordAuthentication.*/PasswordAuthentication no/' "${SSHD_CONFIG}"
sed -i 's/^#\?PermitRootLogin.*/PermitRootLogin no/' "${SSHD_CONFIG}"
sed -i 's/^#\?ChallengeResponseAuthentication.*/ChallengeResponseAuthentication no/' "${SSHD_CONFIG}"

grep -q '^MaxAuthTries' "${SSHD_CONFIG}" \
    || echo "MaxAuthTries 3" >> "${SSHD_CONFIG}"
grep -q '^ClientAliveInterval' "${SSHD_CONFIG}" \
    || echo "ClientAliveInterval 300" >> "${SSHD_CONFIG}"
grep -q '^ClientAliveCountMax' "${SSHD_CONFIG}" \
    || echo "ClientAliveCountMax 2" >> "${SSHD_CONFIG}"

if systemctl is-active --quiet dropbear 2>/dev/null; then
    log "Disabling Dropbear..."
    systemctl stop dropbear
    systemctl disable dropbear
fi

systemctl enable ssh
systemctl restart ssh
log "SSH hardened and restarted."
