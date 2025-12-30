import React, { useState, useEffect, useRef } from 'react';
import { getCurrentTheme } from '../../../colorTheme';

// Mapping of colla names to their color_codes (from colles_fundacio.json)
const COLLA_COLORS = {
  "Al·lots de Llevant": "darkgreen",
  "Arreplegats de la Zona Universitària": "turquese",
  "Bordegassos de Vilanova": "yellow",
  "Capgrossos de Mataró": "darkblue",
  "Castellers d'Altafulla": "lila",
  "Castellers d'Esparreguera": "granate",
  "Castellers d'Esplugues": "blue",
  "Castellers de Badalona": "yellow",
  "Castellers de Barcelona": "red",
  "Castellers de Berga": "darkblue",
  "Castellers de Castelldefels": "yellow",
  "Castellers de la Sagrada Família": "green",
  "Castellers de la Vila de Gràcia": "darkblue",
  "Castellers de Lleida": "granate",
  "Castellers de Sabadell": "darkgreen",
  "Castellers de Sant Cugat": "darkgreen",
  "Castellers de Sants": "gray",
  "Castellers de Sarrià": "granate",
  "Castellers de Terrassa": "darkturquesa",
  "Castellers de Vilafranca": "turquese",
  "Colla Castellera Jove de Barcelona": "granate",
  "Colla Castellera Sant Pere i Sant Pau": "green",
  "Colla Jove de Castellers de Sitges": "granate",
  "Colla Jove Xiquets de Tarragona": "malva",
  "Colla Joves Xiquets de Valls": "red",
  "Colla Vella dels Xiquets de Valls": "rosat",
  "Marrecs de Salt": "blue",
  "Minyons de Terrassa": "malva",
  "Moixiganguers d'Igualada": "lila",
  "Nens del Vendrell": "red",
  "Nois de la Torre": "bluesky",
  "Sagals d'Osona": "orange",
  "Xicots de Vilafranca": "red",
  "Xics de Granollers": "granate",
  "Xiquets de Reus": "brown",
  "Xiquets de Tarragona": "ralles",
  "Xiquets del Serrallo": "darkblue"
};

// Colles with boost >= 2 from json_colles.json
const AVAILABLE_COLLES = [
  "Castellers de Vilafranca",
  "Colla Jove Xiquets de Tarragona",
  "Colla Joves Xiquets de Valls",
  "Colla Vella dels Xiquets de Valls",
  "Minyons de Terrassa",
  "Capgrossos de Mataró",
  "Marrecs de Salt",
  "Moixiganguers d'Igualada",
  "Nens del Vendrell",
  "Xiquets de Reus",
  "Xiquets de Tarragona",
  "Xiquets del Serrallo",
  "Bordegassos de Vilanova",
  "Castellers d'Altafulla",
  "Castellers d'Esparreguera",
  "Castellers d'Esplugues",
  "Castellers de Badalona",
  "Castellers de Barcelona",
  "Castellers de Berga",
  "Castellers de Castelldefels",
  "Castellers de la Sagrada Família",
  "Castellers de la Vila de Gràcia",
  "Castellers de Lleida",
  "Castellers de Sabadell",
  "Castellers de Sant Cugat",
  "Castellers de Sants",
  "Castellers de Sarrià",
  "Castellers de Terrassa",
  "Colla Castellera Jove de Barcelona",
  "Colla Castellera Sant Pere i Sant Pau",
  "Colla Jove de Castellers de Sitges",
  "Nois de la Torre",
  "Sagals d'Osona",
  "Xicots de Vilafranca",
  "Xics de Granollers",
  "Al·lots de Llevant",
  "Arreplegats de la Zona Universitària"
];

// Years 2000-2025 excluding 2020 and 2021
const AVAILABLE_YEARS = Array.from({ length: 26 }, (_, i) => 2000 + i)
  .filter(year => year !== 2020 && year !== 2021).sort((a, b) => b - a); // Sort descending


