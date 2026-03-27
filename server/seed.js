const bcrypt = require('bcrypt');
const pool = require('./db');

async function seed() {
  const client = await pool.connect();
  try {
    // ── Users ──────────────────────────────────────────────────────
    await client.query(`
      CREATE TABLE IF NOT EXISTS users (
        id SERIAL PRIMARY KEY,
        username VARCHAR(50) UNIQUE NOT NULL,
        password_hash VARCHAR(255) NOT NULL,
        role VARCHAR(20) DEFAULT 'user',
        created_at TIMESTAMP DEFAULT NOW()
      )
    `);
    await client.query(`ALTER TABLE users ADD COLUMN IF NOT EXISTS role VARCHAR(20) DEFAULT 'user'`);

    // ── Виды ЧС ────────────────────────────────────────────────────
    await client.query(`
      CREATE TABLE IF NOT EXISTS emergency_types (
        id SERIAL PRIMARY KEY,
        name VARCHAR(100) NOT NULL,
        created_at TIMESTAMP DEFAULT NOW()
      )
    `);

    // ── Типы опасности ─────────────────────────────────────────────
    await client.query(`
      CREATE TABLE IF NOT EXISTS danger_levels (
        id SERIAL PRIMARY KEY,
        name VARCHAR(100) NOT NULL,
        color VARCHAR(20) DEFAULT '#ef4444',
        emergency_type_id INTEGER REFERENCES emergency_types(id) ON DELETE CASCADE,
        created_at TIMESTAMP DEFAULT NOW()
      )
    `);

    // ── Telegram-чаты (куда бот рассылает) ────────────────────────
    await client.query(`
      CREATE TABLE IF NOT EXISTS telegram_chats (
        id SERIAL PRIMARY KEY,
        chat_id BIGINT UNIQUE NOT NULL,
        name VARCHAR(200),
        active BOOLEAN DEFAULT TRUE,
        created_at TIMESTAMP DEFAULT NOW()
      )
    `);

    // ── Очередь от веб-портала (бот читает через pg_sync) ─────────
    await client.query(`
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
    `);

    // ── Единый лог (пишут и бот, и веб; читает Excel-экспорт) ────
    await client.query(`
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
    `);

    // ── Администраторы бота (для postgres_auth) ───────────────────
    await client.query(`
      CREATE TABLE IF NOT EXISTS bot_admins (
        telegram_id BIGINT PRIMARY KEY,
        full_name   VARCHAR(200) DEFAULT '',
        username    VARCHAR(100) DEFAULT '',
        role        VARCHAR(20)  DEFAULT 'admin',
        is_active   BOOLEAN      DEFAULT TRUE,
        created_at  TIMESTAMP    DEFAULT NOW()
      )
    `);

    // ── Шаблоны ────────────────────────────────────────────────────
    await client.query(`
      CREATE TABLE IF NOT EXISTS templates (
        id SERIAL PRIMARY KEY,
        name VARCHAR(100) NOT NULL,
        emergency_type_id INTEGER REFERENCES emergency_types(id) ON DELETE SET NULL,
        message_text TEXT NOT NULL,
        media_url VARCHAR(500),
        buttons JSONB DEFAULT '[]',
        created_at TIMESTAMP DEFAULT NOW()
      )
    `);

    // ── Очередь отправки (веб → бот) ──────────────────────────────
    await client.query(`
      CREATE TABLE IF NOT EXISTS send_queue (
        id SERIAL PRIMARY KEY,
        template_id INTEGER REFERENCES templates(id) ON DELETE SET NULL,
        emergency_type VARCHAR(100),
        message_text TEXT NOT NULL,
        media_url VARCHAR(500),
        buttons JSONB DEFAULT '[]',
        sent_by VARCHAR(50),
        status VARCHAR(20) DEFAULT 'pending',
        created_at TIMESTAMP DEFAULT NOW(),
        processed_at TIMESTAMP
      )
    `);

    // ── Лог всех отправленных сообщений (веб + бот) ───────────────
    await client.query(`
      CREATE TABLE IF NOT EXISTS message_logs (
        id SERIAL PRIMARY KEY,
        template_id INTEGER REFERENCES templates(id) ON DELETE SET NULL,
        emergency_type VARCHAR(100),
        chat_id BIGINT,
        chat_name VARCHAR(200),
        message_text TEXT,
        source VARCHAR(20) DEFAULT 'web',
        sent_by VARCHAR(100),
        telegram_message_id BIGINT,
        sent_at TIMESTAMP DEFAULT NOW()
      )
    `);

    // ── Карта ЧС ───────────────────────────────────────────────────
    await client.query(`
      CREATE TABLE IF NOT EXISTS map_incidents (
        id SERIAL PRIMARY KEY,
        title VARCHAR(200) NOT NULL,
        description TEXT DEFAULT '',
        lat DOUBLE PRECISION NOT NULL,
        lon DOUBLE PRECISION NOT NULL,
        emergency_type_id INTEGER REFERENCES emergency_types(id) ON DELETE SET NULL,
        danger_level_id INTEGER REFERENCES danger_levels(id) ON DELETE SET NULL,
        status VARCHAR(20) DEFAULT 'active',
        created_at TIMESTAMP DEFAULT NOW()
      )
    `);

    // ── Пользователи (только при первом запуске — ON CONFLICT DO NOTHING) ─────
    // Удаляем обычных пользователей если они есть
    await client.query(`DELETE FROM users WHERE role = 'user'`);
    const credentials = [
      { username: 'admin',  password: 'Admin123!',  role: 'superuser' },
      { username: 'Maxim',  password: 'Maxim2026!', role: 'superuser' },
      { username: 'Matvey', password: 'Matvey2026!',role: 'superuser' },
      { username: 'L3sha',  password: 'L3sha2026!', role: 'superuser' },
    ];
    for (const cred of credentials) {
      const hash = await bcrypt.hash(cred.password, 10);
      await client.query(
        `INSERT INTO users (username, password_hash, role)
         VALUES ($1, $2, $3)
         ON CONFLICT (username) DO NOTHING`,
        [cred.username, hash, cred.role]
      );
    }

    // ── Настройки приложения (маркер первоначального заполнения) ──
    await client.query(`
      CREATE TABLE IF NOT EXISTS app_settings (
        key   VARCHAR(100) PRIMARY KEY,
        value TEXT NOT NULL
      )
    `);

    // ── Виды ЧС (только при первом запуске seed) ───────────────────
    const seededRow = await client.query(`SELECT value FROM app_settings WHERE key = 'defaults_seeded'`);
    if (!seededRow.rows.length) {
      // Проверяем — если данные уже есть (миграция с предыдущей версии), только ставим маркер
      const existingCount = await client.query('SELECT COUNT(*) AS cnt FROM emergency_types');
      if (parseInt(existingCount.rows[0].cnt) === 0) {
        const types = ['Пожар', 'Наводнение', 'Землетрясение', 'Химическая авария', 'Террористическая угроза'];
        for (const name of types) {
          await client.query(`INSERT INTO emergency_types (name) VALUES ($1)`, [name]);
        }

        // ── Типы опасности (начальные данные) ──────────────────────
        const etRes = await client.query('SELECT id, name FROM emergency_types');
        const typeMap = Object.fromEntries(etRes.rows.map(r => [r.name, r.id]));
        const levels = [
          { name: 'Высокий',     color: '#ef4444', type: 'Пожар' },
          { name: 'Средний',     color: '#f97316', type: 'Пожар' },
          { name: 'Низкий',      color: '#eab308', type: 'Пожар' },
          { name: 'Критический', color: '#dc2626', type: 'Наводнение' },
          { name: 'Умеренный',   color: '#f97316', type: 'Наводнение' },
        ];
        for (const l of levels) {
          if (typeMap[l.type]) {
            await client.query(
              `INSERT INTO danger_levels (name, color, emergency_type_id) VALUES ($1,$2,$3)`,
              [l.name, l.color, typeMap[l.type]]
            );
          }
        }
        console.log('Начальные виды ЧС добавлены.');
      } else {
        console.log('Данные уже существуют — ставим маркер инициализации.');
      }
      // Ставим маркер в любом случае — больше не проверяем при повторном запуске
      await client.query(`INSERT INTO app_settings (key, value) VALUES ('defaults_seeded', 'true')`);
    } else {
      console.log('База уже инициализирована — виды ЧС не перезаписываются.');
    }

    console.log('База данных заполнена успешно.');
    console.log('  Логин: admin   Пароль: Admin123!   Роль: superuser');
    console.log('  Логин: Maxim   Пароль: Maxim2026!  Роль: superuser');
    console.log('  Логин: Matvey  Пароль: Matvey2026! Роль: superuser');
    console.log('  Логин: L3sha   Пароль: L3sha2026!  Роль: superuser');
  } catch (err) {
    console.error('Ошибка при заполнении базы:', err);
  } finally {
    client.release();
    await pool.end();
  }
}

seed();
