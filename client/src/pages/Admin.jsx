import { useState, useEffect, useRef } from 'react';
import { useNavigate } from 'react-router-dom';
import L from 'leaflet';
import 'leaflet/dist/leaflet.css';

// Fix Leaflet default icon paths for Vite
delete L.Icon.Default.prototype._getIconUrl;
L.Icon.Default.mergeOptions({
  iconRetinaUrl: new URL('leaflet/dist/images/marker-icon-2x.png', import.meta.url).href,
  iconUrl: new URL('leaflet/dist/images/marker-icon.png', import.meta.url).href,
  shadowUrl: new URL('leaflet/dist/images/marker-shadow.png', import.meta.url).href,
});

function useTheme() {
  const [dark, setDark] = useState(() => localStorage.getItem('theme') === 'dark');
  useEffect(() => {
    document.body.classList.toggle('dark', dark);
    localStorage.setItem('theme', dark ? 'dark' : 'light');
  }, [dark]);
  return [dark, setDark];
}

const _BASE = import.meta.env.VITE_API_URL || 'http://localhost:3001';
const API = `${_BASE}/api/admin`;
const API_BASE = _BASE;
const MEDIA_BASE = _BASE;

function authHeaders() {
  return { Authorization: `Bearer ${localStorage.getItem('token')}` };
}
function jsonHeaders() {
  return { 'Content-Type': 'application/json', ...authHeaders() };
}

// ── Modal ──────────────────────────────────────────────────────────────────

function Modal({ title, onClose, children }) {
  return (
    <div className="modal-overlay" onClick={onClose}>
      <div className="modal-box" onClick={e => e.stopPropagation()}>
        <div className="modal-header">
          <h3>{title}</h3>
          <button className="modal-close" onClick={onClose}>×</button>
        </div>
        <div className="modal-body">{children}</div>
      </div>
    </div>
  );
}

// ── Tab: Виды ЧС ──────────────────────────────────────────────────────────

function EmergencyTypesTab() {
  const [items, setItems] = useState([]);
  const [modal, setModal] = useState(null);
  const [name, setName] = useState('');

  const load = async () => {
    const r = await fetch(`${API}/emergency-types`, { headers: authHeaders() });
    setItems(await r.json());
  };
  useEffect(() => { load(); }, []);

  const openAdd = () => { setName(''); setModal('add'); };
  const openEdit = item => { setName(item.name); setModal(item); };

  const save = async () => {
    if (modal === 'add') {
      await fetch(`${API}/emergency-types`, { method: 'POST', headers: jsonHeaders(), body: JSON.stringify({ name }) });
    } else {
      await fetch(`${API}/emergency-types/${modal.id}`, { method: 'PUT', headers: jsonHeaders(), body: JSON.stringify({ name }) });
    }
    setModal(null); load();
  };

  const del = async id => {
    if (!confirm('Удалить вид ЧС? Это удалит все связанные шаблоны и уровни опасности.')) return;
    await fetch(`${API}/emergency-types/${id}`, { method: 'DELETE', headers: authHeaders() });
    load();
  };

  return (
    <div className="tab-content">
      <div className="tab-toolbar">
        <div>
          <h2 className="tab-title">Виды ЧС</h2>
          <p className="tab-subtitle">Управление видами чрезвычайных ситуаций</p>
        </div>
        <button className="btn-add" onClick={openAdd}>+ Добавить</button>
      </div>
      <table className="admin-table">
        <thead><tr><th>Название</th><th>Действия</th></tr></thead>
        <tbody>
          {items.map(i => (
            <tr key={i.id}>
              <td>{i.name}</td>
              <td><div className="actions-cell">
                <button className="btn-edit" onClick={() => openEdit(i)}>Изменить</button>
                <button className="btn-del" onClick={() => del(i.id)}>Удалить</button>
              </div></td>
            </tr>
          ))}
          {!items.length && <tr><td colSpan={2} className="empty-row">Нет данных</td></tr>}
        </tbody>
      </table>
      {modal && (
        <Modal title={modal === 'add' ? 'Добавить вид ЧС' : 'Редактировать вид ЧС'} onClose={() => setModal(null)}>
          <div className="form-group">
            <label className="form-label">Название</label>
            <input className="form-input" value={name} onChange={e => setName(e.target.value)} placeholder="Например: Пожар" />
          </div>
          <div className="modal-footer">
            <button className="btn-cancel" onClick={() => setModal(null)}>Отмена</button>
            <button className="btn-save" onClick={save} disabled={!name.trim()}>Сохранить</button>
          </div>
        </Modal>
      )}
    </div>
  );
}

