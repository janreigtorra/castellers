import React from 'react';

const Results = ({ answeredQuestions, questions, onPlayAgain, onBack, theme }) => {
  const totalPoints = answeredQuestions.reduce((sum, item) => sum + item.points, 0);
  const percentage = Math.round((totalPoints / questions.length) * 100);
  
  // Determine result icon based on score
  const getResultIcon = () => {
    if (percentage >= 80) return '/xiquet_images/questions/correct.png';
    if (percentage >= 50) return '/xiquet_images/questions/half_point.png';
    return '/xiquet_images/questions/incorrect.png';
  };

  const getResultMessage = () => {
    if (percentage >= 80) return 'Excel·lent!';
    if (percentage >= 50) return 'Bona feina!';
    return 'Continua practicant!';
  };

  const formatAnswer = (answer, isOrdering, isMultiple) => {
    if (Array.isArray(answer)) {
      if (isOrdering) {
        return answer.map((ans, idx) => `${idx + 1}. ${ans}`).join(', ');
      }
      return answer.length > 0 ? answer.join(', ') : '(cap)';
    }
    return answer;
  };

  return (
    <>
      {/* Left Panel with Score */}
      <div className="joc-mocador-left-panel joc-mocador-results-left-panel">
        <div className="joc-mocador-xiquet-panel">
          <img 
            src={getResultIcon()} 
            alt="Resultat" 
            className="joc-mocador-xiquet-panel-icon joc-mocador-result-icon"
          />
          <div className="joc-mocador-results-score-panel">
            <div className="joc-mocador-score-big">{totalPoints.toFixed(1)}</div>
            <div className="joc-mocador-score-total-text">de {questions.length}</div>
            <div className="joc-mocador-score-percentage">{percentage}%</div>
            <p className="joc-mocador-results-message">{getResultMessage()}</p>
          </div>
        </div>
      </div>

      {/* Right Content Area */}
      <div className="joc-mocador-results-content">
        <div className="joc-mocador-results-header">
          <h1>Resultats</h1>
        </div>

        <div className="joc-mocador-results-details">
          <h2>Resum de les respostes:</h2>
          <div className="joc-mocador-answers-summary">
            {answeredQuestions.map((item, index) => {
              const pointsPercentage = Math.round(item.points * 100);
              const isPartial = item.points > 0 && item.points < 1.0;
              const isMultiple = item.questionType === 'mcq_multiple';
              const isOrdering = item.questionType === 'ordering';
              
              return (
                <div key={index} className={`joc-mocador-answer-item ${item.isCorrect ? 'correct' : isPartial ? 'partial' : 'incorrect'}`}>
                  <div className="joc-mocador-answer-item-number">{index + 1}</div>
                  <div className="joc-mocador-answer-item-content">
                    <p className="joc-mocador-answer-item-question">{item.question}</p>
                    <div className="joc-mocador-answer-item-answers">
                      <span className={`joc-mocador-answer-item-selected ${item.isCorrect ? 'correct' : isPartial ? 'partial' : 'incorrect'}`}>
                        {isOrdering ? 'El teu ordre: ' : isMultiple ? 'Les teves respostes: ' : 'La teva resposta: '}
                        {formatAnswer(item.selectedAnswer, isOrdering, isMultiple)}
                        {isPartial && ` (${pointsPercentage}%)`}
                      </span>
                      {(!item.isCorrect || isPartial) && (
                        <span className="joc-mocador-answer-item-correct">
                          {isOrdering ? 'Ordre correcte: ' : isMultiple ? 'Respostes correctes: ' : 'Resposta correcta: '}
                          {formatAnswer(item.correctAnswer, isOrdering, isMultiple)}
                        </span>
                      )}
                    </div>
                  </div>
                  <div className="joc-mocador-answer-item-icon">
                    {item.isCorrect ? '✓' : isPartial ? '~' : '✗'}
                  </div>
                </div>
              );
            })}
          </div>
        </div>

        <div className="joc-mocador-results-actions">
          <button className="joc-mocador-play-again-btn" onClick={onPlayAgain}>
            Tornar a Jugar
          </button>
          {onBack && (
            <button className="joc-mocador-back-btn" onClick={onBack}>
              Tornar al Xat
            </button>
          )}
        </div>
      </div>
    </>
  );
};

export default Results;
