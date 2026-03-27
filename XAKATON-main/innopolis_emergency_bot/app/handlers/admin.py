from __future__ import annotations

from datetime import datetime, timedelta, timezone

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, FSInputFile, Message

from app.keyboards import (
    admin_manage_kb,
    back_home_kb,
    buttons_manage_kb,
    chat_manage_kb,
    dispatch_preview_kb,
    home_kb,
    items_kb,
    moderation_chat_kb,
    template_manage_kb,
    toggles_kb,
)
from app.services.report import build_dispatch_report_from_pg
from app.services.notifier import send_rich_message
from app.states import AdminState, ChatState, DispatchState, GreetingState, LevelState, MapIncidentState, ReportState, TemplateState, TypeState

router = Router(name="admin")


def _admin_guard(entity, storage) -> bool:
    user = getattr(entity, "from_user", None)
    if not user or not storage.is_admin(user.id):
        return False
    if isinstance(entity, CallbackQuery):
        message = entity.message
        return bool(message and message.chat and message.chat.type == "private")
    chat = getattr(entity, "chat", None)
    return bool(chat and chat.type == "private")


async def _deny(entity):
    target = entity.message if isinstance(entity, CallbackQuery) else entity
    await target.answer("Доступно только администраторам в личном чате.")


async def _safe_edit_message(message: Message, text: str, reply_markup=None) -> None:
    try:
        await message.edit_text(text, reply_markup=reply_markup)
    except Exception:
        await message.answer(text, reply_markup=reply_markup)


async def _show_home(target: Message | CallbackQuery, storage) -> None:
    text = storage.get_setting("staff_greeting")
    if isinstance(target, CallbackQuery):
        await _safe_edit_message(target.message, text, reply_markup=home_kb())
    else:
        await target.answer(text, reply_markup=home_kb())


async def _render_template_open(message: Message, template_id: int, storage) -> None:
    row = storage.get_template(template_id)
    if not row:
        await _safe_edit_message(message, "Шаблон не найден.", reply_markup=back_home_kb())
        return
    buttons = storage.list_template_buttons(template_id)
    targets = storage.list_template_targets(template_id)
    text = (
        f"<b>{row['title']}</b>\n"
        f"Тип ЧС: {row['type_name']}\n"
        f"Подуровень: {row['level_name'] or 'не задан'}\n"
        f"Медиа: {row['media_type'] or 'нет'}\n"
        f"Кнопок: {len(buttons)}\n"
        f"Чатов по умолчанию: {len(targets)}\n\n"
        f"{row['body']}"
    )
    await _safe_edit_message(message, text, reply_markup=template_manage_kb(template_id))


async def _render_template_buttons(message: Message, template_id: int, storage) -> None:
    rows = storage.list_template_buttons(template_id)
    kb = buttons_manage_kb(template_id, [(r["id"], f"{r['text']} → {r['url']}") for r in rows])
    text = "<b>Кнопки шаблона</b>\n\n" + ("\n".join([f"• {r['text']} — {r['url']}" for r in rows]) if rows else "Кнопок пока нет.")
    await _safe_edit_message(message, text, reply_markup=kb)


async def _render_chat_open(message: Message, chat_id: int, storage) -> None:
    row = storage.get_chat(chat_id)
    if not row:
        await _safe_edit_message(message, "Чат не найден.", reply_markup=back_home_kb())
        return
    username_line = f"@{row['username']}" if row['username'] else '—'
    text = (
        f"<b>{row['title']}</b>\n"
        f"ID: <code>{row['chat_id']}</code>\n"
        f"Тип: {row['chat_type']}\n"
        f"Статус: {'активен' if row['is_active'] else 'отключён'}\n"
        f"Username: {username_line}\n\n"
        f"Примечание: {row['notes'] or 'нет'}"
    )
    await _safe_edit_message(message, text, reply_markup=chat_manage_kb(chat_id, bool(row['is_active'])))


def _types_text(storage) -> str:
    rows = storage.list_emergency_types()
    if not rows:
        return "Типы ЧС пока не добавлены."
    out = ["<b>Виды ЧС</b>"]
    for row in rows:
        out.append(f"• <b>{row['name']}</b> — {row['description'] or 'без описания'}")
    return "\n".join(out)


@router.message(Command("admin"))
async def cmd_admin(message: Message, storage) -> None:
    if not _admin_guard(message, storage):
        await _deny(message)
        return
    await _show_home(message, storage)


@router.message(Command("health"))
async def cmd_health(message: Message, storage, config) -> None:
    if not _admin_guard(message, storage):
        await _deny(message)
        return
    chats = len(storage.list_chats())
    active_chats = len(storage.list_chats(active_only=True))
    templates = len(storage.list_templates())
    types = len(storage.list_emergency_types())
    alerts = storage.list_recent_alerts(5)
    text = (
        "<b>Состояние системы</b>\n"
        f"• База: OK\n"
        f"• Админов из БД: работает\n"
        f"• Город: {config.city_name}\n"
        f"• Чаты/каналы: {active_chats} активных из {chats}\n"
        f"• Типы ЧС: {types}\n"
        f"• Шаблоны: {templates}\n"
        f"• Последних алертов: {len(alerts)}"
    )
    await message.answer(text, reply_markup=back_home_kb())


@router.callback_query(F.data == "nav:home")
async def cb_home(callback: CallbackQuery, storage) -> None:
    if not _admin_guard(callback, storage):
        await callback.answer("Нет доступа", show_alert=True)
        return
    await callback.answer()
    await _show_home(callback, storage)


@router.callback_query(F.data == "home:greeting")
async def menu_greeting(callback: CallbackQuery, storage) -> None:
    if not _admin_guard(callback, storage):
        await callback.answer("Нет доступа", show_alert=True)
        return
    text = storage.get_setting("staff_greeting")
    kb = items_kb("greeting", [], extra=[("✏️ Изменить приветствие", "greeting:edit")], back="nav:home")
    await callback.answer()
    await _safe_edit_message(callback.message, f"<b>Приветственное сообщение</b>\n\n{text}", reply_markup=kb)


@router.callback_query(F.data == "greeting:edit")
async def greeting_edit(callback: CallbackQuery, state: FSMContext, storage) -> None:
    if not _admin_guard(callback, storage):
        await callback.answer("Нет доступа", show_alert=True)
        return
    await state.set_state(GreetingState.waiting_text)
    await callback.answer()
    await _safe_edit_message(callback.message, "Отправьте новый текст приветствия одним сообщением.", reply_markup=back_home_kb())


@router.message(GreetingState.waiting_text)
async def greeting_save(message: Message, state: FSMContext, storage) -> None:
    if not _admin_guard(message, storage):
        await _deny(message)
        return
    storage.set_setting("staff_greeting", message.html_text)
    await state.clear()
    await message.answer("Приветствие обновлено.", reply_markup=home_kb())


