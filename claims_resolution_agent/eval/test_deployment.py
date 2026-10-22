import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "server"))
from harness import full_gate
from golden_claims import make_golden_set, make_system_hook
from deployment import Deployment

golden = make_golden_set()
dep = Deployment()
print(f"starting stage: {dep.stage}")

print()
print("=== promotion attempt with NO evidence linked ===")
r = dep.attempt_promotion(None)
print(f"  {r}")

print()
print("=== a real evaluation run, used as the linked evidence ===")
evidence = full_gate(make_system_hook("A"), golden, accuracy_floor=0.9)
print(f"  ran the golden set: accuracy={evidence['layer2']['accuracy']}  passed={evidence['passed']}")

print()
print("=== promotion attempt WITH that evidence ===")
r = dep.attempt_promotion(evidence)
print(f"  {r}")
print(f"  now at stage: {dep.stage}")

print()
print("=== a second real promotion, same way ===")
evidence2 = full_gate(make_system_hook("B"), golden, accuracy_floor=0.9)
r2 = dep.attempt_promotion(evidence2)
print(f"  {r2}")
print(f"  now at stage: {dep.stage}")

print()
print("=== a SIMULATED failing evaluation run — demotes automatically ===")
failing_evidence = {"passed": False, "accuracy_floor": 0.9,
                      "layer2": {"accuracy": 0.6, "total": 5, "passed": 3}}
r3 = dep.demote_on_failure(failing_evidence)
print(f"  {r3}")
print(f"  now at stage: {dep.stage}")
print(f"  approved_by for that demotion: {dep.history[-1]['approved_by']}")
