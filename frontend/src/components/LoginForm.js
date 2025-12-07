import React, { useState } from 'react';
import { authHelpers } from '../supabaseClient';

const LoginForm = ({ onLogin, onClose }) => {
  const [isLogin, setIsLogin] = useState(true);
  const [formData, setFormData] = useState({
    email: '',
    password: '',
    username: ''
  });
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState('');

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

    try {
      let result;
      
      if (isLogin) {
        result = await authHelpers.signIn(formData.email, formData.password);
      } else {
        result = await authHelpers.signUp(formData.email, formData.password, formData.username);
      }
      
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
      
      <form onSubmit={handleSubmit}>
        {!isLogin && (
          <div className="form-group">
            <label htmlFor="username">Nom d\'usuari:</label>
            <input
              type="text"
              id="username"
              name="username"
              value={formData.username}
              onChange={handleChange}
              required={!isLogin}
            />
          </div>
        )}
        
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
        
        <button type="submit" disabled={isLoading}>
          {isLoading ? <span className="spinner"></span> : (isLogin ? 'Entrar' : 'Registrar-se')}
        </button>
      </form>
      
      <div style={{ textAlign: 'center', marginTop: '1rem' }}>
        <button 
          type="button" 
          onClick={() => setIsLogin(!isLogin)}
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
