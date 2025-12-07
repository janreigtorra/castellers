import React, { useState } from 'react';
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
import './PassaFaixaGame.css';

const NUM_QUESTIONS = 10;

const PassaFaixaGame = ({ theme, onBack }) => {
  const [gameState, setGameState] = useState('menu'); // 'menu', 'playing', 'results'
  const [questions, setQuestions] = useState([]);
  const [currentQuestionIndex, setCurrentQuestionIndex] = useState(0);
  const [selectedAnswer, setSelectedAnswer] = useState(null);
  const [selectedAnswers, setSelectedAnswers] = useState([]); // For multiple options questions
  const [score, setScore] = useState(0);
  const [isLoading, setIsLoading] = useState(false);
  const [answeredQuestions, setAnsweredQuestions] = useState([]);

  const startGame = async () => {
    setIsLoading(true);
    try {
      const response = await apiService.getGameQuestions(NUM_QUESTIONS);
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
      <div className="passafaixa-container passafaixa-menu-state" style={{ '--theme-color': currentTheme.secondary, '--theme-accent': currentTheme.accent }}>
        <Menu 
          onStartGame={startGame}
          isLoading={isLoading}
          onBack={onBack}
          theme={currentTheme}
        />
      </div>
    );
  }

  if (gameState === 'playing' && currentQuestion) {
    return (
      <div className="passafaixa-container" style={{ '--theme-color': currentTheme.secondary, '--theme-accent': currentTheme.accent }}>
        <div className="passafaixa-game">
          <div className="passafaixa-progress">
            <div className="passafaixa-progress-bar">
              <div 
                className="passafaixa-progress-fill"
                style={{ width: `${((currentQuestionIndex + 1) / questions.length) * 100}%` }}
              ></div>
            </div>
            <span className="passafaixa-progress-text">
              Pregunta {currentQuestionIndex + 1} de {questions.length}
            </span>
          </div>

          <div className="passafaixa-question-container">
            <div className="passafaixa-question-icon">
              <img 
                src={currentTheme.image} 
                alt="Xiquet" 
                className="passafaixa-xiquet-icon-small"
              />
            </div>
            <div className="passafaixa-question-content">
              <h2 className="passafaixa-question-text">{currentQuestion.question}</h2>
              
              {isOrdering ? (
                <OrderingQuestion
                  question={currentQuestion}
                  selectedAnswer={selectedAnswer}
                  onSubmit={handleOrderingSubmit}
                  onNext={handleNextQuestion}
                  isLastQuestion={currentQuestionIndex === questions.length - 1}
                />
              ) : isMultiple ? (
                <MultipleOptionsQuestion
                  question={currentQuestion}
                  selectedAnswers={selectedAnswers}
                  selectedAnswer={selectedAnswer}
                  onAnswerToggle={handleMultipleAnswerToggle}
                  onSubmit={handleMultipleAnswerSubmit}
                  onNext={handleNextQuestion}
                  isLastQuestion={currentQuestionIndex === questions.length - 1}
                />
              ) : isSlider ? (
                <SliderQuestion
                  question={currentQuestion}
                  selectedAnswer={selectedAnswer}
                  onSubmit={handleSliderSubmit}
                  onNext={handleNextQuestion}
                  isLastQuestion={currentQuestionIndex === questions.length - 1}
                />
              ) : (
                <>
                  <MCQQuestion
                    question={currentQuestion}
                    selectedAnswer={selectedAnswer}
                    onAnswerSelect={handleAnswerSelect}
                  />
                  {selectedAnswer !== null && (
                    <div className="passafaixa-feedback">
                      <button 
                        className="passafaixa-next-btn"
                        onClick={handleNextQuestion}
                      >
                        {currentQuestionIndex < questions.length - 1 ? 'Següent' : 'Veure Resultats'}
                      </button>
                    </div>
                  )}
                </>
              )}
            </div>
          </div>
        </div>
      </div>
    );
  }

  if (gameState === 'results') {
    return (
      <div className="passafaixa-container" style={{ '--theme-color': currentTheme.secondary, '--theme-accent': currentTheme.accent }}>
        <Results
          answeredQuestions={answeredQuestions}
          questions={questions}
          onPlayAgain={handlePlayAgain}
          onBack={onBack}
        />
      </div>
    );
  }

  return null;
};

export default PassaFaixaGame;

