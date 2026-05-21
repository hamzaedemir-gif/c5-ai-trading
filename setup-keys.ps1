# Interactive API-key setup for C5 AI Trading.
#
# Prompts for the three keys you need, validates each with one real HTTP
# request, and writes them into .env atomically (no duplicates, no hand
# editing). Run this once after cloning the repo:
#
#     .\setup-keys.ps1
#
# If PowerShell blocks the script with an execution-policy error, run this
# once in the same window first:
#     Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass

$ErrorActionPreference = "Stop"
$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Definition
Set-Location $scriptDir

# Use TLS 1.2 for older PowerShell defaults.
[System.Net.ServicePointManager]::SecurityProtocol = `
    [System.Net.ServicePointManager]::SecurityProtocol -bor `
    [System.Net.SecurityProtocolType]::Tls12

$envPath = Join-Path $scriptDir ".env"

# ---------- helpers --------------------------------------------------------

function Set-EnvVar([string]$key, [string]$value) {
    $lines = if (Test-Path $envPath) { Get-Content $envPath } else { @() }
    if ($null -eq $lines) { $lines = @() }
    $seen = $false
    $newLines = @()
    foreach ($line in $lines) {
        $trim = $line.TrimStart()
        if ($trim -match "^$([regex]::Escape($key))=" -and -not $trim.StartsWith("#")) {
            if (-not $seen) {
                $newLines += "$key=$value"
                $seen = $true
            }
            # else: collapse duplicate
        } else {
            $newLines += $line
        }
    }
    if (-not $seen) { $newLines += "$key=$value" }
    Set-Content -Path $envPath -Value $newLines -Encoding UTF8
}

function Read-Secret([string]$prompt) {
    $secure = Read-Host -AsSecureString -Prompt $prompt
    $bstr = [System.Runtime.InteropServices.Marshal]::SecureStringToBSTR($secure)
    try {
        return [System.Runtime.InteropServices.Marshal]::PtrToStringBSTR($bstr)
    } finally {
        [System.Runtime.InteropServices.Marshal]::ZeroFreeBSTR($bstr)
    }
}

function Test-Alpaca([string]$key, [string]$secret) {
    if (-not $key -or -not $secret) {
        return @{ ok = $false; error = "empty key or secret" }
    }
    $headers = @{
        "APCA-API-KEY-ID"     = $key
        "APCA-API-SECRET-KEY" = $secret
    }
    try {
        $r = Invoke-WebRequest -Uri "https://paper-api.alpaca.markets/v2/account" `
            -Headers $headers -UseBasicParsing -TimeoutSec 10
        if ($r.StatusCode -eq 200) {
            $info = $r.Content | ConvertFrom-Json
            return @{ ok = $true; status = $info.status; account_number = $info.account_number }
        }
        return @{ ok = $false; error = "HTTP $($r.StatusCode)" }
    } catch {
        $msg = $_.Exception.Message
        # Trim the leading "The remote server returned an error: " noise.
        return @{ ok = $false; error = $msg }
    }
}

function Test-Finnhub([string]$key) {
    if (-not $key) { return @{ ok = $false; error = "empty key" } }
    try {
        $r = Invoke-WebRequest -Uri "https://finnhub.io/api/v1/quote?symbol=AAPL&token=$key" `
            -UseBasicParsing -TimeoutSec 10
        if ($r.StatusCode -eq 200) {
            $info = $r.Content | ConvertFrom-Json
            if ($info.c -ne $null -and $info.c -gt 0) {
                return @{ ok = $true; aapl_price = $info.c }
            }
            return @{ ok = $false; error = "response had no price (invalid key?)" }
        }
        return @{ ok = $false; error = "HTTP $($r.StatusCode)" }
    } catch {
        return @{ ok = $false; error = $_.Exception.Message }
    }
}

# ---------- ensure .env exists ---------------------------------------------

if (-not (Test-Path $envPath)) {
    if (Test-Path ".env.example") {
        Copy-Item ".env.example" $envPath
        Write-Host "==> Created .env from .env.example" -ForegroundColor Cyan
    } else {
        New-Item -ItemType File -Path $envPath | Out-Null
        Write-Host "==> Created empty .env" -ForegroundColor Cyan
    }
}

