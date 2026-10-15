"""Eval harness. Offline, deterministic, runs in CI in a few seconds.

Measures what the client actually cares about, in this order:
1. Did it route to the right team at the right priority (and, when wrong, did it say so)?
2. Did any customer PII survive into anything we store or send?
3. Is every draft grounded in a cited help-centre article, and policy-clean?
4. Latency and cost per ticket.
Plus a baseline of the business metric (first-response time) from the client's own export.
"""

from __future__ import annotations

import json
import statistics
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .config import PRIORITIES, Settings, load_settings
from .ingest import ingest, load_raw_dir, normalize
from .models import RawTicket, TriageResult
from .pii import find_leaks, redact
from .pipeline import Pipeline

# holdout_v1 was inspected while fixing P1 recall (Oct 2026), so it is now a *seen* regression set.
# holdout_v2 was written and committed before that fix ran against it (see scripts/holdout_v2_source.py).
HOLDOUTS = ("holdout_v1", "holdout_v2")
HOLDOUT_LABELS = {"holdout_v1": "Holdout v1, seen", "holdout_v2": "Holdout v2, new"}
FRT_TARGET_MIN = {"P1": 15, "P2": 60, "P3": 240, "P4": 480}
INJECT = " Contact me at jane.roe+test@example.com or +44 7700 900123. Card 4111 1111 1111 1111."


@dataclass
class GoldenItem:
    id: str
    subject: str
    body: str
    label: dict[str, str]


def load_golden(path: Path) -> list[GoldenItem]:
    out = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            d = json.loads(line)
            out.append(GoldenItem(d["id"], d["subject"], d["body"], d["label"]))
    return out


def _pct(n: int | float, d: int | float) -> float:
    return round(100.0 * n / d, 1) if d else 0.0


def _serialised(r: TriageResult) -> str:
    return json.dumps(r.to_dict(), ensure_ascii=False)


def routing_metrics(
    pipe: Pipeline, items: list[GoldenItem]
) -> tuple[dict[str, Any], list[dict[str, Any]], list[TriageResult]]:
    results, misses = [], []
    cat = team = prio = prio1 = under = flagged_miss = miss = p1_total = p1_hit = flagged = 0
    p1_pred = p1_false = 0
    for g in items:
        t = normalize(RawTicket("golden", g.id, "", "eval@example.com", "email", g.subject, g.body))
        r = pipe.triage(t)
        results.append(r)
        c, lab = r.classification, g.label
        ok_cat = c.category == lab["category"]
        cat += ok_cat
        team += c.team == lab["team"] or (c.needs_human_triage and ok_cat)
        prio += c.priority == lab["priority"]
        d = PRIORITIES.index(c.priority) - PRIORITIES.index(lab["priority"])
        prio1 += abs(d) <= 1
        under += d > 0
        flagged += c.needs_human_triage
        if lab["priority"] == "P1":
            p1_total += 1
            p1_hit += c.priority == "P1"
        if c.priority == "P1":
            p1_pred += 1
            p1_false += lab["priority"] != "P1"
        if not ok_cat:
            miss += 1
            flagged_miss += c.needs_human_triage
        if not ok_cat or c.priority != lab["priority"]:
            misses.append(
                {
                    "id": g.id,
                    "subject": g.subject,
                    "expected": f"{lab['category']}/{lab['priority']}",
                    "got": f"{c.category}/{c.priority}",
                    "confidence": c.confidence,
                    "flagged_for_human": c.needs_human_triage,
                }
            )
    n = len(items)
    return (
        {
            "n": n,
            "category_accuracy": _pct(cat, n),
            "team_accuracy": _pct(team, n),
            "priority_exact": _pct(prio, n),
            "priority_within_one": _pct(prio1, n),
            "under_prioritised": under,
            "p1_total": p1_total,
            "p1_recall": _pct(p1_hit, p1_total),
            # Of tickets ranked P1, how many deserved it (100 when nothing was ranked P1).
            "p1_precision": _pct(p1_pred - p1_false, p1_pred) if p1_pred else 100.0,
            # Non-P1 tickets wrongly paged as P1, as % of all non-P1 tickets: the cost side of the safety bias.
            "p1_over_escalation": _pct(p1_false, n - p1_total),
            "flagged_for_human": flagged,
            "misroutes_caught_by_flag": f"{flagged_miss}/{miss}",
        },
        misses,
        results,
    )


