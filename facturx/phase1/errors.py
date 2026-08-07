"""Error types that map directly to the Phase 1 HTTP status rules.

- UnsupportedInputError -> 400/415: the request itself can't be classified
  (wrong content type entirely, missing required field, missing/unknown
  organization context). Raised before the classification pipeline runs.
- TechnicalProcessingError -> 5xx: an unclassified failure inside the
  pipeline (e.g. the structured-extraction library raising unexpectedly).
  Anticipated content-level outcomes (encrypted, low-confidence, unsupported
  *detected* format) are never raised as either of these -- they flow
  through to a classified nicht_pruefbar report instead, per
  docs/invoice_phase1/automation_boundary.md.
"""


class UnsupportedInputError(Exception):
    def __init__(self, error_code: str, detail: str, status_code: int = 400):
        self.error_code = error_code
        self.detail = detail
        self.status_code = status_code
        super().__init__(detail)


class TechnicalProcessingError(Exception):
    def __init__(self, error_code: str, detail: str, status_code: int = 503):
        self.error_code = error_code
        self.detail = detail
        self.status_code = status_code
        super().__init__(detail)
