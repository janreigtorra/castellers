import React, { useState, useEffect, useRef } from 'react';
import { createPortal } from 'react-dom';
import { apiService } from '../apiService';
import './CompararDiades.css';
import '../components/JocDelMocador/JocDelMocador.css';
import PilarLoader from './PilarLoader';
import { COLOR_THEMES, getThemeForColor } from '../colorTheme';
import collesData from '../data/colles_fundacio.json';

// Build a map from colla name to color_code from the JSON
const COLLES_COLORS = collesData.reduce((acc, colla) => {
  acc[colla.name] = colla.color_code;
  return acc;
}, {});

// Map color codes to theme keys
const COLOR_CODE_TO_THEME = {
  'darkgreen': 'darkgreen',
  'skyblue': 'bluesky',
  'turquese': 'turquese',
  'lightgreen': 'lightgreen',
  'yellow': 'yellow',
  'darkblue': 'darkblue',
  'lila': 'lila',
  'granate': 'granate',
  'blue': 'blue',
  'red': 'red',
  'green': 'green',
  'brown': 'brown',
  'gray': 'gray',
  'rosat': 'rosat',
  'malva': 'malva',
  'orange': 'orange',
  'white': 'white',
  'darkturquesa': 'darkturquesa',
  'ralles': 'ralles'
};

const getCollaTheme = (collaName) => {
  if (!collaName) return null;
  const colorCode = COLLES_COLORS[collaName];
  if (!colorCode || colorCode === 'white') return null;
  const themeKey = COLOR_CODE_TO_THEME[colorCode];
  if (!themeKey || !COLOR_THEMES[themeKey]) return null;
  return getThemeForColor(themeKey);
};

