from __future__ import annotations

from pathlib import Path

from openpyxl import Workbook
from openpyxl.styles import Font


def build_dispatch_report_from_pg(rows, output_path: str) -> str:
    """Строит Excel-отчёт из строк dispatch_log (PostgreSQL — общий лог бота и веба)."""
    wb = Workbook()
    ws = wb.active
    ws.title = "Рассылки"
    headers = [
        "№",
        "Источник",
        "Вид ЧС",
        "Чат",
        "Chat ID",
        "Отправил",
        "Дата отправки",
        "Текст сообщения",
    ]
    ws.append(headers)
    for cell in ws[1]:
        cell.font = Font(bold=True)

    for row in rows:
        source_label = "Telegram бот" if row.get("source") == "bot" else "Веб-портал"
        sent_at = row.get("sent_at")
        if sent_at and hasattr(sent_at, "strftime"):
            sent_at = sent_at.strftime("%d.%m.%Y %H:%M")
        ws.append([
            row.get("id"),
            source_label,
            row.get("emergency_type") or "",
            row.get("chat_name") or "",
            row.get("chat_id"),
            row.get("sent_by") or "",
            sent_at,
            row.get("message_text") or "",
        ])

    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    wb.save(path)
    return str(path)


# Оставляем старую функцию как заглушку для обратной совместимости
def build_dispatch_report(rows, output_path: str) -> str:
    return build_dispatch_report_from_pg(rows, output_path)
