<#
.SYNOPSIS
  Reads back n8n's own execution history for local/dev evidence lookup --
  "who ran what, when" for a given correlationId, execution id, or a listing
  of recent executions.

.DESCRIPTION
  n8n already saves full execution data by default (community edition, no
  license needed) but stores it in its own internal serialization and
  nothing in this project reads it back. This copies the container's
  database.sqlite out (read-only, so it never contends with n8n's own
  writes) and runs get-execution-trace.mjs against the copy.

  This is a read-only, ad hoc dev tool, not a replacement for the planned
  Evidence Store (persisting ActivityExecution durably at write-time,
  indexed, queryable by the platform itself). See examples/n8n/README.md.

.PARAMETER Container
  Name of the running n8n container. Defaults to the dev-stack's n8n
  (compose.dev.yml). Use "digitax-phase1-demo-n8n" for the presentation
  stack instead.

.EXAMPLE
  ./Get-ExecutionTrace.ps1 -List

.EXAMPLE
  ./Get-ExecutionTrace.ps1 -CorrelationId "34b2e399-29c3-4f87-9a3e-..."

.EXAMPLE
  ./Get-ExecutionTrace.ps1 -ExecutionId 1
#>

param(
    [string]$Container = "digitax-devstack-n8n",
    [string]$CorrelationId,
    [int]$ExecutionId,
    [switch]$List
)

$ErrorActionPreference = "Stop"
$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$tempDb = Join-Path $env:TEMP "n8n-execution-trace-$Container.sqlite"

docker inspect $Container *> $null
if ($LASTEXITCODE -ne 0) {
    Write-Error "Container '$Container' is not running. Start it first (compose.dev.yml or docker-compose.phase1-upload-demo.yml)."
    exit 1
}

docker cp "${Container}:/home/node/.n8n/database.sqlite" $tempDb | Out-Null

if (-not (Test-Path (Join-Path $scriptDir "node_modules/flatted"))) {
    Write-Host "Installing 'flatted' (one-time, build-time-only dev dependency)..." -ForegroundColor Yellow
    Push-Location $scriptDir/..
    npm install flatted --no-save --silent
    Pop-Location
}

$nodeArgs = @("--no-warnings", "$scriptDir/get-execution-trace.mjs", "--db", $tempDb)
if ($List) { $nodeArgs += "--list" }
elseif ($CorrelationId) { $nodeArgs += @("--correlation-id", $CorrelationId) }
elseif ($ExecutionId) { $nodeArgs += @("--execution-id", $ExecutionId) }
else {
    Write-Error "Specify -List, -CorrelationId <id>, or -ExecutionId <id>."
    exit 1
}

node @nodeArgs
