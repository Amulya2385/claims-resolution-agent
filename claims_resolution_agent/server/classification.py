"""M3 · Classification. scope × reversibility × persistence, applied
to a claim — plus overrides for the shapes that factor alone gets
wrong: a damage claim with no photo, or a disputed charge, are not
made safe by being small.
"""

TIER_ROUTINE = "routine"              # auto-execute, no human approval
TIER_SINGLE_APPROVAL = "single"       # one named approver
TIER_FOUR_EYES = "four_eyes"          # two independent named approvers
TIER_DECLINE = "decline"              # must not be resolved as an ordinary refund


def classify(claim: dict, refund_history_count: int, profile: str = "A") -> dict:
    """Returns {tier, reasons, policy_clause}. policy_clause is the
    SPECIFIC clause that justified this decision, set at the rule that
    actually fired — not a single per-tier citation. TIER_DECLINE
    alone has two different possible causes and two different clauses;
    collapsing them to one would misattribute half of them."""
    reasons = []

    if claim.get("chargeback_in_progress"):
        return {"tier": TIER_DECLINE,
                 "reasons": ["a chargeback or bank dispute is already in progress for this order"],
                 "policy_clause": "customer-account-standing#Section 3 — Disputed Charges"}

    if claim.get("reason") == "damaged" and not claim.get("photo_on_file"):
        return {"tier": TIER_DECLINE,
                 "reasons": ["a damage claim requires a photograph on file before any refund"],
                 "policy_clause": "refund-authorization#Clause 8 — Damage Claims"}

    amount = claim["amount"]
    if amount <= 100.00:
        tier = TIER_ROUTINE
        reasons.append(f"amount {amount:.2f} is at or below the routine threshold" if profile == "A"
                         else f"{amount:.2f} falls within the auto-approve band")
    elif amount <= 1000.00:
        tier = TIER_SINGLE_APPROVAL
        reasons.append(f"amount {amount:.2f} is above routine, at or below single-approval" if profile == "A"
                         else f"{amount:.2f} clears routine but stays under the four-eyes line")
    else:
        tier = TIER_FOUR_EYES
        reasons.append(f"amount {amount:.2f} exceeds the single-approval threshold" if profile == "A"
                         else f"{amount:.2f} is large enough to require two independent approvers")

    if tier == TIER_ROUTINE and refund_history_count >= 3:
        tier = TIER_SINGLE_APPROVAL
        reasons.append(
            f"customer has {refund_history_count} approved refunds in the trailing 90 days "
            f"(threshold 3 or more) — an additional one is not routine regardless of amount"
        )

    return {"tier": tier, "reasons": reasons,
             "policy_clause": "refund-authorization#Clause 6 — Authorization Thresholds"}
