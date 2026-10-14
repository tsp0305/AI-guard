# DelegateGuard

DelegateGuard is a small, interactive prototype that demonstrates how to govern tool access in a multi-agent finance workflow. Its sample accounts-payable process reviews invoices and prepares simulated payment drafts while limiting each agent to the specific action it needs.

> **Prototype only:** this project uses synthetic records and simulated drafts. It does not connect to a bank or accounting system, approve or release payments, or move money.

## What problem does it address?

When agents hand work to other agents, a broadly shared tool credential can let any agent perform actions outside its intended role. For example, an invoice-reading agent that encounters malicious instructions should not be able to create a payment draft. If every agent shares the same authority, it is harder to contain misuse and determine which agent made a tool call.

DelegateGuard demonstrates a least-privilege approach: each agent gets a short-lived, signed capability for a specific invocation, with a narrow tool scope and invoice constraint. A gateway checks each tool call against that capability and the project policy, then records whether the call was allowed or blocked. This limits the actions available to an agent and provides an audit trail for the demo.

## What the project does

The browser console runs a three-agent accounts-payable workflow on synthetic invoice, vendor, and purchase-order records. Sample amounts are denominated in Indian rupees (INR) and formatted for the Indian locale:

1. **Invoice Reader** reads the selected invoice.
2. **Invoice Verifier** checks the vendor, purchase order, currency, amount, and duplicate invoice number.
3. **Payment Drafter** creates a simulated draft only after verification succeeds.

The UI streams the workflow stages and tool decisions as they happen. A successful draft is marked as awaiting human approval; there is no payment-release action.

## Features

- **Scoped agent permissions:** reader, verifier, and drafter each have a distinct permitted tool.
- **Invocation-bound capabilities:** calls are tied to the current invoice and workflow invocation, with limited call counts and expiry.
- **Gateway enforcement:** requests are authenticated and checked before a finance tool runs.
- **Invoice validation:** sample rules check vendor approval, purchase-order vendor and currency, amount limits, and duplicate invoice numbers.
- **Prompt-injection demonstration:** one sample invoice contains hostile instructions. The reader's attempted draft creation is outside its scope and is blocked.
- **Live workflow display:** the UI shows agent progress, verification results, draft status, and allowed or blocked calls.
- **Audit and state persistence:** the demo records gateway activity and invocation state locally using a signed audit log and SQLite.
- **Safe simulated payments:** drafts are local sample records and cannot be released or paid.

## Run locally

From the repository root:

```powershell
python -m venv .venv
. .venv/Scripts/Activate.ps1
pip install -r requirements.txt
uvicorn delegateguard.asgi:app --host 127.0.0.1 --port 8000
```

