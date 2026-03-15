"""
besoccer_scraper.py — BeSoccer scraper para alineaciones y árbitros
====================================================================
Cubre todas las ligas. Funciona con requests (sin JS).
"""
import requests
from bs4 import BeautifulSoup
from typing import Dict, List, Optional
from datetime import datetime
import re

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36',
    'Accept-Language': 'es-ES,es;q=0.9',
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
}

TEAM_SLUGS = {
    "FC Barcelona": "barcelona", "Real Madrid": "real-madrid",
    "Atletico Madrid": "atletico-madrid", "Sevilla FC": "sevilla",
    "Athletic Club": "athletic-club", "Villarreal": "villarreal",
    "Real Betis": "real-betis", "Real Sociedad": "real-sociedad",
    "Celta de Vigo": "celta-vigo", "Osasuna": "osasuna",
    "Alavés": "alaves", "Girona": "girona", "Mallorca": "mallorca",
    "Valencia": "valencia", "Getafe": "getafe",
    "Rayo Vallecano": "rayo-vallecano", "Espanyol": "espanyol",
    "Arsenal": "arsenal", "Manchester City": "manchester-city",
    "Liverpool": "liverpool", "Chelsea": "chelsea",
    "Tottenham": "tottenham-hotspur", "Manchester Utd": "manchester-united",
    "Newcastle": "newcastle-united", "Aston Villa": "aston-villa",
    "Bayern Munich": "bayern-munchen", "Dortmund": "borussia-dortmund",
    "Bayer Leverkusen": "bayer-leverkusen", "RB Leipzig": "rb-leipzig",
    "Inter Milan": "inter", "AC Milan": "milan",
    "Napoles": "napoli", "Juventus": "juventus", "AS Roma": "roma",
    "PSG": "paris-saint-germain", "Marseille": "marseille",
    "Lyon": "olympique-lyonnais", "Monaco": "monaco",
}


def _get_slug(name: str) -> str:
    if name in TEAM_SLUGS:
        return TEAM_SLUGS[name]
    slug = re.sub(r'^(FC|CF|CD|UD|SD)\s+', '', name, flags=re.I)
    return slug.lower().strip().replace(' ', '-').replace('.', '')


def fetch_lineup(home: str, away: str) -> Dict:
    """Busca alineaciones en BeSoccer."""
    result = {"home": [], "away": [], "bajas": [],
              "source": "BeSoccer", "verification_link": None, "_is_fallback": True}
    try:
        home_slug = _get_slug(home)
        away_slug = _get_slug(away)
        url = f"https://es.besoccer.com/partido/{home_slug}/{away_slug}"
        r = requests.get(url, headers=HEADERS, timeout=10)
        if r.status_code != 200:
            return result

        soup = BeautifulSoup(r.text, 'html.parser')
        result["verification_link"] = url

        # Buscar jugadores en la alineación
        home_players, away_players = [], []

        # Estrategia 1: divs con clase lineup/team
        for div in soup.find_all(['div', 'ul'], class_=re.compile(r'lineup|team-lineup|formation', re.I)):
            players = [a.get_text().strip() for a in div.find_all('a')
                      if len(a.get_text().strip().split()) >= 2]
            if players:
                if not home_players:
                    home_players = players[:11]
                elif not away_players:
                    away_players = players[:11]

        # Estrategia 2: spans/links con nombres
        if not home_players:
            player_links = soup.find_all('a', href=re.compile(r'/jugador/|/player/'))
            names = [a.get_text().strip() for a in player_links
                    if len(a.get_text().strip().split()) >= 2]
            if len(names) >= 11:
                home_players = names[:11]
                away_players = names[11:22]

        if home_players or away_players:
            result.update({
                "home": home_players,
                "away": away_players,
                "_is_fallback": False
            })

    except Exception as e:
        print(f"[BeSoccer] lineup error: {e}")
    return result


def fetch_referee(home: str, away: str) -> Optional[Dict]:
    """Busca árbitro en BeSoccer."""
    try:
        home_slug = _get_slug(home)
        away_slug = _get_slug(away)
        url = f"https://es.besoccer.com/partido/{home_slug}/{away_slug}"
        r = requests.get(url, headers=HEADERS, timeout=10)
        if r.status_code != 200:
            return None

        soup = BeautifulSoup(r.text, 'html.parser')

        # Buscar árbitro en la página
        for el in soup.find_all(string=re.compile(r'árbitro|arbitro|referee', re.I)):
            parent = el.parent
            text = parent.get_text(separator=' ').strip()
            # Buscar nombre tras la palabra árbitro
            m = re.search(
                r'(?:árbitro|arbitro|referee)[:\s]+([A-ZÁÉÍÓÚÑ][a-záéíóúñ]+(?:\s+[A-ZÁÉÍÓÚÑ][a-záéíóúñ]+){1,2})',
                text, re.IGNORECASE
            )
            if m:
                name = m.group(1).strip()
                if len(name.split()) >= 2:
                    return {
                        "name": name,
                        "source": "BeSoccer",
                        "verification_link": url,
                        "_is_fallback": False
                    }

        # Buscar en sección de info del partido
        info_divs = soup.find_all(['div','span','p'],
                                   class_=re.compile(r'referee|arbitro|match-info', re.I))
        for div in info_divs:
            text = div.get_text().strip()
            if len(text.split()) in range(2, 5):
                return {
                    "name": text,
                    "source": "BeSoccer",
                    "verification_link": url,
                    "_is_fallback": False
                }

    except Exception as e:
        print(f"[BeSoccer] referee error: {e}")
    return None
