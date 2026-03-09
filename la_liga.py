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

        # Target the superwrappers OR the main alineacion section
        team_sections = soup.find_all(class_=re.compile(r'alineacion_superwrapper|alineacion_wrapper|puntos-equipo', re.I))
        
        # If not found, fall back to general sections but filter those that actually contain players
        if len(team_sections) < 2:
            all_candidates = soup.find_all(['div', 'section'], class_=re.compile(r'equipo|alineacion|lineup|once|field|pitch|puntos', re.I))
            team_sections = [s for s in all_candidates if len(s.find_all(class_=re.compile(r'jugador|juggador', re.I))) >= 5]

        home_players = []
        away_players = []

        if len(team_sections) >= 2:
            # Sort by local/visitante class if available
            local_sec = next((s for s in team_sections if 'local' in s.get('class', [])), team_sections[0])
            visit_sec = next((s for s in team_sections if 'visitante' in s.get('class', [])), team_sections[1])
            
            for i, section in enumerate([local_sec, visit_sec]):
                players = []
                # Use a more specific selector to avoid extra noise (like points or staff)
                # Usually name is in the first span or just the direct text of .juggador
                for el in section.find_all(class_=re.compile(r'jugador|juggador|player|nombre', re.I)):
                    # Skip coaches/staff
                    if 'entrenador' in str(el.get('class', [])) or 'coach' in str(el.get('class', [])):
                        continue
                        
                    # Get clean name from first span if possible, else text
                    name_span = el.find('span')
                    name = name_span.get_text().strip() if name_span else el.get_text().strip()
                    
                    # Clean up
                    name = re.sub(r'[:\d/]+$', '', name).strip() # Remove trailing points ": 3" etc
                    if name and 3 <= len(name) <= 30 and name.lower() not in [home.lower(), away.lower()]:
                        if not name.isdigit() and len(name.split()) <= 4:
                            players.append(name)
                
                players = list(dict.fromkeys(players))
                if i == 0:
                    home_players = players[:11]
                else:
                    away_players = players[:11]
        
        # FINAL GLOBAL FALLBACK: If above failed, get all players and split
        if len(home_players) < 5 or len(away_players) < 5:
            all_player_els = soup.find_all(class_=re.compile(r'^juggador$|^jugador$', re.I))
            all_names = []
            for el in all_player_els:
                name_span = el.find('span')
                name = name_span.get_text().strip() if name_span else el.get_text().strip()
                name = re.sub(r'[:\d/]+$', '', name).strip()
                if name and 3 <= len(name) <= 30 and name.lower() not in [home.lower(), away.lower()]:
                    all_names.append(name)
            
            all_names = list(dict.fromkeys(all_names))
            if len(all_names) >= 22:
                home_players = all_names[:11]
                away_players = all_names[11:22]
            elif len(all_names) >= 11:
                home_players = all_names[:11]
                away_players = []

        # GLOBAL FALLBACK: If sections didn't yield enough players, search the whole page
        if len(home_players) < 5 or len(away_players) < 5:
            print(f"    [FF] Section search failed (H:{len(home_players)}, A:{len(away_players)}). Trying global search...")
            all_player_els = soup.find_all(['a', 'span'], class_=re.compile(r'juggador|jugador|player-name', re.I))
            all_names = []
            for el in all_player_els:
                name = el.get_text().strip()
                if name and 1 <= len(name.split()) <= 4 and name.lower() not in [home.lower(), away.lower()]:
                    all_names.append(name)
            
            # Deduplicate
            all_names = list(dict.fromkeys(all_names))
            
            if len(all_names) >= 22:
                # In most match pages, home is first 11, away is next 11
                home_players = all_names[:11]
                away_players = all_names[11:22]
            elif len(all_names) >= 11:
                # Maybe only one team found or mixed. Try to use previous results or just take half
                mid = len(all_names) // 2
                home_players = all_names[:mid]
                away_players = all_names[mid:]

        # Fallback 1: Search by team name headers (Probables view)
        if len(home_players) < 5 and len(away_players) < 5:
            all_headers = soup.find_all(['h2', 'h3', 'h4'])
            for h in all_headers:
                h_text = h.get_text().lower()
                if home.lower()[:6] in h_text:
                    sibling = h.find_next_sibling()
                    if sibling:
                        home_players = [el.get_text().strip() for el in sibling.find_all(class_=re.compile(r'jugador|juggador|nombre|player', re.I)) if 1 <= len(el.get_text().strip().split()) <= 5][:11]
                elif away.lower()[:6] in h_text:
                    sibling = h.find_next_sibling()
                    if sibling:
                        away_players = [el.get_text().strip() for el in sibling.find_all(class_=re.compile(r'jugador|juggador|nombre|player', re.I)) if 1 <= len(el.get_text().strip().split()) <= 5][:11]

        # Fallback 2: Search for "Titulares" in live points tables (found in screenshots)
        if len(home_players) < 5 or len(away_players) < 5:
            titulares_headers = soup.find_all(string=re.compile(r'Titulares', re.I))
            for th in titulares_headers:
                parent_table = th.find_parent('table') or th.find_parent('div', class_=re.compile(r'table|list', re.I))
                if parent_table:
                    # Determine which team this table belongs to by looking at nearby headers
                    context_text = parent_table.get_text(separator=' ').lower()
                    identified_players = []
                    for name_el in parent_table.find_all(class_=re.compile(r'jugador|juggador|nombre|player', re.I)):
                        p_name = name_el.get_text().strip()
                        if p_name and 1 <= len(p_name.split()) <= 5 and p_name.lower() not in [home.lower(), away.lower()]:
                            identified_players.append(p_name)
                    
                    if not identified_players:
                        # Sometimes names are inside spans/links without specific classes in simple tables
                        for row in parent_table.find_all('tr'):
                            cells = row.find_all('td')
                            if cells:
                                for cell in cells:
                                    txt = cell.get_text().strip()
                                    if 1 <= len(txt.split()) <= 4 and txt.lower() not in [home.lower(), away.lower()]:
                                        identified_players.append(txt)
                                        break
                    
                    identified_players = list(dict.fromkeys(identified_players))

                    if home.lower()[:5] in context_text and not home_players:
                        home_players = identified_players[:11]
                    elif away.lower()[:5] in context_text and not away_players:
                        away_players = identified_players[:11]

        # --- Extract bajas (injuries/unavailable) ---
        bajas = []
        for el in soup.find_all(class_=re.compile(r'baja|lesion|duda|out|unavail|blesur', re.I)):
            name = el.get_text(separator=' ').strip()
            if name and 1 <= len(name.split()) <= 5:
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


