# Eval report

Provider: `heuristic`

| Metric | Golden (n=40) | Holdout (n=20) |
|---|---|---|
| Category accuracy % | 100.0 | 75.0 |
| Team routing accuracy % | 100.0 | 75.0 |
| Priority exact % | 100.0 | 65.0 |
| Priority within one level % | 100.0 | 95.0 |
| P1 recall % | 100.0 | 0.0 |
| Under-prioritised tickets | 0 | 7 |
| Flagged low-confidence -> human triage | 0 | 10 |
| Misroutes caught by that flag | 0/0 | 5/5 |
| Drafts with >=1 citation % | 100.0 | 100.0 |
| Expected doc cited % | 92.5 | 75.0 |
| Expected doc is first citation % | 85.0 | 75.0 |
| Policy-clean drafts % | 100.0 | 100.0 |

| PII check | Values | Leaks |
|---|---|---|
| Injected (email+phone+card on every golden ticket) | 123 | 0 |
| Client export (159 raw tickets) | 235 | 0 |

Latency per ticket: p50 1.04 ms, p95 1.17 ms. Cost per ticket: $0.0.

## Baseline: first-response time in the legacy queue

| Priority (as triaged) | Tickets | Median FRT (min) | Target (min) | Over target |
|---|---|---|---|---|
| P1 | 10 | 324 | 15 | 100.0% |
| P2 | 38 | 417 | 60 | 100.0% |
| P3 | 48 | 509 | 240 | 87.5% |
| P4 | 53 | 624 | 480 | 64.2% |

## Misses (holdout)

| id | subject | expected | got | conf | flagged |
|---|---|---|---|---|---|
| H001 | Help | card_issue/P2 | card_issue/P3 | 0.449 | False |
| H002 | payment fails | card_issue/P3 | technical_bug/P3 | 0.377 | True |
| H004 | Mortgage payment | payments_transfer/P2 | card_issue/P3 | 0.195 | True |
| H005 | cannot get in | account_access/P2 | kyc_verification/P3 | 0.194 | True |
| H011 | strange payments | fraud_dispute/P1 | fraud_dispute/P2 | 0.382 | True |
| H012 | refund from shop | fraud_dispute/P3 | billing_fees/P4 | 0.241 | True |
| H013 | Was this phishing? | fraud_dispute/P1 | fraud_dispute/P2 | 0.458 | False |
| H019 | Compte bloqué | account_access/P2 | billing_fees/P4 | 0.387 | True |