@router.callback_query(F.data == "home:types")
async def menu_types(callback: CallbackQuery, storage) -> None:
    if not _admin_guard(callback, storage):
        await callback.answer("Нет доступа", show_alert=True)
        return
    rows = storage.list_emergency_types()
    items = [(f"📂 {r['name']}", f"type_open:{r['id']}") for r in rows]
    kb = items_kb("types", items, extra=[("➕ Добавить тип ЧС", "type:add")], back="nav:home")
    await callback.answer()
    await _safe_edit_message(callback.message, _types_text(storage), reply_markup=kb)


@router.callback_query(F.data == "type:add")
async def type_add_start(callback: CallbackQuery, state: FSMContext, storage) -> None:
    if not _admin_guard(callback, storage):
        await callback.answer("Нет доступа", show_alert=True)
        return
    await state.set_state(TypeState.waiting_name)
    await callback.answer()
    await _safe_edit_message(callback.message, "Введите название нового вида ЧС.", reply_markup=back_home_kb())


@router.message(TypeState.waiting_name)
async def type_add_name(message: Message, state: FSMContext, storage) -> None:
    if not _admin_guard(message, storage):
        await _deny(message)
        return
    await state.update_data(name=message.text.strip())
    await state.set_state(TypeState.waiting_description)
    await message.answer("Теперь отправьте описание этого вида ЧС.")


@router.message(TypeState.waiting_description)
async def type_add_desc(message: Message, state: FSMContext, storage) -> None:
    if not _admin_guard(message, storage):
        await _deny(message)
        return
    data = await state.get_data()
    storage.add_emergency_type(data["name"], message.text.strip())
    await state.clear()
    await message.answer("Вид ЧС добавлен.", reply_markup=home_kb())


@router.callback_query(F.data.startswith("type_open:"))
async def type_open(callback: CallbackQuery, storage) -> None:
    if not _admin_guard(callback, storage):
        await callback.answer("Нет доступа", show_alert=True)
        return
    type_id = int(callback.data.split(":", 1)[1])
    row = storage.get_emergency_type(type_id)
    if not row:
        await callback.answer("Тип не найден", show_alert=True)
        return
    levels = storage.list_danger_levels(type_id)
    text = (
        f"<b>{row['name']}</b>\n\n"
        f"{row['description'] or 'Без описания'}\n\n"
        f"Подуровней опасности: {len(levels)}"
    )
    kb = items_kb(
        "type",
        [],
        extra=[
            ("✏️ Изменить", f"type_edit:{type_id}"),
            ("➕ Добавить подуровень", f"level_add_for:{type_id}"),
            ("🗑 Удалить", f"type_delete:{type_id}"),
        ],
        back="home:types",
    )
    await callback.answer()
    await _safe_edit_message(callback.message, text, reply_markup=kb)


@router.callback_query(F.data.startswith("type_delete:"))
async def type_delete(callback: CallbackQuery, storage) -> None:
    if not _admin_guard(callback, storage):
        await callback.answer("Нет доступа", show_alert=True)
        return
    type_id = int(callback.data.split(":", 1)[1])
    storage.delete_emergency_type(type_id)
    await callback.answer("Удалено")
    await menu_types(callback, storage)


@router.callback_query(F.data.startswith("type_edit:"))
async def type_edit_start(callback: CallbackQuery, state: FSMContext, storage) -> None:
    if not _admin_guard(callback, storage):
        await callback.answer("Нет доступа", show_alert=True)
        return
    type_id = int(callback.data.split(":", 1)[1])
    row = storage.get_emergency_type(type_id)
    if not row:
        await callback.answer("Не найдено", show_alert=True)
        return
    await state.set_state(TypeState.editing_name)
    await state.update_data(type_id=type_id)
    await callback.answer()
    await _safe_edit_message(callback.message, f"Текущее название: <b>{row['name']}</b>\n\nОтправьте новое название.")


@router.message(TypeState.editing_name)
async def type_edit_name(message: Message, state: FSMContext, storage) -> None:
    await state.update_data(name=message.text.strip())
    await state.set_state(TypeState.editing_description)
    await message.answer("Теперь отправьте новое описание.")


@router.message(TypeState.editing_description)
async def type_edit_desc(message: Message, state: FSMContext, storage) -> None:
    data = await state.get_data()
    storage.update_emergency_type(int(data["type_id"]), data["name"], message.text.strip())
    await state.clear()
    await message.answer("Тип ЧС обновлён.", reply_markup=home_kb())


@router.callback_query(F.data == "home:levels")
async def menu_levels(callback: CallbackQuery, storage) -> None:
    if not _admin_guard(callback, storage):
        await callback.answer("Нет доступа", show_alert=True)
        return
    rows = storage.list_danger_levels()
    items = [(f"📌 {r['type_name']} → {r['name']}", f"level_open:{r['id']}") for r in rows]
    kb = items_kb("levels", items, extra=[("➕ Добавить подуровень", "level_add")], back="nav:home")
    text = "<b>Подуровни опасности</b>\n\n" + ("\n".join([f"• {r['type_name']} — {r['name']} (ранг {r['severity_rank']})" for r in rows]) if rows else "Пока пусто.")
    await callback.answer()
    await _safe_edit_message(callback.message, text, reply_markup=kb)


async def _ask_level_type(target: CallbackQuery | Message, storage):
    types = storage.list_emergency_types()
    kb = items_kb("lvltypes", [(r["name"], f"level_pick_type:{r['id']}") for r in types], back="home:levels")
    if isinstance(target, CallbackQuery):
        await target.message.edit_text("Выберите вид ЧС для подуровня.", reply_markup=kb)
    else:
        await target.answer("Выберите вид ЧС для подуровня.", reply_markup=kb)


@router.callback_query(F.data.in_({"level_add"}) | F.data.startswith("level_add_for:"))
async def level_add_start(callback: CallbackQuery, state: FSMContext, storage) -> None:
    if not _admin_guard(callback, storage):
        await callback.answer("Нет доступа", show_alert=True)
        return
    await state.clear()
    await state.set_state(LevelState.waiting_type)
    if callback.data.startswith("level_add_for:"):
        type_id = int(callback.data.split(":", 1)[1])
        await state.update_data(type_id=type_id)
        await state.set_state(LevelState.waiting_name)
        await callback.answer()
        await _safe_edit_message(callback.message, "Введите название подуровня опасности.")
        return
    await callback.answer()
    await _ask_level_type(callback, storage)


@router.callback_query(F.data.startswith("level_pick_type:"))
async def level_pick_type(callback: CallbackQuery, state: FSMContext, storage) -> None:
    await state.update_data(type_id=int(callback.data.split(":", 1)[1]))
    await state.set_state(LevelState.waiting_name)
    await callback.answer()
    await _safe_edit_message(callback.message, "Введите название подуровня опасности.")


@router.message(LevelState.waiting_name)
async def level_name(message: Message, state: FSMContext) -> None:
    await state.update_data(name=message.text.strip())
    await state.set_state(LevelState.waiting_description)
    await message.answer("Введите описание подуровня.")


