"""Run as a subprocess. Performs exactly one execute_refund call
against a FILE-based ledger (so state survives the process dying),
sleeping briefly between the ledger commit and printing confirmation
— the parent kills this process in that window, simulating a network
timeout that occurs after the write actually succeeded.
"""
import sys
import time

import mcp_server as srv
from ledger import Ledger
import ledger as ledger_module

DB_PATH = sys.argv[1]
CLAIM_ID = sys.argv[2]
IDEMPOTENCY_KEY = sys.argv[3]

# Point this process's ledger singleton at the shared file.
ledger_module._LEDGER = Ledger(DB_PATH)

req = {"jsonrpc": "2.0", "id": 1, "method": "tools/call",
       "params": {"name": "execute_refund",
                  "arguments": {"claim_id": CLAIM_ID, "idempotency_key": IDEMPOTENCY_KEY}}}
resp = srv.dispatch(req)
print(f"WRITE COMMITTED: {resp}", flush=True)

# The window the parent kills us in — the write above already
# committed to the SQLite file; this sleep represents the response
# travelling back to a caller who will never receive it.
time.sleep(5)
print("RESPONSE SENT", flush=True)  # never reached in the kill scenario
