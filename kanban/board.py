"""
Lightweight kanban board backed by SQLite.

Columns: TODO -> SCRAPING -> SCRIPTING -> VIDEO -> REVIEW -> DONE

Each pipeline run (per product/niche) creates one card. Agents move the
card forward as they complete their stage. This gives us a real, inspectable
kanban trail (for the eval criteria + the "video output of the hermes kanban"
deliverable) without needing a paid Trello/Jira integration.
"""

import sqlite3
import json
import time
from pathlib import Path
from dataclasses import dataclass, field
from typing import Optional

DB_PATH = Path(__file__).parent / "kanban.db"

COLUMNS = ["TODO", "SCRAPING", "SCRIPTING", "VIDEO", "REVIEW", "DONE"]


@dataclass
class Card:
    id: int
    title: str
    column: str
    payload: dict = field(default_factory=dict)
    created_at: float = 0.0
    updated_at: float = 0.0
    log: list = field(default_factory=list)


class KanbanBoard:
    def __init__(self, db_path: Path = DB_PATH):
        self.db_path = db_path
        self._init_db()

    def _init_db(self):
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS cards (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    title TEXT NOT NULL,
                    column_name TEXT NOT NULL,
                    payload TEXT NOT NULL DEFAULT '{}',
                    log TEXT NOT NULL DEFAULT '[]',
                    created_at REAL NOT NULL,
                    updated_at REAL NOT NULL
                )
                """
            )
            conn.commit()

    def create_card(self, title: str, payload: Optional[dict] = None) -> int:
        now = time.time()
        with sqlite3.connect(self.db_path) as conn:
            cur = conn.execute(
                "INSERT INTO cards (title, column_name, payload, log, created_at, updated_at) "
                "VALUES (?, ?, ?, ?, ?, ?)",
                (title, "TODO", json.dumps(payload or {}), json.dumps([
                    {"ts": now, "event": "card_created"}
                ]), now, now),
            )
            conn.commit()
            return cur.lastrowid

    def move_card(self, card_id: int, to_column: str, note: str = ""):
        if to_column not in COLUMNS:
            raise ValueError(f"Unknown column: {to_column}. Must be one of {COLUMNS}")
        card = self.get_card(card_id)
        log = card.log
        log.append({"ts": time.time(), "event": f"moved -> {to_column}", "note": note})
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                "UPDATE cards SET column_name = ?, log = ?, updated_at = ? WHERE id = ?",
                (to_column, json.dumps(log), time.time(), card_id),
            )
            conn.commit()

    def update_payload(self, card_id: int, updates: dict):
        card = self.get_card(card_id)
        card.payload.update(updates)
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                "UPDATE cards SET payload = ?, updated_at = ? WHERE id = ?",
                (json.dumps(card.payload), time.time(), card_id),
            )
            conn.commit()

    def get_card(self, card_id: int) -> Card:
        with sqlite3.connect(self.db_path) as conn:
            row = conn.execute(
                "SELECT id, title, column_name, payload, log, created_at, updated_at "
                "FROM cards WHERE id = ?",
                (card_id,),
            ).fetchone()
        if not row:
            raise ValueError(f"No card with id {card_id}")
        return Card(
            id=row[0], title=row[1], column=row[2],
            payload=json.loads(row[3]), log=json.loads(row[4]),
            created_at=row[5], updated_at=row[6],
        )

    def board_snapshot(self) -> dict:
        """Returns {column: [cards]} for rendering/printing the board."""
        snapshot = {c: [] for c in COLUMNS}
        with sqlite3.connect(self.db_path) as conn:
            rows = conn.execute(
                "SELECT id, title, column_name FROM cards ORDER BY updated_at DESC"
            ).fetchall()
        for cid, title, col in rows:
            snapshot[col].append({"id": cid, "title": title})
        return snapshot

    def render_ascii(self) -> str:
        snap = self.board_snapshot()
        lines = []
        header = " | ".join(f"{c:^12}" for c in COLUMNS)
        lines.append(header)
        lines.append("-" * len(header))
        max_rows = max((len(v) for v in snap.values()), default=0)
        for i in range(max_rows):
            row = []
            for c in COLUMNS:
                cell = snap[c][i]["title"][:12] if i < len(snap[c]) else ""
                row.append(f"{cell:^12}")
            lines.append(" | ".join(row))
        return "\n".join(lines)


if __name__ == "__main__":
    board = KanbanBoard()
    cid = board.create_card("trading-signals-ad-run-1", {"niche": "trading signals"})
    board.move_card(cid, "SCRAPING", note="Ads Manager started")
    print(board.render_ascii())
