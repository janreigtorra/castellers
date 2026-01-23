import React from 'react';
import welcomeQuestions from '../data/welcomeQuestions.json';
import collesData from '../data/colles_fundacio.json';
import { COLOR_THEMES } from '../colorTheme';

// Build a map from colla name to color_code from the JSON
const COLLES_COLORS = collesData.reduce((acc, colla) => {
  acc[colla.name] = colla.color_code;
  return acc;
}, {});

// Map color codes to theme keys (most are the same, with a few exceptions)
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
      onClick={() => onClick(question)}
    >
      {question}
    </button>
  );
};

const ScrollingBanner = ({ questions, direction, onQuestionClick }) => {
  // Duplicate questions to create seamless loop
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

const WelcomeMessage = ({ theme, onQuestionClick }) => {
  const questions = welcomeQuestions.questions;
  
  // Split questions into 4 groups for the 4 banners
  const quarterLength = Math.ceil(questions.length / 4);
  const group1 = questions.slice(0, quarterLength);
  const group2 = questions.slice(quarterLength, quarterLength * 2);
  const group3 = questions.slice(quarterLength * 2, quarterLength * 3);
  const group4 = questions.slice(quarterLength * 3);
  
  return (
    <div className="welcome-container">
      <ScrollingBanner 
        questions={group1} 
        direction="right" 
        onQuestionClick={onQuestionClick}
      />
      <ScrollingBanner 
        questions={group2} 
        direction="left" 
        onQuestionClick={onQuestionClick}
      />
      
      <div className="welcome-message">
        <img 
          src={theme?.image || '/xiquet_images/colors/basic_white.png'} 
          alt="Xiquet" 
          className="welcome-xiquet-icon-large"
        />
        <div className="welcome-text-container">
          <p className="welcome-text-main">Hola! Sóc el Xiquet, l'agent d'Intel·ligència Artificial expert en el món casteller.</p>
          <p className="welcome-text-sub">Fes-me qualsevol pregunta sobre castells!</p>
        </div>
      </div>
      
      <ScrollingBanner 
        questions={group3} 
        direction="right" 
        onQuestionClick={onQuestionClick}
      />
      <ScrollingBanner 
        questions={group4} 
        direction="left" 
        onQuestionClick={onQuestionClick}
      />
    </div>
  );
};

export default WelcomeMessage;

