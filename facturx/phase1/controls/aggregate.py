"""Phase 1 status aggregation, per docs/invoice_phase1/automation_boundary.md:

- nicht_pruefbar: source cannot be read, schema is unsupported, required PDF
  extraction is unreliable, or control execution failed technically.
- klaerung_erforderlich: a blocking content/arithmetic/master-data/external-
  validation finding exists.
- hinweis: only non-blocking findings remain.
- unauffaellig: all applicable automated controls passed.

Unknown/unexpected combinations use the safe fallback nicht_pruefbar.
"""
from .executor import ControlResult

STATUSES = ("unauffaellig", "hinweis", "klaerung_erforderlich", "nicht_pruefbar")
ROUTINGS = ("standard_review", "prioritized_review")


def aggregate(controls: list[ControlResult]) -> tuple[str, str]:
    if not controls:
        return "nicht_pruefbar", "prioritized_review"

    doc_001 = next((c for c in controls if c.control_id == "DOC-001"), None)
    if doc_001 is not None and doc_001.outcome == "failed":
        return "nicht_pruefbar", "prioritized_review"

    if any(c.outcome == "not_reliable" for c in controls):
        return "nicht_pruefbar", "prioritized_review"

    if any(c.outcome == "failed" and c.severity == "blocking" for c in controls):
        return "klaerung_erforderlich", "prioritized_review"

    if any(c.outcome == "failed" and c.severity in ("warning", "info") for c in controls):
        return "hinweis", "standard_review"

    if all(c.outcome in ("passed", "not_applicable", "not_run") for c in controls):
        return "unauffaellig", "standard_review"

    # Anything not explicitly classified above (e.g. an outcome value the
    # aggregation rules above don't recognize) falls back to the safe default.
    return "nicht_pruefbar", "prioritized_review"
