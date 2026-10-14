"""HTTP boundary for an already configured DelegateGuard gateway."""
from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse
from pydantic import BaseModel
from typing import Any
import random
import re
import uuid
from pathlib import Path

class ToolRequest(BaseModel):
    body: dict[str, Any]
    sig: str
    token: list[dict[str, Any]]

    class Config:
        extra = "forbid"


def create_app(gateway, demo_system=None):
    app = FastAPI(title="DelegateGuard", version="1.0.0")
    app.state.metrics = {"allowed": 0, "denied": 0, "errors": 0}

    @app.get("/", response_class=HTMLResponse)
    def demo_ui():
        page = Path(__file__).with_name("ui").joinpath("index.html")
        return HTMLResponse(page.read_text(encoding="utf-8"))

    @app.get("/health")
    def health():
        return {"status": "ok"}

    @app.get("/metrics")
    def metrics():
        return dict(app.state.metrics)

    if demo_system is not None:
        from pydantic import Field

        class DemoTicket(BaseModel):
            description: str = Field(min_length=3, max_length=3000)
            user_email: str = Field(min_length=3, max_length=254)

            class Config:
                extra = "forbid"

        @app.post("/v1/demo/run")
        def run_demo(request: DemoTicket):
            if not re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", request.user_email):
                raise HTTPException(status_code=422, detail="Enter a valid email address")
            ticket_id = "UI-" + uuid.uuid4().hex[:8].upper()
            demo_system.tools.tickets[ticket_id] = {"text": request.description, "status": "open"}
            first_attempt = len(demo_system.attempts)
            try:
                invocation_id = demo_system.run_case(
                    {"ticket_id": ticket_id, "user_email": request.user_email},
                    random.Random(0),
                )
            except Exception as exc:
                app.state.metrics["errors"] += 1
                raise HTTPException(status_code=500, detail="Demo run failed") from exc
            attempts = demo_system.attempts[first_attempt:]
            app.state.metrics["allowed"] += sum(1 for a in attempts if a["ok"])
            app.state.metrics["denied"] += sum(1 for a in attempts if not a["ok"])
            return {
                "ticket_id": ticket_id,
                "invocation_id": invocation_id,
                "status": demo_system.tools.tickets[ticket_id]["status"],
                "email_sent": any(m["inv"] == invocation_id for m in demo_system.tools.outbox),
                "attempts": [
                    {"caller": a["agent"], "tool": a["tool"], "decision": a["log"].get("decision"),
                     "reason": a["log"].get("reason"), "args": a["log"].get("args", {})}
                    for a in attempts
                ],
                "summary": {
                    "allowed": sum(1 for a in attempts if a["ok"]),
                    "blocked": sum(1 for a in attempts if not a["ok"]),
                    "harmful_executed": sum(1 for a in attempts if a["harmful"] and a["ok"]),
                },
            }

        @app.get("/v1/demo/audit")
        def demo_audit(limit: int = 30):
            if not 1 <= limit <= 100:
                raise HTTPException(status_code=422, detail="limit must be between 1 and 100")
            entries = getattr(getattr(gateway, "log", None), "entries", [])
            result = []
            for record in reversed(entries[-limit:]):
                event = record.get("entry", {})
                result.append({k: event.get(k) for k in ("seq", "ts", "caller", "tool", "decision", "reason", "invocation_id", "args")})
            return {"events": result}

    @app.post("/v1/tool-calls")
    def tool_call(request: ToolRequest):
        try:
            ok, result = gateway.call(request.dict())
            app.state.metrics["allowed" if ok else "denied"] += 1
            if not ok:
                raise HTTPException(status_code=403, detail=result)
            return {"ok": True, "result": result}
        except HTTPException:
            raise
        except Exception as exc:
            app.state.metrics["errors"] += 1
            raise HTTPException(status_code=400, detail="request could not be processed") from exc

    return app
