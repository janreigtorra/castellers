import React, { useState, useEffect, useRef } from 'react';
import { apiService } from '../apiService';
import './CollaDetail.css';
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

// Create slug function (same as in CollesCastelleres)
const createSlug = (name) => {
  if (!name) return '';
  return name
    .toLowerCase()
    .normalize('NFD')
    .replace(/[\u0300-\u036f]/g, '')
    .replace(/[^a-z0-9]+/g, '-')
    .replace(/^-+|-+$/g, '');
};

// Convert slug back to colla identifier
const slugToIdentifier = async (slug) => {
  try {
    // First try to fetch all colles and find matching one
    const data = await apiService.getColles();
    const colles = data.colles || [];
    
    // Find colla by slug
    for (const colla of colles) {
      if (createSlug(colla.name) === slug.toLowerCase()) {
        return colla.colla_id || colla.id || colla.name;
      }
    }
    
    // If not found, return slug as-is (might be an ID or old format)
    return slug;
  } catch (err) {
    console.error('Error fetching colles for slug lookup:', err);
    return slug; // Fallback to slug
  }
};

// Multi-select dropdown component with search (same as Menu.js)
const MultiSelect = ({ options, selected, onChange, placeholder, disabled, displayTransform }) => {
  const [isOpen, setIsOpen] = useState(false);
  const [searchTerm, setSearchTerm] = useState('');
  const dropdownRef = useRef(null);
  const searchInputRef = useRef(null);

  // Lock scroll when dropdown is open
  useEffect(() => {
    if (isOpen) {
      document.body.style.overflow = 'hidden';
      setTimeout(() => searchInputRef.current?.focus(), 0);
    } else {
      document.body.style.overflow = '';
      setSearchTerm('');
    }
    return () => {
      document.body.style.overflow = '';
    };
  }, [isOpen]);

  // Close dropdown when clicking outside
  useEffect(() => {
    const handleClickOutside = (event) => {
      if (dropdownRef.current && !dropdownRef.current.contains(event.target)) {
        setIsOpen(false);
        setSearchTerm('');
      }
    };

    if (isOpen) {
      document.addEventListener('mousedown', handleClickOutside);
      return () => document.removeEventListener('mousedown', handleClickOutside);
    }
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
    if (selected.length === options.length) return `Tots els anys (${options.length})`;
    if (selected.length <= 2) {
      return selected.map(s => displayTransform ? displayTransform(s) : s).join(', ');
    }
    return `${selected.length} anys seleccionats`;
  };

  return (
    <div className="joc-mocador-multiselect" ref={dropdownRef}>
      {isOpen && <div className="joc-mocador-multiselect-overlay" onClick={closeDropdown} />}
      <button 
        type="button"
        className={`joc-mocador-multiselect-trigger ${isOpen ? 'open' : ''}`}
        onClick={() => !disabled && setIsOpen(!isOpen)}
        disabled={disabled}
      >
        <span className="joc-mocador-multiselect-text">{getDisplayText()}</span>
        <span className="joc-mocador-multiselect-arrow">{isOpen ? '▲' : '▼'}</span>
      </button>
      {isOpen && (
        <div className="joc-mocador-multiselect-dropdown">
          <div className="joc-mocador-multiselect-search">
            <input
              ref={searchInputRef}
              type="text"
              placeholder="Cerca any..."
              value={searchTerm}
              onChange={(e) => setSearchTerm(e.target.value)}
              className="joc-mocador-multiselect-search-input"
              onClick={(e) => e.stopPropagation()}
            />
          </div>
          <div className="joc-mocador-multiselect-actions">
            <button type="button" onClick={selectAll} className="joc-mocador-multiselect-action">
              {searchTerm ? `Seleccionar (${filteredOptions.length})` : 'Seleccionar tot'}
            </button>
            <button type="button" onClick={clearAll} className="joc-mocador-multiselect-action">
              Netejar
            </button>
          </div>
          <div className="joc-mocador-multiselect-options">
            {filteredOptions.length > 0 ? (
              filteredOptions.map((option) => (
                <label key={option} className="joc-mocador-multiselect-option">
                  <input
                    type="checkbox"
                    checked={selected.includes(option)}
                    onChange={() => toggleOption(option)}
                  />
                  <span>{displayTransform ? displayTransform(option) : option}</span>
                </label>
              ))
            ) : (
              <div className="joc-mocador-multiselect-empty">
                No s'han trobat resultats
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
};

const CollaDetail = ({ collaId, theme, onBack }) => {
  const [colla, setColla] = useState(null);
  const [millorDiada, setMillorDiada] = useState([]);
  const [millorsCastells, setMillorsCastells] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [loadingDiada, setLoadingDiada] = useState(true);
  const [loadingCastells, setLoadingCastells] = useState(true);
  const [collaTheme, setCollaTheme] = useState(null);
  const [selectedYears, setSelectedYears] = useState([]);
  const [availableYears, setAvailableYears] = useState([]);

  useEffect(() => {
    const fetchData = async () => {
      try {
        setLoading(true);
        setError(null);

        // Convert slug to identifier (ID or name)
        const identifier = await slugToIdentifier(collaId);

        // Fetch colla details
        const collaData = await apiService.getCollaDetail(identifier);
        setColla(collaData);

        // Get colla's theme color
        const theme = getCollaTheme(collaData.name);
        setCollaTheme(theme);

        // Update SEO meta tags
        if (collaData.name) {
          document.title = `${collaData.name} - Colles Castelleres - Xiquet CAT`;
          const metaDescription = document.querySelector('meta[name="description"]');
          if (metaDescription) {
            const description = collaData.wikipedia_description 
              ? `${collaData.wikipedia_description.substring(0, 155)}...`
              : `Informació sobre ${collaData.name}, una colla castellera de Catalunya. Descobreix les seves millors diades i castells.`;
            metaDescription.setAttribute('content', description);
          }
        }

        // Fetch available years
        try {
          const entityOptions = await apiService.getEntityOptions();
          const years = entityOptions.anys || [];
          // Sort years descending
          setAvailableYears(years.sort((a, b) => parseInt(b) - parseInt(a)));
        } catch (err) {
          console.error('Error fetching years:', err);
        }

        setLoading(false);
      } catch (err) {
        console.error('Error fetching colla data:', err);
        setError('No s\'ha pogut carregar la informació de la colla. Torna-ho a intentar.');
        setLoading(false);
      }
    };

    if (collaId) {
      fetchData();
    }
  }, [collaId]);

  // Fetch table data when selectedYears changes
  useEffect(() => {
    const fetchTableData = async () => {
      if (!colla) return;
      
      try {
        setLoadingDiada(true);
        setLoadingCastells(true);
        
        // Convert slug to identifier
        const identifier = await slugToIdentifier(collaId);
        
        // Convert selectedYears array to single year or null for API (use first selected year)
        const yearParam = selectedYears.length > 0 ? parseInt(selectedYears[0]) : null;
        
        const [diadaData, castellsData] = await Promise.all([
          apiService.getCollaMillorDiada(identifier, 10, yearParam),
          apiService.getCollaMillorsCastells(identifier, 20, yearParam)
        ]);
        
        setMillorDiada(diadaData.results || []);
        setMillorsCastells(castellsData.results || []);
      } catch (err) {
        console.error('Error fetching table data:', err);
      } finally {
        setLoadingDiada(false);
        setLoadingCastells(false);
      }
    };
    
    if (colla) {
      fetchTableData();
    }
  }, [colla, selectedYears, collaId]);

  const handleBack = () => {
    window.history.pushState({}, '', '/colles-castelleres');
    if (onBack) onBack();
    else window.dispatchEvent(new PopStateEvent('popstate'));
  };

  // Use colla's theme if available, otherwise fall back to user's theme
  const pageTheme = collaTheme || theme;

  if (loading) {
    return (
      <div className="colla-detail-page" style={{ '--theme-color': pageTheme?.secondary, '--theme-accent': pageTheme?.accent }}>
        <div className="colla-detail-content">
          <PilarLoader />
        </div>
      </div>
    );
  }

  if (error || !colla) {
    return (
      <div className="colla-detail-page" style={{ '--theme-color': pageTheme?.secondary, '--theme-accent': pageTheme?.accent }}>
        <div className="colla-detail-content">
          <button onClick={handleBack} className="colla-detail-back-link">
            ← Tornar a Colles Castelleres
          </button>
          <div className="colla-detail-error">
            {error || 'Colla no trobada'}
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="colla-detail-page" style={{ '--theme-color': pageTheme?.secondary, '--theme-accent': pageTheme?.accent }}>
      <div className="colla-detail-content">
        <button onClick={handleBack} className="colla-detail-back-link">
          ← Tornar a Colles Castelleres
        </button>

        <header className="colla-detail-header">
          <div className="colla-detail-header-top">
            {colla.logo_url && (
              <div className="colla-detail-logo">
                <img src={colla.logo_url} alt={`Logo ${colla.name}`} />
              </div>
            )}
            <div className="colla-detail-header-info">
              <h1>{colla.name}</h1>
              {colla.wikipedia_title && colla.wikipedia_title !== colla.name && (
                <p className="colla-detail-subtitle">{colla.wikipedia_title}</p>
              )}
              <div className="colla-detail-links">
                {colla.website && (
                  <a
                    href={colla.website}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="colla-detail-link"
                    title="Web"
                  >
                    <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                      <circle cx="12" cy="12" r="10" />
                      <line x1="2" y1="12" x2="22" y2="12" />
                      <path d="M12 2a15.3 15.3 0 0 1 4 10 15.3 15.3 0 0 1-4 10 15.3 15.3 0 0 1-4-10 15.3 15.3 0 0 1 4-10z" />
                    </svg>
                    <span>Web</span>
                  </a>
                )}
                {colla.instagram && (
                  <a
                    href={colla.instagram}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="colla-detail-link"
                    title="Instagram"
                  >
                    <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                      <rect x="2" y="2" width="20" height="20" rx="5" ry="5" />
                      <path d="M16 11.37A4 4 0 1 1 12.63 8 4 4 0 0 1 16 11.37z" />
                      <line x1="17.5" y1="6.5" x2="17.51" y2="6.5" />
                    </svg>
                    <span>Instagram</span>
                  </a>
                )}
                {colla.facebook && (
                  <a
                    href={colla.facebook}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="colla-detail-link"
                    title="Facebook"
                  >
                    <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                      <path d="M18 2h-3a5 5 0 0 0-5 5v3H7v4h3v8h4v-8h3l1-4h-4V7a1 1 0 0 1 1-1h3z" />
                    </svg>
                    <span>Facebook</span>
                  </a>
                )}
                {colla.wikipedia_url && (
                  <a
                    href={colla.wikipedia_url}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="colla-detail-link"
                    title="Wikipedia"
                  >
                    <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                      <path d="M12 2C6.48 2 2 6.48 2 12s4.48 10 10 10 10-4.48 10-10S17.52 2 12 2zm-1 16h2v-2h-2v2zm0-4h2V7h-2v7z" />
                    </svg>
                    <span>Wikipedia</span>
                  </a>
                )}
              </div>
            </div>
          </div>
        </header>

        {/* Year filter - shared across both tables */}
        <div className="colla-detail-year-filter-container">
          <label className="colla-detail-year-filter-label">Filtrar per any:</label>
          <MultiSelect
            options={availableYears}
            selected={selectedYears}
            onChange={setSelectedYears}
            placeholder="Tots els anys"
            disabled={loading || loadingDiada || loadingCastells}
            displayTransform={(year) => year.toString()}
          />
        </div>

        <section className="colla-detail-section">
          <h2>Millors Diades</h2>
          {loadingDiada ? (
            <div className="colla-detail-loading">
              <PilarLoader />
            </div>
          ) : millorDiada.length === 0 ? (
            <p className="colla-detail-empty">No hi ha dades disponibles.</p>
          ) : (
            <div className="colla-detail-table-container">
              <table className="colla-detail-table">
                <thead>
                  <tr>
                    <th>Ranking</th>
                    <th>Diada</th>
                    <th>Data</th>
                    <th>Lloc</th>
                    <th>Castells Fets</th>
                  </tr>
                </thead>
                <tbody>
                  {millorDiada.map((diada, index) => (
                    <tr key={index}>
                      <td>{diada.ranking || index + 1}</td>
                      <td><strong>{diada.event_name}</strong></td>
                      <td>{diada.event_date}</td>
                      <td>{diada.event_city || '-'}</td>
                      <td>{diada.castells_fets || '-'}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </section>

        <section className="colla-detail-section">
          <h2>Millors Castells</h2>
          {loadingCastells ? (
            <div className="colla-detail-loading">
              <PilarLoader />
            </div>
          ) : millorsCastells.length === 0 ? (
            <p className="colla-detail-empty">No hi ha dades disponibles.</p>
          ) : (
            <div className="colla-detail-table-container">
              <table className="colla-detail-table">
                <thead>
                  <tr>
                    <th>Castell</th>
                    <th>Estat</th>
                    <th>Diada</th>
                    <th>Data</th>
                    <th>Lloc</th>
                  </tr>
                </thead>
                <tbody>
                  {millorsCastells.map((castell, index) => (
                    <tr key={index}>
                      <td><strong>{castell.castell_name}</strong></td>
                      <td>{castell.status}</td>
                      <td>{castell.event_name}</td>
                      <td>{castell.date}</td>
                      <td>{castell.city || '-'}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </section>
      </div>
    </div>
  );
};

export default CollaDetail;