@router.message(LevelState.waiting_description)
async def level_desc(message: Message, state: FSMContext) -> None:
    await state.update_data(description=message.text.strip())
    await state.set_state(LevelState.waiting_rank)
    await message.answer(
        "Введите числовой ранг серьёзности (от 1 до 5):\n\n"
        "1 — минимальный (зелёный)\n"
        "2 — низкий (жёлтый)\n"
        "3 — средний (оранжевый)\n"
        "4 — высокий (красный)\n"
        "5 — критический (тёмно-малиновый)"
    )


@router.message(LevelState.waiting_rank)
async def level_rank(message: Message, state: FSMContext, storage) -> None:
    data = await state.get_data()
    rank = int(message.text.strip())
    storage.add_danger_level(int(data["type_id"]), data["name"], data["description"], rank)
    await state.clear()
    await message.answer("Подуровень опасности добавлен.", reply_markup=home_kb())


@router.callback_query(F.data.startswith("level_open:"))
async def level_open(callback: CallbackQuery, storage) -> None:
    level_id = int(callback.data.split(":", 1)[1])
    row = storage.get_danger_level(level_id)
    if not row:
        await callback.answer("Не найдено", show_alert=True)
        return
    text = (
        f"<b>{row['name']}</b>\n"
        f"Тип ЧС: {row['type_name']}\n"
        f"Ранг: {row['severity_rank']}\n\n"
        f"{row['description'] or 'Без описания'}"
    )
    kb = items_kb(
        "level",
        [],
        extra=[
            ("🗑 Удалить", f"level_delete:{level_id}"),
        ],
        back="home:levels",
    )
    await callback.answer()
    await _safe_edit_message(callback.message, text, reply_markup=kb)


@router.callback_query(F.data.startswith("level_delete:"))
async def level_delete(callback: CallbackQuery, storage) -> None:
    storage.delete_danger_level(int(callback.data.split(":", 1)[1]))
    await callback.answer("Удалено")
    await menu_levels(callback, storage)


@router.callback_query(F.data == "home:templates")
async def menu_templates(callback: CallbackQuery, storage) -> None:
    rows = storage.list_templates()
    items = [(f"🧩 {r['title']}", f"tmpl_open:{r['id']}") for r in rows]
    kb = items_kb("tmpl", items, extra=[("➕ Новый шаблон", "tmpl:add")], back="nav:home")
    text = "<b>Шаблоны</b>\n\n" + ("\n".join([f"• {r['title']} — {r['type_name']}{' / ' + r['level_name'] if r['level_name'] else ''}" for r in rows]) if rows else "Пока нет шаблонов.")
    await callback.answer()
    await _safe_edit_message(callback.message, text, reply_markup=kb)


@router.callback_query(F.data == "tmpl:add")
async def template_add_start(callback: CallbackQuery, state: FSMContext, storage) -> None:
    await state.clear()
    await state.set_state(TemplateState.waiting_type)
    types = storage.list_emergency_types()
    kb = items_kb("tmpltypes", [(r["name"], f"tmpl_type:{r['id']}") for r in types], back="home:templates")
    await callback.answer()
    await _safe_edit_message(callback.message, "Выберите вид ЧС для шаблона.", reply_markup=kb)


@router.callback_query(F.data.startswith("tmpl_type:"))
async def template_pick_type(callback: CallbackQuery, state: FSMContext, storage) -> None:
    type_id = int(callback.data.split(":", 1)[1])
    await state.update_data(type_id=type_id)
    await state.set_state(TemplateState.waiting_level)
    await _show_level_picker(callback.message, type_id, storage, edit=True)
    await callback.answer()


async def _show_level_picker(message: Message, type_id: int, storage, edit: bool = False) -> None:
    levels = storage.list_danger_levels(type_id)
    items = [(r["name"], f"tmpl_level:{r['id']}") for r in levels]
    items.append(("Без привязки к подуровню", "tmpl_level:none"))
    items.append(("➕ Создать новый подуровень", f"tmpl_level_create:{type_id}"))
    kb = items_kb("tmpllvl", items, back="home:templates")
    text = "Выберите подуровень опасности или создайте новый."
    if edit:
        await _safe_edit_message(message, text, reply_markup=kb)
    else:
        await message.answer(text, reply_markup=kb)


@router.callback_query(F.data.startswith("tmpl_level_create:"))
async def template_level_create_start(callback: CallbackQuery, state: FSMContext) -> None:
    type_id = int(callback.data.split(":", 1)[1])
    await state.update_data(type_id=type_id)
    await state.set_state(TemplateState.creating_level_name)
    await callback.answer()
    await _safe_edit_message(callback.message, "Введите название нового подуровня опасности.\nНапример: Высокий, Средний, Критический")


@router.message(TemplateState.creating_level_name)
async def template_level_create_save(message: Message, state: FSMContext, storage) -> None:
    name = message.text.strip()
    data = await state.get_data()
    type_id = data["type_id"]
    storage.add_danger_level(type_id, name, "", 0)
    await state.set_state(TemplateState.waiting_level)
    await message.answer(f"Подуровень «{name}» создан.")
    await _show_level_picker(message, type_id, storage, edit=False)


@router.callback_query(F.data.startswith("tmpl_level:"))
async def template_pick_level(callback: CallbackQuery, state: FSMContext) -> None:
    raw = callback.data.split(":", 1)[1]
    await state.update_data(level_id=None if raw == "none" else int(raw), buttons=[], target_ids=[])
    await state.set_state(TemplateState.waiting_title)
    await callback.answer()
    await _safe_edit_message(callback.message, "Введите внутренний заголовок шаблона.")


@router.message(TemplateState.waiting_title)
async def template_title(message: Message, state: FSMContext) -> None:
    await state.update_data(title=message.text.strip())
    await state.set_state(TemplateState.waiting_body)
    await message.answer("Теперь отправьте основной текст шаблона.")


@router.message(TemplateState.waiting_body)
async def template_body(message: Message, state: FSMContext) -> None:
    await state.update_data(body=message.html_text)
    await state.set_state(TemplateState.waiting_media)
    await message.answer("Пришлите фото, видео или документ для шаблона. Если медиа не нужно — отправьте /skip.")


@router.message(Command("skip"), TemplateState.waiting_media)
async def template_media_skip(message: Message, state: FSMContext, storage) -> None:
    await _finalize_template(message, state, storage, "", "")


@router.message(TemplateState.waiting_media)
async def template_media(message: Message, state: FSMContext, storage) -> None:
    media_type = ""
    media_file_id = ""
    if message.photo:
        media_type = "photo"
        media_file_id = message.photo[-1].file_id
    elif message.video:
        media_type = "video"
        media_file_id = message.video.file_id
    elif message.document:
        media_type = "document"
        media_file_id = message.document.file_id
    else:
        await message.answer("Нужны фото, видео, документ или команда /skip.")
        return
    await _finalize_template(message, state, storage, media_type, media_file_id)


async def _finalize_template(message: Message, state: FSMContext, storage, media_type: str, media_file_id: str) -> None:
    data = await state.get_data()
    template_id = storage.add_template(
        int(data["type_id"]),
        data.get("level_id"),
        data["title"],
        data["body"],
        media_type,
        media_file_id,
        message.from_user.id if message.from_user else None,
    )
    await state.clear()
    await message.answer(
        "Шаблон создан. Теперь можно добавить кнопки и чаты по умолчанию.",
        reply_markup=template_manage_kb(template_id),
    )


