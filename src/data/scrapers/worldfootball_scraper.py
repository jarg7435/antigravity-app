"""
worldfootball_scraper.py — Scraper para WorldFootball.net
=========================================================
Fuente especializada en árbitros y estadísticas históricas.
Utiliza Playwright (js_scraper) para saltar bloqueos 403.
"""
import re
import unicodedata
from typing import Dict, List, Optional
from bs4 import BeautifulSoup
from src.data.scrapers.js_scraper import get_html_with_js, is_available as js_available

# Mapeo de ligas LAGEMA -> WorldFootball slugs
LEAGUE_SLUGS = {
    "La Liga":          "esp-primera-division",
    "Premier League":   "eng-premier-league",
    "Serie A":          "ita-serie-a",
    "Bundesliga":       "bundesliga",
    "Ligue 1":          "fra-ligue-1",
    "Champions League": "clu",
    "Europa League":    "uel",
    "Eredivisie":       "ned-eredivisie",
    "Primeira Liga":    "por-primeira-liga",
    "Denmark":          "den-superliga",
    "Austria":          "aut-bundesliga",
    "Poland":           "pol-ekstraklasa",
    "Sweden":           "swe-allsvenskan",
    "Norway":           "nor-eliteserien",
    "Croatia":          "cro-1-hnl",
    "Czech Liga":       "cze-1-fotbalova-liga",
    "Hungary":          "hun-nb-i",
}

def _norm(text: str) -> str:
    """Normalización básica."""
    return "".join(
        c for c in unicodedata.normalize('NFD', text.lower())
        if unicodedata.category(c) != 'Mn'
    ).strip()

def _match_team(query: str, target: str) -> bool:
    q = _norm(query)
    t = _norm(target)
    if q in t or t in q:
        return True
    # Probar con partes del nombre (e.g. "Salzburg" en "Red Bull Salzburg")
    q_words = [w for w in q.split() if len(w) > 4]
    if q_words and any(w in t for w in q_words):
        return True
    return False

def _is_team_name(name: str, home: str, away: str) -> bool:
    """Evita falsos positivos donde un equipo es detectado como árbitro."""
    n = _norm(name)
    h = _norm(home)
    a = _norm(away)
    return n in h or h in n or n in a or a in n

def fetch_referee_worldfootball(home: str, away: str, league: str, season: str = "2025-2026") -> Dict:
    """
    Busca el árbitro de un partido en WorldFootball.net usando Playwright.
    """
    slug = LEAGUE_SLUGS.get(league)
    if not slug:
        print(f"    [WF] Liga no soportada: {league}")
        return {"name": None, "_is_fallback": True}

    # URL de la jornada actual/calendario completo
    # Patrón: https://www.worldfootball.net/all_matches/{slug}-{season}/
    url = f"https://www.worldfootball.net/all_matches/{slug}-{season}/"
    
    print(f"    [WF] Buscando árbitro en: {url}")
    
    html = None
    if js_available():
        html = get_html_with_js(url, wait_for="networkidle", timeout_ms=20000)
    
    if not html:
        print(f"    [WF] No se pudo obtener HTML (Playwright fail o no disponible)")
        return {"name": None, "_is_fallback": True}

    try:
        soup = BeautifulSoup(html, 'html.parser')
        # Las tablas de partidos suelen tener filas con los equipos y el árbitro al final o en un link
        # Buscamos la fila que contiene a ambos equipos
        for row in soup.find_all('tr'):
            text = row.get_text()
            if _match_team(home, text) and _match_team(away, text):
                # El árbitro suele estar en la última columna o en un enlace con "referee_summary"
                ref_link = row.find('a', href=re.compile(r'/referee_summary/'))
                if ref_link:
                    name = ref_link.get_text().strip()
                    if name and not _is_team_name(name, home, away):
                        print(f"    [WF] Árbitro encontrado: {name}")
                        return {
                            "name": name,
                            "source": "WorldFootball.net",
                            "verification_link": f"https://www.worldfootball.net{ref_link['href']}",
                            "_is_fallback": False
                        }
                
                # A veces el nombre está en texto plano al final
                cells = row.find_all('td')
                if len(cells) > 5:
                    potential_ref = cells[-1].get_text().strip()
                    if len(potential_ref.split()) >= 2 and not any(x in potential_ref.lower() for x in ["report", "info"]):
                        if not _is_team_name(potential_ref, home, away):
                            print(f"    [WF] Árbitro encontrado (texto): {potential_ref}")
                            return {
                                "name": potential_ref,
                                "source": "WorldFootball.net",
                                "verification_link": url,
                                "_is_fallback": False
                            }
        
        print(f"    [WF] Partido no encontrado en la lista de {league}")
    except Exception as e:
        print(f"    [WF] Error parseando: {e}")

    return {"name": None, "_is_fallback": True}

def fetch_referee_stats(ref_name: str) -> Dict:
    """
    Obtiene estadísticas extendidas de un árbitro desde su perfil en WorldFootball.
    """
    # Slug de búsqueda: nombres separados por guión
    slug = _norm(ref_name).replace(' ', '-')
    url = f"https://www.worldfootball.net/referee_summary/{slug}/"
    
    print(f"    [WF] Buscando stats en: {url}")
    
    html = None
    if js_available():
        html = get_html_with_js(url, wait_for="networkidle")
    
    if not html:
        return {}

    try:
        soup = BeautifulSoup(html, 'html.parser')
        # Buscar la tabla de "Referee summary"
        stats = {}
        # WorldFootball tiene tablas con columnas: Competition, Season, Matches, Yellow, Second Yellow, Red, Penalty
        # Buscamos la fila de "Total" o la temporada actual
        table = soup.find('table', class_='standard_tabelle')
        if table:
            rows = table.find_all('tr')
            for row in rows:
                if "Total" in row.get_text():
                    cols = row.find_all('td')
                    if len(cols) >= 7:
                        stats = {
                            "matches": cols[2].get_text().strip(),
                            "yellow": cols[3].get_text().strip(),
                            "yellow_red": cols[4].get_text().strip(),
                            "red": cols[5].get_text().strip(),
                            "penalty": cols[6].get_text().strip()
                        }
                        # Calcular promedios
                        try:
                            m = int(stats["matches"])
                            if m > 0:
                                stats["avg_yellow"] = round(int(stats["yellow"]) / m, 2)
                                stats["avg_red"] = round((int(stats["red"]) + int(stats["yellow_red"])) / m, 2)
                        except:
                            pass
                        break
        return stats
    except Exception as e:
        print(f"    [WF] Error stats: {e}")
        return {}
