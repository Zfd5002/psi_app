#!/usr/bin/env pwsh
param(
    [string]$SourcePath = ""
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

function Write-Info {
    param([string]$Message)
    Write-Host "[PSI update] $Message"
}

function Fail {
    param([string]$Message)
    Write-Host "[PSI update] ERROR: $Message" -ForegroundColor Red
    exit 1
}

function Resolve-OverlayRoot {
    param([string]$Path)
    if (Test-Path -LiteralPath (Join-Path $Path "overlay_file_list.txt")) {
        return $Path
    }
    $children = Get-ChildItem -LiteralPath $Path -Directory -ErrorAction SilentlyContinue
    if ($children.Count -eq 1) {
        $candidate = $children[0].FullName
        if (Test-Path -LiteralPath (Join-Path $candidate "overlay_file_list.txt")) {
            return $candidate
        }
    }
    return $Path
}

$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$repoRoot = (Resolve-Path (Join-Path $scriptDir "..\..")).Path
Set-Location $repoRoot

foreach ($required in @("psi\version.py", "PATCH_NOTES.md")) {
    if (-not (Test-Path -LiteralPath (Join-Path $repoRoot $required))) {
        Fail "Current folder does not look like a PSI repo root (missing $required)."
    }
}

if (-not $SourcePath) {
    $SourcePath = Read-Host "Enter update package path (.zip or folder)"
}
if (-not $SourcePath) {
    Fail "No update source provided."
}

try {
    $sourceResolved = (Resolve-Path -LiteralPath $SourcePath).Path
} catch {
    Fail "Update source was not found: $SourcePath"
}

$tempRoot = Join-Path ([System.IO.Path]::GetTempPath()) ("psi_update_" + (Get-Date -Format "yyyyMMdd_HHmmss"))
New-Item -ItemType Directory -Path $tempRoot | Out-Null

try {
    if ($sourceResolved.ToLower().EndsWith(".zip")) {
        Write-Info "Extracting update ZIP..."
        Expand-Archive -LiteralPath $sourceResolved -DestinationPath $tempRoot -Force
        $sourceRoot = Resolve-OverlayRoot -Path $tempRoot
    } else {
        $sourceRoot = Resolve-OverlayRoot -Path $sourceResolved
    }

    if (-not (Test-Path -LiteralPath $sourceRoot)) {
        Fail "Could not resolve update content root."
    }

    Write-Info "Applying overlay from:"
    Write-Host "  $sourceRoot"
    Write-Info "Into repo:"
    Write-Host "  $repoRoot"
    Write-Info "Preserving local runtime data (.venv, uploads, sqlite/db files)."

    $excludeDirs = @(
        ".git",
        ".venv",
        "uploads",
        "psi\\uploads",
        "__pycache__",
        ".pytest_cache",
        ".mypy_cache",
        ".ruff_cache"
    )
    $excludeFiles = @(
        "*.sqlite",
        "*.sqlite3",
        "*.sqlite-wal",
        "*.sqlite-shm",
        "*.sqlite-journal",
        "*.db",
        "*.pyc",
        "*.pyo"
    )

    $roboArgs = @(
        $sourceRoot,
        $repoRoot,
        "/E",
        "/R:1",
        "/W:1",
        "/NFL",
        "/NDL",
        "/NJH",
        "/NJS",
        "/NP",
        "/XD"
    ) + $excludeDirs + @("/XF") + $excludeFiles

    $null = & robocopy @roboArgs
    $rc = $LASTEXITCODE
    if ($rc -gt 7) {
        Fail "Update copy failed (robocopy exit code $rc)."
    }

    if (-not (Test-Path -LiteralPath (Join-Path $repoRoot "psi\version.py"))) {
        Fail "Update completed but psi\\version.py is missing."
    }

    Write-Host ""
    Write-Host "[PSI update] Update completed successfully." -ForegroundColor Green
    Write-Host "[PSI update] Local data was preserved (.venv, uploads, sqlite/db files)."
    Write-Host "[PSI update] Next: launch PSI from desktop shortcut or scripts\\windows\\launch_psi.cmd"
    exit 0
} finally {
    if (Test-Path -LiteralPath $tempRoot) {
        Remove-Item -LiteralPath $tempRoot -Recurse -Force -ErrorAction SilentlyContinue
    }
}
