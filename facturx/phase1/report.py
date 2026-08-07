"""Assembles a phase1_control_report and validates it against its contract
schema before it's ever returned -- "fail closed on schema errors" per
examples/n8n/invoice_phase1_node_plan.md.
"""
import uuid
from datetime import datetime, timezone
from typing import Optional

from .capabilities import CATALOG_VERSION
from .contracts import validate_phase1_control_report
from .controls.executor import ControlResult
from .controls.profiles import ControlProfile


def build_report(
    source_sha256: str,
    control_profile: ControlProfile,
    controls: list[ControlResult],
    status: str,
    routing: str,
    run_id: Optional[str] = None,
    reqeli: Optional[dict] = None,
) -> dict:
    run_id = run_id or f"RUN-{uuid.uuid4().hex[:12].upper()}"
    report = {
        "schemaVersion": "1.0.0",
        "reportId": f"REP-{uuid.uuid4().hex[:12].upper()}",
        "runId": run_id,
        "sourceSha256": source_sha256,
        "catalogVersion": CATALOG_VERSION,
        "controlProfileId": control_profile.id,
        "status": status,
        "routing": routing,
        "controls": [
            {
                "controlId": c.control_id,
                "title": c.title,
                "outcome": c.outcome,
                "severity": c.severity,
                "reasonCodes": c.reason_codes,
                "evidenceRefs": c.evidence_refs,
                "ruleVersion": c.rule_version,
                "message": c.message,
            }
            for c in controls
        ],
        "suggestions": [],
        "reqeli": reqeli or {"invoked": False, "status": "disabled", "analysisRef": None},
        "createdAt": datetime.now(timezone.utc).isoformat(),
    }
    validate_phase1_control_report(report)
    return report
