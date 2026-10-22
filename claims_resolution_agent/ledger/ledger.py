"""M6 · Shared ledger. Append-only, hash-chained — same design as
Project 1's ledger.py, its own copy here since each project must be
independently buildable. Adds one thing Project 1's ledger did not
need: lookup by idempotency key, since payments (unlike Project 1's
reads) must never double-execute on a retry.
"""
import hashlib
import json
import sqlite3
import time


def _canonical(payload: dict) -> str:
    return json.dumps(payload, sort_keys=True, separators=(",", ":"))


class Ledger:
    def __init__(self, db_path: str = ":memory:"):
        self.conn = sqlite3.connect(db_path)
        self.conn.execute("""
            CREATE TABLE IF NOT EXISTS ledger (
                seq INTEGER PRIMARY KEY AUTOINCREMENT,
                tenant_id TEXT NOT NULL,
                payload TEXT NOT NULL,
                prev_hash TEXT NOT NULL,
                entry_hash TEXT NOT NULL,
                written_at TEXT NOT NULL
            )
        """)
        self.conn.commit()

    def _head_hash(self, tenant_id: str) -> str:
        row = self.conn.execute(
            "SELECT entry_hash FROM ledger WHERE tenant_id=? ORDER BY seq DESC LIMIT 1",
            (tenant_id,)).fetchone()
        return row[0] if row else "0" * 64

    def append(self, tenant_id: str, payload: dict) -> dict:
        prev_hash = self._head_hash(tenant_id)
        canon = _canonical(payload)
        entry_hash = hashlib.sha256((prev_hash + canon).encode()).hexdigest()
        written_at = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        self.conn.execute(
            "INSERT INTO ledger (tenant_id, payload, prev_hash, entry_hash, written_at) VALUES (?,?,?,?,?)",
            (tenant_id, canon, prev_hash, entry_hash, written_at))
        self.conn.commit()
        return {"tenant_id": tenant_id, "entry_hash": entry_hash, "written_at": written_at}

    def find_by_idempotency_key(self, key: str) -> dict | None:
        rows = self.conn.execute("SELECT payload, entry_hash FROM ledger").fetchall()
        for payload, entry_hash in rows:
            data = json.loads(payload)
            if data.get("idempotency_key") == key:
                return {"entry_hash": entry_hash, **data}
        return None

    def verify(self, tenant_id: str) -> dict:
        rows = self.conn.execute(
            "SELECT seq, payload, prev_hash, entry_hash FROM ledger WHERE tenant_id=? ORDER BY seq ASC",
            (tenant_id,)).fetchall()
        expected_prev = "0" * 64
        for seq, payload, prev_hash, stored_hash in rows:
            recomputed = hashlib.sha256((expected_prev + payload).encode()).hexdigest()
            if recomputed != stored_hash or prev_hash != expected_prev:
                remaining = len(rows) - rows.index((seq, payload, prev_hash, stored_hash))
                return {"valid": False, "first_bad_seq": seq, "entries_invalidated_from_here": remaining}
            expected_prev = stored_hash
        return {"valid": True, "entries_checked": len(rows)}

    def _corrupt_for_test(self, tenant_id: str, seq: int, new_payload: dict):
        self.conn.execute("UPDATE ledger SET payload=? WHERE tenant_id=? AND seq=?",
                            (_canonical(new_payload), tenant_id, seq))
        self.conn.commit()


_LEDGER = None


def get_ledger() -> Ledger:
    global _LEDGER
    if _LEDGER is None:
        _LEDGER = Ledger()
    return _LEDGER
