"""
Bundesliga Data Scraper
Cascade: Kicker.de (JS) → DFB → Fallback Pool

Sources:
- Lineups:  https://www.kicker.de/bundesliga/aufstellungen
- Referee:  https://www.dfb.de/schiedsrichter/ansetzungen/
- Fallback: Resultados-Futbol, Kicker
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
    urls = [
        "https://www.dfb.de/schiedsrichter/ansetzungen/",
        "https://datencenter.dfb.de/schiedsrichter-ansetzungen"
    ]
    for url in urls:
        try:
            resp = requests.get(url, headers=HEADERS, timeout=12)
            resp.raise_for_status()
            soup = BeautifulSoup(resp.text, 'html.parser')
            text = soup.get_text(separator=' ')
            
            # Improved keyword extraction: take the most significant name part
            def get_kw(name):
                parts = name.lower().replace("bayer ", "").replace("mainz ", "").replace("04", "").replace("05", "").split()
                return parts[0] if parts else name.lower().split()[0]
                
            home_kw = get_kw(home)
            away_kw = get_kw(away)
            
            pattern = rf'{home_kw}.{{0,100}}{away_kw}.{{0,300}}?([A-ZÁÉÍÓÚ][a-záéíóú]+(?:\s[A-ZÁÉÍÓÚ][a-záéíóú]+){{1,3}})'
            m = re.search(pattern, text, re.IGNORECASE | re.DOTALL)
            if m:
                return {'name': m.group(1).strip(), 'source': 'DFB Oficial', 'verification_link': url}
        except Exception as e:
            print(f"    [DFB] Error scraping {url}: {e}")
    return None


def fetch_referee_rf(home: str, away: str) -> Optional[Dict]:
    """
    Scrapes 'resultados-futbol.com' for Bundesliga referee assignments.
    """
    try:
        url = "https://www.resultados-futbol.com/bundesliga"
        resp = requests.get(url, headers=HEADERS, timeout=12)
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, 'html.parser')

        # Refined keyword matching
        home_kw = home.lower().split()[0]
        away_kw = away.lower().split()[0]
        if "leverkusen" in home.lower(): home_kw = "leverkusen"
        if "mainz" in away.lower(): away_kw = "mainz"

        match_link = None
        for a in soup.find_all('a', href=True):
            href = a['href'].lower()
            if '/partido/' in href and home_kw in href and away_kw in href:
                match_link = a['href']
                break

        if not match_link:
            return None

        m_url = match_link if match_link.startswith('http') else "https://www.resultados-futbol.com" + match_link
        resp2 = requests.get(m_url, headers=HEADERS, timeout=12)
        soup2 = BeautifulSoup(resp2.text, 'html.parser')

        for rt in soup2.find_all(string=re.compile(r'(?i)arbitro|árbitro')):
            text = rt.parent.parent.get_text(separator=' ', strip=True)
            if 'principal' in text.lower():
                name_part = text.split('principal')[-1].strip()
                return {'name': name_part, 'source': 'Resultados-Futbol', 'verification_link': m_url}
    except Exception as e:
        print(f"    [RF Bundesliga] Error: {e}")
    return None


def fetch_referee_kicker(home: str, away: str) -> Optional[Dict]:
    """
    Scrapes 'kicker.de' match pages for referee assignments.
    """
    try:
        url = "https://www.kicker.de/bundesliga/aufstellungen"
        resp = requests.get(url, headers=HEADERS, timeout=12)
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, 'html.parser')

        home_kw = home.lower().split()[0]
        away_kw = away.lower().split()[0]
        if "leverkusen" in home.lower(): home_kw = "leverkusen"

        match_link = None
        for a in soup.find_all('a', href=True):
            href = a['href'].lower()
            if ('analyse' in href or 'direkt' in href) and home_kw in href and away_kw in href:
                match_link = a['href']
                break

        if not match_link:
            return None

        m_url = match_link if match_link.startswith('http') else "https://www.kicker.de" + match_link
        resp2 = requests.get(m_url, headers=HEADERS, timeout=12)
        soup2 = BeautifulSoup(resp2.text, 'html.parser')

        for rt in soup2.find_all(string=re.compile(r'(?i)schiedsrichter')):
            parent = rt.parent.parent
            text = parent.get_text(separator=' ', strip=True)
            # Example: "Schiedsrichter Tobias Stieler (Hamburg)"
            name_match = re.search(r'Schiedsrichter\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+)+)', text)
            if name_match:
                return {'name': name_match.group(1).strip(), 'source': 'Kicker.de', 'verification_link': m_url}
    except Exception as e:
        print(f"    [Kicker Referee] Error: {e}")
    return None


class BundesligaDataScraper:
    """Unified scraper for Bundesliga. Cascade: DFB → RF → Kicker → Fallback Pool."""

    def fetch_lineup(self, home: str, away: str, match_date: datetime) -> Dict:
        print(f"  [Bundesliga] Fetching lineup: {home} vs {away}")
        result = fetch_lineup_kicker(home, away)
        if result['home'] or result['away']:
            return result
        return {'home': [], 'away': [], 'bajas': [], 'source': 'Sin datos Bundesliga', 'verification_link': 'https://www.kicker.de/bundesliga/aufstellungen'}

    def fetch_referee(self, home: str, away: str, match_date: datetime) -> Dict:
        import random
        print(f"  [Bundesliga] Fetching referee: {home} vs {away}")
        
        # 1. DFB Official
        ref = fetch_referee_dfb(home, away)
        if ref: return self._enrich_referee(ref)
        
        # 2. Resultados-Futbol
        ref = fetch_referee_rf(home, away)
        if ref: return self._enrich_referee(ref)
        
        # 3. Kicker
        ref = fetch_referee_kicker(home, away)
        if ref: return self._enrich_referee(ref)
        
        # 4. Fallback Pool
        fallback = random.choice(BUNDESLIGA_REFEREE_POOL)
        return {'name': fallback['name'], 'avg_cards': fallback['avg_cards'],
                'source': 'Pool Bundesliga', 'verification_link': 'https://www.dfb.de/schiedsrichter/ansetzungen/', '_is_fallback': True}

    def _enrich_referee(self, ref: Dict) -> Dict:
        from src.models.base import RefereeStrictness
        name = ref.get('name', '').lower()
        ref['strictness'] = RefereeStrictness.HIGH if 'brych' in name or 'aytekin' in name else RefereeStrictness.MEDIUM
        ref['avg_cards'] = 4.8 if ref['strictness'] == RefereeStrictness.HIGH else 3.9
        ref['_is_fallback'] = False
        return ref
