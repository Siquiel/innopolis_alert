from __future__ import annotations

import json
import sqlite3
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

SCHEMA = """
PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS admins (
    telegram_id INTEGER PRIMARY KEY,
    full_name TEXT DEFAULT '',
    username TEXT DEFAULT '',
    role TEXT NOT NULL DEFAULT 'admin',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS settings (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS managed_chats (
    chat_id INTEGER PRIMARY KEY,
    title TEXT NOT NULL,
    username TEXT DEFAULT '',
    chat_type TEXT NOT NULL,
    is_active INTEGER NOT NULL DEFAULT 1,
    auto_registered INTEGER NOT NULL DEFAULT 1,
    notes TEXT DEFAULT '',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    last_seen_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS emergency_types (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL UNIQUE,
    description TEXT DEFAULT '',
    is_active INTEGER NOT NULL DEFAULT 1,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS danger_levels (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    emergency_type_id INTEGER NOT NULL,
    name TEXT NOT NULL,
    description TEXT DEFAULT '',
    severity_rank INTEGER NOT NULL DEFAULT 1,
    is_active INTEGER NOT NULL DEFAULT 1,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    UNIQUE(emergency_type_id, name),
    FOREIGN KEY(emergency_type_id) REFERENCES emergency_types(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS templates (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    emergency_type_id INTEGER NOT NULL,
    danger_level_id INTEGER,
    title TEXT NOT NULL,
    body TEXT NOT NULL,
    media_type TEXT DEFAULT '',
    media_file_id TEXT DEFAULT '',
    is_active INTEGER NOT NULL DEFAULT 1,
    created_by INTEGER,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    FOREIGN KEY(emergency_type_id) REFERENCES emergency_types(id) ON DELETE CASCADE,
    FOREIGN KEY(danger_level_id) REFERENCES danger_levels(id) ON DELETE SET NULL
);

CREATE TABLE IF NOT EXISTS template_buttons (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    template_id INTEGER NOT NULL,
    text TEXT NOT NULL,
    url TEXT NOT NULL,
    sort_order INTEGER NOT NULL DEFAULT 0,
    FOREIGN KEY(template_id) REFERENCES templates(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS template_targets (
    template_id INTEGER NOT NULL,
    chat_id INTEGER NOT NULL,
    PRIMARY KEY(template_id, chat_id),
    FOREIGN KEY(template_id) REFERENCES templates(id) ON DELETE CASCADE,
    FOREIGN KEY(chat_id) REFERENCES managed_chats(chat_id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS dispatches (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    template_id INTEGER,
    emergency_type_id INTEGER,
    danger_level_id INTEGER,
    title TEXT NOT NULL,
    final_text TEXT NOT NULL,
    media_type TEXT DEFAULT '',
    media_file_id TEXT DEFAULT '',
    button_payload_json TEXT NOT NULL DEFAULT '[]',
    created_by INTEGER NOT NULL,
    status TEXT NOT NULL,
    error_text TEXT DEFAULT '',
    created_at TEXT NOT NULL,
    sent_at TEXT,
    FOREIGN KEY(template_id) REFERENCES templates(id) ON DELETE SET NULL,
    FOREIGN KEY(emergency_type_id) REFERENCES emergency_types(id) ON DELETE SET NULL,
    FOREIGN KEY(danger_level_id) REFERENCES danger_levels(id) ON DELETE SET NULL
);

CREATE TABLE IF NOT EXISTS dispatch_targets (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    dispatch_id INTEGER NOT NULL,
    chat_id INTEGER NOT NULL,
    chat_title TEXT NOT NULL,
    status TEXT NOT NULL,
    error_text TEXT DEFAULT '',
    sent_at TEXT,
    FOREIGN KEY(dispatch_id) REFERENCES dispatches(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS alerts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    source TEXT NOT NULL,
    dedupe_key TEXT NOT NULL UNIQUE,
    title TEXT NOT NULL,
    body TEXT NOT NULL,
    severity TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'new',
    created_at TEXT NOT NULL,
    acknowledged_at TEXT
);
"""


@dataclass(slots=True)
class DispatchDraft:
    title: str
    text: str
    media_type: str = ""
    media_file_id: str = ""
    buttons: list[dict[str, str]] | None = None


