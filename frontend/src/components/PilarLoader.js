import './PilarLoader.css';

const PilarLoader = () => {
  return (
    <div className="pilar-loader">
      {/* Enxaneta - a dalt de tot */}
      <div className="pilar-pom">
        <span className="pilar-enxaneta"></span>
      </div>

      {/* Tronc - 4 pisos de 1 persona */}
      <div className="pilar-tronc pilar-tronc-4">
        <span className="pilar-person"></span>
      </div>
      <div className="pilar-tronc pilar-tronc-3">
        <span className="pilar-person"></span>
      </div>
      <div className="pilar-tronc pilar-tronc-2">
        <span className="pilar-person"></span>
      </div>
      <div className="pilar-tronc pilar-tronc-1">
        <span className="pilar-person"></span>
      </div>

      {/* Manilles - 3 persones */}
      <div className="pilar-manilles">
        <span className="pilar-person pilar-manilles-person"></span>
        <span className="pilar-person pilar-manilles-person"></span>
        <span className="pilar-person pilar-manilles-person"></span>
      </div>

      {/* Folre - 5 persones */}
      <div className="pilar-folre">
        <span className="pilar-person pilar-folre-person"></span>
        <span className="pilar-person pilar-folre-person"></span>
        <span className="pilar-person pilar-folre-person"></span>
        <span className="pilar-person pilar-folre-person"></span>
        <span className="pilar-person pilar-folre-person"></span>
      </div>

      {/* Pinya - 8 persones */}
      <div className="pilar-pinya">
        <span className="pilar-person pilar-pinya-person"></span>
        <span className="pilar-person pilar-pinya-person"></span>
        <span className="pilar-person pilar-pinya-person"></span>
        <span className="pilar-person pilar-pinya-person"></span>
        <span className="pilar-person pilar-pinya-person"></span>
        <span className="pilar-person pilar-pinya-person"></span>
        <span className="pilar-person pilar-pinya-person"></span>
        <span className="pilar-person pilar-pinya-person"></span>
      </div>
    </div>
  );
};

export default PilarLoader;

