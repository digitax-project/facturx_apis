<#
.SYNOPSIS
  Deterministic sync/check for the invoice-intake activity binding lockfile
  (examples/n8n/activity_binding.invoice_intake.json), generated only from
  A6's vendored, hash-pinned export -- never hand-edited.

.DESCRIPTION
  -Regenerate is the only way the vendored snapshot
  (examples/n8n/vendor/a6_activity_binding_export.json) and the lockfile
  may change. It (1) reads A6's published export from -SourcePath (a local
  file) or -SourceUrl (a deployed Process Generator endpoint); (2) computes
  the export's own SHA-256; (3) overwrites the vendored snapshot with the
  export verbatim; (4) derives the lockfile's processDefinition/
  activityDefinition/executor/provenance fields from that same vendored
  snapshot; (5) fills workflowBindings[].workflowVersion/nodeId by reading
  each of the three Flow-1a workflow JSON files' own literals directly
  (workflowVersion parsed from the workflow's own "| vX.Y.Z" name suffix;
  nodeId is the fixed, verified-present node name "03.1 Run DigiTax
  controls") -- never invented.

  -CheckOnly never reads A6's original source (verfahren-builder is a
  read-only binding source this repository must not depend on at CI/runtime
  time). It re-derives the lockfile purely from the already-committed
  vendored snapshot plus the three workflow files, into a temporary path,
  and diffs the result against what is actually committed -- catching a
  lockfile that was hand-edited to look published without the sync script
  ever having run, or a vendored snapshot that was hand-edited directly.

  provenance carries no generation-time field. generatorVersion is a fixed
  literal in this script's own source, bumped by hand only when this
  script's own logic changes -- never written by regeneration itself, only
  ever read back unchanged. Because every written field is a pure function
  of the vendored snapshot's bytes plus the three workflow files' own
  bytes, two consecutive -Regenerate runs against unchanged inputs produce
  byte-identical output, which is what -CheckOnly's byte-for-byte
  comparison depends on.

.PARAMETER Regenerate
  Read the source export (-SourcePath or -SourceUrl), overwrite the
  vendored snapshot, and regenerate the lockfile from it.

.PARAMETER CheckOnly
  Regenerate the lockfile from the already-committed vendored snapshot into
  a temp path and diff against the committed lockfile; throw on any
  difference.

.PARAMETER SourcePath
  Local file path to A6's published activity-binding export (used only by
  -Regenerate).

.PARAMETER SourceUrl
  URL of a deployed Process Generator endpoint serving the same export
  (used only by -Regenerate; alternative to -SourcePath).

.PARAMETER SourceRef
  Portable provenance reference describing where the export came from
  (e.g. "verfahren-builder@<commit>:<path>"). Required by -Regenerate.
  -CheckOnly always reuses the already-committed lockfile's own
  provenance.sourceRef, since it has no independent source to re-describe.

.EXAMPLE
  ./Sync-ActivityBinding.ps1 -Regenerate -SourcePath <path-to-A6-export> -SourceRef "verfahren-builder@<commit>:<path>"
  ./Sync-ActivityBinding.ps1 -Regenerate -SourceUrl <process-generator-endpoint> -SourceRef "process-generator@<endpoint>"
  ./Sync-ActivityBinding.ps1 -CheckOnly
#>
param(
    [Parameter(ParameterSetName = "RegenerateFromPath", Mandatory = $true)]
    [Parameter(ParameterSetName = "RegenerateFromUrl", Mandatory = $true)]
    [switch]$Regenerate,

    [Parameter(ParameterSetName = "CheckOnly", Mandatory = $true)]
    [switch]$CheckOnly,

    [Parameter(ParameterSetName = "RegenerateFromPath", Mandatory = $true)]
    [string]$SourcePath,

    [Parameter(ParameterSetName = "RegenerateFromUrl", Mandatory = $true)]
    [string]$SourceUrl,

    [Parameter(ParameterSetName = "RegenerateFromPath", Mandatory = $true)]
    [Parameter(ParameterSetName = "RegenerateFromUrl", Mandatory = $true)]
    [string]$SourceRef
)

$ErrorActionPreference = "Stop"

$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$N8nDir = Split-Path -Parent $ScriptDir
$VendoredSnapshotPath = Join-Path $N8nDir "vendor\a6_activity_binding_export.json"
$LockfilePath = Join-Path $N8nDir "activity_binding.invoice_intake.json"

$WorkflowFileNames = @(
    "digitax_invoice_phase1_flow1a_upload_v1_0_0.json",
    "digitax_invoice_phase1_flow1a_batch_item_v1_0_0.json",
    "digitax_invoice_phase1_flow1a_structured_regression_v1_0_0.json"
)
$RequiredNodeId = "03.1 Run DigiTax controls"
$GeneratorVersion = "1.0.0"

function Get-Sha256Hex {
    param([string]$Path)
    (Get-FileHash -Algorithm SHA256 -Path $Path).Hash.ToLowerInvariant()
}

