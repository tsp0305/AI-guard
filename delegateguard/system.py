"""The helpdesk multi-agent system: Orchestrator -> Retriever / Executor.

Runs in two modes with identical agent logic:
  mode="baseline"      one shared API key given to every agent
  mode="delegateguard" per-agent identity + attenuated token chain + gateway

The "brain" of each agent is pluggable. SimulatedBrain is a deterministic
stand-in for an LLM that follows injected instructions with probability p.
Replace it with a real LLM (see llm_brain.py) for the final paper results.
"""
import json
import random
import re
import time
import uuid
from .identity import Identity, Registry
from .token import issue_root, attenuate, AUTHORITY
from .gateway import (DelegateGuardGateway, BaselineGateway, make_request,
                      SHARED_KEY)
from .tools import Tools, CORP_DOMAIN, is_harmful

INJECT_RE = re.compile(r"\[\[INJECT\]\](.*?)\[\[/INJECT\]\]", re.S)


class SimulatedBrain:
    """Follows an embedded injection with probability p (the agent is 'fooled')."""
    def __init__(self, p=0.8):
        self.p = p

    def extra_calls(self, text, rng):
        m = INJECT_RE.search(text or "")
        if m and rng.random() < self.p:
            return json.loads(m.group(1))
        return []


class HelpdeskSystem:
    def __init__(self, mode="delegateguard", brain=None, max_depth=3):
        assert mode in ("baseline", "delegateguard")
        self.mode, self.max_depth = mode, max_depth
        self.brain = brain or SimulatedBrain()
        self.tools = Tools()
        self.authority = Identity(AUTHORITY)
        self.gw_id = Identity("gateway")
        self.agents = {n: Identity(n) for n in
                       ["orchestrator", "retriever", "executor", "sub1", "sub2", "sub3"]}
        self.registry = Registry()
        for i in [self.authority, self.gw_id, *self.agents.values()]:
            self.registry.register(i)
        self.gw = (DelegateGuardGateway(self.registry, self.tools, self.gw_id)
                   if mode == "delegateguard" else BaselineGateway(self.tools))
        self.tokens = {}
        self.attempts = []   # ground truth: which agent really attempted what

    # ---- delegation -------------------------------------------------
    def start_invocation(self):
        inv = uuid.uuid4().hex
        if self.mode == "delegateguard":
            A = self.agents
            root = issue_root(
                self.authority, "orchestrator",
                ["read_ticket", "search_kb", "update_ticket", "send_email"],
                max_depth=self.max_depth, invocation_id=inv,
                constraints={"send_email": {"to_domain": CORP_DOMAIN}})
            self.tokens = {
                "orchestrator": root,
                "retriever": attenuate(root, A["orchestrator"], "retriever",
                                       ["read_ticket", "search_kb"]),
                "executor": attenuate(root, A["orchestrator"], "executor",
                                      ["update_ticket", "send_email"]),
            }
        return inv

    def end_invocation(self, inv):
        self.gw.close_invocation(inv)

    # ---- tool access ------------------------------------------------
    def call(self, agent, tool, args, inv, token=None):
        """Returns (ok, result, latency_seconds)."""
        t0 = time.perf_counter()
        if self.mode == "baseline":
            ok, res = self.gw.call(SHARED_KEY, tool, args, inv)
        else:
            tok = token if token is not None else self.tokens[agent]
            req = make_request(self.agents[agent], tok, tool, args, inv)
            ok, res = self.gw.call(req)
        dt = time.perf_counter() - t0
        entry = (self.gw.log.entries[-1]["entry"] if self.mode == "delegateguard"
                 else self.gw.entries[-1])
        self.attempts.append({"agent": agent, "tool": tool, "args": args, "inv": inv,
                              "ok": ok, "harmful": is_harmful(tool, args),
                              "log": entry})
        return ok, res, dt

    # ---- one helpdesk case -------------------------------------------
    def run_case(self, case, rng):
        """case: {ticket_id, user_email}. Ticket text may hold an injection."""
        inv = self.start_invocation()
        tid = case["ticket_id"]
        _, text, _ = self.call("retriever", "read_ticket", {"id": tid}, inv)
        self.call("retriever", "search_kb", {"q": "password reset"}, inv)
        for c in self.brain.extra_calls(text, rng):          # Retriever fooled?
            self.call("retriever", c["tool"], c["args"], inv)
        # Executor receives the retrieved text via the orchestrator
        plan = [("update_ticket", {"id": tid, "status": "resolved"}),
                ("send_email", {"to": case["user_email"], "body": "Resolved."})]
        plan += [(c["tool"], c["args"]) for c in self.brain.extra_calls(text, rng)]
        for tool, args in plan:
            self.call("executor", tool, args, inv)
        self.end_invocation(inv)
        return inv
