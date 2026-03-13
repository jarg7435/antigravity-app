"""
Ligue 1 Data Scraper
Cascade: L'Équipe (JS) → FFF/LFP → Fallback Pool

Sources:
- Lineups:  https://www.lequipe.fr/Football/Actualite/Compositions-probables
- Referee:  https://fff.fr/arbitrage/designations/
"""
import requests
from bs4 import BeautifulSoup
from typing import Dict, Optional
from datetime import datetime
import re
from src.data.scrapers.js_scraper import get_html_with_js, is_available as js_available


HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
    'Accept-Language': 'fr-FR,fr;q=0.9,en;q=0.8',
}

LIGUE1_REFEREE_POOL = [
    {'name': 'Clément Turpin', 'avg_cards': 4.7},
    {'name': 'Benoît Bastien', 'avg_cards': 4.0},
    {'name': 'François Letexier', 'avg_cards': 3.8},
    {'name': 'Jérôme Brisard', 'avg_cards': 3.3},
    {'name': 'Willy Delajod', 'avg_cards': 4.1},
    {'name': 'Ruddy Buquet', 'avg_cards': 3.6},
]


def fetch_lineup_lequipe(home: str, away: str) -> Dict:
    """Fetches probable lineup from L'Equipe."""
    result = {'home': [], 'away': [], 'bajas': [], 'source': None}
    try:
        url = "https://www.lequipe.fr/Football/Actualite/Compositions-probables-de-la-journee-de-ligue-1/1"
        resp = requests.get(url, headers=HEADERS, timeout=12)
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, 'html.parser')

        home_n = home.lower()[:6]
        away_n = away.lower()[:6]
        home_players, away_players = [], []

        for card in soup.find_all(['div', 'section'], class_=re.compile(r'match|rencontr|compo', re.I)):
            card_text = card.get_text(separator=' ').lower()
            if home_n in card_text and away_n in card_text:
                teams = card.find_all(class_=re.compile(r'team|equipe', re.I))
                for i, team in enumerate(teams[:2]):
                    players = [el.get_text().strip() for el in
                               team.find_all(class_=re.compile(r'player|joueur', re.I))
                               if el.get_text().strip()]
                    if i == 0:
                        home_players = players[:11]
                    else:
                        away_players = players[:11]
                break

        result.update({'home': home_players, 'away': away_players,
                       'source': f"L'Equipe ({url})", 'verification_link': url})
    except Exception as e:
        print(f"    [L'Equipe] Error: {e}")
    return result


def fetch_referee_fff(home: str, away: str) -> Optional[Dict]:
    """Fetches referee from FFF official designations."""
    try:
        url = "https://fff.fr/arbitrage/designations/"
        resp = requests.get(url, headers=HEADERS, timeout=12)
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, 'html.parser')
        text = soup.get_text(separator=' ')
        home_kw = home.lower().split()[0]
        away_kw = away.lower().split()[0]
        pattern = rf'{home_kw}.{{0,100}}{away_kw}.{{0,300}}?([A-ZÁÉÍÓÚ][a-záéíóú]+(?:\s[A-ZÁÉÍÓÚ][a-záéíóú]+){{1,3}})'
        m = re.search(pattern, text, re.IGNORECASE | re.DOTALL)
        if m:
            return {'name': m.group(1).strip(), 'source': 'FFF Oficial', 'verification_link': url}
    except Exception as e:
        print(f"    [FFF] Error: {e}")
    return None


class Ligue1DataScraper:
    """Unified scraper for Ligue 1. Cascade: L'Equipe → FFF → Fallback Pool."""

    def fetch_lineup(self, home: str, away: str, match_date: datetime) -> Dict:
        print(f"  [Ligue1] Fetching lineup: {home} vs {away}")
        result = fetch_lineup_lequipe(home, away)
        if result['home'] or result['away']:
            return result
        return {'home': [], 'away': [], 'bajas': [], 'source': 'Sin datos Ligue 1', 'verification_link': 'https://www.lequipe.fr'}

    def fetch_referee(self, home: str, away: str, match_date: datetime) -> Dict:
        import random
        print(f"  [Ligue1] Fetching referee: {home} vs {away}")
        ref = fetch_referee_fff(home, away)
        if ref:
            return self._enrich_referee(ref)
        fallback = random.choice(LIGUE1_REFEREE_POOL)
        return {'name': fallback['name'], 'avg_cards': fallback['avg_cards'],
                'source': 'Pool Ligue 1', 'verification_link': 'https://fff.fr/arbitrage/designations/', '_is_fallback': True}

    def _enrich_referee(self, ref: Dict) -> Dict:
        from src.models.base import RefereeStrictness
        name = ref.get('name', '').lower()
        ref['strictness'] = RefereeStrictness.HIGH if 'turpin' in name or 'letexier' in name else RefereeStrictness.MEDIUM
        ref['avg_cards'] = 4.7 if ref['strictness'] == RefereeStrictness.HIGH else 3.9
        ref['_is_fallback'] = False
        return ref