// 5 фиксированных уровней опасности: 1 (зелёный) → 5 (тёмно-малиновый)
const SEVERITY_LEVELS = [
  { value: 1, color: '#16a34a', label: '1 — Минимальный' },
  { value: 2, color: '#ca8a04', label: '2 — Низкий' },
  { value: 3, color: '#ea580c', label: '3 — Средний' },
  { value: 4, color: '#dc2626', label: '4 — Высокий' },
  { value: 5, color: '#881337', label: '5 — Критический' },
];

// ── Tab: Типы опасности ────────────────────────────────────────────────────

function DangerLevelsTab() {
  const [items, setItems] = useState([]);
  const [types, setTypes] = useState([]);
  const [modal, setModal] = useState(null);
  const [form, setForm] = useState({ name: '', severity: 1, emergency_type_id: '' });

  const severityToColor = (s) => SEVERITY_LEVELS.find(l => l.value === Number(s))?.color || '#16a34a';

  const load = async () => {
    const [r1, r2] = await Promise.all([
      fetch(`${API}/danger-levels`, { headers: authHeaders() }),
      fetch(`${API}/emergency-types`, { headers: authHeaders() }),
    ]);
    setItems(await r1.json()); setTypes(await r2.json());
  };
  useEffect(() => { load(); }, []);

  const openAdd = () => { setForm({ name: '', severity: 1, emergency_type_id: '' }); setModal('add'); };
  const openEdit = item => {
    // Определяем severity по цвету
    const found = SEVERITY_LEVELS.find(l => l.color === item.color);
    setForm({ name: item.name, severity: found ? found.value : 1, emergency_type_id: item.emergency_type_id || '' });
    setModal(item);
  };

  const save = async () => {
    const color = severityToColor(form.severity);
    const body = JSON.stringify({ name: form.name, color, emergency_type_id: form.emergency_type_id });
    if (modal === 'add') await fetch(`${API}/danger-levels`, { method: 'POST', headers: jsonHeaders(), body });
    else await fetch(`${API}/danger-levels/${modal.id}`, { method: 'PUT', headers: jsonHeaders(), body });
    setModal(null); load();
  };

  const del = async id => {
    if (!confirm('Удалить тип опасности?')) return;
    await fetch(`${API}/danger-levels/${id}`, { method: 'DELETE', headers: authHeaders() });
    load();
  };

  const getSeverityLabel = (color) => SEVERITY_LEVELS.find(l => l.color === color)?.label || color;

  return (
    <div className="tab-content">
      <div className="tab-toolbar">
        <div>
          <h2 className="tab-title">Типы опасности</h2>
          <p className="tab-subtitle">Подуровни для каждого вида ЧС</p>
        </div>
        <button className="btn-add" onClick={openAdd}>+ Добавить</button>
      </div>

      {/* Легенда уровней */}
      <div className="severity-legend">
        {SEVERITY_LEVELS.map(l => (
          <div key={l.value} className="severity-legend-item">
            <span className="color-dot" style={{ background: l.color }} />
            {l.label}
          </div>
        ))}
      </div>

      <table className="admin-table">
        <thead><tr><th>Название</th><th>Уровень</th><th>Вид ЧС</th><th>Действия</th></tr></thead>
        <tbody>
          {items.map(i => (
            <tr key={i.id}>
              <td>{i.name}</td>
              <td><div className="color-cell"><span className="color-dot" style={{ background: i.color }} />{getSeverityLabel(i.color)}</div></td>
              <td>{i.emergency_type_name || '—'}</td>
              <td><div className="actions-cell">
                <button className="btn-edit" onClick={() => openEdit(i)}>Изменить</button>
                <button className="btn-del" onClick={() => del(i.id)}>Удалить</button>
              </div></td>
            </tr>
          ))}
          {!items.length && <tr><td colSpan={4} className="empty-row">Нет данных</td></tr>}
        </tbody>
      </table>

      {modal && (
        <Modal title={modal === 'add' ? 'Добавить тип опасности' : 'Редактировать'} onClose={() => setModal(null)}>
          <div className="form-group">
            <label className="form-label">Название</label>
            <input className="form-input" value={form.name} onChange={e => setForm(f => ({ ...f, name: e.target.value }))} placeholder="Например: Высокий" />
          </div>
          <div className="form-group">
            <label className="form-label">Уровень опасности</label>
            <div className="severity-picker">
              {SEVERITY_LEVELS.map(l => (
                <button key={l.value} type="button"
                  className={`severity-btn ${form.severity === l.value ? 'active' : ''}`}
                  style={{ '--sev-color': l.color }}
                  onClick={() => setForm(f => ({ ...f, severity: l.value }))}>
                  <span className="sev-dot" style={{ background: l.color }} />
                  {l.label}
                </button>
              ))}
            </div>
          </div>
          <div className="form-group">
            <label className="form-label">Вид ЧС</label>
            <select className="form-select" value={form.emergency_type_id} onChange={e => setForm(f => ({ ...f, emergency_type_id: e.target.value }))}>
              <option value="">— Не выбрано —</option>
              {types.map(t => <option key={t.id} value={t.id}>{t.name}</option>)}
            </select>
          </div>
          <div className="modal-footer">
            <button className="btn-cancel" onClick={() => setModal(null)}>Отмена</button>
            <button className="btn-save" onClick={save} disabled={!form.name.trim()}>Сохранить</button>
          </div>
        </Modal>
      )}
    </div>
  );
}

