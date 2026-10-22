"""M4 · Boundaries. Approver counts and thresholds by tier — the
POLICY CLAUSE that authorises a specific decision is not here. It
comes from classification.classify(), which knows which rule actually
fired; a decline can happen for two different reasons with two
different clauses, and a single per-tier citation here would
misattribute one of them. This file answers 'how many approvers,'
not 'why.'
"""
from classification import TIER_ROUTINE, TIER_SINGLE_APPROVAL, TIER_FOUR_EYES, TIER_DECLINE

_BOUNDARIES = {
    TIER_ROUTINE: {"required_approvers": 0, "max_amount": 100.00},
    TIER_SINGLE_APPROVAL: {"required_approvers": 1, "max_amount": 1000.00},
    TIER_FOUR_EYES: {"required_approvers": 2, "max_amount": None},
    TIER_DECLINE: {"required_approvers": None, "max_amount": None},
}


def boundary_for(tier: str) -> dict:
    if tier not in _BOUNDARIES:
        raise KeyError(f"no boundary declared for tier: {tier}")
    return {"tier": tier, **_BOUNDARIES[tier]}
