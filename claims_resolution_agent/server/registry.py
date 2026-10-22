"""M1 · The registry. Single source of every tool's schema, versioned."""

REGISTRY_VERSION = "2026.09.1"

_TOOLS = {
    "lookup_claim": {
        "version": 1,
        "description": "Claim details: order, customer, amount, reason, flags. Read-only.",
        "input_schema": {
            "type": "object",
            "properties": {"claim_id": {"type": "string", "pattern": "^CLM-[0-9]{5}$"}},
            "required": ["claim_id"], "additionalProperties": False,
        },
    },
    "check_customer_history": {
        "version": 1,
        "description": "Approved-refund count for a customer in the trailing 90 days. Read-only.",
        "input_schema": {
            "type": "object",
            "properties": {"customer_id": {"type": "string", "pattern": "^CUST-[0-9]{4}$"}},
            "required": ["customer_id"], "additionalProperties": False,
        },
    },
    "search_policy_corpus": {
        "version": 1,
        "description": "Hybrid search over refund and account-standing policy. Read-only.",
        "input_schema": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "minLength": 3, "maxLength": 300},
                "k": {"type": "integer", "minimum": 1, "maximum": 8},
            },
            "required": ["query"], "additionalProperties": False,
        },
    },
    "execute_refund": {
        "version": 1,
        "description": (
            "Executes a refund for a claim. Amount and currency are never "
            "supplied by the caller — they are derived server-side from "
            "the claim record, so a caller cannot request a refund for more "
            "than the claim actually states. Above the auto-approve "
            "threshold, approval_token is required and is checked against "
            "a hash of the exact claim being executed."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "claim_id": {"type": "string", "pattern": "^CLM-[0-9]{5}$"},
                "idempotency_key": {"type": "string", "minLength": 8, "maxLength": 64},
                "approval_token": {"type": "string", "minLength": 8},
            },
            "required": ["claim_id", "idempotency_key"],
            "additionalProperties": False,
        },
    },
}


def list_tools() -> list[dict]:
    return [{"name": n, "version": s["version"], "description": s["description"],
              "inputSchema": s["input_schema"]} for n, s in sorted(_TOOLS.items())]


def get_schema(name: str) -> dict | None:
    spec = _TOOLS.get(name)
    return spec["input_schema"] if spec else None
