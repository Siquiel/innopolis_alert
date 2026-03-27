const express = require('express');
const cors = require('cors');
const bcrypt = require('bcrypt');
const jwt = require('jsonwebtoken');
const multer = require('multer');
const path = require('path');
const fs = require('fs');
const XLSX = require('xlsx');
require('dotenv').config();

const pool = require('./db');
const app = express();

const uploadsDir = path.join(__dirname, 'uploads');
if (!fs.existsSync(uploadsDir)) fs.mkdirSync(uploadsDir);

app.use(cors({ origin: process.env.CLIENT_ORIGIN ? process.env.CLIENT_ORIGIN.split(',') : true }));
app.use(express.json());
app.use('/uploads', express.static(uploadsDir));

const storage = multer.diskStorage({
  destination: (req, file, cb) => cb(null, uploadsDir),
  filename: (req, file, cb) => cb(null, `${Date.now()}${path.extname(file.originalname)}`),
});
const upload = multer({ storage, limits: { fileSize: 50 * 1024 * 1024 } });

// ── Middleware ──────────────────────────────────────────────────────────────

function authMiddleware(req, res, next) {
  const auth = req.headers.authorization;
  if (!auth) return res.status(401).json({ error: 'Токен не передан' });
  try {
    req.user = jwt.verify(auth.split(' ')[1], process.env.JWT_SECRET);
    next();
  } catch {
    res.status(401).json({ error: 'Токен недействителен' });
  }
}

function superuser(req, res, next) {
  if (req.user?.role !== 'superuser') return res.status(403).json({ error: 'Доступ запрещён' });
  next();
}

// ── Auth ────────────────────────────────────────────────────────────────────

app.post('/api/login', async (req, res) => {
  const { username, password } = req.body;
  if (!username || !password)
    return res.status(400).json({ error: 'Логин и пароль обязательны' });
  try {
    const r = await pool.query('SELECT * FROM users WHERE username = $1', [username]);
    if (!r.rows.length) return res.status(401).json({ error: 'Неверный логин или пароль' });
    const user = r.rows[0];
    if (!await bcrypt.compare(password, user.password_hash))
      return res.status(401).json({ error: 'Неверный логин или пароль' });
    const token = jwt.sign(
      { id: user.id, username: user.username, role: user.role },
      process.env.JWT_SECRET, { expiresIn: '8h' }
    );
    res.json({ token, username: user.username, role: user.role });
  } catch (err) {
    console.error(err);
    res.status(500).json({ error: 'Внутренняя ошибка сервера' });
  }
});

app.get('/api/verify', (req, res) => {
  const auth = req.headers.authorization;
  if (!auth) return res.status(401).json({ error: 'Токен не передан' });
  try {
    const decoded = jwt.verify(auth.split(' ')[1], process.env.JWT_SECRET);
    res.json({ username: decoded.username, role: decoded.role });
  } catch {
    res.status(401).json({ error: 'Токен недействителен' });
  }
});

// ── Виды ЧС ─────────────────────────────────────────────────────────────────

app.get('/api/admin/emergency-types', authMiddleware, async (req, res) => {
  const r = await pool.query('SELECT * FROM emergency_types ORDER BY id');
  res.json(r.rows);
});
app.post('/api/admin/emergency-types', authMiddleware, superuser, async (req, res) => {
  const r = await pool.query('INSERT INTO emergency_types (name) VALUES ($1) RETURNING *', [req.body.name]);
  res.json(r.rows[0]);
});
app.put('/api/admin/emergency-types/:id', authMiddleware, superuser, async (req, res) => {
  const r = await pool.query('UPDATE emergency_types SET name=$1 WHERE id=$2 RETURNING *', [req.body.name, req.params.id]);
  res.json(r.rows[0]);
});
app.delete('/api/admin/emergency-types/:id', authMiddleware, superuser, async (req, res) => {
  await pool.query('DELETE FROM emergency_types WHERE id=$1', [req.params.id]);
  res.json({ ok: true });
});

// ── Типы опасности ───────────────────────────────────────────────────────────