@router.callback_query(F.data.startswith("tmpl_open:"))
async def template_open(callback: CallbackQuery, storage) -> None:
    template_id = int(callback.data.split(":", 1)[1])
    await callback.answer()
    await _render_template_open(callback.message, template_id, storage)


@router.callback_query(F.data.startswith("tmpl_delete:"))
async def template_delete(callback: CallbackQuery, storage) -> None:
    storage.delete_template(int(callback.data.split(":", 1)[1]))
    await callback.answer("Удалено")
    await menu_templates(callback, storage)


@router.callback_query(F.data.startswith("tmpl_edit_title:"))
async def template_edit_title_start(callback: CallbackQuery, state: FSMContext, storage) -> None:
    if not _admin_guard(callback, storage):
        await callback.answer("Нет доступа", show_alert=True)
        return
    template_id = int(callback.data.split(":", 1)[1])
    row = storage.get_template(template_id)
    if not row:
        await callback.answer("Шаблон не найден", show_alert=True)
        return
    await state.set_state(TemplateState.editing_title)
    await state.update_data(template_id=template_id)
    await callback.answer()
    await _safe_edit_message(callback.message, f"Текущий заголовок: <b>{row['title']}</b>\n\nОтправьте новый заголовок:")


@router.message(TemplateState.editing_title)
async def template_edit_title_save(message: Message, state: FSMContext, storage) -> None:
    if not _admin_guard(message, storage):
        await _deny(message)
        return
    data = await state.get_data()
    template_id = int(data["template_id"])
    storage.execute(
        "UPDATE templates SET title = ?, updated_at = ? WHERE id = ?",
        (message.text.strip(), storage.now(), template_id),
    )
    await state.clear()
    await message.answer("Заголовок обновлён.", reply_markup=template_manage_kb(template_id))


@router.callback_query(F.data.startswith("tmpl_edit_body:"))
async def template_edit_body_start(callback: CallbackQuery, state: FSMContext, storage) -> None:
    if not _admin_guard(callback, storage):
        await callback.answer("Нет доступа", show_alert=True)
        return
    template_id = int(callback.data.split(":", 1)[1])
    row = storage.get_template(template_id)
    if not row:
        await callback.answer("Шаблон не найден", show_alert=True)
        return
    await state.set_state(TemplateState.editing_body)
    await state.update_data(template_id=template_id)
    await callback.answer()
    await _safe_edit_message(
        callback.message,
        f"Текущий текст:\n<blockquote>{row['body'][:300]}</blockquote>\n\nОтправьте новый текст шаблона:",
    )


@router.message(TemplateState.editing_body)
async def template_edit_body_save(message: Message, state: FSMContext, storage) -> None:
    if not _admin_guard(message, storage):
        await _deny(message)
        return
    data = await state.get_data()
    template_id = int(data["template_id"])
    storage.execute(
        "UPDATE templates SET body = ?, updated_at = ? WHERE id = ?",
        (message.html_text, storage.now(), template_id),
    )
    await state.clear()
    await message.answer("Текст шаблона обновлён.", reply_markup=template_manage_kb(template_id))


@router.callback_query(F.data.startswith("tmpl_edit_media:"))
async def template_edit_media_start(callback: CallbackQuery, state: FSMContext, storage) -> None:
    if not _admin_guard(callback, storage):
        await callback.answer("Нет доступа", show_alert=True)
        return
    template_id = int(callback.data.split(":", 1)[1])
    await state.set_state(TemplateState.editing_media)
    await state.update_data(template_id=template_id)
    await callback.answer()
    await _safe_edit_message(
        callback.message,
        "Пришлите новое фото, видео или документ для шаблона.\nЧтобы убрать медиа — отправьте /skip.",
    )


@router.message(Command("skip"), TemplateState.editing_media)
async def template_edit_media_skip(message: Message, state: FSMContext, storage) -> None:
    data = await state.get_data()
    template_id = int(data["template_id"])
    storage.execute(
        "UPDATE templates SET media_type = '', media_file_id = '', updated_at = ? WHERE id = ?",
        (storage.now(), template_id),
    )
    await state.clear()
    await message.answer("Медиа удалено.", reply_markup=template_manage_kb(template_id))


@router.message(TemplateState.editing_media)
async def template_edit_media_save(message: Message, state: FSMContext, storage) -> None:
    if not _admin_guard(message, storage):
        await _deny(message)
        return
    media_type = ""
    media_file_id = ""
    if message.photo:
        media_type = "photo"
        media_file_id = message.photo[-1].file_id
    elif message.video:
        media_type = "video"
        media_file_id = message.video.file_id
    elif message.document:
        media_type = "document"
        media_file_id = message.document.file_id
    else:
        await message.answer("Нужно отправить фото, видео, документ или /skip.")
        return
    data = await state.get_data()
    template_id = int(data["template_id"])
    storage.execute(
        "UPDATE templates SET media_type = ?, media_file_id = ?, updated_at = ? WHERE id = ?",
        (media_type, media_file_id, storage.now(), template_id),
    )
    await state.clear()
    await message.answer("Медиа шаблона обновлено.", reply_markup=template_manage_kb(template_id))


@router.callback_query(F.data.startswith("tmpl_buttons:"))
async def template_buttons(callback: CallbackQuery, storage) -> None:
    template_id = int(callback.data.split(":", 1)[1])
    await callback.answer()
    await _render_template_buttons(callback.message, template_id, storage)


@router.callback_query(F.data.startswith("tmpl_button_add:"))
async def button_add_start(callback: CallbackQuery, state: FSMContext) -> None:
    template_id = int(callback.data.split(":", 1)[1])
    await state.set_state(TemplateState.waiting_button_text)
    await state.update_data(template_id=template_id)
    await callback.answer()
    await _safe_edit_message(callback.message, "Введите текст кнопки.")


@router.message(TemplateState.waiting_button_text)
async def button_add_text(message: Message, state: FSMContext) -> None:
    await state.update_data(button_text=message.text.strip())
    await state.set_state(TemplateState.waiting_button_url)
    await message.answer("Теперь отправьте URL для этой кнопки.")


@router.message(TemplateState.waiting_button_url)
async def button_add_url(message: Message, state: FSMContext, storage) -> None:
    url = message.text.strip()
    if url and not url.startswith(("http://", "https://", "tg://")):
        url = "https://" + url
    data = await state.get_data()
    storage.add_template_button(int(data["template_id"]), data["button_text"], url)
    template_id = int(data["template_id"])
    await state.clear()
    await message.answer("Кнопка добавлена.", reply_markup=template_manage_kb(template_id))


@router.callback_query(F.data.startswith("tmpl_button_del:"))
async def button_delete(callback: CallbackQuery, storage) -> None:
    _, template_id, button_id = callback.data.split(":")
    storage.delete_template_button(int(button_id))
    await callback.answer("Кнопка удалена")
    await _render_template_buttons(callback.message, int(template_id), storage)


