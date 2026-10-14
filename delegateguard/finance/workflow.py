"""LangGraph orchestration for guarded, multi-agent invoice processing."""
import time
import uuid
from typing import Any, Callable, TypedDict

from langgraph.graph import END, START, StateGraph

from ..gateway import DelegateGuardGateway, make_request
from ..identity import Identity, Registry
from ..token import AUTHORITY, attenuate, issue_root
from .agents import InvoiceReaderAgent, InvoiceRiskAgent, InvoiceVerifierAgent, PaymentDrafterAgent
from .llm import GeminiAdvisor
from .tools import FinanceTools


class FinanceState(TypedDict, total=False):
    invoice_id: str
    invocation_id: str
    tokens: dict[str, list[dict[str, Any]]]
    on_event: Callable[[dict], None] | None
    invoice: dict[str, Any]
    verification: dict[str, Any]
    risk: dict[str, Any]
    draft: dict[str, Any] | None


class InvoiceWorkflow:
    def __init__(self, state_path=None, audit_path=None):
        self.advisor = GeminiAdvisor()
        self.tools = FinanceTools(self.advisor)
        self.authority = Identity(AUTHORITY)
        self.orchestrator = Identity("finance-orchestrator")
        self.agent_names = ("invoice-reader", "invoice-verifier", "invoice-risk-analyst", "payment-drafter")
        self.agents = {name: Identity(name) for name in self.agent_names}
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
        self.risk_analyst = InvoiceRiskAgent()
        self.drafter = PaymentDrafterAgent()
        self.runs = {}
        self.graph = self._build_graph()

    def _build_graph(self):
        graph = StateGraph(FinanceState)
        graph.add_node("invoice_reader", self._read_invoice)
        graph.add_node("invoice_verifier", self._verify_invoice)
        graph.add_node("risk_analyst", self._assess_risk)
        graph.add_node("payment_drafter", self._create_draft)
        graph.add_node("review_required", self._require_review)
        graph.add_edge(START, "invoice_reader")
        graph.add_edge("invoice_reader", "invoice_verifier")
        graph.add_edge("invoice_verifier", "risk_analyst")
        graph.add_conditional_edges(
            "risk_analyst", self._next_after_risk,
            {"draft": "payment_drafter", "review": "review_required"},
        )
        graph.add_edge("payment_drafter", END)
        graph.add_edge("review_required", END)
        return graph.compile()

    @staticmethod
    def _emit(state, event):
        callback = state.get("on_event")
        if callback:
            callback(event)

    def _read_invoice(self, state):
        self._emit(state, {"type": "step", "agent": "invoice-reader", "status": "running", "label": "Reading the invoice and analyzing its notes"})
        invoice = self.reader.run(self, state["tokens"]["invoice-reader"], state["invoice_id"], state["invocation_id"], state.get("on_event"))
        self._emit(state, {"type": "step", "agent": "invoice-reader", "status": "complete", "label": "Invoice read; invoice text treated as untrusted"})
        return {"invoice": invoice}

    def _verify_invoice(self, state):
        self._emit(state, {"type": "step", "agent": "invoice-verifier", "status": "running", "label": "Checking vendor, purchase order, amount, and duplicates"})
        result = self.verifier.run(self, state["tokens"]["invoice-verifier"], state["invoice_id"], state["invocation_id"], state.get("on_event"))
        self._emit(state, {"type": "step", "agent": "invoice-verifier", "status": "complete", "label": "Verification " + result["status"].replace("_", " ")})
        return {"verification": result}

    def _assess_risk(self, state):
        self._emit(state, {"type": "step", "agent": "invoice-risk-analyst", "status": "running", "label": "Assessing invoice notes with Gemini and local safety rules"})
        result = self.risk_analyst.run(self, state["tokens"]["invoice-risk-analyst"], state["invoice_id"], state["invocation_id"], state.get("on_event"))
        self._emit(state, {"type": "step", "agent": "invoice-risk-analyst", "status": "complete", "label": "Risk level: " + result["level"]})
        return {"risk": result}

    @staticmethod
    def _next_after_risk(state):
        verification = state.get("verification", {})
        risk = state.get("risk", {})
        return "draft" if verification.get("status") == "verified" and risk.get("level") == "low" else "review"

    def _create_draft(self, state):
        self._emit(state, {"type": "step", "agent": "payment-drafter", "status": "running", "label": "Preparing a draft from verified invoice data"})
        draft = self.drafter.run(self, state["tokens"]["payment-drafter"], state["invoice_id"], state["invocation_id"], state.get("on_event"))
        self._emit(state, {"type": "step", "agent": "payment-drafter", "status": "complete", "label": "Draft created; no payment released"})
        return {"draft": draft}

    def _require_review(self, state):
        verification = state.get("verification", {})
        risk = state.get("risk", {})
        if verification.get("status") != "verified":
            label = "Skipped because deterministic invoice checks did not pass"
        else:
            label = "Skipped because risk assessment requires human review"
        self._emit(state, {"type": "step", "agent": "payment-drafter", "status": "skipped", "label": label})
        return {"draft": None}

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
        scopes = {
            "invoice-reader": "read_invoice",
            "invoice-verifier": "verify_invoice",
            "invoice-risk-analyst": "assess_invoice_risk",
            "payment-drafter": "create_payment_draft",
        }
        constraints = {
            tool: {"allowed_ids": [invoice_id], "max_calls": 1}
            for tool in scopes.values()
        }
        root = issue_root(
            self.authority, "finance-orchestrator", list(scopes.values()),
            ttl=180, max_depth=1, invocation_id=invocation_id, constraints=constraints,
        )
        tokens = {
            agent: attenuate(root, self.orchestrator, agent, [tool])
            for agent, tool in scopes.items()
        }
        started = time.time()
        try:
            state = self.graph.invoke({
                "invoice_id": invoice_id,
                "invocation_id": invocation_id,
                "tokens": tokens,
                "on_event": on_event,
            })
        finally:
            self.gateway.close_invocation(invocation_id)
        records = [
            dict(record["entry"]) for record in self.gateway.log.entries
            if record.get("entry", {}).get("invocation_id") == invocation_id
        ]
        result = {
            "invoice": state.get("invoice"),
            "verification": state.get("verification", {"status": "needs_review", "flags": []}),
            "risk": state.get("risk", {"level": "high", "reasons": ["Risk assessment unavailable"]}),
            "draft": state.get("draft"),
            "invocation_id": invocation_id,
            "events": records,
            "duration_ms": round((time.time() - started) * 1000, 2),
        }
        self.runs[invocation_id] = result
        return result
