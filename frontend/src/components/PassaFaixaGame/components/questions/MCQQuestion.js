import React from 'react';

const MCQQuestion = ({ question, selectedAnswer, onAnswerSelect }) => {
  return (
    <>
      <div className="passafaixa-answers">
        {question.answers.map((answer, index) => {
          const isSelected = selectedAnswer === answer;
          const isCorrect = answer === question.correct_answer;
          const showResult = selectedAnswer !== null;
          
          let answerClass = 'passafaixa-answer';
          if (showResult) {
            if (isCorrect) {
              answerClass += ' passafaixa-answer-correct';
            } else if (isSelected && !isCorrect) {
              answerClass += ' passafaixa-answer-incorrect';
            }
          } else if (isSelected) {
            answerClass += ' passafaixa-answer-selected';
          }

          return (
            <button
              key={index}
              className={answerClass}
              onClick={() => onAnswerSelect(answer)}
              disabled={selectedAnswer !== null}
            >
              {answer}
            </button>
          );
        })}
      </div>

      {selectedAnswer !== null && (
        <div className="passafaixa-feedback">
          {selectedAnswer === question.correct_answer ? (
            <p className="passafaixa-feedback-correct">Correcte! 🎉</p>
          ) : (
            <p className="passafaixa-feedback-incorrect">
              Incorrecte. La resposta correcta és: <strong>{question.correct_answer}</strong>
            </p>
          )}
        </div>
      )}
    </>
  );
};

export default MCQQuestion;

