import { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';

function useTheme() {
  const [dark, setDark] = useState(() => localStorage.getItem('theme') === 'dark');
  useEffect(() => {
    document.body.classList.toggle('dark', dark);
    localStorage.setItem('theme', dark ? 'dark' : 'light');
  }, [dark]);
  return [dark, setDark];
}

export default function Dashboard() {
  const navigate = useNavigate();
  const [username, setUsername] = useState('');
  const [role, setRole] = useState('');
  const [dark, setDark] = useTheme();

  useEffect(() => {
    setUsername(localStorage.getItem('username') || '');
    setRole(localStorage.getItem('role') || '');
  }, []);

  const handleLogout = () => {
    localStorage.removeItem('token');
    localStorage.removeItem('username');
    localStorage.removeItem('role');
    navigate('/');
  };

  return (
    <div className="dashboard-page">
      <header className="dashboard-header">
        <div className="header-left">
          <button className="btn-theme" onClick={() => setDark(d => !d)} title="Сменить тему">
            {dark ? 'L' : 'D'}
          </button>
          <span className="header-title">Портал</span>
        </div>
        <div className="header-right">
          <span className="header-user">{username}</span>
          <button className="btn-logout" onClick={handleLogout}>Выйти</button>
        </div>
      </header>

      <main className="dashboard-main">
        <div className="welcome-card">
          <div className="welcome-accent" />
          <h2 className="welcome-title">Вы успешно вошли</h2>
          <p className="welcome-text">
            Добро пожаловать, <span className="welcome-name">{username}</span>
          </p>
        </div>

        <button className="btn-map-center" onClick={() => navigate('/map')}>
          Карта ЧС
        </button>

        {role === 'superuser' && (
          <button className="btn-admin-center" onClick={() => navigate('/admin')}>
            Администрирование
          </button>
        )}
      </main>

      <div className="footer-stripe" />

      <footer className="site-footer">
        <div className="footer-inner">
          <div className="footer-col">
            <div className="footer-logo-block" />
            <span className="footer-brand">InnoAlert</span>
            <p className="footer-desc">Система оповещения об экстренных ситуациях</p>
          </div>
          <div className="footer-col">
            <h4 className="footer-heading">Контакты</h4>
            <p className="footer-contact">+7 (843) 000-00-00</p>
            <p className="footer-contact">alert@innopolis.ru</p>
            <p className="footer-contact">Иннополис, ул. Университетская, 1</p>
          </div>
          <div className="footer-col">
            <h4 className="footer-heading">Экстренные службы</h4>
            <p className="footer-contact">Пожарная: 101</p>
            <p className="footer-contact">Скорая: 103</p>
            <p className="footer-contact">Полиция: 102</p>
          </div>
        </div>
        <div className="footer-bottom">
          © {new Date().getFullYear()} InnoAlert. Все права защищены.
        </div>
      </footer>
    </div>
  );
}
