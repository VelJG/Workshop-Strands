"""One local SQLite record per proposal. Approved records are the tickets."""
from contextlib import closing
from pathlib import Path
import sqlite3
from time import time
from uuid import uuid4

from .policy import APPROVAL_TTL_SECONDS, MAX_RECORDS, next_status


class CapacityReached(Exception):
    pass


class Store:
    def __init__(self, path: Path):
        self.path = path

    def connect(self):
        connection = sqlite3.connect(self.path, timeout=2)
        connection.row_factory = sqlite3.Row
        return connection

    def initialize(self):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with closing(self.connect()) as db, db:
            db.execute("""CREATE TABLE IF NOT EXISTS actions (
                id TEXT PRIMARY KEY, content TEXT NOT NULL,
                status TEXT NOT NULL CHECK (status IN ('pending', 'approved', 'denied')),
                expires_at REAL NOT NULL,
                title TEXT, category TEXT, priority TEXT, created_at REAL
            )""")
            columns = {row[1] for row in db.execute("PRAGMA table_info(actions)")}
            for name, column_type in (("title", "TEXT"), ("category", "TEXT"),
                                      ("priority", "TEXT"), ("created_at", "REAL")):
                if name not in columns:
                    db.execute(f"ALTER TABLE actions ADD COLUMN {name} {column_type}")

    @staticmethod
    def _ticket(row):
        return {"ticket_id": row["id"], "ticket_ref": f"IT-{row['rowid']:05d}",
                "title": row["title"] or row["content"][:80],
                "content": row["content"], "category": row["category"] or "other",
                "priority": row["priority"] or "normal", "status": "Pending",
                "created_at": row["created_at"] or row["expires_at"] - APPROVAL_TTL_SECONDS}

    def propose(self, content: str, *, title=None, category="other", priority="normal") -> str:
        approval_id = str(uuid4())
        with closing(self.connect()) as db, db:
            db.execute("BEGIN IMMEDIATE")
            db.execute("DELETE FROM actions WHERE status = 'pending' AND expires_at <= ?", (time(),))
            if db.execute("SELECT count(*) FROM actions").fetchone()[0] >= MAX_RECORDS:
                raise CapacityReached
            db.execute("""INSERT INTO actions
                (id, content, status, expires_at, title, category, priority)
                VALUES (?, ?, 'pending', ?, ?, ?, ?)""",
                       (approval_id, content, time() + APPROVAL_TTL_SECONDS,
                        title or content[:80], category, priority))
        return approval_id

    def decide(self, approval_id: str, approve: bool):
        with closing(self.connect()) as db, db:
            db.execute("BEGIN IMMEDIATE")
            row = db.execute("SELECT rowid, * FROM actions WHERE id = ?", (approval_id,)).fetchone()
            if row is None:
                return None, False
            result = next_status(row["status"], approve=approve, expires_at=row["expires_at"], now=time())
            newly_approved = row["status"] != result and result == "approved"
            if row["status"] != result:
                db.execute("UPDATE actions SET status = ?, created_at = ? WHERE id = ?",
                           (result, time() if result == "approved" else None, approval_id))
            ticket_row = (db.execute("SELECT rowid, * FROM actions WHERE id = ?", (approval_id,)).fetchone()
                          if result == "approved" else None)
        if result == "approved":
            return {**self._ticket(ticket_row), "status": "approved"}, newly_approved
        return {"status": "denied"}, False

    def ticket(self, ticket_id: str):
        with closing(self.connect()) as db:
            row = db.execute("SELECT rowid, * FROM actions WHERE id = ? AND status = 'approved'",
                             (ticket_id,)).fetchone()
        return self._ticket(row) if row else None

    def list_tickets(self, limit: int = 20):
        with closing(self.connect()) as db:
            rows = db.execute("SELECT rowid, * FROM actions WHERE status = 'approved' ORDER BY rowid DESC LIMIT ?",
                              (min(max(limit, 1), 20),)).fetchall()
        return [self._ticket(row) for row in rows]