app.get('/api/admin/danger-levels', authMiddleware, async (req, res) => {
  const r = await pool.query(`
    SELECT dl.*, et.name AS emergency_type_name
    FROM danger_levels dl LEFT JOIN emergency_types et ON et.id = dl.emergency_type_id
    ORDER BY dl.id`);
  res.json(r.rows);
});
app.post('/api/admin/danger-levels', authMiddleware, superuser, async (req, res) => {
  const { name, color, emergency_type_id } = req.body;
  const r = await pool.query(
    'INSERT INTO danger_levels (name, color, emergency_type_id) VALUES ($1,$2,$3) RETURNING *',
    [name, color || '#ef4444', emergency_type_id || null]
  );
  res.json(r.rows[0]);
});
app.put('/api/admin/danger-levels/:id', authMiddleware, superuser, async (req, res) => {
  const { name, color, emergency_type_id } = req.body;
  const r = await pool.query(
    'UPDATE danger_levels SET name=$1, color=$2, emergency_type_id=$3 WHERE id=$4 RETURNING *',
    [name, color || '#ef4444', emergency_type_id || null, req.params.id]
  );
  res.json(r.rows[0]);
});
app.delete('/api/admin/danger-levels/:id', authMiddleware, superuser, async (req, res) => {
  await pool.query('DELETE FROM danger_levels WHERE id=$1', [req.params.id]);
  res.json({ ok: true });
});

// ── Telegram-чаты ────────────────────────────────────────────────────────────

app.get('/api/admin/telegram-chats', authMiddleware, async (req, res) => {
  const r = await pool.query('SELECT * FROM telegram_chats ORDER BY id');
  res.json(r.rows);
});
app.post('/api/admin/telegram-chats', authMiddleware, superuser, async (req, res) => {
  const { chat_id, name } = req.body;
  const r = await pool.query(
    'INSERT INTO telegram_chats (chat_id, name) VALUES ($1,$2) ON CONFLICT (chat_id) DO UPDATE SET name=$2, active=TRUE RETURNING *',
    [chat_id, name || '']
  );
  res.json(r.rows[0]);
});
app.put('/api/admin/telegram-chats/:id', authMiddleware, superuser, async (req, res) => {
  const { name, active } = req.body;
  const r = await pool.query(
    'UPDATE telegram_chats SET name=$1, active=$2 WHERE id=$3 RETURNING *',
    [name, active !== false, req.params.id]
  );
  res.json(r.rows[0]);
});
app.delete('/api/admin/telegram-chats/:id', authMiddleware, superuser, async (req, res) => {
  await pool.query('DELETE FROM telegram_chats WHERE id=$1', [req.params.id]);
  res.json({ ok: true });
});

// ── Шаблоны ──────────────────────────────────────────────────────────────────

app.get('/api/admin/templates', authMiddleware, async (req, res) => {
  const r = await pool.query(`
    SELECT t.*, et.name AS emergency_type_name
    FROM templates t LEFT JOIN emergency_types et ON et.id = t.emergency_type_id
    ORDER BY t.id`);
  res.json(r.rows);
});
app.post('/api/admin/templates', authMiddleware, superuser, upload.single('media'), async (req, res) => {
  const { name, emergency_type_id, message_text, buttons } = req.body;
  const media_url = req.file ? `/uploads/${req.file.filename}` : null;
  const r = await pool.query(
    'INSERT INTO templates (name, emergency_type_id, message_text, media_url, buttons) VALUES ($1,$2,$3,$4,$5) RETURNING *',
    [name, emergency_type_id || null, message_text, media_url, buttons ? JSON.parse(buttons) : []]
  );
  res.json(r.rows[0]);
});
app.put('/api/admin/templates/:id', authMiddleware, superuser, upload.single('media'), async (req, res) => {
  const { name, emergency_type_id, message_text, buttons, remove_media } = req.body;
  const ex = await pool.query('SELECT media_url FROM templates WHERE id=$1', [req.params.id]);
  let media_url = ex.rows[0]?.media_url || null;
  if (req.file) {
    if (media_url) { const p = path.join(__dirname, media_url); if (fs.existsSync(p)) fs.unlinkSync(p); }
    media_url = `/uploads/${req.file.filename}`;
  } else if (remove_media === 'true') {
    if (media_url) { const p = path.join(__dirname, media_url); if (fs.existsSync(p)) fs.unlinkSync(p); }
    media_url = null;
  }
  const r = await pool.query(
    'UPDATE templates SET name=$1, emergency_type_id=$2, message_text=$3, media_url=$4, buttons=$5 WHERE id=$6 RETURNING *',
    [name, emergency_type_id || null, message_text, media_url, buttons ? JSON.parse(buttons) : [], req.params.id]
  );
  res.json(r.rows[0]);
});
app.delete('/api/admin/templates/:id', authMiddleware, superuser, async (req, res) => {
  const r = await pool.query('SELECT media_url FROM templates WHERE id=$1', [req.params.id]);
  const mu = r.rows[0]?.media_url;
  if (mu) { const p = path.join(__dirname, mu); if (fs.existsSync(p)) fs.unlinkSync(p); }
  await pool.query('DELETE FROM templates WHERE id=$1', [req.params.id]);
  res.json({ ok: true });
});

