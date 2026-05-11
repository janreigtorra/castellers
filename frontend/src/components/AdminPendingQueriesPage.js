import React, { useEffect, useState } from 'react';
import { apiService } from '../apiService';
import './AdminPendingQueriesPage.css';

const formatWhen = (iso) => {
  if (!iso) return '—';
  try {
    return new Date(iso).toLocaleString('ca-ES', {
      dateStyle: 'short',
      timeStyle: 'short',
    });
  } catch {
    return iso;
  }
};

const AdminPendingQueriesPage = ({ theme, onBack }) => {
  const [items, setItems] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      setLoading(true);
      setError(null);
      try {
        const data = await apiService.getAdminPendingQueries();
        if (!cancelled) setItems(data.items || []);
      } catch (e) {
        if (!cancelled) {
          const msg =
            e.response?.status === 403
              ? 'No tens permisos per veure aquesta pàgina.'
              : "No s'han pogut carregar les dades.";
          setError(msg);
        }
      } finally {
        if (!cancelled) setLoading(false);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, []);

  const handleBack = () => {
    window.history.pushState({}, '', '/');
    if (onBack) onBack();
    else window.dispatchEvent(new PopStateEvent('popstate'));
  };

  return (
    <div
      className="admin-queries-page"
      style={{
        '--theme-color': theme?.secondary,
        '--theme-accent': theme?.accent,
      }}
    >
      <div className="admin-queries-inner">
        <button type="button" onClick={handleBack} className="admin-queries-back">
          ← Tornar al xat
        </button>

        <header className="admin-queries-header">
          <h1>Seguiment de consultes</h1>
          <p className="admin-queries-sub">
            {
              "Consultes dels usuaris (més noves primer). Les teves consultes no s'inclouen en aquest llistat."
            }
          </p>
        </header>

        {loading && (
          <p className="admin-queries-muted">Carregant…</p>
        )}
        {error && <p className="admin-queries-error">{error}</p>}

        {!loading && !error && items.length === 0 && (
          <p className="admin-queries-muted">No hi ha registres per mostrar.</p>
        )}

        <ul className="admin-queries-list">
          {items.map((row) => (
            <li key={row.id} className="admin-queries-card">
              <div className="admin-queries-card-top">
                <span className="admin-queries-name">
                  {row.username?.trim() || 'Sense nom al perfil'}
                </span>
                <span className="admin-queries-when">{formatWhen(row.created_at)}</span>
                <span
                  className={`admin-queries-status admin-queries-status--${(row.status || '').replace(/_/g, '-')}`}
                >
                  {row.status || '—'}
                </span>
              </div>
              {row.route_used && (
                <div className="admin-queries-route">Ruta: {row.route_used}</div>
              )}
              <div className="admin-queries-question">
                {row.content}
              </div>
              <details className="admin-queries-details">
                <summary>Resposta / detall</summary>
                {row.error_message && (
                  <div className="admin-queries-error-block">{row.error_message}</div>
                )}
                {row.response ? (
                  <pre className="admin-queries-response">{row.response}</pre>
                ) : (
                  !row.error_message && (
                    <p className="admin-queries-muted">Encara sense resposta registrada.</p>
                  )
                )}
              </details>
            </li>
          ))}
        </ul>
      </div>
    </div>
  );
};

export default AdminPendingQueriesPage;
