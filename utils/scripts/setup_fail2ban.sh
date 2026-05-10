#!/usr/bin/env bash
set -euo pipefail

log() { echo "[setup_fail2ban] $*"; }

log "Configuring fail2ban..."

cat > /etc/fail2ban/jail.local << 'EOF'
[DEFAULT]
bantime  = 3600
findtime = 600
maxretry = 3

[sshd]
enabled  = true
port     = ssh
EOF

systemctl enable fail2ban
systemctl restart fail2ban
log "fail2ban configured and started."