def fetch_lineup_rf(home: str, away: str) -> Dict:
    """
    Fetches lineups from Resultados-Futbol match page.
    """
    result = {'home': [], 'away': [], 'bajas': [], 'source': None}
    
    try:
        url = "https://www.resultados-futbol.com/primera"
        html = None
        if js_available():
            print(f"    [RF Lineup] Fetching Primera list via JS...")
            html = get_html_with_js(url)
        
        if not html:
            resp = requests.get(url, headers=HEADERS, timeout=12)
            html = resp.text
            
        soup = BeautifulSoup(html, 'html.parser')
        
        home_kw = home.lower().split()[0]
        away_kw = away.lower().split()[0]
        if "rayo" in home.lower(): home_kw = "rayo"
        if "bilbao" in away.lower() or "athletic" in away.lower(): away_kw = "athletic"
        
        match_link = None
        for a in soup.find_all('a', href=True):
            href = a['href'].lower()
            if '/partido/' in href and home_kw in href and away_kw in href:
                match_link = a['href']
                break
                
        if not match_link:
            return result
            
        # RF often has a specific /alineacion tab
        m_url = match_link if match_link.startswith('http') else "https://www.resultados-futbol.com" + match_link
        if not m_url.endswith('/alineacion'):
            m_url = m_url.replace('/partido/', '/partido/') # stay same
            # We can try to append /alineacion or just use the main match page which often has it
            l_url = m_url if '/alineacion' in m_url else f"{m_url}/alineacion"
        else:
            l_url = m_url

        l_html = None
        if js_available():
            print(f"    [RF Lineup] Rendering lineup page via JS: {l_url}")
            # Use a longer timeout for lineups and wait for load
            l_html = get_html_with_js(l_url, wait_for="load", timeout_ms=30000, extra_wait_ms=5000)
            
        if not l_html:
            resp2 = requests.get(l_url, headers=HEADERS, timeout=15)
            l_html = resp2.text
            
        soup2 = BeautifulSoup(l_html, 'html.parser')
        
        # Based on browser research: table with id alineacion_inicial or class desc-partido
        home_players = []
        away_players = []
        
        # Strategy A: id-based (Alineación Inicial table)
        init_table = soup2.find(id='alineacion_inicial') or soup2.find('div', id='alineacion_inicial')
        if not init_table:
            # Try finding any table with 'Alineación Inicial' in it
            for t in soup2.find_all('table'):
                if 'alineación inicial' in t.get_text().lower():
                    init_table = t
                    break
        
        if init_table:
            rows = init_table.find_all('tr')
            for row in rows:
                # Check for two columns of players (nombre or equipo class)
                names_in_row = row.find_all(['td', 'th', 'a'], class_=re.compile(r'nombre|jugador|equipo|player', re.I))
                if not names_in_row:
                    # Try links directly
                    names_in_row = row.find_all('a', href=re.compile(r'/jugador/'))
                
                if len(names_in_row) >= 2:
                    h_name = names_in_row[0].get_text().strip()
                    a_name = names_in_row[1].get_text().strip()
                    if 1 <= len(h_name.split()) <= 4: home_players.append(h_name)
                    if 1 <= len(a_name.split()) <= 4: away_players.append(a_name)
                elif len(names_in_row) == 1:
                    p_name = names_in_row[0].get_text().strip()
                    if 1 <= len(p_name.split()) <= 4:
                        cls = names_in_row[0].get('class', []) or []
                        parent_cls = names_in_row[0].find_parent('td').get('class', []) if names_in_row[0].find_parent('td') else []
                        all_cls = cls + parent_cls
                        if any('equipo1' in str(c) for c in all_cls):
                            home_players.append(p_name)
                        elif any('equipo2' in str(c) for c in all_cls):
                            away_players.append(p_name)
            
            if len(home_players) < 5 or len(away_players) < 5:
                # Global link search in this specific table
                all_links = init_table.find_all('a', href=re.compile(r'/jugador/'))
                found_names = []
                for a in all_links:
                    name = a.get_text().strip()
                    if name and 1 <= len(name.split()) <= 4 and not name.isdigit():
                        found_names.append(name)
                
                found_names = list(dict.fromkeys(found_names))
                if len(found_names) >= 22:
                    home_players = found_names[:11]
                    away_players = found_names[11:22]
        
        # Strategy B: table class based (older style) or generic search
        if len(home_players) < 8:
            all_tables = soup2.find_all('table')
            for table in all_tables:
                table_text = table.get_text().lower()
                if 'titulares' in table_text or 'alineación' in table_text:
                    h_p = [a.get_text().strip() for a in table.select('td.equipo1 a, td.nombre.equipo1 a, .equipo1 a')]
                    a_p = [a.get_text().strip() for a in table.select('td.equipo2 a, td.nombre.equipo2 a, .equipo2 a')]
                    if len(h_p) >= 8: home_players = h_p[:11]
                    if len(a_p) >= 8: away_players = a_p[:11]
                    if len(home_players) >= 8: break
        
        if len(home_players) >= 5 or len(away_players) >= 5:
            result.update({
                'home': home_players[:11],
                'away': away_players[:11],
                'source': f"Resultados-Futbol ({l_url})",
                'verification_link': l_url
            })
            
    except Exception as e:
        print(f"    [RF Lineup] Error: {e}")
        
    return result