@router.callback_query(F.data.startswith("tmpl_targets:"))
async def template_targets(callback: CallbackQuery, state: FSMContext, storage) -> None:
    template_id = int(callback.data.split(":", 1)[1])
    selected = set(storage.list_template_target_ids(template_id))
    await state.set_state(TemplateState.waiting_targets)
    await state.update_data(template_id=template_id, selected_targets=list(selected))
    chats = storage.list_chats(active_only=True)
    values = [(c["title"], str(c["chat_id"]), int(c["chat_id"]) in selected) for c in chats]
    await callback.answer()
    await _safe_edit_message(callback.message, 
        "Выберите чаты по умолчанию для этого шаблона.",
        reply_markup=toggles_kb("tmpl_target_toggle", values, "tmpl_target_done", f"tmpl_open:{template_id}"),
    )


@router.callback_query(F.data.startswith("tmpl_target_toggle:"), TemplateState.waiting_targets)
async def template_target_toggle(callback: CallbackQuery, state: FSMContext, storage) -> None:
    chat_id = int(callback.data.split(":", 1)[1])
    data = await state.get_data()
    selected = set(data.get("selected_targets", []))
    if chat_id in selected:
        selected.remove(chat_id)
    else:
        selected.add(chat_id)
    await state.update_data(selected_targets=list(selected))
    template_id = int(data["template_id"])
    chats = storage.list_chats(active_only=True)
    values = [(c["title"], str(c["chat_id"]), int(c["chat_id"]) in selected) for c in chats]
    await callback.answer()
    await callback.message.edit_reply_markup(
        reply_markup=toggles_kb("tmpl_target_toggle", values, "tmpl_target_done", f"tmpl_open:{template_id}")
    )


@router.callback_query(F.data == "tmpl_target_done", TemplateState.waiting_targets)
async def template_target_done(callback: CallbackQuery, state: FSMContext, storage) -> None:
    data = await state.get_data()
    template_id = int(data["template_id"])
    selected = [int(x) for x in data.get("selected_targets", [])]
    storage.replace_template_targets(template_id, selected)
    await state.clear()
    await callback.answer("Сохранено")
    await _render_template_open(callback.message, template_id, storage)


@router.callback_query(F.data == "home:chats")
async def menu_chats(callback: CallbackQuery, storage) -> None:
    rows = storage.list_chats()
    items = [(f"{'🟢' if r['is_active'] else '⚪️'} {r['title']}", f"chat_open:{r['chat_id']}") for r in rows]
    kb = items_kb("chats", items, back="nav:home")
    text = "<b>Чаты и каналы</b>\n\n" + ("\n".join([f"• {'активен' if r['is_active'] else 'отключён'} — {r['title']} ({r['chat_type']})" for r in rows]) if rows else "Пока бот никуда не добавлен.")
    await callback.answer()
    await _safe_edit_message(callback.message, text, reply_markup=kb)


@router.callback_query(F.data.startswith("chat_open:"))
async def chat_open(callback: CallbackQuery, storage) -> None:
    chat_id = int(callback.data.split(":", 1)[1])
    await callback.answer()
    await _render_chat_open(callback.message, chat_id, storage)


@router.callback_query(F.data.startswith("chat_toggle:"))
async def chat_toggle(callback: CallbackQuery, storage) -> None:
    chat_id = int(callback.data.split(":", 1)[1])
    row = storage.get_chat(chat_id)
    if not row:
        await callback.answer("Чат не найден", show_alert=True)
        return
    storage.set_chat_active(chat_id, not bool(row['is_active']))
    await callback.answer("Статус изменён")
    await _render_chat_open(callback.message, chat_id, storage)


@router.callback_query(F.data.startswith("chat_notes:"))
async def chat_notes_start(callback: CallbackQuery, state: FSMContext) -> None:
    chat_id = int(callback.data.split(":", 1)[1])
    await state.set_state(ChatState.editing_notes)
    await state.update_data(chat_id=chat_id)
    await callback.answer()
    await _safe_edit_message(callback.message, "Отправьте новое примечание для этого чата.")


@router.message(ChatState.editing_notes)
async def chat_notes_save(message: Message, state: FSMContext, storage) -> None:
    data = await state.get_data()
    chat_id = int(data["chat_id"])
    storage.update_chat_notes(chat_id, message.text.strip())
    await state.clear()
    await message.answer("Примечание обновлено.", reply_markup=home_kb())


@router.callback_query(F.data.startswith("chat_delete:"))
async def chat_delete(callback: CallbackQuery, storage) -> None:
    chat_id = int(callback.data.split(":", 1)[1])
    storage.delete_managed_chat(chat_id)
    if storage.get_moderator_chat_id() == chat_id:
        storage.set_setting("moderator_chat_id", "")
    await callback.answer("Чат удалён из системы")
    await menu_chats(callback, storage)


@router.callback_query(F.data == "home:moderation")
async def menu_moderation(callback: CallbackQuery, storage, config) -> None:
    admins = storage.list_admins()
    selected_chat_id = storage.get_moderator_chat_id() or config.moderator_chat_id
    chats = [(int(r["chat_id"]), str(r["title"])) for r in storage.list_chats()]
    admin_lines = [f"• <code>{r['telegram_id']}</code> — {r['full_name'] or r['username'] or 'без имени'} ({r['role']})" for r in admins]
    text = (
        "<b>Модерация и доступ</b>\n\n"
        f"Текущий чат модерации: <code>{selected_chat_id or 'не выбран'}</code>\n\n"
        "<b>Администраторы</b>\n"
        + ("\n".join(admin_lines) if admin_lines else "Пока нет администраторов")
        + "\n\nНиже можно выбрать чат модерации и управлять локальными администраторами. "
          "Если подключён PostgreSQL, пользователи из таблицы <code>bot_admins</code> также смогут входить в бота."
    )
    kb = moderation_chat_kb(chats, selected_chat_id)
    await callback.answer()
    await _safe_edit_message(callback.message, text, reply_markup=kb)


@router.callback_query(F.data.startswith("moder_chat_set:"))
async def moderation_chat_set(callback: CallbackQuery, storage, config) -> None:
    chat_id = int(callback.data.split(":", 1)[1])
    storage.set_moderator_chat_id(chat_id)
    await callback.answer("Чат модерации обновлён")
    await menu_moderation(callback, storage, config)


@router.callback_query(F.data == "admin_add")
async def admin_add_start(callback: CallbackQuery, state: FSMContext, storage) -> None:
    if not _admin_guard(callback, storage):
        await callback.answer("Нет доступа", show_alert=True)
        return
    await state.set_state(AdminState.waiting_admin_id)
    await callback.answer()
    await _safe_edit_message(callback.message, "Отправьте Telegram ID нового администратора. Можно просто числом.")


@router.message(AdminState.waiting_admin_id)
async def admin_add_save(message: Message, state: FSMContext, storage) -> None:
    raw = (message.text or "").strip()
    try:
        admin_id = int(raw)
    except ValueError:
        await message.answer("Нужен числовой Telegram ID.")
        return
    storage.upsert_admin(admin_id)
    await state.clear()
    await message.answer("Администратор добавлен локально.", reply_markup=home_kb())


