"""
futbolfantasy_scraper.py — Scraper universal para FutbolFantasy.com
=====================================================================
FutbolFantasy.com publica alineaciones probables (y confirmadas), árbitros
y lesionados para TODAS las grandes ligas:
  - La Liga, Premier League, Serie A, Bundesliga, Ligue 1
  - y partidos de Champions League y Europa League

Estrategia:
  1. Buscar el partido en la sección de posibles alineaciones de la liga
  2. Hacer scraping de la página del partido para obtener:
     - Alineaciones (local y visitante)
     - Árbitro designado
     - Jugadores lesionados / sancionados
"""
import re
import requests
import unicodedata
from bs4 import BeautifulSoup
from typing import Dict, List, Optional, Tuple

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36',
    'Accept-Language': 'es-ES,es;q=0.9,en;q=0.8',
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
}

# URL de alineaciones probables por liga
LEAGUE_LINEUP_URLS = {
    "La Liga":        "https://www.futbolfantasy.com/laliga/posibles-alineaciones",
    "Primera":        "https://www.futbolfantasy.com/laliga/posibles-alineaciones",
    "Premier League": "https://www.futbolfantasy.com/premier/posibles-alineaciones",
    "Premier":        "https://www.futbolfantasy.com/premier/posibles-alineaciones",
    "Serie A":        "https://www.futbolfantasy.com/serie-a/posibles-alineaciones",
    "Bundesliga":     "https://www.futbolfantasy.com/bundesliga/posibles-alineaciones",
    "Ligue 1":        "https://www.futbolfantasy.com/ligue-1/posibles-alineaciones",
    "Champions League": "https://www.futbolfantasy.com/champions/posibles-alineaciones",
    "Europa League":  "https://www.futbolfantasy.com/europa-league/posibles-alineaciones",
}

# Fallback URL global si la liga no tiene página propia
GLOBAL_SEARCH_URL = "https://www.futbolfantasy.com"


def _norm(text: str) -> str:
    """Normaliza texto eliminando acentos y pasando a minúsculas."""
    return "".join(
        c for c in unicodedata.normalize('NFD', text.lower())
        if unicodedata.category(c) != 'Mn'
    ).strip()


def _slug(name: str) -> str:
    """Convierte nombre de equipo en slug para comparar URLs."""
    n = _norm(name)
    n = re.sub(r'\s+', '-', n)
    n = re.sub(r'[^a-z0-9\-]', '', n)
    return n


def _team_matches_url(team_name: str, url_part: str) -> bool:
    """¿El slug del equipo aparece en la URL del partido?"""
    slug = _slug(team_name)
    short = slug.split('-')[0]  # primera palabra del slug
    url_norm = _norm(url_part)
    return slug in url_norm or (len(short) >= 3 and short in url_norm)


def find_match_url(home: str, away: str, league: str) -> Optional[str]:
    """
    Busca la URL del partido en FutbolFantasy para la liga indicada.
    Retorna la URL completa o None si no se encuentra.
    """
    base_url = LEAGUE_LINEUP_URLS.get(league)
    
    # Intentar varias versiones de la URL si la primera da 404
    candidate_urls = []
    if base_url:
        candidate_urls.append(base_url)
    # Siempre probar las URL conocidas como fallback
    for url in LEAGUE_LINEUP_URLS.values():
        if url not in candidate_urls:
            candidate_urls.append(url)

    for try_url in candidate_urls[:3]:  # No probar todas para no hacer muchas peticiones
        try:
            r = requests.get(try_url, headers=HEADERS, timeout=12)
            if r.status_code != 200:
                continue
            soup = BeautifulSoup(r.text, 'html.parser')
        except Exception as e:
            print(f"  [FF] Error accediendo a {try_url}: {e}")
            continue

        # Buscar todos los enlaces que contengan /partidos/
        for a in soup.find_all('a', href=True):
            href = a['href']
            if '/partidos/' not in href:
                continue
            
            home_ok = _team_matches_url(home, href)
            away_ok = _team_matches_url(away, href)
            
            if home_ok and away_ok:
                match_url = href if href.startswith('http') else f"https://www.futbolfantasy.com{href}"
                print(f"  [FF] Partido encontrado: {match_url}")
                return match_url

        # Fallback: buscar por texto del enlace visible
        for a in soup.find_all('a', href=True):
            if '/partidos/' not in a['href']:
                continue
            text = _norm(a.get_text(separator=' '))
            home_short = _slug(home).split('-')[0]
            away_short = _slug(away).split('-')[0]
            if (len(home_short) >= 3 and home_short in text) and (len(away_short) >= 3 and away_short in text):
                match_url = a['href'] if a['href'].startswith('http') else f"https://www.futbolfantasy.com{a['href']}"
                print(f"  [FF] Partido encontrado (por texto): {match_url}")
                return match_url

    print(f"  [FF] Partido no encontrado: {home} vs {away}")
    return None


