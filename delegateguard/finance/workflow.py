"""Orchestrate the invoice agents and issue narrow per-invocation capabilities."""
import time
import uuid
from ..gateway import DelegateGuardGateway, make_request
from ..identity import Identity, Registry
from ..token import AUTHORITY, attenuate, issue_root
from .agents import InvoiceReaderAgent, InvoiceVerifierAgent, PaymentDrafterAgent
from .tools import FinanceTools

class InvoiceWorkflow:
    def __init__(self, state_path=None, audit_path=None):
        self.tools = FinanceTools()
        self.authority = Identity(AUTHORITY)
        self.orchestrator = Identity("finance-orchestrator")
        self.agents = {
            "invoice-reader": Identity("invoice-reader"),
            "invoice-verifier": Identity("invoice-verifier"),
            "payment-drafter": Identity("payment-drafter"),
        }
        self.gateway_identity = Identity("finance-gateway")
        self.registry = Registry()
        for identity in (self.authority, self.orchestrator, self.gateway_identity, *self.agents.values()):
            self.registry.register(identity)
        self.gateway = DelegateGuardGateway(
            self.registry, self.tools, self.gateway_identity,
            state_path=state_path or "delegateguard-finance-state.sqlite3",
            audit_path=audit_path or "delegateguard-finance-audit.jsonl",
        )
        self.reader = InvoiceReaderAgent()
        self.verifier = InvoiceVerifierAgent()
        self.drafter = PaymentDrafterAgent()
        self.runs = {}

    def list_invoices(self):
        return [
            {"id": inv["id"], "vendor_id": inv["vendor_id"],
             "invoice_number": inv["invoice_number"], "amount": inv["amount"],
             "currency": inv["currency"], "due_date": inv["due_date"]}
            for inv in self.tools.invoices.values()
        ]

    def call(self, agent_name, token, tool, args, invocation_id, on_event=None):
        request = make_request(self.agents[agent_name], token, tool, args, invocation_id)
        ok, result = self.gateway.call(request)
        if on_event:
            on_event({
                "type": "tool", "agent": agent_name, "tool": tool,
                "decision": "allow" if ok else "deny",
                "reason": result if not ok else "Authorized by DelegateGuard",
                "args": args,
            })
        return ok, result

    def run(self, invoice_id, on_event=None):
        if invoice_id not in self.tools.invoices:
            raise ValueError("Select an invoice from the sample queue")
        invocation_id = uuid.uuid4().hex
        invoice_constraint = {
            "read_invoice": {"allowed_ids": [invoice_id], "max_calls": 1},
            "verify_invoice": {"allowed_ids": [invoice_id], "max_calls": 1},
            "create_payment_draft": {"allowed_ids": [invoice_id], "max_calls": 1},
        }
        root = issue_root(
            self.authority, "finance-orchestrator",
            ["read_invoice", "verify_invoice", "create_payment_draft"],
            ttl=120, max_depth=1, invocation_id=invocation_id,
            constraints=invoice_constraint,
        )
        tokens = {
            "invoice-reader": attenuate(root, self.orchestrator, "invoice-reader", ["read_invoice"]),
            "invoice-verifier": attenuate(root, self.orchestrator, "invoice-verifier", ["verify_invoice"]),
            "payment-drafter": attenuate(root, self.orchestrator, "payment-drafter", ["create_payment_draft"]),
        }
        first_event = len(self.gateway.log.entries)
        started = time.time()
        if on_event:
            on_event({"type": "step", "agent": "invoice-reader", "status": "running", "label": "Reading the selected invoice"})
        invoice = self.reader.run(self, tokens["invoice-reader"], invoice_id, invocation_id, on_event)
        if on_event:
            on_event({"type": "step", "agent": "invoice-reader", "status": "complete", "label": "Invoice read; invoice text treated as untrusted"})
            on_event({"type": "step", "agent": "invoice-verifier", "status": "running", "label": "Checking vendor, purchase order, amount, and duplicates"})
        verification = self.verifier.run(self, tokens["invoice-verifier"], invoice_id, invocation_id, on_event)
        if on_event:
            on_event({"type": "step", "agent": "invoice-verifier", "status": "complete", "label": "Verification " + verification["status"].replace("_", " ")})
        draft = None
        if verification["status"] == "verified":
            if on_event:
                on_event({"type": "step", "agent": "payment-drafter", "status": "running", "label": "Preparing a draft from verified invoice data"})
            draft = self.drafter.run(self, tokens["payment-drafter"], invoice_id, invocation_id, on_event)
            if on_event:
                on_event({"type": "step", "agent": "payment-drafter", "status": "complete", "label": "Draft created; no payment released"})
        elif on_event:
            on_event({"type": "step", "agent": "payment-drafter", "status": "skipped", "label": "Skipped because verification did not pass"})
        self.gateway.close_invocation(invocation_id)
        records = self.gateway.log.entries[first_event:]
        result = {
            "invoice": invoice,
            "verification": verification,
            "draft": draft,
            "invocation_id": invocation_id,
            "events": [dict(record["entry"]) for record in records],
            "duration_ms": round((time.time() - started) * 1000, 2),
        }
        self.runs[invocation_id] = result
        return result
