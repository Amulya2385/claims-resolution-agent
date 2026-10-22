# The Claims Resolution Agent — reference build

Requires Python 3.12+ (built and tested on 3.12.3).

## Setup

    pip install -r requirements.txt --break-system-packages
    export CRA_JWT_SIGNING_KEY="any string you like"

## Run everything (from server/, except the two noted)

    cd server
    python3 test_approval.py
    python3 test_idempotency_kill.py
    python3 test_adversarial.py
    python3 test_engagement.py

    cd ../ledger && python3 test_ledger_tamper.py

    cd ../eval && python3 test_deployment.py

## Layout

- `server/` — tool server, identity, classification, boundaries, the
  approval protocol.
- `policy/` — refund and account-standing policy documents, chunker,
  hybrid retriever.
- `ledger/` — hash-chained audit ledger with idempotency-key lookup.
- `eval/` — golden set, evaluation harness, staged-deployment
  mechanism.

See the implementation document for what each milestone proves and
the exact trace each command above should produce.
