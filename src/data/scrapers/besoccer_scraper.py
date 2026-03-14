"""
besoccer_scraper.py — Scraper para BeSoccer.com
===============================================
Especializado en ligas españolas, portuguesas y ligas menores europeas.
Utiliza Playwright (js_scraper) para saltar bloqueos 406.
"""
import re
import unicodedata
from typing import Dict, List, Optional
from bs4 import BeautifulSoup
from src.data.scrapers.js_scraper import get_html_with_js, is_available as js_available

# Mapeo de ligas LAGEMA -> BeSoccer slugs
# BeSoccer usa nombres en español en es.besoccer.com
LEAGUE_SLUGS = {
    "La Liga":          "primera_division",
    "Premier League":   "premier_league",
    "Serie A":          "serie_a",
    "Bundesliga":       "bundesliga",
    "Ligue 1":          "ligue_1",
    "Champions League": "champions_league",
    "Europa League":    "europa_league",
    "Eredivisie":       "eredivisie",
    "Primeira Liga":    "primeira_liga",
    "Segunda":          "segunda_division",
    "Denmark":          "superliga",
    "Austria":          "bundesliga_austria",
    "Hungary":          "nb_i",
    "Sweden":           "allsvenskan",
    "Norway":           "eliteserien",
    "Poland":           "ekstraklasa",
    "Croatia":          "1_hnl",
    "Slovenia":         "prva_liga",
}

def _norm(text: str) -> str:
    return "".join(
        c for c in unicodedata.normalize('NFD', text.lower())
        if unicodedata.category(c) != 'Mn'
    ).strip()

def _match_team(query: str, target: str) -> bool:
    q = _norm(query)
    t = _norm(target)
    if q in t or t in q:
        return True
    q_words = [w for w in q.split() if len(w) > 4]
    if q_words and any(w in t for w in q_words):
        return True
    return False

def _is_team_name(name: str, home: str, away: str) -> bool:
    n = _norm(name)
    h = _norm(home)
    a = _norm(away)
    return n in h or h in n or n in a or a in n

def fetch_data_besoccer(home: str, away: str, league: str, season: str = "2026") -> Dict:
    """
    Busca alineaciones y árbitro en BeSoccer.
    """
    slug = LEAGUE_SLUGS.get(league)
    if not slug:
        return {"home": [], "away": [], "referee": None, "_is_fallback": True}

    # Intentamos encontrar el partido en la lista de la competición
    url = f"https://es.besoccer.com/competicion/partidos/{slug}/{season}"
    
    print(f"    [BeSoccer] Buscando en: {url}")
    
    html = None
    if js_available():
        html = get_html_with_js(url, wait_for="networkidle", timeout_ms=25000)
    
    if not html:
        return {"home": [], "away": [], "referee": None, "_is_fallback": True}

    match_url = None
    try:
        soup = BeautifulSoup(html, 'html.parser')
        # Buscar el enlace al partido
        for a in soup.find_all('a', href=re.compile(r'/partido/')):
            text = a.get_text()
            if _match_team(home, text) and _match_team(away, text):
                match_url = a['href']
                if not match_url.startswith('http'):
                    match_url = f"https://es.besoccer.com{match_url}"
                break
    except Exception as e:
        print(f"    [BeSoccer] Error buscando partido: {e}")

    if not match_url:
        print(f"    [BeSoccer] Partido no encontrado en {url}")
        return {"home": [], "away": [], "referee": None, "_is_fallback": True}

    # Ahora scrapeamos la página del partido
    print(f"    [BeSoccer] Scrapeando partido: {match_url}")
    match_html = get_html_with_js(match_url, wait_for="networkidle", timeout_ms=20000)
    if not match_html:
        return {"home": [], "away": [], "referee": None, "_is_fallback": True}

    result = {
        "home": [], "away": [],
        "referee": None,
        "source": "BeSoccer",
        "verification_link": match_url,
        "_is_fallback": False
    }

    try:
        soup = BeautifulSoup(match_html, 'html.parser')
        
        # 1. Árbitro
        # Suele estar en un div con clase 'referee' o texto "Árbitro:"
        ref_div = soup.find(class_=re.compile(r'referee|arbitro', re.I))
        if not ref_div:
            # Buscar por texto
            ref_label = soup.find(string=re.compile(r'Árbitro:', re.I))
            if ref_label:
                ref_div = ref_label.parent
        
        if ref_div:
            ref_name = ref_div.get_text().replace('Árbitro:', '').strip()
            ref_name = re.sub(r'\(.*?\)', '', ref_name).strip()
            if ref_name and not _is_team_name(ref_name, home, away):
                result["referee"] = ref_name
                print(f"    [BeSoccer] Árbitro: {ref_name}")

        # 2. Alineaciones
        # BeSoccer tiene secciones 'posible-lineup' o 'lineup'
        # Buscamos nombres de jugadores en las tablas de alineación
        lineup_tables = soup.find_all('table', class_=re.compile(r'lineup|alineacion', re.I))
        if len(lineup_tables) >= 2:
            for i, table in enumerate(lineup_tables[:2]):
                players = []
                for name_cell in table.find_all(class_=re.compile(r'name|jugador', re.I)):
                    name = name_cell.get_text().strip()
                    if name and not name.isdigit():
                        players.append(name)
                players = list(dict.fromkeys(players))
                if i == 0: result["home"] = players[:11]
                else: result["away"] = players[:11]

    except Exception as e:
        print(f"    [BeSoccer] Error parseando partido: {e}")

    return result
