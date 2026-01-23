import React, { useState, useEffect, useRef } from 'react';
import LoginForm from './LoginForm';

const Header = ({ user, onLogin, onLogout, theme, currentPage = 'chat', onPageChange, onOpenProfile, onOpenAbout }) => {
  const [showLogin, setShowLogin] = useState(false);
  const [showSettingsDropdown, setShowSettingsDropdown] = useState(false);
  const [showShareModal, setShowShareModal] = useState(false);
  const [copied, setCopied] = useState(false);
  const dropdownRef = useRef(null);

  const handleLoginSuccess = (userData) => {
    onLogin(userData);
    setShowLogin(false);
  };

  // Close dropdown when clicking outside
  useEffect(() => {
    const handleClickOutside = (event) => {
      if (dropdownRef.current && !dropdownRef.current.contains(event.target)) {
        setShowSettingsDropdown(false);
      }
    };

    document.addEventListener('mousedown', handleClickOutside);
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, []);

  const getInitials = (name) => {
    if (!name) return '?';
    const parts = name.trim().split(/\s+/);
    if (parts.length >= 2) {
      return (parts[0][0] + parts[parts.length - 1][0]).toUpperCase();
    }
    return name.substring(0, 2).toUpperCase();
  };

  const handleProfileClick = () => {
    setShowSettingsDropdown(false);
    if (onOpenProfile) {
      onOpenProfile();
    }
  };

  const handleSettingsItemClick = (action) => {
    setShowSettingsDropdown(false);
    
    switch (action) {
      case 'logout':
        onLogout();
        break;
      case 'profile':
        if (onOpenProfile) {
          onOpenProfile();
        }
        break;
      case 'share':
        setShowShareModal(true);
        break;
      case 'about':
        if (onOpenAbout) {
          onOpenAbout();
        }
        break;
      case 'contact':
        if (onPageChange) {
          onPageChange('contact');
        }
        break;
      default:
        break;
    }
  };

  const isWhiteTheme = theme?.secondary === '#ffffff';
  
  return (
    <>
      <header 
        className={`header ${isWhiteTheme ? 'header-white-theme' : ''}`} 
        style={{ '--theme-color': theme?.secondary, '--theme-accent': theme?.accent }}
      >
        <div className="header-logo">
          <img src="/xiquet_images/xiquet_logo.png" alt="Xiquet AI" width="55" height="55" />
          <h1>Xiquet AI</h1>
        </div>
        <div className="header-nav">
          {user && (
            <nav className="header-nav-buttons">
              <button 
                className={`header-nav-btn ${currentPage === 'chat' ? 'active' : ''}`}
                onClick={() => onPageChange && onPageChange('chat')}
              >
                Xat
              </button>
              <button 
                className={`header-nav-btn ${currentPage === 'joc-del-mocador' ? 'active' : ''}`}
                onClick={() => onPageChange && onPageChange('joc-del-mocador')}
              >
                El Joc del Mocador
              </button>
            </nav>
          )}
        </div>
        <div className="user-info">
          {user ? (
            <div className="user-controls">
              {/* Profile Avatar Button */}
              <button 
                className="profile-avatar-btn"
                onClick={handleProfileClick}
                title={`Perfil de ${user.username}`}
              >
                <span 
                  className={`profile-avatar-circle ${isWhiteTheme ? 'white-theme' : ''}`}
                  style={{ backgroundColor: isWhiteTheme ? '#ffffff' : (theme?.secondary || '#d0282c') }}
                >
                  {getInitials(user.username)}
                </span>
              </button>

              {/* Settings Button with Dropdown */}
              <div className="settings-dropdown-container" ref={dropdownRef}>
                <button 
                  className={`settings-btn ${showSettingsDropdown ? 'active' : ''}`}
                  onClick={() => setShowSettingsDropdown(!showSettingsDropdown)}
                  title="Configuració"
                >
                  <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                    <circle cx="12" cy="12" r="3" />
                    <path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 0 1 0 2.83 2 2 0 0 1-2.83 0l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 0 1-2 2 2 2 0 0 1-2-2v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 0 1-2.83 0 2 2 0 0 1 0-2.83l.06-.06a1.65 1.65 0 0 0 .33-1.82 1.65 1.65 0 0 0-1.51-1H3a2 2 0 0 1-2-2 2 2 0 0 1 2-2h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 0 1 0-2.83 2 2 0 0 1 2.83 0l.06.06a1.65 1.65 0 0 0 1.82.33H9a1.65 1.65 0 0 0 1-1.51V3a2 2 0 0 1 2-2 2 2 0 0 1 2 2v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 0 1 2.83 0 2 2 0 0 1 0 2.83l-.06.06a1.65 1.65 0 0 0-.33 1.82V9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 0 1 2 2 2 2 0 0 1-2 2h-.09a1.65 1.65 0 0 0-1.51 1z" />
                  </svg>
                </button>

                {showSettingsDropdown && (
                  <div className="settings-dropdown">
                    <button 
                      className="settings-dropdown-item"
                      onClick={() => handleSettingsItemClick('profile')}
                    >
                      <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                        <path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2" />
                        <circle cx="12" cy="7" r="4" />
                      </svg>
                      Perfil
                    </button>
                    
                    <button 
                      className="settings-dropdown-item"
                      onClick={() => handleSettingsItemClick('share')}
                    >
                      <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                        <circle cx="18" cy="5" r="3" />
                        <circle cx="6" cy="12" r="3" />
                        <circle cx="18" cy="19" r="3" />
                        <line x1="8.59" y1="13.51" x2="15.42" y2="17.49" />
                        <line x1="15.41" y1="6.51" x2="8.59" y2="10.49" />
                      </svg>
                      Compartir Xiquet
                    </button>
                    
                    <button 
                      className="settings-dropdown-item"
                      onClick={() => handleSettingsItemClick('about')}
                    >
                      <img 
                        src="/xiquet_images/xiquet_logo_zoom.png" 
                        alt="Xiquet" 
                        width="16" 
                        height="16" 
                        style={{ objectFit: 'contain' }}
                      />
                      Sobre Xiquet AI
                    </button>
                    
                    <button 
                      className="settings-dropdown-item"
                      onClick={() => handleSettingsItemClick('contact')}
                    >
                      <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                        <path d="M4 4h16c1.1 0 2 .9 2 2v12c0 1.1-.9 2-2 2H4c-1.1 0-2-.9-2-2V6c0-1.1.9-2 2-2z" />
                        <polyline points="22,6 12,13 2,6" />
                      </svg>
                      Contacte
                    </button>
                    
                    <div className="settings-dropdown-divider"></div>
                    
                    <button 
                      className="settings-dropdown-item"
                      onClick={() => handleSettingsItemClick('logout')}
                    >
                      <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                        <path d="M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4" />
                        <polyline points="16 17 21 12 16 7" />
                        <line x1="21" y1="12" x2="9" y2="12" />
                      </svg>
                      Sortir
                    </button>
                  </div>
                )}
              </div>
            </div>
          ) : (
            <button onClick={() => setShowLogin(true)}>Entrar</button>
          )}
        </div>
        
        {showLogin && (
          <LoginForm 
            onLogin={handleLoginSuccess}
            onClose={() => setShowLogin(false)}
          />
        )}
      </header>
      <div className="header-border-bottom"></div>

      {/* Share Modal */}
      {showShareModal && (
        <div className="share-modal-overlay" onClick={() => setShowShareModal(false)}>
          <div className="share-modal" onClick={(e) => e.stopPropagation()}>
            <button 
              className="share-modal-close"
              onClick={() => setShowShareModal(false)}
            >
              <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                <line x1="18" y1="6" x2="6" y2="18" />
                <line x1="6" y1="6" x2="18" y2="18" />
              </svg>
            </button>
            
            
            <h2>Comparteix Xiquet AI</h2>
            
            <div className="share-modal-link-container">
              <input 
                type="text" 
                value="www.xiquet.cat" 
                readOnly 
                className="share-modal-link-input"
              />
              <button 
                className={`share-modal-copy-btn ${copied ? 'copied' : ''}`}
                onClick={() => {
                  navigator.clipboard.writeText('https://www.xiquet.cat');
                  setCopied(true);
                  setTimeout(() => setCopied(false), 2000);
                }}
              >
                {copied ? (
                  <>
                    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                      <polyline points="20 6 9 17 4 12" />
                    </svg>
                    Copiat!
                  </>
                ) : (
                  <>
                    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                      <rect x="9" y="9" width="13" height="13" rx="2" ry="2" />
                      <path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1" />
                    </svg>
                    Copiar
                  </>
                )}
              </button>
            </div>
          </div>
        </div>
      )}
    </>
  );
};

export default Header;
