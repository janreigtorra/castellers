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
      <div className="joc-mocador-answers">
        {question.options.map((option, index) => {
          const isSelected = selectedAnswers.includes(option);
          const isCorrect = correctAnswers.includes(option);
          
          let answerClass = 'joc-mocador-answer joc-mocador-answer-multiple';
          if (showResult) {
            if (isCorrect) {
              answerClass += ' joc-mocador-answer-correct';
            } else if (isSelected && !isCorrect) {
              answerClass += ' joc-mocador-answer-incorrect';
            } else if (!isSelected && isCorrect) {
              answerClass += ' joc-mocador-answer-missed';
            }
          } else if (isSelected) {
            answerClass += ' joc-mocador-answer-selected';
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
                className="joc-mocador-checkbox"
              />
              <span>{option}</span>
            </label>
          );
        })}
      </div>

      {!showResult && selectedAnswers.length > 0 && (
        <button
          className="joc-mocador-submit-btn joc-mocador-submit-btn-active"
          onClick={onSubmit}
        >
          Confirmar Resposta
        </button>
      )}
    </>
  );
};

export default MultipleOptionsQuestion;
