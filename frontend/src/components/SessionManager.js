import React, { useState, useEffect } from 'react';
import { apiService } from '../apiService';
import PilarLoader from './PilarLoader';

const SessionManager = ({ currentSessionId, onSessionChange, onNewSession, theme, isUnsaved, onSaveClick }) => {
  const [sessions, setSessions] = useState([]);
  const [isLoading, setIsLoading] = useState(true);
  // Check if mobile on initial render to collapse by default on mobile
  const [isCollapsed, setIsCollapsed] = useState(() => {
    return typeof window !== 'undefined' && window.innerWidth <= 768;
  });
  const [isMobile, setIsMobile] = useState(() => {
    return typeof window !== 'undefined' && window.innerWidth <= 768;
  });

  // Listen for window resize to update mobile state
  useEffect(() => {
    const handleResize = () => {
      const mobile = window.innerWidth <= 768;
      setIsMobile(mobile);
      // Auto-collapse when switching to mobile
      if (mobile && !isMobile) {
        setIsCollapsed(true);
      }
    };

    window.addEventListener('resize', handleResize);
    return () => window.removeEventListener('resize', handleResize);
  }, [isMobile]);

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

  // Check if theme color is white (use gray instead)
  const isWhiteTheme = theme?.secondary && 
    (theme.secondary.toLowerCase() === '#ffffff' || 
     theme.secondary.toLowerCase() === '#fff' ||
     theme.secondary.toLowerCase() === 'white');
  
  // Button color for collapsed state on mobile
  const collapsedBtnStyle = isMobile && isCollapsed ? {
    background: isWhiteTheme ? '#808080' : (theme?.secondary || '#d0282c'),
  } : {};

  return (
    <>
      {/* Mobile backdrop overlay - click to close sidebar */}
      {isMobile && !isCollapsed && (
        <div 
          className="session-manager-backdrop"
          onClick={() => setIsCollapsed(true)}
        />
      )}
      <div className={`session-manager ${isCollapsed ? 'collapsed' : ''}`}>
        {/* Header is always visible */}
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
              style={collapsedBtnStyle}
            >
              ▶
            </button>
          )}
        </div>

        {/* Session list - shows loader only here */}
        {!isCollapsed && (
          <div className="session-list">
            {isLoading ? (
              <div className="session-list-loading">
                <PilarLoader />
              </div>
            ) : sessions.length === 0 ? (
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
    </>
  );
};

export default SessionManager;
