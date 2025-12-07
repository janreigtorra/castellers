import React, { useState } from 'react';
import LoginForm from './LoginForm';

const Header = ({ user, onLogin, onLogout, theme, currentPage = 'chat', onPageChange }) => {
  const [showLogin, setShowLogin] = useState(false);

  const handleLoginSuccess = (userData) => {
    onLogin(userData);
    setShowLogin(false);
  };

  const isWhiteTheme = theme?.secondary === '#ffffff';
  
  return (
    <>
      <header 
        className={`header ${isWhiteTheme ? 'header-white-theme' : ''}`} 
        style={{ '--theme-color': theme?.secondary, '--theme-accent': theme?.accent }}
      >
        <div className="header-logo">
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
                className={`header-nav-btn ${currentPage === 'passafaixa' ? 'active' : ''}`}
                onClick={() => onPageChange && onPageChange('passafaixa')}
              >
                PassaFaixa
              </button>
            </nav>
          )}
        </div>
        <div className="user-info">
          {user ? (
            <>
              <span>Hola, {user.username}!</span>
              <button onClick={onLogout}>Sortir</button>
            </>
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
    </>
  );
};

export default Header;
