#!/usr/bin/env bash
set -euo pipefail

log() { echo "[setup_ufw] $*"; }

log "Resetting UFW rules..."
ufw --force reset
ufw default deny incoming
ufw default allow outgoing

# Detect primary LAN subnet (exclude tailscale, loopback, docker)
LAN_SUBNET=$(ip route 2>/dev/null \
    | grep -v 'tailscale\|tun\|docker\|br-\|lo\|default' \
    | awk '/\// {print $1}' \
    | head -1)

if [[ -n "${LAN_SUBNET}" ]]; then
    log "Detected LAN subnet: ${LAN_SUBNET}"
    ufw allow from "${LAN_SUBNET}" to any port 22 proto tcp comment "SSH from LAN"
fi

ufw allow from 100.64.0.0/10 to any port 22 proto tcp comment "SSH from Tailscale"
ufw allow 41641/udp comment "Tailscale WireGuard"

if [[ "$(hostname)" == rpi5* ]]; then
    log "Adding rpi5-specific rules (DNS)..."
    ufw allow from 100.64.0.0/10 to any port 53 comment "DNS from Tailscale"
fi

ufw --force enable
log "UFW enabled."
ufw status verbose
