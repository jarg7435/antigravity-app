"""
Serie A Data Scraper
Cascade: Fantacalcio (JS) → AIA-FIGC → Fallback Pool

Sources:
- Lineups:  https://www.fantacalcio.it/probabili-formazioni-serie-a
- Referee:  https://www.aia-figc.it/designazioni/cana/
"""
import requests
from bs4 import BeautifulSoup
from typing import Dict, Optional
from datetime import datetime
import re
from src.data.scrapers.js_scraper import get_html_with_js, is_available as js_available


HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
    'Accept-Language': 'it-IT,it;q=0.9,en;q=0.8',
}

SERIE_A_REFEREE_POOL = [
    {'name': 'Daniele Orsato', 'avg_cards': 5.3},
    {'name': 'Marco Guida', 'avg_cards': 3.6},
    {'name': 'Davide Massa', 'avg_cards': 4.4},
    {'name': 'Maurizio Mariani', 'avg_cards': 4.1},
    {'name': 'Luca Pairetto', 'avg_cards': 4.0},
    {'name': 'Gianluca Manganiello', 'avg_cards': 4.7},
]


def fetch_lineup_fantacalcio(home: str, away: str) -> Dict:
    """Fetches probable lineups from Fantacalcio."""
    result = {'home': [], 'away': [], 'bajas': [], 'source': None}
    try:
        url = "https://www.fantacalcio.it/probabili-formazioni-serie-a"
        resp = requests.get(url, headers=HEADERS, timeout=12)
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, 'html.parser')

        home_n = home.lower()[:6]
        away_n = away.lower()[:6]
        home_players, away_players = [], []

        # Fantacalcio uses .match-tab or .team-module per team
        for card in soup.find_all(['div', 'article'], class_=re.compile(r'match|partita|formaz', re.I)):
            card_text = card.get_text(separator=' ').lower()
            if home_n in card_text and away_n in card_text:
                teams = card.find_all(class_=re.compile(r'team|squadra', re.I))
                for i, team in enumerate(teams[:2]):
                    players = [el.get_text().strip() for el in team.find_all(class_=re.compile(r'player|giocator', re.I)) if el.get_text().strip()]
                    if i == 0:
                        home_players = players[:11]
                    else:
                        away_players = players[:11]
                break

        result.update({'home': home_players, 'away': away_players,
                       'source': f"Fantacalcio ({url})", 'verification_link': url})
    except Exception as e:
        print(f"    [Fantacalcio] Error: {e}")
    return result


def fetch_referee_aia(home: str, away: str) -> Optional[Dict]:
    """Fetches referee from AIA-FIGC official designations."""
    try:
        url = "https://www.aia-figc.it/designazioni/cana/"
        resp = requests.get(url, headers=HEADERS, timeout=12)
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, 'html.parser')

        text = soup.get_text(separator=' ')
        home_kw = home.lower().split()[0]
        away_kw = away.lower().split()[0]

        pattern = rf'{home_kw}.{{0,100}}{away_kw}.{{0,300}}?([A-ZÁÉÍÓÚ][a-záéíóú]+(?:\s[A-ZÁÉÍÓÚ][a-záéíóú]+){{1,3}})'
        m = re.search(pattern, text, re.IGNORECASE | re.DOTALL)
        if m:
            return {'name': m.group(1).strip(), 'source': 'AIA-FIGC', 'verification_link': url}
    except Exception as e:
        print(f"    [AIA] Error: {e}")
    return None


class SerieADataScraper:
    """Unified scraper for Serie A. Cascade: Fantacalcio → AIA → Fallback Pool."""

    def fetch_lineup(self, home: str, away: str, match_date: datetime) -> Dict:
        print(f"  [SerieA] Fetching lineup: {home} vs {away}")
        result = fetch_lineup_fantacalcio(home, away)
        if result['home'] or result['away']:
            return result
        return {'home': [], 'away': [], 'bajas': [], 'source': 'Sin datos Serie A', 'verification_link': 'https://www.fantacalcio.it/probabili-formazioni-serie-a'}

    def fetch_referee(self, home: str, away: str, match_date: datetime) -> Dict:
        import random
        print(f"  [SerieA] Fetching referee: {home} vs {away}")
        ref = fetch_referee_aia(home, away)
        if ref:
            return self._enrich_referee(ref)
        fallback = random.choice(SERIE_A_REFEREE_POOL)
        return {'name': fallback['name'], 'avg_cards': fallback['avg_cards'],
                'source': 'Pool Serie A', 'verification_link': 'https://www.aia-figc.it/designazioni/cana/', '_is_fallback': True}

    def _enrich_referee(self, ref: Dict) -> Dict:
        from src.models.base import RefereeStrictness
        name = ref.get('name', '').lower()
        ref['strictness'] = RefereeStrictness.HIGH if 'orsato' in name or 'massa' in name else RefereeStrictness.MEDIUM
        ref['avg_cards'] = 5.0 if ref['strictness'] == RefereeStrictness.HIGH else 4.0
        ref['_is_fallback'] = False
        return ref
