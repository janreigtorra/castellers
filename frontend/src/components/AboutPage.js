import React from 'react';
import './AboutPage.css';

const AboutPage = ({ theme, onBack }) => {
  const handleBack = () => {
    window.history.pushState({}, '', '/');
    if (onBack) onBack();
    else window.dispatchEvent(new PopStateEvent('popstate'));
  };

  return (
    <div 
      className="about-page" 
      style={{ '--theme-color': theme?.secondary, '--theme-accent': theme?.accent }}
    >
      <div className="about-page-content">
        {/* Back link */}
        <button onClick={handleBack} className="about-back-link">
          ← Tornar al xat
        </button>

        {/* Project Section */}
        <section className="about-section">
          <h1>Sobre Xiquet AI</h1>
          
          <p>
            <strong>Xiquet AI</strong> neix amb la missió de facilitar l'accés a la informació del món casteller 
            a través de la intel·ligència artificial.
          </p>
          
          <p>
            Colles, diades, castells, actuacions, puntuacions... tota la riquesa del patrimoni casteller 
            al teu abast, d'una manera intuïtiva i conversacional.
          </p>

          <p>
            Xiquet s'alimenta d'informació provinent de la base de dades de la <strong>CCCC</strong> sobre 
            les diades i castells fets per les colles al llarg dels anys, així com d'informació d'altres fonts d'internet 
            per a informació conceptual.
          </p>

          <p>
            Aquest projecte s'ha fet sense ànim de lucre i sense cap finançament, i encara està en 
            desenvolupament. Per això, pot ser que ocasionalment s'equivoqui o no pugui respondre a 
            algun tipus de pregunta. Si tens alguna incidència o suggerència de millora, pots posar-te 
            en contacte amb nosaltres.
          </p>

          <p>
            <strong>Xiquet només parla català.</strong> No està disponible —ni ho estarà mai— en altres 
            llengües.
          </p>
        </section>

        <hr className="about-divider" />

        {/* Creator Section */}
        <section className="about-section">
          <h2>Sobre el Creador</h2>

          <div className="about-images">
            <img src="/jan/jan_1.jpg" alt="Jan Reig fent castells" />
            <img src="/jan/jan_2.jpg" alt="Jan Reig a una torre humana" />
          </div>

          <h3>Jan Reig</h3>
          <p>
            Nascut a Solsona, de petit va ser membre dels <strong>Castellers de Solsona</strong> i des 
            de sempre ha estat aficionat a la cultura popular catalana, especialment als gegants i als 
            castells. Va estudiar Estadística i Economia a la UPC i UB, i Data Science al MIT (Boston, EUA). Actualment viu i 
            treballa als Estats Units liderant projectes d'intel·ligència artificial.
          </p>
          
          <p>
            És un dels fundadors dels <strong>Castellers de Boston</strong> i actualment impulsa un 
            projecte per crear una colla castellera a San Francisco.
          </p>
        </section>

        <hr className="about-divider" />

        {/* Footer */}
        <footer className="about-footer">
          <p>Fet amb amor per la cultura popular</p>
        </footer>
      </div>
    </div>
  );
};

export default AboutPage;
