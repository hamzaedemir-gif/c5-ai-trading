# Hot-reload dev mode (Windows PowerShell).
#
# Backend  : uvicorn --reload  (restarts on any *.py change)
# Frontend : vite dev server   (instant HMR on .ts/.tsx changes)
# Both run concurrently in one terminal; Ctrl+C stops everything.
#
# Defaults to demo mode (C5_DEMO_MODE=1) so it works with no API keys.
#
# Run from PowerShell:
#     .\dev.ps1
#
# If PowerShell blocks the script with an execution-policy error, run this
# once (in the same window):
#     Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass

$ErrorActionPreference = "Stop"
$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Definition
Set-Location $scriptDir

function Require-Cmd($name, $hint) {
  if (-not (Get-Command $name -ErrorAction SilentlyContinue)) {
    Write-Host "ERROR: '$name' not found. $hint" -ForegroundColor Red
    exit 1
  }
}
Require-Cmd python "Install Python 3.10+ from https://www.python.org/downloads/ (tick 'Add Python to PATH')."
Require-Cmd npm    "Install Node 18+ LTS from https://nodejs.org/."

# --- one-time setup --------------------------------------------------------
if (-not (Test-Path ".venv")) {
  Write-Host "==> Creating Python venv (.venv)" -ForegroundColor Green
  python -m venv .venv
}
& "$scriptDir\.venv\Scripts\Activate.ps1"
pip install --quiet --disable-pip-version-check -r requirements.txt | Out-Null

if (-not (Test-Path "node_modules")) {
  Write-Host "==> Installing dev-orchestration deps (concurrently)" -ForegroundColor Green
  npm install --no-audit --no-fund --silent
}

if (-not (Test-Path "frontend\node_modules")) {
  Write-Host "==> Installing frontend deps (~30s, one-time)" -ForegroundColor Green
  Push-Location frontend
  npm install --no-audit --no-fund --silent
  Pop-Location
}

# --- env -------------------------------------------------------------------
# Default the trading mode and DB path. DO NOT force C5_DEMO_MODE here:
# create_app() picks live vs demo automatically based on whether Alpaca
# keys are in .env. Run .\setup-keys.ps1 once to add them.
if (-not $env:C5_TRADING_MODE) { $env:C5_TRADING_MODE = "paper" }
if (-not $env:C5_DB_PATH)      { $env:C5_DB_PATH = Join-Path $scriptDir "c5_local.sqlite" }

$dataMode = "DEMO DATA (no Alpaca keys found in .env)"
if (Test-Path ".env") {
    $envText = Get-Content ".env" -Raw
    if ($envText -match "(?m)^\s*ALPACA_API_KEY=\S" -and `
        $envText -match "(?m)^\s*ALPACA_API_SECRET=\S") {
        $dataMode = "LIVE DATA (Alpaca IEX websocket)"
    }
}

Write-Host ""
Write-Host "============================================================" -ForegroundColor Cyan
Write-Host "  C5 AI Trading - dev mode (hot-reload)"                      -ForegroundColor Cyan
Write-Host "  Data source: $dataMode"                                     -ForegroundColor Cyan
Write-Host ""
Write-Host "  Open in your browser:"                                      -ForegroundColor Cyan
Write-Host ""
Write-Host "      http://localhost:5173"                                  -ForegroundColor Yellow
Write-Host ""
Write-Host "  Backend auto-restarts on Python changes."                   -ForegroundColor Cyan
Write-Host "  Frontend HMR is instant on .ts / .tsx changes."             -ForegroundColor Cyan
Write-Host ""
Write-Host "  To switch from demo to live data, run:  .\setup-keys.ps1"   -ForegroundColor Cyan
Write-Host "  Press Ctrl+C to stop."                                      -ForegroundColor Cyan
Write-Host "============================================================" -ForegroundColor Cyan
Write-Host ""

npm run dev:all