// Multi-select dropdown component with search
const MultiSelect = ({ options, selected, onChange, placeholder, disabled, displayTransform }) => {
  const [isOpen, setIsOpen] = useState(false);
  const [searchTerm, setSearchTerm] = useState('');
  const dropdownRef = useRef(null);
  const searchInputRef = useRef(null);

  // Lock scroll when dropdown is open
  useEffect(() => {
    if (isOpen) {
      document.body.style.overflow = 'hidden';
      // Focus search input when dropdown opens
      setTimeout(() => searchInputRef.current?.focus(), 0);
    } else {
      document.body.style.overflow = '';
      setSearchTerm(''); // Clear search when closing
    }
    return () => {
      document.body.style.overflow = '';
    };
  }, [isOpen]);

  const closeDropdown = () => {
    setIsOpen(false);
    setSearchTerm('');
  };

  const toggleOption = (option) => {
    if (selected.includes(option)) {
      onChange(selected.filter(item => item !== option));
    } else {
      onChange([...selected, option]);
    }
  };

  // Filter options based on search term
  const filteredOptions = options.filter(option => {
    const displayValue = displayTransform ? displayTransform(option) : option;
    return displayValue.toLowerCase().includes(searchTerm.toLowerCase());
  });

  const selectAll = () => {
    onChange([...filteredOptions]);
    setSearchTerm('');
  };
  
  const clearAll = () => {
    onChange([]);
    setSearchTerm('');
  };

  const getDisplayText = () => {
    if (selected.length === 0) return placeholder;
    if (selected.length === options.length) return `Totes (${options.length})`;
    if (selected.length <= 2) {
      return selected.map(s => displayTransform ? displayTransform(s) : s).join(', ');
    }
    return `${selected.length} seleccionats`;
  };

  return (
    <div className="passafaixa-multiselect" ref={dropdownRef}>
      {isOpen && <div className="passafaixa-multiselect-overlay" onClick={closeDropdown} />}
      <button 
        type="button"
        className={`passafaixa-multiselect-trigger ${isOpen ? 'open' : ''}`}
        onClick={() => !disabled && setIsOpen(!isOpen)}
        disabled={disabled}
      >
        <span className="passafaixa-multiselect-text">{getDisplayText()}</span>
        <span className="passafaixa-multiselect-arrow">{isOpen ? '▲' : '▼'}</span>
      </button>
      {isOpen && (
        <div className="passafaixa-multiselect-dropdown">
          <div className="passafaixa-multiselect-search">
            <input
              ref={searchInputRef}
              type="text"
              placeholder="Cerca..."
              value={searchTerm}
              onChange={(e) => setSearchTerm(e.target.value)}
              className="passafaixa-multiselect-search-input"
              onClick={(e) => e.stopPropagation()}
            />
          </div>
          <div className="passafaixa-multiselect-actions">
            <button type="button" onClick={selectAll} className="passafaixa-multiselect-action">
              {searchTerm ? `Seleccionar (${filteredOptions.length})` : 'Seleccionar tot'}
            </button>
            <button type="button" onClick={clearAll} className="passafaixa-multiselect-action">
              Netejar
            </button>
          </div>
          <div className="passafaixa-multiselect-options">
            {filteredOptions.length > 0 ? (
              filteredOptions.map((option) => (
                <label key={option} className="passafaixa-multiselect-option">
                  <input
                    type="checkbox"
                    checked={selected.includes(option)}
                    onChange={() => toggleOption(option)}
                  />
                  <span>{displayTransform ? displayTransform(option) : option}</span>
                </label>
              ))
            ) : (
              <div className="passafaixa-multiselect-empty">
                No s'han trobat resultats
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
};


const Menu = ({ onStartGame, isLoading, onBack, theme, gameSettings, onSettingsChange, onColorChange, selectedColor }) => {
  const currentTheme = theme || getCurrentTheme();
  const [buttonText, setButtonText] = useState('Jugar');
  const [buttonPulse, setButtonPulse] = useState(false);
  const [loadingDots, setLoadingDots] = useState('');

  // Local state for settings - now arrays for multi-select
  const [numQuestions, setNumQuestions] = useState(gameSettings?.numQuestions || 10);
  const [selectedColles, setSelectedColles] = useState(gameSettings?.colles || []);
  const [selectedYears, setSelectedYears] = useState(gameSettings?.years || []);
  
  // Track previous colla selection to detect changes
  const prevCollesRef = useRef([]);

  // Change color when exactly one colla is newly selected or changed
  useEffect(() => {
    if (!onColorChange) return;
    
    const prevColles = prevCollesRef.current;
    const wasExactlyOne = prevColles.length === 1;
    const isExactlyOne = selectedColles.length === 1;
    
    // Only change color when selecting exactly 1 colla (new selection or different colla)
    if (isExactlyOne) {
      const collaName = selectedColles[0];
      const prevCollaName = prevColles[0];
      
      // Only trigger color change if this is a new single selection or a different colla
      if (!wasExactlyOne || collaName !== prevCollaName) {
        const collaColor = COLLA_COLORS[collaName];
        if (collaColor) {
          onColorChange(collaColor);
        }
      }
    }
    // Don't restore color when deselecting - let user keep their choice
    
    prevCollesRef.current = [...selectedColles];
  }, [selectedColles, onColorChange]);

  useEffect(() => {
    if (isLoading) {
      setButtonText('Carregant');
      let dotCount = 0;
      const interval = setInterval(() => {
        dotCount = (dotCount + 1) % 4;
        setLoadingDots('.'.repeat(dotCount));
      }, 500);
      return () => clearInterval(interval);
    } else {
      setLoadingDots('');
      const playTexts = ['Jugar', 'Començar', 'Endavant!'];
      let textIndex = 0;
      const interval = setInterval(() => {
        setButtonText(playTexts[textIndex]);
        setButtonPulse(true);
        setTimeout(() => setButtonPulse(false), 300);
        textIndex = (textIndex + 1) % playTexts.length;
      }, 2000);
      return () => clearInterval(interval);
    }
  }, [isLoading]);

  // Notify parent of settings changes
  useEffect(() => {
    if (onSettingsChange) {
      onSettingsChange({
        numQuestions,
        colles: selectedColles,
        years: selectedYears
      });
    }
  }, [numQuestions, selectedColles, selectedYears, onSettingsChange]);

  const handleNumQuestionsChange = (e) => {
    const value = parseInt(e.target.value, 10);
    setNumQuestions(value);
  };

  // Handle colles change - clears years (mutually exclusive)
  const handleCollesChange = (newColles) => {
    setSelectedColles(newColles);
    if (newColles.length > 0) {
      setSelectedYears([]); // Clear years when colles are selected
    }
  };

  // Handle years change - clears colles (mutually exclusive)
  const handleYearsChange = (newYears) => {
    setSelectedYears(newYears);
    if (newYears.length > 0) {
      setSelectedColles([]); // Clear colles when years are selected
    }
  };

  // Generate dynamic description based on selections
  const getDescription = () => {
    const hasColles = selectedColles.length > 0;
    const hasYears = selectedYears.length > 0;
    
    const baseText = `Respon a ${numQuestions} preguntes sobre castells, diades, fets castellers, etc.`;
    
    if (!hasColles && !hasYears) {
      return `${baseText} Si vols, pots seleccionar anys o colles específiques per jugar.`;
    }
    
    if (hasColles) {
      if (selectedColles.length === 1) {
        return <>{baseText}<br /><span className="passafaixa-filter-text">Preguntes referents a la colla {selectedColles[0]}.</span></>;
      } else if (selectedColles.length <= 6) {
        const lastColla = selectedColles[selectedColles.length - 1];
        const otherColles = selectedColles.slice(0, -1).join(', ');
        return <>{baseText}<br /><span className="passafaixa-filter-text">Preguntes referents a les colles {otherColles} i {lastColla}.</span></>;
      } else {
        const firstSix = selectedColles.slice(0, 6).join(', ');
        return <>{baseText}<br /><span className="passafaixa-filter-text">Preguntes referents a les colles {firstSix}... (i {selectedColles.length - 6} més).</span></>;
      }
    }
    
    if (hasYears) {
      const sortedYears = [...selectedYears].sort((a, b) => a - b);
      if (sortedYears.length === 1) {
        return <>{baseText}<br /><span className="passafaixa-filter-text">Preguntes referents a l'any {sortedYears[0]}.</span></>;
      } else if (sortedYears.length <= 6) {
        const lastYear = sortedYears[sortedYears.length - 1];
        const otherYears = sortedYears.slice(0, -1).join(', ');
        return <>{baseText}<br /><span className="passafaixa-filter-text">Preguntes referents als anys {otherYears} i {lastYear}.</span></>;
      } else {
        const firstSix = sortedYears.slice(0, 6).join(', ');
        return <>{baseText}<br /><span className="passafaixa-filter-text">Preguntes referents als anys {firstSix}... (i {sortedYears.length - 6} més).</span></>;
      }
    }
    
    return baseText;
  };

  return (
    <div className="passafaixa-menu">
      {/* Left sidebar with options */}
      <div className="passafaixa-menu-sidebar">
        <h3 className="passafaixa-sidebar-title">Personalitza la teva partida</h3>
        
        {/* Number of questions */}
        <div className="passafaixa-sidebar-option">
          <label className="passafaixa-option-label">Nombre de preguntes</label>
          <div className="passafaixa-slider-option">
            <input
              type="range"
              min="5"
              max="20"
              value={numQuestions}
              onChange={handleNumQuestionsChange}
              className="passafaixa-option-slider"
              disabled={isLoading}
            />
            <span className="passafaixa-option-value">{numQuestions}</span>
          </div>
        </div>

        {/* Colla selection */}
        <div className={`passafaixa-sidebar-option ${selectedYears.length > 0 ? 'passafaixa-option-disabled' : ''}`}>
          <label className="passafaixa-option-label">
            Colles
            {selectedYears.length > 0 && <span className="passafaixa-option-hint"> (neteja anys primer)</span>}
          </label>
          <MultiSelect
            options={AVAILABLE_COLLES}
            selected={selectedColles}
            onChange={handleCollesChange}
            placeholder="Totes les colles"
            disabled={isLoading || selectedYears.length > 0}
          />
        </div>

        {/* Year selection */}
        <div className={`passafaixa-sidebar-option ${selectedColles.length > 0 ? 'passafaixa-option-disabled' : ''}`}>
          <label className="passafaixa-option-label">
            Anys
            {selectedColles.length > 0 && <span className="passafaixa-option-hint"> (neteja colles primer)</span>}
          </label>
          <MultiSelect
            options={AVAILABLE_YEARS}
            selected={selectedYears}
            onChange={handleYearsChange}
            placeholder="Tots els anys"
            disabled={isLoading || selectedColles.length > 0}
            displayTransform={(year) => year.toString()}
          />
        </div>
      </div>

      {/* Main content */}
      <div className="passafaixa-menu-content">
        <div className="passafaixa-icon-container">
          <img 
            src={isLoading ? "/xiquet_images/xiquet_loading.png" : "/xiquet_images/xiquet_go.png"}
            alt="Xiquet" 
            className="passafaixa-xiquet-icon"
          />
        </div>
        <div className="passafaixa-menu-text">
          <h1 className="passafaixa-title">El PassaFaixa</h1>
          <p className="passafaixa-subtitle">El joc on pots posar a prova tot el que saps sobre el món casteller. En sabràs més que jo?</p>
          <p className="passafaixa-description">{getDescription()}</p>
          <button 
            className={`passafaixa-play-btn ${buttonPulse ? 'pulse' : ''}`}
            onClick={onStartGame}
            disabled={isLoading}
          >
            <span className="button-text">
              {buttonText}
              {isLoading && <span className="loading-dots">{loadingDots}</span>}
            </span>
            {!isLoading && <span className="button-arrow">→</span>}
          </button>
        </div>
      </div>
    </div>
  );
};

export default Menu;

