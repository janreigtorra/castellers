import React from 'react';
import './ColorSelector.css';

const ColorSelector = ({ selectedColor, onColorChange }) => {
  const colors = [
    { key: 'white', color: '#ffffff' },
    { key: 'rosat', color: '#E76253' },
    { key: 'turquese', color: '#2BB5A3' },
    { key: 'red', color: '#d0282c' },
    { key: 'blue', color: '#236ca8' },
    { key: 'malva', color: '#C1B6D7' },
    { key: 'orange', color: '#E27B27' },
    { key: 'green', color: '#3a9636' },
    { key: 'yellow', color: '#e8c62b' },
    { key: 'brown', color: '#6F5930' },
    { key: 'darkblue', color: '#2f4f80' },
    { key: 'darkturquesa', color: '#3F8087' },
    { key: 'granate', color: '#550E14' },
    { key: 'gray', color: '#747373' },
    { key: 'lila', color: '#9573A4' },
    { key: 'bluesky', color: '#59AFD1' },
    { key: 'darkgreen', color: '#366549' },
    { key: 'ralles', color: '#DB9FB6' },
    { key: 'lightgreen', color: '#93BB7B' }
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

