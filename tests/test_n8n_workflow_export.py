"""Regression guard for examples/n8n/digitax_invoice_intake.json.

This is a structural check, not a live n8n import. examples/n8n/README.md
records the real import-verification result (via the official n8nio/n8n
Docker image, since the local `n8n` CLI needs a newer Node than this
environment has) separately -- this test exists so a future edit can't
silently re-introduce a secret, a real internal URL, or the real
organization name/address that were stripped out in this slice.
"""
import json
import re
from pathlib import Path

WORKFLOW_PATH = (
    Path(__file__).parent.parent / "examples" / "n8n" / "digitax_invoice_intake.json"
)

FORBIDDEN_PATTERNS = [
    # Not just DSNs with literal credentials -- Reqeli must never receive a
    # Postgres connection string at all, env-var-templated or otherwise
    # (an earlier draft of this sanitization still shipped a live DB
    # password over HTTP via an env-var-templated DSN; caught in review).
    # It gets an opaque connection_ref it resolves server-side instead.
    (re.compile(r"postgresql://"), "a Postgres connection string of any kind"),
    (re.compile(r"sharepoint\.com", re.IGNORECASE), "a SharePoint URL"),
    (re.compile(r"outlook\.office365\.com", re.IGNORECASE), "an Outlook deep link"),
    (re.compile(r"host\.docker\.internal"), "a hardcoded local-dev host"),
    (re.compile(r"vn ?impex", re.IGNORECASE), "the real organization name"),
]


def _load_workflow() -> dict:
    return json.loads(WORKFLOW_PATH.read_text(encoding="utf-8"))


def test_workflow_file_exists_and_is_valid_json():
    assert WORKFLOW_PATH.exists(), "sanitized n8n export is missing"
    _load_workflow()  # raises if not valid JSON


def test_workflow_has_no_instance_id():
    data = _load_workflow()
    assert "instanceId" not in data.get("meta", {})


def test_workflow_credentials_are_placeholders():
    data = _load_workflow()
    for node in data["nodes"]:
        for cred_type, cred in node.get("credentials", {}).items():
            assert cred["id"] == "REPLACE_WITH_YOUR_CREDENTIAL_ID", (
                f"node {node['name']!r} credential {cred_type!r} is not a placeholder"
            )


def test_workflow_has_no_forbidden_content():
    text = json.dumps(_load_workflow())
    for pattern, description in FORBIDDEN_PATTERNS:
        assert not pattern.search(text), f"found {description} in the sanitized export"


def test_workflow_connections_reference_existing_nodes():
    data = _load_workflow()
    node_names = {n["name"] for n in data["nodes"]}
    node_ids = [n["id"] for n in data["nodes"]]
    assert len(node_ids) == len(set(node_ids)), "duplicate node ids"
    assert len(data["nodes"]) == len(node_names), "duplicate node names"

    for source_name, outputs in data.get("connections", {}).items():
        assert source_name in node_names, f"connection source {source_name!r} does not exist"
        for output_type, branches in outputs.items():
            for branch in branches:
                for edge in branch:
                    assert edge["node"] in node_names, (
                        f"connection target {edge['node']!r} does not exist "
                        f"(referenced from {source_name!r})"
                    )


def test_reqeli_request_uses_opaque_connection_ref_not_db_credentials():
    """Reqeli must own its DB credentials server-side; n8n sends only an
    opaque reference, never a connection string of any kind."""
    data = _load_workflow()
    prepare_reqeli = next(n for n in data["nodes"] if n["name"] == "Prepare Reqeli")
    code = prepare_reqeli["parameters"]["jsCode"]
    assert "connection_ref" in code
    assert "connection_string" not in code
    assert "postgresql://" not in code


def test_reqeli_is_disabled_by_default():
    """AGENTS.md: Reqeli must be behind an optional disabled-by-default gate."""
    data = _load_workflow()
    trigger_node = next(n for n in data["nodes"] if n["name"] == "Trigger Reqeli?")
    conditions_block = trigger_node["parameters"]["conditions"]
    assert conditions_block["combinator"] == "and", (
        "Reqeli trigger conditions must be AND-ed with an explicit opt-in gate"
    )
    env_gate = [
        c
        for c in conditions_block["conditions"]
        if "REQELI_ENABLED" in c.get("leftValue", "")
    ]
    assert env_gate, "no REQELI_ENABLED environment gate found on the Reqeli trigger"