def scrape_match_page(match_url: str) -> Dict:
    """
    Extrae de la página del partido:
    - Árbitro designado
    - Jugadores titulares (local y visitante)
    - Jugadores lesionados / sancionados
    """
    result = {
        "home": [], "away": [],
        "bajas_home": [], "bajas_away": [],
        "referee": None,
        "source": match_url,
        "verification_link": match_url,
        "_is_fallback": True
    }

    try:
        r = requests.get(match_url, headers=HEADERS, timeout=12)
        r.raise_for_status()
        soup = BeautifulSoup(r.text, 'html.parser')
    except Exception as e:
        print(f"  [FF] Error cargando página del partido: {e}")
        return result

    html = r.text

    # --- 1. ÁRBITRO ---
    arb_patterns = [
        r'[Áá]rbitro[:\s]+([A-ZÁÉÍÓÚÑ][a-záéíóúñ]+(?:\s+[A-ZÁÉÍÓÚÑ][a-záéíóúñ]+){1,3})',
        r'rbitro no asignado',
    ]
    for pattern in arb_patterns:
        m = re.search(pattern, html)
        if m:
            if 'no asignado' not in m.group(0).lower():
                ref_name = m.group(1).strip() if m.lastindex else None
                if ref_name:
                    result["referee"] = ref_name
                    print(f"  [FF] Árbitro: {ref_name}")
            else:
                print(f"  [FF] Árbitro no asignado aún")
            break

    # --- 2. ALINEACIONES ---
    # Método primario: parsear slugs /jugadores/{slug} del HTML
    # Cada jugador aparece en el HTML referenciado dentro de su equipo
    # Buscamos los nombres directamente por el slug o por las secciones
    
    # Encontrar secciones de equipo por wrapppers  
    local_players = []
    visit_players = []

    team_wrappers = soup.find_all(class_=re.compile(r'alineacion_superwrapper|alineacion_wrapper|puntos-equipo', re.I))

    if len(team_wrappers) >= 2:
        for i, wrapper in enumerate(team_wrappers[:2]):
            players = _extract_players_from_section(wrapper)
            if i == 0:
                local_players = players[:11]
            else:
                visit_players = players[:11]

    # Método secundario: extraer desde slugs /jugadores/ y capitalizar
    # Los slugs aparecen en grupos: ~22 titulares + suplentes + resto
    if len(local_players) < 7 or len(visit_players) < 7:
        # Extraer nombres desde slugs de forma determinista
        # Los primeros grupos de jugadores son los titulares del local y visitor
        slug_pattern = re.compile(r'/jugadores/([a-z][a-z0-9\-]{2,})')
        all_slugs = slug_pattern.findall(html)
        
        # Deduplicar manteniendo orden de primera aparición
        seen = set()
        unique_slugs = []
        for s in all_slugs:
            if s not in seen:
                seen.add(s)
                unique_slugs.append(s)
        
        # Convertir slugs a nombres legibles
        def slug_to_name(s: str) -> str:
            parts = s.replace('-', ' ').split()
            # Mayúscula initial por palabra, manejar apellidos compuestos
            return ' '.join(p.capitalize() for p in parts)
        
        names = [slug_to_name(s) for s in unique_slugs if len(s) > 4]
        # Filtrar nombres plausibles (al menos 2 palabras ó nombre conocido corto)
        names = [n for n in names if ' ' in n or len(n.replace(' ', '')) > 6]
        
        if not local_players and len(names) >= 11:
            local_players = names[:11]
        if not visit_players and len(names) >= 22:
            visit_players = names[11:22]
        elif not visit_players and len(names) > 11:
            visit_players = names[11:min(22, len(names))]

    if local_players or visit_players:
        result["home"] = local_players
        result["away"] = visit_players
        result["_is_fallback"] = False
        print(f"  [FF] Alineaciones: {len(local_players)} local, {len(visit_players)} visitante")

    # --- 3. BAJAS / LESIONADOS ---
    baja_links = soup.find_all('a', href=re.compile(r'parte-medico|sancionado|lesion'), string=True)
    for link in baja_links[:6]:
        name = link.get_text().strip()
        if len(name.split()) >= 2:
            result["bajas_home"].append(name)

    return result


def _extract_players_from_section(section) -> List[str]:
    """Extrae nombres de jugadores de una sección de alineación."""
    players = []
    for el in section.find_all(class_=re.compile(r'jugador|juggador|player|nombre', re.I)):
        if 'entrenador' in str(el.get('class', [])) or 'coach' in str(el.get('class', [])):
            continue
        name_span = el.find('span')
        raw = name_span.get_text() if name_span else el.get_text()
        name = _clean_player_name(raw)
        if name:
            players.append(name)
    return list(dict.fromkeys(players))


def _clean_player_name(raw: str) -> Optional[str]:
    """Limpia el texto crudo de un elemento de jugador."""
    name = raw.strip()
    name = re.sub(r'[\d:/]+$', '', name).strip()
    name = re.sub(r'\s+', ' ', name)
    if name and 3 <= len(name) <= 35 and not name.isdigit():
        parts = name.split()
        if 1 <= len(parts) <= 4:
            return name
    return None


def fetch_lineup_and_referee(home: str, away: str, league: str) -> Dict:
    """
    Función principal: busca el partido en FutbolFantasy y extrae
    alineaciones, árbitro y bajas.
    """
    match_url = find_match_url(home, away, league)
    if not match_url:
        return {
            "home": [], "away": [], "bajas": [],
            "referee": None,
            "source": "FutbolFantasy (partido no encontrado)",
            "verification_link": LEAGUE_LINEUP_URLS.get(league, "https://www.futbolfantasy.com"),
            "_is_fallback": True
        }

    data = scrape_match_page(match_url)
    data["bajas"] = data.get("bajas_home", []) + data.get("bajas_away", [])
    return data
