import React from 'react';
import './ColorSelector.css';

const ColorSelector = ({ selectedColor, onColorChange }) => {
  const colors = [
    { key: 'white', color: '#ffffff' },
    { key: 'green', color: '#3a9636' },
    { key: 'yellow', color: '#e8c62b' },
    { key: 'red', color: '#d0282c' },
    { key: 'blue', color: '#236ca8' }
  ];

  return (
    <div className="color-selector">
      <div className="color-selector-content">
        <span className="color-selector-label">De quin color és la teva camisa?</span>
        <div className="color-selector-options">
          {colors.map(({ key, color }) => (
            <button
              key={key}
              className={`color-chip ${selectedColor === key ? 'selected' : ''}`}
              onClick={() => onColorChange(key)}
              style={{ backgroundColor: color }}
              title={key}
            />
          ))}
        </div>
      </div>
    </div>
  );
};

export default ColorSelector;

