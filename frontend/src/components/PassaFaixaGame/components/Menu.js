import React, { useState, useEffect } from 'react';
import { getCurrentTheme } from '../../../colorTheme';

const Menu = ({ onStartGame, isLoading, onBack, theme }) => {
  const currentTheme = theme || getCurrentTheme();
  const [buttonText, setButtonText] = useState('Jugar');
  const [buttonPulse, setButtonPulse] = useState(false);
  const [loadingDots, setLoadingDots] = useState('');

  useEffect(() => {
    if (isLoading) {
      setButtonText('Carregant');
      let dotCount = 0;
      const interval = setInterval(() => {
        dotCount = (dotCount + 1) % 4;
        setLoadingDots('.'.repeat(dotCount));
      }, 500);
      return () => clearInterval(interval);
    } else {
      setLoadingDots('');
      const playTexts = ['Jugar', 'Començar', 'Endavant!'];
      let textIndex = 0;
      const interval = setInterval(() => {
        setButtonText(playTexts[textIndex]);
        setButtonPulse(true);
        setTimeout(() => setButtonPulse(false), 300);
        textIndex = (textIndex + 1) % playTexts.length;
      }, 2000);
      return () => clearInterval(interval);
    }
  }, [isLoading]);

  return (
    <div className="passafaixa-menu">
      <div className="passafaixa-menu-content">
        <div className="passafaixa-icon-container">
          <img 
            src={isLoading ? "/xiquet_images/xiquet_loading.png" : "/xiquet_images/xiquet_go.png"}
            alt="Xiquet" 
            className="passafaixa-xiquet-icon"
          />
        </div>
        <div className="passafaixa-menu-text">
          <h1 className="passafaixa-title">El PassaFaixa</h1>
          <p className="passafaixa-subtitle">El joc on pots posar a prova tot el que saps sobre el món casteller. En sabàs més que jo?</p>
          <p className="passafaixa-description">Respon a 10 preguntes sobre castells, diades, fets castellers, etc. Si vols, pots seleccionar un any o una colla específica per jugar.</p>
          <button 
            className={`passafaixa-play-btn ${buttonPulse ? 'pulse' : ''}`}
            onClick={onStartGame}
            disabled={isLoading}
          >
            <span className="button-text">
              {buttonText}
              {isLoading && <span className="loading-dots">{loadingDots}</span>}
            </span>
            {!isLoading && <span className="button-arrow">→</span>}
          </button>
        </div>
      </div>
    </div>
  );
};

export default Menu;

