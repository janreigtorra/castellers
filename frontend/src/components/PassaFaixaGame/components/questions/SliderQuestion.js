import React, { useState, useEffect } from 'react';

const SliderQuestion = ({ 
  question, 
  selectedAnswer, 
  onSubmit
}) => {
  const [sliderValue, setSliderValue] = useState(question.slider_min);
  const showResult = selectedAnswer !== null;

  // Reset slider value when question changes
  useEffect(() => {
    setSliderValue(question.slider_min);
  }, [question]);

  const handleSubmit = () => {
    if (showResult || sliderValue === null) return;
    onSubmit(sliderValue);
  };

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
          className="passafaixa-submit-btn passafaixa-submit-btn-active"
          onClick={handleSubmit}
        >
          Confirmar Resposta
        </button>
      )}
    </div>
  );
};

export default SliderQuestion;
