<#
.SYNOPSIS
  Generates and sends all six synthetic profile-demo invoices through the
  live n8n upload webhook.
#>
param(
    [string]$WebhookUrl = "http://localhost:5679/webhook/phase1-invoice-upload"
)

$ErrorActionPreference = "Stop"
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$RepoRoot = [System.IO.Path]::GetFullPath((Join-Path $ScriptDir "..\..\.."))
$OutputDir = Join-Path $RepoRoot ".demo-output"
$Generator = Join-Path $RepoRoot "examples\demo\generate_demo_invoices.py"
$ManifestPath = Join-Path $OutputDir "generated_manifest.json"
$ResultDir = Join-Path $OutputDir "n8n-results"

python $Generator --output-dir $OutputDir
if ($LASTEXITCODE -ne 0) { throw "Demo invoice generation failed." }

$manifest = Get-Content -Raw -Path $ManifestPath | ConvertFrom-Json
New-Item -ItemType Directory -Force -Path $ResultDir | Out-Null
$failures = @()

foreach ($entry in $manifest.entries) {
    $invoicePath = Join-Path $OutputDir $entry.generatedPdf
    $responsePath = Join-Path $ResultDir "$($entry.scenarioId).html"
    Write-Host "Testing $($entry.scenarioId) with $($entry.organizationId) ..."

    $httpCode = & curl.exe -s -o $responsePath -w "%{http_code}" $WebhookUrl `
        -F "invoiceFile=@$invoicePath;type=application/pdf" `
        -F "organizationId=$($entry.organizationId)"
    if ($LASTEXITCODE -ne 0) {
        $failures += "$($entry.scenarioId): curl exit $LASTEXITCODE"
        continue
    }

    $response = Get-Content -Raw -Path $responsePath
    $expectedStatus = "STATUS: $($entry.expectedStatus)"
    $expectedProfile = $entry.controlProfileId
    if ($httpCode -ne "200" -or $response -notmatch [regex]::Escape($expectedStatus) -or
        $response -notmatch [regex]::Escape($expectedProfile)) {
        $failures += "$($entry.scenarioId): HTTP $httpCode, expected $expectedStatus and $expectedProfile"
        continue
    }
    Write-Host "  PASS: $($entry.expectedStatus), $expectedProfile"
}

if ($failures.Count -gt 0) {
    throw "Demo matrix failed:`n$($failures -join "`n")"
}

Write-Host "All $($manifest.entries.Count) demo cases passed through n8n."
Write-Host "Browser-readable responses: $ResultDir"
