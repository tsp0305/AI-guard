# DelegateGuard Finance Demo Plan

## Implemented prototype

- [x] Finance operations use case: sample accounts-payable invoice processing.
- [x] Four LangGraph roles: Invoice Reader, Invoice Verifier, Risk Analyst, Payment Drafter.
- [x] Gemini structured analysis for invoice notes and risk, with a labeled rule-based demo fallback.
- [x] Conditional review path: only verified, low-risk invoices reach the payment drafter.
- [x] Per-invocation, per-invoice, per-agent tool capabilities.
- [x] Sample vendor and purchase-order checks, amount limit, and duplicate detection.
- [x] Simulated payment drafts only after verification passes.
- [x] Demonstration of an invoice prompt injection attempting an out-of-scope draft action; the risk branch requires review.
- [x] Browser console with sample cases, outcomes, and audit events.

## Prototype walkthrough

1. Process `INV-1001`; show a clean verification and draft.
2. Process `INV-1002`; show that vendor mismatch/unapproved status stops draft creation.
3. Process `INV-1003`; show the reader's injected draft attempt blocked by its capability and the risk branch routing the invoice to review without creating a draft.
4. Process `INV-1004`; show a second valid invoice. The sample queue currently has no duplicate pair.

## Future work

1. Add an authenticated human approval/rejection step bound to the exact draft contents.
2. Replace in-memory fixtures with a database and add user-uploaded invoice parsing.
3. Expand Gemini model evaluation across independent cases; treat invoice content and model output as untrusted.
4. Add stable managed identities, audit-key continuity, retention, monitoring, and deployment authentication.
5. Add regression and integration tests for cross-invoice access, malformed tool calls, replay, duplicate handling, and approval enforcement.

The demo has no accounting-system connection and cannot release payments. Keep real payment integrations out of scope until identity, approval, and operational controls are designed and reviewed.
