import React, { useState, useCallback } from 'react';
import { apiService } from '../../apiService';
import { getCurrentTheme } from '../../colorTheme';
import { isSliderQuestion, isMultipleOptionsQuestion, isOrderingQuestion } from './utils/questionTypes';
import { calculateSliderScore, calculateMultipleOptionsScore, calculateOrderingScore } from './utils/scoring';
import Menu from './components/Menu';
import Results from './components/Results';
import MCQQuestion from './components/questions/MCQQuestion';
import MultipleOptionsQuestion from './components/questions/MultipleOptionsQuestion';
import OrderingQuestion from './components/questions/OrderingQuestion';
import SliderQuestion from './components/questions/SliderQuestion';
import './JocDelMocador.css';

const JocDelMocador = ({ theme, onBack, onColorChange, selectedColor }) => {
  const [gameState, setGameState] = useState('menu'); // 'menu', 'playing', 'results'
  const [questions, setQuestions] = useState([]);
  const [currentQuestionIndex, setCurrentQuestionIndex] = useState(0);
  const [selectedAnswer, setSelectedAnswer] = useState(null);
  const [selectedAnswers, setSelectedAnswers] = useState([]); // For multiple options questions
  const [score, setScore] = useState(0);
  const [isLoading, setIsLoading] = useState(false);
  const [answeredQuestions, setAnsweredQuestions] = useState([]);
  
  // Game settings
  const [gameSettings, setGameSettings] = useState({
    numQuestions: 10,
    colles: [],  // Empty array means all colles
    years: []    // Empty array means all years
  });

  const handleSettingsChange = useCallback((newSettings) => {
    setGameSettings(newSettings);
  }, []);

  const startGame = async () => {
    setIsLoading(true);
    try {
      // Pass selected colles and years to filter questions
      const response = await apiService.getGameQuestions(
        gameSettings.numQuestions,
        gameSettings.colles,
        gameSettings.years
      );
      setQuestions(response.questions);
      setGameState('playing');
      setCurrentQuestionIndex(0);
      setScore(0);
      setSelectedAnswer(null);
      setSelectedAnswers([]);
      setAnsweredQuestions([]);
    } catch (error) {
      console.error('Error loading questions:', error);
      alert('Error carregant les preguntes. Si us plau, torna-ho a intentar.');
    } finally {
      setIsLoading(false);
    }
  };

  const handleAnswerSelect = (answer) => {
    if (selectedAnswer !== null) return; // Already answered
    setSelectedAnswer(answer);
    
    const currentQuestion = questions[currentQuestionIndex];
    const isCorrect = answer === currentQuestion.correct_answer;
    const points = isCorrect ? 1.0 : 0.0;
    
    setScore(score + points);
    
    // Store the answer result
    setAnsweredQuestions([
      ...answeredQuestions,
      {
        question: currentQuestion.question,
        selectedAnswer: answer,
        correctAnswer: currentQuestion.correct_answer,
        isCorrect: isCorrect,
        points: points,
        questionType: 'mcq'
      }
    ]);
  };

  const handleMultipleAnswerToggle = (option) => {
    if (selectedAnswer !== null) return; // Already submitted
    
    setSelectedAnswers(prev => {
      if (prev.includes(option)) {
        return prev.filter(a => a !== option);
      } else {
        return [...prev, option];
      }
    });
  };

  const handleMultipleAnswerSubmit = () => {
    if (selectedAnswers.length === 0) return; // No answer selected
    if (selectedAnswer !== null) return; // Already answered
    
    const currentQuestion = questions[currentQuestionIndex];
    const correctAnswers = currentQuestion.correct_answer || [];
    
    const scoreInfo = calculateMultipleOptionsScore(selectedAnswers, correctAnswers);
    
    setSelectedAnswer(selectedAnswers); // Mark as answered
    setScore(score + scoreInfo.points);
    
    // Store the answer result
    setAnsweredQuestions([
      ...answeredQuestions,
      {
        question: currentQuestion.question,
        selectedAnswer: selectedAnswers,
        correctAnswer: correctAnswers,
        isCorrect: scoreInfo.isPerfect,
        points: scoreInfo.points,
        questionType: 'mcq_multiple'
      }
    ]);
  };

  const handleSliderSubmit = (sliderValue) => {
    if (sliderValue === null) return; // No answer selected
    if (selectedAnswer !== null) return; // Already answered
    
    const currentQuestion = questions[currentQuestionIndex];
    const correctAnswer = currentQuestion.correct_answer;
    const halfPointMargin = currentQuestion.half_point || 5;
    
    const points = calculateSliderScore(sliderValue, correctAnswer, halfPointMargin);
    const isCorrect = points === 1.0;
    
    setSelectedAnswer(sliderValue);
    setScore(score + points);
    
    // Store the answer result
    setAnsweredQuestions([
      ...answeredQuestions,
      {
        question: currentQuestion.question,
        selectedAnswer: sliderValue,
        correctAnswer: correctAnswer,
        isCorrect: isCorrect,
        points: points,
        questionType: 'slider'
      }
    ]);
  };

  const handleOrderingSubmit = (submittedOrder) => {
    if (selectedAnswer !== null) return; // Already answered
    
    const currentQuestion = questions[currentQuestionIndex];
    const correctOrder = currentQuestion.correct_answer_order || [];
    
    const scoreInfo = calculateOrderingScore(submittedOrder, correctOrder);
    
    setSelectedAnswer(submittedOrder);
    setScore(score + scoreInfo.points);
    
    // Store the answer result
    setAnsweredQuestions([
      ...answeredQuestions,
      {
        question: currentQuestion.question,
        selectedAnswer: submittedOrder,
        correctAnswer: correctOrder,
        isCorrect: scoreInfo.isPerfect,
        points: scoreInfo.points,
        questionType: 'ordering'
      }
    ]);
  };

  const handleNextQuestion = () => {
    if (currentQuestionIndex < questions.length - 1) {
      setCurrentQuestionIndex(currentQuestionIndex + 1);
      setSelectedAnswer(null);
      setSelectedAnswers([]);
    } else {
      // Game finished
      setGameState('results');
    }
  };

  const handlePlayAgain = () => {
    setGameState('menu');
    setQuestions([]);
    setCurrentQuestionIndex(0);
    setSelectedAnswer(null);
    setSelectedAnswers([]);
    setScore(0);
    setAnsweredQuestions([]);
  };

  const currentQuestion = questions[currentQuestionIndex];
  const currentTheme = theme || getCurrentTheme();
  const isSlider = currentQuestion && isSliderQuestion(currentQuestion);
  const isMultiple = currentQuestion && isMultipleOptionsQuestion(currentQuestion);
  const isOrdering = currentQuestion && isOrderingQuestion(currentQuestion);

  if (gameState === 'menu') {
    return (
      <div className="joc-mocador-container joc-mocador-menu-state" style={{ '--theme-color': currentTheme.secondary, '--theme-accent': currentTheme.accent, '--theme-highlight': currentTheme.highlight }}>
        <Menu 
          onStartGame={startGame}
          isLoading={isLoading}
          onBack={onBack}
          theme={currentTheme}
          gameSettings={gameSettings}
          onSettingsChange={handleSettingsChange}
          onColorChange={onColorChange}
          selectedColor={selectedColor}
        />
      </div>
    );
  }

  // Determine result info for feedback
  const getResultInfo = () => {
    if (selectedAnswer === null) return null;
    
    if (isOrdering) {
      const scoreInfo = calculateOrderingScore(selectedAnswer, currentQuestion.correct_answer_order || []);
      const correctOrder = currentQuestion.correct_answer_order || [];
      if (scoreInfo.isPerfect) {
        return { type: 'correct', icon: '/xiquet_images/questions/correct.png', message: "Perfecte! L'ordre és correcte! " };
      }
      if (scoreInfo.points > 0) {
        const percentage = Math.round(scoreInfo.points * 100);
        return { 
          type: 'partial', 
          icon: '/xiquet_images/questions/half_point.png', 
          message: `Gairebé! Has obtingut ${percentage}% dels punts.`,
          explanation: "L'ordre correcte és:",
          correctAnswers: correctOrder,
          isOrdered: true
        };
      }
      return { 
        type: 'incorrect', 
        icon: '/xiquet_images/questions/incorrect.png', 
        message: 'No és correcte...',
        explanation: "L'ordre correcte és:",
        correctAnswers: correctOrder,
        isOrdered: true
      };
    } else if (isMultiple) {
      const correctAnswers = currentQuestion.correct_answer || [];
      const scoreInfo = calculateMultipleOptionsScore(selectedAnswer, correctAnswers);
      if (scoreInfo.isPerfect) {
        return { type: 'correct', icon: '/xiquet_images/questions/correct.png', message: 'Excel·lent! Totes les respostes correctes!' };
      }
      if (scoreInfo.points > 0) {
        const percentage = Math.round(scoreInfo.points * 100);
        return { 
          type: 'partial', 
          icon: '/xiquet_images/questions/half_point.png', 
          message: `Gairebé! Has obtingut ${percentage}% dels punts.`,
          explanation: 'Les respostes correctes són:',
          correctAnswers: correctAnswers
        };
      }
      return { 
        type: 'incorrect', 
        icon: '/xiquet_images/questions/incorrect.png', 
        message: 'No és correcte...',
        explanation: 'Les respostes correctes són:',
        correctAnswers: correctAnswers
      };
    } else if (isSlider) {
      const points = calculateSliderScore(selectedAnswer, currentQuestion.correct_answer, currentQuestion.half_point || 5);
      if (points === 1.0) {
        return { type: 'correct', icon: '/xiquet_images/questions/correct.png', message: 'Perfecte! Has encertat!' };
      }
      if (points > 0) {
        const percentage = Math.round(points * 100);
        return { 
          type: 'partial', 
          icon: '/xiquet_images/questions/half_point.png', 
          message: `Gairebé! Has obtingut ${percentage}% dels punts.`,
          explanation: `La resposta correcta és: ${currentQuestion.correct_answer}`
        };
      }
      return { 
        type: 'incorrect', 
        icon: '/xiquet_images/questions/incorrect.png', 
        message: 'No és correcte...',
        explanation: `La resposta correcta és: ${currentQuestion.correct_answer}`
      };
    } else {
      // MCQ
      if (selectedAnswer === currentQuestion.correct_answer) {
        return { type: 'correct', icon: '/xiquet_images/questions/correct.png', message: 'Molt bé! Has encertat!' };
      }
      return { 
        type: 'incorrect', 
        icon: '/xiquet_images/questions/incorrect.png', 
        message: 'No és correcte...',
        explanation: `La resposta correcta és: ${currentQuestion.correct_answer}`
      };
    }
  };

  const resultInfo = getResultInfo();

  if (gameState === 'playing' && currentQuestion) {
    return (
      <div className={`joc-mocador-container joc-mocador-playing-state ${selectedAnswer !== null ? 'joc-mocador-showing-result' : ''}`} style={{ '--theme-color': currentTheme.secondary, '--theme-accent': currentTheme.accent, '--theme-highlight': currentTheme.highlight }}>
        {/* Left Panel with Xiquet and ALL Feedback */}
        <div className="joc-mocador-left-panel">
          <div className="joc-mocador-xiquet-panel">
            {/* Show result icon if answered, otherwise show basic xiquet */}
            <img 
              src={resultInfo ? resultInfo.icon : currentTheme.image} 
              alt={resultInfo ? 'Resultat' : 'Xiquet'} 
              className={`joc-mocador-xiquet-panel-icon ${resultInfo ? 'joc-mocador-result-icon' : ''}`}
            />
            
            {/* Feedback text - only shown after answering */}
            {resultInfo && (
              <div className="joc-mocador-panel-feedback">
                <p className={`joc-mocador-panel-message joc-mocador-panel-message-${resultInfo.type}`}>
                  {resultInfo.message}
                </p>
                {resultInfo.explanation && (
                  <p className="joc-mocador-panel-explanation">{resultInfo.explanation}</p>
                )}
                {resultInfo.correctAnswers && (
                  resultInfo.isOrdered ? (
                    <ol className="joc-mocador-panel-answers-list">
                      {resultInfo.correctAnswers.map((ans, idx) => (
                        <li key={idx}>{ans}</li>
                      ))}
                    </ol>
                  ) : (
                    <ul className="joc-mocador-panel-answers-list">
                      {resultInfo.correctAnswers.map((ans, idx) => (
                        <li key={idx}>{ans}</li>
                      ))}
                    </ul>
                  )
                )}
              </div>
            )}
          </div>
        </div>

        {/* Right Content Area */}
        <div className="joc-mocador-game-content">
          <div className="joc-mocador-progress">
            <div className="joc-mocador-progress-bar">
              <div 
                className="joc-mocador-progress-fill"
                style={{ width: `${((currentQuestionIndex + 1) / questions.length) * 100}%` }}
              >
                <div className="joc-mocador-progress-indicator">
                  <img 
                    src="/xiquet_images/xiquet_logo.png" 
                    alt="Xiquet" 
                    className="joc-mocador-progress-xiquet"
                  />
                </div>
              </div>
            </div>
            <span className="joc-mocador-progress-text">
              Pregunta {currentQuestionIndex + 1} de {questions.length}
            </span>
          </div>

          <div className="joc-mocador-question-container">
            <div className="joc-mocador-question-content">
              <h2 className="joc-mocador-question-text">{currentQuestion.question}</h2>
              
              {isOrdering ? (
                <OrderingQuestion
                  question={currentQuestion}
                  selectedAnswer={selectedAnswer}
                  onSubmit={handleOrderingSubmit}
                />
              ) : isMultiple ? (
                <MultipleOptionsQuestion
                  question={currentQuestion}
                  selectedAnswers={selectedAnswers}
                  selectedAnswer={selectedAnswer}
                  onAnswerToggle={handleMultipleAnswerToggle}
                  onSubmit={handleMultipleAnswerSubmit}
                />
              ) : isSlider ? (
                <SliderQuestion
                  question={currentQuestion}
                  selectedAnswer={selectedAnswer}
                  onSubmit={handleSliderSubmit}
                />
              ) : (
                <MCQQuestion
                  question={currentQuestion}
                  selectedAnswer={selectedAnswer}
                  onAnswerSelect={handleAnswerSelect}
                />
              )}

              {/* Next button - shown after answering */}
              {selectedAnswer !== null && (
                <button 
                  className="joc-mocador-next-btn"
                  onClick={handleNextQuestion}
                >
                  {currentQuestionIndex === questions.length - 1 ? 'Veure Resultats' : 'Següent'}
                </button>
              )}
            </div>
          </div>
        </div>
      </div>
    );
  }

  if (gameState === 'results') {
    return (
      <div className="joc-mocador-container joc-mocador-results-state" style={{ '--theme-color': currentTheme.secondary, '--theme-accent': currentTheme.accent, '--theme-highlight': currentTheme.highlight }}>
        <Results
          answeredQuestions={answeredQuestions}
          questions={questions}
          onPlayAgain={handlePlayAgain}
          onBack={onBack}
          theme={currentTheme}
        />
      </div>
    );
  }

  return null;
};

export default JocDelMocador;

