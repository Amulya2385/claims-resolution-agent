"""M8 · Evaluation harness. Same three-layer design as Project 1's
harness.py — structural, semantic, adversarial — built fresh here
since Project 2 must be independently buildable, not dependent on
Project 1's copy.
"""


class GoldenCase:
    def __init__(self, cid, claim_id, check, description):
        self.cid = cid
        self.claim_id = claim_id
        self.check = check              # callable(response) -> (bool, str)
        self.description = description


def layer2_semantic(system_hook, golden_set) -> dict:
    results = []
    for gc in golden_set:
        resp = system_hook(gc.claim_id)
        ok, reason = gc.check(resp)
        results.append({"cid": gc.cid, "passed": ok, "reason": reason})
    passed = sum(1 for r in results if r["passed"])
    return {"total": len(golden_set), "passed": passed,
             "accuracy": round(passed / len(golden_set), 3) if golden_set else None,
             "results": results}


def full_gate(system_hook, golden_set, accuracy_floor=0.9) -> dict:
    l2 = layer2_semantic(system_hook, golden_set)
    passed = l2["accuracy"] is not None and l2["accuracy"] >= accuracy_floor
    return {"passed": passed, "layer2": l2, "accuracy_floor": accuracy_floor}
