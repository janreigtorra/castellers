import React, { useState, useEffect } from 'react';
import { apiService } from '../apiService';
import './CollesCastelleres.css';
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

// Convert colla name to URL-friendly slug
const createSlug = (name) => {
  if (!name) return '';
  return name
    .toLowerCase()
    .normalize('NFD')
    .replace(/[\u0300-\u036f]/g, '') // Remove diacritics
    .replace(/[^a-z0-9]+/g, '-') // Replace non-alphanumeric with hyphens
    .replace(/^-+|-+$/g, ''); // Remove leading/trailing hyphens
};

// Convert slug back to colla name (approximate - will need to match against actual names)
const slugToName = (slug, colles) => {
  const normalizedSlug = slug.toLowerCase();
  // Try exact match first
  for (const colla of colles) {
    if (createSlug(colla.name) === normalizedSlug) {
      return colla.name;
    }
  }
  // Try partial match
  for (const colla of colles) {
    if (createSlug(colla.name).includes(normalizedSlug) || normalizedSlug.includes(createSlug(colla.name))) {
      return colla.name;
    }
  }
  return null;
};

const CollesCastelleres = ({ theme, onBack, onCollaClick }) => {
  const [colles, setColles] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [searchTerm, setSearchTerm] = useState('');

  useEffect(() => {
    // Update page title and meta tags for SEO
    document.title = 'Colles Castelleres - Xiquet.cat';
    const metaDescription = document.querySelector('meta[name="description"]');
    if (metaDescription) {
      metaDescription.setAttribute('content', 'Descobreix totes les colles castelleres de Catalunya amb informació detallada sobre les seves millors diades i castells.');
    }

    const fetchColles = async () => {
      try {
        setLoading(true);
        const data = await apiService.getColles();
        const collesList = data.colles || [];
        
        // Sort colles: first those with logos (alphabetically), then those without (alphabetically)
        const sortedColles = [...collesList].sort((a, b) => {
          const aHasLogo = !!a.logo_url;
          const bHasLogo = !!b.logo_url;
          
          // If one has logo and the other doesn't, prioritize the one with logo
          if (aHasLogo && !bHasLogo) return -1;
          if (!aHasLogo && bHasLogo) return 1;
          
          // Both have the same logo status, sort alphabetically by name
          const nameA = (a.name || '').toLowerCase();
          const nameB = (b.name || '').toLowerCase();
          return nameA.localeCompare(nameB);
        });
        
        setColles(sortedColles);
        setError(null);
      } catch (err) {
        console.error('Error fetching colles:', err);
        setError('No s\'han pogut carregar les colles. Torna-ho a intentar.');
      } finally {
        setLoading(false);
      }
    };

    fetchColles();
  }, []);

  const handleBack = () => {
    window.history.pushState({}, '', '/');
    if (onBack) onBack();
    else window.dispatchEvent(new PopStateEvent('popstate'));
  };

  const handleCollaClick = (colla) => {
    const slug = createSlug(colla.name);
    if (onCollaClick) {
      // Pass both slug and ID for compatibility
      onCollaClick(slug, colla.colla_id || colla.id);
    } else {
      window.location.href = `/colles/${slug}`;
    }
  };

  const filteredColles = colles.filter(colla => {
    if (!searchTerm) return true;
    const searchLower = searchTerm.toLowerCase();
    return (
      colla.name?.toLowerCase().includes(searchLower) ||
      colla.wikipedia_title?.toLowerCase().includes(searchLower)
    );
  });

  if (loading) {
    return (
      <div className="colles-page" style={{ '--theme-color': theme?.secondary, '--theme-accent': theme?.accent }}>
        <div className="colles-page-content">
          <PilarLoader />
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="colles-page" style={{ '--theme-color': theme?.secondary, '--theme-accent': theme?.accent }}>
        <div className="colles-page-content">
          <button onClick={handleBack} className="colles-back-link">
            ← Tornar
          </button>
          <div className="colles-error">{error}</div>
        </div>
      </div>
    );
  }

  return (
    <div className="colles-page" style={{ '--theme-color': theme?.secondary, '--theme-accent': theme?.accent }}>
      <div className="colles-page-content">
        <button onClick={handleBack} className="colles-back-link">
          ← Tornar
        </button>

        <header className="colles-header">
          <h1>Colles Castelleres</h1>
        </header>

        <div className="colles-search">
          <input
            type="text"
            placeholder="Cerca una colla..."
            value={searchTerm}
            onChange={(e) => setSearchTerm(e.target.value)}
            className="colles-search-input"
          />
        </div>

        <div className="colles-grid">
          {filteredColles.length === 0 ? (
            <div className="colles-empty">
              {searchTerm ? 'No s\'ha trobat cap colla amb aquest nom.' : 'No hi ha colles disponibles.'}
            </div>
          ) : (
            filteredColles.map((colla) => {
              const collaTheme = getCollaTheme(colla.name);
              const cardTheme = collaTheme || theme;
              return (
              <div
                key={colla.id}
                className="colla-card"
                onClick={() => handleCollaClick(colla)}
                style={{ '--theme-color': cardTheme?.secondary, '--theme-accent': cardTheme?.accent }}
              >
                {colla.logo_url && (
                  <div className="colla-card-logo">
                    <img src={colla.logo_url} alt={`Logo ${colla.name}`} />
                  </div>
                )}
                <div className="colla-card-content">
                  <h2 className="colla-card-name">{colla.name}</h2>
                  <div className="colla-card-links">
                    {colla.website && (
                      <a
                        href={colla.website}
                        target="_blank"
                        rel="noopener noreferrer"
                        onClick={(e) => e.stopPropagation()}
                        className="colla-card-link"
                      >
                        Web
                      </a>
                    )}
                    {colla.instagram && (
                      <a
                        href={colla.instagram}
                        target="_blank"
                        rel="noopener noreferrer"
                        onClick={(e) => e.stopPropagation()}
                        className="colla-card-link"
                      >
                        Instagram
                      </a>
                    )}
                    {colla.facebook && (
                      <a
                        href={colla.facebook}
                        target="_blank"
                        rel="noopener noreferrer"
                        onClick={(e) => e.stopPropagation()}
                        className="colla-card-link"
                      >
                        Facebook
                      </a>
                    )}
                  </div>
                </div>
                <div className="colla-card-arrow">→</div>
              </div>
              );
            })
          )}
        </div>
      </div>
    </div>
  );
};

export default CollesCastelleres;

