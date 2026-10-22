import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "ledger"))
from ledger import Ledger

ledger = Ledger()
tenant = "claims-agent"

for i in range(4):
    r = ledger.append(tenant, {"event": "refund_executed", "claim_id": f"CLM-{90100+i}",
                                 "amount": 50.00 + i, "idempotency_key": f"tamper-test-{i}"})
    print(f"  appended seq {i}: entry_hash={r['entry_hash'][:16]}...")

print()
print("=== verify: untouched chain ===")
print(" ", ledger.verify(tenant))

print()
print("=== ATTACK: directly edit entry seq=2's payload in storage ===")
ledger._corrupt_for_test(tenant, seq=3, new_payload={"event": "refund_executed",
                          "claim_id": "CLM-90102", "amount": "TAMPERED", "idempotency_key": "tamper-test-2"})
print(" ", ledger.verify(tenant))