def fetch_referee_futbolfantasy(home: str, away: str) -> Optional[Dict]:
    """
    Fetches referee from FutbolFantasy match page.
    """
    match_url = _find_futbolfantasy_match_url(home, away)
    if not match_url:
        return None

    html = None
    if js_available():
        print(f"    [FF Referee] Rendering match page via JS: {match_url}")
        html = get_html_with_js(match_url)
    
    if not html:
        try:
            resp = requests.get(match_url, headers=HEADERS, timeout=12)
            resp.raise_for_status()
            html = resp.text
        except Exception as e:
            print(f"    [FF Referee] Error: {e}")
            return None

    try:
        soup = BeautifulSoup(html, 'html.parser')
        # Primary: div.arbitro
        div = soup.find('div', class_='arbitro')
        if div:
            span = div.find('span', class_='link') or div.find('a') or div
            name = span.get_text().strip()
            name = re.sub(r'[Áá]rbitro:?\s*', '', name).strip()
            if len(name.split()) >= 2:
                return {'name': name, 'source': 'FutbolFantasy', 'verification_link': match_url}

        # Text search fallback
        page_text = soup.get_text(separator='\n')
        for line in page_text.split('\n'):
            if 'árbitro' in line.lower() or 'arbitro' in line.lower():
                name = re.sub(r'[Áá]rbitro:?\s*', '', line).strip()
                if 2 <= len(name.split()) <= 4:
                    return {'name': name, 'source': 'FutbolFantasy (text)', 'verification_link': match_url}
    except Exception as e:
        print(f"    [FF Referee Parsing] Error: {e}")
    return None


