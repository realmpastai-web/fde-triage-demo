import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from triage import api
from triage.config import REPO_ROOT, Settings
from triage.evals import check_gate, run_eval
from triage.pipeline import Service


@pytest.fixture
def client(settings: Settings) -> TestClient:
    api._svc = Service.create(settings)
    api._svc.run_ingest()
    return TestClient(api.app)


def test_dashboard_and_queue(client: TestClient) -> None:
    assert "Kestrel support triage" in client.get("/").text
    q = client.get("/api/queue").json()
    assert len(q) > 100 and q[0]["priority"] == "P1"  # P1 first
    m = client.get("/api/metrics").json()
    assert m["audit_chain_ok"] and m["status_counts"]["pending_approval"] == len(q)


def test_new_ticket_approve_flow(client: TestClient) -> None:
    r = client.post("/api/tickets", json={"subject": "Lost card", "body": "Lost my card, email me at x.y@example.com"})
    assert r.status_code == 200
    body = r.json()
    assert "example.com" not in json.dumps(body)
    tid = body["ticket"]["id"]
    assert client.post(f"/api/tickets/{tid}/approve", json={"reviewer": "alex"}).json()["status"] == "approved"
    assert client.post(f"/api/tickets/{tid}/approve", json={"reviewer": "alex"}).status_code == 409
    audit = client.get(f"/api/audit?ticket_id={tid}").json()
    assert {e["event"] for e in audit} >= {"triaged", "approved", "action_executed"}


def test_eval_meets_committed_gate(settings: Settings) -> None:
    report = run_eval(settings)
    thresholds = json.loads((REPO_ROOT / "evals" / "thresholds.json").read_text())
    assert check_gate(report, thresholds) == []
    assert report["pii"]["injected_leaks"] == 0 and report["pii"]["corpus_leaks"] == 0


def test_gate_catches_regression() -> None:
    fake = {"routing": {"category_accuracy": 50.0}}
    assert check_gate(fake, {"routing.category_accuracy": {"min": 90}}) != []


def test_golden_set_shape() -> None:
    rows = [json.loads(x) for x in Path(REPO_ROOT / "data" / "golden" / "golden.jsonl").read_text().splitlines()]
    assert len(rows) == 40 and all({"category", "team", "priority", "expected_doc"} <= set(r["label"]) for r in rows)
