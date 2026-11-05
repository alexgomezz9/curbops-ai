#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
(cd backend && python3 -m pytest -q)
(cd frontend && npm run lint && npm run build)
