import React, { useState } from 'react';
import { apiService } from '../apiService';
import './ContactPage.css';

const ContactPage = ({ theme, onBack }) => {
  const [formData, setFormData] = useState({
    name: '',
    email: '',
    message: ''
  });
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [submitStatus, setSubmitStatus] = useState(null); // 'success', 'error', null

  const handleBack = () => {
    window.history.pushState({}, '', '/');
    if (onBack) onBack();
    else window.dispatchEvent(new PopStateEvent('popstate'));
  };

  const handleChange = (e) => {
    const { name, value } = e.target;
    setFormData(prev => ({
      ...prev,
      [name]: value
    }));
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    
    if (!formData.name.trim() || !formData.email.trim() || !formData.message.trim()) {
      return;
    }

    setIsSubmitting(true);
    setSubmitStatus(null);

    try {
      await apiService.sendContactMessage(formData);
      setSubmitStatus('success');
      setFormData({ name: '', email: '', message: '' });
    } catch (error) {
      console.error('Error sending message:', error);
      setSubmitStatus('error');
    } finally {
      setIsSubmitting(false);
    }
  };

  const isFormValid = formData.name.trim() && formData.email.trim() && formData.message.trim();

  return (
    <div 
      className="contact-page" 
      style={{ '--theme-color': theme?.secondary, '--theme-accent': theme?.accent }}
    >
      <div className="contact-page-content">
        {/* Back link */}
        <button onClick={handleBack} className="contact-back-link">
          ← Tornar al xat
        </button>

        {/* Header */}
        <section className="contact-section">
          <h1>Contacta amb nosaltres</h1>
          
          <p>
            Tens alguna pregunta, suggeriment o has trobat algun error? 
            Omple el formulari i et respondrem tan aviat com puguem.
          </p>
        </section>

        {/* Contact Form */}
        <form className="contact-form" onSubmit={handleSubmit}>
          <div className="contact-field">
            <label htmlFor="name">Nom</label>
            <input
              type="text"
              id="name"
              name="name"
              value={formData.name}
              onChange={handleChange}
              placeholder="El teu nom"
              disabled={isSubmitting}
              required
            />
          </div>

          <div className="contact-field">
            <label htmlFor="email">Correu electrònic</label>
            <input
              type="email"
              id="email"
              name="email"
              value={formData.email}
              onChange={handleChange}
              placeholder="el.teu.correu@exemple.com"
              disabled={isSubmitting}
              required
            />
          </div>

          <div className="contact-field">
            <label htmlFor="message">Missatge</label>
            <textarea
              id="message"
              name="message"
              value={formData.message}
              onChange={handleChange}
              placeholder="Escriu aquí el teu missatge..."
              rows={6}
              disabled={isSubmitting}
              required
            />
          </div>

          {submitStatus === 'success' && (
            <div className="contact-status contact-status-success">
              <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                <path d="M22 11.08V12a10 10 0 1 1-5.93-9.14" />
                <polyline points="22 4 12 14.01 9 11.01" />
              </svg>
              <span>Missatge enviat correctament! Et respondrem aviat.</span>
            </div>
          )}

          {submitStatus === 'error' && (
            <div className="contact-status contact-status-error">
              <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                <circle cx="12" cy="12" r="10" />
                <line x1="15" y1="9" x2="9" y2="15" />
                <line x1="9" y1="9" x2="15" y2="15" />
              </svg>
              <span>Hi ha hagut un error. Si us plau, torna-ho a intentar.</span>
            </div>
          )}

          <button 
            type="submit" 
            className="contact-submit-btn"
            disabled={isSubmitting || !isFormValid}
          >
            {isSubmitting ? (
              <>
                <span className="contact-spinner"></span>
                Enviant...
              </>
            ) : (
              <>
                <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                  <line x1="22" y1="2" x2="11" y2="13" />
                  <polygon points="22 2 15 22 11 13 2 9 22 2" />
                </svg>
                Enviar missatge
              </>
            )}
          </button>
        </form>

        <hr className="contact-divider" />

        {/* Alternative Contact */}
        <section className="contact-section contact-alternative">
          <h2>Altres maneres de contactar</h2>
          <p>
            També pots escriure'ns directament a:{' '}
            <a href="mailto:xiquet.cat.ai@gmail.com" className="contact-email-link">
              xiquet.cat.ai@gmail.com
            </a>
          </p>
        </section>

        {/* Footer */}
        <footer className="contact-footer">
          <p>Gràcies per ajudar-nos a millorar Xiquet AI!</p>
        </footer>
      </div>
    </div>
  );
};

export default ContactPage;

