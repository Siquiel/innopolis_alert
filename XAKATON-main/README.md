# XAKATON
# InnoAlert — бот локального оповещения

Что умеет сейчас:
- личный чат с ботом как админ-панель;
- автопривязка групп и каналов, куда добавили бота;
- ручная регистрация чата через `/register_here`;
- CRUD для видов ЧС, подуровней и шаблонов;
- удаление видов ЧС, подуровней, шаблонов, кнопок и чатов из системы;
- выбор чата модерации прямо через личку бота;
- локальные админы в SQLite и опциональный вход админов через PostgreSQL;
- AI-улучшение текста под формат реального официального оповещения;
- рассылка по выбранным чатам и каналам;
- Excel-отчёт по периоду;
- мониторинг погодных рисков.

## Быстрый запуск

```bash
pip install -r requirements.txt
cp .env.example .env
python -m app.main
```

## PostgreSQL для входа администраторов

Если у вас есть общий сайт/портал на PostgreSQL, бот может впускать администраторов оттуда.
Достаточно указать `POSTGRES_DSN` и создать таблицу:

```sql
CREATE TABLE IF NOT EXISTS bot_admins (
    telegram_id BIGINT PRIMARY KEY,
    full_name TEXT DEFAULT '',
    username TEXT DEFAULT '',
    role TEXT NOT NULL DEFAULT 'admin',
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
```

При `/start` бот проверит локальную SQLite-базу и, если нужно, попробует найти пользователя в PostgreSQL-таблице `bot_admins`.

## Как выбрать чат модерации

1. Добавьте бота в нужную группу или канал.
2. Убедитесь, что бот увидел чат автоматически или выполните в чате `/register_here`.
3. В личке бота откройте раздел `👮 Модерация`.
4. Нажмите на нужный чат — он станет чатом модерации.

## Что важно для боевого контура

Для официального сценария лучше перейти с SQLite на PostgreSQL как на основную БД и вынести запуск на VPS/Linux с авто-рестартом.


## Weather API note

Set `YANDEX_WEATHER_API_KEY` in `.env`. The bot uses the Yandex Weather v2 `forecast` endpoint and falls back to Open-Meteo if Yandex is unavailable.

