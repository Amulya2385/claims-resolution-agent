"""Idempotency, demonstrated with an actual process kill — not a
simulated one. Starts _kill_test_worker.py, waits for it to print
confirmation that the ledger write committed, then SIGKILLs it before
it can report success — a real network-timeout-after-commit. A fresh
process then retries with the identical idempotency key, and the
ledger is checked directly: one entry, not two.
"""
import os
import signal
import subprocess
import sys
import time

_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(_HERE, "..", "ledger"))

DB_PATH = "/tmp/cra_kill_test_ledger.db"
CLAIM_ID = "CLM-77005"
IDEMPOTENCY_KEY = "kill-test-key-001"


def run():
    if os.path.exists(DB_PATH):
        os.remove(DB_PATH)

    print("=== starting the worker; it will commit the write, then sleep ===")
    proc = subprocess.Popen(
        [sys.executable, "_kill_test_worker.py", DB_PATH, CLAIM_ID, IDEMPOTENCY_KEY],
        stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
    )

    committed = False
    start = time.time()
    while time.time() - start < 5:
        line = proc.stdout.readline()
        if not line:
            time.sleep(0.02)
            continue
        print(f"  worker: {line.strip()}")
        if line.startswith("WRITE COMMITTED"):
            committed = True
            break

    if not committed:
        print("FAIL — worker never confirmed a commit")
        sys.exit(1)

    print(f"=== killing pid {proc.pid} now, before it could report success ===")
    os.kill(proc.pid, signal.SIGKILL)
    proc.wait()
    print(f"  worker exit code: {proc.returncode} (killed, no clean exit)")

    print()
    print("=== retry: a fresh process, same idempotency key ===")
    retry = subprocess.run(
        [sys.executable, "_kill_test_worker.py", DB_PATH, CLAIM_ID, IDEMPOTENCY_KEY],
        capture_output=True, text=True, timeout=10,
    )
    print(f"  retry stdout: {retry.stdout.strip().splitlines()[0] if retry.stdout else '(none)'}")

    print()
    print("=== checking the ledger directly, not trusting either process's own report ===")
    from ledger import Ledger
    led = Ledger(DB_PATH)
    rows = led.conn.execute(
        "SELECT payload FROM ledger WHERE tenant_id='claims-agent'").fetchall()
    matching = [r for r in rows if IDEMPOTENCY_KEY in r[0]]
    print(f"  total ledger entries for this idempotency key: {len(matching)}")
    if len(matching) != 1:
        print(f"FAIL — expected exactly 1 entry, found {len(matching)}")
        sys.exit(1)
    print("PASS — one payment, despite the kill and the retry")


if __name__ == "__main__":
    run()
