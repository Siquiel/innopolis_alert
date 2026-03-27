import { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import logoSrc from '../assets/logo.png';

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
        <img src={logoSrc} alt="InnoAlert" style={{ width: '420px', maxWidth: '90%', filter: 'brightness(0) invert(1)', marginBottom: '16px' }} />
        <h2 className="login-brand-title">InnoAlert</h2>
        <p className="login-brand-sub">Система оповещения об экстренных ситуациях</p>
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
