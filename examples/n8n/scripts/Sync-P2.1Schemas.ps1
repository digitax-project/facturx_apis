<#
.SYNOPSIS
  Deterministic vendoring sync for the two canonical P2.1 execution-evidence
  schemas this project depends on (ActivityExecution is actively used in
  Stage 1; HumanReviewDecision is vendored for atomic hash-pinning only and
  stays deferred -- see examples/n8n/vendor/p2_1/schema_provenance.json).

.DESCRIPTION
  -Regenerate is the only way examples/n8n/vendor/p2_1/*.schema.json and
  schema_provenance.json may change: it copies both schemas verbatim from
  the local P2.1 research-workspace package, hashes them, and overwrites the
  vendored snapshot pair. This is a local, one-time-per-schema-change
  developer operation -- CI never runs -Regenerate, only -CheckOnly, because
  a GitHub-hosted (or any CI) runner checking out only this repository never
  has the research workspace path.

  -CheckOnly regenerates into a temporary directory from the same research
  workspace source and diffs the result against what is actually committed,
  exiting non-zero on any difference. This has no network variant (unlike
  Sync-ActivityBinding.ps1's -SourceUrl option) because the P2.1 package is
  a local research artifact with no deployed endpoint to fetch from.

  schema_provenance.json carries no generation-timestamp field -- both
  entries are a pure function of the two source files' own bytes, so two
  consecutive -Regenerate runs against unchanged inputs always produce
  byte-identical output, which is what makes -CheckOnly's byte-for-byte
  comparison usable in CI instead of failing on every run purely because
  "now" changed.

.PARAMETER Regenerate
  Copy both schemas from -ResearchWorkspaceSchemasPath, recompute hashes,
  and overwrite the vendored snapshot pair plus schema_provenance.json.

.PARAMETER CheckOnly
  Regenerate into a temp directory and diff against the committed vendored
  files; exit non-zero (throw) on any difference. Intended for CI and local
  pre-commit verification alike.

.PARAMETER ResearchWorkspaceSchemasPath
  Local path to the P2.1 package's schemas/ directory. Only read by
  -Regenerate. Defaults to this repository's known sibling location inside
  the research workspace; override for a different checkout layout.

.EXAMPLE
  ./Sync-P2.1Schemas.ps1 -Regenerate
  ./Sync-P2.1Schemas.ps1 -CheckOnly
#>
param(
    [Parameter(ParameterSetName = "Regenerate", Mandatory = $true)]
    [switch]$Regenerate,

    [Parameter(ParameterSetName = "CheckOnly", Mandatory = $true)]
    [switch]$CheckOnly,

    [string]$ResearchWorkspaceSchemasPath
)

$ErrorActionPreference = "Stop"

$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$N8nDir = Split-Path -Parent $ScriptDir
$VendorDir = Join-Path $N8nDir "vendor\p2_1"

if (-not $ResearchWorkspaceSchemasPath) {
    # $N8nDir = .../work/repos/facturx_apis_standard_correction/examples/n8n
    # -> repo root -> work/repos -> work -> work/arbeitsbericht/research/.../schemas
    $RepoRoot = Split-Path -Parent (Split-Path -Parent $N8nDir)
    $ReposDir = Split-Path -Parent $RepoRoot
    $WorkDir = Split-Path -Parent $ReposDir
    $ResearchWorkspaceSchemasPath = Join-Path $WorkDir "arbeitsbericht\research\2026-08-12_execution_evidence_profile_p2_1\schemas"
}

# Portable sourceRef recorded in provenance: relative to the research
# workspace root (ResearchAssistant/), the way the accepted A5 plan states
# it, independent of where this repository happens to be checked out.
$SourceRefPrefix = "work/arbeitsbericht/research/2026-08-12_execution_evidence_profile_p2_1/schemas"

$Schemas = [ordered]@{
    "activity-execution"    = [ordered]@{
        fileName = "activity-execution.schema.json"
        usage    = "ACTIVE_STAGE1_ACTIVITY_EXECUTION_VALIDATION"
    }
    "human-review-decision" = [ordered]@{
        fileName = "human-review-decision.schema.json"
        usage    = "DEFERRED_VENDORED_FOR_ATOMIC_HASH_PIN_ONLY_NOT_GENERATED_FLOW_2_OUT_OF_SCOPE"
    }
}

function Get-Sha256Hex {
    param([string]$Path)
    (Get-FileHash -Algorithm SHA256 -Path $Path).Hash.ToLowerInvariant()
}

function Write-VendoredSet {
    param([string]$TargetDir)

    New-Item -ItemType Directory -Force -Path $TargetDir | Out-Null

    $provenance = [ordered]@{}
    foreach ($key in $Schemas.Keys) {
        $entry = $Schemas[$key]
        $sourcePath = Join-Path $ResearchWorkspaceSchemasPath $entry.fileName
        if (-not (Test-Path $sourcePath)) {
            throw "Source schema not found: $sourcePath"
        }
        $destPath = Join-Path $TargetDir $entry.fileName
        Copy-Item -Path $sourcePath -Destination $destPath -Force

        $provenance[$key] = [ordered]@{
            sourceRef    = "$SourceRefPrefix/$($entry.fileName)"
            sourceSha256 = Get-Sha256Hex -Path $sourcePath
            usage        = $entry.usage
        }
    }

    $provenanceJson = $provenance | ConvertTo-Json -Depth 10
    $provenancePath = Join-Path $TargetDir "schema_provenance.json"
    # No trailing newline drift between -Regenerate and -CheckOnly runs.
    [System.IO.File]::WriteAllText($provenancePath, "$provenanceJson`n")

    return $TargetDir
}

function Compare-Directories {
    param([string]$Left, [string]$Right)

    $leftFiles = Get-ChildItem -Path $Left -File | Sort-Object Name
    $rightFiles = Get-ChildItem -Path $Right -File | Sort-Object Name

    if ($leftFiles.Count -ne $rightFiles.Count) {
        throw "Vendored file count differs: committed=$($leftFiles.Count) regenerated=$($rightFiles.Count)"
    }

    $diffs = @()
    foreach ($f in $leftFiles) {
        $rightPath = Join-Path $Right $f.Name
        if (-not (Test-Path $rightPath)) {
            $diffs += "Missing in regenerated output: $($f.Name)"
            continue
        }
        $leftBytes = [System.IO.File]::ReadAllBytes($f.FullName)
        $rightBytes = [System.IO.File]::ReadAllBytes($rightPath)
        if (-not [System.Linq.Enumerable]::SequenceEqual($leftBytes, $rightBytes)) {
            $diffs += "Byte-level drift detected: $($f.Name)"
        }
    }
    return $diffs
}

if ($Regenerate) {
    Write-VendoredSet -TargetDir $VendorDir | Out-Null
    Write-Host "Regenerated $VendorDir from $ResearchWorkspaceSchemasPath"
}
elseif ($CheckOnly) {
    if (-not (Test-Path $VendorDir)) {
        throw "Vendored directory does not exist: $VendorDir"
    }
    $tempDir = Join-Path ([System.IO.Path]::GetTempPath()) ("p2_1_schema_check_" + [System.Guid]::NewGuid().ToString("N"))
    try {
        Write-VendoredSet -TargetDir $tempDir | Out-Null
        $diffs = Compare-Directories -Left $VendorDir -Right $tempDir
        if ($diffs.Count -gt 0) {
            throw "P2.1 schema vendoring drift detected:`n$($diffs -join "`n")"
        }
        Write-Host "OK: $VendorDir matches a fresh regeneration from $ResearchWorkspaceSchemasPath byte-for-byte."
    }
    finally {
        Remove-Item -Path $tempDir -Recurse -Force -ErrorAction SilentlyContinue
    }
}