// ── Tab: Шаблоны ──────────────────────────────────────────────────────────

function TemplatesTab() {
  const [items, setItems] = useState([]);
  const [types, setTypes] = useState([]);
  const [modal, setModal] = useState(null);
  const [sendModal, setSendModal] = useState(null);
  const [sending, setSending] = useState(false);
  const [form, setForm] = useState({ name: '', emergency_type_id: '', message_text: '', buttons: [] });
  const [mediaFile, setMediaFile] = useState(null);
  const [removeMedia, setRemoveMedia] = useState(false);
  const fileRef = useRef();

  const load = async () => {
    const [r1, r2] = await Promise.all([
      fetch(`${API}/templates`, { headers: authHeaders() }),
      fetch(`${API}/emergency-types`, { headers: authHeaders() }),
    ]);
    setItems(await r1.json()); setTypes(await r2.json());
  };
  useEffect(() => { load(); }, []);

  const openAdd = () => { setForm({ name: '', emergency_type_id: '', message_text: '', buttons: [] }); setMediaFile(null); setRemoveMedia(false); setModal('add'); };
  const openEdit = item => {
    setSendModal(null);
    setForm({
      name: item.name || '',
      emergency_type_id: item.emergency_type_id || '',
      message_text: item.message_text || '',
      buttons: Array.isArray(item.buttons) ? item.buttons : [],
    });
    setMediaFile(null); setRemoveMedia(false); setModal(item);
  };

  const save = async () => {
    const fd = new FormData();
    fd.append('name', form.name);
    fd.append('message_text', form.message_text);
    fd.append('buttons', JSON.stringify(form.buttons));
    if (form.emergency_type_id) fd.append('emergency_type_id', form.emergency_type_id);
    if (mediaFile) fd.append('media', mediaFile);
    if (removeMedia) fd.append('remove_media', 'true');
    if (modal === 'add') await fetch(`${API}/templates`, { method: 'POST', headers: authHeaders(), body: fd });
    else await fetch(`${API}/templates/${modal.id}`, { method: 'PUT', headers: authHeaders(), body: fd });
    setModal(null); load();
  };

  const del = async id => {
    if (!confirm('Удалить шаблон?')) return;
    await fetch(`${API}/templates/${id}`, { method: 'DELETE', headers: authHeaders() });
    load();
  };

  const sendTemplate = async () => {
    setSending(true);
    try {
      const r = await fetch(`${_BASE}/api/send`, {
        method: 'POST', headers: jsonHeaders(),
        body: JSON.stringify({ template_id: sendModal.id }),
      });
      const data = await r.json();
      setSendModal(null);
      if (!r.ok) {
        alert(data.error || 'Ошибка отправки');
      } else {
        alert(`Задание добавлено в очередь. Бот отправит сообщение в ${data.chat_count} чат(а).`);
      }
    } catch {
      alert('Ошибка подключения к серверу');
    } finally {
      setSending(false);
    }
  };

  const addButton = () => setForm(f => ({ ...f, buttons: [...f.buttons, { text: '', url: '' }] }));
  const updateButton = (i, field, val) => setForm(f => { const b = [...f.buttons]; b[i] = { ...b[i], [field]: val }; return { ...f, buttons: b }; });
  const removeButton = i => setForm(f => ({ ...f, buttons: f.buttons.filter((_, idx) => idx !== i) }));

  const existingMedia = modal && modal !== 'add' ? modal.media_url : null;

  return (
    <div className="tab-content">
      <div className="tab-toolbar">
        <div>
          <h2 className="tab-title">Шаблоны</h2>
          <p className="tab-subtitle">Шаблоны сообщений для рассылки через Telegram</p>
        </div>
        <button className="btn-add" onClick={openAdd}>+ Добавить</button>
      </div>
      <table className="admin-table">
        <thead><tr><th>Название</th><th>Вид ЧС</th><th>Сообщение</th><th>Медиа</th><th>Кнопки</th><th>Действия</th></tr></thead>
        <tbody>
          {items.map(i => (
            <tr key={i.id}>
              <td style={{ fontWeight: 600 }}>{i.name}</td>
              <td>{i.emergency_type_name || '—'}</td>
              <td style={{ maxWidth: 180, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{i.message_text}</td>
              <td>{i.media_url ? (i.media_url.match(/\.(mp4|webm)$/i) ? '🎥 Видео' : <img className="media-preview" src={`${MEDIA_BASE}${i.media_url}`} alt="" />) : '—'}</td>
              <td>{(i.buttons || []).length > 0 ? `${i.buttons.length} шт.` : '—'}</td>
              <td><div className="actions-cell">
                <button className="btn-send" onClick={() => setSendModal(i)}>Отправить</button>
                <button className="btn-edit" onClick={() => openEdit(i)}>Изменить</button>
                <button className="btn-del" onClick={() => del(i.id)}>Удалить</button>
              </div></td>
            </tr>
          ))}
          {!items.length && <tr><td colSpan={6} className="empty-row">Нет шаблонов</td></tr>}
        </tbody>
      </table>

      {/* Модал отправки */}
      {sendModal && (
        <Modal title="Отправить в Telegram" onClose={() => setSendModal(null)}>
          <p style={{ fontSize: 14, color: '#374151' }}>
            Шаблон: <strong>{sendModal.name}</strong>
          </p>
          <div style={{ background: '#f9fafb', borderRadius: 8, padding: 14, fontSize: 14, color: '#374151', lineHeight: 1.6 }}>
            {sendModal.message_text}
          </div>
          <p style={{ fontSize: 13, color: '#6b7280' }}>
            Сообщение будет добавлено в очередь и отправлено ботом во все активные чаты.
          </p>
          <div className="modal-footer">
            <button className="btn-cancel" onClick={() => setSendModal(null)}>Отмена</button>
            <button className="btn-save" onClick={sendTemplate} disabled={sending}>
              {sending ? 'Отправка...' : 'Отправить'}
            </button>
          </div>
        </Modal>
      )}

      {/* Модал редактирования */}
      {modal && (
        <Modal title={modal === 'add' ? 'Добавить шаблон' : 'Редактировать шаблон'} onClose={() => setModal(null)}>
          <div className="form-group">
            <label className="form-label">Название</label>
            <input className="form-input" value={form.name} onChange={e => setForm(f => ({ ...f, name: e.target.value }))} placeholder="Название шаблона" />
          </div>
          <div className="form-group">
            <label className="form-label">Вид ЧС</label>
            <select className="form-select" value={form.emergency_type_id} onChange={e => setForm(f => ({ ...f, emergency_type_id: e.target.value }))}>
              <option value="">— Не выбрано —</option>
              {types.map(t => <option key={t.id} value={t.id}>{t.name}</option>)}
            </select>
          </div>
          <div className="form-group">
            <label className="form-label">Текст сообщения</label>
            <textarea className="form-textarea" value={form.message_text} onChange={e => setForm(f => ({ ...f, message_text: e.target.value }))} placeholder="Текст уведомления для жителей..." />
          </div>
          <div className="form-group">
            <label className="form-label">Медиафайл (необязательно)</label>
            {existingMedia && !removeMedia && !mediaFile ? (
              <div className="upload-preview">
                <span>{existingMedia.split('/').pop()}</span>
                <button className="btn-remove-media" onClick={() => setRemoveMedia(true)}>Удалить</button>
              </div>
            ) : mediaFile ? (
              <div className="upload-preview">
                <span>{mediaFile.name}</span>
                <button className="btn-remove-media" onClick={() => setMediaFile(null)}>✕</button>
              </div>
            ) : (
              <div className="upload-area" onClick={() => fileRef.current?.click()}>
                <input ref={fileRef} type="file" accept="image/*,video/*" onChange={e => { setMediaFile(e.target.files[0]); setRemoveMedia(false); }} />
                <div>Нажмите чтобы выбрать файл</div>
                <div className="upload-hint">Изображение или видео (до 50 МБ)</div>
              </div>
            )}
          </div>
          <div className="form-group">
            <label className="form-label">Кнопки для пользователей (необязательно)</label>
            <div className="buttons-list">
              {form.buttons.map((btn, i) => (
                <div key={i} className="button-row">
                  <input className="form-input" value={btn.text} onChange={e => updateButton(i, 'text', e.target.value)} placeholder="Текст кнопки" />
                  <input className="form-input" value={btn.url} onChange={e => updateButton(i, 'url', e.target.value)} placeholder="Ссылка (URL)" />
                  <button className="btn-remove-row" onClick={() => removeButton(i)}>×</button>
                </div>
              ))}
              <button className="btn-add-row" onClick={addButton}>+ Добавить кнопку</button>
            </div>
          </div>
          <div className="modal-footer">
            <button className="btn-cancel" onClick={() => setModal(null)}>Отмена</button>
            <button className="btn-save" onClick={save} disabled={!form.name.trim() || !form.message_text.trim()}>Сохранить</button>
          </div>
        </Modal>
      )}
    </div>
  );
}

// ── Tab: Telegram-чаты ────────────────────────────────────────────────────

function TelegramChatsTab() {
  const [items, setItems] = useState([]);
  const [modal, setModal] = useState(null);
  const [form, setForm] = useState({ chat_id: '', name: '' });

  const load = async () => {
    const r = await fetch(`${API}/telegram-chats`, { headers: authHeaders() });
    setItems(await r.json());
  };
  useEffect(() => { load(); }, []);

  const openAdd = () => { setForm({ chat_id: '', name: '' }); setModal('add'); };
  const openEdit = item => { setForm({ chat_id: item.chat_id, name: item.name || '' }); setModal(item); };

  const save = async () => {
    if (modal === 'add') {
      await fetch(`${API}/telegram-chats`, { method: 'POST', headers: jsonHeaders(), body: JSON.stringify(form) });
    } else {
      await fetch(`${API}/telegram-chats/${modal.id}`, { method: 'PUT', headers: jsonHeaders(), body: JSON.stringify({ name: form.name, active: modal.active }) });
    }
    setModal(null); load();
  };

  const toggleActive = async item => {
    await fetch(`${API}/telegram-chats/${item.id}`, {
      method: 'PUT', headers: jsonHeaders(),
      body: JSON.stringify({ name: item.name, active: !item.active }),
    });
    load();
  };

  const del = async id => {
    if (!confirm('Удалить чат?')) return;
    await fetch(`${API}/telegram-chats/${id}`, { method: 'DELETE', headers: authHeaders() });
    load();
  };

  return (
    <div className="tab-content">
      <div className="tab-toolbar">
        <div>
          <h2 className="tab-title">Telegram-чаты</h2>
          <p className="tab-subtitle">Чаты, куда бот отправляет рассылки</p>
        </div>
        <button className="btn-add" onClick={openAdd}>+ Добавить чат</button>
      </div>

      <div style={{ background: '#fff8e1', border: '1px solid #fde68a', borderRadius: 10, padding: '12px 16px', marginBottom: 20, fontSize: 13, color: '#78350f' }}>
        Чтобы узнать Chat ID: добавьте бота в чат, отправьте любое сообщение, и бот получит ID автоматически.
        Или используйте команду <strong>/chatid</strong> в чате с ботом.
      </div>

      <table className="admin-table">
        <thead><tr><th>Chat ID</th><th>Название чата</th><th>Статус</th><th>Действия</th></tr></thead>
        <tbody>
          {items.map(i => (
            <tr key={i.id}>
              <td style={{ fontFamily: 'monospace', fontSize: 13 }}>{i.chat_id}</td>
              <td>{i.name || '—'}</td>
              <td>
                <span style={{
                  display: 'inline-block', padding: '3px 10px', borderRadius: 20, fontSize: 12, fontWeight: 600,
                  background: i.active ? '#f0fdf4' : '#f9fafb',
                  color: i.active ? '#16a34a' : '#9ca3af',
                  border: `1px solid ${i.active ? '#bbf7d0' : '#e5e7eb'}`,
                }}>
                  {i.active ? 'Активен' : 'Отключён'}
                </span>
              </td>
              <td><div className="actions-cell">
                <button className="btn-edit" onClick={() => openEdit(i)}>Изменить</button>
                <button className="btn-edit" style={{ background: i.active ? '#fff7ed' : '#f0fdf4', color: i.active ? '#c2410c' : '#16a34a', borderColor: i.active ? '#fed7aa' : '#bbf7d0' }}
                  onClick={() => toggleActive(i)}>{i.active ? 'Откл.' : 'Вкл.'}</button>
                <button className="btn-del" onClick={() => del(i.id)}>Удалить</button>
              </div></td>
            </tr>
          ))}
          {!items.length && <tr><td colSpan={4} className="empty-row">Нет чатов</td></tr>}
        </tbody>
      </table>

      {modal && (
        <Modal title={modal === 'add' ? 'Добавить чат' : 'Редактировать чат'} onClose={() => setModal(null)}>
          {modal === 'add' && (
            <div className="form-group">
              <label className="form-label">Chat ID</label>
              <input className="form-input" value={form.chat_id} onChange={e => setForm(f => ({ ...f, chat_id: e.target.value }))} placeholder="-1001234567890" />
            </div>
          )}
          <div className="form-group">
            <label className="form-label">Название чата (для удобства)</label>
            <input className="form-input" value={form.name} onChange={e => setForm(f => ({ ...f, name: e.target.value }))} placeholder="Например: Жители района Северный" />
          </div>
          <div className="modal-footer">
            <button className="btn-cancel" onClick={() => setModal(null)}>Отмена</button>
            <button className="btn-save" onClick={save} disabled={modal === 'add' && !form.chat_id.trim()}>Сохранить</button>
          </div>
        </Modal>
      )}
    </div>
  );
}

// ── Tab: Отчёты ────────────────────────────────────────────────────────────

function ReportsTab() {
  const [from, setFrom] = useState('');
  const [to, setTo] = useState('');

  const exportExcel = async () => {
    const params = new URLSearchParams();
    if (from) params.set('from', from);
    if (to) params.set('to', to);
    try {
      const r = await fetch(`${API}/export?${params}`, { headers: authHeaders() });
      if (!r.ok) {
        const err = await r.json().catch(() => ({}));
        alert(err.error || 'Ошибка при скачивании отчёта');
        return;
      }
      const blob = await r.blob();
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url; a.download = 'report.xlsx'; a.click();
      URL.revokeObjectURL(url);
    } catch {
      alert('Ошибка подключения к серверу');
    }
  };

  return (
    <div className="tab-content">
      <div className="tab-toolbar">
        <div>
          <h2 className="tab-title">Отчёты</h2>
          <p className="tab-subtitle">Единый отчёт по рассылкам с портала и Telegram-бота</p>
        </div>
      </div>
      <div className="report-card">
        <h3>Экспорт в Excel</h3>
        <p style={{ fontSize: 13, color: '#6b7280', marginBottom: 20 }}>
          Включает рассылки из обоих источников: веб-портал и Telegram-бот.
        </p>
        <div className="date-row">
          <div className="form-group">
            <label className="form-label">Дата от</label>
            <input className="form-input" type="date" value={from} onChange={e => setFrom(e.target.value)} />
          </div>
          <div className="form-group">
            <label className="form-label">Дата до</label>
            <input className="form-input" type="date" value={to} onChange={e => setTo(e.target.value)} />
          </div>
        </div>
        <button className="btn-export" onClick={exportExcel}>Скачать Excel</button>
      </div>
    </div>
  );
}

// ── Tab: Карта ЧС (admin editable) ────────────────────────────────────────

const INNOPOLIS = [55.7525, 48.7442];

function MapTab() {
  const mapRef = useRef(null);
  const mapInstance = useRef(null);
  const markersRef = useRef([]);
  const tempMarkerRef = useRef(null);
  const [incidents, setIncidents] = useState([]);
  const [types, setTypes] = useState([]);
  const [dangerLevels, setDangerLevels] = useState([]);
  const [modal, setModal] = useState(null); // null | 'add' | incident object
  const [addLatLon, setAddLatLon] = useState(null);
  const [form, setForm] = useState({ title: '', description: '', emergency_type_id: '', danger_level_id: '', status: 'active' });

  const load = async () => {
    const [r1, r2, r3] = await Promise.all([
      fetch(`${API_BASE}/api/map/incidents`, { headers: authHeaders() }),
      fetch(`${API}/emergency-types`, { headers: authHeaders() }),
      fetch(`${API}/danger-levels`, { headers: authHeaders() }),
    ]);
    if (r1.ok) setIncidents(await r1.json());
    if (r2.ok) setTypes(await r2.json());
    if (r3.ok) setDangerLevels(await r3.json());
  };

  useEffect(() => { load(); }, []);

  // Init map once
  useEffect(() => {
    if (!mapRef.current || mapInstance.current) return;
    mapInstance.current = L.map(mapRef.current, { attributionControl: false }).setView(INNOPOLIS, 13);
    L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png').addTo(mapInstance.current);

    mapInstance.current.on('click', (e) => {
      const { lat, lng } = e.latlng;
      setAddLatLon([lat, lng]);
      setForm({ title: '', description: '', emergency_type_id: '', danger_level_id: '', status: 'active' });
      setModal('add');
    });

    return () => {
      if (mapInstance.current) { mapInstance.current.remove(); mapInstance.current = null; }
    };
  }, []);

  // Redraw markers on data change
  useEffect(() => {
    if (!mapInstance.current) return;
    markersRef.current.forEach(m => m.remove());
    markersRef.current = [];

    incidents.forEach(inc => {
      const color = inc.danger_color || '#ef4444';
      const marker = L.circleMarker([inc.lat, inc.lon], {
        radius: 12, fillColor: color, color: '#fff', weight: 2, opacity: 1, fillOpacity: 0.85,
      }).addTo(mapInstance.current);

      marker.bindTooltip(inc.title, { permanent: false, direction: 'top' });
      marker.on('click', (e) => {
        L.DomEvent.stopPropagation(e);
        setForm({
          title: inc.title,
          description: inc.description || '',
          emergency_type_id: inc.emergency_type_id || '',
          danger_level_id: inc.danger_level_id || '',
          status: inc.status || 'active',
        });
        setModal(inc);
      });
      markersRef.current.push(marker);
    });
  }, [incidents]);

  // Show temp marker while adding
  useEffect(() => {
    if (!mapInstance.current) return;
    if (tempMarkerRef.current) { tempMarkerRef.current.remove(); tempMarkerRef.current = null; }
    if (addLatLon && modal === 'add') {
      tempMarkerRef.current = L.circleMarker(addLatLon, {
        radius: 12, fillColor: '#22c55e', color: '#fff', weight: 2, opacity: 1, fillOpacity: 0.85,
      }).addTo(mapInstance.current);
      tempMarkerRef.current.bindTooltip('Новый инцидент', { permanent: true, direction: 'top' });
    }
  }, [addLatLon, modal]);

  const save = async () => {
    const body = {
      ...form,
      lat: addLatLon ? addLatLon[0] : modal.lat,
      lon: addLatLon ? addLatLon[1] : modal.lon,
    };
    if (modal === 'add') {
      await fetch(`${API_BASE}/api/map/incidents`, { method: 'POST', headers: jsonHeaders(), body: JSON.stringify(body) });
    } else {
      await fetch(`${API_BASE}/api/map/incidents/${modal.id}`, { method: 'PUT', headers: jsonHeaders(), body: JSON.stringify(body) });
    }
    if (tempMarkerRef.current) { tempMarkerRef.current.remove(); tempMarkerRef.current = null; }
    setModal(null); setAddLatLon(null); load();
  };

  const del = async (id) => {
    if (!confirm('Удалить инцидент с карты?')) return;
    await fetch(`${API_BASE}/api/map/incidents/${id}`, { method: 'DELETE', headers: authHeaders() });
    setModal(null); load();
  };

  const closeModal = () => {
    if (tempMarkerRef.current) { tempMarkerRef.current.remove(); tempMarkerRef.current = null; }
    setModal(null); setAddLatLon(null);
  };

  return (
    <div className="tab-content" style={{ padding: 0, display: 'flex', flexDirection: 'column', height: 'calc(100vh - 110px)' }}>
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', padding: '8px 20px', borderBottom: '1px solid var(--border)' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 16 }}>
          <span style={{ fontSize: 15, fontWeight: 700, color: 'var(--text-main)' }}>Карта ЧС</span>
          <span style={{ fontSize: 12, color: 'var(--text-muted)' }}>Нажмите на карту — добавить. На маркер — редактировать.</span>
        </div>
        <span style={{ fontSize: 12, color: 'var(--text-muted)' }}>Инцидентов: {incidents.length}</span>
      </div>
      <div ref={mapRef} style={{ flex: 1 }} />

      {modal && (
        <Modal title={modal === 'add' ? 'Добавить инцидент' : 'Редактировать инцидент'} onClose={closeModal}>
          <div className="form-group">
            <label className="form-label">Название</label>
            <input className="form-input" value={form.title} onChange={e => setForm(f => ({ ...f, title: e.target.value }))} placeholder="Например: Пожар на ул. Центральной" />
          </div>
          <div className="form-group">
            <label className="form-label">Описание</label>
            <textarea className="form-textarea" value={form.description} onChange={e => setForm(f => ({ ...f, description: e.target.value }))} placeholder="Подробности инцидента..." />
          </div>
          <div className="form-group">
            <label className="form-label">Вид ЧС</label>
            <select className="form-select" value={form.emergency_type_id} onChange={e => setForm(f => ({ ...f, emergency_type_id: e.target.value }))}>
              <option value="">— Не выбрано —</option>
              {types.map(t => <option key={t.id} value={t.id}>{t.name}</option>)}
            </select>
          </div>
          <div className="form-group">
            <label className="form-label">Уровень опасности</label>
            <select className="form-select" value={form.danger_level_id} onChange={e => setForm(f => ({ ...f, danger_level_id: e.target.value }))}>
              <option value="">— Не выбрано —</option>
              {dangerLevels.map(d => <option key={d.id} value={d.id}>{d.name} ({d.emergency_type_name || 'без типа'})</option>)}
            </select>
          </div>
          <div className="form-group">
            <label className="form-label">Статус</label>
            <select className="form-select" value={form.status} onChange={e => setForm(f => ({ ...f, status: e.target.value }))}>
              <option value="active">Активный</option>
              <option value="resolved">Завершён</option>
            </select>
          </div>
          {modal !== 'add' && (
            <div style={{ marginBottom: 12 }}>
              <p style={{ fontSize: 12, color: 'var(--text-muted)', margin: 0 }}>
                Координаты: {modal.lat?.toFixed(5)}, {modal.lon?.toFixed(5)}
              </p>
            </div>
          )}
          <div className="modal-footer" style={{ justifyContent: modal !== 'add' ? 'space-between' : 'flex-end' }}>
            {modal !== 'add' && (
              <button className="btn-del" onClick={() => del(modal.id)}>Удалить</button>
            )}
            <div style={{ display: 'flex', gap: 8 }}>
              <button className="btn-cancel" onClick={closeModal}>Отмена</button>
              <button className="btn-save" onClick={save} disabled={!form.title.trim()}>Сохранить</button>
            </div>
          </div>
        </Modal>
      )}
    </div>
  );
}

// ── Main Admin Page ────────────────────────────────────────────────────────

const TABS = [
  { key: 'types',     label: 'Виды ЧС' },
  { key: 'danger',    label: 'Типы опасности' },
  { key: 'templates', label: 'Шаблоны' },
  { key: 'chats',     label: 'Telegram-чаты' },
  { key: 'reports',   label: 'Отчёты' },
  { key: 'map',       label: 'Карта ЧС' },
];

export default function Admin() {
  const navigate = useNavigate();
  const [tab, setTab] = useState('types');
  const [dark, setDark] = useTheme();
  const role = localStorage.getItem('role');
  const username = localStorage.getItem('username');

  const handleLogout = () => {
    localStorage.removeItem('token');
    localStorage.removeItem('username');
    localStorage.removeItem('role');
    navigate('/');
  };

  if (role !== 'superuser') {
    return (
      <div className="dashboard-page">
        <header className="dashboard-header">
          <div className="header-left"><div className="header-logo" /><span className="header-title">Портал</span></div>
          <div className="header-right"><button className="btn-logout" onClick={handleLogout}>Выйти</button></div>
        </header>
        <div className="access-denied">
          <h2>Доступ запрещён</h2>
          <p>Эта страница доступна только суперпользователям.</p>
          <button className="btn-save" onClick={() => navigate('/dashboard')}>На главную</button>
        </div>
      </div>
    );
  }

  return (
    <div className="admin-page">
      <header className="dashboard-header">
        <div className="header-left">
          <button className="btn-theme" onClick={() => setDark(d => !d)} title="Сменить тему">
            {dark ? 'L' : 'D'}
          </button>
          <span className="header-title">Администрирование</span>
        </div>
        <div className="header-right">
          <span className="header-user">{username}</span>
          <button className="btn-logout" onClick={() => navigate('/dashboard')}>← На портал</button>
          <button className="btn-logout" onClick={handleLogout}>Выйти</button>
        </div>
      </header>

      <nav className="admin-tabs">
        {TABS.map(t => (
          <button key={t.key} className={`admin-tab ${tab === t.key ? 'active' : ''}`} onClick={() => setTab(t.key)}>
            {t.label}
          </button>
        ))}
      </nav>

      {tab === 'types'     && <EmergencyTypesTab />}
      {tab === 'danger'    && <DangerLevelsTab />}
      {tab === 'templates' && <TemplatesTab />}
      {tab === 'chats'     && <TelegramChatsTab />}
      {tab === 'reports'   && <ReportsTab />}
      {tab === 'map'       && <MapTab />}
    </div>
  );
}