@router.callback_query(F.data.startswith("admin_del:"))
async def admin_delete(callback: CallbackQuery, storage, config) -> None:
    admin_id = int(callback.data.split(":", 1)[1])
    if admin_id == callback.from_user.id:
        await callback.answer("Нельзя удалить самого себя из текущей сессии", show_alert=True)
        return
    storage.delete_admin(admin_id)
    await callback.answer("Администратор удалён")
    await menu_moderation(callback, storage, config)


@router.callback_query(F.data == "admin_manage")
async def admin_manage(callback: CallbackQuery, storage) -> None:
    rows = storage.list_admins()
    items = [(int(r["telegram_id"]), f"{r['full_name'] or r['username'] or r['telegram_id']} ({r['role']})") for r in rows]
    text = "<b>Удаление локальных администраторов</b>\n\nНажмите на администратора, которого нужно удалить из локальной БД бота."
    await callback.answer()
    await _safe_edit_message(callback.message, text, reply_markup=admin_manage_kb(items, callback.from_user.id))


@router.callback_query(F.data == "home:dispatch")
async def menu_dispatch(callback: CallbackQuery, storage) -> None:
    rows = storage.list_templates()
    items = [(f"📣 {r['title']}", f"dispatch_from_template:{r['id']}") for r in rows]
    kb = items_kb("dispatch", items, back="nav:home")
    await callback.answer()
    await _safe_edit_message(callback.message, "Выберите шаблон для создания рассылки.", reply_markup=kb)


async def _load_dispatch_draft(template_id: int, storage) -> dict | None:
    row = storage.get_template(template_id)
    if not row:
        return None
    buttons = [{"text": b["text"], "url": b["url"]} for b in storage.list_template_buttons(template_id)]
    targets = storage.list_template_target_ids(template_id)
    return {
        "template_id": template_id,
        "title": row["title"],
        "text": row["body"],
        "media_type": row["media_type"],
        "media_file_id": row["media_file_id"],
        "buttons": buttons,
        "target_ids": targets,
        "emergency_type_id": row["emergency_type_id"],
        "danger_level_id": row["danger_level_id"],
        "emergency_type_name": row["type_name"],
        "danger_level_name": row["level_name"],
    }


async def _show_dispatch_preview(callback: CallbackQuery | Message, state: FSMContext) -> None:
    data = await state.get_data()
    text = (
        f"<b>Черновик рассылки</b>\n"
        f"Шаблон: {data.get('title', '—')}\n"
        f"Чатов выбрано: {len(data.get('target_ids', []))}\n"
        f"Медиа: {data.get('media_type') or 'нет'}\n"
        f"Кнопок: {len(data.get('buttons', []))}\n\n"
        f"{data.get('text', '')}"
    )
    if isinstance(callback, CallbackQuery):
        await _safe_edit_message(callback.message, text, reply_markup=dispatch_preview_kb())
    else:
        await callback.answer(text, reply_markup=dispatch_preview_kb())


@router.callback_query(F.data.startswith("dispatch_from_template:"))
async def dispatch_from_template(callback: CallbackQuery, state: FSMContext, storage) -> None:
    template_id = int(callback.data.split(":", 1)[1])
    draft = await _load_dispatch_draft(template_id, storage)
    if not draft:
        await callback.answer("Шаблон не найден", show_alert=True)
        return
    await state.set_state(DispatchState.choosing_template)
    await state.set_data(draft)
    await callback.answer()
    await _show_dispatch_preview(callback, state)


@router.callback_query(F.data == "dispatch:edit_text", DispatchState.choosing_template)
async def dispatch_edit_text_start(callback: CallbackQuery, state: FSMContext) -> None:
    await state.set_state(DispatchState.editing_text)
    await callback.answer()
    await _safe_edit_message(callback.message, "Отправьте новый текст рассылки одним сообщением.")


@router.message(DispatchState.editing_text)
async def dispatch_edit_text_save(message: Message, state: FSMContext) -> None:
    await state.update_data(text=message.html_text)
    await state.set_state(DispatchState.choosing_template)
    await message.answer("Текст обновлён.", reply_markup=dispatch_preview_kb())


@router.callback_query(F.data == "dispatch:media", DispatchState.choosing_template)
async def dispatch_media_start(callback: CallbackQuery, state: FSMContext) -> None:
    await state.set_state(DispatchState.waiting_media)
    await callback.answer()
    await _safe_edit_message(callback.message, "Пришлите фото, видео или документ для этой рассылки. Чтобы убрать медиа, отправьте /skip.")


@router.message(Command("skip"), DispatchState.waiting_media)
async def dispatch_media_skip(message: Message, state: FSMContext) -> None:
    await state.update_data(media_type="", media_file_id="")
    await state.set_state(DispatchState.choosing_template)
    await message.answer("Медиа убрано.", reply_markup=dispatch_preview_kb())


@router.message(DispatchState.waiting_media)
async def dispatch_media_save(message: Message, state: FSMContext) -> None:
    media_type = ""
    media_file_id = ""
    if message.photo:
        media_type = "photo"
        media_file_id = message.photo[-1].file_id
    elif message.video:
        media_type = "video"
        media_file_id = message.video.file_id
    elif message.document:
        media_type = "document"
        media_file_id = message.document.file_id
    else:
        await message.answer("Нужно отправить фото, видео, документ или /skip.")
        return
    await state.update_data(media_type=media_type, media_file_id=media_file_id)
    await state.set_state(DispatchState.choosing_template)
    await message.answer("Медиа обновлено.", reply_markup=dispatch_preview_kb())


@router.callback_query(F.data == "dispatch:targets", DispatchState.choosing_template)
async def dispatch_targets_start(callback: CallbackQuery, state: FSMContext, storage) -> None:
    data = await state.get_data()
    selected = set(data.get("target_ids", []))
    await state.set_state(DispatchState.choosing_targets)
    chats = storage.list_chats(active_only=True)
    values = [(c["title"], str(c["chat_id"]), int(c["chat_id"]) in selected) for c in chats]
    await callback.answer()
    await _safe_edit_message(callback.message,
        "Отметьте чаты и каналы для отправки.",
        reply_markup=toggles_kb("dispatch_target_toggle", values, "dispatch_target_done", "dispatch_back_preview", select_all_cb="dispatch_select_all"),
    )


@router.callback_query(F.data.startswith("dispatch_target_toggle:"), DispatchState.choosing_targets)
async def dispatch_target_toggle(callback: CallbackQuery, state: FSMContext, storage) -> None:
    chat_id = int(callback.data.split(":", 1)[1])
    data = await state.get_data()
    selected = set(data.get("target_ids", []))
    if chat_id in selected:
        selected.remove(chat_id)
    else:
        selected.add(chat_id)
    await state.update_data(target_ids=list(selected))
    chats = storage.list_chats(active_only=True)
    values = [(c["title"], str(c["chat_id"]), int(c["chat_id"]) in selected) for c in chats]
    await callback.answer()
    await callback.message.edit_reply_markup(reply_markup=toggles_kb("dispatch_target_toggle", values, "dispatch_target_done", "dispatch_back_preview", select_all_cb="dispatch_select_all"))


