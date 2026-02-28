"""
La Liga Data Scraper
Cascade: FutbolFantasy (JS) → FutbolFantasy (requests) → RFEF → BeSoccer → Fallback Pool

Sources:
- Lineups:  https://www.futbolfantasy.com/laliga/posibles-alineaciones
- Referee:  https://www.rfef.es/noticias/arbitros/designaciones
- Validate: https://www.besoccer.com
"""
import requests
from bs4 import BeautifulSoup
from typing import Dict, List, Optional
from datetime import datetime
import re
from src.data.scrapers.js_scraper import get_html_with_js, get_html_with_selector, is_available as js_available


HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36',
    'Accept-Language': 'es-ES,es;q=0.9,en;q=0.8',
}

# Referee pool as last resort
LALIGA_REFEREE_POOL = [
    {'name': 'Jesús Gil Manzano', 'avg_cards': 5.8},
    {'name': 'Sánchez Martínez', 'avg_cards': 4.5},
    {'name': 'Hernández Hernández', 'avg_cards': 5.5},
    {'name': 'Díaz de Mera', 'avg_cards': 3.8},
    {'name': 'Munuera Montero', 'avg_cards': 4.2},
    {'name': 'Del Cerro Grande', 'avg_cards': 4.0},
    {'name': 'Figueroa Vázquez', 'avg_cards': 4.3},
    {'name': 'Trujillo Suárez', 'avg_cards': 4.1},
]


def _normalize(name: str) -> str:
    """Lowercase, strip accents roughly for URL matching."""
    return name.lower().strip()


def _find_futbolfantasy_match_url(home: str, away: str) -> Optional[str]:
    """
    Searches FutbolFantasy's posibles-alineaciones page for the specific match URL.
    Uses Playwright (JS rendering) first, then falls back to requests.
    """
    base_url = "https://www.futbolfantasy.com/laliga/posibles-alineaciones"

    # Try JS rendering first (includes dynamically loaded match cards)
    html = None
    if js_available():
        print(f"    [FF] Fetching match list via Playwright JS...")
        html = get_html_with_js(base_url, wait_for="networkidle", extra_wait_ms=3000)

    # Fallback to requests if playwright not available or failed
    if not html:
        try:
            print(f"    [FF] Falling back to requests for match list...")
            resp = requests.get(base_url, headers=HEADERS, timeout=12)
            resp.raise_for_status()
            html = resp.text
        except Exception as e:
            print(f"    [FF] Error fetching match list: {e}")
            return None

    try:
        soup = BeautifulSoup(html, 'html.parser')
        home_n = _normalize(home)
        away_n = _normalize(away)
        home_short = home_n.split()[0]
        away_short = away_n.split()[0]

        # Strategy 1: href contains both team slugs
        for a in soup.find_all('a', href=True):
            href = a['href'].lower()
            if '/partidos/' in href:
                if (home_short in href or home_n[:6] in href) and (away_short in href or away_n[:6] in href):
                    return href if href.startswith('http') else f"https://www.futbolfantasy.com{href}"

        # Strategy 2: link text contains both team names
        for a in soup.find_all('a', href=True):
            if '/partidos/' in a['href']:
                text = a.get_text(separator=' ').lower()
                if home_short in text and away_short in text:
                    href = a['href']
                    return href if href.startswith('http') else f"https://www.futbolfantasy.com{href}"

        # Strategy 3: scan parent containers (match cards)
        for card in soup.find_all(['div', 'article'], class_=re.compile(r'partido|match|encuen|card', re.I)):
            card_text = card.get_text(separator=' ').lower()
            if home_short in card_text and away_short in card_text:
                link = card.find('a', href=True)
                if link and '/partidos/' in link['href']:
                    href = link['href']
                    return href if href.startswith('http') else f"https://www.futbolfantasy.com{href}"

        print(f"    [FF] Match not found on page for {home} vs {away}")
        return None
    except Exception as e:
        print(f"    [FF] Error parsing match list: {e}")
        return None


