from __future__ import annotations

import asyncio
import json
import logging
import pathlib

from aiogram import Bot
from aiogram.types import FSInputFile

from app.services.notifier import build_buttons_markup, send_rich_message

# Папка с загруженными файлами веб-сервера
_parents = pathlib.Path(__file__).parents
_SERVER_UPLOADS = (
    _parents[4] / "server" / "uploads"
    if len(_parents) > 4
    else pathlib.Path("/app") / "server" / "uploads"
)


def _resolve_media(media_url: str | None):
    """Возвращает (media_type, FSInputFile | None) для локального файла."""
    if not media_url:
        return "", None
    filename = media_url.lstrip("/").replace("uploads/", "")
    path = _SERVER_UPLOADS / filename
    if not path.exists():
        return "", None
    ext = path.suffix.lower()
    if ext in (".mp4", ".webm", ".mov", ".avi"):
        return "video", path
    return "photo", path

logger = logging.getLogger(__name__)


class PgSync:
    """Синхронизация между Telegram-ботом и веб-порталом через PostgreSQL."""

    def __init__(self, dsn: str | None):
        self.dsn = dsn
        self.enabled = bool(dsn)

    # ── Подключения ───────────────────────────────────────────────────────────

    def _sync_connect(self):
        try:
            import psycopg
            return psycopg.connect(self.dsn)
        except Exception:
            logger.exception("PgSync: sync connect failed")
            return None

    async def _connect(self):
        try:
            import psycopg
            return await psycopg.AsyncConnection.connect(self.dsn)
        except Exception:
            logger.exception("PgSync: async connect failed")
            return None

    # ── Инициализация таблиц ─────────────────────────────────────────────────

    def ensure_tables(self) -> None:
        if not self.enabled:
            return
        conn = self._sync_connect()
        if not conn:
            return
        try:
            with conn.cursor() as cur:
                cur.execute("""
                    CREATE TABLE IF NOT EXISTS bot_admins (
                        telegram_id BIGINT PRIMARY KEY,
                        full_name    VARCHAR(200) DEFAULT '',
                        username     VARCHAR(100) DEFAULT '',
                        role         VARCHAR(20)  DEFAULT 'admin',
                        is_active    BOOLEAN      DEFAULT TRUE,
                        created_at   TIMESTAMP    DEFAULT NOW()
                    )
                """)
                cur.execute("""
                    CREATE TABLE IF NOT EXISTS telegram_chats (
                        id       SERIAL PRIMARY KEY,
                        chat_id  BIGINT UNIQUE NOT NULL,
                        name     VARCHAR(200),
                        active   BOOLEAN DEFAULT TRUE,
                        created_at TIMESTAMP DEFAULT NOW()
                    )
                """)
                cur.execute("""
                    CREATE TABLE IF NOT EXISTS web_queue (
                        id             SERIAL PRIMARY KEY,
                        emergency_type VARCHAR(100),
                        message_text   TEXT NOT NULL,
                        media_url      VARCHAR(500),
                        buttons        JSONB DEFAULT '[]',
                        sent_by        VARCHAR(50),
                        status         VARCHAR(20) DEFAULT 'pending',
                        created_at     TIMESTAMP   DEFAULT NOW(),
                        processed_at   TIMESTAMP
                    )
                """)
                cur.execute("""
                    CREATE TABLE IF NOT EXISTS dispatch_log (
                        id             SERIAL PRIMARY KEY,
                        source         VARCHAR(20) NOT NULL,
                        emergency_type VARCHAR(100),
                        chat_id        BIGINT,
                        chat_name      VARCHAR(200),
                        message_text   TEXT,
                        sent_by        VARCHAR(100),
                        sent_at        TIMESTAMP DEFAULT NOW()
                    )
                """)
            conn.commit()
            logger.info("PgSync: tables OK")
        except Exception:
            logger.exception("PgSync: ensure_tables failed")
        finally:
            conn.close()

    # ── Регистрация чата в PostgreSQL ────────────────────────────────────────

    async def register_chat_to_pg(self, chat_id: int, title: str, active: bool = True) -> None:
        """Записывает/обновляет чат в таблице telegram_chats."""
        if not self.enabled:
            return
        conn = await self._connect()
        if not conn:
            return
        try:
            async with conn.cursor() as cur:
                await cur.execute(
                    """
                    INSERT INTO telegram_chats (chat_id, name, active)
                    VALUES (%s, %s, %s)
                    ON CONFLICT (chat_id) DO UPDATE SET name = EXCLUDED.name
                    """,
                    (chat_id, title or "", active),
                )
            await conn.commit()
        except Exception:
            logger.exception("PgSync: register_chat_to_pg failed for %s", chat_id)
        finally:
            await conn.close()

    # ── Синхронизация шаблонов PG → SQLite ──────────────────────────────────

    async def sync_templates_to_sqlite(self, storage) -> None:
        """Импортирует шаблоны с веб-портала (PostgreSQL) в SQLite бота."""
        if not self.enabled:
            return
        conn = await self._connect()
        if not conn:
            return
        try:
            import psycopg.rows
            async with conn.cursor(row_factory=psycopg.rows.dict_row) as cur:
                # Типы ЧС из PG
                await cur.execute("SELECT id, name FROM emergency_types ORDER BY id")
                pg_types = await cur.fetchall()

                # Шаблоны из PG
                await cur.execute("""
                    SELECT t.id, t.name, t.message_text, t.buttons, et.name AS type_name
                    FROM templates t
                    LEFT JOIN emergency_types et ON et.id = t.emergency_type_id
                    ORDER BY t.id
                """)
                pg_templates = await cur.fetchall()

            # Уpsert типов ЧС в SQLite
            for pt in pg_types:
                existing_type = storage.fetchone(
                    "SELECT id FROM emergency_types WHERE name = ?", (pt["name"],)
                )
                if not existing_type:
                    storage.add_emergency_type(pt["name"], "")

            # Upsert шаблонов в SQLite (с маркером [Портал])
            for tmpl in pg_templates:
                if not tmpl.get("type_name"):
                    continue
                et_row = storage.fetchone(
                    "SELECT id FROM emergency_types WHERE name = ?", (tmpl["type_name"],)
                )
                if not et_row:
                    continue
                et_id = et_row["id"]
                title = f"[Портал] {tmpl['name']}"
                existing_tmpl = storage.fetchone(
                    "SELECT id FROM templates WHERE title = ?", (title,)
                )
                if not existing_tmpl:
                    tmpl_id = storage.add_template(
                        emergency_type_id=et_id,
                        danger_level_id=None,
                        title=title,
                        body=tmpl["message_text"] or "",
                        media_type="",
                        media_file_id="",
                        created_by=None,
                    )
                    buttons = tmpl.get("buttons") or []
                    if isinstance(buttons, str):
                        buttons = json.loads(buttons)
                    for btn in buttons:
                        if isinstance(btn, dict) and btn.get("text") and btn.get("url"):
                            storage.add_template_button(tmpl_id, btn["text"], btn["url"])
                else:
                    # Обновляем текст шаблона если изменился
                    storage.execute(
                        "UPDATE templates SET body = ?, updated_at = ? WHERE title = ?",
                        (tmpl["message_text"] or "", storage.now(), title),
                    )

            logger.info("PgSync: templates synced to SQLite (%d templates)", len(pg_templates))
        except Exception:
            logger.exception("PgSync: sync_templates_to_sqlite failed")
        finally:
            await conn.close()

    # ── Логирование рассылки ─────────────────────────────────────────────────

    async def log_dispatch(
        self,
        source: str,
        emergency_type: str | None,
        chat_id: int,
        chat_name: str,
        message_text: str,
        sent_by: str = "bot",
    ) -> None:
        if not self.enabled:
            return
        conn = await self._connect()
        if not conn:
            return
        try:
            async with conn.cursor() as cur:
                await cur.execute(
                    """
                    INSERT INTO dispatch_log
                        (source, emergency_type, chat_id, chat_name, message_text, sent_by)
                    VALUES (%s, %s, %s, %s, %s, %s)
                    """,
                    (source, emergency_type, chat_id, chat_name, message_text, sent_by),
                )
            await conn.commit()
        except Exception:
            logger.exception("PgSync: log_dispatch failed")
        finally:
            await conn.close()

    # ── Чтение dispatch_log для отчёта ──────────────────────────────────────

    async def fetch_dispatch_log(self, date_from: str | None, date_to: str | None) -> list[dict]:
        """Читает unified dispatch_log из PostgreSQL для Excel-отчёта."""
        if not self.enabled:
            return []
        conn = await self._connect()
        if not conn:
            return []
        try:
            import psycopg.rows
            async with conn.cursor(row_factory=psycopg.rows.dict_row) as cur:
                await cur.execute(
                    """
                    SELECT id, source, emergency_type, chat_id, chat_name,
                           message_text, sent_by, sent_at
                    FROM dispatch_log
                    WHERE (%s::date IS NULL OR sent_at >= %s::date)
                      AND (%s::date IS NULL OR sent_at <= (%s::date + interval '1 day'))
                    ORDER BY sent_at DESC
                    """,
                    (date_from, date_from, date_to, date_to),
                )
                rows = await cur.fetchall()
            return list(rows)
        except Exception:
            logger.exception("PgSync: fetch_dispatch_log failed")
            return []
        finally:
            await conn.close()

    # ── Добавление инцидента на карту ────────────────────────────────────────

    async def add_map_incident(
        self,
        title: str,
        description: str,
        lat: float,
        lon: float,
        emergency_type_id: int | None,
    ) -> bool:
        """Добавляет точку на карту ЧС в PostgreSQL."""
        if not self.enabled:
            return False
        conn = await self._connect()
        if not conn:
            return False
        try:
            async with conn.cursor() as cur:
                await cur.execute(
                    """
                    INSERT INTO map_incidents (title, description, lat, lon, emergency_type_id, status)
                    VALUES (%s, %s, %s, %s, %s, 'active')
                    """,
                    (title, description or "", lat, lon, emergency_type_id),
                )
            await conn.commit()
            return True
        except Exception:
            logger.exception("PgSync: add_map_incident failed")
            return False
        finally:
            await conn.close()

    # ── Список типов ЧС из PostgreSQL ────────────────────────────────────────

    async def fetch_emergency_types(self) -> list[dict]:
        if not self.enabled:
            return []
        conn = await self._connect()
        if not conn:
            return []
        try:
            import psycopg.rows
            async with conn.cursor(row_factory=psycopg.rows.dict_row) as cur:
                await cur.execute("SELECT id, name FROM emergency_types ORDER BY id")
                return list(await cur.fetchall())
        except Exception:
            logger.exception("PgSync: fetch_emergency_types failed")
            return []
        finally:
            await conn.close()

    # ── Активные инциденты карты для мониторинга ─────────────────────────────

    async def fetch_active_map_incidents(self, limit: int = 10) -> list[dict]:
        """Возвращает активные инциденты с карты ЧС из PostgreSQL."""
        if not self.enabled:
            return []
        conn = await self._connect()
        if not conn:
            return []
        try:
            import psycopg.rows
            async with conn.cursor(row_factory=psycopg.rows.dict_row) as cur:
                await cur.execute(
                    """
                    SELECT mi.id, mi.title, mi.description, mi.lat, mi.lon, mi.status,
                           mi.created_at,
                           et.name AS emergency_type_name,
                           dl.name AS danger_level_name,
                           dl.color AS danger_color
                    FROM map_incidents mi
                    LEFT JOIN emergency_types et ON et.id = mi.emergency_type_id
                    LEFT JOIN danger_levels dl ON dl.id = mi.danger_level_id
                    WHERE mi.status = 'active'
                    ORDER BY mi.created_at DESC
                    LIMIT %s
                    """,
                    (limit,),
                )
                return list(await cur.fetchall())
        except Exception:
            logger.exception("PgSync: fetch_active_map_incidents failed")
            return []
        finally:
            await conn.close()

    # ── Цикл обработки очереди от веб-портала ───────────────────────────────

    async def web_queue_loop(self, bot: Bot, storage) -> None:
        if not self.enabled:
            logger.info("PgSync: disabled (POSTGRES_DSN не задан)")
            return
        logger.info("PgSync: web_queue_loop запущен")
        while True:
            try:
                await self._process_queue(bot, storage)
            except Exception:
                logger.exception("PgSync: web_queue_loop error")
            await asyncio.sleep(5)

    async def _process_queue(self, bot: Bot, storage) -> None:
        conn = await self._connect()
        if not conn:
            return
        try:
            import psycopg.rows

            async with conn.cursor(row_factory=psycopg.rows.dict_row) as cur:
                # Забираем pending-задания
                await cur.execute(
                    """
                    SELECT * FROM web_queue
                    WHERE status = 'pending'
                    ORDER BY created_at
                    LIMIT 10
                    FOR UPDATE SKIP LOCKED
                    """
                )
                jobs = await cur.fetchall()
                if not jobs:
                    await conn.rollback()
                    return
                job_ids = [j["id"] for j in jobs]
                await cur.execute(
                    "UPDATE web_queue SET status='processing' WHERE id = ANY(%s)", (job_ids,)
                )
                await conn.commit()

                # Читаем активные чаты из PostgreSQL (веб-портал управляет ими)
                await cur.execute(
                    "SELECT chat_id, name FROM telegram_chats WHERE active = TRUE"
                )
                pg_chats = await cur.fetchall()

            # Если в PG нет чатов — берём из SQLite (fallback)
            if pg_chats:
                chats = [{"chat_id": c["chat_id"], "title": c["name"] or str(c["chat_id"])} for c in pg_chats]
            else:
                chats = [{"chat_id": c["chat_id"], "title": c["title"]} for c in storage.list_chats(active_only=True)]

            for job in jobs:
                sent = 0
                failed = 0
                buttons = job.get("buttons") or []
                if isinstance(buttons, str):
                    buttons = json.loads(buttons)

                media_type, media_path = _resolve_media(job.get("media_url"))
                markup = build_buttons_markup(buttons)

                for chat in chats:
                    chat_id = int(chat["chat_id"])
                    chat_name = str(chat["title"])
                    try:
                        text = job["message_text"]
                        if media_path and media_type == "photo":
                            await bot.send_photo(chat_id, photo=FSInputFile(str(media_path)), caption=text, reply_markup=markup)
                        elif media_path and media_type == "video":
                            await bot.send_video(chat_id, video=FSInputFile(str(media_path)), caption=text, reply_markup=markup)
                        else:
                            await send_rich_message(bot, chat_id, text, "", "", buttons)
                        sent += 1
                        await self.log_dispatch(
                            "web",
                            job.get("emergency_type"),
                            chat_id, chat_name,
                            job["message_text"],
                            job.get("sent_by") or "web",
                        )
                    except Exception:
                        logger.exception("PgSync: send failed -> chat %s", chat_id)
                        failed += 1

                status = "done" if failed == 0 else ("partial" if sent > 0 else "failed")
                async with conn.cursor() as cur:
                    await cur.execute(
                        "UPDATE web_queue SET status=%s, processed_at=NOW() WHERE id=%s",
                        (status, job["id"]),
                    )
                await conn.commit()

        except Exception:
            logger.exception("PgSync: _process_queue error")
            with asyncio.suppress(Exception):
                await conn.rollback()
        finally:
            await conn.close()
