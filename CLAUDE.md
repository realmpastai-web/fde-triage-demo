# CLAUDE.md

Read `AGENTS.md` first; it is the source of truth for this repo and applies to you in full.

Claude-specific notes:

- Start every session with `make check` and report the result before editing.
- Use plan mode for anything that touches more than two files under `src/triage/`. Show the
  plan, including which test or golden case will prove the change, before writing code.
- Keep the change and its test in the same commit. Don't leave a TODO where a test should be.
- Never run `python -m triage approve` against a non-demo data dir, and never set
  `OPENAI_API_KEY` / `ANTHROPIC_API_KEY` yourself. Live-model evals are run by a human with a budget.
- When you finish, summarise: what changed, eval before/after (golden and holdout), anything you
  were unsure about.
