from __future__ import annotations

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder


def home_kb() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    buttons = [
        ("📣 Рассылка", "home:dispatch"),
        ("🏘 Чаты и каналы", "home:chats"),
        ("👮 Модерация", "home:moderation"),
        ("📄 Отчёт", "home:report"),
        ("🗺 Карта ЧС", "home:map"),
        ("📡 Мониторинг", "home:monitor"),
        ("📂 Виды ЧС", "home:types"),
        ("📋 Шаблоны", "home:templates"),
        ("ℹ️ ID / Статус", "home:status"),
    ]
    for text, data in buttons:
        builder.button(text=text, callback_data=data)
    builder.adjust(2, 2, 2, 2, 2, 1)
    return builder.as_markup()


def back_home_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="⬅️ В главное меню", callback_data="nav:home")]])


def yes_no_kb(prefix: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="✅ Да", callback_data=f"{prefix}:yes"),
                InlineKeyboardButton(text="❌ Нет", callback_data=f"{prefix}:no"),
            ]
        ]
    )


def items_kb(prefix: str, items: list[tuple[str, str]], extra: list[tuple[str, str]] | None = None, back: str = "nav:home") -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    for text, data in items:
        builder.button(text=text, callback_data=data)
    if extra:
        for text, data in extra:
            builder.button(text=text, callback_data=data)
    builder.button(text="⬅️ Назад", callback_data=back)
    builder.adjust(1)
    return builder.as_markup()


def template_manage_kb(template_id: int) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="✏️ Изменить заголовок", callback_data=f"tmpl_edit_title:{template_id}")
    builder.button(text="📝 Изменить текст", callback_data=f"tmpl_edit_body:{template_id}")
    builder.button(text="🖼 Медиа", callback_data=f"tmpl_edit_media:{template_id}")
    builder.button(text="🔗 Кнопки", callback_data=f"tmpl_buttons:{template_id}")
    builder.button(text="🎯 Чаты по умолчанию", callback_data=f"tmpl_targets:{template_id}")
    builder.button(text="📣 Создать рассылку", callback_data=f"dispatch_from_template:{template_id}")
    builder.button(text="🗑 Удалить", callback_data=f"tmpl_delete:{template_id}")
    builder.button(text="⬅️ К шаблонам", callback_data="home:templates")
    builder.adjust(2, 2, 1, 1, 1)
    return builder.as_markup()


def dispatch_preview_kb() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="🤖 Улучшить ИИ", callback_data="dispatch:ai")
    builder.button(text="✏️ Редактировать текст", callback_data="dispatch:edit_text")
    builder.button(text="🖼 Медиа", callback_data="dispatch:media")
    builder.button(text="🎯 Выбрать чаты", callback_data="dispatch:targets")
    builder.button(text="🚀 Отправить", callback_data="dispatch:send")
    builder.button(text="❌ Отменить", callback_data="dispatch:cancel")
    builder.adjust(2, 2, 1, 1)
    return builder.as_markup()


def toggles_kb(prefix: str, values: list[tuple[str, str, bool]], done_cb: str, back_cb: str, select_all_cb: str | None = None) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    if select_all_cb:
        all_selected = all(enabled for _, _, enabled in values)
        label = "❎ Снять все" if all_selected else "✅ Выбрать все"
        builder.button(text=label, callback_data=select_all_cb)
    for label, value, enabled in values:
        mark = "✅" if enabled else "⬜️"
        builder.button(text=f"{mark} {label}", callback_data=f"{prefix}:{value}")
    builder.button(text="💾 Готово", callback_data=done_cb)
    builder.button(text="⬅️ Назад", callback_data=back_cb)
    builder.adjust(1)
    return builder.as_markup()


def buttons_manage_kb(template_id: int, button_rows: list[tuple[int, str]]) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    for button_id, label in button_rows:
        builder.button(text=f"🗑 {label}", callback_data=f"tmpl_button_del:{template_id}:{button_id}")
    builder.button(text="➕ Добавить кнопку", callback_data=f"tmpl_button_add:{template_id}")
    builder.button(text="⬅️ К шаблону", callback_data=f"tmpl_open:{template_id}")
    builder.adjust(1)
    return builder.as_markup()


def chat_manage_kb(chat_id: int, is_active: bool) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="✏️ Примечание", callback_data=f"chat_notes:{chat_id}")
    builder.button(text=("🔕 Отключить" if is_active else "🔔 Включить"), callback_data=f"chat_toggle:{chat_id}")
    builder.button(text="🎛 Сделать чатом модерации", callback_data=f"moder_chat_set:{chat_id}")
    builder.button(text="🗑 Удалить из системы", callback_data=f"chat_delete:{chat_id}")
    builder.button(text="⬅️ К списку чатов", callback_data="home:chats")
    builder.adjust(1)
    return builder.as_markup()


def moderation_chat_kb(chats: list[tuple[int, str]], selected_chat_id: int | None) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    for chat_id, title in chats:
        mark = "✅" if selected_chat_id == chat_id else "⬜️"
        builder.button(text=f"{mark} {title}", callback_data=f"moder_chat_set:{chat_id}")
    builder.button(text="➕ Добавить локального админа", callback_data="admin_add")
    builder.button(text="🗑 Удалить локального админа", callback_data="admin_manage")
    builder.button(text="⬅️ В главное меню", callback_data="nav:home")
    builder.adjust(1)
    return builder.as_markup()


def admin_manage_kb(admin_rows: list[tuple[int, str]], self_id: int | None = None) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    for admin_id, label in admin_rows:
        if self_id and admin_id == self_id:
            continue
        builder.button(text=f"🗑 {label}", callback_data=f"admin_del:{admin_id}")
    builder.button(text="➕ Добавить по Telegram ID", callback_data="admin_add")
    builder.button(text="⬅️ В главное меню", callback_data="nav:home")
    builder.adjust(1)
    return builder.as_markup()
