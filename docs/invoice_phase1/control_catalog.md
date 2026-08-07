# Candidate control catalog

## Purpose

This is an extensible list of possible inbound-invoice controls. It is not one
universal checklist: an organization selects a versioned control profile based
on invoice type, tax case, risk, available master data, and implementation
maturity. Each control must declare its applicability before it can affect the
Phase 1 status.

The Factur-X service owns format-specific extraction and validation. n8n loads
the applicable profile, orchestrates services, and routes the result. Reusable
deterministic controls should move into a control service instead of growing as
unversioned n8n code.

## Candidate controls

### Document intake and technical processing

| ID | Possible control | Typical implementation |
|---|---|---|
| DOC-001 | File received, readable, supported, and within size limits | n8n/API |
| DOC-002 | MIME type and file signature are consistent | deterministic |
| DOC-003 | File is not encrypted or password-protected | deterministic |
| DOC-004 | Source hash is recorded and duplicate intake is detected | deterministic |
| DOC-005 | Structured, hybrid-PDF, plain-PDF, and unsupported input are distinguished | Factur-X/API |
| DOC-006 | Malware/security scan completed where configured | security service |
| DOC-007 | Overall extraction confidence is sufficient for a reliable assessment, independent of any individual field's confidence | API (control profile) |

### Structured e-invoice controls

| ID | Possible control | Typical implementation |
|---|---|---|
| STR-001 | Embedded XML exists and is safely extractable | Factur-X API |
| STR-002 | Format, profile, and version are recognized and supported | Factur-X API |
| STR-003 | XML is well formed and valid against the applicable XSD | Factur-X API |
| STR-004 | Official Schematron/business rules pass or produce traceable findings | Factur-X API |
| STR-005 | Required invoice data are contained in the structured part | deterministic/rules |
| STR-006 | XML and visible hybrid-PDF representation have no material contradiction | deterministic, optional visual comparison |

### Formal invoice information

| ID | Possible control | Typical basis |
|---|---|---|
| FRM-001 | Supplier and buyer names are present | UStG Section 14(4) |
| FRM-002 | Supplier and buyer addresses are present | UStG Section 14(4) |
| FRM-003 | Supplier tax number or VAT ID is present | UStG Section 14(4) |
| FRM-004 | Issue date is present and parseable | UStG Section 14(4) |
| FRM-005 | Invoice number is present | UStG Section 14(4) |
| FRM-006 | Quantity/type of goods or scope/type of service is described | UStG Section 14(4) |
| FRM-007 | Delivery/service date or period is present when applicable | UStG Section 14(4) |
| FRM-008 | Consideration is split by tax rate/exemption and reductions are represented | UStG Section 14(4) |
| FRM-009 | Tax rate and tax amount or exemption reason are present | UStG Section 14(4) |
| FRM-010 | Required special wording is present for the applicable case | UStG Sections 14/14a |
| FRM-011 | Credit note, advance/final invoice, small-value invoice, or travel ticket profile is identified | UStG/UStDV applicability |

### Arithmetic and consistency

| ID | Possible control | Typical implementation |
|---|---|---|
| CAL-001 | Line net amounts are arithmetically consistent | deterministic |
| CAL-002 | Tax bases and tax amounts are consistent with rates and rounding rules | deterministic |
| CAL-003 | Net, tax, gross, allowances/charges, paid amounts, and payable amount reconcile | deterministic |
| CAL-004 | Currency is present, supported, and used consistently | deterministic |
| CAL-005 | Dates and periods are internally plausible | deterministic |
| CAL-006 | Payment terms and due date are internally consistent where present | deterministic |

### Organization and process controls

