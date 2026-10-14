import os, sys, time, unittest
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from delegateguard.identity import Identity, Registry
from delegateguard.token import issue_root, attenuate, verify_chain, AUTHORITY
from delegateguard.system import HelpdeskSystem


def setup():
    ids = {n: Identity(n) for n in [AUTHORITY, "a", "b", "c"]}
    reg = Registry()
    for i in ids.values():
        reg.register(i)
    return ids, reg


class TokenTests(unittest.TestCase):
    def test_valid_chain(self):
        ids, reg = setup()
        t = issue_root(ids[AUTHORITY], "a", ["x", "y"])
        t = attenuate(t, ids["a"], "b", ["x"])
        ok, why, info = verify_chain(t, reg)
        self.assertTrue(ok, why)
        self.assertEqual(info["tools"], {"x"})

    def test_cannot_widen(self):
        ids, reg = setup()
        t = issue_root(ids[AUTHORITY], "a", ["x"])
        with self.assertRaises(ValueError):
            attenuate(t, ids["a"], "b", ["x", "z"])
        bad = attenuate(t, ids["a"], "b", ["x", "z"], enforce=False)
        self.assertFalse(verify_chain(bad, reg)[0])

    def test_tamper_detected(self):
        ids, reg = setup()
        t = attenuate(issue_root(ids[AUTHORITY], "a", ["x"]), ids["a"], "b", ["x"])
        t[-1]["data"]["tools"] = ["x", "z"]
        self.assertFalse(verify_chain(t, reg)[0])

    def test_expiry_and_depth(self):
        ids, reg = setup()
        t = issue_root(ids[AUTHORITY], "a", ["x"], ttl=-1)
        self.assertFalse(verify_chain(t, reg)[0])
        t = issue_root(ids[AUTHORITY], "a", ["x"], max_depth=1)
        t = attenuate(t, ids["a"], "b"); t = attenuate(t, ids["b"], "c")
        self.assertEqual(verify_chain(t, reg)[1], "delegation depth exceeded")


class SystemTests(unittest.TestCase):
    def test_log_tamper_detected(self):
        s = HelpdeskSystem("delegateguard")
        s.tools.tickets["T1"] = {"text": "hi", "status": "open"}
        import random
        s.run_case({"ticket_id": "T1", "user_email": "u@corp.example"}, random.Random(1))
        self.assertTrue(s.gw.log.verify(s.registry))
        s.gw.log.entries[1]["entry"]["decision"] = "allow"
        s.gw.log.entries[1]["entry"]["tool"] = "tampered"
        self.assertFalse(s.gw.log.verify(s.registry))


if __name__ == "__main__":
    unittest.main()
