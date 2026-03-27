import { useEffect, useRef, useState } from 'react';
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

const INNOPOLIS = [55.7525, 48.7442];
const API_BASE = import.meta.env.VITE_API_URL || 'http://localhost:3001';

function authHeaders() {
  return { Authorization: `Bearer ${localStorage.getItem('token')}` };
}

export default function MapPage() {
  const navigate = useNavigate();
  const [dark, setDark] = useTheme();
  const mapRef = useRef(null);
  const mapInstance = useRef(null);
  const markersRef = useRef([]);
  const [incidents, setIncidents] = useState([]);
  const [selected, setSelected] = useState(null);
  const username = localStorage.getItem('username') || '';

  const loadIncidents = async () => {
    try {
      const r = await fetch(`${API_BASE}/api/map/incidents`, { headers: authHeaders() });
      if (r.ok) setIncidents(await r.json());
    } catch { /* ignore */ }
  };

  useEffect(() => {
    loadIncidents();
    const interval = setInterval(loadIncidents, 15000);
    return () => clearInterval(interval);
  }, []);

  // Init map
  useEffect(() => {
    if (!mapRef.current || mapInstance.current) return;
    mapInstance.current = L.map(mapRef.current, { attributionControl: false }).setView(INNOPOLIS, 13);
    L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png').addTo(mapInstance.current);
    return () => {
      if (mapInstance.current) {
        mapInstance.current.remove();
        mapInstance.current = null;
      }
    };
  }, []);

  // Draw markers
  useEffect(() => {
    if (!mapInstance.current) return;
    markersRef.current.forEach(m => m.remove());
    markersRef.current = [];

    incidents.forEach(inc => {
      const color = inc.danger_color || '#ef4444';
      const marker = L.circleMarker([inc.lat, inc.lon], {
        radius: 12,
        fillColor: color,
        color: '#fff',
        weight: 2,
        opacity: 1,
        fillOpacity: 0.85,
      }).addTo(mapInstance.current);

      marker.bindPopup(`
        <div style="min-width:180px">
          <strong style="font-size:14px">${inc.title}</strong><br/>
          ${inc.emergency_type_name ? `<span style="color:#6b7280;font-size:12px">${inc.emergency_type_name}</span><br/>` : ''}
          ${inc.danger_level_name ? `<span style="color:${color};font-size:12px;font-weight:600">${inc.danger_level_name}</span><br/>` : ''}
          ${inc.description ? `<p style="margin:6px 0 0;font-size:13px">${inc.description}</p>` : ''}
          <p style="margin:4px 0 0;font-size:11px;color:#9ca3af">
            Статус: ${inc.status === 'active' ? 'Активный' : 'Завершён'}
          </p>
        </div>
      `);
      marker.on('click', () => setSelected(inc));
      markersRef.current.push(marker);
    });
  }, [incidents]);

  const handleLogout = () => {
    localStorage.removeItem('token');
    localStorage.removeItem('username');
    localStorage.removeItem('role');
    navigate('/');
  };

  const activeCount = incidents.filter(i => i.status === 'active').length;

  return (
    <div className="dashboard-page" style={{ display: 'flex', flexDirection: 'column', minHeight: '100vh' }}>
      <header className="dashboard-header">
        <div className="header-left">
          <button className="btn-theme" onClick={() => setDark(d => !d)} title="Сменить тему">
            {dark ? 'L' : 'D'}
          </button>
          <span className="header-title">Карта ЧС</span>
        </div>
        <div className="header-right">
          <span className="header-user">{username}</span>
          <button className="btn-logout" onClick={() => navigate('/dashboard')}>← На портал</button>
          <button className="btn-logout" onClick={handleLogout}>Выйти</button>
        </div>
      </header>

      <div style={{ display: 'flex', flex: 1, overflow: 'hidden' }}>
        {/* Sidebar */}
        <div style={{
          width: 280,
          background: 'var(--bg-card)',
          borderRight: '1px solid var(--border)',
          display: 'flex',
          flexDirection: 'column',
          overflow: 'hidden',
        }}>
          <div style={{ padding: '16px', borderBottom: '1px solid var(--border)' }}>
            <h3 style={{ margin: 0, fontSize: 15, color: 'var(--text-main)', fontWeight: 700 }}>
              Инциденты ЧС
            </h3>
            <p style={{ margin: '4px 0 0', fontSize: 12, color: 'var(--text-muted)' }}>
              Активных: {activeCount} из {incidents.length}
            </p>
          </div>
          <div style={{ overflowY: 'auto', flex: 1 }}>
            {incidents.length === 0 && (
              <p style={{ padding: 16, fontSize: 13, color: 'var(--text-muted)', textAlign: 'center' }}>
                Нет данных
              </p>
            )}
            {incidents.map(inc => (
              <div
                key={inc.id}
                onClick={() => {
                  setSelected(inc);
                  mapInstance.current?.setView([inc.lat, inc.lon], 15);
                }}
                style={{
                  padding: '12px 16px',
                  cursor: 'pointer',
                  borderBottom: '1px solid var(--border)',
                  background: selected?.id === inc.id ? 'var(--bg-row-alt)' : 'transparent',
                  transition: 'background 0.15s',
                }}
              >
                <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                  <span style={{
                    width: 10, height: 10, borderRadius: '50%',
                    background: inc.danger_color || '#ef4444',
                    flexShrink: 0,
                  }} />
                  <strong style={{ fontSize: 13, color: 'var(--text-main)' }}>{inc.title}</strong>
                </div>
                {inc.emergency_type_name && (
                  <p style={{ margin: '3px 0 0 18px', fontSize: 11, color: 'var(--text-muted)' }}>
                    {inc.emergency_type_name}
                    {inc.danger_level_name && ` · ${inc.danger_level_name}`}
                  </p>
                )}
                <p style={{ margin: '2px 0 0 18px', fontSize: 11, color: inc.status === 'active' ? '#16a34a' : '#9ca3af' }}>
                  {inc.status === 'active' ? 'Активный' : 'Завершён'}
                </p>
              </div>
            ))}
          </div>
        </div>

        {/* Map */}
        <div ref={mapRef} style={{ flex: 1 }} />
      </div>

      {/* Incident detail panel */}
      {selected && (
        <div style={{
          position: 'fixed', bottom: 24, right: 24,
          background: 'var(--bg-card)',
          border: '1px solid var(--border)',
          borderRadius: 12,
          padding: '16px 20px',
          minWidth: 260,
          maxWidth: 320,
          boxShadow: '0 4px 24px rgba(0,0,0,0.15)',
          zIndex: 1000,
        }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
            <strong style={{ fontSize: 15, color: 'var(--text-main)' }}>{selected.title}</strong>
            <button onClick={() => setSelected(null)} style={{
              background: 'none', border: 'none', cursor: 'pointer',
              fontSize: 18, color: 'var(--text-muted)', padding: 0, lineHeight: 1,
            }}>×</button>
          </div>
          {selected.emergency_type_name && (
            <p style={{ margin: '6px 0 0', fontSize: 13, color: 'var(--text-muted)' }}>
              {selected.emergency_type_name}
            </p>
          )}
          {selected.danger_level_name && (
            <p style={{ margin: '4px 0 0', fontSize: 13, fontWeight: 600, color: selected.danger_color || '#ef4444' }}>
              {selected.danger_level_name}
            </p>
          )}
          {selected.description && (
            <p style={{ margin: '8px 0 0', fontSize: 13, color: 'var(--text-main)', lineHeight: 1.5 }}>
              {selected.description}
            </p>
          )}
          <p style={{ margin: '8px 0 0', fontSize: 12, color: selected.status === 'active' ? '#16a34a' : '#9ca3af' }}>
            Статус: {selected.status === 'active' ? 'Активный' : 'Завершён'}
          </p>
        </div>
      )}
    </div>
  );
}
