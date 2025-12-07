import React from 'react';

const Results = ({ answeredQuestions, questions, onPlayAgain, onBack }) => {
  const totalPoints = answeredQuestions.reduce((sum, item) => sum + item.points, 0);
  const percentage = Math.round((totalPoints / questions.length) * 100);
  
  const formatAnswer = (answer, isOrdering, isMultiple) => {
    if (Array.isArray(answer)) {
      if (isOrdering) {
        // For ordering, show as numbered list
        return answer.map((ans, idx) => `${idx + 1}. ${ans}`).join(', ');
      }
      return answer.length > 0 ? answer.join(', ') : '(cap)';
    }
    return answer;
  };

  return (
    <div className="passafaixa-results">
      <div className="passafaixa-results-header">
        <h1>Resultats</h1>
        <div className="passafaixa-score-circle">
          <div className="passafaixa-score-number">{totalPoints.toFixed(1)}</div>
          <div className="passafaixa-score-total">de {questions.length}</div>
        </div>
        <div className="passafaixa-score-percentage">{percentage}%</div>
      </div>

      <div className="passafaixa-results-details">
        <h2>Resum de les respostes:</h2>
        <div className="passafaixa-answers-summary">
          {answeredQuestions.map((item, index) => {
            const pointsPercentage = Math.round(item.points * 100);
            const isPartial = item.points > 0 && item.points < 1.0;
            const isMultiple = item.questionType === 'mcq_multiple';
            const isOrdering = item.questionType === 'ordering';
            
            return (
              <div key={index} className={`passafaixa-answer-item ${item.isCorrect ? 'correct' : isPartial ? 'partial' : 'incorrect'}`}>
                <div className="passafaixa-answer-item-number">{index + 1}</div>
                <div className="passafaixa-answer-item-content">
                  <p className="passafaixa-answer-item-question">{item.question}</p>
                  <div className="passafaixa-answer-item-answers">
                    <span className={`passafaixa-answer-item-selected ${item.isCorrect ? 'correct' : isPartial ? 'partial' : 'incorrect'}`}>
                      {isOrdering ? 'El teu ordre: ' : isMultiple ? 'Les teves respostes: ' : 'La teva resposta: '}
                      {formatAnswer(item.selectedAnswer, isOrdering, isMultiple)}
                      {isPartial && ` (${pointsPercentage}% dels punts)`}
                    </span>
                    {(!item.isCorrect || isPartial) && (
                      <span className="passafaixa-answer-item-correct">
                        {isOrdering ? 'Ordre correcte: ' : isMultiple ? 'Respostes correctes: ' : 'Resposta correcta: '}
                        {formatAnswer(item.correctAnswer, isOrdering, isMultiple)}
                      </span>
                    )}
                  </div>
                </div>
                <div className="passafaixa-answer-item-icon">
                  {item.isCorrect ? '✓' : isPartial ? '~' : '✗'}
                </div>
              </div>
            );
          })}
        </div>
      </div>

      <div className="passafaixa-results-actions">
        <button className="passafaixa-play-again-btn" onClick={onPlayAgain}>
          Tornar a Jugar
        </button>
        {onBack && (
          <button className="passafaixa-back-btn" onClick={onBack}>
            Tornar al Xat
          </button>
        )}
      </div>
    </div>
  );
};

export default Results;

