"""
Premier League Data Scraper
Cascade: PremierInjuries (JS) → BBC Sport (JS) → Transfermarkt → Fallback Pool

Sources:
- Lineups:  https://www.premierinjuries.com/injury-table.php
- Referee:  https://www.bbc.co.uk/sport/football
- Validate: https://www.transfermarkt.co.uk
"""
import requests
from bs4 import BeautifulSoup
from typing import Dict, List, Optional
from datetime import datetime
import re
from src.data.scrapers.js_scraper import get_html_with_js, is_available as js_available


HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36',
    'Accept-Language': 'en-GB,en;q=0.9',
}

PREMIER_REFEREE_POOL = [
    {'name': 'Michael Oliver', 'avg_cards': 4.9},
    {'name': 'Anthony Taylor', 'avg_cards': 5.1},
    {'name': 'Craig Pawson', 'avg_cards': 3.4},
    {'name': 'Paul Tierney', 'avg_cards': 4.0},
    {'name': 'Simon Hooper', 'avg_cards': 4.2},
    {'name': 'John Brooks', 'avg_cards': 3.8},
    {'name': 'Robert Jones', 'avg_cards': 4.4},
]

TEAM_SLUG_MAP = {
    'Arsenal': 'arsenal',
    'Chelsea': 'chelsea',
    'Liverpool': 'liverpool',
    'Manchester City': 'manchester-city',
    'Manchester United': 'manchester-united',
    'Tottenham': 'tottenham-hotspur',
    'Newcastle': 'newcastle-united',
    'Aston Villa': 'aston-villa',
    'Brighton': 'brighton-hove-albion',
    'West Ham': 'west-ham-united',
    'Fulham': 'fulham',
    'Brentford': 'brentford',
    'Crystal Palace': 'crystal-palace',
    'Wolves': 'wolverhampton-wanderers',
    'Wolverhampton': 'wolverhampton-wanderers',
    'Everton': 'everton',
    'Leicester': 'leicester-city',
    'Southampton': 'southampton',
    'Ipswich': 'ipswich-town',
    'Nottingham Forest': 'nottingham-forest',
}


def _get_team_slug(name: str) -> str:
    slug = TEAM_SLUG_MAP.get(name)
    if slug:
        return slug
    return name.lower().replace(' ', '-')


def fetch_lineup_premierinjuries(home: str, away: str) -> Dict:
    """Fetches lineup/injury data from premierinjuries.com."""
    result = {'home': [], 'away': [], 'bajas': [], 'source': None}
    try:
        url = "https://www.premierinjuries.com/injury-table.php"
        resp = requests.get(url, headers=HEADERS, timeout=12)
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, 'html.parser')

        home_n = home.lower()
        away_n = away.lower()
        bajas = []

        # Tables by team name headers
        current_team = None
        for el in soup.find_all(['h2', 'h3', 'tr']):
            if el.name in ['h2', 'h3']:
                current_team = el.get_text().lower().strip()
            elif el.name == 'tr' and current_team:
                cells = el.find_all('td')
                if len(cells) >= 2:
                    p_name = cells[0].get_text().strip()
                    status = cells[1].get_text().strip().lower() if len(cells) > 1 else ''
                    if p_name:
                        is_home = home_n[:6] in current_team
                        is_away = away_n[:6] in current_team
                        if 'out' in status or 'doubtful' in status:
                            bajas.append(f"{p_name} ({current_team.title()}, {status})")
                        elif is_home and 'available' in status:
                            result['home'].append(p_name)
                        elif is_away and 'available' in status:
                            result['away'].append(p_name)

        result['bajas'] = bajas
        result['source'] = f"PremierInjuries ({url})"
        result['verification_link'] = url
    except Exception as e:
        print(f"    [PremierInjuries] Error: {e}")

    return result


def fetch_referee_bbcsport(home: str, away: str) -> Optional[Dict]:
    """Fetches match referee from BBC Sport fixture pages."""
    try:
        home_slug = _get_team_slug(home)
        away_slug = _get_team_slug(away)

        # Search BBC Sport for the fixture
        search_url = f"https://www.bbc.co.uk/sport/football/scores-fixtures"
        resp = requests.get(search_url, headers=HEADERS, timeout=12)
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, 'html.parser')

        home_sn = home.lower()[:6]
        away_sn = away.lower()[:6]

        for article in soup.find_all(['article', 'li', 'div'], class_=re.compile(r'fixture|match|game', re.I)):
            text = article.get_text(separator=' ').lower()
            if home_sn in text and away_sn in text:
                link = article.find('a', href=True)
                if link:
                    match_url = link['href']
                    if not match_url.startswith('http'):
                        match_url = f"https://www.bbc.co.uk{match_url}"
                    # Fetch match page
                    resp2 = requests.get(match_url, headers=HEADERS, timeout=12)
                    soup2 = BeautifulSoup(resp2.text, 'html.parser')
                    for el in soup2.find_all(string=re.compile(r'referee', re.I)):
                        parent = el.parent
                        sibling_text = parent.get_text(separator=' ').strip()
                        name = re.sub(r'referee:?\s*', '', sibling_text, flags=re.I).strip()
                        if 1 < len(name.split()) < 5:
                            return {'name': name, 'source': 'BBC Sport', 'verification_link': match_url}

    except Exception as e:
        print(f"    [BBC Sport] Error: {e}")
    return None


class PremierLeagueDataScraper:
    """
    Unified scraper for Premier League lineups and referee.
    Cascade: PremierInjuries → BBC Sport → Fallback Pool
    """

    def fetch_lineup(self, home: str, away: str, match_date: datetime) -> Dict:
        print(f"  [Premier] Fetching lineup: {home} vs {away}")
        result = fetch_lineup_premierinjuries(home, away)
        if result.get('bajas'):
            print(f"    -> PremierInjuries: {len(result['bajas'])} bajas detectadas")
            return result

        return {'home': [], 'away': [], 'bajas': [], 'source': 'Sin datos (requiere JS)', 'verification_link': 'https://www.premierinjuries.com/injury-table.php'}

    def fetch_referee(self, home: str, away: str, match_date: datetime) -> Dict:
        import random
        print(f"  [Premier] Fetching referee: {home} vs {away}")

        ref = fetch_referee_bbcsport(home, away)
        if ref:
            print(f"    -> BBC Sport: {ref['name']}")
            return self._enrich_referee(ref)

        print(f"    -> AVISO: Usando pool de árbitros Premier League.")
        fallback = random.choice(PREMIER_REFEREE_POOL)
        return {
            'name': fallback['name'],
            'avg_cards': fallback['avg_cards'],
            'source': 'Pool Premier League (fuentes no disponibles)',
            'verification_link': 'https://www.premierleague.com/referees/overview',
            '_is_fallback': True
        }

    def _enrich_referee(self, ref: Dict) -> Dict:
        from src.models.base import RefereeStrictness
        name = ref.get('name', '').lower()
        strict = ['oliver', 'taylor']
        lenient = ['pawson', 'brooks']
        if any(s in name for s in strict):
            ref['strictness'] = RefereeStrictness.HIGH
            ref['avg_cards'] = 5.0
        elif any(s in name for s in lenient):
            ref['strictness'] = RefereeStrictness.LOW
            ref['avg_cards'] = 3.4
        else:
            ref['strictness'] = RefereeStrictness.MEDIUM
            ref['avg_cards'] = 4.1
        ref['_is_fallback'] = False
        return ref