def grounding_metrics(items: list[GoldenItem], results: list[TriageResult]) -> dict[str, Any]:
    n = len(items)
    cited = sum(1 for r in results if r.draft.citations)
    expected = sum(
        1
        for g, r in zip(items, results, strict=True)
        if g.label["expected_doc"] in {c.doc_id for c in r.draft.citations}
    )
    top1 = sum(
        1
        for g, r in zip(items, results, strict=True)
        if r.draft.citations and r.draft.citations[0].doc_id == g.label["expected_doc"]
    )
    clean = sum(1 for r in results if not r.draft.policy_violations)
    return {
        "drafts_with_citation": _pct(cited, n),
        "expected_doc_cited": _pct(expected, n),
        "expected_doc_top1": _pct(top1, n),
        "policy_clean_drafts": _pct(clean, n),
    }


def pii_metrics(pipe: Pipeline, items: list[GoldenItem], settings: Settings) -> dict[str, Any]:
    """Two checks: injected PII on every golden ticket, and every raw ticket in the client export."""
    injected_leaks = injected_found = 0
    for g in items:
        raw = RawTicket("golden", g.id, "", "eval@example.com", "email", g.subject, g.body + INJECT)
        original = redact(raw.subject + "\n" + raw.body).findings
        injected_found += len(original)
        out = _serialised(pipe.triage(normalize(raw)))
        injected_leaks += len(find_leaks(original, out))
    raws = load_raw_dir(settings.raw_dir)
    corpus_leaks = corpus_found = 0
    for raw in raws:
        original = redact(raw.subject + "\n" + raw.body).findings
        if raw.customer_email:
            original += redact(raw.customer_email).findings
        corpus_found += len(original)
        out = _serialised(pipe.triage(normalize(raw)))
        corpus_leaks += len(find_leaks(original, out))
    return {
        "injected_pii_values": injected_found,
        "injected_leaks": injected_leaks,
        "corpus_tickets": len(raws),
        "corpus_pii_values": corpus_found,
        "corpus_leaks": corpus_leaks,
    }


def perf_metrics(
    pipe: Pipeline, results: list[TriageResult], items: list[GoldenItem], repeats: int = 5
) -> dict[str, Any]:
    tickets = [r.ticket for r in results]
    lat: list[float] = []
    for _ in range(repeats):
        for t in tickets:
            t0 = time.perf_counter()
            pipe.triage(t)
            lat.append((time.perf_counter() - t0) * 1000)
    lat.sort()
    costs = [r.cost_usd for r in results]
    return {
        "latency_ms_p50": round(statistics.median(lat), 2),
        "latency_ms_p95": round(lat[int(0.95 * len(lat)) - 1], 2),
        "cost_usd_per_ticket": round(sum(costs) / len(costs), 6),
        "provider": results[0].classification.provider,
    }


def baseline_metrics(pipe: Pipeline, settings: Settings) -> dict[str, Any]:
    """First-response time in the client's legacy FIFO queue, grouped by the priority our
    triage assigns. This is the 'before' number; 'after' comes from shadow mode."""
    rep = ingest(load_raw_dir(settings.raw_dir))
    by: dict[str, list[float]] = {p: [] for p in PRIORITIES}
    for t in rep.tickets:
        if t.first_response_minutes is not None:
            by[pipe.triage(t).classification.priority].append(t.first_response_minutes)
    rows = {}
    for p, v in by.items():
        if v:
            rows[p] = {
                "tickets": len(v),
                "median_frt_min": round(statistics.median(v)),
                "target_min": FRT_TARGET_MIN[p],
                "pct_over_target": _pct(sum(x > FRT_TARGET_MIN[p] for x in v), len(v)),
            }
    return {
        "raw_tickets": rep.raw_count,
        "after_dedupe": len(rep.tickets),
        "duplicates_merged": rep.duplicates_merged,
        "languages": rep.languages,
        "frt_by_priority": rows,
    }


def run_eval(settings: Settings | None = None, holdout: bool = True) -> dict[str, Any]:
    s = settings or load_settings()
    pipe = Pipeline.build(s)
    golden = load_golden(s.golden_path)
    routing, misses, results = routing_metrics(pipe, golden)
    report: dict[str, Any] = {
        "routing": routing,
        "grounding": grounding_metrics(golden, results),
        "pii": pii_metrics(pipe, golden, s),
        "perf": perf_metrics(pipe, results, golden),
        "baseline": baseline_metrics(pipe, s),
        "misses": misses,
    }
    for name in HOLDOUTS:
        hpath = s.golden_path.with_name(f"{name}.jsonl")
        if holdout and hpath.exists():
            h = load_golden(hpath)
            h_routing, h_misses, h_results = routing_metrics(pipe, h)
            report[name] = {"routing": h_routing, "grounding": grounding_metrics(h, h_results), "misses": h_misses}
    return report


