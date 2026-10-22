"""Approval is engaged, not rubber-stamped.

Every individual approval below is validly bound \u2014 correct signer,
correct payload hash, nothing forged. The signature check alone would
pass all of them. flag_if_rubber_stamped is the separate check that
catches the batch where every decision was instant.
"""
import time
import approval as ap


def instant_batch():
    """Ten approvals, signed with no deliberation \u2014 a script clicking
    'approve' as fast as it can."""
    records = []
    for i in range(10):
        rec = ap.request_approval(f"CLM-ENG{i:03d}", 200.00, "USD", required_approvers=1)
        ap.sign_approval(rec["approval_id"], "approver-jane")
        records.append(rec)
    return records


def realistic_batch():
    """Ten approvals with a real, if compressed, decision pause \u2014
    standing in for an approver who actually opened and read each
    one."""
    records = []
    for i in range(10):
        rec = ap.request_approval(f"CLM-ENGR{i:03d}", 200.00, "USD", required_approvers=1)
        time.sleep(0.05)  # standing in for real deliberation, compressed
        # so this test finishes in under a second rather than minutes
        ap.sign_approval(rec["approval_id"], "approver-jane")
        records.append(rec)
    return records


if __name__ == "__main__":
    print("=== ten instantly-signed approvals, every one validly bound ===")
    instant = instant_batch()
    r1 = ap.flag_if_rubber_stamped(instant, min_seconds=0.02)
    print(f"  {r1}")

    print()
    print("=== ten approvals with a real pause before each signature ===")
    realistic = realistic_batch()
    r2 = ap.flag_if_rubber_stamped(realistic, min_seconds=0.02)
    print(f"  {r2}")

    print()
    if r1["flagged"] and not r2["flagged"]:
        print("PASS \u2014 instant batch flagged, deliberated batch was not")
    else:
        print("FAIL")