@router.callback_query(F.data == "dispatch_select_all", DispatchState.choosing_targets)
async def dispatch_select_all(callback: CallbackQuery, state: FSMContext, storage) -> None:
    data = await state.get_data()
    chats = storage.list_chats(active_only=True)
    selected = set(data.get("target_ids", []))
    all_ids = {int(c["chat_id"]) for c in chats}
    # Если все выбраны — снимаем все, иначе выбираем все
    if all_ids == selected:
        selected = set()
    else:
        selected = all_ids
    await state.update_data(target_ids=list(selected))
    values = [(c["title"], str(c["chat_id"]), int(c["chat_id"]) in selected) for c in chats]
    await callback.answer()
    await callback.message.edit_reply_markup(
        reply_markup=toggles_kb("dispatch_target_toggle", values, "dispatch_target_done", "dispatch_back_preview", select_all_cb="dispatch_select_all")
    )


@router.callback_query(F.data == "dispatch_target_done", DispatchState.choosing_targets)
async def dispatch_target_done(callback: CallbackQuery, state: FSMContext) -> None:
    await state.set_state(DispatchState.choosing_template)
    await callback.answer("Чаты сохранены")
    await _show_dispatch_preview(callback, state)


@router.callback_query(F.data == "dispatch_back_preview", DispatchState.choosing_targets)
async def dispatch_back_preview(callback: CallbackQuery, state: FSMContext) -> None:
    await state.set_state(DispatchState.choosing_template)
    await callback.answer()
    await _show_dispatch_preview(callback, state)


@router.callback_query(F.data == "dispatch:ai", DispatchState.choosing_template)
async def dispatch_ai(callback: CallbackQuery, state: FSMContext, ai_writer) -> None:
    data = await state.get_data()
    improved = await ai_writer.improve_dispatch(
        data.get("title", ""),
        data.get("text", ""),
        data.get("emergency_type_name"),
        data.get("danger_level_name"),
    )
    await state.update_data(text=improved)
    await callback.answer("Текст обновлён ИИ")
    await _show_dispatch_preview(callback, state)


@router.callback_query(F.data == "dispatch:send", DispatchState.choosing_template)
async def dispatch_send(callback: CallbackQuery, state: FSMContext, storage, bot, pg_sync=None) -> None:
    data = await state.get_data()
    target_ids = [int(x) for x in data.get("target_ids", [])]
    if not target_ids:
        await callback.answer("Сначала выберите хотя бы один чат", show_alert=True)
        return
    dispatch_id = storage.create_dispatch(
        data.get("template_id"),
        data.get("emergency_type_id"),
        data.get("danger_level_id"),
        data.get("title", ""),
        data.get("text", ""),
        data.get("media_type", ""),
        data.get("media_file_id", ""),
        data.get("buttons", []),
        callback.from_user.id,
    )
    sent = 0
    failed = 0
    for chat_id in target_ids:
        chat_row = storage.get_chat(chat_id)
        title = chat_row["title"] if chat_row else str(chat_id)
        try:
            await send_rich_message(bot, chat_id, data.get("text", ""), data.get("media_type", ""), data.get("media_file_id", ""), data.get("buttons", []))
            storage.add_dispatch_target(dispatch_id, chat_id, title, "sent")
            sent += 1
            if pg_sync and pg_sync.enabled:
                await pg_sync.log_dispatch("bot", data.get("emergency_type_name"), chat_id, title, data.get("text", ""), str(callback.from_user.id))
        except Exception as exc:
            storage.add_dispatch_target(dispatch_id, chat_id, title, "failed", str(exc))
            failed += 1
    if failed == 0:
        storage.mark_dispatch_sent(dispatch_id, "sent")
    else:
        storage.mark_dispatch_sent(dispatch_id, "partial" if sent else "failed", f"Ошибок: {failed}")
    await state.clear()
    await callback.answer()
    await _safe_edit_message(callback.message, 
        f"Рассылка завершена.\n\nУспешно: {sent}\nОшибок: {failed}\nID рассылки: {dispatch_id}",
        reply_markup=home_kb(),
    )


@router.callback_query(F.data == "dispatch:cancel")
async def dispatch_cancel(callback: CallbackQuery, state: FSMContext) -> None:
    await state.clear()
    await callback.answer("Отменено")
    await _safe_edit_message(callback.message, "Черновик рассылки удалён.", reply_markup=home_kb())


@router.callback_query(F.data == "home:report")
async def menu_report(callback: CallbackQuery, state: FSMContext) -> None:
    await state.set_state(ReportState.waiting_period)
    await callback.answer()
    await _safe_edit_message(callback.message,
        "Отправьте период в формате <code>ГГГГ-ММ-ДД ГГГГ-ММ-ДД</code>.\n"
        "Например: <code>2026-03-01 2026-03-31</code>\n\n"
        "Или напишите <code>all</code> чтобы скачать весь лог.",
        reply_markup=back_home_kb(),
    )


@router.message(ReportState.waiting_period)
async def report_build(message: Message, state: FSMContext, pg_sync, storage) -> None:
    raw = (message.text or "").strip()
    date_from = None
    date_to = None
    if raw.lower() != "all":
        parts = raw.split()
        if len(parts) != 2:
            await message.answer("Неверный формат. Нужно: ГГГГ-ММ-ДД ГГГГ-ММ-ДД  или  all")
            return
        date_from, date_to = parts[0], parts[1]

    if pg_sync and pg_sync.enabled:
        rows = await pg_sync.fetch_dispatch_log(date_from, date_to)
        path = build_dispatch_report_from_pg(rows, "reports/dispatch_report.xlsx")
        await state.clear()
        caption = f"Единый отчёт (бот + веб-портал). Строк: {len(rows)}"
        if not rows:
            caption = "Записей за указанный период не найдено в общем логе."
        await message.answer_document(FSInputFile(path), caption=caption, reply_markup=home_kb())
    else:
        # Fallback: отчёт из локальной SQLite-базы бота
        from datetime import datetime, timezone
        if date_from and date_to:
            start_iso = date_from + "T00:00:00"
            end_iso = date_to + "T23:59:59"
        else:
            start_iso = "2000-01-01T00:00:00"
            end_iso = "2099-12-31T23:59:59"
        sqlite_rows = storage.list_dispatches_between(start_iso, end_iso)
        # Convert SQLite rows to dispatch_log format for the report builder
        converted = []
        for r in sqlite_rows:
            converted.append({
                "id": r["id"],
                "source": "bot",
                "emergency_type": None,
                "chat_name": "—",
                "chat_id": None,
                "sent_by": str(r["created_by"]),
                "sent_at": r["sent_at"] or r["created_at"],
                "message_text": r["final_text"],
            })
        path = build_dispatch_report_from_pg(converted, "reports/dispatch_report.xlsx")
        await state.clear()
        caption = f"Отчёт из локальной БД бота. Строк: {len(converted)}\n⚠️ Для объединённого отчёта (бот + веб) настройте POSTGRES_DSN."
        if not converted:
            caption = "Рассылок за указанный период не найдено.\n⚠️ Для объединённого отчёта настройте POSTGRES_DSN."
        await message.answer_document(FSInputFile(path), caption=caption, reply_markup=home_kb())


