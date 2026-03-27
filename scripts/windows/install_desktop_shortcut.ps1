#!/usr/bin/env pwsh
Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

function Fail {
    param([string]$Message)
    Write-Host "[PSI shortcut] ERROR: $Message" -ForegroundColor Red
    exit 1
}

$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$repoRoot = (Resolve-Path (Join-Path $scriptDir "..\..")).Path
$launcher = Join-Path $repoRoot "scripts\windows\launch_psi.cmd"
if (-not (Test-Path -LiteralPath $launcher)) {
    Fail "Launcher not found: $launcher"
}

$desktop = [Environment]::GetFolderPath("Desktop")
if (-not $desktop) {
    Fail "Could not resolve Desktop path."
}

$shortcutPath = Join-Path $desktop "PSI.lnk"
$wsh = New-Object -ComObject WScript.Shell
$shortcut = $wsh.CreateShortcut($shortcutPath)
$shortcut.TargetPath = $launcher
$shortcut.WorkingDirectory = $repoRoot
$shortcut.Description = "Launch PSI (Preclinical Systems Intelligence)"
$shortcut.IconLocation = "$env:SystemRoot\System32\shell32.dll,220"
$shortcut.Save()

Write-Host "[PSI shortcut] Installed desktop shortcut:" -ForegroundColor Green
Write-Host "  $shortcutPath"
Write-Host "[PSI shortcut] Double-click 'PSI' on the desktop for daily launch."
exit 0
