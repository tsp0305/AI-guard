# DelegateGuard implementation plan

This plan separates the working prototype from the work required for a limited pilot. The checked boxes describe repository capabilities; they do not imply production readiness.

## Implemented in the prototype

- [x] Signed Ed25519 delegation chains with tool, expiry, depth, invocation, and argument-constraint checks.
- [x] Strict schemas for the included mock helpdesk tools.
- [x] FastAPI factory and local ASGI demo with health and process-local metrics endpoints.
- [x] SQLite persistence for closed invocations and per-invocation tool call limits.
- [x] JSONL hash-chained audit events signed by the configured gateway identity.
- [x] PEM key loading interfaces for identities and public-key registry setup.
- [x] Provider-neutral structured-output model adapter interface.

## Required before a limited pilot

1. **Identity and keys:** connect managed workload identities, enforce key rotation, load stable gateway signing keys, and verify audit records across restarts and rotations.
2. **Tool adapters:** replace mocks with narrow business-system adapters using isolated least-privilege credentials, timeouts, idempotency, and bounded retries.
3. **Approval workflow:** add reviewer identities and an authenticated approval process bound to the exact invocation, tool, and arguments. Require approval for high-impact actions.
4. **Operational controls:** protect the API with deployment authentication and network policy, export metrics and audit events, configure alerts, and implement state/audit retention and recovery.
5. **Policy review:** version policies and schemas; define limits for records, recipients, data classes, state transitions, and action frequency.
6. **Model integration:** configure a provider client, structured output, privacy controls, and failure behavior. Treat retrieved content and model output as untrusted.

## Validation and release

- Run the unit suite and the simulation suite after code changes.
- Add integration tests for API authentication, restart persistence, key rotation, audit verification, and approval decisions.
- Evaluate prompt injection against the actual selected model and connected tools; simulated results are not evidence of model robustness.
- Use staging to rehearse backups, restore, incident response, and operator review before any pilot.

The local demo is for development and review only. It uses mock tools and ephemeral identities and should not be exposed as a production service.
