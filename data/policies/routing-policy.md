# Kestrel routing policy (agreed with the client's support lead in discovery)

| Category | Owning team | Default priority |
|---|---|---|
| fraud_dispute | Fraud & Risk | P2 |
| account_access | Identity & Access | P2 |
| card_issue | Cards Ops | P3 |
| payments_transfer | Payments Ops | P3 |
| kyc_verification | Compliance Ops | P3 |
| technical_bug | App Engineering | P3 |
| billing_fees | Billing Ops | P4 |
| general_inquiry | Tier-1 Support | P4 |

Priority definitions:

- **P1**: money is leaving the account right now or the account is in someone else's hands (account takeover, active unauthorised payments, phishing with credentials shared). First response target: 15 minutes.
- **P2**: money or access is at risk or stuck and the customer cannot fix it alone (lost card, locked out, rent/salary transfer stuck past its window). Target: 1 hour.
- **P3**: something isn't working but nothing is at risk (declines, KYC in review, app bugs, slow transfers inside their window). Target: 4 hours.
- **P4**: questions, plan and fee queries, feedback. Target: 1 business day.

Escalate one level when the customer signals urgency (deadline, "urgent", rent, salary) and the category can plausibly justify it. Never escalate P4 information requests on tone alone.
