import time
import approval as ap


def demo_pattern_one_replay():
    """Failure pattern one, sharpest form: a token that has already
    been used to execute a payment still validates under the naive
    verifier, because it checks only 'is there an approved record
    with this hash' — not 'has this specific grant already been
    spent.' The same signature authorizes the same payment twice."""
    print("=== Pattern one: hash-only binding allows a token to be reused ===")
    rec = ap.request_approval("CLM-90001", 340.00, "USD", required_approvers=1)
    tok = ap.sign_approval(rec["approval_id"], "approver-jane")
    print(f"  approved for CLM-90001 at $340.00, one token issued")

    ok1, reason1 = ap.verify_naive(tok, "CLM-90001")
    print(f"  first use of the token:  allowed={ok1}  reason={reason1}")
    ok2, reason2 = ap.verify_naive(tok, "CLM-90001")
    print(f"  SAME token, used again:  allowed={ok2}  reason={reason2}")
    print(f"  (naive_verify never marks a grant spent — one signature, refunded twice)")

    ok_fixed1, reason_fixed1 = ap.verify_and_consume(tok, "CLM-90001", 340.00, "USD")
    print(f"  verify_and_consume, first use:  allowed={ok_fixed1}  reason={reason_fixed1}")
    ok_fixed2, reason_fixed2 = ap.verify_and_consume(tok, "CLM-90001", 340.00, "USD")
    print(f"  verify_and_consume, SAME token again: allowed={ok_fixed2}  reason={reason_fixed2}")


def demo_pattern_two_stale_approval():
    """Failure pattern two: an approval granted for one amount is
    presented after the claim's amount changed — e.g. a correction
    was applied between suspension and resume. The naive verifier,
    which does not re-derive the hash from current state, accepts a
    token whose bound amount no longer matches reality."""
    print()
    print("=== Pattern two: no re-verification at resume ===")
    rec = ap.request_approval("CLM-90002", 340.00, "USD", required_approvers=1)
    tok = ap.sign_approval(rec["approval_id"], "approver-jane")
    print(f"  approved for CLM-90002 at $340.00")

    # The claim's amount is corrected AFTER approval, before execution
    # — a real scenario: a partial refund was recalculated.
    new_amount = 3400.00
    print(f"  claim amount corrected to ${new_amount:.2f} before execution")

    ok_naive, reason_naive = ap.verify_naive(tok, "CLM-90002")
    print(f"  verify_naive (does not re-check amount): allowed={ok_naive}  reason={reason_naive}")

    ok_fixed, reason_fixed = ap.verify_and_consume(tok, "CLM-90002", new_amount, "USD")
    print(f"  verify_and_consume (re-derives hash from CURRENT amount): allowed={ok_fixed}  reason={reason_fixed}")


def demo_fix_holds_for_the_correct_case():
    print()
    print("=== The fix, exercised on the path it is meant to allow ===")
    rec = ap.request_approval("CLM-90003", 500.00, "USD", required_approvers=1)
    tok = ap.sign_approval(rec["approval_id"], "approver-jane")
    ok, reason = ap.verify_and_consume(tok, "CLM-90003", 500.00, "USD")
    print(f"  correct claim_id, unchanged amount: allowed={ok}  reason={reason}")

    ok_replay, reason_replay = ap.verify_and_consume(tok, "CLM-90003", 500.00, "USD")
    print(f"  SAME token, presented again (replay): allowed={ok_replay}  reason={reason_replay}")


def demo_four_eyes_needs_two_different_people():
    print()
    print("=== Four-eyes: two different approvers required ===")
    rec = ap.request_approval("CLM-90004", 1450.00, "USD", required_approvers=2)
    tok_after_first = ap.sign_approval(rec["approval_id"], "approver-jane")
    print(f"  after one signature (jane): token issued={tok_after_first is not None}")
    try:
        ap.sign_approval(rec["approval_id"], "approver-jane")
        print("  jane signed twice: UNEXPECTEDLY ALLOWED")
    except ValueError as e:
        print(f"  jane signing twice: correctly rejected — {e}")
    tok_after_second = ap.sign_approval(rec["approval_id"], "approver-marcus")
    print(f"  after a second, different signature (marcus): token issued={tok_after_second is not None}")


if __name__ == "__main__":
    demo_pattern_one_replay()
    demo_pattern_two_stale_approval()
    demo_fix_holds_for_the_correct_case()
    demo_four_eyes_needs_two_different_people()
