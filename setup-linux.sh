#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"
command -v node >/dev/null 2>&1 || { echo "Install Node.js 22 or newer first."; exit 1; }
command -v python3 >/dev/null 2>&1 || { echo "Install Python 3.10 or newer first."; exit 1; }
if ! python3 -m venv .venv; then
  echo
  echo "Froja could not create a Python virtual environment."
  echo "On Ubuntu/Debian install it with: sudo apt install python3-venv"
  echo "Then run ./setup-linux.sh again."
  exit 1
fi
.venv/bin/python -m pip install --upgrade pip
.venv/bin/python -m pip install -r requirements.txt
npm install
npm run build
if [ ! -f config/config.local.json ]; then cp config/config.example.json config/config.local.json; fi
echo "Setup complete. Edit config/config.local.json, then run ./start-froja.sh"
