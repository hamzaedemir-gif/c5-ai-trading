#!/usr/bin/env bash
# Interactive API-key setup for C5 AI Trading (macOS / Linux).
# Mirrors setup-keys.ps1. Prompts -> writes .env (no duplicates) -> validates.
set -e
SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" &> /dev/null && pwd)"
cd "$SCRIPT_DIR"

if [ ! -f ".env" ]; then
  if [ -f ".env.example" ]; then
    cp .env.example .env
    echo "==> Created .env from .env.example"
  else
    : > .env
    echo "==> Created empty .env"
  fi
fi

# Use the Python helper so the upsert logic is shared with the test suite.
upsert() {
  local key="$1" value="$2"
  python3 - <<PY
from core.env_file import update_env_file
update_env_file(".env", {"$key": """$value"""})
PY
}

read_secret() {
  local prompt="$1" var
  if [ -t 0 ]; then
    read -rs -p "$prompt" var; echo
  else
    read -r var
  fi
  printf '%s' "$var"
}

echo
echo "============================================================"
echo "  C5 AI Trading - API key setup"
echo "============================================================"
echo
echo "Press Enter to skip a key (e.g. if it is already valid in .env)."
echo

echo "[1/2] Alpaca (real-time prices, free)"
echo "  Get keys at: https://alpaca.markets -> Paper Trading -> Generate API Keys"
read -r -p "  Alpaca API Key: " ALPACA_KEY
ALPACA_SECRET=$(read_secret "  Alpaca API Secret: ")

echo
echo "[2/2] Finnhub (news + earnings, free)"
echo "  Get a key at: https://finnhub.io -> Sign up -> Dashboard"
read -r -p "  Finnhub API Key: " FINNHUB_KEY

echo
echo "==> Writing .env..."
[ -n "$ALPACA_KEY"    ] && upsert ALPACA_API_KEY    "$ALPACA_KEY"
[ -n "$ALPACA_SECRET" ] && upsert ALPACA_API_SECRET "$ALPACA_SECRET"
[ -n "$FINNHUB_KEY"   ] && upsert FINNHUB_API_KEY   "$FINNHUB_KEY"
upsert C5_DEMO_MODE 0
upsert C5_TRADING_MODE paper
echo "    .env updated (no duplicate lines)"

echo
echo "==> Validating keys with real API calls..."
echo

python3 - <<'PY'
import os, sys
from core.env_file import read_env_keys
from data.alpaca_stream import _iso_from_alpaca_ts  # ensure package imports OK
import urllib.request, urllib.error, json

env = read_env_keys(".env")
ak  = env.get("ALPACA_API_KEY", "")
asec= env.get("ALPACA_API_SECRET", "")
fk  = env.get("FINNHUB_API_KEY", "")

def check_alpaca():
    if not ak or not asec:
        return False, "empty key or secret"
    req = urllib.request.Request(
        "https://paper-api.alpaca.markets/v2/account",
        headers={"APCA-API-KEY-ID": ak, "APCA-API-SECRET-KEY": asec},
    )
    try:
        with urllib.request.urlopen(req, timeout=10) as r:
            body = json.loads(r.read().decode())
            return True, f"account {body.get('account_number','?')}, status {body.get('status','?')}"
    except urllib.error.HTTPError as e:
        return False, f"HTTP {e.code} {e.reason}"
    except Exception as e:
        return False, str(e)

def check_finnhub():
    if not fk:
        return False, "empty key"
    try:
        with urllib.request.urlopen(
            f"https://finnhub.io/api/v1/quote?symbol=AAPL&token={fk}", timeout=10
        ) as r:
            body = json.loads(r.read().decode())
            if body.get("c"):
                return True, f"AAPL quote = ${body['c']}"
            return False, f"response had no price (invalid key?): {body}"
    except urllib.error.HTTPError as e:
        return False, f"HTTP {e.code} {e.reason}"
    except Exception as e:
        return False, str(e)

ok_a, msg_a = check_alpaca()
ok_f, msg_f = check_finnhub()
print(f"  Alpaca:  {'OK ' if ok_a else 'FAILED'}  --  {msg_a}")
print(f"  Finnhub: {'OK ' if ok_f else 'FAILED'}  --  {msg_f}")
sys.exit(0 if (ok_a and ok_f) else 1)
PY
rc=$?

echo
if [ $rc -eq 0 ]; then
  echo "============================================================"
  echo "  All keys valid. Now launch the dashboard with hot-reload:"
  echo
  echo "      ./dev.sh"
  echo
  echo "  Open http://localhost:5173 in your browser."
  echo "============================================================"
else
  echo "============================================================"
  echo "  One or more keys failed validation."
  echo "  Fix the key(s) above and re-run ./setup-keys.sh."
  echo
  echo "  You can still run ./dev.sh right now -- the app will fall"
  echo "  back to demo mode for whatever source is missing keys."
  echo "============================================================"
fi
exit $rc
