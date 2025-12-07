import React, { useState, useEffect } from 'react';
import { apiService } from '../apiService';

const SessionManager = ({ currentSessionId, onSessionChange, onNewSession, theme, isUnsaved, onSaveClick }) => {
  const [sessions, setSessions] = useState([]);
  const [isLoading, setIsLoading] = useState(true);
  const [isCollapsed, setIsCollapsed] = useState(false);

  useEffect(() => {
    loadSessions();
  }, []);

  // Reload sessions when currentSessionId changes (might be a new saved session)
  useEffect(() => {
    if (currentSessionId) {
      loadSessions();
    }
  }, [currentSessionId]);

  const loadSessions = async () => {
    try {
      const sessionList = await apiService.getSessions();
      setSessions(sessionList);
    } catch (error) {
      console.error('Error loading sessions:', error);
    } finally {
      setIsLoading(false);
    }
  };

  const handleNewConversa = () => {
    // Just start a new unsaved chat (no session)
    onNewSession(null);
  };

  const handleDeleteSession = async (sessionId) => {
    // Delete directly without confirmation
    try {
      await apiService.deleteSession(sessionId);
      setSessions(prev => prev.filter(s => s.id !== sessionId));
      
      // If we deleted the current session, switch to the first available session
      if (sessionId === currentSessionId) {
        const remainingSessions = sessions.filter(s => s.id !== sessionId);
        if (remainingSessions.length > 0) {
          onSessionChange(remainingSessions[0].id);
        } else {
          onNewSession(null); // Create new session
        }
      }
    } catch (error) {
      console.error('Error deleting session:', error);
    }
  };

  if (isLoading) {
    return (
      <div className={`session-manager ${isCollapsed ? 'collapsed' : ''}`}>
        <div className="loading">Carregant converses...</div>
      </div>
    );
  }

  return (
    <div className={`session-manager ${isCollapsed ? 'collapsed' : ''}`}>
      <div className="session-header">
        {!isCollapsed && (
          <>
            <div className="session-header-top">
              <h3>Converses</h3>
              <div className="session-header-actions">
                <button 
                  onClick={handleNewConversa}
                  className="new-session-btn"
                  title="Nova conversa"
                >
                  +
                </button>
                {isUnsaved && (
                  <button 
                    onClick={onSaveClick}
                    className="save-chat-btn-small"
                    title="Guardar conversa"
                  >
                    <svg width="16" height="16" viewBox="0 0 16 16" fill="none" xmlns="http://www.w3.org/2000/svg">
                      <path d="M3 2H11L13 4V13H3V2Z" stroke="currentColor" strokeWidth="1.5" fill="none"/>
                      <path d="M3 2V6H11V2" stroke="currentColor" strokeWidth="1.5" fill="none"/>
                      <rect x="6" y="8" width="4" height="1" fill="currentColor"/>
                      <rect x="6" y="10" width="4" height="1" fill="currentColor"/>
                    </svg>
                  </button>
                )}
              </div>
              <button 
                className="collapse-btn"
                onClick={() => setIsCollapsed(!isCollapsed)}
                title="Ocultar converses"
              >
                ◀
              </button>
            </div>
          </>
        )}
        {isCollapsed && (
          <button 
            className="collapse-btn"
            onClick={() => setIsCollapsed(!isCollapsed)}
            title="Mostrar converses"
          >
            ▶
          </button>
        )}
      </div>

      {!isCollapsed && (
        <div className="session-list">
        {sessions.length === 0 ? (
          <div className="no-sessions">
            <p>No tens converses encara.</p>
            <p>Crea la teva primera conversa!</p>
          </div>
        ) : (
          sessions.map(session => (
            <div 
              key={session.id}
              className={`session-item ${session.id === currentSessionId ? 'active' : ''}`}
              onClick={() => onSessionChange(session.id)}
            >
              <div className="session-title">{session.title}</div>
              <div className="session-meta">
                <span className="message-count">{session.message_count} missatges</span>
                <span className="session-date">
                  {new Date(session.updated_at).toLocaleDateString('ca-ES')}
                </span>
              </div>
              <button 
                className="delete-session-btn"
                onClick={(e) => {
                  e.stopPropagation();
                  handleDeleteSession(session.id);
                }}
                title="Esborrar conversa"
              >
                ×
              </button>
            </div>
          ))
        )}
        </div>
      )}
    </div>
  );
};

export default SessionManager;
