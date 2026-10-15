import json

import pytest

from triage.models import ActionKind
from triage.pipeline import Service


def test_outbound_actions_wait_for_approval(service: Service) -> None:
    service.run_ingest()
    pending = service.queue.list(status="pending_approval", limit=500)
    assert pending
    for row in pending:
        kinds = {a["kind"] for a in row["result"]["actions"]}
        assert ActionKind.OUTBOUND.value in kinds
    # Nothing has been sent before a human approved it.
    assert not service.outbox.exists()
    executed = [e for e in service.audit.read() if e["event"] == "action_executed"]
    assert executed and all(e["data"]["kind"] != "outbound" for e in executed)


def test_approve_executes_and_audits(service: Service) -> None:
    service.run_ingest()
    tid = service.queue.list(status="pending_approval", limit=1)[0]["ticket_id"]
    out = service.approve(tid, "alex")
    assert out["status"] == "approved" and "send_reply" in out["executed"]
    sent = [json.loads(line) for line in service.outbox.read_text().splitlines()]
    assert {s["ticket_id"] for s in sent} == {tid}
    events = [e["event"] for e in service.audit.read(ticket_id=tid)]
    assert events[0] == "triaged" and "approved" in events and events[-1] == "action_executed"
    with pytest.raises(ValueError):
        service.approve(tid, "alex")  # cannot approve twice


def test_edited_reply_is_policy_checked(service: Service) -> None:
    service.run_ingest()
    tid = service.queue.list(status="pending_approval", limit=1)[0]["ticket_id"]
    with pytest.raises(ValueError, match="secret"):
        service.approve(tid, "alex", edited_reply="Please send us your PIN so we can check.")
    assert service.queue.get(tid)["status"] == "pending_approval"  # type: ignore[index]
    assert any(e["event"] == "approval_blocked" for e in service.audit.read(ticket_id=tid))


def test_reject(service: Service) -> None:
    service.run_ingest()
    tid = service.queue.list(status="pending_approval", limit=1)[0]["ticket_id"]
    service.reject(tid, "sam", "wrong doc")
    assert service.queue.get(tid)["status"] == "rejected"  # type: ignore[index]
    assert not service.outbox.exists()


def test_audit_chain_detects_tampering(service: Service) -> None:
    service.run_ingest()
    ok, n, _ = service.audit.verify()
    assert ok and n > 100
    lines = service.audit.path.read_text().splitlines()
    tampered = json.loads(lines[5])
    tampered["data"]["priority"] = "P4"
    lines[5] = json.dumps(tampered, sort_keys=True)
    service.audit.path.write_text("\n".join(lines) + "\n")
    ok, n, msg = service.audit.verify()
    assert not ok and n == 7 and "broken" in msg


def test_audit_never_contains_raw_pii(service: Service) -> None:
    service.run_ingest()
    text = service.audit.path.read_text()
    assert "@example.com" not in text and "@example.org" not in text and "4111 1111 1111 1111" not in text
