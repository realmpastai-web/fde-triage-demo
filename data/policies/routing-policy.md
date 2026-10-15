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

## Fraud and account-takeover escalation (agreed with the support lead and Fraud & Risk, Oct 2026)

Added after the first holdout showed two urgent fraud tickets landing at P2. The asymmetry is
deliberate: an under-ranked fraud ticket costs the customer money and us a reimbursement; an
over-ranked one costs a Fraud & Risk specialist a few minutes. **When a ticket plausibly meets a
P1 condition below, rank it P1.** This applies whatever category the ticket is routed to.

A ticket is **P1** when the customer reports any of:

1. **Money already moved without consent.** A payment, card use, withdrawal or transfer on their
   account that they say they did not make, authorise or recognise, including "a merchant I've
   never heard of / never used", or card use somewhere they could not have been.
2. **Someone else has control of the account.** Another person signed in, or changed the email,
   phone, password, PIN or devices, without the customer doing it; or the customer is locked out
   *and* reports a sign of a third party (an alert, a change or a login they didn't make).
3. **Credentials or codes handed over.** The customer gave, read out, typed or sent a one-time
   code, PIN, password or card details to someone other than Kestrel's own app.
4. **An impersonation scam in progress.** Someone posing as Kestrel, a bank or the police has asked
   them to move money (e.g. to a "safe account") or to share a code, and the customer has not
   said they refused.

These stay **below P1** (near misses):

- A payment the customer doesn't recognise but suggests may be their own (a subscription under a
  different merchant name), or a balance that "looks off" with no third party involved: **P2**
  (fraud default), so a specialist checks within the hour.
- A phishing message or call the customer ignored, deleted or hung up on without sharing anything: **P2**.
- A new-login alert the customer says was them: category default.
- A lost or stolen card with no payments the customer disputes: **P2** (lost card).
- Merchant disputes where the customer authorised the purchase (not delivered, charged twice,
  refund not received, a fee or charge they dispute with the merchant or under their plan): **P3**
  for merchant disputes, P4 for Kestrel fee queries. Disputing the amount is not the same as not
  having made the payment.

Tickets that meet one of these conditions are owned by **Fraud & Risk** (category `fraud_dispute`), even when
they also mention a card, a login or a transfer. They page the Fraud & Risk on-call and are never parked in the
low-confidence triage queue.

