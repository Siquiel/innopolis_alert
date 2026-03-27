/**
 * Скрипт управления пользователями:
 * - Удаляет всех обычных пользователей (роль 'user')
 * - Добавляет 3 суперпользователей: Maxim, Matvey, L3sha
 *
 * Запуск: node add_superusers.js
 */
const bcrypt = require('bcrypt');
const pool = require('./db');

const newSuperusers = [
  { username: 'Maxim',  password: 'Maxim2026!' },
  { username: 'Matvey', password: 'Matvey2026!' },
  { username: 'L3sha',  password: 'L3sha2026!' },
];

async function run() {
  const client = await pool.connect();
  try {
    // Удаляем всех обычных пользователей (роль user)
    const del = await client.query(`DELETE FROM users WHERE role = 'user' RETURNING username`);
    if (del.rows.length) {
      console.log('Удалены обычные пользователи:', del.rows.map(r => r.username).join(', '));
    } else {
      console.log('Обычных пользователей не было.');
    }

    // Добавляем / обновляем суперпользователей
    for (const u of newSuperusers) {
      const hash = await bcrypt.hash(u.password, 10);
      await client.query(
        `INSERT INTO users (username, password_hash, role)
         VALUES ($1, $2, 'superuser')
         ON CONFLICT (username) DO UPDATE SET password_hash = $2, role = 'superuser'`,
        [u.username, hash]
      );
      console.log(`  Суперпользователь: ${u.username}  Пароль: ${u.password}`);
    }

    console.log('\nГотово. Текущие пользователи:');
    const all = await client.query('SELECT username, role FROM users ORDER BY id');
    all.rows.forEach(r => console.log(`  ${r.username} (${r.role})`));
  } catch (err) {
    console.error('Ошибка:', err.message);
  } finally {
    client.release();
    await pool.end();
  }
}

run();
