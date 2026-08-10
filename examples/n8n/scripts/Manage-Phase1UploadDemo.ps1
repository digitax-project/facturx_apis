<#
.SYNOPSIS
  One-command management of the isolated DigiTax Phase 1 operator upload
  demo (Factur-X API + n8n 2.33.7), fully separate from any manually-run
  n8n instance on port 5678 / volume n8n_data.

.DESCRIPTION
  Wraps docker-compose.phase1-upload-demo.yml so start/stop/smoke-test
  happen in the right order: bring the stack up, wait for both real health
  endpoints (never assume "container started" means "ready"), import both
  workflows idempotently (n8n's CLI import upserts by the workflow JSON's
  own "id" field -- reimporting never creates a duplicate), then optionally
  run a smoke test and save sanitized evidence.

  Reset is a separate, explicitly confirmed action. It never runs as part
  of Start/Stop, and it re-verifies the exact volume name before removing
  anything.

.PARAMETER Action
  Start | Stop | Status | SmokeTest | Reset

.PARAMETER Confirm
  Required (and must be $true) for -Action Reset. No other action reads it.

.EXAMPLE
  ./Manage-Phase1UploadDemo.ps1 -Action Start
  ./Manage-Phase1UploadDemo.ps1 -Action SmokeTest
  ./Manage-Phase1UploadDemo.ps1 -Action Stop
  ./Manage-Phase1UploadDemo.ps1 -Action Reset -Confirm
#>
param(
    [Parameter(Mandatory = $true)]
    [ValidateSet("Start", "Stop", "Status", "SmokeTest", "Reset")]
    [string]$Action,

    [switch]$Confirm
)

$ErrorActionPreference = "Stop"

$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$N8nDir = Split-Path -Parent $ScriptDir
$ComposeFile = Join-Path $N8nDir "docker-compose.phase1-upload-demo.yml"

$N8nContainer = "digitax-phase1-demo-n8n"
$VolumeName = "digitax_n8n_phase1_data"
$ApiHealthUrl = "http://localhost:6970/health"
$N8nHealthUrl = "http://localhost:5679/healthz"

$RegressionWorkflowId = "digitax-invoice-phase1-structured-demo"
$UploadWorkflowId = "digitax-invoice-phase1-upload-demo"

$EvidenceDir = [System.IO.Path]::GetFullPath((Join-Path $N8nDir "..\..\..\..\..\output\bpmn\renders\versions\digitax_flow01_n8n\upload-automation\review_evidence"))

function Wait-ForHealth {
    param(
        [string]$Url,
        [string]$Label,
        [int]$TimeoutSeconds = 90
    )
    Write-Host "Waiting for $Label ($Url) ..."
    $deadline = (Get-Date).AddSeconds($TimeoutSeconds)
    while ((Get-Date) -lt $deadline) {
        try {
            $resp = Invoke-WebRequest -Uri $Url -UseBasicParsing -TimeoutSec 3 -ErrorAction Stop
            if ($resp.StatusCode -eq 200) {
                Write-Host "$Label is healthy."
                return
            }
        }
        catch {
            Start-Sleep -Seconds 2
        }
    }
    throw "$Label did not become healthy within $TimeoutSeconds seconds ($Url)"
}

function Invoke-N8nImport {
    param([string]$WorkflowFileName)
    Write-Host "Importing $WorkflowFileName ..."
    docker exec $N8nContainer n8n import:workflow --input="/data/workflows/$WorkflowFileName"
    if ($LASTEXITCODE -ne 0) {
        throw "n8n import:workflow failed for $WorkflowFileName (exit $LASTEXITCODE)"
    }
}

function Publish-UploadWorkflow {
    # n8n's import:workflow always deactivates the imported workflow as a
    # safety default (confirmed empirically: every import prints
    # "Deactivating workflow ..." even when the source JSON has
    # "active": true) -- so the upload demo's production webhook needs an
    # explicit publish step after every import, and a restart for that
    # activation to take effect on the already-running n8n process.
    Write-Host "Publishing $UploadWorkflowId so its webhook goes live ..."
    docker exec $N8nContainer n8n update:workflow --id=$UploadWorkflowId --active=true
    if ($LASTEXITCODE -ne 0) { throw "n8n update:workflow --active=true failed (exit $LASTEXITCODE)" }

    Write-Host "Restarting n8n so the published webhook activates ..."
    docker restart $N8nContainer
    if ($LASTEXITCODE -ne 0) { throw "docker restart $N8nContainer failed (exit $LASTEXITCODE)" }
    Wait-ForHealth -Url $N8nHealthUrl -Label "n8n 2.33.7 (post-restart)"
}