// ── Отправка (веб → web_queue → бот) ─────────────────────────────────────────

app.post('/api/send', authMiddleware, superuser, async (req, res) => {
  const { template_id } = req.body;
  try {
    const t = await pool.query(
      `SELECT t.*, et.name AS emergency_type_name FROM templates t
       LEFT JOIN emergency_types et ON et.id = t.emergency_type_id WHERE t.id = $1`,
      [template_id]
    );
    if (!t.rows.length) return res.status(404).json({ error: 'Шаблон не найден' });
    const tmpl = t.rows[0];

    // Проверяем есть ли активные чаты
    const chatsRes = await pool.query('SELECT COUNT(*) AS cnt FROM telegram_chats WHERE active = TRUE');
    const chatCount = parseInt(chatsRes.rows[0].cnt, 10);
    if (chatCount === 0) {
      return res.status(400).json({ error: 'Нет активных Telegram-чатов. Добавьте чаты на вкладке «Telegram-чаты».' });
    }

    // Создаём задание в очереди — бот подберёт через pg_sync
    await pool.query(
      `INSERT INTO web_queue (emergency_type, message_text, media_url, buttons, sent_by)
       VALUES ($1,$2,$3,$4,$5)`,
      [tmpl.emergency_type_name, tmpl.message_text, tmpl.media_url, JSON.stringify(tmpl.buttons || []), req.user.username]
    );
    res.json({ ok: true, chat_count: chatCount });
  } catch (err) {
    console.error(err);
    res.status(500).json({ error: 'Внутренняя ошибка сервера' });
  }
});

// ── Экспорт Excel ─────────────────────────────────────────────────────────────