| ID | Possible control | Required reference |
|---|---|---|
| ORG-001 | Buyer data match the approved organization master-data snapshot | organization master data |
| ORG-002 | Supplier exists and its identifiers match approved supplier data | supplier master data |
| ORG-003 | Supplier VAT ID is externally confirmed when applicable and available | external validation |
| ORG-004 | Purchase order, contract, or other order reference exists where required | procurement data |
| ORG-005 | Invoice corresponds to documented goods receipt or service confirmation | operational evidence |
| ORG-006 | No duplicate invoice exists by number, supplier, amount, date, or source hash | invoice history |
| ORG-007 | Bank details match approved supplier data; changes are highlighted | supplier master data |
| ORG-008 | Amount and account assignment fit configured approval thresholds | approval configuration |
| ORG-009 | Required human role and segregation/four-eyes step are assigned | role/control model |

### Special tax and risk controls

| ID | Possible control | Applicability example |
|---|---|---|
| TAX-001 | Reverse-charge treatment and required wording are consistent | applicable cross-border/domestic cases |
| TAX-002 | Intra-Community supply/acquisition data are consistent | EU transaction |
| TAX-003 | Tax exemption reason and evidence requirement are identified | exempt transaction |
| TAX-004 | Advance payments and final-invoice deductions are consistent | advance/final invoice |
| TAX-005 | Credit-note reference and sign logic are consistent | credit note |
| TAX-006 | Unusual tax rate, country, amount, or supplier combination is flagged | configured risk rules |

### Evidence and traceability

| ID | Possible control | Typical implementation |
|---|---|---|
| EVD-001 | Original source, hash, receipt time, and channel are retained | evidence repository |
| EVD-002 | Extracted value points to XML field, PDF region, or OCR/LLM evidence | canonical contract |
| EVD-003 | Control, rule, schema, and profile versions are retained | control report |
| EVD-004 | Technical and human decisions are timestamped and attributable | audit trail |
| EVD-005 | Structured original is retained unaltered and can be reproduced | archive/integrity control |

### Optional semantic support

| ID | Possible control | Boundary |
|---|---|---|
| SEM-001 | Service description is understandable and sufficiently specific | LLM suggestion, human review |
| SEM-002 | Contradictions between invoice text and structured fields are highlighted | LLM/deterministic comparison |
| SEM-003 | Findings are summarized and possible clarification steps are suggested | optional Reqeli analysis |
| SEM-004 | Similar historical exception patterns are indicated | optional risk support |

Semantic controls only create findings or suggestions. They never establish
legal correctness or perform final approval.

## Suggested implementation waves

| Wave | Scope | Result |
|---|---|---|
| 1 - starter profile | DOC-001 to DOC-005, STR-001 to STR-005 when structured, FRM-001 to FRM-009, CAL-001 to CAL-004, ORG-001, EVD-001 to EVD-003 | Shared baseline for Factur-X/ZUGFeRD and PDF |
| 2 - operating controls | ORG-002 to ORG-009, CAL-005 to CAL-006 | Links invoice checks to master data, order/receipt, approval, and duplicate prevention |
| 3 - tax cases | FRM-010 to FRM-011 and TAX-001 to TAX-005 | Adds explicit applicability profiles for special cases |
| 4 - risk and learning | TAX-006 and SEM-001 to SEM-004 | Adds explainable anomaly and LLM-supported clarification |

The first implementation does not need to implement every Wave 1 control at
once. It must publish the selected `controlProfileId`, catalog version, omitted
controls, and known limits so later controls can be added without changing the
workflow contract.

## Sources

- German VAT Act, especially Section 14:
  <https://www.gesetze-im-internet.de/ustg_1980/__14.html>
- German VAT Act, special invoice obligations in Section 14a:
  <https://www.gesetze-im-internet.de/ustg_1980/__14a.html>
- German VAT Implementation Ordinance, small-value invoices and travel
  tickets in Sections 33 and 34:
  <https://www.gesetze-im-internet.de/ustdv_1980/__33.html>
  and <https://www.gesetze-im-internet.de/ustdv_1980/__34.html>
- German Ministry of Finance e-invoice FAQ, current as checked on 2026-08-07:
  <https://www.bundesfinanzministerium.de/Content/DE/FAQ/e-rechnung.html>
- Current FeRD ZUGFeRD/Factur-X package:
  <https://www.ferd-net.de/en/downloads/publications/details/zugferd-25-deutsch>
