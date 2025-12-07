import React from 'react';
import { calculateMultipleOptionsScore } from '../../utils/scoring';

const MultipleOptionsQuestion = ({ 
  question, 
  selectedAnswers, 
  selectedAnswer, 
  onAnswerToggle, 
  onSubmit,
  onNext,
  isLastQuestion = false
}) => {
  const showResult = selectedAnswer !== null;
  const correctAnswers = question.correct_answer || [];
  
  let scoreInfo = null;
  if (showResult) {
    scoreInfo = calculateMultipleOptionsScore(selectedAnswer, correctAnswers);
  }

  return (
    <>
      <div className="passafaixa-answers">
        {question.options.map((option, index) => {
          const isSelected = selectedAnswers.includes(option);
          const isCorrect = correctAnswers.includes(option);
          
          let answerClass = 'passafaixa-answer passafaixa-answer-multiple';
          if (showResult) {
            if (isCorrect) {
              answerClass += ' passafaixa-answer-correct';
            } else if (isSelected && !isCorrect) {
              answerClass += ' passafaixa-answer-incorrect';
            } else if (!isSelected && isCorrect) {
              answerClass += ' passafaixa-answer-missed';
            }
          } else if (isSelected) {
            answerClass += ' passafaixa-answer-selected';
          }

          return (
            <label
              key={index}
              className={answerClass}
            >
              <input
                type="checkbox"
                checked={isSelected}
                onChange={() => onAnswerToggle(option)}
                disabled={showResult}
                className="passafaixa-checkbox"
              />
              <span>{option}</span>
            </label>
          );
        })}
      </div>

      {!showResult && (
        <button
          className="passafaixa-submit-btn"
          onClick={onSubmit}
          disabled={selectedAnswers.length === 0}
        >
          Confirmar Resposta
        </button>
      )}

      {showResult && (
        <div className="passafaixa-feedback">
          {(() => {
            const percentage = Math.round(scoreInfo.points * 100);
            
            if (scoreInfo.isPerfect) {
              return <p className="passafaixa-feedback-correct">Correcte! 🎉</p>;
            } else if (scoreInfo.points > 0) {
              return (
                <div>
                  <p className="passafaixa-feedback-partial">
                    Gairebé! Has obtingut {percentage}% dels punts.
                  </p>
                  <p className="passafaixa-feedback-info">
                    Les respostes correctes són:
                  </p>
                  <ul className="passafaixa-correct-answers-list">
                    {correctAnswers.map((ans, idx) => (
                      <li key={idx}><strong>{ans}</strong></li>
                    ))}
                  </ul>
                </div>
              );
            } else {
              return (
                <div>
                  <p className="passafaixa-feedback-incorrect">
                    Incorrecte. Les respostes correctes són:
                  </p>
                  <ul className="passafaixa-correct-answers-list">
                    {correctAnswers.map((ans, idx) => (
                      <li key={idx}><strong>{ans}</strong></li>
                    ))}
                  </ul>
                </div>
              );
            }
          })()}
          <button 
            className="passafaixa-next-btn"
            onClick={onNext}
          >
            {isLastQuestion ? 'Veure Resultats' : 'Següent'}
          </button>
        </div>
      )}
    </>
  );
};

export default MultipleOptionsQuestion;

