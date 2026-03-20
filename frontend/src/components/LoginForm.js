import React, { useState, useRef, useEffect } from 'react';
import { authHelpers } from '../supabaseClient';
import collesData from '../data/colles_fundacio.json';
import './JocDelMocador/JocDelMocador.css';

// Same active colles list as ProfileModal (no year ranges, with color_code)
const getActiveColles = () => {
  return collesData
    .filter(colla => !colla.name.includes('(') && colla.color_code)
    .sort((a, b) => a.name.localeCompare(b.name));
};

// Single-select dropdown with search (same look as Menu.js MultiSelect, stays inside modal)
const SingleSelect = ({ options, selected, onChange, placeholder, disabled }) => {
  const [isOpen, setIsOpen] = useState(false);
  const [searchTerm, setSearchTerm] = useState('');
  const dropdownRef = useRef(null);
  const searchInputRef = useRef(null);

  useEffect(() => {
    if (isOpen) {
      document.body.style.overflow = 'hidden';
      setTimeout(() => searchInputRef.current?.focus(), 0);
    } else {
      document.body.style.overflow = '';
      setSearchTerm('');
    }
    return () => { document.body.style.overflow = ''; };
  }, [isOpen]);

  const closeDropdown = () => {
    setIsOpen(false);
    setSearchTerm('');
  };

  const selectOption = (option) => {
    onChange(option);
    closeDropdown();
  };

  const filteredOptions = options.filter(opt =>
    opt.toLowerCase().includes(searchTerm.toLowerCase())
  );

  const getDisplayText = () => {
    return selected || placeholder;
  };

  useEffect(() => {
    const handleClickOutside = (e) => {
      if (dropdownRef.current && !dropdownRef.current.contains(e.target)) closeDropdown();
    };
    if (isOpen) {
      document.addEventListener('mousedown', handleClickOutside);
      return () => document.removeEventListener('mousedown', handleClickOutside);
    }
  }, [isOpen]);

  return (
    <div className="joc-mocador-multiselect login-form-collaselect" ref={dropdownRef}>
      {isOpen && <div className="joc-mocador-multiselect-overlay" onClick={closeDropdown} />}
      <button
        type="button"
        className={`joc-mocador-multiselect-trigger ${isOpen ? 'open' : ''} ${!selected ? 'is-placeholder' : ''}`}
        onClick={() => !disabled && setIsOpen(!isOpen)}
        disabled={disabled}
      >
        <span className="joc-mocador-multiselect-text">{getDisplayText()}</span>
        <span className="joc-mocador-multiselect-arrow" aria-hidden>{isOpen ? '▲' : '▼'}</span>
      </button>
      {isOpen && (
        <div className="joc-mocador-multiselect-dropdown">
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
          {selected && (
            <div className="joc-mocador-multiselect-actions">
              <button
                type="button"
                className="joc-mocador-multiselect-action"
                onClick={() => selectOption('')}
              >
                Netejar
              </button>
            </div>
          )}
          <div className="joc-mocador-multiselect-options">
            {filteredOptions.length > 0 ? (
              filteredOptions.map((option) => (
                <label
                  key={option}
                  className={`joc-mocador-multiselect-option ${selected === option ? 'selected' : ''}`}
                  onClick={() => selectOption(option)}
                >
                  <input type="radio" checked={selected === option} readOnly />
                  <span>{option}</span>
                </label>
              ))
            ) : (
              <div className="joc-mocador-multiselect-empty">No s'han trobat resultats</div>
            )}
          </div>
        </div>
      )}
    </div>
  );
};

