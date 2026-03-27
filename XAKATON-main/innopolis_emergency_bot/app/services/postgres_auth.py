from __future__ import annotations

import logging
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass(slots=True)
class ExternalAdmin:
    telegram_id: int
    full_name: str = ""
    username: str = ""
    role: str = "admin"


class PostgresAuth:
    def __init__(self, dsn: str | None):
        self.dsn = dsn
        self.enabled = bool(dsn)

    def fetch_admins(self) -> list[ExternalAdmin]:
        if not self.dsn:
            return []
        try:
            import psycopg
        except Exception:
            logger.exception("psycopg is not installed")
            return []
        try:
            with psycopg.connect(self.dsn) as conn:
                with conn.cursor() as cur:
                    cur.execute(
                        """
                        SELECT telegram_id, COALESCE(full_name, ''), COALESCE(username, ''), COALESCE(role, 'admin')
                        FROM bot_admins
                        WHERE COALESCE(is_active, TRUE) = TRUE
                        """
                    )
                    rows = cur.fetchall()
            return [ExternalAdmin(int(r[0]), str(r[1] or ''), str(r[2] or ''), str(r[3] or 'admin')) for r in rows]
        except Exception:
            logger.exception("Failed to fetch admins from PostgreSQL")
            return []

    def get_admin(self, telegram_id: int) -> ExternalAdmin | None:
        if not self.dsn:
            return None
        try:
            import psycopg
        except Exception:
            logger.exception("psycopg is not installed")
            return None
        try:
            with psycopg.connect(self.dsn) as conn:
                with conn.cursor() as cur:
                    cur.execute(
                        """
                        SELECT telegram_id, COALESCE(full_name, ''), COALESCE(username, ''), COALESCE(role, 'admin')
                        FROM bot_admins
                        WHERE telegram_id = %s AND COALESCE(is_active, TRUE) = TRUE
                        LIMIT 1
                        """,
                        (telegram_id,),
                    )
                    row = cur.fetchone()
            if not row:
                return None
            return ExternalAdmin(int(row[0]), str(row[1] or ''), str(row[2] or ''), str(row[3] or 'admin'))
        except Exception:
            logger.exception("Failed to fetch admin from PostgreSQL")
            return None