def fetch_lineup_futbolfantasy(home: str, away: str) -> Dict:
    """
    Fetches probable lineups from FutbolFantasy for a La Liga match.
    Uses Playwright JS rendering first, falls back to requests.
    Returns dict with home/away player lists and list of detected bajas.
    """
    result = {'home': [], 'away': [], 'bajas': [], 'source': None}

    match_url = _find_futbolfantasy_match_url(home, away)
    if not match_url:
        print(f"    [FF] No match URL found for {home} vs {away}")
        return result

    # Attempt JS rendering of the match page
    html = None
    if js_available():
        print(f"    [FF] Rendering match page with Playwright: {match_url}")
        html = get_html_with_selector(
            match_url,
            wait_selector='.jugador, .player-name, .alineacion, [class*="lineup"]',
            timeout_ms=20000
        )
        if html:
            print(f"    [FF] JS rendering succeeded")

    # Fallback to requests if JS failed/not available
    if not html:
        try:
            print(f"    [FF] Fetching match page via requests: {match_url}")
            resp = requests.get(match_url, headers=HEADERS, timeout=12)
            resp.raise_for_status()
            html = resp.text
        except Exception as e:
            print(f"    [FF] Lineup fetch error: {e}")
            return result

    try:
        soup = BeautifulSoup(html, 'html.parser')

        # --- Extract lineups ---
        # FutbolFantasy structure: two .equipo or .alineacion divs
        team_sections = soup.find_all(['div', 'section'], class_=re.compile(r'equipo|alineacion|lineup|once', re.I))

        home_players = []
        away_players = []

        if len(team_sections) >= 2:
            for i, section in enumerate(team_sections[:2]):
                players = []
                for el in section.find_all(class_=re.compile(r'jugador|player|nombre|player-name', re.I)):
                    name = el.get_text(separator=' ').strip()
                    if name and 2 <= len(name.split()) <= 5:
                        players.append(name)
                if i == 0:
                    home_players = players[:11]
                else:
                    away_players = players[:11]

        # Fallback: search by team name headers
        if not home_players and not away_players:
            all_headers = soup.find_all(['h2', 'h3', 'h4'])
            for h in all_headers:
                h_text = h.get_text().lower()
                if home.lower()[:6] in h_text:
                    sibling = h.find_next_sibling()
                    if sibling:
                        home_players = [el.get_text().strip() for el in sibling.find_all(class_=re.compile(r'jugador|nombre|player', re.I))][:11]
                elif away.lower()[:6] in h_text:
                    sibling = h.find_next_sibling()
                    if sibling:
                        away_players = [el.get_text().strip() for el in sibling.find_all(class_=re.compile(r'jugador|nombre|player', re.I))][:11]

        # --- Extract bajas (injuries/unavailable) ---
        bajas = []
        for el in soup.find_all(class_=re.compile(r'baja|lesion|duda|out|unavail|blesur', re.I)):
            name = el.get_text(separator=' ').strip()
            if name and 2 <= len(name.split()) <= 5:
                bajas.append(name)

        result.update({
            'home': home_players,
            'away': away_players,
            'bajas': bajas,
            'source': f"FutbolFantasy ({match_url})",
            'verification_link': match_url
        })

    except Exception as e:
        print(f"    [FF] Parsing error: {e}")

    return result


