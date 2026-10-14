"""Attenuating delegation tokens (a simple JWT/Biscuit-style signed chain).

A token is a list of blocks. Block 0 is issued by the trusted authority.
Each next block is signed by the previous block's audience and may only
NARROW: tools subset, expiry not later, max_depth not larger.
Each signature also covers the previous signature, so blocks cannot be
reordered, dropped or spliced between chains.
"""
import json
import copy
import time
import uuid
from .identity import Identity, Registry

AUTHORITY = "user-authority"


def canon(d: dict) -> bytes:
    return json.dumps(d, sort_keys=True, separators=(",", ":")).encode()


def _sign_block(signer: Identity, data: dict, prev_sig: str) -> dict:
    return {"data": data, "sig": signer.sign(canon(data) + prev_sig.encode())}


def issue_root(authority: Identity, audience: str, tools, ttl=60.0,
               max_depth=3, invocation_id=None, constraints=None) -> list:
    data = {
        "issuer": authority.name, "audience": audience, "tools": sorted(tools),
        "expires": time.time() + ttl, "max_depth": max_depth,
        "invocation_id": invocation_id or uuid.uuid4().hex,
        "constraints": constraints or {},
    }
    return [_sign_block(authority, data, "")]


def attenuate(token: list, holder: Identity, audience: str, tools=None,
              expires=None, constraints=None, enforce=True) -> list:
    """Holder delegates to `audience` with equal or narrower scope.
    enforce=False is used only by the attack simulations."""
    last = token[-1]["data"]
    new_tools = sorted(tools if tools is not None else last["tools"])
    new_exp = expires if expires is not None else last["expires"]
    if enforce:
        if not set(new_tools) <= set(last["tools"]):
            raise ValueError("attenuation may not add tools")
        if new_exp > last["expires"]:
            raise ValueError("attenuation may not extend expiry")
    new_constraints = copy.deepcopy(constraints if constraints is not None else last["constraints"])
    if enforce and not _constraints_narrow(new_constraints, last["constraints"]):
        raise ValueError("constraints may not widen parent scope")
    data = {
        "issuer": holder.name, "audience": audience, "tools": new_tools,
        "expires": new_exp, "max_depth": last["max_depth"],
        "invocation_id": last["invocation_id"],
        "constraints": new_constraints,
    }
    return copy.deepcopy(token) + [_sign_block(holder, data, token[-1]["sig"])]


def _constraints_narrow(child, parent):
    """Every parent restriction must be preserved or made stricter."""
    if not isinstance(child, dict) or not isinstance(parent, dict):
        return False
    for tool, parent_rules in parent.items():
        if tool not in child or not isinstance(parent_rules, dict) or not isinstance(child[tool], dict):
            return False
        rules = child[tool]
        for key, pv in parent_rules.items():
            if key not in rules: return False
            value = rules[key]
            if key == "to_domain":
                if not isinstance(value, str) or value.lower() != pv.lower(): return False
            elif key == "allowed_ids":
                if (not isinstance(pv, list) or not isinstance(value, list) or
                    not all(isinstance(x, (str, int)) for x in pv + value) or not set(value) <= set(pv)): return False
            elif key == "max_calls":
                if not isinstance(pv, int) or not isinstance(value, int) or value < 0 or value > pv: return False
            elif value != pv:
                return False
        if set(rules) - set(parent_rules): return False
    return set(child) <= set(parent)


def verify_chain(token: list, registry: Registry, now=None):
    """Returns (ok, reason, info)."""
    now = now if now is not None else time.time()
    if not isinstance(token, list) or not token:
        return False, "empty or malformed token", None
    prev_sig, prev = "", None
    required = {"issuer", "audience", "tools", "expires", "max_depth", "invocation_id", "constraints"}
    for i, blk in enumerate(token):
        if not isinstance(blk, dict) or set(blk) != {"data", "sig"} or not isinstance(blk["data"], dict):
            return False, f"malformed block {i}", None
        d = blk["data"]
        if not required <= set(d) or not isinstance(d["issuer"], str) or not isinstance(d["audience"], str):
            return False, f"malformed data at block {i}", None
        if not isinstance(d["tools"], list) or not all(isinstance(x, str) for x in d["tools"]):
            return False, f"malformed tools at block {i}", None
        if not isinstance(d["expires"], (int, float)) or not isinstance(d["max_depth"], int) or d["max_depth"] < 0:
            return False, f"malformed limits at block {i}", None
        if not isinstance(d["constraints"], dict) or not isinstance(d["invocation_id"], str):
            return False, f"malformed constraints at block {i}", None
        if not isinstance(blk["sig"], str):
            return False, f"malformed signature at block {i}", None
        if not registry.verify(d["issuer"], canon(d) + prev_sig.encode(), blk["sig"]):
            return False, f"bad signature at block {i}", None
        if i == 0:
            if d["issuer"] != AUTHORITY:
                return False, "root not issued by trusted authority", None
        else:
            if d["issuer"] != prev["audience"]:
                return False, f"broken chain at block {i}", None
            if d["invocation_id"] != prev["invocation_id"]:
                return False, "invocation id changed", None
            if not set(d["tools"]) <= set(prev["tools"]):
                return False, f"privilege escalation at block {i}", None
            if d["expires"] > prev["expires"] or d["max_depth"] > prev["max_depth"] or not _constraints_narrow(d["constraints"], prev["constraints"]):
                return False, f"scope widened at block {i}", None
        if d["expires"] < now:
            return False, f"expired at block {i}", None
        prev_sig, prev = blk["sig"], d
    hops = len(token) - 1
    if hops > token[0]["data"]["max_depth"]:
        return False, "delegation depth exceeded", None
    last = token[-1]["data"]
    return True, "ok", {
        "audience": last["audience"], "tools": set(last["tools"]),
        "invocation_id": last["invocation_id"],
        "constraints": [b["data"]["constraints"] for b in token],
        "issuers": [b["data"]["issuer"] for b in token] + [last["audience"]],
    }


def size_bytes(token: list) -> int:
    return len(json.dumps(token).encode())
