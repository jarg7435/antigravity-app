"""
Fuentes de élite por liga — La Gema JARG74.

Mapa curado de los medios que publican alineaciones probables y partes de
lesiones con mayor fiabilidad en cada una de las cinco grandes ligas europeas
que fija Objetivos.md.

Se conserva como datos de referencia para el scraping selectivo: indica qué
sitios merece la pena consultar por liga, sin imponer cómo hacerlo. El scraper
de FutbolFantasy (futbolfantasy_scraper.py) es la primera implementación real
sobre esta lista.

Autor: Antigravity - La Gema JARG74
"""

from typing import Dict, List

ELITE_SOURCES: Dict[str, List[str]] = {
    "La Liga": [
        "https://www.futbolfantasy.com",
        "https://as.com",
        "https://marca.com",
    ],
    "Premier League": [
        "https://www.premierinjuries.com",
        "https://theathletic.com",
    ],
    "Serie A": [
        "https://www.gazzetta.it",
        "https://sosfanta.calciomercato.com",
    ],
    "Bundesliga": [
        "https://www.kicker.de",
        "https://www.ligainsider.de",
    ],
    "Ligue 1": [
        "https://www.lequipe.fr",
        "https://www.rmcsport.bfmtv.com",
    ],
}


def fuentes_de(liga: str) -> List[str]:
    """
    Fuentes de élite de una liga, o lista vacía si no hay ninguna registrada.

    Acepta el nombre normalizado que produce
    multi_source_fetcher._norm_league() ("La Liga", "Premier League", ...).
    """
    return list(ELITE_SOURCES.get(liga, []))
