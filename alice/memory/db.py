import sqlite3
from datetime import datetime
from pathlib import Path

DB_PATH = Path(__file__).parent / "alice.db"

CREATE_PROFILES = """
CREATE TABLE IF NOT EXISTS profiles (
    id       INTEGER PRIMARY KEY AUTOINCREMENT,
    name     TEXT NOT NULL UNIQUE,
    features TEXT DEFAULT '',
    created  TEXT NOT NULL,
    updated  TEXT NOT NULL
)
"""

CREATE_CONVERSATIONS = """
CREATE TABLE IF NOT EXISTS conversations (
    id        INTEGER PRIMARY KEY AUTOINCREMENT,
    profile_id INTEGER REFERENCES profiles(id),
    role      TEXT NOT NULL,
    content   TEXT NOT NULL,
    timestamp TEXT NOT NULL
)
"""


class MemoryDB:
    def __init__(self, db_path: Path = DB_PATH):
        self._conn = sqlite3.connect(str(db_path), check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._init_tables()

    def _init_tables(self) -> None:
        cur = self._conn.cursor()
        cur.execute(CREATE_PROFILES)
        cur.execute(CREATE_CONVERSATIONS)
        self._conn.commit()

    # --- プロフィール ---

    def upsert_profile(self, name: str, features: str = "") -> int:
        now = datetime.now().isoformat()
        cur = self._conn.cursor()
        cur.execute("SELECT id FROM profiles WHERE name = ?", (name,))
        row = cur.fetchone()
        if row:
            cur.execute(
                "UPDATE profiles SET features = ?, updated = ? WHERE id = ?",
                (features, now, row["id"]),
            )
            self._conn.commit()
            return row["id"]
        cur.execute(
            "INSERT INTO profiles (name, features, created, updated) VALUES (?, ?, ?, ?)",
            (name, features, now, now),
        )
        self._conn.commit()
        return cur.lastrowid

    def get_profile(self, name: str) -> dict | None:
        cur = self._conn.cursor()
        cur.execute("SELECT * FROM profiles WHERE name = ?", (name,))
        row = cur.fetchone()
        return dict(row) if row else None

    def format_profile(self, name: str) -> str:
        profile = self.get_profile(name)
        if not profile:
            return ""
        return f"名前: {profile['name']}\n特徴: {profile['features']}"

    # --- 会話履歴 ---

    def save_turn(self, profile_id: int, role: str, content: str) -> None:
        now = datetime.now().isoformat()
        self._conn.execute(
            "INSERT INTO conversations (profile_id, role, content, timestamp) VALUES (?, ?, ?, ?)",
            (profile_id, role, content, now),
        )
        self._conn.commit()

    def get_recent_history(self, profile_id: int, limit: int = 10) -> list[dict]:
        cur = self._conn.cursor()
        cur.execute(
            "SELECT role, content FROM conversations WHERE profile_id = ? ORDER BY id DESC LIMIT ?",
            (profile_id, limit),
        )
        rows = cur.fetchall()
        return [dict(r) for r in reversed(rows)]

    def close(self) -> None:
        self._conn.close()
