"""Gateways. DelegateGuardGateway verifies the whole token chain on EVERY
tool call. BaselineGateway accepts one shared API key (the practice the
lecture criticises). Both write an audit log."""
import time
from .identity import Identity, Registry
from .token import verify_chain, canon
from .audit import AuditLog
from .state import InvocationStore
from .policy import validate_argument_constraints

SHARED_KEY = "SHARED-API-KEY-123"


def make_request(agent: Identity, token, tool, args, invocation_id):
    body = {"caller": agent.name, "tool": tool, "args": args,
            "invocation_id": invocation_id, "ts": time.time()}
    return {"body": body, "sig": agent.sign(canon(body)), "token": token}


class DelegateGuardGateway:
    def __init__(self, registry, tools, signer: Identity, state_path=None, audit_path=None):
        self.registry, self.tools = registry, tools
        self.log = AuditLog(signer, audit_path)
        self.state = InvocationStore(state_path)

    def close_invocation(self, inv):
        if not isinstance(inv, str) or not inv: raise ValueError("invalid invocation id")
        self.state.close(inv)

    def _decide(self, req):
        if not isinstance(req, dict) or set(req) != {"body", "sig", "token"} or not isinstance(req["body"], dict):
            return False, "malformed request", None
        b = req["body"]
        if set(b) != {"caller", "tool", "args", "invocation_id", "ts"}:
            return False, "malformed request body", None
        if not isinstance(b["caller"], str) or not isinstance(b["tool"], str) or not isinstance(b["args"], dict) or not isinstance(b["invocation_id"], str) or not isinstance(req["sig"], str) or not isinstance(req["token"], list):
            return False, "invalid request field types", None
        if not isinstance(b["ts"], (int, float)) or abs(time.time() - b["ts"]) > 30:
            return False, "stale request timestamp", None
        if not self.registry.verify(b["caller"], canon(b), req["sig"]):
            return False, "bad request signature", None
        ok, why, info = verify_chain(req["token"], self.registry)
        if not ok:
            return False, why, None
        if info["audience"] != b["caller"]:
            return False, "token not issued to caller (stolen/misused)", info
        if info["invocation_id"] != b["invocation_id"]:
            return False, "token bound to a different invocation", info
        if self.state.is_closed(b["invocation_id"]):
            return False, "invocation closed (replay)", info
        if b["tool"] not in info["tools"]:
            return False, "tool outside delegated scope", info
        try:
            self.tools.validate(b["tool"], b["args"])
        except (ValueError, KeyError, TypeError) as exc:
            return False, f"invalid tool arguments: {exc}", info
        try:
            validate_argument_constraints(b["tool"], b["args"], info["constraints"])
        except ValueError as exc:
            return False, str(exc), info
        return True, "ok", info

    def call(self, req):
        b = req.get("body", {}) if isinstance(req, dict) else {}
        ok, why, info = self._decide(req)
        if ok and not self.state.reserve_call(info, b["invocation_id"], b["tool"]):
            ok, why = False, "tool call limit exceeded"
        raw_args = b.get("args", {})
        if not isinstance(raw_args, dict): raw_args = {}
        safe_args = {str(k): ("[REDACTED]" if any(x in str(k).lower() for x in ("password", "secret", "token", "body", "content")) else v) for k, v in raw_args.items()}
        self.log.add(caller=b.get("caller", "unknown"), tool=b.get("tool", "unknown"), args=safe_args,
                     invocation_id=b.get("invocation_id"),
                     decision="allow" if ok else "deny", reason=why,
                     chain=info["issuers"] if info else None)
        if not ok:
            return False, why
        return True, self.tools.call(b["tool"], b["args"], b["invocation_id"])


class BaselineGateway:
    def __init__(self, tools):
        self.tools, self.entries = tools, []

    def close_invocation(self, inv):
        pass

    def call(self, key, tool, args, invocation_id):
        ok = key == SHARED_KEY
        # Only the key is known; the log cannot say WHICH agent used it.
        self.entries.append({"key_id": key[:6], "tool": tool, "args": args,
                             "invocation_id": invocation_id,
                             "decision": "allow" if ok else "deny"})
        if not ok:
            return False, "bad key"
        return True, self.tools.call(tool, args, invocation_id)
