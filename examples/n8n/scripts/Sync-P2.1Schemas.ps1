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
  developer operation.

  -CheckOnly is fully self-contained (A1 round-1 review, High: the previous
  version regenerated from the research workspace even in -CheckOnly mode,
  so it failed with "Source schema not found" on any checkout that does not
  also have that external, sibling-repository path -- including a genuine
  clean `git clone` of just this repository, which is exactly what CI
  provides). It now validates ONLY what is already committed: both vendored
  schema files are present and valid JSON, schema_provenance.json's shape
  and "usage" markers match the expected constants, its two sourceSha256
  values are a fresh hash of the committed vendored files themselves (not
  merely copied and trusted), and no stray files exist under vendor/p2_1/.
  It never touches the research workspace.

  -VerifyAgainstSource is the explicit, separate, local/dev-only operation
  that DOES read the research workspace: it compares the committed vendored
  files against the source originals byte-for-byte and reports drift,
  without writing anything. Use this (or -Regenerate, which is a superset)
  when you actually have that sibling checkout and want to confirm the
  vendored copies are still faithful to their upstream origin. This has no
  network variant (unlike Sync-ActivityBinding.ps1's -SourceUrl option)
  because the P2.1 package is a local research artifact with no deployed
  endpoint to fetch from.

  schema_provenance.json carries no generation-timestamp field -- both
  entries are a pure function of the two vendored files' own bytes, so two
  consecutive -Regenerate runs against unchanged inputs always produce
  byte-identical output.

.PARAMETER Regenerate
  Copy both schemas from -ResearchWorkspaceSchemasPath, recompute hashes,
  and overwrite the vendored snapshot pair plus schema_provenance.json.
  Requires the research workspace to be present.

.PARAMETER CheckOnly
  Self-contained: validate the committed vendored file set and its
  hashes/provenance shape. Never reads the research workspace. Intended for
  CI and any checkout containing only this repository.

.PARAMETER VerifyAgainstSource
  Local/dev-only: compare the committed vendored files against the research
  workspace originals byte-for-byte; report drift; write nothing. Requires
  the research workspace to be present.

.PARAMETER ResearchWorkspaceSchemasPath
  Local path to the P2.1 package's schemas/ directory. Only read by
  -Regenerate and -VerifyAgainstSource. Defaults to this repository's known
  sibling location inside the research workspace; override for a different
  checkout layout.

.EXAMPLE
  ./Sync-P2.1Schemas.ps1 -Regenerate
  ./Sync-P2.1Schemas.ps1 -CheckOnly
  ./Sync-P2.1Schemas.ps1 -VerifyAgainstSource
#>
param(
    [Parameter(ParameterSetName = "Regenerate", Mandatory = $true)]
    [switch]$Regenerate,

    [Parameter(ParameterSetName = "CheckOnly", Mandatory = $true)]
    [switch]$CheckOnly,

    [Parameter(ParameterSetName = "VerifyAgainstSource", Mandatory = $true)]
    [switch]$VerifyAgainstSource,

    [string]$ResearchWorkspaceSchemasPath
)

$ErrorActionPreference = "Stop"

$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$N8nDir = Split-Path -Parent $ScriptDir
$VendorDir = Join-Path $N8nDir "vendor\p2_1"
$ProvenancePath = Join-Path $VendorDir "schema_provenance.json"

function Resolve-ResearchWorkspaceSchemasPath {
    if ($script:ResearchWorkspaceSchemasPath) {
        return $script:ResearchWorkspaceSchemasPath
    }
    # $N8nDir = .../work/repos/facturx_apis_standard_correction/examples/n8n
    # -> repo root -> work/repos -> work -> work/arbeitsbericht/research/.../schemas
    $RepoRoot = Split-Path -Parent (Split-Path -Parent $N8nDir)
    $ReposDir = Split-Path -Parent $RepoRoot
    $WorkDir = Split-Path -Parent $ReposDir
    return Join-Path $WorkDir "arbeitsbericht\research\2026-08-12_execution_evidence_profile_p2_1\schemas"
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
    # Reads from the research workspace. Only ever called by -Regenerate or
    # -VerifyAgainstSource, never by -CheckOnly.
    param([string]$TargetDir, [string]$SourceSchemasPath)

    New-Item -ItemType Directory -Force -Path $TargetDir | Out-Null

    $provenance = [ordered]@{}
    foreach ($key in $Schemas.Keys) {
        $entry = $Schemas[$key]
        $sourcePath = Join-Path $SourceSchemasPath $entry.fileName
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

    # ConvertTo-Json on Windows PowerShell 5.1 embeds CRLF between every
    # property internally (an Environment.NewLine artifact, unrelated to any
    # git checkout filter) -- normalized to LF-only here so -Regenerate's
    # output is byte-identical to what git actually stores and to a fresh
    # regeneration on any machine, not just the one that originally ran
    # -Regenerate. Discovered by testing against a genuine fresh git clone.
    $provenanceJson = ($provenance | ConvertTo-Json -Depth 10) -replace "`r`n", "`n"
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

function Test-VendoredSetSelfConsistent {
    # Self-contained: reads only what is already committed under
    # $VendorDir. Never touches the research workspace. Returns a list of
    # human-readable problems; empty means fully consistent.
    $problems = @()

    if (-not (Test-Path $VendorDir)) {
        return @("Vendored directory does not exist: $VendorDir")
    }

    $expectedFileNames = @($Schemas.Values.fileName) + @("schema_provenance.json")
    $actualFileNames = @(Get-ChildItem -Path $VendorDir -File | Select-Object -ExpandProperty Name)
    $stray = $actualFileNames | Where-Object { $_ -notin $expectedFileNames }
    if ($stray) {
        $problems += "Unexpected file(s) under ${VendorDir}: $($stray -join ', ')"
    }
    $missing = $expectedFileNames | Where-Object { $_ -notin $actualFileNames }
    if ($missing) {
        $problems += "Missing file(s) under ${VendorDir}: $($missing -join ', ')"
        return $problems
    }

    $provenanceRaw = Get-Content -Raw -Path $ProvenancePath
    try {
        $provenance = $provenanceRaw | ConvertFrom-Json
    }
    catch {
        return @("schema_provenance.json is not valid JSON: $($_.Exception.Message)")
    }

    if ($provenanceRaw -match "(?i)generatedat|generationtime") {
        $problems += "schema_provenance.json appears to contain a generation-timestamp field"
    }

    foreach ($key in $Schemas.Keys) {
        $entry = $Schemas[$key]
        $schemaPath = Join-Path $VendorDir $entry.fileName

        try {
            Get-Content -Raw -Path $schemaPath | ConvertFrom-Json | Out-Null
        }
        catch {
            $problems += "$($entry.fileName) is not valid JSON: $($_.Exception.Message)"
            continue
        }

        $provenanceEntry = $provenance.$key
        if (-not $provenanceEntry) {
            $problems += "schema_provenance.json has no entry for '$key'"
            continue
        }

        $freshHash = Get-Sha256Hex -Path $schemaPath
        if ($provenanceEntry.sourceSha256 -ne $freshHash) {
            $problems += "schema_provenance.json's '$key'.sourceSha256 ($($provenanceEntry.sourceSha256)) does not match a fresh hash of the committed file ($freshHash) -- the vendored file or the provenance entry was hand-edited"
        }
        if ($provenanceEntry.usage -ne $entry.usage) {
            $problems += "schema_provenance.json's '$key'.usage is '$($provenanceEntry.usage)', expected '$($entry.usage)'"
        }
        if (-not $provenanceEntry.sourceRef) {
            $problems += "schema_provenance.json's '$key'.sourceRef is empty"
        }
    }

    return $problems
}

if ($Regenerate) {
    $sourcePath = Resolve-ResearchWorkspaceSchemasPath
    Write-VendoredSet -TargetDir $VendorDir -SourceSchemasPath $sourcePath | Out-Null
    Write-Host "Regenerated $VendorDir from $sourcePath"
}
elseif ($CheckOnly) {
    $problems = Test-VendoredSetSelfConsistent
    if ($problems.Count -gt 0) {
        throw "P2.1 schema vendoring self-consistency check failed:`n$($problems -join "`n")"
    }
    Write-Host "OK: $VendorDir is internally self-consistent (hashes, provenance, JSON validity) -- checked without reading any external source."
}
elseif ($VerifyAgainstSource) {
    $sourcePath = Resolve-ResearchWorkspaceSchemasPath
    if (-not (Test-Path $sourcePath)) {
        throw "Research workspace not found: $sourcePath (this is a local/dev-only check, not required to pass in CI)"
    }
    $tempDir = Join-Path ([System.IO.Path]::GetTempPath()) ("p2_1_schema_verify_" + [System.Guid]::NewGuid().ToString("N"))
    try {
        Write-VendoredSet -TargetDir $tempDir -SourceSchemasPath $sourcePath | Out-Null
        $diffs = Compare-Directories -Left $VendorDir -Right $tempDir
        if ($diffs.Count -gt 0) {
            throw "P2.1 schema vendoring drift against the research workspace detected:`n$($diffs -join "`n")"
        }
        Write-Host "OK: $VendorDir matches the research workspace at $sourcePath byte-for-byte."
    }
    finally {
        Remove-Item -Path $tempDir -Recurse -Force -ErrorAction SilentlyContinue
    }
}
