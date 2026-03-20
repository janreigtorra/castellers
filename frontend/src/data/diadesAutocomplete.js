import diadesCatalog from './diades.json';

/** Unique diada names from diades.json, sorted for stable autocomplete order (after colles). */
const raw = Array.isArray(diadesCatalog) ? diadesCatalog : [];
const seen = new Set();
const names = [];
for (const item of raw) {
  const n = item && typeof item.name === 'string' ? item.name.trim() : '';
  if (!n) continue;
  const k = n.toLowerCase();
  if (seen.has(k)) continue;
  seen.add(k);
  names.push(n);
}
names.sort((a, b) => a.localeCompare(b, 'ca', { sensitivity: 'base' }));

export const DIADES_AUTOCOMPLETE = names;
