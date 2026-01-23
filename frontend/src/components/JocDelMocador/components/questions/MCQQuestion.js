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
      <div className="joc-mocador-answers">
        {question.answers.map((answer, index) => {
          const isPending = pendingAnswer === answer;
          const isSelectedAnswer = selectedAnswer === answer;
          const isCorrectAnswer = answer === question.correct_answer;
          
          let answerClass = 'joc-mocador-answer';
          if (showResult) {
            if (isCorrectAnswer) {
              answerClass += ' joc-mocador-answer-correct';
            } else if (isSelectedAnswer && !isCorrectAnswer) {
              answerClass += ' joc-mocador-answer-incorrect';
            }
          } else if (isPending) {
            answerClass += ' joc-mocador-answer-selected';
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
          className="joc-mocador-submit-btn joc-mocador-submit-btn-active"
          onClick={handleConfirm}
        >
          Confirmar Resposta
        </button>
      )}
    </>
  );
};

export default MCQQuestion;