const LoginForm = ({ onLogin, onClose }) => {
  const colles = getActiveColles();
  const collaOptions = colles.map(c => c.name);
  const [isLogin, setIsLogin] = useState(true);
  const [formData, setFormData] = useState({
    email: '',
    password: '',
    username: '',
    colla_castellers: ''
  });
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState('');
  const [successMessage, setSuccessMessage] = useState('');

  const handleChange = (e) => {
    setFormData({
      ...formData,
      [e.target.name]: e.target.value
    });
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    setIsLoading(true);
    setError('');
    setSuccessMessage('');

    try {
      let result;
      
      if (isLogin) {
        result = await authHelpers.signIn(formData.email, formData.password);
        
        if (result.error) {
          setError(result.error.message);
        } else if (result.data?.user) {
          const userData = {
            id: result.data.user.id,
            email: result.data.user.email,
            username: result.data.user.user_metadata?.username || formData.username
          };
          onLogin(userData);
        }
      } else {
        // Registration
        result = await authHelpers.signUp(formData.email, formData.password, formData.username, formData.colla_castellers?.trim() || null);
        
        if (result.error) {
          setError(result.error.message);
        } else if (result.data?.user) {
          // Show success message for email verification
          setSuccessMessage(`Compte creat! Revisa el teu correu electrònic (${formData.email}) per confirmar el teu compte. Si no veus el correu, revisa la bústia de correu brossa.`);
          
          // Clear form
          setFormData({
            email: '',
            password: '',
            username: '',
            colla_castellers: ''
          });
          
          // Don't log them in yet - they need to verify email first
          // Switch to login mode after a delay
          setTimeout(() => {
            setIsLogin(true);
            setSuccessMessage('');
          }, 5000);
        }
      }
    } catch (error) {
      setError('Error en l\'autenticació');
      console.error('Auth error:', error);
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div className="login-form">
      <h2>{isLogin ? 'Entrar' : 'Registrar-se'}</h2>
      
      {error && <div className="error">{error}</div>}
      {successMessage && <div className="success-message">{successMessage}</div>}
      
      <form onSubmit={handleSubmit}>
        {!isLogin ? (
          <>
            <div className="form-group">
              <label htmlFor="username">Nom d\'usuari:</label>
              <input
                type="text"
                id="username"
                name="username"
                value={formData.username}
                onChange={handleChange}
                required
              />
            </div>
            <div className="form-group">
              <label htmlFor="colla_castellers">Colla castellers (opcional):</label>
              <SingleSelect
                options={collaOptions}
                selected={formData.colla_castellers || ''}
                onChange={(value) => setFormData(prev => ({ ...prev, colla_castellers: value || '' }))}
                placeholder="Selecciona una colla..."
              />
            </div>
            <div className="form-group">
              <label htmlFor="email">Email:</label>
              <input
                type="email"
                id="email"
                name="email"
                value={formData.email}
                onChange={handleChange}
                required
              />
            </div>
            <div className="form-group">
              <label htmlFor="password">Contrasenya:</label>
              <input
                type="password"
                id="password"
                name="password"
                value={formData.password}
                onChange={handleChange}
                required
              />
            </div>
          </>
        ) : (
          <>
            <div className="form-group">
              <label htmlFor="email">Email:</label>
              <input
                type="email"
                id="email"
                name="email"
                value={formData.email}
                onChange={handleChange}
                required
              />
            </div>
            <div className="form-group">
              <label htmlFor="password">Contrasenya:</label>
              <input
                type="password"
                id="password"
                name="password"
                value={formData.password}
                onChange={handleChange}
                required
              />
            </div>
          </>
        )}
        
        <button type="submit" disabled={isLoading}>
          {isLoading ? <span className="spinner"></span> : (isLogin ? 'Entrar' : 'Registrar-se')}
        </button>
      </form>
      
      <div style={{ textAlign: 'center', marginTop: '1.5rem' }}>
        <button
          type="button"
          onClick={() => {
            setIsLogin(!isLogin);
            setSuccessMessage('');
            setError('');
          }}
          style={{ background: 'none', border: 'none', color: '#3498db', cursor: 'pointer' }}
        >
          {isLogin ? 'No tens compte? Registra\'t' : 'Ja tens compte? Entra'}
        </button>
      </div>
      <div style={{ textAlign: 'center', marginTop: '1rem' }}>
        <button
          type="button"
          onClick={onClose}
          style={{ background: 'none', border: 'none', color: '#666', cursor: 'pointer' }}
        >
          Tancar
        </button>
      </div>
    </div>
  );
};

export default LoginForm;
