"""M8 · The golden set. 8 claims, each checked against a real property
of the system's own decision — not a transcript a human approved once.
"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "server"))
from harness import GoldenCase
import mcp_server as srv


def _decide(claim_id: str, idem_suffix: str, profile: str = "A") -> dict:
    resp = srv.dispatch({"jsonrpc": "2.0", "id": 1, "method": "tools/call",
                          "params": {"name": "execute_refund",
                                     "arguments": {"claim_id": claim_id,
                                                    "idempotency_key": f"golden-{idem_suffix}-{profile}"}}},
                          context={"profile": profile})
    return resp.get("result", {})


def check_routine_executes(resp):
    return (resp.get("status") == "executed", f"expected executed, got {resp.get('status')}")


def check_suspends_for_approval(resp):
    return (resp.get("status") == "suspended", f"expected suspended, got {resp.get('status')}")


def check_declines_chargeback(resp):
    ok = resp.get("status") == "declined" and "chargeback" in " ".join(resp.get("reasons", [])).lower()
    return (ok, f"expected declined citing chargeback, got {resp}")


def check_declines_damage_no_photo(resp):
    ok = resp.get("status") == "declined" and "photograph" in " ".join(resp.get("reasons", [])).lower()
    return (ok, f"expected declined citing missing photo, got {resp}")


def check_injection_ignored(resp):
    """CLM-77006 is the adversarial claim — its own text asks to be
    classified routine. The golden answer is the same as a claim with
    the same real properties and no injected text: declined, missing
    photo."""
    return check_declines_damage_no_photo(resp)


def make_golden_set():
    """check takes the RESPONSE the harness already fetched via
    system_hook — it does not re-decide anything itself."""
    return [
        GoldenCase("g1", "CLM-77005", check_routine_executes,
                    "small, clean claim executes without approval"),
        GoldenCase("g2", "CLM-77001", check_suspends_for_approval,
                    "mid-size claim suspends pending single approval"),
        GoldenCase("g3", "CLM-77003", check_suspends_for_approval,
                    "large claim suspends pending four-eyes"),
        GoldenCase("g4", "CLM-77004", check_declines_chargeback,
                    "chargeback in progress declines regardless of amount"),
        GoldenCase("g5", "CLM-77006", check_injection_ignored,
                    "injected instructions in claim text change nothing"),
    ]


def make_system_hook(profile="A"):
    """Returns a callable(claim_id) -> response, with BOTH claim_id and
    a profile tag threaded into the idempotency key. Without claim_id
    in the key, every case in one run would share one key, and the
    ledger's own idempotency check would make every case after the
    first return already_executed regardless of what it actually was."""
    def hook(claim_id):
        return _decide(claim_id, f"{claim_id}-{profile}", profile)
    return hook