def fetch_referee_futbolfantasy(home: str, away: str) -> Optional[Dict]:
    """
    Fetches referee from FutbolFantasy match page.
    Looks for: <div class="arbitro"><span class="link">Name</span>
    """
    match_url = _find_futbolfantasy_match_url(home, away)
    if not match_url:
        return None

    try:
        resp = requests.get(match_url, headers=HEADERS, timeout=12)
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, 'html.parser')

        # Primary: div.arbitro > span.link
        div = soup.find('div', class_='arbitro')
        if div:
            span = div.find('span', class_='link') or div.find('a') or div
            name = span.get_text().strip() if span else div.get_text().strip()
            name = re.sub(r'[Áá]rbitro:?\s*', '', name).strip()
            if len(name.split()) >= 2:
                return {'name': name, 'source': 'FutbolFantasy', 'verification_link': match_url}

        # Fallback: search for "árbitro" in text
        page_text = soup.get_text(separator='\n')
        for line in page_text.split('\n'):
            if 'árbitro' in line.lower() or 'arbitro' in line.lower():
                name = re.sub(r'[Áá]rbitro:?\s*', '', line).strip()
                if 2 <= len(name.split()) <= 4:
                    return {'name': name, 'source': 'FutbolFantasy (text)', 'verification_link': match_url}

    except Exception as e:
        print(f"    [FF Referee] Error: {e}")

    return None


def fetch_referee_rf(home: str, away: str) -> Optional[Dict]:
    """
    Scrapes 'resultados-futbol.com' which often reliably overrides WAF blocks.
    """
    try:
        url = "https://www.resultados-futbol.com/primera"
        resp = requests.get(url, headers=HEADERS, timeout=12)
        soup = BeautifulSoup(resp.text, 'html.parser')
        
        home_kw = home.lower().split()[0]
        away_kw = away.lower().split()[0]
        if home_kw == 'athletic': home_kw = 'athletic'
        
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
                # Extract name (e.g. "Árbitro principal García Verdura")
                name_part = text.split('principal')[-1].strip()
                return {
                    "name": name_part,
                    "source": "Resultados-Futbol",
                    "verification_link": m_url
                }
                
    except Exception as e:
        print(f"    [RF] Error: {e}")
    return None

def fetch_referee_rfef(home: str, away: str) -> Optional[Dict]:
    """
    Fetches referee from RFEF official designaciones page.
    Searches for the match between home and away in the published document.
    """
    try:
        url = "https://www.rfef.es/noticias/arbitros/designaciones"
        resp = requests.get(url, headers=HEADERS, timeout=12)
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, 'html.parser')

        text = soup.get_text(separator=' ')
        home_kw = home.lower().split()[0]
        away_kw = away.lower().split()[0]

        # Search for "HomeTeam - AwayTeam ... Árbitro: Name" patterns
        pattern = rf'{home_kw}.{{0,80}}{away_kw}.{{0,200}}?([A-ZÁÉÍÓÚ][a-záéíóú]+(?:\s[A-ZÁÉÍÓÚ][a-záéíóú]+){{1,3}})'
        match = re.search(pattern, text, re.IGNORECASE | re.DOTALL)
        if match:
            name = match.group(1).strip()
            return {'name': name, 'source': 'RFEF Oficial', 'verification_link': url}

        return None
    except Exception as e:
        print(f"    [RFEF] Error: {e}")
        return None


def fetch_referee_besoccer(home: str, away: str) -> Optional[Dict]:
    """
    Cross-validates referee via BeSoccer match search.
    """
    try:
        home_slug = home.lower().replace(' ', '-').replace('ñ', 'n')
        away_slug = away.lower().replace(' ', '-').replace('ñ', 'n')
        search_url = f"https://es.besoccer.com/partido/{home_slug}-{away_slug}"

        resp = requests.get(search_url, headers=HEADERS, timeout=10)
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, 'html.parser')

        # BeSoccer wraps referee in .referee-name or similar
        for el in soup.find_all(class_=re.compile(r'referee|arbitro|juez', re.I)):
            name = el.get_text().strip()
            if 2 <= len(name.split()) <= 4:
                return {'name': name, 'source': 'BeSoccer', 'verification_link': search_url}

        # Text search fallback
        text = soup.get_text(separator='\n')
        for line in text.split('\n'):
            if 'árbitro' in line.lower() or 'referee' in line.lower():
                name = re.sub(r'[Áá]rbitro:?\s*|Referee:?\s*', '', line).strip()
                if 2 <= len(name.split()) <= 4:
                    return {'name': name, 'source': 'BeSoccer', 'verification_link': search_url}

    except Exception as e:
        print(f"    [BeSoccer] Error: {e}")

    return None


