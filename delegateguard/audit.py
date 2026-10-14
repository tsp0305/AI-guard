"""Append-only, hash-chained audit records signed by the gateway identity."""
import hashlib
import json
import os
import time
from pathlib import Path
from .identity import Identity, Registry
from .token import canon

class AuditLog:
    """Hash-chained, gateway-signed log. Tampering is detectable."""
    def __init__(self, signer: Identity, path=None):
        self.signer, self.entries, self._prev = signer, [], "0" * 64
        self.path = Path(path or os.environ.get("DELEGATEGUARD_AUDIT", "delegateguard-audit.jsonl"))
        self.path.parent.mkdir(parents=True, exist_ok=True)
        if self.path.exists():
            for line in self.path.read_text(encoding="utf-8").splitlines():
                try: self.entries.append(json.loads(line))
                except json.JSONDecodeError: raise ValueError("audit file is malformed; refusing startup")
            if self.entries: self._prev = self.entries[-1]["hash"]

    def add(self, **fields):
        e = {"seq": len(self.entries), "ts": time.time(), "prev": self._prev, **fields}
        h = hashlib.sha256(canon(e)).hexdigest()
        record = {"entry": e, "hash": h, "sig": self.signer.sign(h.encode())}
        self.entries.append(record)
        with self.path.open("a", encoding="utf-8") as f: f.write(json.dumps(record, sort_keys=True) + "\n")
        self._prev = h
        return e

    def verify(self, registry: Registry) -> bool:
        prev = "0" * 64
        for x in self.entries:
            h = hashlib.sha256(canon(x["entry"])).hexdigest()
            if x["entry"]["prev"] != prev or h != x["hash"]:
                return False
            if not registry.verify(self.signer.name, h.encode(), x["sig"]):
                return False
            prev = h
        return True
