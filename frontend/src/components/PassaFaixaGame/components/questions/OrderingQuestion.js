import React, { useState, useEffect } from 'react';

const OrderingQuestion = ({ 
  question, 
  selectedAnswer, 
  onSubmit
}) => {
  const [orderedOptions, setOrderedOptions] = useState([]);
  const [draggedIndex, setDraggedIndex] = useState(null);
  const [dragOverIndex, setDragOverIndex] = useState(null);
  const showResult = selectedAnswer !== null;
  const correctOrder = question.correct_answer_order || [];

  // Initialize ordered options when question changes
  useEffect(() => {
    if (question && Array.isArray(question.options)) {
      setOrderedOptions([...question.options]);
    } else {
      setOrderedOptions([]);
    }
    setDraggedIndex(null);
    setDragOverIndex(null);
  }, [question]);

  const handleDragStart = (index) => {
    if (showResult) return;
    setDraggedIndex(index);
  };

  const handleDragOver = (e, index) => {
    e.preventDefault();
    if (showResult) return;
    setDragOverIndex(index);
  };

  const handleDragLeave = () => {
    setDragOverIndex(null);
  };

  const handleDrop = (e, dropIndex) => {
    e.preventDefault();
    if (showResult || draggedIndex === null) return;
    
    const newOrder = [...orderedOptions];
    const draggedItem = newOrder[draggedIndex];
    
    // Remove dragged item
    newOrder.splice(draggedIndex, 1);
    // Insert at new position
    newOrder.splice(dropIndex, 0, draggedItem);
    
    setOrderedOptions(newOrder);
    setDraggedIndex(null);
    setDragOverIndex(null);
  };

  const handleDragEnd = () => {
    setDraggedIndex(null);
    setDragOverIndex(null);
  };

  const handleSubmit = () => {
    if (showResult) return;
    onSubmit(orderedOptions);
  };

  return (
    <>
      <div className="passafaixa-ordering-container">
        {orderedOptions.map((option, index) => {
          const isCorrectPosition = showResult && index < correctOrder.length && option === correctOrder[index];
          const isWrongPosition = showResult && index < correctOrder.length && option !== correctOrder[index];
          const isDragging = draggedIndex === index;
          const isDragOver = dragOverIndex === index;
          
          let itemClass = 'passafaixa-ordering-item';
          if (showResult) {
            if (isCorrectPosition) {
              itemClass += ' passafaixa-ordering-correct';
            } else if (isWrongPosition) {
              itemClass += ' passafaixa-ordering-incorrect';
            }
          } else {
            if (isDragging) {
              itemClass += ' passafaixa-ordering-dragging';
            }
            if (isDragOver) {
              itemClass += ' passafaixa-ordering-drag-over';
            }
          }
          
          return (
            <div
              key={index}
              className={itemClass}
              draggable={!showResult}
              onDragStart={() => handleDragStart(index)}
              onDragOver={(e) => handleDragOver(e, index)}
              onDragLeave={handleDragLeave}
              onDrop={(e) => handleDrop(e, index)}
              onDragEnd={handleDragEnd}
            >
              <div className="passafaixa-ordering-drag-handle">⋮⋮</div>
              <div className="passafaixa-ordering-number">{index + 1}</div>
              <div className="passafaixa-ordering-text">{option}</div>
            </div>
          );
        })}
      </div>

      {!showResult && (
        <button
          className="passafaixa-submit-btn passafaixa-submit-btn-active"
          onClick={handleSubmit}
          disabled={orderedOptions.length === 0}
        >
          Confirmar Resposta
        </button>
      )}
    </>
  );
};

export default OrderingQuestion;