// Single-select dropdown component with search (based on MultiSelect from Menu.js)
const SingleSelect = ({ options, selected, onChange, placeholder, disabled, displayTransform, getOptionKey }) => {
  const [isOpen, setIsOpen] = useState(false);
  const [searchTerm, setSearchTerm] = useState('');
  const [dropdownPosition, setDropdownPosition] = useState({ top: 0, left: 0, width: 0 });
  const dropdownRef = useRef(null);
  const dropdownPortalRef = useRef(null);
  const triggerRef = useRef(null);
  const searchInputRef = useRef(null);

  // Helper to compare options (handles both primitives and objects)
  const isOptionEqual = (opt1, opt2) => {
    if (opt1 === opt2) return true;
    if (!opt1 || !opt2) return false;
    if (getOptionKey) {
      return getOptionKey(opt1) === getOptionKey(opt2);
    }
    if (typeof opt1 === 'object' && typeof opt2 === 'object') {
      // For objects, compare by event_id if available
      return opt1.event_id === opt2.event_id;
    }
    return false;
  };

  // Calculate dropdown position when opening
  useEffect(() => {
    if (isOpen && triggerRef.current) {
      const rect = triggerRef.current.getBoundingClientRect();
      const viewportHeight = window.innerHeight;
      const dropdownHeight = 300; // max-height from CSS
      const spaceBelow = viewportHeight - rect.bottom;
      const spaceAbove = rect.top;
      
      // Position below if there's enough space, otherwise above
      const shouldPositionAbove = spaceBelow < dropdownHeight && spaceAbove > spaceBelow;
      
      setDropdownPosition({
        top: shouldPositionAbove 
          ? rect.top + window.scrollY - Math.min(dropdownHeight, spaceAbove - 10)
          : rect.bottom + window.scrollY,
        left: rect.left + window.scrollX,
        width: rect.width,
        positionAbove: shouldPositionAbove
      });
      setTimeout(() => searchInputRef.current?.focus(), 0);
    } else {
      setSearchTerm('');
    }
  }, [isOpen]);

  // Lock scroll when dropdown is open
  useEffect(() => {
    if (isOpen) {
      document.body.style.overflow = 'hidden';
    } else {
      document.body.style.overflow = '';
    }
    return () => {
      document.body.style.overflow = '';
    };
  }, [isOpen]);

  const closeDropdown = () => {
    setIsOpen(false);
    setSearchTerm('');
  };

  const selectOption = (option) => {
    onChange(option);
    closeDropdown();
  };

  // Filter options based on search term
  const filteredOptions = options.filter(option => {
    const displayValue = displayTransform ? displayTransform(option) : option;
    return displayValue.toLowerCase().includes(searchTerm.toLowerCase());
  });

  const getDisplayText = () => {
    if (!selected) return placeholder;
    return displayTransform ? displayTransform(selected) : selected;
  };

  // Close dropdown when clicking outside
  useEffect(() => {
    const handleClickOutside = (event) => {
      const clickedTrigger = triggerRef.current && triggerRef.current.contains(event.target);
      const clickedDropdown = dropdownPortalRef.current && dropdownPortalRef.current.contains(event.target);
      
      if (!clickedTrigger && !clickedDropdown) {
        closeDropdown();
      }
    };

    if (isOpen) {
      document.addEventListener('mousedown', handleClickOutside);
      return () => document.removeEventListener('mousedown', handleClickOutside);
    }
  }, [isOpen]);

  // Get unique key for option (for React key prop)
  const getOptionKeyValue = (option) => {
    if (getOptionKey) return getOptionKey(option);
    if (typeof option === 'object' && option.event_id) return option.event_id;
    return option;
  };

  return (
    <div className="joc-mocador-multiselect" ref={dropdownRef}>
      {isOpen && createPortal(
        <div className="joc-mocador-multiselect-overlay" onClick={closeDropdown} style={{ zIndex: 9999 }} />,
        document.body
      )}
      <button 
        ref={triggerRef}
        type="button"
        className={`joc-mocador-multiselect-trigger ${isOpen ? 'open' : ''} ${isOpen && dropdownPosition.positionAbove ? 'open-above' : ''}`}
        onClick={() => !disabled && setIsOpen(!isOpen)}
        disabled={disabled}
      >
        <span className="joc-mocador-multiselect-text">{getDisplayText()}</span>
        <span className="joc-mocador-multiselect-arrow">{isOpen ? '▲' : '▼'}</span>
      </button>
      {isOpen && createPortal(
        <div 
          ref={dropdownPortalRef}
          className={`joc-mocador-multiselect-dropdown ${dropdownPosition.positionAbove ? 'position-above' : ''}`}
          style={{
            position: 'fixed',
            top: `${dropdownPosition.top}px`,
            left: `${dropdownPosition.left}px`,
            width: `${dropdownPosition.width}px`,
            zIndex: 10000
          }}
          onClick={(e) => e.stopPropagation()}
        >
          <div className="joc-mocador-multiselect-search">
            <input
              ref={searchInputRef}
              type="text"
              placeholder="Cerca..."
              value={searchTerm}
              onChange={(e) => setSearchTerm(e.target.value)}
              className="joc-mocador-multiselect-search-input"
              onClick={(e) => e.stopPropagation()}
            />
          </div>
          <div className="joc-mocador-multiselect-options">
            {filteredOptions.length > 0 ? (
              filteredOptions.map((option) => {
                const isSelected = isOptionEqual(selected, option);
                return (
                  <div
                    key={getOptionKeyValue(option)}
                    className={`joc-mocador-multiselect-option ${isSelected ? 'selected' : ''}`}
                    onClick={(e) => {
                      e.stopPropagation();
                      selectOption(option);
                    }}
                  >
                    <span>{displayTransform ? displayTransform(option) : option}</span>
                    {isSelected && <span style={{ color: 'var(--theme-accent)', fontWeight: 'bold' }}>✓</span>}
                  </div>
                );
              })
            ) : (
              <div className="joc-mocador-multiselect-empty">
                No s'han trobat resultats
              </div>
            )}
          </div>
        </div>,
        document.body
      )}
    </div>
  );
};