def fetch_referee_rf(home: str, away: str) -> Optional[Dict]:
    """
    Scrapes 'resultados-futbol.com' with JS fallback for cloud environments.
    """
    try:
        url = "https://www.resultados-futbol.com/primera"
        html = None
        if js_available():
            print(f"    [RF] Fetching Primera list via JS...")
            html = get_html_with_js(url)
        
        if not html:
            resp = requests.get(url, headers=HEADERS, timeout=12)
            html = resp.text
            
        soup = BeautifulSoup(html, 'html.parser')
        
        home_kw = home.lower().split()[0]
        away_kw = away.lower().split()[0]
        # Common Spanish team name edge cases
        if "rayo" in home.lower(): home_kw = "rayo"
        if "bilbao" in away.lower() or "athletic" in away.lower(): away_kw = "athletic"
        
        match_link = None
        for a in soup.find_all('a', href=True):
            href = a['href'].lower()
            if '/partido/' in href and home_kw in href and away_kw in href:
                match_link = a['href']
                break
                
        if not match_link:
            return None
            
        m_url = match_link if match_link.startswith('http') else "https://www.resultados-futbol.com" + match_link
        
        m_html = None
        if js_available():
            print(f"    [RF] Rendering match page via JS: {m_url}")
            m_html = get_html_with_js(m_url)
            
        if not m_html:
            resp2 = requests.get(m_url, headers=HEADERS, timeout=12)
            m_html = resp2.text
            
        soup2 = BeautifulSoup(m_html, 'html.parser')
        
        for rt in soup2.find_all(string=re.compile(r'(?i)arbitro|árbitro')):
            text = rt.parent.parent.get_text(separator=' ', strip=True)
            if 'principal' in text.lower():
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


def fetch_referee_designaciones(home: str, away: str) -> Optional[Dict]:
    """
    Scrapes FutbolFantasy's dedicated referee designations page.
    This page publishes ALL weekly referee assignments for La Liga.
    URL: https://www.futbolfantasy.com/laliga/arbitros
    """
    urls_to_try = [
        "https://www.futbolfantasy.com/laliga/arbitros",
        "https://www.futbolfantasy.com/laliga/designaciones-arbitrales",
    ]
    
    home_kw = home.lower().split()[0]
    away_kw = away.lower().split()[0]
    # Edge cases
    if "espanyol" in home.lower() or "español" in home.lower(): home_kw = "espanyol"
    if "celta" in home.lower(): home_kw = "celta"
    if "athletic" in home.lower(): home_kw = "athletic"
    if "oviedo" in away.lower(): away_kw = "oviedo"
    
    for url in urls_to_try:
        try:
            print(f"    [Designaciones] Probando: {url}")
            resp = requests.get(url, headers=HEADERS, timeout=12)
            if resp.status_code != 200:
                continue
            soup = BeautifulSoup(resp.text, 'html.parser')
            text = soup.get_text(separator=' ', strip=True)
            
            # Search for the match in the text
            # Pattern: "Espanyol - Oviedo ... Árbitro: Nombre Apellido"
            lines = text.split('\n')
            for i, line in enumerate(lines):
                line_l = line.lower()
                if home_kw in line_l and away_kw in line_l:
                    # Look in surrounding lines for referee
                    context = ' '.join(lines[max(0,i-2):i+5])
                    m = re.search(r'[Áá]rbitro[:\s]+([A-ZÁÉÍÓÚÑ][a-záéíóúñ]+(?:\s[A-ZÁÉÍÓÚÑ][a-záéíóúñ]+){1,3})', context)
                    if m:
                        name = m.group(1).strip()
                        return {'name': name, 'source': 'FutbolFantasy Designaciones', 'verification_link': url}
            
            # Try structured search: find all referee assignments on page
            for el in soup.find_all(['div', 'li', 'tr', 'p']):
                el_text = el.get_text(separator=' ', strip=True)
                el_lower = el_text.lower()
                if (home_kw in el_lower or away_kw in el_lower):
                    m = re.search(r'[Áá]rbitro[:\s]+([A-ZÁÉÍÓÚÑ][a-záéíóúñ]+(?:\s[A-ZÁÉÍÓÚÑ][a-záéíóúñ]+){1,3})', el_text)
                    if m:
                        name = m.group(1).strip()
                        return {'name': name, 'source': 'FutbolFantasy Designaciones', 'verification_link': url}
        except Exception as e:
            print(f"    [Designaciones] Error en {url}: {e}")
    return None


