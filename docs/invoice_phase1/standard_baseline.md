# Factur-X and ZUGFeRD validation baseline

## Purpose

This file separates three facts that must not be conflated:

1. the current release shown by the official standard owners;
2. the validation artifacts actually vendored by this repository; and
3. the profiles the DigiTax Phase 1 API has reviewed and enabled.

External standard facts are a dated snapshot. They must be checked again
before a later release is claimed.

## Official release snapshot

Checked on: `2026-08-10`

| Fact | Observation |
| --- | --- |
| Current release identified by FeRD/FNFE-MPE | Factur-X `1.09` / ZUGFeRD `2.5` |
| Publication date | `2026-06-10` |
| Recommended use from | `2026-07-01` |
| Relationship | Factur-X 1.09 and ZUGFeRD 2.5 are described as technically identical formats |
| Profiles in the official package | MINIMUM, BASIC_WL, BASIC, EN16931, EXTENDED, each with profile-specific validation artifacts |
| Later release check | The checked official sources did not identify Factur-X 1.09.2 / ZUGFeRD 2.5.2 |

Primary sources:

- FeRD release announcement:
  <https://www.ferd-net.de/aktuelles-veranstaltungen/aktuelles/news/neue-zugferd-version-25-veroeffentlicht>
- FeRD ZUGFeRD 2.5 package description:
  <https://www.ferd-net.de/publikationen-produkte/publikationen/detailseite/zugferd-25-english>
- FNFE-MPE Factur-X release page:
  <https://fnfe-mpe.org/factur-x/>

## Repository baseline

| Profile | Local XSD baseline | Official Schematron in Phase 1 | `/process` status |
| --- | --- | --- | --- |
| EN16931 | Factur-X `1.09` | enabled and reviewed | processable |
| MINIMUM | Factur-X `1.07.2` legacy resource | not enabled | recognized, not processable |
| BASIC_WL | Factur-X `1.07.2` legacy resource | not enabled | recognized, not processable |
| BASIC | Factur-X `1.07.2` legacy resource | not enabled | recognized, not processable |
| EXTENDED | Factur-X `1.07.2` legacy resource | not enabled | recognized, not processable |

The non-EN16931 entries describe inherited local resources, not current
official support claims. They route to `nicht_pruefbar` with
`UNSUPPORTED_PROFILE` in the Phase 1 process.

The exact EN16931 files, hashes, wheel source, and license evidence are in
`facturx/phase1/resources/facturx-1.09-en16931/PROVENANCE.json`.

## Update procedure

Before changing a claimed standard baseline:

1. check the official FeRD and FNFE-MPE release pages;
2. record the check date, release name, publication date, and source URLs;
3. acquire the official or otherwise fully traceable validation package;
4. record file-level SHA-256 hashes and license/provenance;
5. run XSD, Schematron, security, fixture, API, and n8n end-to-end tests;
6. update `/capabilities`, this file, `PROVENANCE.json`, and the README in the
   same reviewed change;
7. do not mark a profile processable until its controls and expected findings
   have been reviewed.
