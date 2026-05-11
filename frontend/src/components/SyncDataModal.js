import React, { useState, useEffect } from 'react';
import { apiService } from '../apiService';

const SyncDataModal = ({ user, onClose, theme }) => {
  const [dateStart, setDateStart] = useState('');
  const [dateEnd, setDateEnd] = useState('');
  const [useToday, setUseToday] = useState(false);
  const [lastEventDate, setLastEventDate] = useState(null);
  const [isLoadingLastDate, setIsLoadingLastDate] = useState(true);
  const [isScraping, setIsScraping] = useState(false);
  const [isUpdating, setIsUpdating] = useState(false);
  const [isRevistaScraping, setIsRevistaScraping] = useState(false);
  const [isRagIndexing, setIsRagIndexing] = useState(false);
  const [scrapeResult, setScrapeResult] = useState(null);
  const [updateResult, setUpdateResult] = useState(null);
  const [revistaResult, setRevistaResult] = useState(null);
  const [ragIndexResult, setRagIndexResult] = useState(null);
  const [error, setError] = useState('');

  useEffect(() => {
    loadLastEventDate();
  }, []);

  useEffect(() => {
    if (useToday) {
      const today = new Date();
      const day = String(today.getDate()).padStart(2, '0');
      const month = String(today.getMonth() + 1).padStart(2, '0');
      const year = today.getFullYear();
      setDateEnd(`${day}/${month}/${year}`);
    }
  }, [useToday]);

  const loadLastEventDate = async () => {
    setIsLoadingLastDate(true);
    try {
      const date = await apiService.getLastEventDate();
      setLastEventDate(date);
    } catch (err) {
      console.error('Error loading last event date:', err);
      setError('Error loading last event date');
    } finally {
      setIsLoadingLastDate(false);
    }
  };

  const handleScrape = async () => {
    if (!dateStart || !dateEnd) {
      setError('Please provide both start and end dates');
      return;
    }

    setIsScraping(true);
    setError('');
    setScrapeResult(null);

    try {
      const result = await apiService.scrapeEvents(dateStart, dateEnd);
      setScrapeResult(result);
    } catch (err) {
      // Extract error message from axios error response
      const errorMessage = err.response?.data?.detail || err.message || 'Error scraping events';
      setError(errorMessage);
      console.error('Scrape error:', err);
      console.error('Error details:', err.response?.data);
    } finally {
      setIsScraping(false);
    }
  };

  const handleUpdateDatabase = async () => {
    if (!dateStart) {
      setError('Please provide a start date');
      return;
    }

    setIsUpdating(true);
    setError('');
    setUpdateResult(null);

    try {
      const result = await apiService.updateDatabase(dateStart);
      setUpdateResult(result);
    } catch (err) {
      // Extract error message from axios error response
      const errorMessage = err.response?.data?.detail || err.message || 'Error updating database';
      setError(errorMessage);
      console.error('Update error:', err);
      console.error('Error details:', err.response?.data);
    } finally {
      setIsUpdating(false);
    }
  };

  const handleRevistaScrape = async () => {
    setIsRevistaScraping(true);
    setError('');
    setRevistaResult(null);
    try {
      const result = await apiService.scrapeRevistaCastells();
      setRevistaResult(result);
    } catch (err) {
      const errorMessage =
        err.response?.data?.detail || err.message || "Error en l'scrape de Revista Castells";
      setError(errorMessage);
      console.error('Revista scrape error:', err);
    } finally {
      setIsRevistaScraping(false);
    }
  };

  const handleRagIndex = async () => {
    setIsRagIndexing(true);
    setError('');
    setRagIndexResult(null);
    try {
      const result = await apiService.indexRagChunks();
      setRagIndexResult(result);
    } catch (err) {
      const errorMessage =
        err.response?.data?.detail || err.message || "Error en l'indexació RAG";
      setError(errorMessage);
      console.error('RAG index error:', err);
    } finally {
      setIsRagIndexing(false);
    }
  };

  const formatDate = (dateStr) => {
    if (!dateStr) return 'N/A';
    // If date is in DD/MM/YYYY format, return as is
    if (dateStr.includes('/')) {
      return dateStr;
    }
    // Otherwise try to parse and format
    try {
      const date = new Date(dateStr);
      const day = String(date.getDate()).padStart(2, '0');
      const month = String(date.getMonth() + 1).padStart(2, '0');
      const year = date.getFullYear();
      return `${day}/${month}/${year}`;
    } catch {
      return dateStr;
    }
  };

  return (
    <div className="sync-modal-overlay" onClick={onClose}>
      <div className="sync-modal" onClick={(e) => e.stopPropagation()}>
        <button 
          className="sync-modal-close"
          onClick={onClose}
        >
          <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
            <line x1="18" y1="6" x2="6" y2="18" />
            <line x1="6" y1="6" x2="18" y2="18" />
          </svg>
        </button>

        <h2>Sincronitzar Noves Dades</h2>

        {/* Last Event Date */}
        <div className="sync-section">
          <label>Última data d'event a la base de dades:</label>
          <div className="sync-info">
            {isLoadingLastDate ? (
              <span>Carregant...</span>
            ) : (
              <strong>{lastEventDate ? formatDate(lastEventDate) : 'No hi ha events'}</strong>
            )}
          </div>
        </div>

        {/* Date Inputs */}
        <div className="sync-section">
          <label htmlFor="date-start">Data d'inici (DD/MM/YYYY):</label>
          <input
            id="date-start"
            type="text"
            value={dateStart}
            onChange={(e) => setDateStart(e.target.value)}
            placeholder="DD/MM/YYYY"
            className="sync-input"
          />
        </div>

        <div className="sync-section">
          <label htmlFor="date-end">Data de fi (DD/MM/YYYY):</label>
          <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
            <input
              id="date-end"
              type="text"
              value={dateEnd}
              onChange={(e) => setDateEnd(e.target.value)}
              placeholder="DD/MM/YYYY"
              className="sync-input"
              disabled={useToday}
            />
            <label style={{ display: 'flex', alignItems: 'center', gap: '5px', cursor: 'pointer' }}>
              <input
                type="checkbox"
                checked={useToday}
                onChange={(e) => setUseToday(e.target.checked)}
              />
              <span>Avui</span>
            </label>
          </div>
        </div>

        {/* Error Message */}
        {error && (
          <div className="sync-error">
            {error}
          </div>
        )}

        {/* Scrape Button */}
        <div className="sync-section">
          <button
            className="sync-button"
            onClick={handleScrape}
            disabled={isScraping || !dateStart || !dateEnd}
          >
            {isScraping ? 'Sincronitzant...' : 'Sincronitzar Events'}
          </button>

          {scrapeResult && (
            <div className="sync-result">
              <h3>Resultat de la sincronització:</h3>
              <div className="sync-stats">
                <p><strong>Total events:</strong> {scrapeResult.total_events || 'N/A'}</p>
                <p><strong>Events amb resultats:</strong> {scrapeResult.events_with_results || 'N/A'}</p>
                <p><strong>Total castells:</strong> {scrapeResult.total_castells || 'N/A'}</p>
                <p><strong>Colles úniques:</strong> {scrapeResult.unique_colles || 'N/A'}</p>
                <p><strong>Ciutats úniques:</strong> {scrapeResult.unique_cities || 'N/A'}</p>
              </div>
            </div>
          )}
        </div>

        {/* Update Database Button */}
        <div className="sync-section">
          <button
            className="sync-button"
            onClick={handleUpdateDatabase}
            disabled={isUpdating || !dateStart}
          >
            {isUpdating ? 'Actualitzant base de dades...' : 'Actualitzar Base de Dades'}
          </button>

          {updateResult && (
            <div className="sync-result">
              <h3>Resultat de l'actualització:</h3>
              <div className="sync-stats">
                <p><strong>Events inserits:</strong> {updateResult.events_inserted || 0}</p>
                <p><strong>Relacions event-colla:</strong> {updateResult.event_colles_inserted || 0}</p>
                <p><strong>Castells inserits:</strong> {updateResult.castells_inserted || 0}</p>
              </div>
            </div>
          )}
        </div>

        <hr className="sync-modal-divider" />

        <div className="sync-section">
          <h3 className="sync-subheading">Revista Castells i cerca (RAG)</h3>
          <p className="sync-hint">
            Només afegeix contingut nou (idempotent): primer actualitza el JSON des del web, després
            incrusta i insereix a Supabase els chunks que encara no hi són.
          </p>
          <button
            type="button"
            className="sync-button"
            onClick={handleRevistaScrape}
            disabled={isRevistaScraping || isRagIndexing}
          >
            {isRevistaScraping ? 'Descarregant Revista…' : 'Actualitzar JSON Revista Castells'}
          </button>
          {revistaResult && (
            <div className="sync-result">
              <h3>Resultat Revista (fitxer local):</h3>
              <div className="sync-stats">
                <p>
                  <strong>Chunks nous:</strong>{' '}
                  {revistaResult.new_chunks != null ? revistaResult.new_chunks : '—'}
                </p>
                <p>
                  <strong>Articles nous:</strong>{' '}
                  {revistaResult.new_articles != null ? revistaResult.new_articles : '—'}
                </p>
              </div>
            </div>
          )}
        </div>

        <div className="sync-section">
          <button
            type="button"
            className="sync-button"
            onClick={handleRagIndex}
            disabled={isRagIndexing || isRevistaScraping}
          >
            {isRagIndexing ? 'Embeddings i Supabase…' : 'Indexar chunks nous a Supabase (RAG)'}
          </button>
          {ragIndexResult && (
            <div className="sync-result">
              <h3>Resultat indexació RAG:</h3>
              <div className="sync-stats">
                <p>
                  <strong>Processats (embed + insert):</strong>{' '}
                  {ragIndexResult.chunks_to_embed != null ? ragIndexResult.chunks_to_embed : '—'}
                </p>
                <p>
                  <strong>Files inserides (aquesta execució):</strong>{' '}
                  {ragIndexResult.rows_inserted != null ? ragIndexResult.rows_inserted : '—'}
                </p>
                <p>
                  <strong>Total a la BD:</strong>{' '}
                  {ragIndexResult.rows_total_in_db != null ? ragIndexResult.rows_total_in_db : '—'}
                </p>
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
};

export default SyncDataModal;