const CompararDiades = ({ theme, onBack }) => {
  const [colles, setColles] = useState([]);
  const [anys, setAnys] = useState([]);
  const [loading, setLoading] = useState(true);
  
  // Diada 1 state
  const [colla1, setColla1] = useState(null);
  const [any1, setAny1] = useState(null);
  const [diades1, setDiades1] = useState([]);
  const [diada1, setDiada1] = useState(null);
  const [diada1Details, setDiada1Details] = useState(null);
  const [loadingDiada1, setLoadingDiada1] = useState(false);
  
  // Diada 2 state
  const [colla2, setColla2] = useState(null);
  const [any2, setAny2] = useState(null);
  const [diades2, setDiades2] = useState([]);
  const [diada2, setDiada2] = useState(null);
  const [diada2Details, setDiada2Details] = useState(null);
  const [loadingDiada2, setLoadingDiada2] = useState(false);
  
  // Comparison parameters
  const [castellsCount, setCastellsCount] = useState(3);
  const [pilarsCount, setPilarsCount] = useState(1);

  // Fetch colles and anys on mount
  useEffect(() => {
    const fetchData = async () => {
      try {
        setLoading(true);
        const [collesData, entityOptions] = await Promise.all([
          apiService.getColles(),
          apiService.getEntityOptions()
        ]);
        
        setColles(collesData.colles || []);
        
        // Extract years from entity options and sort descending
        const years = (entityOptions.anys || []).map(y => parseInt(y)).filter(y => !isNaN(y)).sort((a, b) => b - a);
        setAnys(years);
      } catch (err) {
        // Error fetching initial data
      } finally {
        setLoading(false);
      }
    };
    
    fetchData();
  }, []);

  // Fetch diades when colla1 and any1 change
  useEffect(() => {
    if (colla1 && any1) {
      const fetchDiades = async () => {
        try {
          const collaId = colles.find(c => c.name === colla1)?.colla_id || colles.find(c => c.name === colla1)?.id;
          const data = await apiService.getDiades(collaId, any1);
          setDiades1(data.diades || []);
          setDiada1(null);
          setDiada1Details(null);
        } catch (err) {
          setDiades1([]);
        }
      };
      fetchDiades();
    } else {
      setDiades1([]);
      setDiada1(null);
      setDiada1Details(null);
    }
  }, [colla1, any1, colles]);

  // Fetch diades when colla2 and any2 change
  useEffect(() => {
    if (colla2 && any2) {
      const fetchDiades = async () => {
        try {
          const collaId = colles.find(c => c.name === colla2)?.colla_id || colles.find(c => c.name === colla2)?.id;
          const data = await apiService.getDiades(collaId, any2);
          setDiades2(data.diades || []);
          setDiada2(null);
          setDiada2Details(null);
        } catch (err) {
          setDiades2([]);
        }
      };
      fetchDiades();
    } else {
      setDiades2([]);
      setDiada2(null);
      setDiada2Details(null);
    }
  }, [colla2, any2, colles]);

  // Fetch diada 1 details when diada1 or comparisonMode changes
  useEffect(() => {
    if (diada1 && colla1) {
      const fetchDetails = async () => {
        try {
          setLoadingDiada1(true);
          const colla = colles.find(c => c.name === colla1);
          if (!colla) {
            setDiada1Details(null);
            return;
          }
          const collaIdentifier = colla1;
          const data = await apiService.getDiadaDetails(diada1.event_id, collaIdentifier, castellsCount, pilarsCount);
          setDiada1Details(data);
        } catch (err) {
          setDiada1Details(null);
        } finally {
          setLoadingDiada1(false);
        }
      };
      fetchDetails();
    } else {
      setDiada1Details(null);
    }
  }, [diada1, castellsCount, pilarsCount, colla1, colles]);

  // Fetch diada 2 details when diada2 or comparisonMode changes
  useEffect(() => {
    if (diada2 && colla2) {
      const fetchDetails = async () => {
        try {
          setLoadingDiada2(true);
          const colla = colles.find(c => c.name === colla2);
          if (!colla) {
            setDiada2Details(null);
            return;
          }
          const collaIdentifier = colla2;
          const data = await apiService.getDiadaDetails(diada2.event_id, collaIdentifier, castellsCount, pilarsCount);
          setDiada2Details(data);
        } catch (err) {
          setDiada2Details(null);
        } finally {
          setLoadingDiada2(false);
        }
      };
      fetchDetails();
    } else {
      setDiada2Details(null);
    }
  }, [diada2, castellsCount, pilarsCount, colla2, colles]);

  const colla1Theme = colla1 ? getCollaTheme(colla1) : null;
  const colla2Theme = colla2 ? getCollaTheme(colla2) : null;

  // Helper to get safe color (red if white or null)
  const getSafeColor = (color) => {
    if (!color || color === '#ffffff' || color === 'white' || color === '#fff') {
      return '#d0282c'; // Default red
    }
    return color;
  };

  // Get safe theme color for UI elements
  const safeThemeColor = getSafeColor(theme?.secondary);

  const formatDiadaName = (diada) => {
    if (!diada) return '';
    const parts = [diada.event_name];
    if (diada.event_date) parts.push(`(${diada.event_date})`);
    if (diada.event_city) parts.push(`- ${diada.event_city}`);
    return parts.join(' ');
  };

  if (loading) {
    return (
      <div className="comparar-diades-container">
        <PilarLoader theme={theme} />
      </div>
    );
  }

  return (
    <div className="comparar-diades-container" style={{ '--theme-color': theme?.secondary, '--theme-accent': theme?.accent, '--safe-theme-color': safeThemeColor }}>
      <div className="comparar-diades-header">
        <button className="back-button" style={{ color: safeThemeColor }} onClick={onBack}>
          <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
            <path d="M19 12H5M12 19l-7-7 7-7" />
          </svg>
          Tornar
        </button>
        <h1>Comparar Diades</h1>
      </div>

      {/* Comparison Parameters Selector */}
      <div className="comparison-mode-selector">
        <label>Paràmetres de comparació:</label>
        <div className="mode-buttons">
          <div className="comparison-param">
            <label htmlFor="castells-count">Top Castells:</label>
            <input
              id="castells-count"
              type="number"
              min="0"
              max="10"
              value={castellsCount}
              onChange={(e) => {
                const inputVal = e.target.value;
                if (inputVal === '') {
                  setCastellsCount(0);
                  return;
                }
                const val = parseInt(inputVal, 10);
                if (!isNaN(val) && val >= 0 && val <= 10) {
                  setCastellsCount(val);
                }
              }}
              className="comparison-input"
              style={{
                borderColor: safeThemeColor,
                color: theme?.text || '#000'
              }}
            />
          </div>
          <div className="comparison-param">
            <label htmlFor="pilars-count">Top Pilars:</label>
            <input
              id="pilars-count"
              type="number"
              min="0"
              max="10"
              value={pilarsCount}
              onChange={(e) => {
                const inputVal = e.target.value;
                if (inputVal === '') {
                  setPilarsCount(0);
                  return;
                }
                const val = parseInt(inputVal, 10);
                if (!isNaN(val) && val >= 0 && val <= 10) {
                  setPilarsCount(val);
                }
              }}
              className="comparison-input"
              style={{
                borderColor: safeThemeColor,
                color: theme?.text || '#000'
              }}
            />
          </div>
        </div>
      </div>

      {/* Selection Section */}
      <div className="diades-selection">
        {/* Diada 1 */}
        <div className="diada-selector" style={{ '--colla-color': colla1Theme?.secondary || theme?.secondary }}>
          <h2>Diada 1</h2>
          <div className="joc-mocador-sidebar-option">
            <label className="joc-mocador-option-label">Colla</label>
            <SingleSelect
              options={colles.map(c => c.name)}
              selected={colla1}
              onChange={setColla1}
              placeholder="Selecciona una colla"
            />
          </div>
          
          {colla1 && (
            <div className="joc-mocador-sidebar-option">
              <label className="joc-mocador-option-label">Any</label>
              <SingleSelect
                options={anys}
                selected={any1}
                onChange={setAny1}
                placeholder="Selecciona un any"
                displayTransform={(year) => year.toString()}
              />
            </div>
          )}
          
          {colla1 && any1 && (
            <div className="joc-mocador-sidebar-option">
              <label className="joc-mocador-option-label">Diada</label>
              <SingleSelect
                options={diades1}
                selected={diada1}
                onChange={setDiada1}
                placeholder={diades1.length === 0 ? 'No hi ha diades disponibles' : 'Selecciona una diada'}
                disabled={diades1.length === 0}
                displayTransform={(diada) => formatDiadaName(diada)}
                getOptionKey={(diada) => diada.event_id}
              />
            </div>
          )}
        </div>

        {/* VS Divider */}
        <div className="vs-divider">
          <span style={{ color: safeThemeColor, borderColor: safeThemeColor }}>VS</span>
        </div>

        {/* Diada 2 */}
        <div className="diada-selector" style={{ '--colla-color': colla2Theme?.secondary || theme?.secondary }}>
          <h2>Diada 2</h2>
          <div className="joc-mocador-sidebar-option">
            <label className="joc-mocador-option-label">Colla</label>
            <SingleSelect
              options={colles.map(c => c.name)}
              selected={colla2}
              onChange={setColla2}
              placeholder="Selecciona una colla"
            />
          </div>
          
          {colla2 && (
            <div className="joc-mocador-sidebar-option">
              <label className="joc-mocador-option-label">Any</label>
              <SingleSelect
                options={anys}
                selected={any2}
                onChange={setAny2}
                placeholder="Selecciona un any"
                displayTransform={(year) => year.toString()}
              />
            </div>
          )}
          
          {colla2 && any2 && (
            <div className="joc-mocador-sidebar-option">
              <label className="joc-mocador-option-label">Diada</label>
              <SingleSelect
                options={diades2}
                selected={diada2}
                onChange={setDiada2}
                placeholder={diades2.length === 0 ? 'No hi ha diades disponibles' : 'Selecciona una diada'}
                disabled={diades2.length === 0}
                displayTransform={(diada) => formatDiadaName(diada)}
                getOptionKey={(diada) => diada.event_id}
              />
            </div>
          )}
        </div>
      </div>

      {/* Comparison Results */}
      {(diada1Details || diada2Details) && (
        <div className="comparison-results">
          <div className="comparison-side">
            {loadingDiada1 ? (
              <div className="loading-placeholder">
                <PilarLoader theme={colla1Theme || theme} />
              </div>
            ) : diada1Details ? (
              <DiadaCard 
                diada={diada1Details} 
                theme={colla1Theme || theme}
                isWinner={diada1Details && diada2Details && diada1Details.total_punts > diada2Details.total_punts}
              />
            ) : (
              <div className="empty-placeholder">
                <p>Selecciona una diada per comparar</p>
              </div>
            )}
          </div>

          <div className="comparison-side">
            {loadingDiada2 ? (
              <div className="loading-placeholder">
                <PilarLoader theme={colla2Theme || theme} />
              </div>
            ) : diada2Details ? (
              <DiadaCard 
                diada={diada2Details} 
                theme={colla2Theme || theme}
                isWinner={diada1Details && diada2Details && diada2Details.total_punts > diada1Details.total_punts}
              />
            ) : (
              <div className="empty-placeholder">
                <p>Selecciona una diada per comparar</p>
              </div>
            )}
          </div>
        </div>
      )}

    </div>
  );
};

