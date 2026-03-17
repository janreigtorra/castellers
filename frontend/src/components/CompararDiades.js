import React, { useState, useEffect, useRef } from 'react';
import { createPortal } from 'react-dom';
import { apiService } from '../apiService';
import { authHelpers } from '../supabaseClient';
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

const STATUS_OPTIONS = ['Descarregat', 'Carregat', 'Intent desmuntat', 'Intent'];

const normalizeCastellName = (value) =>
  String(value || '')
    .toLowerCase()
    .replace(/\s+/g, '')
    .replace(/-/g, '');

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
      const maxAvailableHeight = shouldPositionAbove
        ? Math.max(160, spaceAbove - 10)
        : Math.max(160, spaceBelow - 10);
      
      setDropdownPosition({
        top: shouldPositionAbove
          ? rect.top + window.scrollY
          : rect.bottom + window.scrollY,
        left: rect.left + window.scrollX,
        width: rect.width,
        positionAbove: shouldPositionAbove,
        maxHeight: Math.min(dropdownHeight, maxAvailableHeight)
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
            maxHeight: `${dropdownPosition.maxHeight || 300}px`,
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

const SimulationEntryRow = ({ index, label, value, options, onChange, emptyPlaceholder }) => {
  return (
    <div className="simulation-castell-row">
      <div className="simulation-castell-field">
        <label>{label} {index + 1}</label>
        <SingleSelect
          options={options}
          selected={value.castell}
          onChange={(castell) => onChange({ ...value, castell })}
          placeholder={emptyPlaceholder}
          disabled={options.length === 0}
          displayTransform={(castell) => castell.castell_name}
          getOptionKey={(castell) => castell.castell_name}
        />
      </div>

      <div className="simulation-castell-field">
        <label>Estat</label>
        <SingleSelect
          options={STATUS_OPTIONS}
          selected={value.status}
          onChange={(status) => onChange({ ...value, status })}
          placeholder="Selecciona un estat"
        />
      </div>
    </div>
  );
};

const CompararDiades = ({ theme, onBack }) => {
  const [colles, setColles] = useState([]);
  const [anys, setAnys] = useState([]);
  const [castellsCatalog, setCastellsCatalog] = useState([]);
  const [currentUserName, setCurrentUserName] = useState('Usuari');
  const [loading, setLoading] = useState(true);
  const [showScoreTable, setShowScoreTable] = useState(false);
  
  // Diada 1 state
  const [diada1Mode, setDiada1Mode] = useState('database');
  const [colla1, setColla1] = useState(null);
  const [any1, setAny1] = useState(null);
  const [diades1, setDiades1] = useState([]);
  const [diada1, setDiada1] = useState(null);
  const [diada1Details, setDiada1Details] = useState(null);
  const [loadingDiada1, setLoadingDiada1] = useState(false);
  const [simulationCastells1, setSimulationCastells1] = useState([]);
  const [simulationPilars1, setSimulationPilars1] = useState([]);
  
  // Diada 2 state
  const [diada2Mode, setDiada2Mode] = useState('database');
  const [colla2, setColla2] = useState(null);
  const [any2, setAny2] = useState(null);
  const [diades2, setDiades2] = useState([]);
  const [diada2, setDiada2] = useState(null);
  const [diada2Details, setDiada2Details] = useState(null);
  const [loadingDiada2, setLoadingDiada2] = useState(false);
  const [simulationCastells2, setSimulationCastells2] = useState([]);
  const [simulationPilars2, setSimulationPilars2] = useState([]);
  
  // Comparison parameters
  const [castellsCount, setCastellsCount] = useState(3);
  const [pilarsCount, setPilarsCount] = useState(1);

  // Fetch colles and anys on mount
  useEffect(() => {
    const fetchData = async () => {
      try {
        setLoading(true);
        const [collesData, entityOptions, castellsCatalogData] = await Promise.all([
          apiService.getColles(),
          apiService.getEntityOptions(),
          apiService.getCastellsCatalog()
        ]);
        
        setColles(collesData.colles || []);
        setCastellsCatalog(castellsCatalogData.castells || []);
        
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

  useEffect(() => {
    const fetchCurrentUser = async () => {
      const { user } = await authHelpers.getCurrentUser();
      setCurrentUserName(user?.user_metadata?.username || user?.email?.split('@')[0] || 'Usuari');
    };

    fetchCurrentUser();
  }, []);

  useEffect(() => {
    const createEmptyRow = () => ({ castell: null, status: 'Descarregat' });

    const buildSimulationRows = (currentRows) => {
      const normalizedRows = Array.isArray(currentRows) ? currentRows.slice(0, castellsCount) : [];
      while (normalizedRows.length < castellsCount) {
        normalizedRows.push(createEmptyRow());
      }
      return normalizedRows;
    };

    const buildPilotRows = (currentRows) => {
      const normalizedRows = Array.isArray(currentRows) ? currentRows.slice(0, pilarsCount) : [];
      while (normalizedRows.length < pilarsCount) {
        normalizedRows.push(createEmptyRow());
      }
      return normalizedRows;
    };

    setSimulationCastells1((currentRows) => (diada1Mode === 'simulated' ? buildSimulationRows(currentRows) : currentRows.slice(0, castellsCount)));
    setSimulationPilars1((currentRows) => (diada1Mode === 'simulated' ? buildPilotRows(currentRows) : currentRows.slice(0, pilarsCount)));
    setSimulationCastells2((currentRows) => (diada2Mode === 'simulated' ? buildSimulationRows(currentRows) : currentRows.slice(0, castellsCount)));
    setSimulationPilars2((currentRows) => (diada2Mode === 'simulated' ? buildPilotRows(currentRows) : currentRows.slice(0, pilarsCount)));
  }, [castellsCount, pilarsCount, diada1Mode, diada2Mode]);

  // Fetch diades when colla1 and any1 change
  useEffect(() => {
    if (diada1Mode !== 'database') {
      setDiades1([]);
      return;
    }

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
  }, [colla1, any1, colles, diada1Mode]);

  // Fetch diades when colla2 and any2 change
  useEffect(() => {
    if (diada2Mode !== 'database') {
      setDiades2([]);
      return;
    }

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
  }, [colla2, any2, colles, diada2Mode]);

  // Fetch diada 1 details when diada1 or comparisonMode changes
  useEffect(() => {
    if (diada1Mode !== 'database') {
      setDiada1Details(null);
      setLoadingDiada1(false);
      return;
    }

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
  }, [diada1, castellsCount, pilarsCount, colla1, colles, diada1Mode]);

  // Fetch diada 2 details when diada2 or comparisonMode changes
  useEffect(() => {
    if (diada2Mode !== 'database') {
      setDiada2Details(null);
      setLoadingDiada2(false);
      return;
    }

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
  }, [diada2, castellsCount, pilarsCount, colla2, colles, diada2Mode]);

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

  const canMirrorColla = (sourceColla) => {
    if (!sourceColla) return false;
    return colles.some((colla) => colla.name === sourceColla);
  };

  const canMirrorAny = (sourceAny) => {
    if (sourceAny === null || sourceAny === undefined) return false;
    return anys.includes(sourceAny);
  };

  const canMirrorDiada = (sourceDiada, targetDiades) => {
    if (!sourceDiada) return false;
    return targetDiades.some((diada) => String(diada.event_id) === String(sourceDiada.event_id));
  };

  const isPilarName = (name) => normalizeCastellName(name).startsWith('p');
  const castellOptions = castellsCatalog.filter((item) => !isPilarName(item.castell_name));
  const pilarOptions = castellsCatalog.filter((item) => isPilarName(item.castell_name));

  const getCastellPoints = (castellName, status) => {
    const catalogEntry = castellsCatalog.find((item) => normalizeCastellName(item.castell_name) === normalizeCastellName(castellName));
    if (!catalogEntry) {
      return { punts: 0, puntsMissing: true };
    }

    if (status === 'Descarregat') {
      return {
        punts: catalogEntry.punts_descarregat || 0,
        puntsMissing: catalogEntry.punts_descarregat === null || catalogEntry.punts_descarregat === undefined
      };
    }

    if (status === 'Carregat') {
      return {
        punts: catalogEntry.punts_carregat || 0,
        puntsMissing: catalogEntry.punts_carregat === null || catalogEntry.punts_carregat === undefined
      };
    }

    return { punts: 0, puntsMissing: false };
  };

  const buildSimulatedDiada = (rows) => {
    const castells = (rows || [])
      .map((row) => {
        if (!row?.castell?.castell_name || !row?.status) {
          return null;
        }

        const { punts, puntsMissing } = getCastellPoints(row.castell.castell_name, row.status);
        return {
          castell_name: row.castell.castell_name,
          status: row.status,
          punts,
          punts_missing: puntsMissing && (row.status === 'Descarregat' || row.status === 'Carregat'),
          tipus: row.castell.castell_name.toLowerCase().startsWith('p') ? 'pilar' : 'castell',
          is_counted: true
        };
      })
      .filter(Boolean);

    const total_punts = castells.reduce((sum, castell) => sum + (castell.punts || 0), 0);

    return {
      event_id: `simulated-${currentUserName || 'user'}`,
      event_name: 'Diada simulada',
      event_date: null,
      event_city: null,
      event_place: null,
      colla_id: 'simulated',
      colla_name: `Colla ${currentUserName || 'Usuari'}`,
      colla_logo_url: null,
      castells,
      total_punts,
      castells_count: castellsCount,
      pilars_count: pilarsCount,
      is_simulated: true
    };
  };

  const buildSimulatedRows = (rows, count, defaultStatus = 'Descarregat') => {
    const normalizedRows = Array.isArray(rows) ? rows.slice(0, count) : [];
    while (normalizedRows.length < count) {
      normalizedRows.push({ castell: null, status: defaultStatus });
    }
    return normalizedRows;
  };

  const handleModeToggle = (side) => {
    if (side === 'left') {
      setDiada1Mode((mode) => {
        const nextMode = mode === 'simulated' ? 'database' : 'simulated';
        if (nextMode === 'simulated') {
          setColla1(null);
          setAny1(null);
          setDiada1(null);
          setDiada1Details(null);
          setSimulationCastells1((rows) => buildSimulatedRows(rows, castellsCount));
          setSimulationPilars1((rows) => buildSimulatedRows(rows, pilarsCount));
        }
        return nextMode;
      });
      return;
    }

    setDiada2Mode((mode) => {
      const nextMode = mode === 'simulated' ? 'database' : 'simulated';
      if (nextMode === 'simulated') {
        setColla2(null);
        setAny2(null);
        setDiada2(null);
        setDiada2Details(null);
        setSimulationCastells2((rows) => buildSimulatedRows(rows, castellsCount));
        setSimulationPilars2((rows) => buildSimulatedRows(rows, pilarsCount));
      }
      return nextMode;
    });
  };

  const updateSimulationCastell = (side, kind, index, nextValue) => {
    const updater =
      side === 'left'
        ? kind === 'castell'
          ? setSimulationCastells1
          : setSimulationPilars1
        : kind === 'castell'
          ? setSimulationCastells2
          : setSimulationPilars2;
    updater((rows) => rows.map((row, rowIndex) => (rowIndex === index ? nextValue : row)));
  };

  const displayDiada1Details = diada1Mode === 'simulated' ? buildSimulatedDiada([...simulationCastells1, ...simulationPilars1]) : diada1Details;
  const displayDiada2Details = diada2Mode === 'simulated' ? buildSimulatedDiada([...simulationCastells2, ...simulationPilars2]) : diada2Details;
  const scoreTableRows = [...castellsCatalog].sort((a, b) => {
    const pointsA = Number(a?.punts_descarregat ?? -1);
    const pointsB = Number(b?.punts_descarregat ?? -1);

    if (pointsA !== pointsB) return pointsB - pointsA;
    return String(a?.castell_name || '').localeCompare(String(b?.castell_name || ''));
  });

  const MirrorButton = ({ label, onClick, disabled = false }) => (
    <button
      type="button"
      className="comparison-copy-button"
      onClick={onClick}
      disabled={disabled}
    >
      {label}
    </button>
  );

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
        <button
          type="button"
          className="score-table-button"
          onClick={() => setShowScoreTable(true)}
        >
          Taula de puntuacions
        </button>
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
          <div className="diada-selector-title-row">
            <h2>Diada 1</h2>
            <button
              type="button"
              className={`simulation-mode-button ${diada1Mode === 'simulated' ? 'active' : ''}`}
              onClick={() => handleModeToggle('left')}
            >
              {diada1Mode === 'simulated' ? 'Seleccionar diada' : 'Simular diada'}
            </button>
          </div>
          <div className="diada-selector-title-line" aria-hidden="true" />

          {diada1Mode === 'database' ? (
            <>
              <div className="joc-mocador-sidebar-option">
                <div className="comparison-field-header">
                  <label className="joc-mocador-option-label">Colla</label>
                  {!colla1 && canMirrorColla(colla2) && colla2 !== colla1 && (
                    <MirrorButton label="Mateixa colla" onClick={() => setColla1(colla2)} />
                  )}
                </div>
                <SingleSelect
                  options={colles.map(c => c.name)}
                  selected={colla1}
                  onChange={setColla1}
                  placeholder="Selecciona una colla"
                />
              </div>

              {colla1 && (
                <div className="joc-mocador-sidebar-option">
                  <div className="comparison-field-header">
                    <label className="joc-mocador-option-label">Any</label>
                    {!any1 && canMirrorAny(any2) && any2 !== any1 && (
                      <MirrorButton label="Mateix any" onClick={() => setAny1(any2)} />
                    )}
                  </div>
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
                  <div className="comparison-field-header">
                    <label className="joc-mocador-option-label">Diada</label>
                    {!diada1 && canMirrorDiada(diada2, diades1) && (
                      <MirrorButton label="Mateixa diada" onClick={() => setDiada1(diada2)} />
                    )}
                  </div>
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
            </>
          ) : (
            <div className="simulation-mode-panel">
              <p className="simulation-helper-text">
                Defineix fins a {castellsCount} castells i {pilarsCount} pilars amb el seu estat per calcular els punts.
              </p>
              {castellsCatalog.length > 0 ? (
                <div className="simulation-builder">
                  <div className="simulation-builder-section">
                    <h3 className="simulation-builder-title">Castells</h3>
                    {simulationCastells1.map((row, index) => (
                      <SimulationEntryRow
                        key={`simulation-left-castell-${index}`}
                        label="Castell"
                        index={index}
                        value={row}
                        options={castellOptions}
                        emptyPlaceholder="Selecciona un castell"
                        onChange={(nextValue) => updateSimulationCastell('left', 'castell', index, nextValue)}
                      />
                    ))}
                  </div>

                  <div className="simulation-builder-section">
                    <h3 className="simulation-builder-title">Pilars</h3>
                    {simulationPilars1.map((row, index) => (
                      <SimulationEntryRow
                        key={`simulation-left-pilar-${index}`}
                        label="Pilar"
                        index={index}
                        value={row}
                        options={pilarOptions}
                        emptyPlaceholder="Selecciona un pilar"
                        onChange={(nextValue) => updateSimulationCastell('left', 'pilar', index, nextValue)}
                      />
                    ))}
                  </div>
                </div>
              ) : (
                <div className="empty-placeholder simulation-empty-placeholder">
                  <p>No s'ha pogut carregar el catàleg de castells.</p>
                </div>
              )}
            </div>
          )}
        </div>

        {/* VS Divider */}
        <div className="vs-divider">
          <span style={{ color: safeThemeColor, borderColor: safeThemeColor }}>VS</span>
        </div>

        {/* Diada 2 */}
        <div className="diada-selector" style={{ '--colla-color': colla2Theme?.secondary || theme?.secondary }}>
          <div className="diada-selector-title-row">
            <h2>Diada 2</h2>
            <button
              type="button"
              className={`simulation-mode-button ${diada2Mode === 'simulated' ? 'active' : ''}`}
              onClick={() => handleModeToggle('right')}
            >
              {diada2Mode === 'simulated' ? 'Seleccionar diada' : 'Simular diada'}
            </button>
          </div>
          <div className="diada-selector-title-line" aria-hidden="true" />

          {diada2Mode === 'database' ? (
            <>
              <div className="joc-mocador-sidebar-option">
                <div className="comparison-field-header">
                  <label className="joc-mocador-option-label">Colla</label>
                  {!colla2 && canMirrorColla(colla1) && colla1 !== colla2 && (
                    <MirrorButton label="Mateixa colla" onClick={() => setColla2(colla1)} />
                  )}
                </div>
                <SingleSelect
                  options={colles.map(c => c.name)}
                  selected={colla2}
                  onChange={setColla2}
                  placeholder="Selecciona una colla"
                />
              </div>

              {colla2 && (
                <div className="joc-mocador-sidebar-option">
                  <div className="comparison-field-header">
                    <label className="joc-mocador-option-label">Any</label>
                    {!any2 && canMirrorAny(any1) && any1 !== any2 && (
                      <MirrorButton label="Mateix any" onClick={() => setAny2(any1)} />
                    )}
                  </div>
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
                  <div className="comparison-field-header">
                    <label className="joc-mocador-option-label">Diada</label>
                    {!diada2 && canMirrorDiada(diada1, diades2) && (
                      <MirrorButton label="Mateixa diada" onClick={() => setDiada2(diada1)} />
                    )}
                  </div>
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
            </>
          ) : (
            <div className="simulation-mode-panel">
              <p className="simulation-helper-text">
                Defineix fins a {castellsCount} castells i {pilarsCount} pilars amb el seu estat per calcular els punts.
              </p>
              {castellsCatalog.length > 0 ? (
                <div className="simulation-builder">
                  <div className="simulation-builder-section">
                    <h3 className="simulation-builder-title">Castells</h3>
                    {simulationCastells2.map((row, index) => (
                      <SimulationEntryRow
                        key={`simulation-right-castell-${index}`}
                        label="Castell"
                        index={index}
                        value={row}
                        options={castellOptions}
                        emptyPlaceholder="Selecciona un castell"
                        onChange={(nextValue) => updateSimulationCastell('right', 'castell', index, nextValue)}
                      />
                    ))}
                  </div>

                  <div className="simulation-builder-section">
                    <h3 className="simulation-builder-title">Pilars</h3>
                    {simulationPilars2.map((row, index) => (
                      <SimulationEntryRow
                        key={`simulation-right-pilar-${index}`}
                        label="Pilar"
                        index={index}
                        value={row}
                        options={pilarOptions}
                        emptyPlaceholder="Selecciona un pilar"
                        onChange={(nextValue) => updateSimulationCastell('right', 'pilar', index, nextValue)}
                      />
                    ))}
                  </div>
                </div>
              ) : (
                <div className="empty-placeholder simulation-empty-placeholder">
                  <p>No s'ha pogut carregar el catàleg de castells.</p>
                </div>
              )}
            </div>
          )}
        </div>
      </div>

      {/* Comparison Results */}
      {(displayDiada1Details || displayDiada2Details) && (
        <div className="comparison-results">
          <div className="comparison-side">
            {diada1Mode === 'database' && loadingDiada1 ? (
              <div className="loading-placeholder">
                <PilarLoader theme={colla1Theme || theme} />
              </div>
            ) : displayDiada1Details ? (
              <DiadaCard 
                diada={displayDiada1Details} 
                theme={colla1Theme || theme}
                isWinner={displayDiada1Details && displayDiada2Details && displayDiada1Details.total_punts > displayDiada2Details.total_punts}
              />
            ) : (
              <div className="empty-placeholder">
                <p>Selecciona una diada per comparar</p>
              </div>
            )}
          </div>

          <div className="comparison-side">
            {diada2Mode === 'database' && loadingDiada2 ? (
              <div className="loading-placeholder">
                <PilarLoader theme={colla2Theme || theme} />
              </div>
            ) : displayDiada2Details ? (
              <DiadaCard 
                diada={displayDiada2Details} 
                theme={colla2Theme || theme}
                isWinner={displayDiada1Details && displayDiada2Details && displayDiada2Details.total_punts > displayDiada1Details.total_punts}
              />
            ) : (
              <div className="empty-placeholder">
                <p>Selecciona una diada per comparar</p>
              </div>
            )}
          </div>
        </div>
      )}

      {showScoreTable && createPortal(
        <div className="score-table-modal-overlay" onClick={() => setShowScoreTable(false)}>
          <div className="score-table-modal" onClick={(e) => e.stopPropagation()}>
            <div className="score-table-modal-header">
              <h2>Taula de puntuacions</h2>
              <button type="button" className="score-table-close-button" onClick={() => setShowScoreTable(false)}>
                ×
              </button>
            </div>
            <div className="score-table-modal-body">
              <table className="score-table">
                <thead>
                  <tr>
                    <th>Castell / Pilar</th>
                    <th>Descarregat</th>
                    <th>Carregat</th>
                  </tr>
                </thead>
                <tbody>
                  {scoreTableRows.map((item) => (
                    <tr key={item.castell_name}>
                      <td>{item.castell_name}</td>
                      <td>{item.punts_descarregat ?? '-'}</td>
                      <td>{item.punts_carregat ?? '-'}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        </div>,
        document.body
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

