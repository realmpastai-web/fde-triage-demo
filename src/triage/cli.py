"""Command line: the same Service the API uses."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from .config import REPO_ROOT, load_settings
from .pipeline import Service


def _service() -> Service:
    return Service.create()


def cmd_run(args: argparse.Namespace) -> int:
    svc = _service()
    if args.reset:
        svc.reset()
    rep = svc.run_ingest()
    print(f"ingested {rep.raw_count} raw -> {len(rep.tickets)} tickets ({rep.duplicates_merged} duplicates merged)")
    print(f"pii redacted: {rep.pii_redacted}  languages: {rep.languages}")
    print(f"queue: {svc.queue.counts()}")
    return 0


def cmd_queue(args: argparse.Namespace) -> int:
    for row in _service().queue.list(status=args.status, limit=args.limit):
        r = row["result"]
        print(
            f"{row['ticket_id']}  {row['priority']}  {row['status']:<17} {row['team']:<18} "
            f"{r['ticket']['subject'][:50]}"
        )
    return 0


def cmd_show(args: argparse.Namespace) -> int:
    row = _service().queue.get(args.ticket_id)
    if not row:
        print("not found", file=sys.stderr)
        return 1
    r = row["result"]
    print(f"{row['ticket_id']}  {row['priority']}  {row['team']}  status={row['status']}")
    print(f"why: {r['classification']['rationale']}  (confidence {r['classification']['confidence']})")
    print(f"\n--- ticket (redacted) ---\n{r['ticket']['subject']}\n{r['ticket']['body']}")
    print(f"\n--- draft ---\n{r['draft']['text']}")
    if r["draft"]["policy_violations"]:
        print(f"\nPOLICY: {r['draft']['policy_violations']}")
    print("\n--- actions ---")
    for a in r["actions"]:
        print(f"  {a['kind']:<15} {a['name']}{'  (needs approval)' if a['kind'] == 'outbound' else ''}")
    return 0


def cmd_approve(args: argparse.Namespace) -> int:
    reply = Path(args.edit).read_text(encoding="utf-8") if args.edit else None
    print(json.dumps(_service().approve(args.ticket_id, args.reviewer, reply)))
    return 0


def cmd_reject(args: argparse.Namespace) -> int:
    print(json.dumps(_service().reject(args.ticket_id, args.reviewer, args.reason)))
    return 0


def cmd_audit(args: argparse.Namespace) -> int:
    svc = _service()
    if args.verify:
        ok, n, msg = svc.audit.verify()
        print(f"{'OK' if ok else 'FAIL'}: {n} entries, {msg}")
        return 0 if ok else 1
    for e in svc.audit.read(ticket_id=args.ticket_id, limit=args.limit):
        print(json.dumps(e, ensure_ascii=False))
    return 0


def cmd_eval(args: argparse.Namespace) -> int:
    from .evals import check_gate, run_eval, to_markdown

    report = run_eval(load_settings())
    md = to_markdown(report)
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    (out / "eval_report.json").write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    (out / "eval_report.md").write_text(md, encoding="utf-8")
    print(md)
    if args.gate:
        thresholds = json.loads(Path(args.gate).read_text(encoding="utf-8"))
        failures = check_gate(report, thresholds)
        if failures:
            print("REGRESSION GATE FAILED:\n  " + "\n  ".join(failures))
            return 1
        print(f"Regression gate passed ({len([k for k in thresholds if not k.startswith('_')])} checks).")
    return 0


def cmd_serve(args: argparse.Namespace) -> int:
    import uvicorn

    uvicorn.run("triage.api:app", host=args.host, port=args.port)
    return 0


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="triage", description="Agentic support triage with a human approval gate")
    sub = p.add_subparsers(dest="cmd", required=True)
    r = sub.add_parser("run", help="ingest the raw exports and triage everything into the queue")
    r.add_argument("--reset", action="store_true", help="clear the queue first (demo)")
    r.set_defaults(fn=cmd_run)
    q = sub.add_parser("queue", help="list the queue")
    q.add_argument("--status", default="pending_approval")
    q.add_argument("--limit", type=int, default=30)
    q.set_defaults(fn=cmd_queue)
    s = sub.add_parser("show", help="show one ticket, its draft and proposed actions")
    s.add_argument("ticket_id")
    s.set_defaults(fn=cmd_show)
    a = sub.add_parser("approve", help="approve outbound actions for a ticket")
    a.add_argument("ticket_id")
    a.add_argument("--reviewer", required=True)
    a.add_argument("--edit", help="path to an edited reply to send instead of the draft")
    a.set_defaults(fn=cmd_approve)
    j = sub.add_parser("reject", help="reject a draft")
    j.add_argument("ticket_id")
    j.add_argument("--reviewer", required=True)
    j.add_argument("--reason", required=True)
    j.set_defaults(fn=cmd_reject)
    au = sub.add_parser("audit", help="print or verify the audit log")
    au.add_argument("--verify", action="store_true")
    au.add_argument("--ticket-id")
    au.add_argument("--limit", type=int, default=20)
    au.set_defaults(fn=cmd_audit)
    e = sub.add_parser("eval", help="run the eval harness")
    e.add_argument("--out", default=str(REPO_ROOT / "reports"))
    e.add_argument("--gate", help="thresholds JSON; exit 1 on regression")
    e.set_defaults(fn=cmd_eval)
    sv = sub.add_parser("serve", help="start the API + dashboard")
    sv.add_argument("--host", default="127.0.0.1")
    sv.add_argument("--port", type=int, default=8000)
    sv.set_defaults(fn=cmd_serve)
    args = p.parse_args(argv)
    return int(args.fn(args))


if __name__ == "__main__":
    raise SystemExit(main())