// Diada Card Component
const DiadaCard = ({ diada, theme, isWinner = false }) => {
  const [showAllCastells, setShowAllCastells] = useState(false);
  
  const collaTheme = diada.colla_name ? getCollaTheme(diada.colla_name) : null;
  const cardTheme = collaTheme || theme;
  
  // Helper to get safe color (red if white or null)
  const getSafeColor = (color) => {
    if (!color || color === '#ffffff' || color === 'white' || color === '#fff') {
      return '#d0282c'; // Default red
    }
    return color;
  };
  
  const safeCollaColor = getSafeColor(cardTheme?.secondary || theme?.secondary);
  
  // Sort castells: counted first, then not counted
  const sortedCastells = [...(diada.castells || [])].sort((a, b) => {
    if (a.is_counted && !b.is_counted) return -1;
    if (!a.is_counted && b.is_counted) return 1;
    return 0;
  });
  
  // Show first 5, or all if showAllCastells is true
  const displayedCastells = showAllCastells ? sortedCastells : sortedCastells.slice(0, 5);
  const hasMoreCastells = sortedCastells.length > 5;

  return (
    <div className="diada-card" style={{ '--colla-color': cardTheme?.secondary, '--colla-accent': cardTheme?.accent }}>
      <div className="diada-card-header">
        {diada.colla_logo_url && (
          <img src={diada.colla_logo_url} alt={diada.colla_name} className="colla-logo" />
        )}
        <div className="diada-card-title">
          <h3 className="diada-card-title-text">{diada.colla_name}</h3>
          <p className="diada-name diada-card-title-text">{diada.event_name}</p>
          <p className="diada-meta">
            {diada.event_date && <span>{diada.event_date}</span>}
            {diada.event_city && <span> • {diada.event_city}</span>}
          </p>
        </div>
      </div>

      <div className="diada-card-body">
        <div className="total-punts-display" style={{ backgroundColor: safeCollaColor }}>
          <span className="total-punts-label">Total Punts:</span>
          <div className="total-punts-value-container">
            {isWinner && (
              <svg className="trophy-icon" width="20" height="20" viewBox="0 0 16 16" fill="none" xmlns="http://www.w3.org/2000/svg">
                <path fillRule="evenodd" clipRule="evenodd" d="M4 0H12V2H16V4C16 6.45641 14.2286 8.49909 11.8936 8.92038C11.5537 10.3637 10.432 11.5054 9 11.874V14H12V16H4V14H7V11.874C5.56796 11.5054 4.44628 10.3637 4.1064 8.92038C1.77136 8.49909 0 6.45641 0 4V2H4V0ZM12 6.82929V4H14C14 5.30622 13.1652 6.41746 12 6.82929ZM4 4H2C2 5.30622 2.83481 6.41746 4 6.82929V4Z" fill="currentColor" />
              </svg>
            )}
            <span className="total-punts-value">{diada.total_punts}</span>
          </div>
        </div>

        <div className="castells-list">
          <h4>Castells:</h4>
          <div className="castells-grid">
            {displayedCastells.map((castell, idx) => (
              <div
                key={idx}
                className={`castell-item ${castell.is_counted ? 'counted' : 'not-counted'} ${castell.tipus}`}
              >
                <div className="castell-name">{castell.castell_name}</div>
                <div className="castell-status">{castell.status}</div>
                <div className="castell-punts">
                  {castell.punts_missing ? '? punts' : `${castell.punts} punts`}
                </div>
              </div>
            ))}
            {hasMoreCastells && !showAllCastells && (
              <div 
                className="castell-item show-more-button"
                onClick={() => setShowAllCastells(true)}
                style={{ cursor: 'pointer' }}
              >
                <div className="show-more-text">
                  + mostra més castells/ pilars
                </div>
              </div>
            )}
            {showAllCastells && hasMoreCastells && (
              <div 
                className="castell-item show-more-button"
                onClick={() => setShowAllCastells(false)}
                style={{ cursor: 'pointer' }}
              >
                <div className="show-more-text">
                  mostra menys
                </div>
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
};

export default CompararDiades;

