import React, { useState } from 'react';
import { calculateSliderScore } from '../../utils/scoring';

const SliderQuestion = ({ 
  question, 
  selectedAnswer, 
  onSubmit,
  onNext,
  isLastQuestion = false
}) => {
  const [sliderValue, setSliderValue] = useState(question.slider_min);
  const showResult = selectedAnswer !== null;

  const handleSubmit = () => {
    if (showResult || sliderValue === null) return;
    onSubmit(sliderValue);
  };

  let scoreInfo = null;
  if (showResult) {
    const points = calculateSliderScore(
      selectedAnswer,
      question.correct_answer,
      question.half_point || 5
    );
    scoreInfo = { points, isPerfect: points === 1.0 };
  }

  return (
    <div className="passafaixa-slider-container">
      <div className="passafaixa-slider-wrapper">
        <input
          type="range"
          min={question.slider_min}
          max={question.slider_max}
          step={question.slider_step || 1}
          value={sliderValue}
          onChange={(e) => setSliderValue(parseInt(e.target.value))}
          disabled={showResult}
          className="passafaixa-slider"
        />
        <div className="passafaixa-slider-labels">
          <span>{question.slider_min}</span>
          <span className="passafaixa-slider-value">
            {sliderValue}
          </span>
          <span>{question.slider_max}</span>
        </div>
      </div>
      
      {!showResult && (
        <button
          className="passafaixa-slider-submit-btn"
          onClick={handleSubmit}
          disabled={sliderValue === null}
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
                    La resposta correcta és: <strong>{question.correct_answer}</strong>
                  </p>
                </div>
              );
            } else {
              return (
                <p className="passafaixa-feedback-incorrect">
                  Incorrecte. La resposta correcta és: <strong>{question.correct_answer}</strong>
                </p>
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
    </div>
  );
};

export default SliderQuestion;

