#!/bin/sh
# One-shot developer-stack initializer for compose.dev.yml's "n8n-init"
# service. Runs to completion BEFORE the long-running "n8n" service starts
# (docker-compose depends_on: condition: service_completed_successfully),
# against the same shared named volume -- so by the time "n8n start" begins,
# every workflow is already imported and the intended workflows are already
# active. No `docker exec` against a running server, no restart.
#
# Verified empirically against n8nio/n8n:2.33.7 (2026-08-11): a workflow
# activated this way is live (its webhook is registered and reachable) the
# moment "n8n start" finishes booting, with no separate activation step.
#
# Idempotency note: `n8n import:workflow` internally tries to deactivate the
# workflow it is about to overwrite, but this fails with a permission error
# on a workflow that is currently ACTIVE and has no owner/sharing record --
# which is the case for every CLI-imported workflow in this headless dev
# stack (verified empirically). Explicitly unpublishing each workflow first
# avoids that error and keeps re-imports on an already-populated volume
# idempotent; unpublishing is skipped on a workflow's very first import
# (unpublishing an unknown ID is itself an error).
#
# CLI note: uses the current, supported `publish:workflow`/
# `unpublish:workflow` commands, not the deprecated `update:workflow
# --active=true/false` (n8n 2.33.7 prints a deprecation warning for the
# latter; the two pairs were verified empirically to behave identically for
# this script's purposes -- same idempotency behavior, same "not found" error
# on an unknown id, same "restart required if n8n is already running" note).
set -eu

WORKFLOWS_DIR="/data/workflows"

# id -> filename, in import order. Only the versioned DigiTax workflows are
# imported -- digitax_invoice_intake.json is an intentionally untouched
# historical reference (see examples/n8n/README.md) and is never imported
# into this or any other n8n instance.
#
# P2.1 Wave 1 A5 Stage 1: the shared "Assemble ActivityExecution"
# subworkflow is imported first (called by the other three via Execute
# Workflow) and must be PUBLISHED like Upload Demo/Batch Item -- it has no
# webhook and is never externally reachable, but n8n 2.33.7's
# WorkflowPublicationService refuses to let Execute Workflow invoke an
# unpublished target at all, confirmed empirically.
WORKFLOW_IDS="digitax-invoice-phase1-shared-assemble-activity-execution digitax-invoice-phase1-structured-demo digitax-invoice-phase1-upload-demo digitax-invoice-phase1-batch-item digitax-invoice-phase1-flow1b-pdf-ocr digitax-invoice-phase1-flow0-mailbox-intake digitax-invoice-phase1-flow2-teams-review-notify"
workflow_file_for_id() {
  case "$1" in
    digitax-invoice-phase1-shared-assemble-activity-execution) echo "digitax_invoice_phase1_shared_assemble_activity_execution_v1_0_0.json" ;;
    digitax-invoice-phase1-structured-demo) echo "digitax_invoice_phase1_flow1a_structured_regression_v1_0_0.json" ;;
    digitax-invoice-phase1-upload-demo) echo "digitax_invoice_phase1_flow1a_upload_v1_0_0.json" ;;
    digitax-invoice-phase1-batch-item) echo "digitax_invoice_phase1_flow1a_batch_item_v1_1_0.json" ;;
    digitax-invoice-phase1-flow1b-pdf-ocr) echo "digitax_invoice_phase1_flow1b_pdf_ocr_concept_v0_3_0.json" ;;
    digitax-invoice-phase1-flow0-mailbox-intake) echo "digitax_invoice_phase1_flow0_mailbox_intake_v0_1_0.json" ;;
    digitax-invoice-phase1-flow2-teams-review-notify) echo "digitax_invoice_phase1_flow2_teams_review_notify_v0_1_0.json" ;;
    *) echo "" ;;
  esac
}

# Published (active) by default; the rest stay inactive. The shared
# subworkflow is published for the reason explained above, not because it
# has a webhook -- it does not.
ACTIVE_IDS="digitax-invoice-phase1-upload-demo digitax-invoice-phase1-batch-item digitax-invoice-phase1-shared-assemble-activity-execution"

existing_ids() {
  n8n list:workflow 2>/dev/null | cut -d'|' -f1
}

import_one() {
  id="$1"
  file="$(workflow_file_for_id "$id")"
  if [ -z "$file" ]; then
    echo "[n8n-init] FATAL: no filename mapped for workflow id $id" >&2
    exit 1
  fi
  if existing_ids | grep -qx "$id"; then
    echo "[n8n-init] Unpublishing existing workflow $id before re-import..."
    n8n unpublish:workflow --id="$id" >/dev/null
  fi
  echo "[n8n-init] Importing $file (id=$id)"
  n8n import:workflow --input="${WORKFLOWS_DIR}/${file}"
}

echo "[n8n-init] Importing DigiTax Phase 1 workflows..."
for id in $WORKFLOW_IDS; do
  import_one "$id"
done

echo "[n8n-init] Publishing: Flow 1a Upload Demo + Flow 1a Batch Item + the shared Assemble ActivityExecution subworkflow (Structured Regression and Flow 1b stay inactive)..."
for id in $ACTIVE_IDS; do
  n8n publish:workflow --id="$id" >/dev/null
done

echo "[n8n-init] Verifying imported workflow set (expect exactly 7, no duplicates)..."
GOT_IDS=$(existing_ids | sort)
EXPECT_IDS=$(printf '%s\n' $WORKFLOW_IDS | sort)
if [ "$GOT_IDS" != "$EXPECT_IDS" ]; then
  echo "[n8n-init] FATAL: imported workflow set does not match expectation." >&2
  echo "[n8n-init] expected:" >&2
  echo "$EXPECT_IDS" >&2
  echo "[n8n-init] got:" >&2
  echo "$GOT_IDS" >&2
  exit 1
fi

echo "[n8n-init] Verifying active workflow set (expect exactly Upload Demo + Batch Item + shared Assemble ActivityExecution)..."
GOT_ACTIVE=$(n8n list:workflow --active=true 2>/dev/null | cut -d'|' -f1 | sort)
EXPECT_ACTIVE=$(printf '%s\n' $ACTIVE_IDS | sort)
if [ "$GOT_ACTIVE" != "$EXPECT_ACTIVE" ]; then
  echo "[n8n-init] FATAL: active workflow set does not match expectation." >&2
  echo "[n8n-init] expected:" >&2
  echo "$EXPECT_ACTIVE" >&2
  echo "[n8n-init] got:" >&2
  echo "$GOT_ACTIVE" >&2
  exit 1
fi

echo "[n8n-init] Done. 7 workflows imported; Upload Demo + Batch Item + shared Assemble ActivityExecution active, Structured Regression + Flow 1b + Flow 0 + Flow 2 inactive."