function New-LockfileFromVendoredSnapshot {
    param(
        [string]$VendoredSnapshotPath,
        [string]$SourceRef
    )

    if (-not (Test-Path $VendoredSnapshotPath)) {
        throw "Vendored snapshot not found: $VendoredSnapshotPath"
    }
    $export = Get-Content -Raw -Path $VendoredSnapshotPath | ConvertFrom-Json
    $sourceSha256 = Get-Sha256Hex -Path $VendoredSnapshotPath

    $workflowBindings = @()
    foreach ($fileName in $WorkflowFileNames) {
        $wfPath = Join-Path $N8nDir $fileName
        if (-not (Test-Path $wfPath)) {
            throw "Workflow file not found: $wfPath"
        }
        $wf = Get-Content -Raw -Path $wfPath | ConvertFrom-Json
        $nodeNames = @($wf.nodes | ForEach-Object { $_.name })
        if ($nodeNames -notcontains $RequiredNodeId) {
            throw "Workflow $fileName has no node named '$RequiredNodeId'"
        }
        if ($wf.name -notmatch '\|\s*v(\d+\.\d+\.\d+)\s*$') {
            throw "Workflow $fileName name '$($wf.name)' has no trailing '| vX.Y.Z' version suffix"
        }
        $workflowBindings += [ordered]@{
            workflowId      = $wf.id
            workflowVersion = $Matches[1]
            nodeId          = $RequiredNodeId
        }
    }

    return [ordered]@{
        bindingSchemaVersion = "1.0.0"
        status               = $export.status
        generatedBy          = "examples/n8n/scripts/Sync-ActivityBinding.ps1 -- do not hand-edit"
        provenance           = [ordered]@{
            sourceRef        = $SourceRef
            sourceSha256     = $sourceSha256
            generatorVersion = $GeneratorVersion
        }
        processDefinition   = [ordered]@{
            processId      = $export.processDefinition.processId
            processVersion = $export.processDefinition.processVersion
        }
        activityDefinition  = [ordered]@{
            activityId      = $export.activityDefinition.activityId
            activityVersion = $export.activityDefinition.activityVersion
        }
        executor            = [ordered]@{
            type      = $export.executor.type
            logicalId = $export.executor.logicalId
            version   = $export.executor.version
        }
        workflowBindings    = $workflowBindings
    }
}

function Write-JsonFile {
    param([string]$Path, $Object)
    $json = $Object | ConvertTo-Json -Depth 10
    [System.IO.File]::WriteAllText($Path, "$json`n")
}

if ($Regenerate) {
    if ($SourceUrl) {
        Write-Host "Fetching A6 export from $SourceUrl ..."
        $exportBytes = (Invoke-WebRequest -Uri $SourceUrl -UseBasicParsing).Content
    }
    else {
        if (-not (Test-Path $SourcePath)) {
            throw "SourcePath not found: $SourcePath"
        }
        $exportBytes = [System.IO.File]::ReadAllBytes($SourcePath)
    }

    New-Item -ItemType Directory -Force -Path (Split-Path -Parent $VendoredSnapshotPath) | Out-Null
    [System.IO.File]::WriteAllBytes($VendoredSnapshotPath, $exportBytes)
    Write-Host "Vendored snapshot written: $VendoredSnapshotPath (SHA-256 $(Get-Sha256Hex -Path $VendoredSnapshotPath))"

    $lockfile = New-LockfileFromVendoredSnapshot -VendoredSnapshotPath $VendoredSnapshotPath -SourceRef $SourceRef
    Write-JsonFile -Path $LockfilePath -Object $lockfile
    Write-Host "Lockfile regenerated: $LockfilePath (status $($lockfile.status))"
}
elseif ($CheckOnly) {
    if (-not (Test-Path $LockfilePath)) {
        throw "Lockfile not found: $LockfilePath"
    }
    $committedLockfile = Get-Content -Raw -Path $LockfilePath | ConvertFrom-Json
    $existingSourceRef = $committedLockfile.provenance.sourceRef

    $tempLockfilePath = Join-Path ([System.IO.Path]::GetTempPath()) ("activity_binding_check_" + [System.Guid]::NewGuid().ToString("N") + ".json")
    try {
        $regenerated = New-LockfileFromVendoredSnapshot -VendoredSnapshotPath $VendoredSnapshotPath -SourceRef $existingSourceRef
        Write-JsonFile -Path $tempLockfilePath -Object $regenerated

        $committedBytes = [System.IO.File]::ReadAllBytes($LockfilePath)
        $regeneratedBytes = [System.IO.File]::ReadAllBytes($tempLockfilePath)
        if (-not [System.Linq.Enumerable]::SequenceEqual($committedBytes, $regeneratedBytes)) {
            throw "Activity binding lockfile drift detected: $LockfilePath does not match a fresh regeneration from the committed vendored snapshot ($VendoredSnapshotPath) and workflow files."
        }
        Write-Host "OK: $LockfilePath matches a fresh regeneration from the committed vendored snapshot byte-for-byte."
    }
    finally {
        Remove-Item -Path $tempLockfilePath -Force -ErrorAction SilentlyContinue
    }
}