def check_gate(report: dict[str, Any], thresholds: dict[str, Any]) -> list[str]:
    """Return failed checks. Each threshold key is 'section.metric' with a 'min' or 'max'."""
    failures = []
    for key, rule in thresholds.items():
        if key.startswith("_"):
            continue
        node: Any = report
        for part in key.split("."):
            node = node[part]
        value = float(node)
        if "min" in rule and value < rule["min"]:
            failures.append(f"{key} = {value} < min {rule['min']}")
        if "max" in rule and value > rule["max"]:
            failures.append(f"{key} = {value} > max {rule['max']}")
    return failures


def to_markdown(r: dict[str, Any]) -> str:
    ro, gr, pi, pe = r["routing"], r["grounding"], r["pii"], r["perf"]
    sets = [h for h in HOLDOUTS if h in r]
    head = " | ".join([f"Golden (n={ro['n']})"] + [f"{HOLDOUT_LABELS[h]} (n={r[h]['routing']['n']})" for h in sets])
    lines = [
        "# Eval report",
        "",
        f"Provider: `{pe['provider']}`",
        "",
        f"| Metric | {head} |",
        "|---|" + "---|" * (1 + len(sets)),
    ]
    for k, label in [
        ("category_accuracy", "Category accuracy %"),
        ("team_accuracy", "Team routing accuracy %"),
        ("priority_exact", "Priority exact %"),
        ("priority_within_one", "Priority within one level %"),
        ("p1_recall", "P1 recall %"),
        ("p1_precision", "P1 precision %"),
        ("p1_over_escalation", "P1 over-escalation (% of non-P1 paged as P1)"),
        ("under_prioritised", "Under-prioritised tickets"),
        ("flagged_for_human", "Flagged low-confidence -> human triage"),
        ("misroutes_caught_by_flag", "Misroutes caught by that flag"),
    ]:
        cells = [str(ro[k])] + [str(r[h]["routing"].get(k, "-")) for h in sets]
        if k == "p1_recall":
            cells = [f"{ro[k]} ({ro['p1_total']} P1s)"] + [
                f"{r[h]['routing'][k]} ({r[h]['routing']['p1_total']} P1s)" for h in sets
            ]
        lines.append(f"| {label} | " + " | ".join(cells) + " |")
    for k, label in [
        ("drafts_with_citation", "Drafts with >=1 citation %"),
        ("expected_doc_cited", "Expected doc cited %"),
        ("expected_doc_top1", "Expected doc is first citation %"),
        ("policy_clean_drafts", "Policy-clean drafts %"),
    ]:
        lines.append(f"| {label} | " + " | ".join([str(gr[k])] + [str(r[h]["grounding"][k]) for h in sets]) + " |")
    lines += [
        "",
        "| PII check | Values | Leaks |",
        "|---|---|---|",
        f"| Injected (email+phone+card on every golden ticket) | {pi['injected_pii_values']} "
        f"| {pi['injected_leaks']} |",
        f"| Client export ({pi['corpus_tickets']} raw tickets) | {pi['corpus_pii_values']} | {pi['corpus_leaks']} |",
        "",
        f"Latency per ticket: p50 {pe['latency_ms_p50']} ms, p95 {pe['latency_ms_p95']} ms. "
        f"Cost per ticket: ${pe['cost_usd_per_ticket']}.",
        "",
        "## Baseline: first-response time in the legacy queue",
        "",
        "| Priority (as triaged) | Tickets | Median FRT (min) | Target (min) | Over target |",
        "|---|---|---|---|---|",
    ]
    for p, row in r["baseline"]["frt_by_priority"].items():
        lines.append(
            f"| {p} | {row['tickets']} | {row['median_frt_min']} | {row['target_min']} | {row['pct_over_target']}% |"
        )
    for name, ms in [("golden", r["misses"])] + [(h, r[h].get("misses", [])) for h in sets]:
        if ms:
            lines += [
                "",
                f"## Misses ({name})",
                "",
                "| id | subject | expected | got | conf | flagged |",
                "|---|---|---|---|---|---|",
            ]
            lines += [
                f"| {m['id']} | {m['subject']} | {m['expected']} | {m['got']} "
                f"| {m['confidence']} | {m['flagged_for_human']} |"
                for m in ms
            ]
    return "\n".join(lines) + "\n"
