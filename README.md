# DelegateGuard

DelegateGuard is a Python prototype of a capability-enforcing gateway for tool-using agents. It verifies signed delegation chains, validates tool requests, enforces invocation closure and configured call limits, and writes hash-chained audit events.

The included helpdesk system uses mock tools and process-generated identities. The HTTP app is a local integration demo. The repository is not a production-ready security product: real identity provisioning, durable gateway signing keys, external business adapters, human approval flows, and production monitoring still need to be supplied.

## Quick start

From the repository root, on Windows PowerShell:

```powershell
python -m venv .venv
. .venv/Scripts/Activate.ps1
pip install -r requirements.txt
python -m unittest discover -s tests -v
python experiments/run_experiments.py
```

Run the local HTTP demo with:

```powershell
uvicorn delegateguard.asgi:app --host 127.0.0.1 --port 8000
```

It opens the agent console at `/`, and exposes `GET /health`, `GET /metrics`, `POST /v1/demo/run`, `GET /v1/demo/audit`, and `POST /v1/tool-calls`. The console includes a normal-ticket preset and a prompt-injection example. The demo generates fresh identities at process start, so external clients cannot make authorized tool calls unless they are provisioned with the corresponding signing identity and token. Its purpose is to exercise the HTTP boundary and inspect health/metrics. Do not expose it on a public network.

The experiments use `SimulatedBrain`; generated attack rates are pipeline demonstrations, not evidence about real model behavior.

## Architecture

A request crosses these layers:

1. `api.py` parses HTTP requests and maps gateway decisions to responses.
2. `gateway.py` authenticates the signed request, verifies token scope, invokes argument validation, reserves configured call limits, and dispatches the tool call.
3. `token.py` issues and verifies signed delegation chains. Every delegated block must preserve or narrow parent constraints.
4. `policy.py` evaluates argument constraints carried by the token chain.
5. `state.py` stores invocation closure and per-invocation tool call counters in SQLite.
6. `audit.py` appends hash-chained gateway-signed events as JSONL.
7. `tools.py` implements the local mock helpdesk tools and their input schemas.

`system.py` composes the local demonstration; `llm_brain.py` adapts a supplied model client to structured tool requests. Model output remains untrusted and every resulting request must pass through the gateway.

## Service integration

A deployment should construct its `DelegateGuardGateway` using its managed identity and trust configuration, then pass that gateway to `create_app` in `delegateguard.api`. The HTTP API accepts a signed request and delegation token; it does not provision caller identities, issue tokens, or configure tools for you. Put the service behind TLS and network access controls, and authenticate service operators separately.

Identity objects accept Ed25519 PEM private-key bytes, and `Registry.register_public` accepts trusted public keys. Load key material from a managed secret or workload identity provider; do not commit keys or store private keys in source configuration. The current `HelpdeskSystem` intentionally generates ephemeral identities for its demo. Use a stable gateway signing key if audit signatures must remain verifiable across restarts and key rotation.

`DELEGATEGUARD_STATE` selects the SQLite state file. `DELEGATEGUARD_AUDIT` selects the JSONL audit file. Mount these on protected durable storage and define backup, retention, and recovery procedures. Audit argument fields whose names contain `body`, `content`, `password`, `secret`, or `token` are redacted; other values may still be sensitive, so review schemas before production use.

## Current limitations and next implementation steps

- The helpdesk adapter is in-memory. Real tools need narrow adapters, separate least-privilege credentials, timeouts, idempotency, and bounded retries.
- There is no human approval workflow. Add reviewer identities, approval records bound to action arguments and invocation, and an authenticated approval endpoint before allowing consequential actions.
- `GET /metrics` reports process-local counters only. Export metrics and audit events to the deployment's monitoring and security systems.
- Invocation state is persistent SQLite, but lifecycle cleanup/retention is not implemented.
- Audit files are append-only by application convention, not immutable storage. Protect them from modification and verify them with a stable gateway public key.
- Prompt injection can still misuse an action already allowed by policy. Scope actions to the user's intent and require review for high-impact operations.
- The provider-neutral `LLMBrain` expects a callable that returns structured tool calls; provider setup, credentials, retries, privacy policy, and model-specific validation belong to the deployment.

## Repository map

| Path | Responsibility |
|---|---|
| `delegateguard/api.py`, `asgi.py` | HTTP factory and local demo entrypoint |
| `delegateguard/gateway.py` | Authentication, authorization, and dispatch orchestration |
| `delegateguard/token.py`, `identity.py` | Delegation tokens, signing identities, trust registry |
| `delegateguard/policy.py` | Token-bound argument constraint checks |
| `delegateguard/state.py` | SQLite invocation lifecycle and call counters |
| `delegateguard/audit.py` | Signed hash-chained JSONL audit log |
| `delegateguard/tools.py` | Tool schemas and mock helpdesk implementations |
| `delegateguard/system.py`, `llm_brain.py` | Demo workflow and model adapter interface |
| `experiments/`, `results/` | Simulated evaluations and generated result artifacts |
| `tests/` | Unit tests |
| `PLAN.md` | Implementation status and rollout plan |
