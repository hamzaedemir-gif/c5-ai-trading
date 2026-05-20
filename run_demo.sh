#!/usr/bin/env bash
# Launch C5 AI Trading in demo mode WITHOUT Docker.
# - Spawns the FastAPI backend on :8000 with C5_DEMO_MODE=1 (sample data
#   pre-seeded, simulated live ticker, NO API keys required).
# - Spawns the Vite dev server on :5173 and proxies /api -> :8000.
#
# Prereqs: Python 3.10+, Node 18+, pip, npm.
# Usage:   ./run_demo.sh

set -e
SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" &> /dev/null && pwd)"
cd "$SCRIPT_DIR"

echo "==> C5 AI Trading -- DEMO MODE"
echo "==> No API keys required. All data is locally generated sample data."
echo

if ! command -v python3 >/dev/null 2>&1; then
  echo "python3 not found" >&2; exit 1
fi
if ! command -v npm >/dev/null 2>&1; then
  echo "npm not found" >&2; exit 1
fi

# --- Python venv + deps ----------------------------------------------------
if [ ! -d ".venv" ]; then
  echo "==> Creating Python venv (.venv)"
  python3 -m venv .venv
fi
source .venv/bin/activate
pip install --quiet --disable-pip-version-check -r requirements.txt
echo "==> Python deps installed"

# --- Frontend deps ---------------------------------------------------------
if [ ! -d "frontend/node_modules" ]; then
  echo "==> Installing frontend deps (one-time, ~30s)"
  (cd frontend && npm install --no-audit --no-fund --silent)
fi
echo "==> Frontend deps installed"

# --- Launch ---------------------------------------------------------------
export C5_DEMO_MODE=1
export C5_TRADING_MODE=paper
export C5_DB_PATH="$SCRIPT_DIR/c5_demo.sqlite"

# Reset demo DB each run so price seed lines up with "now".
rm -f "$C5_DB_PATH"

cleanup() {
  echo
  echo "==> Stopping services"
  if [ -n "${BACKEND_PID:-}" ]; then kill "$BACKEND_PID" 2>/dev/null || true; fi
  if [ -n "${FRONTEND_PID:-}" ]; then kill "$FRONTEND_PID" 2>/dev/null || true; fi
  wait 2>/dev/null || true
}
trap cleanup EXIT INT TERM

echo "==> Starting backend on http://localhost:8000"
python -m api.app > backend.log 2>&1 &
BACKEND_PID=$!

# Wait for backend /healthz to come up.
for i in $(seq 1 30); do
  if curl -sf http://localhost:8000/healthz > /dev/null; then
    echo "==> Backend is up"
    break
  fi
  sleep 1
done

echo "==> Starting frontend on http://localhost:5173"
(cd frontend && npm run dev -- --host 0.0.0.0 > ../frontend.log 2>&1) &
FRONTEND_PID=$!

# Wait for vite to come up.
for i in $(seq 1 30); do
  if curl -sf http://localhost:5173 > /dev/null; then
    break
  fi
  sleep 1
done

cat <<EOF

============================================================
 C5 AI Trading dashboard is running in DEMO MODE.

 Open this in your browser:

     http://localhost:5173

 Logs:
   backend  -> $SCRIPT_DIR/backend.log
   frontend -> $SCRIPT_DIR/frontend.log

 Disclaimer: analytics & education only. Displays data and
 ranks candidates. Places NO trades. Not financial advice.

 Press Ctrl+C here to stop both services.
============================================================
EOF

wait
