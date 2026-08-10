"""Generate the reviewable inventory for the vendored EN16931 Schematron."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from collections import Counter
from pathlib import Path

from lxml import etree


REPO_ROOT = Path(__file__).resolve().parent.parent
SOURCE = (
    REPO_ROOT
    / "facturx/phase1/resources/facturx-1.09-en16931/Factur-X_1.09_EN16931.xsl"
)
JSON_OUTPUT = REPO_ROOT / "docs/invoice_phase1/schematron_rule_inventory.json"
MD_OUTPUT = REPO_ROOT / "docs/invoice_phase1/schematron_rule_inventory.md"
NS = {
    "svrl": "http://purl.oclc.org/dsdl/svrl",
    "xsl": "http://www.w3.org/1999/XSL/Transform",
}
RULE_REF = re.compile(r"^\[([^\]]+)\]")


def _one_text(node: etree._Element, name: str) -> str | None:
    values = node.xpath(f'./xsl:attribute[@name="{name}"]/text()', namespaces=NS)
    return values[0].strip() if values else None


def _normalize(values: list[str]) -> str:
    return " ".join(" ".join(values).split())


def _family(rule_ref: str | None) -> str:
    if rule_ref is None:
        return "Factur-X profile/structure constraint"
    if rule_ref.startswith("PEPPOL-"):
        return "PEPPOL recommendation"
    if rule_ref.startswith("CII-"):
        return "CII syntax rule"
    if rule_ref.startswith("BR-FX"):
        return "Factur-X extension rule"
    if rule_ref.startswith("BR-CO-"):
        return "EN16931 common rule"
    if rule_ref.startswith("BR-DEC-"):
        return "EN16931 decimal rule"
    if rule_ref.startswith(
        ("BR-S-", "BR-Z-", "BR-E-", "BR-AE-", "BR-O-", "BR-G-", "BR-IC-")
    ):
        return "EN16931 VAT-category rule"
    if rule_ref.startswith("BR-"):
        return "EN16931 general rule"
    return "Other referenced rule"


def build_inventory() -> dict:
    source_bytes = SOURCE.read_bytes()
    parser = etree.XMLParser(resolve_entities=False, no_network=True, load_dtd=False)
    tree = etree.parse(str(SOURCE), parser)
    rules = []

    for ordinal, node in enumerate(
        tree.xpath("//svrl:failed-assert", namespaces=NS), start=1
    ):
        message = _normalize(node.xpath(".//svrl:text//text()", namespaces=NS))
        match = RULE_REF.match(message)
        standard_ref = match.group(1) if match else None
        templates = node.xpath("ancestor::xsl:template[1]", namespaces=NS)
        template = templates[0] if templates else None
        flag = _one_text(node, "flag")
        rules.append(
            {
                "ordinal": ordinal,
                "technicalId": _one_text(node, "id"),
                "severity": "warning" if flag == "warning" else "blocking",
                "flag": flag,
                "standardRuleReference": standard_ref,
                "family": _family(standard_ref),
                "message": message,
                "testExpression": node.get("test"),
                "contextExpression": template.get("match") if template is not None else None,
                "templateMode": template.get("mode") if template is not None else None,
                "sourceLine": node.sourceline,
            }
        )

    severity_counts = Counter(rule["severity"] for rule in rules)
    family_counts = Counter(rule["family"] for rule in rules)
    explicit_refs = [rule for rule in rules if rule["standardRuleReference"]]
    technical_ids = {rule["technicalId"] for rule in rules}

    return {
        "metadata": {
            "artifact": "Factur-X 1.09 EN16931 compiled Schematron",
            "sourcePath": SOURCE.relative_to(REPO_ROOT).as_posix(),
            "sourceSha256": hashlib.sha256(source_bytes).hexdigest(),
            "generatedFromSource": True,
            "assertionTemplateCount": len(rules),
            "uniqueTechnicalIdCount": len(technical_ids),
            "explicitStandardReferenceCount": len(explicit_refs),
            "profileConstraintWithoutReferenceCount": len(rules) - len(explicit_refs),
            "severityCounts": dict(sorted(severity_counts.items())),
            "familyCounts": dict(sorted(family_counts.items())),
            "interpretation": (
                "An assertion template is a context-specific executable check. "
                "Technical IDs can recur in multiple contexts, so template count "
                "and unique ID count are intentionally different."
            ),
        },
        "rules": rules,
    }


def render_markdown(inventory: dict) -> str:
    meta = inventory["metadata"]
    lines = [
        "# Factur-X 1.09 EN16931 Schematron rule inventory",
        "",
        "This file is generated from the exact vendored compiled Schematron XSL.",
        "Do not edit it manually; run `python tools/generate_schematron_rule_inventory.py`.",
        "",
        "## Interpretation",
        "",
        f"- Assertion templates: `{meta['assertionTemplateCount']}`",
        f"- Unique technical `FX-SCH-A-*` IDs: `{meta['uniqueTechnicalIdCount']}`",
        f"- Assertions with an explicit standard-rule reference: `{meta['explicitStandardReferenceCount']}`",
        f"- Additional profile/structure constraints without such a reference: `{meta['profileConstraintWithoutReferenceCount']}`",
        f"- Severity: `{meta['severityCounts'].get('blocking', 0)}` blocking, `{meta['severityCounts'].get('warning', 0)}` warning",
        f"- Source SHA-256: `{meta['sourceSha256']}`",
        "",
        "The 427 entries are context-specific executable assertion templates, not",
        "427 independent user-selectable DigiTax controls. `STR-004` executes the",
        "artifact as a whole. This inventory is the basis for later grouping, mock",
        "coverage, and control-profile decisions.",
        "",
        "## Families",
        "",
        "| Family | Assertion templates |",
        "| --- | ---: |",
    ]
    for family, count in meta["familyCounts"].items():
        lines.append(f"| {family} | {count} |")

    lines.extend(
        [
            "",
            "## Complete inventory",
            "",
            "The JSON companion additionally contains the test and context XPath,",
            "template mode, source line, and explicit null values.",
            "",
            "| # | Technical ID | Standard reference | Severity | Family | Message |",
            "| ---: | --- | --- | --- | --- | --- |",
        ]
    )
    for rule in inventory["rules"]:
        values = [
            str(rule["ordinal"]),
            rule["technicalId"] or "-",
            rule["standardRuleReference"] or "-",
            rule["severity"],
            rule["family"],
            rule["message"],
        ]
        escaped = [value.replace("|", "\\|").replace("\n", " ") for value in values]
        lines.append("| " + " | ".join(escaped) + " |")
    return "\n".join(lines) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    inventory = build_inventory()
    json_text = json.dumps(inventory, ensure_ascii=False, indent=2) + "\n"
    md_text = render_markdown(inventory)

    if args.check:
        stale = []
        if not JSON_OUTPUT.exists() or JSON_OUTPUT.read_text(encoding="utf-8") != json_text:
            stale.append(str(JSON_OUTPUT))
        if not MD_OUTPUT.exists() or MD_OUTPUT.read_text(encoding="utf-8") != md_text:
            stale.append(str(MD_OUTPUT))
        if stale:
            print("Generated Schematron inventory is stale: " + ", ".join(stale))
            return 1
        return 0

    JSON_OUTPUT.write_text(json_text, encoding="utf-8")
    MD_OUTPUT.write_text(md_text, encoding="utf-8")
    print(f"Wrote {JSON_OUTPUT}")
    print(f"Wrote {MD_OUTPUT}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
