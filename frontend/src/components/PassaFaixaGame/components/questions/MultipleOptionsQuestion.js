import React from 'react';

const MultipleOptionsQuestion = ({ 
  question, 
  selectedAnswers, 
  selectedAnswer, 
  onAnswerToggle, 
  onSubmit
}) => {
  const showResult = selectedAnswer !== null;
  const correctAnswers = question.correct_answer || [];

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

      {!showResult && selectedAnswers.length > 0 && (
        <button
          className="passafaixa-submit-btn passafaixa-submit-btn-active"
          onClick={onSubmit}
        >
          Confirmar Resposta
        </button>
      )}
    </>
  );
};

export default MultipleOptionsQuestion;