class Storage:
    def __init__(self, path: str):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._ensure_schema()

    @staticmethod
    def now() -> str:
        return datetime.now(timezone.utc).isoformat()

    @contextmanager
    def _conn(self):
        conn = sqlite3.connect(self.path)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
            conn.commit()
        finally:
            conn.close()

    def _ensure_schema(self) -> None:
        with self._conn() as conn:
            conn.executescript(SCHEMA)
        if not self.get_setting("staff_greeting"):
            self.set_setting(
                "staff_greeting",
                "Здравствуйте. Это служебный бот локального оповещения Иннополиса.\n\n"
                "Здесь вы можете управлять типами ЧС, шаблонами, целевыми чатами и запускать рассылки.",
            )

    def execute(self, sql: str, params: Iterable[Any] = ()) -> int:
        with self._conn() as conn:
            cur = conn.execute(sql, tuple(params))
            return int(cur.lastrowid or 0)

    def executemany(self, sql: str, rows: Iterable[Iterable[Any]]) -> None:
        with self._conn() as conn:
            conn.executemany(sql, [tuple(r) for r in rows])

    def fetchone(self, sql: str, params: Iterable[Any] = ()) -> sqlite3.Row | None:
        with self._conn() as conn:
            return conn.execute(sql, tuple(params)).fetchone()

    def fetchall(self, sql: str, params: Iterable[Any] = ()) -> list[sqlite3.Row]:
        with self._conn() as conn:
            return conn.execute(sql, tuple(params)).fetchall()

    # Settings/admins
    def set_setting(self, key: str, value: str) -> None:
        now = self.now()
        self.execute(
            """
            INSERT INTO settings(key, value, updated_at) VALUES(?, ?, ?)
            ON CONFLICT(key) DO UPDATE SET value=excluded.value, updated_at=excluded.updated_at
            """,
            (key, value, now),
        )

    def get_setting(self, key: str, default: str = "") -> str:
        row = self.fetchone("SELECT value FROM settings WHERE key = ?", (key,))
        return str(row["value"]) if row else default

    def upsert_admin(self, telegram_id: int, full_name: str = "", username: str = "", role: str = "admin") -> None:
        now = self.now()
        self.execute(
            """
            INSERT INTO admins(telegram_id, full_name, username, role, created_at, updated_at)
            VALUES(?, ?, ?, ?, ?, ?)
            ON CONFLICT(telegram_id) DO UPDATE SET
                full_name=excluded.full_name,
                username=excluded.username,
                role=excluded.role,
                updated_at=excluded.updated_at
            """,
            (telegram_id, full_name, username, role, now, now),
        )

    def is_admin(self, telegram_id: int) -> bool:
        return self.fetchone("SELECT 1 FROM admins WHERE telegram_id = ?", (telegram_id,)) is not None

    def has_any_admins(self) -> bool:
        row = self.fetchone("SELECT COUNT(*) AS cnt FROM admins")
        return bool(row and int(row["cnt"]) > 0)

    def list_admins(self) -> list[sqlite3.Row]:
        return self.fetchall("SELECT * FROM admins ORDER BY role DESC, full_name COLLATE NOCASE, telegram_id")

    def delete_admin(self, telegram_id: int) -> None:
        self.execute("DELETE FROM admins WHERE telegram_id = ?", (telegram_id,))

    def get_moderator_chat_id(self) -> int | None:
        raw = self.get_setting("moderator_chat_id", "").strip()
        return int(raw) if raw else None

    def set_moderator_chat_id(self, chat_id: int) -> None:
        self.set_setting("moderator_chat_id", str(chat_id))

    # Managed chats
    def upsert_managed_chat(self, chat_id: int, title: str, chat_type: str, username: str = "", auto_registered: bool = True) -> None:
        now = self.now()
        self.execute(
            """
            INSERT INTO managed_chats(chat_id, title, username, chat_type, is_active, auto_registered, created_at, updated_at, last_seen_at)
            VALUES(?, ?, ?, ?, 1, ?, ?, ?, ?)
            ON CONFLICT(chat_id) DO UPDATE SET
                title=excluded.title,
                username=excluded.username,
                chat_type=excluded.chat_type,
                is_active=1,
                auto_registered=excluded.auto_registered,
                updated_at=excluded.updated_at,
                last_seen_at=excluded.last_seen_at
            """,
            (chat_id, title, username, chat_type, 1 if auto_registered else 0, now, now, now),
        )

    def set_chat_active(self, chat_id: int, active: bool) -> None:
        self.execute(
            "UPDATE managed_chats SET is_active = ?, updated_at = ? WHERE chat_id = ?",
            (1 if active else 0, self.now(), chat_id),
        )

    def update_chat_notes(self, chat_id: int, notes: str) -> None:
        self.execute(
            "UPDATE managed_chats SET notes = ?, updated_at = ? WHERE chat_id = ?",
            (notes.strip(), self.now(), chat_id),
        )

    def get_chat(self, chat_id: int):
        return self.fetchone("SELECT * FROM managed_chats WHERE chat_id = ?", (chat_id,))

    def list_chats(self, active_only: bool = False) -> list[sqlite3.Row]:
        sql = "SELECT * FROM managed_chats"
        params: tuple[Any, ...] = ()
        if active_only:
            sql += " WHERE is_active = 1"
        sql += " ORDER BY is_active DESC, title COLLATE NOCASE"
        return self.fetchall(sql, params)

    # Types and levels
    def add_emergency_type(self, name: str, description: str) -> int:
        now = self.now()
        return self.execute(
            "INSERT INTO emergency_types(name, description, created_at, updated_at) VALUES(?, ?, ?, ?)",
            (name.strip(), description.strip(), now, now),
        )

    def update_emergency_type(self, type_id: int, name: str, description: str) -> None:
        self.execute(
            "UPDATE emergency_types SET name = ?, description = ?, updated_at = ? WHERE id = ?",
            (name.strip(), description.strip(), self.now(), type_id),
        )

    def delete_emergency_type(self, type_id: int) -> None:
        self.execute("DELETE FROM emergency_types WHERE id = ?", (type_id,))

    def get_emergency_type(self, type_id: int):
        return self.fetchone("SELECT * FROM emergency_types WHERE id = ?", (type_id,))

    def list_emergency_types(self) -> list[sqlite3.Row]:
        return self.fetchall("SELECT * FROM emergency_types ORDER BY name COLLATE NOCASE")

    def add_danger_level(self, emergency_type_id: int, name: str, description: str, severity_rank: int) -> int:
        now = self.now()
        return self.execute(
            """
            INSERT INTO danger_levels(emergency_type_id, name, description, severity_rank, created_at, updated_at)
            VALUES(?, ?, ?, ?, ?, ?)
            """,
            (emergency_type_id, name.strip(), description.strip(), severity_rank, now, now),
        )

    def update_danger_level(self, level_id: int, emergency_type_id: int, name: str, description: str, severity_rank: int) -> None:
        self.execute(
            """
            UPDATE danger_levels
            SET emergency_type_id = ?, name = ?, description = ?, severity_rank = ?, updated_at = ?
            WHERE id = ?
            """,
            (emergency_type_id, name.strip(), description.strip(), severity_rank, self.now(), level_id),
        )

    def delete_danger_level(self, level_id: int) -> None:
        self.execute("DELETE FROM danger_levels WHERE id = ?", (level_id,))

    def get_danger_level(self, level_id: int):
        return self.fetchone(
            """
            SELECT dl.*, et.name AS type_name
            FROM danger_levels dl
            JOIN emergency_types et ON et.id = dl.emergency_type_id
            WHERE dl.id = ?
            """,
            (level_id,),
        )

    def list_danger_levels(self, emergency_type_id: int | None = None) -> list[sqlite3.Row]:
        sql = """
            SELECT dl.*, et.name AS type_name
            FROM danger_levels dl
            JOIN emergency_types et ON et.id = dl.emergency_type_id
        """
        params: tuple[Any, ...] = ()
        if emergency_type_id is not None:
            sql += " WHERE dl.emergency_type_id = ?"
            params = (emergency_type_id,)
        sql += " ORDER BY et.name COLLATE NOCASE, dl.severity_rank DESC, dl.name COLLATE NOCASE"
        return self.fetchall(sql, params)

    # Templates and buttons
    def add_template(
        self,
        emergency_type_id: int,
        danger_level_id: int | None,
        title: str,
        body: str,
        media_type: str,
        media_file_id: str,
        created_by: int | None,
    ) -> int:
        now = self.now()
        return self.execute(
            """
            INSERT INTO templates(
                emergency_type_id, danger_level_id, title, body, media_type, media_file_id,
                created_by, created_at, updated_at
            ) VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (emergency_type_id, danger_level_id, title.strip(), body.strip(), media_type.strip(), media_file_id.strip(), created_by, now, now),
        )

    def update_template(
        self,
        template_id: int,
        emergency_type_id: int,
        danger_level_id: int | None,
        title: str,
        body: str,
        media_type: str,
        media_file_id: str,
    ) -> None:
        self.execute(
            """
            UPDATE templates
            SET emergency_type_id = ?, danger_level_id = ?, title = ?, body = ?, media_type = ?, media_file_id = ?, updated_at = ?
            WHERE id = ?
            """,
            (emergency_type_id, danger_level_id, title.strip(), body.strip(), media_type.strip(), media_file_id.strip(), self.now(), template_id),
        )

    def delete_template(self, template_id: int) -> None:
        self.execute("DELETE FROM templates WHERE id = ?", (template_id,))

    def get_template(self, template_id: int):
        return self.fetchone(
            """
            SELECT t.*, et.name AS type_name, dl.name AS level_name
            FROM templates t
            JOIN emergency_types et ON et.id = t.emergency_type_id
            LEFT JOIN danger_levels dl ON dl.id = t.danger_level_id
            WHERE t.id = ?
            """,
            (template_id,),
        )

    def list_templates(self, emergency_type_id: int | None = None) -> list[sqlite3.Row]:
        sql = """
            SELECT t.*, et.name AS type_name, dl.name AS level_name
            FROM templates t
            JOIN emergency_types et ON et.id = t.emergency_type_id
            LEFT JOIN danger_levels dl ON dl.id = t.danger_level_id
        """
        params: tuple[Any, ...] = ()
        if emergency_type_id is not None:
            sql += " WHERE t.emergency_type_id = ?"
            params = (emergency_type_id,)
        sql += " ORDER BY t.updated_at DESC"
        return self.fetchall(sql, params)

    def add_template_button(self, template_id: int, text: str, url: str) -> int:
        row = self.fetchone("SELECT COALESCE(MAX(sort_order), 0) + 1 AS next_order FROM template_buttons WHERE template_id = ?", (template_id,))
        next_order = int(row["next_order"]) if row else 1
        return self.execute(
            "INSERT INTO template_buttons(template_id, text, url, sort_order) VALUES(?, ?, ?, ?)",
            (template_id, text.strip(), url.strip(), next_order),
        )

    def delete_template_button(self, button_id: int) -> None:
        self.execute("DELETE FROM template_buttons WHERE id = ?", (button_id,))

    def list_template_buttons(self, template_id: int) -> list[sqlite3.Row]:
        return self.fetchall(
            "SELECT * FROM template_buttons WHERE template_id = ? ORDER BY sort_order, id",
            (template_id,),
        )

    def replace_template_targets(self, template_id: int, chat_ids: list[int]) -> None:
        with self._conn() as conn:
            conn.execute("DELETE FROM template_targets WHERE template_id = ?", (template_id,))
            conn.executemany(
                "INSERT INTO template_targets(template_id, chat_id) VALUES(?, ?)",
                [(template_id, chat_id) for chat_id in chat_ids],
            )

    def list_template_target_ids(self, template_id: int) -> list[int]:
        rows = self.fetchall("SELECT chat_id FROM template_targets WHERE template_id = ?", (template_id,))
        return [int(r["chat_id"]) for r in rows]

    def list_template_targets(self, template_id: int) -> list[sqlite3.Row]:
        return self.fetchall(
            """
            SELECT mc.*
            FROM template_targets tt
            JOIN managed_chats mc ON mc.chat_id = tt.chat_id
            WHERE tt.template_id = ?
            ORDER BY mc.title COLLATE NOCASE
            """,
            (template_id,),
        )

    # Dispatches/reports
    def create_dispatch(
        self,
        template_id: int | None,
        emergency_type_id: int | None,
        danger_level_id: int | None,
        title: str,
        final_text: str,
        media_type: str,
        media_file_id: str,
        buttons: list[dict[str, str]],
        created_by: int,
    ) -> int:
        return self.execute(
            """
            INSERT INTO dispatches(
                template_id, emergency_type_id, danger_level_id, title, final_text, media_type,
                media_file_id, button_payload_json, created_by, status, created_at
            ) VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?, 'draft', ?)
            """,
            (template_id, emergency_type_id, danger_level_id, title.strip(), final_text.strip(), media_type, media_file_id, json.dumps(buttons, ensure_ascii=False), created_by, self.now()),
        )

    def mark_dispatch_sent(self, dispatch_id: int, status: str, error_text: str = "") -> None:
        sent_at = self.now() if status == "sent" else None
        self.execute(
            "UPDATE dispatches SET status = ?, error_text = ?, sent_at = ? WHERE id = ?",
            (status, error_text, sent_at, dispatch_id),
        )

    def add_dispatch_target(self, dispatch_id: int, chat_id: int, chat_title: str, status: str, error_text: str = "") -> None:
        self.execute(
            "INSERT INTO dispatch_targets(dispatch_id, chat_id, chat_title, status, error_text, sent_at) VALUES(?, ?, ?, ?, ?, ?)",
            (dispatch_id, chat_id, chat_title, status, error_text, self.now() if status == "sent" else None),
        )

    def list_dispatches_between(self, start_iso: str, end_iso: str) -> list[sqlite3.Row]:
        return self.fetchall(
            "SELECT * FROM dispatches WHERE created_at >= ? AND created_at <= ? ORDER BY id DESC",
            (start_iso, end_iso),
        )

    # Alerts
    def add_alert_once(self, source: str, dedupe_key: str, title: str, body: str, severity: str) -> bool:
        try:
            self.execute(
                "INSERT INTO alerts(source, dedupe_key, title, body, severity, created_at) VALUES(?, ?, ?, ?, ?, ?)",
                (source, dedupe_key, title, body, severity, self.now()),
            )
            return True
        except sqlite3.IntegrityError:
            return False

    def list_recent_alerts(self, limit: int = 10) -> list[sqlite3.Row]:
        return self.fetchall("SELECT * FROM alerts ORDER BY id DESC LIMIT ?", (limit,))
