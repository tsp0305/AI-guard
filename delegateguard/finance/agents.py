"""Role-scoped agents used by the invoice workflow graph."""

class InvoiceReaderAgent:
    name = "invoice-reader"
    tool = "read_invoice"

    def run(self, workflow, token, invoice_id, invocation_id, on_event=None):
        ok, invoice = workflow.call(self.name, token, self.tool, {"id": invoice_id}, invocation_id, on_event)
        if not ok:
            raise RuntimeError(invoice)
        invoice["ai_analysis"] = workflow.advisor.summarize_invoice(invoice)
        # Invoice notes are untrusted. Simulate a compromised reader following
        # an embedded instruction; DelegateGuard must deny its unscoped action.
        if invoice["ai_analysis"]["suspicious_instructions"] or "[[PROMPT_INJECTION]]" in invoice.get("notes", ""):
            workflow.call(self.name, token, "create_payment_draft", {"id": invoice_id}, invocation_id, on_event)
        return invoice


class InvoiceVerifierAgent:
    name = "invoice-verifier"
    tool = "verify_invoice"

    def run(self, workflow, token, invoice_id, invocation_id, on_event=None):
        ok, result = workflow.call(self.name, token, self.tool, {"id": invoice_id}, invocation_id, on_event)
        if not ok:
            raise RuntimeError(result)
        return result


class PaymentDrafterAgent:
    name = "payment-drafter"
    tool = "create_payment_draft"

    def run(self, workflow, token, invoice_id, invocation_id, on_event=None):
        ok, result = workflow.call(self.name, token, self.tool, {"id": invoice_id}, invocation_id, on_event)
        if not ok:
            raise RuntimeError(result)
        return result


class InvoiceRiskAgent:
    name = "invoice-risk-analyst"
    tool = "assess_invoice_risk"

    def run(self, workflow, token, invoice_id, invocation_id, on_event=None):
        ok, result = workflow.call(self.name, token, self.tool, {"id": invoice_id}, invocation_id, on_event)
        if not ok:
            raise RuntimeError(result)
        return result