Open [http://127.0.0.1:8000](http://127.0.0.1:8000), select an invoice, and choose **Process invoice**. The workflow is deterministic Python code over sample data; it does not call an LLM.

## Sample scenarios

| Invoice | Demo behavior |
|---|---|
| `INV-1001` | Approved vendor and matching purchase order; verification passes and a simulated draft is created. |
| `INV-1002` | Vendor is unapproved and does not match the purchase order; flagged for review and no draft is created. |
| `INV-1003` | Invoice notes contain hostile instructions; the reader's attempt to create a draft is blocked, then the authorized verification flow continues. |
| `INV-1004` | A second valid Acme invoice, used to show that distinct invoice numbers can be processed separately. |

Duplicate invoice detection is implemented in the finance validation rules. The current sample queue does not include a duplicate pair.

## Agent roles and functions

| Agent | Allowed function | Responsibility |
|---|---|---|
| Invoice Reader | `read_invoice` | Reads only the selected invoice. It cannot verify records or create a draft. |
| Invoice Verifier | `verify_invoice` | Checks invoice details against vendor and purchase-order records. |
| Payment Drafter | `create_payment_draft` | Creates a draft after successful verification. The adapter uses the verified invoice's payee and amount; the agent cannot release a payment. |

The workflow orchestrator issues the scoped capabilities and invokes the agents in order. The gateway validates each signed request, checks its scope and constraints, dispatches permitted tools, and logs the decision.

## HTTP API

| Method and path | Function |
|---|---|
| `GET /` | Serves the finance operations UI. |
| `GET /health` | Returns service health. |
| `GET /metrics` | Returns process-local allowed, denied, and error counters. |
| `GET /v1/finance/invoices` | Lists the synthetic invoice queue. |
| `POST /v1/finance/process` | Runs the workflow and returns its result. Request body: `{"invoice_id":"INV-1001"}`. |
| `POST /v1/finance/process/stream` | Streams agent stages, tool decisions, and the final result for the UI. |
| `GET /v1/finance/drafts` | Lists simulated drafts awaiting human approval. |
| `GET /v1/finance/audit?limit=50` | Returns recent gateway audit events. |

## Project layout

| Path | Purpose |
|---|---|
| `delegateguard/finance/data.py` | Synthetic invoices, vendors, and purchase orders. |
| `delegateguard/finance/agents.py` | Reader, verifier, and payment-drafter agent logic. |
| `delegateguard/finance/tools.py` | Finance tool definitions and validation rules. |
| `delegateguard/finance/workflow.py` | Workflow orchestration and scoped capability issuance. |
| `delegateguard/ui/index.html` | Interactive finance console. |
| `delegateguard/api.py` | HTTP endpoints and live event streaming. |
| `delegateguard/gateway.py` | Request authentication, authorization, policy enforcement, and tool dispatch. |
| `delegateguard/token.py`, `identity.py` | Demo identities and signed capabilities. |
| `delegateguard/policy.py`, `state.py`, `audit.py` | Policy checks, SQLite state, and audit logging. |
| `experiments/`, `tests/` | Earlier helpdesk prototype materials and project checks. |
| `PLAN.md` | Project scope and proposed future work. |

## Research background and evaluation

DelegateGuard also contains an exploratory security-research prototype. The research question is whether per-agent identities and invocation-bound, attenuating capabilities can reduce unauthorized tool use in delegated workflows while preserving legitimate task completion and producing attributable audit events. This connects to the broader problems of least-privilege authorization, confused deputies, delegation, prompt injection, replay, and forensic attribution in agentic systems.

The repository has two related but distinct parts:

- The **helpdesk simulator** in `delegateguard/system.py` and `experiments/` is the earlier experimental environment. It compares a shared-authority baseline with DelegateGuard across indirect prompt-injection cases, benign tasks, direct escalation attempts, authorization depth, and an in-scope misuse case.
- The **finance operations demo** described above is an interactive use case showing the same access-control concept in an invoice workflow. Its agents use deterministic Python logic and sample records; it is not the experimental evaluation and does not use a real LLM.

The experiment runner is `experiments/run_experiments.py`. Its generated outputs are in `results/results.json` and `results/results.md`. The checked-in results use a `SimulatedBrain` that follows injected instructions with a configured probability; they are simulation outputs, not measurements of a deployed system or a real language model. For example, the recorded helpdesk simulation reports zero out-of-scope attack success for DelegateGuard in its tested cases, while its separate in-scope misuse case still succeeds frequently. That limitation is important: capability enforcement can bound what tools and resources a compromised agent may access, but it does not determine whether an allowed action is appropriate.

Treat these results as exploratory and specific to this simulator, its generated cases, configuration, and implementation. They do not establish general security effectiveness, real-world prompt-injection resistance, or production performance. Re-run the experiments before citing results, inspect the generated artifacts and configuration, and clearly label the simulated agent. A stronger evaluation should use independently designed cases, repeated runs and uncertainty estimates, explicit false-block and task-success measurements, and carefully controlled real-model experiments where appropriate. Do not present simulator percentages as real-world or LLM evaluation results.

## Current scope and limitations

This is a learning and demonstration prototype, not a production finance system. It uses deterministic agent logic and synthetic in-memory business records. It does not parse uploaded invoices, use an LLM, authenticate real employees, connect to an accounting provider, or implement human approval and payment release. The current signing keys and local SQLite state are for a local demo, not production key management or durable multi-user operation.

A production system would need, at minimum, authenticated users, durable business data, document ingestion, provider integrations, a real approval workflow, managed keys, operational monitoring, and a security review.
