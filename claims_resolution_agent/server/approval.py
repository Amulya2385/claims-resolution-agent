"""M5 · The approval protocol.

canonicalize → hash → suspend-and-checkpoint → notify → sign →
mint a token binding approval_id AND payload_hash → resume with
RE-verification against the claim's CURRENT state → consume once.

Two verifiers exist on purpose. verify_naive is what gets written
first, and it is broken in exactly the two ways this project's own
instructor notes name. verify_and_consume is the fixed version.
test_approval.py demonstrates the naive one actually failing before
showing the fix hold.
"""
import hashlib
import json
import secrets
import time

_SERVER_SECRET = "dev-hmac-secret-not-for-production"  # see identity.py's
# _signing_key() for why a real deployment reads this from environment,
# not source — kept as a plain constant here only because M5's own
# demonstration is about the protocol shape, not secret management,
# which Project 1's M2 already covers once for this whole document
# family.

_APPROVALS: dict[str, dict] = {}


def payload_hash(claim_id: str, amount: float, currency: str) -> str:
    canon = json.dumps({"claim_id": claim_id, "amount": amount, "currency": currency},
                        sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canon.encode()).hexdigest()


def request_approval(claim_id: str, amount: float, currency: str, required_approvers: int) -> dict:
    """Suspend-and-checkpoint: nothing about the claim can execute
    until this resolves. 'Notify' is simulated — a real deployment
    pages or emails the named approver; this reference build returns
    who would have been notified."""
    approval_id = secrets.token_hex(8)
    record = {
        "approval_id": approval_id, "claim_id": claim_id,
        "payload_hash": payload_hash(claim_id, amount, currency),
        "required_approvers": required_approvers, "signatures": [],
        "created_at": time.time(), "expires_at": time.time() + 1800,
        "status": "pending",
    }
    _APPROVALS[approval_id] = record
    return record


def sign_approval(approval_id: str, approver_id: str) -> str | None:
    """Returns a token only once every required signature is present.
    Four-eyes claims need two DIFFERENT approvers; the same person
    signing twice does not count twice."""
    record = _APPROVALS.get(approval_id)
    if record is None:
        raise KeyError(f"no such approval: {approval_id}")
    if record["status"] != "pending":
        raise ValueError(f"approval {approval_id} is not pending (status={record['status']})")
    if time.time() > record["expires_at"]:
        record["status"] = "expired"
        raise ValueError(f"approval {approval_id} expired")
    if approver_id in [s["approver_id"] for s in record["signatures"]]:
        raise ValueError(f"{approver_id} has already signed this approval — four-eyes needs two DIFFERENT people")
    record["signatures"].append({"approver_id": approver_id, "signed_at": time.time()})
    if len(record["signatures"]) >= record["required_approvers"]:
        record["status"] = "approved"
        return _mint_token(record)
    return None


def decision_seconds(record: dict) -> list[float]:
    """Seconds between suspension and each signature — the raw
    material engagement detection is built from."""
    return [s["signed_at"] - record["created_at"] for s in record["signatures"]]


def flag_if_rubber_stamped(records: list[dict], min_seconds: float = 2.0) -> dict:
    """Pairs the approval rate with a companion engagement measure.
    A batch where every approval is individually valid can still be
    entirely rubber-stamped — this is the check that catches that,
    not the signature check, which cannot."""
    times = [t for r in records for t in decision_seconds(r)]
    if not times:
        return {"n": 0, "median_seconds": None, "flagged": False}
    times.sort()
    median = times[len(times) // 2]
    flagged = median < min_seconds
    return {"n": len(times), "median_seconds": round(median, 3),
             "min_seconds_required": min_seconds, "flagged": flagged}


def _mint_token(record: dict) -> str:
    """Binds approval_id AND payload_hash together — the fix for
    failure pattern one. A token that bound only the payload hash
    would let two claims with identical amounts share one signature."""
    body = f"{record['approval_id']}:{record['payload_hash']}"
    sig = hashlib.sha256((body + _SERVER_SECRET).encode()).hexdigest()
    return f"{body}:{sig}"


def verify_naive(token: str, claim_id: str) -> tuple[bool, str]:
    """FAILURE PATTERN ONE, kept here rather than deleted after being
    found: checks only that the token's payload_hash matches SOME
    approved record for this claim_id — not that the approval_id
    itself is this exact, single-use grant. Two identical-amount
    claims for the same claim_id would both validate against either
    token."""
    try:
        approval_id, bound_hash, sig = token.split(":")
    except ValueError:
        return False, "malformed_token"
    for record in _APPROVALS.values():
        if record["claim_id"] == claim_id and record["payload_hash"] == bound_hash \
                and record["status"] in ("approved", "consumed"):
            return True, "ok (naive: matched by hash alone, any record)"
    return False, "no_matching_hash"


def verify_and_consume(token: str, claim_id: str, current_amount: float, current_currency: str) -> tuple[bool, str]:
    """The correct version. Re-derives the hash from the claim's
    CURRENT state — not the state at suspend time — which is the
    fix for failure pattern two: if the claim's amount changed after
    approval was granted, the recomputed hash will not match the
    token's bound hash, and this fails closed."""
    try:
        approval_id, bound_hash, sig = token.split(":")
    except ValueError:
        return False, "malformed_token"

    expected_sig = hashlib.sha256((f"{approval_id}:{bound_hash}" + _SERVER_SECRET).encode()).hexdigest()
    if sig != expected_sig:
        return False, "invalid_signature"

    record = _APPROVALS.get(approval_id)
    if record is None:
        return False, "unknown_approval_id"
    if record["claim_id"] != claim_id:
        return False, "approval_claim_mismatch"
    if record["status"] == "consumed":
        return False, "approval_already_consumed"
    if record["status"] != "approved" or time.time() > record["expires_at"]:
        return False, "approval_not_valid"

    current_hash = payload_hash(claim_id, current_amount, current_currency)
    if bound_hash != current_hash:
        return False, "payload_changed_since_approval"

    record["status"] = "consumed"
    return True, "ok"
