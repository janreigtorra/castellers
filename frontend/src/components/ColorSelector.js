import React, { useState, useEffect } from 'react';
import './ColorSelector.css';

const ColorSelector = ({ selectedColor, onColorChange }) => {
  const [showAllColors, setShowAllColors] = useState(false);
  const [isMobile, setIsMobile] = useState(() => {
    return typeof window !== 'undefined' && window.innerWidth <= 768;
  });

  // Listen for window resize
  useEffect(() => {
    const handleResize = () => {
      setIsMobile(window.innerWidth <= 768);
    };

    window.addEventListener('resize', handleResize);
    return () => window.removeEventListener('resize', handleResize);
  }, []);

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

  // On mobile, show first 6 colors unless expanded
  const visibleColors = isMobile && !showAllColors ? colors.slice(0, 6) : colors;
  const hasMoreColors = isMobile && !showAllColors && colors.length > 6;

  return (
    <div className={`color-selector ${showAllColors ? 'expanded' : ''}`}>
      <div className="color-selector-content">
        <span className="color-selector-label">
          {isMobile ? 'Camisa?' : 'De quin color és la teva camisa?'}
        </span>
        <div className="color-selector-options">
          {visibleColors.map(({ key, color }) => (
            <button
              key={key}
              className={`color-chip ${selectedColor === key ? 'selected' : ''}`}
              onClick={() => onColorChange(key)}
              style={{ backgroundColor: color }}
              title={key}
            />
          ))}
          {hasMoreColors && (
            <button
              className="color-chip color-chip-more"
              onClick={() => setShowAllColors(true)}
              title="Més colors"
            >
              <span>+{colors.length - 6}</span>
            </button>
          )}
          {isMobile && showAllColors && (
            <button
              className="color-chip color-chip-less"
              onClick={() => setShowAllColors(false)}
              title="Menys colors"
            >
              <span>−</span>
            </button>
          )}
        </div>
      </div>
    </div>
  );
};

export default ColorSelector;