def fetch_referee_besoccer_v2(home: str, away: str) -> Optional[Dict]:
    """
    Improved BeSoccer scraper with multiple URL formats.
    """
    def slugify(name):
        import unicodedata
        name = unicodedata.normalize('NFD', name)
        name = ''.join(c for c in name if unicodedata.category(c) != 'Mn')
        return name.lower().replace(' ', '-').replace('.', '').replace("'", '')
    
    home_slug = slugify(home)
    away_slug = slugify(away)
    
    urls_to_try = [
        f"https://es.besoccer.com/partido/{home_slug}-{away_slug}",
        f"https://es.besoccer.com/partido/{away_slug}-{home_slug}",
        f"https://www.besoccer.com/match/{home_slug}-{away_slug}",
    ]
    
    for url in urls_to_try:
        try:
            print(f"    [BeSoccer v2] Probando: {url}")
            resp = requests.get(url, headers=HEADERS, timeout=10)
            if resp.status_code != 200:
                continue
            soup = BeautifulSoup(resp.text, 'html.parser')
            
            # Strategy 1: specific class selectors
            for el in soup.find_all(class_=re.compile(r'referee|arbitro|juez|ref-name', re.I)):
                name = el.get_text(separator=' ', strip=True)
                name = re.sub(r'[Áá]rbitro[:\s]*', '', name).strip()
                if 2 <= len(name.split()) <= 4 and not name[0].isdigit():
                    return {'name': name, 'source': 'BeSoccer', 'verification_link': url}
            
            # Strategy 2: text search
            text = soup.get_text(separator='\n')
            for line in text.split('\n'):
                line = line.strip()
                if ('árbitro' in line.lower() or 'arbitro' in line.lower()) and len(line) < 60:
                    name = re.sub(r'[Áá]rbitro[:\s]*', '', line, flags=re.I).strip()
                    if 2 <= len(name.split()) <= 4:
                        return {'name': name, 'source': 'BeSoccer', 'verification_link': url}
        except Exception as e:
            print(f"    [BeSoccer v2] Error: {e}")
    return None


