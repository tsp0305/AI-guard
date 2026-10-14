# DelegateGuard Finance Demo Plan

## Implemented prototype

- [x] Finance operations use case: sample accounts-payable invoice processing.
- [x] Three separate agent roles: Invoice Reader, Invoice Verifier, Payment Drafter.
- [x] Per-invocation, per-invoice, per-agent tool capabilities.
- [x] Sample vendor and purchase-order checks, amount limit, and duplicate detection.
- [x] Simulated payment drafts only after verification passes.
- [x] Demonstration of an invoice prompt injection attempting an out-of-scope draft action.
- [x] Browser console with sample cases, outcomes, and audit events.

## Prototype walkthrough

1. Process `INV-1001`; show a clean verification and draft.
2. Process `INV-1002`; show that vendor mismatch/unapproved status stops draft creation.
3. Process `INV-1003`; show the reader's injected draft attempt blocked by its capability, followed by verification and a legitimate draft by the Payment Drafter.
4. Process `INV-1004`; show duplicate detection.

## Future work

1. Add an authenticated human approval/rejection step bound to the exact draft contents.
2. Replace in-memory fixtures with a database and add user-uploaded invoice parsing.
3. Replace deterministic agent logic with an LLM adapter; treat invoice content and model output as untrusted.
4. Add stable managed identities, audit-key continuity, retention, monitoring, and deployment authentication.
5. Add regression and integration tests for cross-invoice access, malformed tool calls, replay, duplicate handling, and approval enforcement.

The demo has no accounting-system connection and cannot release payments. Keep real payment integrations out of scope until identity, approval, and operational controls are designed and reviewed.
