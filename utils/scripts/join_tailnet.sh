#!/usr/bin/env bash
set -euo pipefail

TAILSCALE_AUTHKEY="${1:-}"

log() { echo "[join_tailnet] $*"; }

if [[ -z "${TAILSCALE_AUTHKEY}" ]]; then
    log "No authkey provided. Skipping automatic Tailscale authentication."
    log "Run manually after boot: tailscale up --ssh"
    [[ "$(hostname)" == rpi5* ]] && log "Then: tailscale set --advertise-exit-node"
    exit 0
fi

log "Authenticating with Tailscale..."
tailscale up --authkey "${TAILSCALE_AUTHKEY}" --ssh

if [[ "$(hostname)" == rpi5* ]]; then
    log "Advertising as exit node..."
    tailscale set --advertise-exit-node
    log "Approve the exit node in the Tailscale admin console."
fi

log "Tailscale status:"
tailscale status
