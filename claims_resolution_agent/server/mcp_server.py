"""M1 · The tool server. tools/list and tools/call, hand-rolled —
same two verbs as Project 1's server, because the protocol does not
change with the domain. Handlers for this domain's four tools,
registered directly (Project 1's M9 finding: nothing gets served only
through an opt-in extra_handlers dict a caller might forget)."""
import os
import sys
import jsonschema

_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(_HERE, "..", "policy"))
sys.path.insert(0, os.path.join(_HERE, "..", "ledger"))

from registry import list_tools, get_schema
from fixtures import CLAIMS, CUSTOMER_REFUND_HISTORY


def _handle_lookup_claim(args, context):
    cid = args["claim_id"]
    if cid not in CLAIMS:
        return {"error": "no_such_claim", "claim_id": cid}
    return {"claim_id": cid, **CLAIMS[cid]}


def _handle_check_customer_history(args, context):
    custid = args["customer_id"]
    return {"customer_id": custid,
            "approved_refunds_trailing_90d": CUSTOMER_REFUND_HISTORY.get(custid, 0)}


def _handle_search_policy_corpus(args, context):
    from policy_index import get_index
    idx = get_index()
    results = idx.search(args["query"], k=args.get("k", 4))
    return {"results": [{"locator": r["locator"], "text": r["text"][:220]} for r in results]}


def _handle_execute_refund(args, context):
    """The only write. Classification, boundaries and approval are
    enforced HERE, inside the one path every caller — model-issued or
    otherwise — must go through, not in a wrapper a caller could
    bypass by calling dispatch() directly. That placement is the
    entire content of the 'No standing authority' gate."""
    from classification import classify, TIER_ROUTINE, TIER_DECLINE
    from boundaries import boundary_for
    from approval import verify_and_consume
    from ledger import get_ledger
    from fixtures import CLAIMS, CUSTOMER_REFUND_HISTORY

    claim_id = args["claim_id"]
    key = args["idempotency_key"]
    led = get_ledger()

    existing = led.find_by_idempotency_key(key)
    if existing:
        return {"status": "already_executed", "idempotency_key": key,
                 "entry_hash": existing["entry_hash"]}

    claim = CLAIMS.get(claim_id)
    if claim is None:
        return {"status": "error", "reason": "no_such_claim", "claim_id": claim_id}

    hist = CUSTOMER_REFUND_HISTORY.get(claim["customer_id"], 0)
    profile = context.get("profile", "A")
    result = classify(claim, hist, profile=profile)
    tier = result["tier"]
    boundary = boundary_for(tier)

    if tier == TIER_DECLINE:
        return {"status": "declined", "claim_id": claim_id, "reasons": result["reasons"],
                 "policy_clause": result["policy_clause"]}

    if tier != TIER_ROUTINE:
        token = args.get("approval_token")
        if not token:
            return {"status": "suspended", "claim_id": claim_id, "tier": tier,
                     "required_approvers": boundary["required_approvers"],
                     "reasons": result["reasons"], "policy_clause": result["policy_clause"]}
        ok, reason = verify_and_consume(token, claim_id, claim["amount"], claim["currency"])
        if not ok:
            return {"status": "approval_rejected", "claim_id": claim_id, "reason": reason}

    entry = led.append("claims-agent", {
        "event": "refund_executed", "claim_id": claim_id,
        "amount": claim["amount"], "currency": claim["currency"],
        "tier": tier, "idempotency_key": key,
    })
    return {"status": "executed", "claim_id": claim_id, "amount": claim["amount"],
             "tier": tier, "entry_hash": entry["entry_hash"]}


_HANDLERS = {
    "lookup_claim": _handle_lookup_claim,
    "check_customer_history": _handle_check_customer_history,
    "search_policy_corpus": _handle_search_policy_corpus,
    "execute_refund": _handle_execute_refund,
}


def dispatch(request: dict, context: dict | None = None) -> dict:
    rid = request.get("id")
    method = request.get("method")

    if method == "tools/list":
        return {"jsonrpc": "2.0", "id": rid, "result": {"tools": list_tools()}}

    if method == "tools/call":
        params = request.get("params", {})
        name = params.get("name")
        args = params.get("arguments", {})

        schema = get_schema(name)
        if schema is None:
            return {"jsonrpc": "2.0", "id": rid,
                     "error": {"code": -32601, "message": f"unknown tool: {name}"}}
        try:
            jsonschema.validate(instance=args, schema=schema)
        except jsonschema.ValidationError as e:
            return {"jsonrpc": "2.0", "id": rid,
                     "error": {"code": -32602, "message": f"schema violation: {e.message}"}}

        handler = _HANDLERS.get(name)
        if handler is None:
            return {"jsonrpc": "2.0", "id": rid,
                     "error": {"code": -32601, "message": f"no handler registered: {name}"}}
        return {"jsonrpc": "2.0", "id": rid, "result": handler(args, context or {})}

    return {"jsonrpc": "2.0", "id": rid,
             "error": {"code": -32601, "message": f"unknown method: {method}"}}
