#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"

echo "=================================================="
echo "              Froja Image Studio"
echo "=================================================="
echo "Models remain in your own folders and are never copied."

if ! command -v node >/dev/null 2>&1; then
  echo "ERROR: Node.js 22 or newer is required."
  exit 1
fi

if [ ! -d node_modules ]; then npm install; fi
if [ ! -f dist/index.html ]; then npm run build; fi

PYTHON="python3"
if [ -x .venv/bin/python ]; then PYTHON=".venv/bin/python"; fi

(sleep 2; command -v xdg-open >/dev/null 2>&1 && xdg-open http://127.0.0.1:3000 >/dev/null 2>&1 || true) &
exec "$PYTHON" backend.py
