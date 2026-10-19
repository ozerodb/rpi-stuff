#!/usr/bin/env bash
set -euo pipefail

REPO_DIR="$(cd "$(dirname "$0")/../.." && pwd)"

git -C "${REPO_DIR}" pull origin main

cd "${REPO_DIR}/$(hostname)"
if [[ -f .env.example && ! -f .env ]]; then
    echo "error: $(pwd)/.env is missing — see .env.example and the README. Stack left as is." >&2
    exit 1
fi
docker compose pull
docker compose up -d

echo "Stack on $(hostname) updated and running."
