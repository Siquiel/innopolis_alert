import { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';

export default function Login() {
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);
  const [dark, setDark] = useState(false);
  const navigate = useNavigate();

  // Применяем сохранённую тему
  useEffect(() => {
    const saved = localStorage.getItem('theme');
    const isDark = saved === 'dark';
    setDark(isDark);
    document.body.classList.toggle('dark', isDark);
  }, []);

  const toggleTheme = () => {
    const next = !dark;
    setDark(next);
    document.body.classList.toggle('dark', next);
    localStorage.setItem('theme', next ? 'dark' : 'light');
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    setLoading(true);
    setError('');
    try {
      const res = await fetch(`${import.meta.env.VITE_API_URL || 'http://localhost:3001'}/api/login`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ username, password }),
      });
      const data = await res.json();
      if (!res.ok) { setError(data.error); return; }
      localStorage.setItem('token', data.token);
      localStorage.setItem('username', data.username);
      localStorage.setItem('role', data.role);
      navigate('/dashboard');
    } catch {
      setError('Ошибка подключения к серверу');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="login-page">
      {/* Левая панель — брендинг */}
      <div className="login-brand">
        <div className="login-brand-logo">
          <svg viewBox="0 0 56 56" fill="none" xmlns="http://www.w3.org/2000/svg" style={{width:'100%',height:'100%',padding:'10px'}}>
            <path d="M28 8L8 44h40L28 8z" fill="rgba(34,197,94,0.9)" stroke="#fff" strokeWidth="2.5" strokeLinejoin="round"/>
            <rect x="25" y="26" width="6" height="10" rx="1.5" fill="#fff"/>
            <rect x="25" y="20" width="6" height="5" rx="1.5" fill="#fff"/>
          </svg>
        </div>
        <h2 className="login-brand-title">InnoAlert</h2>
        <p className="login-brand-sub">Система оповещения об экстренных ситуациях</p>
        <div className="login-brand-badges">
          <span className="login-badge">Пожар</span>
          <span className="login-badge">Наводнение</span>
          <span className="login-badge">ЧС</span>
          <span className="login-badge">Оповещение</span>
        </div>
      </div>

      {/* Правая панель — форма */}
      <div className="login-form-side">
        <button className="login-theme-toggle" onClick={toggleTheme} title={dark ? 'Светлая тема' : 'Тёмная тема'}>
          {dark ? '☀️' : '🌙'}
        </button>
        <div className="login-card">
          <div className="login-header">
            <h1 className="login-title">Вход в систему</h1>
            <p className="login-subtitle">Введите данные для доступа к порталу</p>
          </div>

          <form onSubmit={handleSubmit} className="login-form">
            <div className="form-group">
              <label className="form-label">Логин</label>
              <input
                className="form-input"
                type="text"
                value={username}
                onChange={(e) => setUsername(e.target.value)}
                placeholder="Введите логин"
                autoComplete="username"
                required
              />
            </div>

            <div className="form-group">
              <label className="form-label">Пароль</label>
              <input
                className="form-input"
                type="password"
                value={password}
                onChange={(e) => setPassword(e.target.value.replace(/\s/g, ''))}
                placeholder="Введите пароль"
                autoComplete="current-password"
                required
              />
            </div>

            {error && <div className="form-error">{error}</div>}

            <button className="btn-login" type="submit" disabled={loading}>
              {loading ? 'Загрузка...' : 'Войти'}
            </button>
          </form>
        </div>
      </div>
    </div>
  );
}
