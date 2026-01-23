import './CastellLoader.css';

const CastellLoader = ({ isMobile = false }) => {
  if (isMobile) {
    // Versió mòbil: 3 pisos (més petit i ràpid)
    return (
      <div className="castell-loader castell-loader-mobile">
        {/* Enxaneta */}
        <div className="pom">
          <span className="enxaneta enxaneta-mobile"></span>
        </div>

        {/* Tronc - 3 pisos */}
        <div className="tronc-pis tronc-pis-3-mobile">
          <span className="person"></span>
          <span className="person"></span>
          <span className="person"></span>
        </div>
        <div className="tronc-pis tronc-pis-2-mobile">
          <span className="person"></span>
          <span className="person"></span>
          <span className="person"></span>
        </div>
        <div className="tronc-pis tronc-pis-1-mobile">
          <span className="person"></span>
          <span className="person"></span>
          <span className="person"></span>
        </div>

        {/* Pinya - 5 persones en mòbil */}
        <div className="pinya">
          <span className="person pinya-person-mobile"></span>
          <span className="person pinya-person-mobile"></span>
          <span className="person pinya-person-mobile"></span>
          <span className="person pinya-person-mobile"></span>
          <span className="person pinya-person-mobile"></span>
        </div>
      </div>
    );
  }

  // Versió desktop: 5 pisos
  return (
    <div className="castell-loader">
      {/* Enxaneta - apareix al final */}
      <div className="pom">
        <span className="enxaneta"></span>
      </div>

      {/* Tronc - 5 pisos de 3 persones, es construeixen de baix a dalt */}
      <div className="tronc-pis tronc-pis-5">
        <span className="person"></span>
        <span className="person"></span>
        <span className="person"></span>
      </div>
      <div className="tronc-pis tronc-pis-4">
        <span className="person"></span>
        <span className="person"></span>
        <span className="person"></span>
      </div>
      <div className="tronc-pis tronc-pis-3">
        <span className="person"></span>
        <span className="person"></span>
        <span className="person"></span>
      </div>
      <div className="tronc-pis tronc-pis-2">
        <span className="person"></span>
        <span className="person"></span>
        <span className="person"></span>
      </div>
      <div className="tronc-pis tronc-pis-1">
        <span className="person"></span>
        <span className="person"></span>
        <span className="person"></span>
      </div>

      {/* Pinya - la base, apareix primer */}
      <div className="pinya">
        <span className="person pinya-person"></span>
        <span className="person pinya-person"></span>
        <span className="person pinya-person"></span>
        <span className="person pinya-person"></span>
        <span className="person pinya-person"></span>
        <span className="person pinya-person"></span>
        <span className="person pinya-person"></span>
      </div>
    </div>
  );
};

export default CastellLoader;