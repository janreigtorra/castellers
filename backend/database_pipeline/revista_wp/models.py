"""Data model and text enrichment for Revista dels Castells (WordPress) posts."""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from typing import Optional
from urllib.parse import urlparse

CATEGORY_MAP: dict[str, str] = {
    "noticies": "noticies",
    "notícies": "noticies",
    "noticíes": "noticies",
    "reportatges": "reportatges",
    "opinió": "opinio",
    "opinio": "opinio",
    "cròniques": "cronicles",
    "croniques": "cronicles",
    "cronicles": "cronicles",
    "història": "historia",
    "historia": "historia",
    "tècnica": "tecnica",
    "tecnica": "tecnica",
    "entrevistes": "entrevistes",
    "ciència i castells": "ciencia-i-castells",
    "ciencia-i-castells": "ciencia-i-castells",
    "cultura": "cultura",
    "internacional": "internacional",
    "sense-categoria": "general",
    "uncategorized": "general",
}

COLLA_PATTERNS = [
    r"Castellers de [A-ZÁÉÍÓÚÀÈÌÒÙÜÏÑ][a-záéíóúàèìòùüïñ\s\-]+",
    r"Castelleres de [A-ZÁÉÍÓÚÀÈÌÒÙÜÏÑ][a-záéíóúàèìòùüïñ\s\-]+",
    r"Xiquets de [A-ZÁÉÍÓÚÀÈÌÒÙÜÏÑ][a-záéíóúàèìòùüïñ\s\-]+",
    r"Xiquetes de [A-ZÁÉÍÓÚÀÈÌÒÙÜÏÑ][a-záéíóúàèìòùüïñ\s\-]+",
    r"Nens del Vendrell",
    r"Nois de la Torre",
    r"Minyons de Terrassa",
    r"Capgrossos",
    r"Bordegassos",
    r"Colla Joves Xiquets de Valls",
    r"Colla Vella dels Xiquets de Valls",
    r"Joves Xiquets de Valls",
    r"Vella dels Xiquets de Valls",
    r"Sagals d[\'e]",
    r"Galejadors",
    r"Moixiganguers",
    r"Castellers de Vilafranca",
    r"Castellers de Sants",
    r"Castellers de Sabadell",
    r"Castellers de Barcelona",
    r"Xics de Granollers",
    r"Xiquets de Reus",
    r"Xiquets del Serrallo",
]
_COLLA_RE = re.compile("|".join(COLLA_PATTERNS))

_YEAR_RE = re.compile(r"\b(1[789]\d{2}|20[012]\d)\b")

PLACE_NAMES = [
    "Valls",
    "Vilafranca del Penedès",
    "Vilafranca",
    "Tarragona",
    "Barcelona",
    "Reus",
    "Lleida",
    "Girona",
    "Terrassa",
    "Sabadell",
    "Mataró",
    "Vendrell",
    "Penedès",
    "Camp de Tarragona",
    "Garraf",
    "Maresme",
    "Vallès",
    "Sitges",
    "Igualada",
    "Manresa",
    "Vic",
    "Figueres",
    "Tortosa",
    "Catalunya",
    "País Valencià",
    "Japó",
    "Xile",
    "Santiago de Xile",
    "Vilanova i la Geltrú",
    "Granollers",
    "Cornellà",
    "Sarrià",
]
_PLACE_RE = re.compile(r"\b(" + "|".join(re.escape(p) for p in PLACE_NAMES) + r")\b")


@dataclass
class Article:
    id: str
    url: str
    title: str
    date: str
    category: str
    tags: list[str] = field(default_factory=list)
    author: Optional[str] = None
    excerpt: Optional[str] = None
    body: str = ""
    image_url: Optional[str] = None
    colles: list[str] = field(default_factory=list)
    years: list[int] = field(default_factory=list)
    places: list[str] = field(default_factory=list)
    scraped_at: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )

    def enrich(self) -> Article:
        text = f"{self.title} {self.body}"
        self.colles = sorted(set(m.strip() for m in _COLLA_RE.findall(text)))
        self.years = sorted(set(int(y) for y in _YEAR_RE.findall(text)))
        self.places = sorted(set(_PLACE_RE.findall(text)))
        if not self.excerpt and self.body:
            self.excerpt = self.body[:220].strip() + (
                "…" if len(self.body) > 220 else ""
            )
        return self

    def to_dict(self) -> dict:
        return asdict(self)


def slug_from_url(url: str) -> str:
    path = urlparse(url).path.strip("/")
    parts = path.split("/")
    return parts[-1] if parts else path


def clean_text(raw: str) -> str:
    text = unicodedata.normalize("NFC", raw)
    text = re.sub(r"\s+", " ", text)
    return text.strip()
