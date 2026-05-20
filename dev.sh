#!/usr/bin/env bash
# Hot-reload dev mode (Linux / macOS).
#
# Backend  : uvicorn --reload    (restarts on any *.py change)
# Frontend : vite dev server     (instant HMR on .ts/.tsx changes)
# Both run concurrently in one terminal; Ctrl+C stops everything.
#
# Defaults to demo mode (C5_DEMO_MODE=1) so it works with no API keys.

set -e
SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" &> /dev/null && pwd)"
cd "$SCRIPT_DIR"

if ! command -v python3 >/dev/null 2>&1; then
  echo "python3 not found (need Python 3.10+)" >&2; exit 1
fi
if ! command -v npm >/dev/null 2>&1; then
  echo "npm not found (need Node 18+)" >&2; exit 1
fi

# --- one-time setup --------------------------------------------------------
if [ ! -d ".venv" ]; then
  echo "==> Creating Python venv (.venv)"
  python3 -m venv .venv
fi
# shellcheck disable=SC1091
source .venv/bin/activate
pip install --quiet --disable-pip-version-check -r requirements.txt

if [ ! -d "node_modules" ]; then
  echo "==> Installing dev-orchestration deps (concurrently)"
  npm install --no-audit --no-fund --silent
fi

if [ ! -d "frontend/node_modules" ]; then
  echo "==> Installing frontend deps (~30s, one-time)"
  (cd frontend && npm install --no-audit --no-fund --silent)
fi

# --- env -------------------------------------------------------------------
export C5_DEMO_MODE=1
export C5_TRADING_MODE=paper
export C5_DB_PATH="$SCRIPT_DIR/c5_demo.sqlite"
rm -f "$C5_DB_PATH"

cat <<EOF

============================================================
  C5 AI Trading - dev mode (hot-reload, demo data)

  Open in your browser:

      http://localhost:5173

  Backend will auto-restart on Python file changes.
  Frontend HMR is instant on .ts / .tsx changes.

  Press Ctrl+C to stop.
============================================================

EOF

exec npm run dev:all