Write-Host ""
Write-Host "============================================================" -ForegroundColor Green
Write-Host "  C5 AI Trading - API key setup"                               -ForegroundColor Green
Write-Host "============================================================" -ForegroundColor Green
Write-Host ""
Write-Host "We will:"
Write-Host "  1. Ask for your Alpaca key + secret (free, real-time prices)"
Write-Host "  2. Ask for your Finnhub key (free, news + earnings)"
Write-Host "  3. Write them into .env (replacing any existing values)"
Write-Host "  4. Validate each one with a real API call"
Write-Host ""
Write-Host "Press Enter to skip a key (e.g. if it is already valid in .env)."
Write-Host ""

# ---------- Alpaca ---------------------------------------------------------

Write-Host "[1/2] Alpaca" -ForegroundColor Yellow
Write-Host "  Get keys at: https://alpaca.markets -> Paper Trading -> Generate API Keys"
$alpacaKey    = Read-Host    "  Alpaca API Key"
$alpacaSecret = Read-Secret  "  Alpaca API Secret"

# ---------- Finnhub --------------------------------------------------------

Write-Host ""
Write-Host "[2/2] Finnhub" -ForegroundColor Yellow
Write-Host "  Get a key at: https://finnhub.io -> Sign up -> Dashboard"
$finnhubKey = Read-Host "  Finnhub API Key"

# ---------- write .env (atomic) --------------------------------------------

Write-Host ""
Write-Host "==> Writing .env..." -ForegroundColor Cyan
if ($alpacaKey)    { Set-EnvVar "ALPACA_API_KEY"    $alpacaKey }
if ($alpacaSecret) { Set-EnvVar "ALPACA_API_SECRET" $alpacaSecret }
if ($finnhubKey)   { Set-EnvVar "FINNHUB_API_KEY"   $finnhubKey }
# Make sure the new key-based detection wins over a stale forced-demo flag.
Set-EnvVar "C5_DEMO_MODE" "0"
Set-EnvVar "C5_TRADING_MODE" "paper"
Write-Host "    .env updated (no duplicate lines)" -ForegroundColor Green

# ---------- validate -------------------------------------------------------

Write-Host ""
Write-Host "==> Validating keys with real API calls..." -ForegroundColor Cyan
Write-Host ""

# Re-read what we just wrote so we validate exactly what the app will see.
$envNow = Get-Content $envPath | Where-Object { $_ -match "^\s*[A-Z_]+=" } |
    ForEach-Object {
        $parts = $_.Split("=", 2)
        [PSCustomObject]@{ Key = $parts[0].Trim(); Value = $parts[1].Trim() }
    }
$envMap = @{}
foreach ($e in $envNow) { $envMap[$e.Key] = $e.Value }

$alpacaResult  = Test-Alpaca  $envMap["ALPACA_API_KEY"] $envMap["ALPACA_API_SECRET"]
$finnhubResult = Test-Finnhub $envMap["FINNHUB_API_KEY"]

if ($alpacaResult.ok) {
    Write-Host ("  Alpaca:  OK  (account {0}, status {1})" -f `
        $alpacaResult.account_number, $alpacaResult.status) -ForegroundColor Green
} else {
    Write-Host ("  Alpaca:  FAILED  --  {0}" -f $alpacaResult.error) -ForegroundColor Red
}

if ($finnhubResult.ok) {
    Write-Host ("  Finnhub: OK  (AAPL quote = ${0})" -f $finnhubResult.aapl_price) `
        -ForegroundColor Green
} else {
    Write-Host ("  Finnhub: FAILED  --  {0}" -f $finnhubResult.error) -ForegroundColor Red
}

Write-Host ""

# ---------- final summary --------------------------------------------------

$allOk = $alpacaResult.ok -and $finnhubResult.ok
if ($allOk) {
    Write-Host "============================================================" -ForegroundColor Green
    Write-Host "  All keys valid. Now launch the dashboard with hot-reload:"  -ForegroundColor Green
    Write-Host ""
    Write-Host "      .\dev.ps1"                                                -ForegroundColor Yellow
    Write-Host ""
    Write-Host "  Open http://localhost:5173 in your browser."                  -ForegroundColor Green
    Write-Host "============================================================" -ForegroundColor Green
    exit 0
} else {
    Write-Host "============================================================" -ForegroundColor Yellow
    Write-Host "  One or more keys failed validation."                          -ForegroundColor Yellow
    Write-Host "  Fix the key(s) above and re-run .\setup-keys.ps1."            -ForegroundColor Yellow
    Write-Host ""
    Write-Host "  You can still run .\dev.ps1 right now -- the app will fall"   -ForegroundColor Yellow
    Write-Host "  back to demo mode for whatever source is missing keys."       -ForegroundColor Yellow
    Write-Host "============================================================" -ForegroundColor Yellow
    exit 1
}
