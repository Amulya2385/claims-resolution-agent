"""Cross-platform crash-safety idempotency test.

Starts the kill-test worker, waits for confirmation that the refund write
committed, terminates the worker before it can report success, retries the
same operation with the identical idempotency key, and verifies directly
from the ledger that exactly one entry exists.

This test validates the real failure mode:

    commit succeeds -> response is lost -> process dies -> client retries

The test harness is platform-independent and does not modify the core
refund/idempotency implementation.
"""

import os
import subprocess
import sys
import tempfile
import time
from pathlib import Path


_HERE = Path(__file__).resolve().parent
_WORKER = _HERE / "_kill_test_worker.py"

DB_PATH = Path(tempfile.gettempdir()) / "cra_kill_test_ledger.db"

CLAIM_ID = "CLM-77005"
IDEMPOTENCY_KEY = "kill-test-key-001"


def run():
    if DB_PATH.exists():
        DB_PATH.unlink()

    if not _WORKER.exists():
        print(f"FAIL — worker not found: {_WORKER}")
        sys.exit(1)

    print("=== starting the worker; it will commit the write, then sleep ===")

    proc = subprocess.Popen(
        [
            sys.executable,
            str(_WORKER),
            str(DB_PATH),
            CLAIM_ID,
            IDEMPOTENCY_KEY,
        ],
        cwd=str(_HERE),
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        bufsize=1,
    )

    committed = False
    start = time.time()

    while time.time() - start < 10:
        line = proc.stdout.readline()

        if line:
            print(f"  worker: {line.strip()}")

            if line.startswith("WRITE COMMITTED"):
                committed = True
                break
        elif proc.poll() is not None:
            break
        else:
            time.sleep(0.02)

    if not committed:
        stderr_output = ""

        if proc.stderr:
            stderr_output = proc.stderr.read().strip()

        if proc.poll() is None:
            proc.kill()
            proc.wait()

        print("FAIL — worker never confirmed a commit")

        if stderr_output:
            print("=== worker stderr ===")
            print(stderr_output)

        sys.exit(1)

    print(f"=== killing pid {proc.pid} now, before it could report success ===")

    proc.kill()
    proc.wait()

    print(f"  worker exit code: {proc.returncode} (killed, no clean exit)")

    print()
    print("=== retry: a fresh process, same idempotency key ===")

    retry = subprocess.run(
        [
            sys.executable,
            str(_WORKER),
            str(DB_PATH),
            CLAIM_ID,
            IDEMPOTENCY_KEY,
        ],
        cwd=str(_HERE),
        capture_output=True,
        text=True,
        timeout=10,
    )

    retry_lines = retry.stdout.strip().splitlines()

    if retry_lines:
        print(f"  retry stdout: {retry_lines[0]}")
    else:
        print("  retry stdout: (none)")

    if retry.returncode != 0:
        print("  retry stderr:")
        print(retry.stderr.strip())
        sys.exit(1)

    print()
    print("=== checking the ledger directly, not trusting either process's own report ===")

    sys.path.insert(0, str(_HERE.parent / "ledger"))

    from ledger import Ledger

    led = Ledger(str(DB_PATH))

    rows = led.conn.execute(
        "SELECT payload FROM ledger WHERE tenant_id='claims-agent'"
    ).fetchall()

    matching = [row for row in rows if IDEMPOTENCY_KEY in row[0]]

    print(
        f"  total ledger entries for this idempotency key: {len(matching)}"
    )

    if len(matching) != 1:
        print(
            f"FAIL — expected exactly 1 entry, found {len(matching)}"
        )
        sys.exit(1)

    print("PASS — one payment, despite the kill and the retry")

    led.conn.close()

    if DB_PATH.exists():
        DB_PATH.unlink()


if __name__ == "__main__":
    run()