app.get('/api/admin/export', authMiddleware, superuser, async (req, res) => {
  const { from, to } = req.query;
  // Читаем из единого dispatch_log — туда пишут и бот, и веб
  const r = await pool.query(`
    SELECT
      dl.id AS "№",
      CASE dl.source WHEN 'bot' THEN 'Telegram бот' ELSE 'Веб-портал' END AS "Источник",
      dl.emergency_type AS "Вид ЧС",
      dl.chat_name AS "Чат",
      dl.chat_id AS "Chat ID",
      dl.sent_by AS "Отправил",
      to_char(dl.sent_at, 'DD.MM.YYYY HH24:MI') AS "Дата отправки",
      dl.message_text AS "Текст сообщения"
    FROM dispatch_log dl
    WHERE ($1::date IS NULL OR dl.sent_at >= $1::date)
      AND ($2::date IS NULL OR dl.sent_at <= ($2::date + interval '1 day'))
    ORDER BY dl.sent_at DESC
  `, [from || null, to || null]);

  const wb = XLSX.utils.book_new();
  const ws = XLSX.utils.json_to_sheet(r.rows.length ? r.rows : [{ 'Нет данных': '' }]);
  XLSX.utils.book_append_sheet(wb, ws, 'Рассылки');
  const buf = XLSX.write(wb, { type: 'buffer', bookType: 'xlsx' });
  res.setHeader('Content-Disposition', 'attachment; filename="report.xlsx"');
  res.setHeader('Content-Type', 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet');
  res.send(buf);
});

// ── Публичная карта (без авторизации) — React SPA обрабатывает роут ──────────

// Публичный API только для чтения карты
app.get('/api/public/map/incidents', async (req, res) => {
  try {
    const r = await pool.query(`
      SELECT mi.id, mi.title, mi.description, mi.lat, mi.lon, mi.status,
             et.name AS emergency_type_name, dl.name AS danger_level_name, dl.color AS danger_color
      FROM map_incidents mi
      LEFT JOIN emergency_types et ON et.id = mi.emergency_type_id
      LEFT JOIN danger_levels dl ON dl.id = mi.danger_level_id
      ORDER BY mi.created_at DESC
    `);
    res.json(r.rows);
  } catch (err) { console.error(err); res.status(500).json({ error: 'Ошибка сервера' }); }
});

// ── Карта ЧС ──────────────────────────────────────────────────────────────────

app.get('/api/map/incidents', authMiddleware, async (req, res) => {
  try {
    const r = await pool.query(`
      SELECT mi.*, et.name AS emergency_type_name, dl.name AS danger_level_name, dl.color AS danger_color
      FROM map_incidents mi
      LEFT JOIN emergency_types et ON et.id = mi.emergency_type_id
      LEFT JOIN danger_levels dl ON dl.id = mi.danger_level_id
      ORDER BY mi.created_at DESC
    `);
    res.json(r.rows);
  } catch (err) { console.error(err); res.status(500).json({ error: 'Ошибка сервера' }); }
});

app.post('/api/map/incidents', authMiddleware, superuser, async (req, res) => {
  const { title, description, lat, lon, emergency_type_id, danger_level_id, status } = req.body;
  try {
    const r = await pool.query(
      `INSERT INTO map_incidents (title, description, lat, lon, emergency_type_id, danger_level_id, status)
       VALUES ($1,$2,$3,$4,$5,$6,$7) RETURNING *`,
      [title, description || '', parseFloat(lat), parseFloat(lon), emergency_type_id || null, danger_level_id || null, status || 'active']
    );
    res.json(r.rows[0]);
  } catch (err) { console.error(err); res.status(500).json({ error: 'Ошибка сервера' }); }
});

app.put('/api/map/incidents/:id', authMiddleware, superuser, async (req, res) => {
  const { title, description, lat, lon, emergency_type_id, danger_level_id, status } = req.body;
  try {
    const r = await pool.query(
      `UPDATE map_incidents SET title=$1,description=$2,lat=$3,lon=$4,emergency_type_id=$5,danger_level_id=$6,status=$7 WHERE id=$8 RETURNING *`,
      [title, description || '', parseFloat(lat), parseFloat(lon), emergency_type_id || null, danger_level_id || null, status || 'active', req.params.id]
    );
    res.json(r.rows[0]);
  } catch (err) { console.error(err); res.status(500).json({ error: 'Ошибка сервера' }); }
});

app.delete('/api/map/incidents/:id', authMiddleware, superuser, async (req, res) => {
  try {
    await pool.query('DELETE FROM map_incidents WHERE id=$1', [req.params.id]);
    res.json({ ok: true });
  } catch (err) { console.error(err); res.status(500).json({ error: 'Ошибка сервера' }); }
});

// ── Раздача React-билда (для production) ─────────────────────────────────────

const distPath = path.join(__dirname, '../client/dist');
if (fs.existsSync(distPath)) {
  app.use(express.static(distPath));
  app.get('*', (req, res) => {
    if (!req.path.startsWith('/api') && !req.path.startsWith('/uploads')) {
      res.sendFile(path.join(distPath, 'index.html'));
    }
  });
}

// ─────────────────────────────────────────────────────────────────────────────

const PORT = process.env.PORT || 3001;
app.listen(PORT, () => console.log(`Сервер запущен: http://localhost:${PORT}`));
