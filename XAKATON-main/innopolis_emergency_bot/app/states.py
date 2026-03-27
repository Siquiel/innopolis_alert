from __future__ import annotations

from aiogram.fsm.state import State, StatesGroup


class GreetingState(StatesGroup):
    waiting_text = State()


class TypeState(StatesGroup):
    waiting_name = State()
    waiting_description = State()
    editing_name = State()
    editing_description = State()


class LevelState(StatesGroup):
    waiting_type = State()
    waiting_name = State()
    waiting_description = State()
    waiting_rank = State()
    editing_name = State()
    editing_description = State()
    editing_rank = State()


class TemplateState(StatesGroup):
    waiting_type = State()
    waiting_level = State()
    creating_level_name = State()
    waiting_title = State()
    waiting_body = State()
    waiting_media = State()
    waiting_button_text = State()
    waiting_button_url = State()
    waiting_targets = State()
    editing_title = State()
    editing_body = State()
    editing_media = State()


class DispatchState(StatesGroup):
    choosing_template = State()
    editing_text = State()
    waiting_media = State()
    choosing_targets = State()
    waiting_ai_prompt = State()


class ChatState(StatesGroup):
    editing_notes = State()


class ReportState(StatesGroup):
    waiting_period = State()


class AdminState(StatesGroup):
    waiting_admin_id = State()


class MapIncidentState(StatesGroup):
    waiting_title = State()
    waiting_description = State()
    waiting_coords = State()
    waiting_type = State()
