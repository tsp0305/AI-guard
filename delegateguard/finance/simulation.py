"""Deterministic synthetic test dataset runner for the finance demo."""
import json
import tempfile
import time
import uuid
from pathlib import Path

from ..token import attenuate, issue_root
from .workflow import InvoiceWorkflow


DATASET_PATH = Path(__file__).with_name("delegateguard_finance_v2.dstore")


def load_dataset():
    return json.loads(DATASET_PATH.read_text(encoding="utf-8"))


def dataset_summary():
    dataset = load_dataset()
    return {
        "dataset_id": dataset["dataset_id"],
        "format": dataset["format"],
        "title": dataset["title"],
        "purpose": dataset["purpose"],
        "total_cases": len(dataset["cases"]),
        "workflow_cases": sum(c["type"] == "invoice_workflow" for c in dataset["cases"]),
        "permission_cases": sum(c["type"] == "permission_probe" for c in dataset["cases"]),
        "download_path": "/v1/finance/simulation/dataset/download",
        "cases": [
            {key: case[key] for key in ("id", "type", "title", "description")}
            for case in dataset["cases"]
        ],
    }


def _install_case_records(workflow, case):
    records = [case["invoice"], *case.get("extra_invoices", [])]
    workflow.tools.invoices.update({record["id"]: dict(record) for record in records})
    workflow.tools.vendors.update({record["id"]: dict(record) for record in case.get("vendors", [])})
    workflow.tools.purchase_orders.update({record["id"]: dict(record) for record in case.get("purchase_orders", [])})


def _issue_agent_tokens(workflow, invoice_id, invocation_id):
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
        workflow.authority, "finance-orchestrator", list(scopes.values()),
        ttl=180, max_depth=1, invocation_id=invocation_id, constraints=constraints,
    )
    return {
        agent: attenuate(root, workflow.orchestrator, agent, [tool])
        for agent, tool in scopes.items()
    }


def _workflow_case(workflow, case):
    _install_case_records(workflow, case)
    trace = []
    result = workflow.run(case["invoice"]["id"], on_event=trace.append)
    expected = case["expect"]
    denied = [event for event in result["events"] if event.get("decision") == "deny"]
    blocked_tool_ok = not expected.get("blocked_tool") or any(
        event.get("tool") == expected["blocked_tool"] for event in denied
    )
    actual = {
        "verification": result["verification"]["status"],
        "risk": result["risk"]["level"],
        "draft": result["draft"] is not None,
        "blocked_calls": len(denied),
        "duration_ms": result["duration_ms"],
    }
    passed = (
        actual["verification"] == expected["verification"]
        and actual["risk"] == expected["risk"]
        and actual["draft"] is expected["draft"]
        and blocked_tool_ok
    )
    return {
        "id": case["id"], "type": case["type"], "title": case["title"],
        "description": case["description"], "passed": passed,
        "expected": expected, "actual": actual, "trace": trace,
    }


def _permission_case(workflow, case):
    probe = case["probe"]
    invocation_id = uuid.uuid4().hex
    bound_id = probe["invoice_id"]
    tokens = _issue_agent_tokens(workflow, bound_id, invocation_id)
    token_key = probe["agent"]
    target_id = probe.get("target_invoice_id", bound_id)

    trace = [{"type": "step", "agent": "finance-orchestrator", "status": "complete",
              "label": "Issued an invocation-bound token with the agent's limited tool scope"}]

    def call():
        return workflow.call(
            token_key, tokens[token_key], probe["tool"], {"id": target_id},
            invocation_id, on_event=trace.append,
        )

    try:
        first_ok, first_result = call()
        second = call() if probe.get("repeat") else None
    finally:
        workflow.gateway.close_invocation(invocation_id)

    if probe.get("repeat"):
        expected_value = probe["expected"]
        passed = first_ok and second is not None and not second[0] and expected_value == "deny_second_call"
        actual = {"first": "allow" if first_ok else "deny", "second": "allow" if second and second[0] else "deny"}
    else:
        decision = "allow" if first_ok else "deny"
        passed = decision == probe["expected"]
        actual = {"decision": decision, "reason": first_result if not first_ok else "authorized"}
    return {
        "id": case["id"], "type": case["type"], "title": case["title"],
        "description": case["description"], "passed": passed,
        "expected": probe["expected"], "actual": actual, "trace": trace,
    }


def run_simulation():
    """Run the whole synthetic set with isolated state and no model API calls."""
    dataset = load_dataset()
    started = time.perf_counter()
    with tempfile.TemporaryDirectory(prefix="delegateguard-simulation-") as temp_dir:
        root = Path(temp_dir)
        workflow = InvoiceWorkflow(
            state_path=str(root / "state.sqlite3"),
            audit_path=str(root / "audit.jsonl"),
        )
        workflow.advisor.client = None
        workflow.advisor.mode = "simulation"

        clean = next(case["invoice"] for case in dataset["cases"] if case["id"] == "invoice-clean")
        workflow.tools.invoices[clean["id"]] = dict(clean)
        workflow.tools.invoices["SIM-CLEAN-02"] = {
            **clean, "id": "SIM-CLEAN-02", "invoice_number": "SIM-AC-002-BOUNDARY",
        }
        results = []
        for case in dataset["cases"]:
            if case["type"] == "invoice_workflow":
                results.append(_workflow_case(workflow, case))
            else:
                results.append(_permission_case(workflow, case))

    passed_count = sum(result["passed"] for result in results)
    return {
        "dataset_id": dataset["dataset_id"],
        "mode": "deterministic synthetic simulation; Gemini is not called",
        "total": len(results), "passed": passed_count,
        "failed": len(results) - passed_count,
        "duration_ms": round((time.perf_counter() - started) * 1000, 2),
        "results": results,
        "research_note": "These are synthetic implementation checks, not measurements of real-world attack resistance or research efficacy.",
    }
