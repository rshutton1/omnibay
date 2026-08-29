#!/usr/bin/env bash
# Bundle the Python engine into the frontend, then serve it. Ctrl-C stops.
set -euo pipefail
cd "$(dirname "$0")"

if [ ! -d frontend/node_modules ]; then
  echo "Installing frontend dependencies…"
  (cd frontend && npm install)
fi

exec npm run dev --prefix frontend
