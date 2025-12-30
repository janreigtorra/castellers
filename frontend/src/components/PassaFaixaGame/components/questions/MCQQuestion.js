import React, { useState, useEffect } from 'react';

const MCQQuestion = ({ question, selectedAnswer, onAnswerSelect }) => {
  const [pendingAnswer, setPendingAnswer] = useState(null);
  const showResult = selectedAnswer !== null;

  // Reset pending answer when question changes
  useEffect(() => {
    setPendingAnswer(null);
  }, [question]);

  const handleOptionClick = (answer) => {
    if (showResult) return;
    setPendingAnswer(answer);
  };

  const handleConfirm = () => {
    if (pendingAnswer === null) return;
    onAnswerSelect(pendingAnswer);
  };

  return (
    <>
      <div className="passafaixa-answers">
        {question.answers.map((answer, index) => {
          const isPending = pendingAnswer === answer;
          const isSelectedAnswer = selectedAnswer === answer;
          const isCorrectAnswer = answer === question.correct_answer;
          
          let answerClass = 'passafaixa-answer';
          if (showResult) {
            if (isCorrectAnswer) {
              answerClass += ' passafaixa-answer-correct';
            } else if (isSelectedAnswer && !isCorrectAnswer) {
              answerClass += ' passafaixa-answer-incorrect';
            }
          } else if (isPending) {
            answerClass += ' passafaixa-answer-selected';
          }

          return (
            <button
              key={index}
              className={answerClass}
              onClick={() => handleOptionClick(answer)}
              disabled={showResult}
            >
              {answer}
            </button>
          );
        })}
      </div>

      {!showResult && pendingAnswer !== null && (
        <button
          className="passafaixa-submit-btn passafaixa-submit-btn-active"
          onClick={handleConfirm}
        >
          Confirmar Resposta
        </button>
      )}
    </>
  );
};

export default MCQQuestion;