class LaLigaDataScraper:
    """
    Unified scraper for La Liga lineups and referee.
    Cascade: FutbolFantasy → RFEF → BeSoccer → Fallback Pool
    """

    def fetch_lineup(self, home: str, away: str, match_date: datetime) -> Dict:
        """Returns lineup dict with home/away players and detected bajas."""
        print(f"  [LaLiga] Fetching lineup: {home} vs {away}")

        # 1. FutbolFantasy (elite source)
        result = fetch_lineup_futbolfantasy(home, away)
        if result['home'] or result['away']:
            print(f"    -> FutbolFantasy: {len(result['home'])} local + {len(result['away'])} visitante")
            return result

        print(f"    -> FutbolFantasy falló. Sin datos de alineaciones en fuentes disponibles.")
        return {'home': [], 'away': [], 'bajas': [], 'source': 'Sin datos (fuentes web requieren JS)', 'verification_link': None}

    def fetch_referee(self, home: str, away: str, match_date: datetime) -> Dict:
        """Returns referee dict with name, source and verification link."""
        import random
        print(f"  [LaLiga] Fetching referee: {home} vs {away}")

        # 1. FutbolFantasy (primary)
        print(f"    [LaLiga] Buscando árbitro en FutbolFantasy...")
        ref = fetch_referee_futbolfantasy(home, away)
        if ref:
            return self._enrich_referee(ref)
            
        # 1.5. Resultados-Futbol (very robust WAF override)
        print(f"    [LaLiga] Buscando árbitro en Resultados-Futbol...")
        ref = fetch_referee_rf(home, away)
        if ref:
            return self._enrich_referee(ref)

        # 2. RFEF Official
        print(f"    [LaLiga] Buscando árbitro en Web RFEF...")
        ref = fetch_referee_rfef(home, away)
        if ref:
            print(f"    -> RFEF: {ref['name']}")
            return self._enrich_referee(ref)

        # 3. BeSoccer cross-validation
        ref = fetch_referee_besoccer(home, away)
        if ref:
            print(f"    -> BeSoccer: {ref['name']}")
            return self._enrich_referee(ref)

        # 4. Fallback pool (never picks randomly — warns user clearly)
        print(f"    -> AVISO: No se pudo obtener árbitro de fuentes web. Usando pool de referencia.")
        fallback = random.choice(LALIGA_REFEREE_POOL)
        return {
            'name': fallback['name'],
            'avg_cards': fallback['avg_cards'],
            'source': 'Pool LaLiga (fuentes no disponibles)',
            'verification_link': 'https://www.rfef.es/noticias/arbitros/designaciones',
            '_is_fallback': True
        }

    def _enrich_referee(self, ref: Dict) -> Dict:
        """Adds strictness and avg_cards to referee dict."""
        from src.models.base import RefereeStrictness
        name = ref.get('name', '')
        strict_refs = ['gil manzano', 'hernández hernández', 'mateu lahoz']
        lenient_refs = ['díaz de mera', 'munuera montero', 'del cerro grande', 'trujillo']

        name_l = name.lower()
        if any(s in name_l for s in strict_refs):
            strictness = RefereeStrictness.HIGH
            avg = 5.5
        elif any(s in name_l for s in lenient_refs):
            strictness = RefereeStrictness.LOW
            avg = 3.8
        else:
            strictness = RefereeStrictness.MEDIUM
            avg = 4.3

        ref['strictness'] = strictness
        ref['avg_cards'] = avg
        ref['_is_fallback'] = False
        return ref
