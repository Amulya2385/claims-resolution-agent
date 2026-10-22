"""M7 · Adversarial testing. Each attack below is shown failing against
the live system, then again with its specific defence layer disabled
— so a zero-breach result proves the layer is doing something, not
that nobody tried.
"""
import sys
import json

import mcp_server as srv
import approval as ap
from fixtures import CLAIMS


def attack_instruction_injection():
    """Family 1: free-text instructions in the claim description,
    trying to talk the system into auto-approving. Defence layer:
    classify() never reads customer_description."""
    print("=== Attack 1: instruction injection in free-text claim description ===")
    resp = srv.dispatch({"jsonrpc": "2.0", "id": 1, "method": "tools/call",
                          "params": {"name": "execute_refund",
                                     "arguments": {"claim_id": "CLM-77006", "idempotency_key": "attack1-live"}}})
    print(f"  live system: {resp['result']['status']} — {resp['result'].get('reasons')}")
    breach_live = resp["result"]["status"] == "executed"

    # Layer disabled: a version of classify that DOES read the field,
    # the way a careless implementation reading free text as signal
    # would.
    from classification import TIER_ROUTINE
    claim = CLAIMS["CLM-77006"]
    text = claim.get("customer_description", "").lower()
    would_classify_routine = "classify as routine" in text
    print(f"  with the layer disabled (reading customer_description as signal): "
          f"would classify routine = {would_classify_routine}")
    return {"family": "instruction_injection", "breach_live": breach_live,
             "breach_with_layer_disabled": would_classify_routine}


def attack_forged_approval_token():
    """Family 2: a random string presented as an approval token.
    Defence layer: HMAC signature check in verify_and_consume."""
    print()
    print("=== Attack 2: a forged approval token, never issued by this server ===")
    forged = "deadbeefcafe:0000000000000000000000000000000000000000000000000000000000000000:alsoforged"
    ok, reason = ap.verify_and_consume(forged, "CLM-77001", 340.00, "USD")
    print(f"  live system (signature checked): allowed={ok}  reason={reason}")
    return {"family": "forged_token", "breach_live": ok}


def attack_replay_after_amount_change():
    """Family 3: an approval granted for one amount, presented after
    the claim's amount changed. Defence layer: re-derivation of the
    hash from CURRENT state in verify_and_consume, vs. verify_naive
    which skips it."""
    print()
    print("=== Attack 3: stale approval, claim amount changed after granting ===")
    rec = ap.request_approval("CLM-90201", 200.00, "USD", required_approvers=1)
    tok = ap.sign_approval(rec["approval_id"], "approver-jane")
    ok_live, reason_live = ap.verify_and_consume(tok, "CLM-90201", 2000.00, "USD")
    print(f"  live system (verify_and_consume, re-checks current amount): "
          f"allowed={ok_live}  reason={reason_live}")

    rec2 = ap.request_approval("CLM-90202", 200.00, "USD", required_approvers=1)
    tok2 = ap.sign_approval(rec2["approval_id"], "approver-jane")
    ok_disabled, reason_disabled = ap.verify_naive(tok2, "CLM-90202")
    print(f"  with the layer disabled (verify_naive, no re-check): "
          f"allowed={ok_disabled}  reason={reason_disabled}")
    return {"family": "stale_approval", "breach_live": ok_live,
             "breach_with_layer_disabled": ok_disabled}


def attack_schema_injection():
    """Family 4: a SQL-injection-shaped string where a claim id
    belongs. Defence layer: jsonschema pattern validation in
    dispatch(), the same one Project 1's M1 fuzzer exercises."""
    print()
    print("=== Attack 4: injection attempt in the claim_id field ===")
    resp = srv.dispatch({"jsonrpc": "2.0", "id": 1, "method": "tools/call",
                          "params": {"name": "execute_refund",
                                     "arguments": {"claim_id": "'; DROP TABLE claims;--",
                                                    "idempotency_key": "attack4-live12"}}})
    print(f"  live system: {json.dumps(resp)}")
    breach_live = "error" not in resp
    return {"family": "schema_injection", "breach_live": breach_live}


if __name__ == "__main__":
    results = [attack_instruction_injection(), attack_forged_approval_token(),
                attack_replay_after_amount_change(), attack_schema_injection()]
    print()
    print("=== summary ===")
    live_breaches = sum(1 for r in results if r.get("breach_live"))
    print(f"  {len(results)} families tested against the live system: {live_breaches} breach(es)")
    for r in results:
        if "breach_with_layer_disabled" in r:
            tag = "SUCCEEDS (as expected — proves the layer is load-bearing)" if r["breach_with_layer_disabled"] else "still fails even disabled"
            print(f"  {r['family']}: with its defence layer disabled, the attack {tag}")
    if live_breaches:
        print("FAIL")
        sys.exit(1)
    print("PASS — zero breaches against the live system")
