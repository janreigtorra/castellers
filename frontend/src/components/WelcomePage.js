import React from 'react';
import LoginForm from './LoginForm';
import ColorSelector from './ColorSelector';
import { getCurrentTheme } from '../colorTheme';
import './WelcomePage.css';

const WelcomePage = ({ selectedColor, onColorChange, onLogin }) => {
  const [showLogin, setShowLogin] = React.useState(false);
  const theme = getCurrentTheme();

  const handleLoginSuccess = (userData) => {
    onLogin(userData);
    setShowLogin(false);
  };

  return (
    <div className="welcome-page" style={{ '--theme-color': theme.secondary, '--theme-accent': theme.accent }}>
      <div className="welcome-content">
        <div className="welcome-main">
          <div className="welcome-icon-container">
            <img 
              src={theme.image} 
              alt="Xiquet" 
              className="welcome-xiquet-icon"
            />
          </div>
          <div className="welcome-right-section">
            <div className="welcome-text-content">
              <h1 className="welcome-title">Benvingut a Xiquet!</h1>
              <p className="welcome-subtitle">
                L'assistent expert en el món casteller
              </p>
              <p className="welcome-description">
                Xiquet és el teu assistent intel·ligent per descobrir tot el món dels castells.
                Fes preguntes sobre colles, actuacions, castells i molt més!
              </p>
              <p className="welcome-cta">
                Per començar, entra o registra't per accedir a l'assistent.
              </p>
              <div className="welcome-btn-container">
                <button 
                  className={`welcome-login-btn ${showLogin ? 'hidden' : ''}`}
                  onClick={() => setShowLogin(true)}
                >
                  Entrar o Registrar-se
                </button>
              </div>
            </div>
            <div className="welcome-login-spacer"></div>
            {showLogin && (
              <div className="welcome-login-container">
                <LoginForm 
                  onLogin={handleLoginSuccess}
                  onClose={() => setShowLogin(false)}
                />
              </div>
            )}
          </div>
        </div>
      </div>

      <ColorSelector 
        selectedColor={selectedColor}
        onColorChange={onColorChange}
      />
    </div>
  );
};

export default WelcomePage;

