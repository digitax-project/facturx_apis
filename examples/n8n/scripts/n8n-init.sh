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
# stack (verified empirically). Explicitly deactivating each workflow first
# avoids that error and keeps re-imports on an already-populated volume
# idempotent; deactivation is skipped on a workflow's very first import
# (deactivating an unknown ID is itself an error).
set -eu

WORKFLOWS_DIR="/data/workflows"

# id -> filename, in import order. Only the versioned DigiTax workflows are
# imported -- digitax_invoice_intake.json is an intentionally untouched
# historical reference (see examples/n8n/README.md) and is never imported
# into this or any other n8n instance.
WORKFLOW_IDS="digitax-invoice-phase1-structured-demo digitax-invoice-phase1-upload-demo digitax-invoice-phase1-batch-item digitax-invoice-phase1-flow1b-pdf-ocr"
workflow_file_for_id() {
  case "$1" in
    digitax-invoice-phase1-structured-demo) echo "digitax_invoice_phase1_flow1a_structured_regression_v1_0_0.json" ;;
    digitax-invoice-phase1-upload-demo) echo "digitax_invoice_phase1_flow1a_upload_v1_0_0.json" ;;
    digitax-invoice-phase1-batch-item) echo "digitax_invoice_phase1_flow1a_batch_item_v1_0_0.json" ;;
    digitax-invoice-phase1-flow1b-pdf-ocr) echo "digitax_invoice_phase1_flow1b_pdf_ocr_concept_v0_2_0.json" ;;
    *) echo "" ;;
  esac
}

# Published (active) by default; the rest stay inactive.
ACTIVE_IDS="digitax-invoice-phase1-upload-demo digitax-invoice-phase1-batch-item"

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
    echo "[n8n-init] Deactivating existing workflow $id before re-import..."
    n8n update:workflow --id="$id" --active=false >/dev/null
  fi
  echo "[n8n-init] Importing $file (id=$id)"
  n8n import:workflow --input="${WORKFLOWS_DIR}/${file}"
}

echo "[n8n-init] Importing DigiTax Phase 1 workflows..."
for id in $WORKFLOW_IDS; do
  import_one "$id"
done

echo "[n8n-init] Publishing: Flow 1a Upload Demo + Flow 1a Batch Item (Structured Regression and Flow 1b stay inactive)..."
for id in $ACTIVE_IDS; do
  n8n update:workflow --id="$id" --active=true >/dev/null
done

echo "[n8n-init] Verifying imported workflow set (expect exactly 4, no duplicates)..."
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

echo "[n8n-init] Verifying active workflow set (expect exactly Upload Demo + Batch Item)..."
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

echo "[n8n-init] Done. 4 workflows imported; Upload Demo + Batch Item active, Structured Regression + Flow 1b inactive."
