#!/usr/bin/env bash
set -euo pipefail

REPO_DIR="$(cd "$(dirname "$0")/../.." && pwd)"

git -C "${REPO_DIR}" pull origin main

cd "${REPO_DIR}/$(hostname)"
docker compose pull
docker compose up -d

echo "Stack on $(hostname) updated and running."
