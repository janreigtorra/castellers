import React, { useState, useEffect } from 'react';
import { authHelpers } from '../supabaseClient';
import { COLOR_THEMES } from '../colorTheme';
import collesData from '../data/colles_fundacio.json';

// Filter active colles (without year ranges in name)
const getActiveColles = () => {
  return collesData
    .filter(colla => !colla.name.includes('(') && colla.color_code)
    .sort((a, b) => a.name.localeCompare(b.name));
};

// Map color_code to theme color
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

const getCollaColor = (colorCode) => {
  const themeKey = COLOR_CODE_TO_THEME[colorCode] || 'white';
  return COLOR_THEMES[themeKey]?.color || '#ffffff';
};

const ProfileModal = ({ user, onClose, onProfileUpdate, theme, onCollaChange }) => {
  const [isEditing, setIsEditing] = useState(false);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState('');
  const [success, setSuccess] = useState('');
  
  const [formData, setFormData] = useState({
    username: user?.username || '',
    colla: user?.colla || '',
    collaColorCode: user?.collaColorCode || '',
    phone: user?.phone || '',
    birthDate: user?.birthDate || ''
  });

  const colles = getActiveColles();

  useEffect(() => {
    // Load user profile data from localStorage or user metadata
    const savedProfile = localStorage.getItem(`user_profile_${user?.id}`);
    if (savedProfile) {
      const parsed = JSON.parse(savedProfile);
      setFormData(prev => ({
        ...prev,
        ...parsed,
        username: user?.username || parsed.username || ''
      }));
    }
  }, [user]);

  const handleChange = (e) => {
    const { name, value } = e.target;
    
    if (name === 'colla') {
      const selectedColla = colles.find(c => c.name === value);
      setFormData(prev => ({
        ...prev,
        colla: value,
        collaColorCode: selectedColla?.color_code || ''
      }));
    } else {
      setFormData(prev => ({
        ...prev,
        [name]: value
      }));
    }
  };

  const handleSave = async () => {
    setIsLoading(true);
    setError('');
    setSuccess('');

    try {
      // Update user metadata in Supabase
      const result = await authHelpers.updateUserProfile({
        username: formData.username,
        colla: formData.colla,
        collaColorCode: formData.collaColorCode,
        phone: formData.phone,
        birthDate: formData.birthDate
      });

      if (result.error) {
        setError(result.error.message || 'Error al guardar el perfil');
      } else {
        // Also save to localStorage for quick access
        localStorage.setItem(`user_profile_${user?.id}`, JSON.stringify(formData));
        
        setSuccess('Perfil actualitzat correctament!');
        setIsEditing(false);
        
        // Notify parent of profile update
        if (onProfileUpdate) {
          onProfileUpdate({
            ...user,
            username: formData.username,
            colla: formData.colla,
            collaColorCode: formData.collaColorCode,
            phone: formData.phone,
            birthDate: formData.birthDate
          });
        }

        // If colla changed, update the app color
        if (formData.collaColorCode && onCollaChange) {
          const themeKey = COLOR_CODE_TO_THEME[formData.collaColorCode];
          if (themeKey) {
            onCollaChange(themeKey);
          }
        }

        setTimeout(() => setSuccess(''), 3000);
      }
    } catch (err) {
      setError('Error al guardar el perfil');
      console.error('Profile save error:', err);
    } finally {
      setIsLoading(false);
    }
  };

  const handleCancel = () => {
    // Reset form to original values
    const savedProfile = localStorage.getItem(`user_profile_${user?.id}`);
    if (savedProfile) {
      const parsed = JSON.parse(savedProfile);
      setFormData(prev => ({
        ...prev,
        ...parsed,
        username: user?.username || parsed.username || ''
      }));
    } else {
      setFormData({
        username: user?.username || '',
        colla: '',
        collaColorCode: '',
        phone: '',
        birthDate: ''
      });
    }
    setIsEditing(false);
    setError('');
  };

  const getInitials = (name) => {
    if (!name) return '?';
    const parts = name.trim().split(/\s+/);
    if (parts.length >= 2) {
      return (parts[0][0] + parts[parts.length - 1][0]).toUpperCase();
    }
    return name.substring(0, 2).toUpperCase();
  };

  const selectedCollaColor = formData.collaColorCode 
    ? getCollaColor(formData.collaColorCode)
    : null;

  const isWhiteTheme = theme?.secondary === '#ffffff';

  return (
    <div className="profile-modal-overlay" onClick={onClose}>
      <div className="profile-modal" onClick={e => e.stopPropagation()}>
        <button className="profile-modal-close" onClick={onClose}>
          <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
            <path d="M18 6L6 18M6 6l12 12" />
          </svg>
        </button>

        <div className="profile-modal-header">
          <div 
            className="profile-avatar-large"
            style={{ 
              backgroundColor: theme?.secondary || '#d0282c',
              color: isWhiteTheme ? '#000000' : '#ffffff'
            }}
          >
            {getInitials(formData.username || user?.username)}
          </div>
          {isEditing && <h2>Editar Perfil</h2>}
        </div>

        {error && <div className="profile-error">{error}</div>}
        {success && <div className="profile-success">{success}</div>}

        <div className="profile-modal-content">
          <div className="profile-field">
            <label>Nom</label>
            {isEditing ? (
              <input
                type="text"
                name="username"
                value={formData.username}
                onChange={handleChange}
                placeholder="El teu nom"
              />
            ) : (
              <p>{formData.username || user?.username || '-'}</p>
            )}
          </div>

          <div className="profile-field">
            <label>Email</label>
            <p className="profile-email">{user?.email || '-'}</p>
          </div>

          <div className="profile-field">
            <label>Colla Castellera</label>
            {isEditing ? (
              <select
                name="colla"
                value={formData.colla}
                onChange={handleChange}
              >
                <option value="">Selecciona una colla...</option>
                {colles.map(colla => (
                  <option key={colla.name} value={colla.name}>
                    {colla.name}
                  </option>
                ))}
              </select>
            ) : (
              <div className="profile-colla-display">
                {formData.colla ? (
                  <span 
                    className="colla-chip"
                    style={{ 
                      backgroundColor: selectedCollaColor || '#e0e0e0',
                      color: selectedCollaColor === '#ffffff' || selectedCollaColor === '#e8c62b' || selectedCollaColor === '#C1B6D7' || selectedCollaColor === '#93BB7B' ? '#000' : '#fff'
                    }}
                  >
                    {formData.colla}
                  </span>
                ) : (
                  <p className="profile-empty">No especificada</p>
                )}
              </div>
            )}
          </div>

          <div className="profile-field">
            <label>Telèfon</label>
            {isEditing ? (
              <input
                type="tel"
                name="phone"
                value={formData.phone}
                onChange={handleChange}
                placeholder="+34 600 000 000"
              />
            ) : (
              <p>{formData.phone || <span className="profile-empty">No especificat</span>}</p>
            )}
          </div>

          <div className="profile-field">
            <label>Data de Naixement</label>
            {isEditing ? (
              <input
                type="date"
                name="birthDate"
                value={formData.birthDate}
                onChange={handleChange}
              />
            ) : (
              <p>
                {formData.birthDate 
                  ? new Date(formData.birthDate).toLocaleDateString('ca-ES', {
                      day: 'numeric',
                      month: 'long',
                      year: 'numeric'
                    })
                  : <span className="profile-empty">No especificada</span>
                }
              </p>
            )}
          </div>
        </div>

        <div className="profile-modal-actions">
          {isEditing ? (
            <>
              <button 
                className="profile-btn profile-btn-secondary"
                onClick={handleCancel}
                disabled={isLoading}
              >
                Cancel·lar
              </button>
              <button 
                className="profile-btn profile-btn-primary"
                onClick={handleSave}
                disabled={isLoading}
                style={{ 
                  backgroundColor: theme?.secondary || '#d0282c',
                  color: isWhiteTheme ? '#000000' : '#ffffff'
                }}
              >
                {isLoading ? <span className="spinner"></span> : 'Guardar'}
              </button>
            </>
          ) : (
            <button 
              className="profile-btn profile-btn-primary"
              onClick={() => setIsEditing(true)}
              style={{ 
                backgroundColor: theme?.secondary || '#d0282c',
                color: isWhiteTheme ? '#000000' : '#ffffff'
              }}
            >
              <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke={isWhiteTheme ? '#000000' : 'currentColor'} strokeWidth="2">
                <path d="M11 4H4a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-7" />
                <path d="M18.5 2.5a2.121 2.121 0 0 1 3 3L12 15l-4 1 1-4 9.5-9.5z" />
              </svg>
              Editar Perfil
            </button>
          )}
        </div>
      </div>
    </div>
  );
};

export default ProfileModal;

