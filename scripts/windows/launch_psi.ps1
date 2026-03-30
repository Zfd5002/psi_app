#!/usr/bin/env pwsh
param(
    [switch]$NoBrowser,
    [switch]$Dev,
    [Alias("Host")]
    [string]$BindHost = "",
    [int]$Port = 0
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

function Write-Info {
    param([string]$Message)
    Write-Host "[PSI launch] $Message"
}

function Fail {
    param([string]$Code, [string]$Message)
    Write-Host "❌ $Code" -ForegroundColor Red
    Write-Host "   $Message"
    exit 1
}

function Test-PortInUse {
    param([string]$CheckHost, [int]$CheckPort)
    $client = New-Object System.Net.Sockets.TcpClient
    try {
        $iar = $client.BeginConnect($CheckHost, $CheckPort, $null, $null)
        if (-not $iar.AsyncWaitHandle.WaitOne(250)) {
            return $false
        }
        $client.EndConnect($iar) | Out-Null
        return $true
    } catch {
        return $false
    } finally {
        $client.Close()
    }
}

$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$repoRoot = (Resolve-Path (Join-Path $scriptDir "..\..")).Path
Set-Location $repoRoot

$resolvedHost = if ($BindHost) { $BindHost } elseif ($env:PSI_HOST) { $env:PSI_HOST } else { "127.0.0.1" }
$resolvedPort = if ($Port -gt 0) { $Port } elseif ($env:PSI_PORT) { [int]$env:PSI_PORT } else { 8000 }
$openBrowser = if ($NoBrowser) { $false } elseif ($env:PSI_OPEN_BROWSER -eq "0") { $false } else { $true }

$venvPython = Join-Path $repoRoot ".venv\Scripts\python.exe"
if (-not (Test-Path -LiteralPath $venvPython)) {
    Fail "launch:error:env_missing" "Setup is incomplete (.venv\\Scripts\\python.exe not found). Run scripts\\windows\\bootstrap_psi.cmd first."
}

& $venvPython -c "import uvicorn, psi.web.asgi"
if ($LASTEXITCODE -ne 0) {
    Fail "launch:error:dependency_missing" "Could not import launch dependencies (uvicorn / psi.web.asgi). Re-run scripts\\windows\\bootstrap_psi.cmd."
}

$url = "http://$resolvedHost`:$resolvedPort"
if (Test-PortInUse -CheckHost $resolvedHost -CheckPort $resolvedPort) {
    Write-Host "⚠️ launch:error:port_in_use" -ForegroundColor Yellow
    Write-Host "   $resolvedHost`:$resolvedPort is already in use."
    Write-Host "   If PSI is already running, this launcher will open it in your browser."
    if ($openBrowser) {
        Start-Process $url | Out-Null
    }
    exit 0
}

$uvicornArgs = @("-m", "uvicorn", "psi.web.asgi:app", "--host", $resolvedHost, "--port", "$resolvedPort")
if ($Dev) {
    $uvicornArgs += "--reload"
}

$mode = if ($Dev) { "dev" } else { "user" }
Write-Info "mode=$mode"
Write-Info "entrypoint=psi.web.asgi:app"
Write-Info "bind=$url"

try {
    $proc = Start-Process -FilePath $venvPython -ArgumentList $uvicornArgs -WorkingDirectory $repoRoot -PassThru
} catch {
    Fail "launch:error:runtime_failed" "Unable to start the PSI server process."
}

if ($openBrowser) {
    $deadline = (Get-Date).AddSeconds(12)
    $opened = $false
    while ((Get-Date) -lt $deadline) {
        $proc.Refresh()
        if ($proc.HasExited) {
            break
        }
        if (Test-PortInUse -CheckHost $resolvedHost -CheckPort $resolvedPort) {
            Start-Process $url | Out-Null
            $opened = $true
            break
        }
        Start-Sleep -Milliseconds 300
    }
    if (-not $opened) {
        Write-Host "[PSI launch] Browser auto-open skipped (server did not become ready within startup window)." -ForegroundColor Yellow
    }
}

Wait-Process -Id $proc.Id
$proc.Refresh()
if ($proc.ExitCode -ne 0) {
    Fail "launch:error:runtime_failed" "PSI server exited unexpectedly."
}
exit 0
