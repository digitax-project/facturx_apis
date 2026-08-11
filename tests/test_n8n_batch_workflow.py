import json
from pathlib import Path

WORKFLOW_PATH = (
    Path(__file__).parent.parent
    / "examples"
    / "n8n"
    / "digitax_invoice_phase1_flow1a_batch_item_v1_0_0.json"
)


def _workflow():
    return json.loads(WORKFLOW_PATH.read_text(encoding="utf-8"))


WEBHOOK_NODE = "01.1 Receive batch item"
PROCESS_NODE = "03.1 Run DigiTax controls"
RESPOND_NODE = "04.2 Respond to batch caller"


def test_batch_workflow_is_portable_and_profile_dynamic():
    workflow = _workflow()
    nodes = {node["name"]: node for node in workflow["nodes"]}
    assert workflow["active"] is True
    assert "instanceId" not in workflow.get("meta", {})
    assert all("credentials" not in node for node in workflow["nodes"])
    assert nodes[WEBHOOK_NODE]["parameters"]["path"] == "phase1-invoice-batch-item"

    process = nodes[PROCESS_NODE]
    assert process["parameters"]["url"].startswith("={{ $env.")
    parameters = process["parameters"]["bodyParameters"]["parameters"]
    organization = next(item for item in parameters if item["name"] == "organizationId")
    assert WEBHOOK_NODE in organization["value"]
    assert "unternehmen-x-demo" not in organization["value"]
    assert "unternehmen-y-demo" not in organization["value"]


def test_batch_workflow_returns_json_with_cors_and_bounded_retry():
    nodes = {node["name"]: node for node in _workflow()["nodes"]}
    process = nodes[PROCESS_NODE]
    assert process["retryOnFail"] is True
    assert process["maxTries"] == 3
    assert process["parameters"]["options"]["response"]["response"]["neverError"] is True

    respond = nodes[RESPOND_NODE]
    assert respond["parameters"]["respondWith"] == "json"
    headers = respond["parameters"]["options"]["responseHeaders"]["entries"]
    assert {item["name"]: item["value"] for item in headers}["Access-Control-Allow-Origin"] == "*"
