import React, { useState, useEffect, useRef } from 'react';
import LoginForm from './LoginForm';
import ColorSelector from './ColorSelector';
import { getCurrentTheme, COLOR_THEMES, getThemeForColor } from '../colorTheme';
import welcomeQuestions from '../data/welcomeQuestions.json';
import collesData from '../data/colles_fundacio.json';
import './WelcomePage.css';

// Build a map from colla name to color_code from the JSON
const COLLES_COLORS = collesData.reduce((acc, colla) => {
  acc[colla.name] = colla.color_code;
  return acc;
}, {});

// Map color codes to theme keys
const COLOR_CODE_TO_THEME = {
  'darkgreen': 'darkgreen',
  'skyblue': 'bluesky',
  'turquese': 'turquese',
  'lightgreen': 'lightgreen',
  'yellow': 'yellow',
  'darkblue': 'darkblue',
  'lila': 'lila',
  'granate': 'granate',
  'blue': 'blue',
  'red': 'red',
  'green': 'green',
  'brown': 'brown',
  'gray': 'gray',
  'rosat': 'rosat',
  'malva': 'malva',
  'orange': 'orange',
  'white': 'white',
  'darkturquesa': 'darkturquesa',
  'ralles': 'ralles'
};

const getCollaColor = (colla) => {
  if (!colla) return null;
  const colorCode = COLLES_COLORS[colla];
  if (!colorCode || colorCode === 'white') return null;
  const themeKey = COLOR_CODE_TO_THEME[colorCode];
  if (!themeKey || !COLOR_THEMES[themeKey]) return null;
  return COLOR_THEMES[themeKey].secondary;
};

const QuestionChip = ({ question, colla, onClick }) => {
  const collaColor = getCollaColor(colla);
  
  const chipStyle = collaColor ? {
    backgroundColor: collaColor,
    color: '#ffffff',
    borderColor: collaColor
  } : {};
  
  return (
    <button 
      className="question-chip" 
      style={chipStyle}
      onClick={onClick}
    >
      {question}
    </button>
  );
};

const ScrollingBanner = ({ questions, direction, onQuestionClick }) => {
  const duplicatedQuestions = [...questions, ...questions];
  
  return (
    <div className={`scrolling-banner ${direction}`}>
      <div className="scrolling-content">
        {duplicatedQuestions.map((q, index) => (
          <QuestionChip
            key={`${direction}-${index}`}
            question={q.question}
            colla={q.colla}
            onClick={onQuestionClick}
          />
        ))}
      </div>
    </div>
  );
};

const WelcomePage = ({ selectedColor, onColorChange, onLogin }) => {
  const [showLogin, setShowLogin] = React.useState(false);
  const [isUserSelectedColor, setIsUserSelectedColor] = useState(false);
  const [userSelectedColor, setUserSelectedColor] = useState(null);
  const [animatedColorIndex, setAnimatedColorIndex] = useState(0);
  const animationIntervalRef = useRef(null);
  
  // Get all available color keys (excluding white from animation)
  const availableColors = Object.keys(COLOR_THEMES).filter(key => key !== 'white');
  
  // Determine which color to use: user-selected or animated
  const currentColor = isUserSelectedColor && userSelectedColor 
    ? userSelectedColor 
    : availableColors[animatedColorIndex % availableColors.length];
  const theme = getThemeForColor(currentColor);

  // Auto-cycling color animation (only if user hasn't manually selected)
  useEffect(() => {
    if (isUserSelectedColor) {
      // Stop animation if user has selected a color
      if (animationIntervalRef.current) {
        clearInterval(animationIntervalRef.current);
        animationIntervalRef.current = null;
      }
      return;
    }

    // Start animation: cycle through colors every 2 seconds
    animationIntervalRef.current = setInterval(() => {
      setAnimatedColorIndex(prev => (prev + 1) % availableColors.length);
    }, 2000);

    return () => {
      if (animationIntervalRef.current) {
        clearInterval(animationIntervalRef.current);
        animationIntervalRef.current = null;
      }
    };
  }, [isUserSelectedColor, availableColors.length]);

  // Handle color change from ColorSelector
  const handleColorChange = (colorKey) => {
    setIsUserSelectedColor(true);
    setUserSelectedColor(colorKey);
    onColorChange(colorKey);
  };

  const questions = welcomeQuestions.questions;
  const midPoint = Math.ceil(questions.length / 2);
  const topQuestions = questions.slice(0, midPoint);
  const bottomQuestions = questions.slice(midPoint);

  const handleLoginSuccess = (userData) => {
    onLogin(userData);
    setShowLogin(false);
  };

  const handleQuestionClick = () => {
    setShowLogin(true);
  };

  return (
    <div className="welcome-page" style={{ '--theme-color': theme.secondary, '--theme-accent': theme.accent }}>
      <ScrollingBanner 
        questions={topQuestions} 
        direction="left" 
        onQuestionClick={handleQuestionClick}
      />

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
                  className="welcome-login-btn"
                  onClick={() => setShowLogin(true)}
                >
                  Entrar o Registrar-se
                </button>
              </div>
            </div>
          </div>
        </div>
      </div>

      <ScrollingBanner 
        questions={bottomQuestions} 
        direction="right" 
        onQuestionClick={handleQuestionClick}
      />

      {showLogin && (
        <div className="login-modal-overlay" onClick={() => setShowLogin(false)}>
          <div className="login-modal" onClick={(e) => e.stopPropagation()}>
            <LoginForm 
              onLogin={handleLoginSuccess}
              onClose={() => setShowLogin(false)}
            />
          </div>
        </div>
      )}

      <ColorSelector 
        selectedColor={currentColor}
        onColorChange={handleColorChange}
      />
    </div>
  );
};

export default WelcomePage;