@router.callback_query(F.data == "home:map")
async def menu_map(callback: CallbackQuery, state: FSMContext, storage) -> None:
    if not _admin_guard(callback, storage):
        await callback.answer("Нет доступа", show_alert=True)
        return
    await state.set_state(MapIncidentState.waiting_title)
    await callback.answer()
    await _safe_edit_message(
        callback.message,
        "📍 <b>Добавить метку на карту ЧС</b>\n\n"
        "Введите название инцидента (например: <i>Пожар на ул. Центральной</i>):",
        reply_markup=back_home_kb(),
    )


@router.message(MapIncidentState.waiting_title)
async def map_incident_title(message: Message, state: FSMContext, storage) -> None:
    if not _admin_guard(message, storage):
        await _deny(message)
        return
    await state.update_data(title=message.text.strip())
    await state.set_state(MapIncidentState.waiting_description)
    await message.answer(
        "Введите описание инцидента (или отправьте /skip чтобы пропустить):",
        reply_markup=back_home_kb(),
    )


@router.message(Command("skip"), MapIncidentState.waiting_description)
async def map_incident_desc_skip(message: Message, state: FSMContext) -> None:
    await state.update_data(description="")
    await state.set_state(MapIncidentState.waiting_coords)
    await message.answer(
        "Отправьте координаты через пробел: <code>широта долгота</code>\n"
        "Например: <code>55.7525 48.7442</code>\n\n"
        "Подсказка: откройте maps.google.com, нажмите на нужную точку — координаты появятся внизу.",
        reply_markup=back_home_kb(),
    )


@router.message(MapIncidentState.waiting_description)
async def map_incident_desc(message: Message, state: FSMContext) -> None:
    await state.update_data(description=message.text.strip())
    await state.set_state(MapIncidentState.waiting_coords)
    await message.answer(
        "Отправьте координаты через пробел: <code>широта долгота</code>\n"
        "Например: <code>55.7525 48.7442</code>",
        reply_markup=back_home_kb(),
    )


@router.message(MapIncidentState.waiting_coords)
async def map_incident_coords(message: Message, state: FSMContext, pg_sync) -> None:
    parts = (message.text or "").strip().replace(",", ".").split()
    if len(parts) != 2:
        await message.answer("Неверный формат. Нужно: широта долгота  (два числа через пробел)")
        return
    try:
        lat = float(parts[0])
        lon = float(parts[1])
    except ValueError:
        await message.answer("Координаты должны быть числами. Попробуйте ещё раз.")
        return
    await state.update_data(lat=lat, lon=lon)
    await state.set_state(MapIncidentState.waiting_type)

    # Загружаем виды ЧС из PostgreSQL
    types = await pg_sync.fetch_emergency_types()
    if types:
        from aiogram.utils.keyboard import InlineKeyboardBuilder
        builder = InlineKeyboardBuilder()
        for t in types:
            builder.button(text=t["name"], callback_data=f"map_type:{t['id']}")
        builder.button(text="Без привязки к типу", callback_data="map_type:none")
        builder.button(text="⬅️ В главное меню", callback_data="nav:home")
        builder.adjust(1)
        await message.answer("Выберите вид ЧС:", reply_markup=builder.as_markup())
    else:
        await state.update_data(emergency_type_id=None)
        data = await state.get_data()
        await _save_map_incident(message, state, pg_sync, data)


@router.callback_query(F.data.startswith("map_type:"))
async def map_incident_type(callback: CallbackQuery, state: FSMContext, pg_sync) -> None:
    raw = callback.data.split(":", 1)[1]
    type_id = None if raw == "none" else int(raw)
    await state.update_data(emergency_type_id=type_id)
    data = await state.get_data()
    await callback.answer()
    await _save_map_incident(callback.message, state, pg_sync, data)


async def _save_map_incident(message: Message, state: FSMContext, pg_sync, data: dict) -> None:
    ok = await pg_sync.add_map_incident(
        title=data["title"],
        description=data.get("description", ""),
        lat=data["lat"],
        lon=data["lon"],
        emergency_type_id=data.get("emergency_type_id"),
    )
    await state.clear()
    if ok:
        await message.answer(
            f"✅ Метка <b>{data['title']}</b> добавлена на карту ЧС.\n"
            f"Координаты: {data['lat']:.5f}, {data['lon']:.5f}",
            reply_markup=home_kb(),
        )
    else:
        await message.answer(
            "Не удалось добавить метку — проверьте подключение к базе данных.",
            reply_markup=home_kb(),
        )


@router.callback_query(F.data == "home:monitor")
async def menu_monitor(callback: CallbackQuery, storage, pg_sync) -> None:
    await callback.answer()
    # Пытаемся получить активные инциденты с карты ЧС из PostgreSQL
    map_incidents = []
    if pg_sync and pg_sync.enabled:
        map_incidents = await pg_sync.fetch_active_map_incidents(limit=10)

    if map_incidents:
        lines = [f"<b>🗺 Активные инциденты на карте ЧС</b> ({len(map_incidents)})\n"]
        for inc in map_incidents:
            dot = "🔴" if inc.get("danger_color") else "🟠"
            type_label = inc.get("emergency_type_name") or ""
            level_label = inc.get("danger_level_name") or ""
            meta = " · ".join(filter(None, [type_label, level_label]))
            lines.append(f"{dot} <b>{inc['title']}</b>")
            if meta:
                lines.append(f"   {meta}")
        text = "\n".join(lines)
    else:
        # Fallback: SQLite alerts
        alerts = storage.list_recent_alerts(5)
        if alerts:
            lines = [f"<b>Последние алерты мониторинга</b>\n"]
            for a in alerts:
                lines.append(f"• {a['title']}")
            text = "\n".join(lines)
        else:
            text = "<b>Мониторинг</b>\n\nАктивных инцидентов нет.\n\nДобавьте инциденты через <b>Карта ЧС</b> или веб-портал."

    await _safe_edit_message(callback.message, text, reply_markup=back_home_kb())


@router.callback_query(F.data == "home:status")
async def menu_status(callback: CallbackQuery, storage, config) -> None:
    user = callback.from_user
    text = (
        f"<b>Служебная информация</b>\n"
        f"Ваш user_id: <code>{user.id}</code>\n"
        f"Модераторский чат: <code>{storage.get_moderator_chat_id() or config.moderator_chat_id or 'не выбран'}</code>\n"
        f"Город: {config.city_name}\n"
        f"Активных чатов: {len(storage.list_chats(active_only=True))}"
    )
    await callback.answer()
    await _safe_edit_message(callback.message, text, reply_markup=back_home_kb())