function Assert-NoDuplicateWorkflows {
    $listOutput = docker exec $N8nContainer n8n list:workflow 2>&1
    if ($LASTEXITCODE -ne 0) {
        throw "n8n list:workflow failed (exit $LASTEXITCODE):`n$listOutput"
    }
    Write-Host $listOutput
    foreach ($id in @($RegressionWorkflowId, $UploadWorkflowId)) {
        $idMatches = @($listOutput | Select-String -SimpleMatch $id)
        if ($idMatches.Count -gt 1) {
            throw "Duplicate workflow detected for id $id ($($idMatches.Count) entries) -- import is not idempotent"
        }
        if ($idMatches.Count -eq 0) {
            throw "Expected workflow id $id not found after import"
        }
    }
    Write-Host "No duplicate workflows: $RegressionWorkflowId and $UploadWorkflowId each appear exactly once."
}

switch ($Action) {
    "Start" {
        Write-Host "Starting isolated Phase 1 upload demo stack (project: digitax-phase1-demo) ..."
        docker compose -f $ComposeFile up -d --build
        if ($LASTEXITCODE -ne 0) { throw "docker compose up failed (exit $LASTEXITCODE)" }

        Wait-ForHealth -Url $ApiHealthUrl -Label "Factur-X Phase 1 API"
        Wait-ForHealth -Url $N8nHealthUrl -Label "n8n 2.33.7"

        Invoke-N8nImport -WorkflowFileName "digitax_invoice_phase1_structured_demo.json"
        Invoke-N8nImport -WorkflowFileName "digitax_invoice_phase1_upload_demo.json"
        Assert-NoDuplicateWorkflows
        Publish-UploadWorkflow

        Write-Host ""
        Write-Host "Stack is up:"
        Write-Host "  n8n UI:      http://localhost:5679"
        Write-Host "  Upload demo: POST http://localhost:5679/webhook/phase1-invoice-upload (multipart: invoiceFile, organizationId or demoMode=true)"
        Write-Host "  API:         http://localhost:6970 (host) / http://api:6969 (container network)"
        Write-Host "  Volume:      $VolumeName (preserved across Stop)"
    }

    "Stop" {
        Write-Host "Stopping isolated Phase 1 upload demo stack (volume $VolumeName is preserved) ..."
        docker compose -f $ComposeFile down
        if ($LASTEXITCODE -ne 0) { throw "docker compose down failed (exit $LASTEXITCODE)" }
        Write-Host "Stopped. Existing n8n on port 5678 / volume n8n_data was never touched."
    }

    "Status" {
        docker compose -f $ComposeFile ps
    }

    "SmokeTest" {
        if (-not (Test-Path $EvidenceDir)) {
            New-Item -ItemType Directory -Force -Path $EvidenceDir | Out-Null
        }
        $timestamp = Get-Date -Format "yyyyMMdd_HHmmss"

        Write-Host "Smoke test 1/2: executing the embedded regression-demo workflow via CLI ..."
        $outputFile = Join-Path $EvidenceDir "smoke_test_cli_$timestamp.json"
        # The already-running main n8n process holds the default Task Runners
        # broker port (5679, coincidental collision with this stack's chosen
        # n8n UI host port -- unrelated, purely an n8n-internal default).
        # `n8n execute` spawns its own broker unless told to use a different
        # port, so it fails with "port 5679 is already in use" against a
        # persistent instance (this didn't surface in PR #5's testing, which
        # only ever used one-shot `docker run --rm` containers with no
        # already-running main process to collide with).
        $result = docker exec -e N8N_RUNNERS_BROKER_PORT=15679 $N8nContainer n8n execute --id=$RegressionWorkflowId 2>&1
        $resultText = $result -join "`n"
        # n8n includes an internal per-execution resume token even for this
        # completed workflow. It is not needed as review evidence and must not
        # leave the local instance when evidence is shared.
        $sanitizedResultText = $resultText `
            -replace '(?i)("resumeToken"\s*:\s*)"[^"]*"', '$1"[redacted]"' `
            -replace '(?i)("resumeUrl"\s*:\s*)"[^"]*"', '$1"[redacted]"'
        $sanitizedResultText | Out-File -FilePath $outputFile -Encoding utf8
        if ($resultText -notmatch '"finished":\s*true') {
            Write-Host "SMOKE TEST 1/2 FAILED -- see $outputFile"
            throw "CLI smoke test did not report finished:true"
        }
        Write-Host "SMOKE TEST 1/2 PASSED -- evidence saved to $outputFile"

        Write-Host "Smoke test 2/2: real multipart POST to the upload webhook ..."
        # Deliberately does not add or commit a new fixture (parallel-agent
        # boundary) -- decodes the same already-accepted embedded XML the
        # regression demo already carries, into a throwaway temp file only
        # for the duration of this check.
        $structuredWorkflowPath = Join-Path $N8nDir "digitax_invoice_phase1_structured_demo.json"
        $wf = Get-Content -Raw -Path $structuredWorkflowPath | ConvertFrom-Json
        $selectNode = $wf.nodes | Where-Object { $_.name -eq "Select Invoice (Demo Fixture)" }
        if (-not ($selectNode.parameters.jsCode -match 'const demoInvoiceBase64 = "([^"]+)"')) {
            throw "Could not locate the embedded demo invoice base64 in $structuredWorkflowPath"
        }
        $tempXmlPath = Join-Path ([System.IO.Path]::GetTempPath()) "phase1_smoke_test_invoice.xml"
        [System.IO.File]::WriteAllBytes($tempXmlPath, [System.Convert]::FromBase64String($Matches[1]))

        try {
            # -Form on Invoke-WebRequest requires PS 6+ (this environment is
            # Windows PowerShell 5.1). curl.exe ships with Windows 10+ and
            # produces a multipart body n8n's webhook parser reliably
            # accepts (verified: a hand-built .NET MultipartFormDataContent
            # request reached the webhook but its string field was not
            # parsed by n8n the same way curl's -F was).
            $htmlOutputFile = Join-Path $EvidenceDir "smoke_test_webhook_$timestamp.html"
            & curl.exe -s -o $htmlOutputFile -w "%{http_code}" `
                "http://localhost:5679/webhook/phase1-invoice-upload" `
                -F "invoiceFile=@$tempXmlPath;type=application/xml" `
                -F "organizationId=unternehmen-x-demo" `
                | Set-Variable -Name webhookStatusCode
            if ($LASTEXITCODE -ne 0) { throw "curl.exe failed (exit $LASTEXITCODE)" }

            $responseBody = Get-Content -Raw -Path $htmlOutputFile
            if ($webhookStatusCode -ne "200" -or $responseBody -notmatch "STATUS: unauffaellig") {
                Write-Host "SMOKE TEST 2/2 FAILED (HTTP $webhookStatusCode) -- see $htmlOutputFile"
                throw "Upload webhook smoke test did not return the expected unauffaellig result"
            }
            Write-Host "SMOKE TEST 2/2 PASSED -- evidence saved to $htmlOutputFile"
        }
        finally {
            Remove-Item -Path $tempXmlPath -Force -ErrorAction SilentlyContinue
        }
    }

    "Reset" {
        if (-not $Confirm) {
            throw "Reset requires -Confirm. This is a destructive, explicit action that deletes $VolumeName. Refusing without it."
        }
        Write-Host "Bringing the stack down first (containers must release the volume before removal) ..."
        docker compose -f $ComposeFile down
        if ($LASTEXITCODE -ne 0) { throw "docker compose down failed before reset (exit $LASTEXITCODE)" }

        docker volume inspect $VolumeName *>$null
        if ($LASTEXITCODE -ne 0) {
            Write-Host "Volume $VolumeName does not exist -- nothing to reset."
            return
        }
        $resolvedName = (docker volume inspect $VolumeName --format "{{.Name}}").Trim()
        if ($resolvedName -ne $VolumeName) {
            throw "Resolved volume name '$resolvedName' does not exactly match expected '$VolumeName' -- refusing to delete."
        }

        Write-Host "Confirmed target volume: $resolvedName. Deleting ..."
        docker volume rm $VolumeName
        if ($LASTEXITCODE -ne 0) { throw "docker volume rm failed (exit $LASTEXITCODE)" }
        Write-Host "Volume $VolumeName deleted. The existing n8n on port 5678 / volume n8n_data was never touched."
    }
}
