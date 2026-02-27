"""
Bundesliga Data Scraper
Cascade: Kicker.de (JS) → DFB → Fallback Pool

Sources:
- Lineups:  https://www.kicker.de/bundesliga/aufstellungen
- Referee:  https://www.dfb.de/sportl-strukturen/schiedsrichter/ansetzungen/
"""
import requests
from bs4 import BeautifulSoup
from typing import Dict, Optional
from datetime import datetime
import re
from src.data.scrapers.js_scraper import get_html_with_js, is_available as js_available


HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
    'Accept-Language': 'de-DE,de;q=0.9,en;q=0.8',
}

BUNDESLIGA_REFEREE_POOL = [
    {'name': 'Felix Brych', 'avg_cards': 4.8},
    {'name': 'Tobias Stieler', 'avg_cards': 3.3},
    {'name': 'Deniz Aytekin', 'avg_cards': 4.0},
    {'name': 'Marco Fritz', 'avg_cards': 3.9},
    {'name': 'Daniel Schlager', 'avg_cards': 4.2},
    {'name': 'Robert Kampka', 'avg_cards': 3.7},
]


def fetch_lineup_kicker(home: str, away: str) -> Dict:
    """Fetches lineup from Kicker.de."""
    result = {'home': [], 'away': [], 'bajas': [], 'source': None}
    try:
        url = "https://www.kicker.de/bundesliga/aufstellungen"
        resp = requests.get(url, headers=HEADERS, timeout=12)
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, 'html.parser')

        home_n = home.lower()[:6]
        away_n = away.lower()[:6]
        home_players, away_players = [], []

        for card in soup.find_all(['div', 'article'], class_=re.compile(r'match|spiel|aufst', re.I)):
            card_text = card.get_text(separator=' ').lower()
            if home_n in card_text and away_n in card_text:
                teams = card.find_all(class_=re.compile(r'team|mannschaft', re.I))
                for i, team in enumerate(teams[:2]):
                    players = [el.get_text().strip() for el in
                               team.find_all(class_=re.compile(r'player|spieler', re.I))
                               if el.get_text().strip()]
                    if i == 0:
                        home_players = players[:11]
                    else:
                        away_players = players[:11]
                break

        result.update({'home': home_players, 'away': away_players,
                       'source': f"Kicker.de ({url})", 'verification_link': url})
    except Exception as e:
        print(f"    [Kicker] Error: {e}")
    return result


def fetch_referee_dfb(home: str, away: str) -> Optional[Dict]:
    """Fetches referee from DFB official page."""
    try:
        url = "https://www.dfb.de/sportl-strukturen/schiedsrichter/ansetzungen/"
        resp = requests.get(url, headers=HEADERS, timeout=12)
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, 'html.parser')
        text = soup.get_text(separator=' ')
        home_kw = home.lower().split()[0]
        away_kw = away.lower().split()[0]
        pattern = rf'{home_kw}.{{0,100}}{away_kw}.{{0,300}}?([A-ZÁÉÍÓÚ][a-záéíóú]+(?:\s[A-ZÁÉÍÓÚ][a-záéíóú]+){{1,3}})'
        m = re.search(pattern, text, re.IGNORECASE | re.DOTALL)
        if m:
            return {'name': m.group(1).strip(), 'source': 'DFB Oficial', 'verification_link': url}
    except Exception as e:
        print(f"    [DFB] Error: {e}")
    return None


class BundesligaDataScraper:
    """Unified scraper for Bundesliga. Cascade: Kicker → DFB → Fallback Pool."""

    def fetch_lineup(self, home: str, away: str, match_date: datetime) -> Dict:
        print(f"  [Bundesliga] Fetching lineup: {home} vs {away}")
        result = fetch_lineup_kicker(home, away)
        if result['home'] or result['away']:
            return result
        return {'home': [], 'away': [], 'bajas': [], 'source': 'Sin datos Bundesliga', 'verification_link': 'https://www.kicker.de/bundesliga/aufstellungen'}

    def fetch_referee(self, home: str, away: str, match_date: datetime) -> Dict:
        import random
        print(f"  [Bundesliga] Fetching referee: {home} vs {away}")
        ref = fetch_referee_dfb(home, away)
        if ref:
            return self._enrich_referee(ref)
        fallback = random.choice(BUNDESLIGA_REFEREE_POOL)
        return {'name': fallback['name'], 'avg_cards': fallback['avg_cards'],
                'source': 'Pool Bundesliga', 'verification_link': 'https://www.dfb.de/sportl-strukturen/schiedsrichter/ansetzungen/', '_is_fallback': True}

    def _enrich_referee(self, ref: Dict) -> Dict:
        from src.models.base import RefereeStrictness
        name = ref.get('name', '').lower()
        ref['strictness'] = RefereeStrictness.HIGH if 'brych' in name or 'aytekin' in name else RefereeStrictness.MEDIUM
        ref['avg_cards'] = 4.8 if ref['strictness'] == RefereeStrictness.HIGH else 3.9
        ref['_is_fallback'] = False
        return ref
