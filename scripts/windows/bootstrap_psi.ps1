#!/usr/bin/env pwsh
param(
    [switch]$IncludeHeavyCompute
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

function Write-Info {
    param([string]$Message)
    Write-Host "[PSI bootstrap] $Message"
}

function Write-Warn {
    param([string]$Message)
    Write-Host "[PSI bootstrap] WARNING: $Message" -ForegroundColor Yellow
}

function Fail {
    param([string]$Message)
    Write-Host "[PSI bootstrap] ERROR: $Message" -ForegroundColor Red
    exit 1
}

function Get-PythonLaunchSpec {
    $candidates = @(
        @{ Exe = "py"; Args = @("-3.11") },
        @{ Exe = "py"; Args = @("-3") },
        @{ Exe = "python"; Args = @() }
    )
    foreach ($candidate in $candidates) {
        $cmd = Get-Command $candidate.Exe -ErrorAction SilentlyContinue
        if (-not $cmd) {
            continue
        }
        try {
            & $candidate.Exe @($candidate.Args + @("--version")) *> $null
            if ($LASTEXITCODE -eq 0) {
                return $candidate
            }
        } catch {
            continue
        }
    }
    return $null
}

$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$repoRoot = (Resolve-Path (Join-Path $scriptDir "..\..")).Path
Set-Location $repoRoot

Write-Info "Repo root: $repoRoot"

foreach ($required in @("requirements.txt", "requirements-heavy.txt", "psi\web\asgi.py")) {
    if (-not (Test-Path -LiteralPath (Join-Path $repoRoot $required))) {
        Fail "Required file missing: $required"
    }
}

$writableProbe = Join-Path $repoRoot ".windows_bootstrap_write_test.tmp"
try {
    Set-Content -LiteralPath $writableProbe -Value "ok" -NoNewline
    Remove-Item -LiteralPath $writableProbe -Force
} catch {
    Fail "Install location is not writable. Move PSI to a writable folder (for example: Documents) and retry."
}

$py = Get-PythonLaunchSpec
if (-not $py) {
    Fail "Python 3 was not found. Install Python 3.11 (or newer) from python.org and retry."
}

$versionText = & $py.Exe @($py.Args + @("-c", "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')"))
if ($LASTEXITCODE -ne 0) {
    Fail "Unable to query Python version."
}
$versionParts = $versionText.Trim().Split(".")
if ([int]$versionParts[0] -lt 3 -or ([int]$versionParts[0] -eq 3 -and [int]$versionParts[1] -lt 10)) {
    Fail "Python $versionText is not supported. Use Python 3.10 or newer."
}
Write-Info "Using Python launcher: $($py.Exe) $($py.Args -join ' ')"

if (-not (Test-Path -LiteralPath ".venv\Scripts\python.exe")) {
    Write-Info "Creating local environment (.venv)..."
    & $py.Exe @($py.Args + @("-m", "venv", ".venv"))
    if ($LASTEXITCODE -ne 0) {
        Fail "Failed to create .venv."
    }
} else {
    Write-Info "Using existing .venv."
}

$venvPython = Join-Path $repoRoot ".venv\Scripts\python.exe"
if (-not (Test-Path -LiteralPath $venvPython)) {
    Fail "Expected interpreter missing: .venv\\Scripts\\python.exe"
}

Write-Info "Installing core dependencies (requirements.txt)..."
& $venvPython -m pip install --upgrade pip
if ($LASTEXITCODE -ne 0) {
    Fail "Failed to upgrade pip in .venv."
}

& $venvPython -m pip install -r requirements.txt
if ($LASTEXITCODE -ne 0) {
    Fail "Failed to install core dependencies from requirements.txt."
}

if ($IncludeHeavyCompute) {
    Write-Info "Installing optional heavy-compute dependencies..."
    & $venvPython -m pip install -r requirements-heavy.txt
    if ($LASTEXITCODE -ne 0) {
        Write-Warn "Heavy-compute dependency installation failed. Core PSI is still usable; heavy compute remains optional."
    }
} else {
    Write-Info "Skipping heavy-compute dependency install (optional for Windows baseline)."
}

Write-Info "Running launch preflight imports..."
& $venvPython -c "import uvicorn, psi.web.asgi"
if ($LASTEXITCODE -ne 0) {
    Fail "Preflight import check failed (uvicorn / psi.web.asgi)."
}

Write-Info "Running schema preflight..."
& $venvPython -c "from psi.core.db import ensure_schema; ensure_schema()"
if ($LASTEXITCODE -ne 0) {
    Fail "Schema preflight failed."
}

Write-Info "Bootstrap complete."
Write-Host ""
Write-Host "Core PSI setup is ready in this folder." -ForegroundColor Green
Write-Host "Heavy compute (ANARCI/domain workflows) is optional and may require extra machine-specific setup."
Write-Host ""
Write-Host "Next steps:"
Write-Host "  1) Install shortcut: scripts\\windows\\install_desktop_shortcut.cmd"
Write-Host "  2) Launch PSI:      scripts\\windows\\launch_psi.cmd"
Write-Host "  3) Re-run bootstrap anytime to re-validate setup."
exit 0
