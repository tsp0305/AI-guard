"""Narrow finance tools exposed to the invoice agents through the gateway."""
from copy import deepcopy
from .data import SAMPLE_INVOICES, SAMPLE_PURCHASE_ORDERS, SAMPLE_VENDORS

class FinanceTools:
    SCHEMAS = {
        "read_invoice": {"id"},
        "verify_invoice": {"id"},
        "assess_invoice_risk": {"id"},
        "create_payment_draft": {"id"},
    }

    def __init__(self, advisor):
        self.advisor = advisor
        self.invoices = deepcopy(SAMPLE_INVOICES)
        self.vendors = deepcopy(SAMPLE_VENDORS)
        self.purchase_orders = deepcopy(SAMPLE_PURCHASE_ORDERS)
        self.verifications = {}
        self.verification_results = {}
        self.risk_assessments = {}
        self.drafts = {}

    def validate(self, tool, args):
        if tool not in self.SCHEMAS:
            raise ValueError("unknown finance tool")
        if not isinstance(args, dict) or set(args) != self.SCHEMAS[tool]:
            raise ValueError("invalid finance tool arguments")
        if not isinstance(args["id"], str) or args["id"] not in self.invoices:
            raise ValueError("invoice is not in the approved sample set")
        return True

    def call(self, tool, args, invocation_id):
        self.validate(tool, args)
        invoice_id = args["id"]
        invoice = self.invoices[invoice_id]
        if tool == "read_invoice":
            return {**invoice, "notes": invoice["notes"]}
        if tool == "verify_invoice":
            flags = []
            vendor = self.vendors.get(invoice["vendor_id"])
            purchase_order = self.purchase_orders.get(invoice["purchase_order_id"])
            if not vendor or not vendor["approved"]:
                flags.append("Vendor is not on the approved vendor list")
            if not purchase_order:
                flags.append("Purchase order was not found")
            else:
                if purchase_order["vendor_id"] != invoice["vendor_id"]:
                    flags.append("Invoice vendor does not match the purchase order")
                if purchase_order["currency"] != invoice["currency"]:
                    flags.append("Invoice currency does not match the purchase order")
                if invoice["amount"] > purchase_order["amount"]:
                    flags.append("Invoice amount exceeds the purchase order")
            duplicate = any(
                other_id != invoice_id
                and other["vendor_id"] == invoice["vendor_id"]
                and other["invoice_number"].casefold() == invoice["invoice_number"].casefold()
                for other_id, other in self.invoices.items()
            )
            if duplicate:
                flags.append("Duplicate vendor invoice number")
            passed = not flags
            self.verifications[(invocation_id, invoice_id)] = passed
            result = {"status": "verified" if passed else "needs_review", "flags": flags}
            self.verification_results[(invocation_id, invoice_id)] = result
            return result
        if tool == "assess_invoice_risk":
            verification = self.verification_results.get((invocation_id, invoice_id), {"status": "needs_review", "flags": ["Verification did not run"]})
            result = self.advisor.assess_risk(invoice, verification)
            self.risk_assessments[(invocation_id, invoice_id)] = result
            return result
        if tool == "create_payment_draft":
            if not self.verifications.get((invocation_id, invoice_id), False):
                raise ValueError("invoice has not passed verification in this invocation")
            risk = self.risk_assessments.get((invocation_id, invoice_id))
            if not risk or risk.get("level") != "low":
                raise ValueError("invoice risk has not passed in this invocation")
            draft_id = f"PAY-{len(self.drafts) + 1:04d}"
            draft = {
                "id": draft_id, "invoice_id": invoice_id,
                "vendor_id": invoice["vendor_id"], "vendor_name": self.vendors[invoice["vendor_id"]]["name"],
                "amount": invoice["amount"], "currency": invoice["currency"],
                "status": "awaiting_human_approval", "invocation_id": invocation_id,
            }
            self.drafts[draft_id] = draft
            return draft
        raise ValueError("unknown finance tool")
