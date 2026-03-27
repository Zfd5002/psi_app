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
    $pathCandidates = @()
    if ($env:LocalAppData) {
        $pathCandidates += (Get-ChildItem -Path (Join-Path $env:LocalAppData "Programs\Python") -Directory -ErrorAction SilentlyContinue | ForEach-Object {
            Join-Path $_.FullName "python.exe"
        })
    }
    if ($env:ProgramFiles) {
        $pathCandidates += (Get-ChildItem -Path (Join-Path $env:ProgramFiles "Python*") -Directory -ErrorAction SilentlyContinue | ForEach-Object {
            Join-Path $_.FullName "python.exe"
        })
    }
    if ($env:ProgramFiles -and $env:ProgramFiles.Contains("x86") -and $env:ProgramW6432) {
        $pathCandidates += (Get-ChildItem -Path (Join-Path $env:ProgramW6432 "Python*") -Directory -ErrorAction SilentlyContinue | ForEach-Object {
            Join-Path $_.FullName "python.exe"
        })
    }

    $candidates = @(
        @{ Exe = "py"; Args = @("-3.11") },
        @{ Exe = "py"; Args = @("-3") },
        @{ Exe = "python"; Args = @() }
    )
    foreach ($p in $pathCandidates | Select-Object -Unique) {
        if (Test-Path -LiteralPath $p) {
            $candidates += @{ Exe = $p; Args = @() }
        }
    }
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

function Get-PythonVersion {
    param([hashtable]$LaunchSpec)
    try {
        $raw = & $LaunchSpec.Exe @($LaunchSpec.Args + @("-c", "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')"))
        if ($LASTEXITCODE -ne 0) {
            return $null
        }
        $text = "$raw".Trim()
        if ($text -notmatch "^\d+\.\d+$") {
            return $null
        }
        $parts = $text.Split(".")
        return @{
            major = [int]$parts[0]
            minor = [int]$parts[1]
            text = $text
        }
    } catch {
        return $null
    }
}

function Is-SupportedPythonVersion {
    param([hashtable]$VersionObj)
    if (-not $VersionObj) {
        return $false
    }
    return ($VersionObj.major -gt 3) -or ($VersionObj.major -eq 3 -and $VersionObj.minor -ge 10)
}

function Install-PythonIfNeeded {
    param([string]$RepoRoot)
    $detected = Get-PythonLaunchSpec
    if ($detected) {
        $detectedVersion = Get-PythonVersion -LaunchSpec $detected
        if (Is-SupportedPythonVersion -VersionObj $detectedVersion) {
            return @{
                launch = $detected
                version = $detectedVersion
            }
        }
        if ($detectedVersion) {
            Write-Warn "Detected unsupported Python $($detectedVersion.text). PSI requires Python 3.10 or newer."
        } else {
            Write-Warn "Detected Python launcher but version check failed. Reinstalling Python is recommended."
        }
    }

    Write-Info "Python 3.10+ was not found. Starting guided Python installation..."
    $installerUrl = "https://www.python.org/ftp/python/3.11.9/python-3.11.9-amd64.exe"
    $dlDir = Join-Path $RepoRoot ".bootstrap_tmp"
    $installerPath = Join-Path $dlDir "python-3.11.9-amd64.exe"
    try {
        New-Item -ItemType Directory -Path $dlDir -Force | Out-Null
    } catch {
        Fail "Could not prepare installer directory: $dlDir"
    }

    try {
        Write-Info "Downloading Python installer..."
        Invoke-WebRequest -Uri $installerUrl -OutFile $installerPath
    } catch {
        Fail "Python download failed. Check internet access and retry."
    }

    if (-not (Test-Path -LiteralPath $installerPath)) {
        Fail "Python installer download was incomplete."
    }

    Write-Info "Running Python installer (this may take a few minutes)..."
    Write-Info "Installer options: per-user install + launcher + PATH update."
    try {
        $proc = Start-Process -FilePath $installerPath -ArgumentList @(
            "/passive",
            "InstallAllUsers=0",
            "PrependPath=1",
            "Include_launcher=1",
            "Include_test=0",
            "Shortcuts=0",
            "SimpleInstall=1"
        ) -Wait -PassThru
    } catch {
        Fail "Could not start Python installer."
    }

    if ($proc.ExitCode -ne 0 -and $proc.ExitCode -ne 3010) {
        Fail "Python installer failed with exit code $($proc.ExitCode)."
    }

    Write-Info "Re-checking Python availability..."
    for ($i = 0; $i -lt 20; $i++) {
        $rechecked = Get-PythonLaunchSpec
        if ($rechecked) {
            $v = Get-PythonVersion -LaunchSpec $rechecked
            if (Is-SupportedPythonVersion -VersionObj $v) {
                return @{
                    launch = $rechecked
                    version = $v
                }
            }
        }
        Start-Sleep -Milliseconds 500
    }

    Fail "Python installation completed, but Python 3.10+ could not be detected. Re-run bootstrap or install Python manually from python.org."
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

$pyInfo = Install-PythonIfNeeded -RepoRoot $repoRoot
$py = $pyInfo.launch
$versionText = $pyInfo.version.text
Write-Info "Using Python launcher: $($py.Exe) $($py.Args -join ' ') (version $versionText)"

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
