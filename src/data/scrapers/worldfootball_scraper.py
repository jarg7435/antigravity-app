"""
worldfootball_scraper.py — WorldFootball.net para árbitros e historial
======================================================================
Especializado en árbitros con estadísticas históricas.
"""
import requests
from bs4 import BeautifulSoup
from typing import Dict, List, Optional
from datetime import datetime
import re

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
    'Accept-Language': 'es-ES,es;q=0.9,en;q=0.8',
}

LEAGUE_PATHS = {
    "La Liga":        "esp-primera-division",
    "Premier League": "eng-premier-league",
    "Bundesliga":     "bundesliga",
    "Serie A":        "ita-serie-a",
    "Ligue 1":        "fra-ligue-1",
    "Champions League": "champions-league",
}


def _slugify(name: str) -> str:
    """Convierte nombre a slug para WorldFootball."""
    s = name.lower().strip()
    s = re.sub(r'[áàä]', 'a', s)
    s = re.sub(r'[éèë]', 'e', s)
    s = re.sub(r'[íìï]', 'i', s)
    s = re.sub(r'[óòö]', 'o', s)
    s = re.sub(r'[úùü]', 'u', s)
    s = re.sub(r'ñ', 'n', s)
    s = re.sub(r'[^a-z0-9\s-]', '', s)
    s = re.sub(r'\s+', '-', s).strip('-')
    return s


def fetch_referee(home: str, away: str, league: str = "") -> Optional[Dict]:
    """Busca árbitro en WorldFootball.net."""
    try:
        league_path = LEAGUE_PATHS.get(league, "")
        home_slug = _slugify(home)
        away_slug = _slugify(away)

        urls_to_try = []
        if league_path:
            urls_to_try.append(
                f"https://www.worldfootball.net/report/{league_path}-{datetime.now().year}-{datetime.now().year+1}/{home_slug}-{away_slug}/"
            )
        # Búsqueda general
        search_url = f"https://www.worldfootball.net/teams/{home_slug}/"
        urls_to_try.append(search_url)

        for url in urls_to_try:
            try:
                r = requests.get(url, headers=HEADERS, timeout=8)
                if r.status_code != 200:
                    continue
                soup = BeautifulSoup(r.text, 'html.parser')

                # Buscar árbitro en tabla de info del partido
                for row in soup.find_all('tr'):
                    cells = row.find_all('td')
                    if len(cells) >= 2:
                        label = cells[0].get_text().strip().lower()
                        if 'arbitro' in label or 'referee' in label or 'schiedsrichter' in label:
                            ref_name = cells[1].get_text().strip()
                            if len(ref_name.split()) >= 2:
                                return {
                                    "name": ref_name,
                                    "source": "WorldFootball.net",
                                    "verification_link": url,
                                    "_is_fallback": False
                                }
            except Exception:
                continue

    except Exception as e:
        print(f"[WorldFootball] referee error: {e}")
    return None


def fetch_referee_stats(referee_name: str) -> Dict:
    """
    Obtiene estadísticas históricas del árbitro desde WorldFootball.
    Devuelve avg_cards, avg_yellows, avg_reds si los encuentra.
    """
    stats = {}
    try:
        slug = _slugify(referee_name)
        url = f"https://www.worldfootball.net/referee/{slug}/"
        r = requests.get(url, headers=HEADERS, timeout=8)
        if r.status_code != 200:
            return stats

        soup = BeautifulSoup(r.text, 'html.parser')

        # Buscar tabla de estadísticas
        for table in soup.find_all('table'):
            headers_row = table.find('tr')
            if not headers_row:
                continue
            headers = [th.get_text().strip().lower() for th in headers_row.find_all(['th','td'])]

            for row in table.find_all('tr')[1:]:
                cells = row.find_all('td')
                if len(cells) < 3:
                    continue
                row_data = {headers[i]: cells[i].get_text().strip()
                           for i in range(min(len(headers), len(cells)))}

                # Buscar columnas de tarjetas
                for key in headers:
                    if 'gelb' in key or 'yellow' in key or 'amarilla' in key:
                        try:
                            stats['avg_yellows'] = float(row_data[key].replace(',','.'))
                        except Exception:
                            pass
                    if 'rot' in key or 'red' in key or 'roja' in key:
                        try:
                            stats['avg_reds'] = float(row_data[key].replace(',','.'))
                        except Exception:
                            pass

        if 'avg_yellows' in stats:
            stats['avg_cards'] = stats.get('avg_yellows', 0) + stats.get('avg_reds', 0)

    except Exception as e:
        print(f"[WorldFootball] stats error for {referee_name}: {e}")
    return stats
