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
# Default the trading mode and DB path; do NOT force C5_DEMO_MODE.
# create_app() picks live vs demo automatically based on whether Alpaca
# keys are in .env. Run ./setup-keys.sh once to add them.
export C5_TRADING_MODE="${C5_TRADING_MODE:-paper}"
export C5_DB_PATH="${C5_DB_PATH:-$SCRIPT_DIR/c5_local.sqlite}"

# Detect mode from .env so we can print the right banner.
data_mode="DEMO DATA (no Alpaca keys found in .env)"
if [ -f ".env" ] && grep -E '^\s*ALPACA_API_KEY=.+' .env > /dev/null 2>&1 \
   && grep -E '^\s*ALPACA_API_SECRET=.+' .env > /dev/null 2>&1; then
    data_mode="LIVE DATA (Alpaca IEX websocket)"
fi

cat <<EOF

============================================================
  C5 AI Trading - dev mode (hot-reload)
  Data source: $data_mode

  Open in your browser:

      http://localhost:5173

  Backend will auto-restart on Python file changes.
  Frontend HMR is instant on .ts / .tsx changes.

  To switch from demo to live data, run:  ./setup-keys.sh
  Press Ctrl+C to stop.
============================================================

EOF

exec npm run dev:all
