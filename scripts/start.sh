#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
[ -f .env ] || cp .env.example .env
docker compose up -d postgres s3
docker compose build pipeline
docker compose run --rm pipeline demo --source s3
docker compose run --rm pipeline inspect