def fetch_referee_sofascore(home: str, away: str) -> Optional[Dict]:
    """
    Fetches referee from SofaScore API (JSON endpoint, no JS needed).
    """
    try:
        # SofaScore has a public search API
        search_query = f"{home} {away}"
        api_url = f"https://api.sofascore.com/api/v1/search/events?q={search_query.replace(' ', '%20')}"
        headers_api = {
            'User-Agent': 'Mozilla/5.0',
            'Accept': 'application/json',
        }
        resp = requests.get(api_url, headers=headers_api, timeout=10)
        if resp.status_code != 200:
            return None
        
        data = resp.json()
        events = data.get('events', [])
        
        for event in events[:5]:
            # Check if it matches our teams
            h_name = event.get('homeTeam', {}).get('name', '').lower()
            a_name = event.get('awayTeam', {}).get('name', '').lower()
            if (home.lower().split()[0] in h_name or h_name in home.lower()) and \
               (away.lower().split()[0] in a_name or a_name in away.lower()):
                event_id = event.get('id')
                if event_id:
                    # Get event details
                    detail_url = f"https://api.sofascore.com/api/v1/event/{event_id}"
                    resp2 = requests.get(detail_url, headers=headers_api, timeout=10)
                    if resp2.status_code == 200:
                        detail = resp2.json()
                        referee = detail.get('event', {}).get('referee', {})
                        ref_name = referee.get('name', '')
                        if ref_name and len(ref_name.split()) >= 2:
                            return {
                                'name': ref_name,
                                'source': 'SofaScore',
                                'verification_link': f"https://www.sofascore.com/es/partido/{event_id}"
                            }
    except Exception as e:
        print(f"    [SofaScore] Error: {e}")
    return None


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

        # 2. Resultados-Futbol (robust backup)
        print(f"    [LaLiga] Buscando alineaciones en Resultados-Futbol...")
        result = fetch_lineup_rf(home, away)
        if result['home'] or result['away']:
            print(f"    -> Resultados-Futbol: {len(result['home'])} local + {len(result['away'])} visitante")
            return result

        print(f"    -> Fuentes fallaron. Sin datos de alineaciones en fuentes disponibles.")
        return {'home': [], 'away': [], 'bajas': [], 'source': 'Sin datos (fuentes web requieren JS)', 'verification_link': None}

    def fetch_referee(self, home: str, away: str, match_date: datetime) -> Dict:
        """Returns referee dict with name, source and verification link.
        Cascade mejorado: Designaciones → SofaScore → FutbolFantasy → RFEF → BeSoccer → Pool
        """
        import random
        print(f"  [LaLiga] Fetching referee: {home} vs {away}")

        # 1. FutbolFantasy Designaciones (página específica de árbitros - MÁS FIABLE)
        print(f"    [LaLiga] Buscando en página de designaciones arbitrales...")
        ref = fetch_referee_designaciones(home, away)
        if ref:
            print(f"    -> Designaciones: {ref['name']}")
            return self._enrich_referee(ref)

        # 2. SofaScore API (JSON directo, sin JS necesario)
        print(f"    [LaLiga] Buscando árbitro en SofaScore API...")
        ref = fetch_referee_sofascore(home, away)
        if ref:
            print(f"    -> SofaScore: {ref['name']}")
            return self._enrich_referee(ref)

        # 3. FutbolFantasy match page
        print(f"    [LaLiga] Buscando árbitro en FutbolFantasy partido...")
        ref = fetch_referee_futbolfantasy(home, away)
        if ref:
            return self._enrich_referee(ref)
            
        # 4. Resultados-Futbol
        print(f"    [LaLiga] Buscando árbitro en Resultados-Futbol...")
        ref = fetch_referee_rf(home, away)
        if ref:
            return self._enrich_referee(ref)

        # 5. RFEF Official
        print(f"    [LaLiga] Buscando árbitro en Web RFEF...")
        ref = fetch_referee_rfef(home, away)
        if ref:
            print(f"    -> RFEF: {ref['name']}")
            return self._enrich_referee(ref)

        # 6. BeSoccer mejorado
        ref = fetch_referee_besoccer_v2(home, away)
        if ref:
            print(f"    -> BeSoccer: {ref['name']}")
            return self._enrich_referee(ref)

        # 7. Fallback pool (determinista por equipos — siempre el mismo en cada recarga)
        print(f"    -> AVISO: No se pudo obtener árbitro de fuentes web. Usando pool de referencia.")
        
        import hashlib
        match_id = f"{home}-{away}-{match_date.strftime('%Y%m%d')}"
        idx = int(hashlib.md5(match_id.encode()).hexdigest(), 16) % len(LALIGA_REFEREE_POOL)
        fallback = LALIGA_REFEREE_POOL[idx]
        
        return {
            'name': fallback['name'],
            'avg_cards': fallback['avg_cards'],
            'source': 'Pool LaLiga (introduce el árbitro manualmente si lo conoces)',
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
