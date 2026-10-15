# AGENTS.md

How coding agents (Claude Code, Codex, Cursor, Copilot) should work in this repo. Humans too.
This is a client deployment, not a sandbox: the code touches customer messages and money-adjacent
actions. Being careful matters more than being fast.

## The 30-second map

```
src/triage/
  ingest.py     raw exports -> redacted, de-duplicated Ticket   (PII is removed HERE, first)
  pii.py        email / phone / card (Luhn) redaction + leak detection
  detect.py     language + urgency heuristics
  lexicon.py    the offline classifier's phrases. Client-reviewed. Edit with care.
  classify.py   HeuristicClassifier (default) and LLMClassifier (optional, falls back)
  retrieval.py  BM25 over data/docs/*.md, section level
  draft.py      ExtractiveDrafter (default) and LLMDrafter (optional, falls back)
  policy.py     reply-policy checks + read / internal_write / outbound action tagging
  pipeline.py   Pipeline (pure) and Service (queue + audit + approvals)
  store.py      SQLite approval queue
  audit.py      append-only, hash-chained JSONL audit log
  evals.py      eval harness + regression gate
  api.py, cli.py, static/dashboard.html
data/           synthetic client data: raw exports, help docs, policies, golden + holdout sets
evals/thresholds.json   the regression gate CI enforces
```

## Before you change anything

```bash
make install
make check      # lint + mypy --strict + pytest + eval gate. Must be green before AND after.
```

If `make check` is red before you start, stop and say so. Don't fix unrelated things in the same change.

## How to take a task

1. **Bounded tasks only.** One behaviour change per PR: "add Italian to language detection", not
   "improve the classifier". If the task is fuzzy, write down the acceptance check first and ask.
2. **Test or eval first.** For a bug, add a failing test that reproduces it. For a routing or
   drafting change, add the case to `data/golden/golden.jsonl` (via `scripts/golden_source.py`)
   and watch it fail. Then change code.
3. **Run the eval, paste the diff.** Every PR that touches `classify.py`, `lexicon.py`,
   `retrieval.py`, `draft.py` or `policy.py` includes before/after numbers from `make eval`
   in the description. A gain on golden with a loss on holdout is overfitting, say so.
4. **Small diffs.** Prefer editing an existing function over adding a framework. No new
   dependencies without a reason in the PR description.

## Hard rules

- **No secrets in the repo, ever.** Keys come from env vars (`OPENAI_API_KEY`, `ANTHROPIC_API_KEY`).
  Don't print them, log them, or put them in tests. Tests mock HTTP; they never call a real API.
- **No real customer data.** Everything in `data/` is synthetic. Use `example.com` emails,
  `+44 7700 900xxx` / `555-01xx` phones and public test card numbers in fixtures.
- **PII is redacted before anything else sees it.** Nothing downstream of `ingest.normalize()`
  may receive raw text. If you add a new input path (API field, new export), route it through
  `normalize()` and add a leak test.
- **Outbound means approval.** Any action that contacts the customer or touches their money is
  `ActionKind.OUTBOUND` and goes through `Service.approve()`. Do not add an auto-send path, a
  "trusted" bypass, or a flag that skips approval. If you think one is needed, open an issue.
- **The audit log is append-only.** Never rewrite, truncate or "clean up" `audit.jsonl` in code.
  New decision points get a new `audit.append(...)` event.
- **Do not lower a threshold in `evals/thresholds.json` to make CI pass.** If a change genuinely
  trades one metric for another, that is a conversation with the client lead, recorded in the PR.
- **The offline path must keep working.** `TRIAGE_LLM=off make check` is what CI runs. LLM
  features are additive and must fall back on any error.
- **Golden labels follow `data/policies/routing-policy.md`.** If a label looks wrong, fix the label
  and cite the policy line; don't bend the code to a bad label. Never edit `holdout.jsonl` to
  make numbers go up: it exists to catch exactly that.

## Style

Python 3.11, `mypy --strict`, ruff (line length 120). Dataclasses for domain types, no ORM, no
framework types outside `api.py`. Comments explain *why*, not *what*. Functions that are pure
stay pure (`Pipeline.triage` has no side effects; keep it that way).

## When you're unsure

Say what you'd do and why, and stop. A clear question beats a confident wrong change in a repo
that sends messages to a client's customers.
