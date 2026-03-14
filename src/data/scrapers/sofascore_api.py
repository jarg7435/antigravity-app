"""
sofascore_api.py — Búsqueda de árbitros y alineaciones
=======================================================
Estrategia multi-fuente (SofaScore API está bloqueado por Cloudflare):
1. Google News RSS (multi-idioma) — fuente principal para árbitros
2. BeSoccer / Marca RSS — fuente secundaria esp. para La Liga
3. Datos de alineación: SofaScore app URL scraping como intento (fallback = DB interna)
"""
import re
import requests
import xml.etree.ElementTree as ET
from datetime import datetime, date, timedelta, timezone
from typing import Optional, Dict, List
import unicodedata


RSS_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    "Accept": "application/rss+xml, application/xml, text/xml, */*",
    "Accept-Language": "es-ES,es;q=0.9",
}

# Alias de nombres de equipos: app (Español/Personalizado) → Nombres internacionales
TEAM_ALIASES = {
    # Bundesliga
    "Bayer Leverkusen":    ["Bayer 04 Leverkusen", "Leverkusen"],
    "Bayern Munich":       ["Bayern München", "FC Bayern München", "FC Bayern", "Bayern de Múnich"],
    "Bayern de Múnich":    ["Bayern München", "FC Bayern München", "FC Bayern", "Bayern Munich"],
    "Dortmund":            ["Borussia Dortmund", "BVB"],
    "RB Leipzig":          ["Rasenballsport Leipzig"],
    "Gladbach":            ["Borussia M'gladbach", "Borussia Mönchengladbach"],
    "Union Berlin":        ["1. FC Union Berlin"],
    "Frankfurt":           ["Eintracht Frankfurt"],
    "Mainz 05":            ["FSV Mainz 05", "Mainz"],
    "Koln":                ["FC Köln", "Cologne", "Köln", "Colonia"],
    "Colonia":             ["FC Köln", "Cologne", "Köln", "Koln"],
    "Hamburgo":            ["Hamburger SV", "HSV"],
    "St. Pauli":           ["FC St. Pauli"],
    "Wolfsburg":           ["VfL Wolfsburg"],
    "Stuttgart":           ["VfB Stuttgart"],
    "Augsburg":            ["FC Augsburg"],
    "Hoffenheim":          ["TSG Hoffenheim", "TSG 1899 Hoffenheim"],
    "Friburgo":            ["Freiburg", "SC Freiburg"],

    # La Liga
    "Atletico Madrid":     ["Atlético Madrid", "Atletico de Madrid", "Atletico"],
    "Atlético Madrid":     ["Atletico Madrid", "Atletico de Madrid", "Atletico"],
    "FC Barcelona":        ["Barcelona"],
    "Sevilla FC":          ["Sevilla"],
    "Celta de Vigo":       ["Celta Vigo", "RC Celta"],
    "Athletic Club":       ["Athletic Bilbao", "Athletic"],
    "Rayo Vallecano":      ["Rayo"],
    "Villarreal":          ["Villarreal CF"],
    "Valencia":            ["Valencia CF"],
    "Betis":               ["Real Betis"],
    "Osasuna":             ["CA Osasuna"],
    "Getafe":              ["Getafe CF"],
    "Sociedad":            ["Real Sociedad"],
    "Girona":              ["Girona FC"],

    # Serie A
    "AC Milan":            ["Milan", "Milán"],
    "Milán":               ["AC Milan", "Milan"],
    "Inter Milan":         ["Inter", "FC Internazionale", "Inter de Milán"],
    "Inter de Milán":      ["Inter", "FC Internazionale", "Inter Milan"],
    "Napoles":             ["Napoli", "SSC Napoli", "Nápoles"],
    "Nápoles":             ["Napoli", "SSC Napoli", "Napoles"],
    "AS Roma":             ["Roma"],
    "Bolonia":             ["Bologna"],
    "Turín":               ["Torino"],
    "Génova":              ["Genoa"],
    "Lacio":               ["Lazio", "SS Lazio"],
    "Florencia":           ["Fiorentina", "ACF Fiorentina"],
    "Udinese":             ["Udinese Calcio"],
    "Salernitana":         ["US Salernitana"],
    "Monza":               ["AC Monza"],

    # Premier League
    "Manchester Utd":      ["Manchester United", "Man Utd", "Man United"],
    "Manchester City":     ["Man City"],
    "Newcastle":           ["Newcastle United"],
    "Tottenham":           ["Tottenham Hotspur", "Spurs"],
    "Wolves":              ["Wolverhampton Wanderers", "Wolverhampton"],
    "West Ham":            ["West Ham United"],
    "Nottingham Forest":   ["Notts Forest"],
    "Brighton":            ["Brighton & Hove Albion"],
    "Leicester":           ["Leicester City"],
    "Norwich":             ["Norwich City"],
    "Southampton":         ["Southampton FC"],

    # Ligue 1
    "PSG":                 ["Paris Saint-Germain", "Paris SG"],
    "Marseille":           ["Olympique Marseille", "OM"],
    "Lyon":                ["Olympique Lyonnais", "OL"],
    "Mónaco":              ["Monaco", "AS Monaco"],
    "Monaco":              ["AS Monaco", "Mónaco"],
    "Niza":                ["Nice", "OGC Nice"],
    "Lille":               ["LOSC Lille", "LOSC"],
    "Lens":                ["RC Lens"],
    "Rennes":              ["Stade Rennais"],
    "Nantes":              ["FC Nantes"],
    "Estrasburgo":         ["Strasbourg", "RC Strasbourg"],

    # Otros
    "Bodø/Glimt":          ["Bodo/Glimt", "FK Bodo/Glimt"],
    "Sporting CP":         ["Sporting", "Sporting Clube de Portugal"],
    "Red Star Belgrade":   ["Crvena zvezda", "FK Crvena zvezda", "Estrella Roja"],
    "Estrella Roja":       ["Crvena zvezda", "FK Crvena zvezda", "Red Star Belgrade"],
    "Oporto":              ["Porto", "FC Porto"],
    "Lisboa":              ["Benfica", "SL Benfica"],
}


def _norm(txt: str) -> str:
    """Normaliza texto: minúsculas, sin acentos."""
    return "".join(
        c for c in unicodedata.normalize('NFD', txt.lower())
        if unicodedata.category(c) != 'Mn'
    ).strip()


def _get_variants(name: str) -> List[str]:
    variants = [name]
    if name in TEAM_ALIASES:
        variants.extend(TEAM_ALIASES[name])
    # Reverse lookup
    for key, aliases in TEAM_ALIASES.items():
        if name in aliases and key not in variants:
            variants.append(key)
    # Strip prefixes
    clean = re.sub(r'^(FC|CF|CD|RC|FK|AC|AS|SSC|FSV|1\.)\\s+', '', name).strip()
    if clean != name and clean not in variants:
        variants.append(clean)
    return list(dict.fromkeys(variants))


def _team_matches(query: str, sofa_name: str) -> bool:
    q = _norm(query)
    s = _norm(sofa_name)
    if q == s or q in s or s in q:
        return True
    q_words = {w for w in q.split() if len(w) > 3}
    s_words = {w for w in s.split() if len(w) > 3}
    if q_words and s_words and (q_words & s_words):
        return True
    return False


def _check_alias_match(home: str, away: str, name_in_source: str) -> bool:
    """Verifica si un nombre en una fuente corresponde a home o away usando aliases."""
    home_variants = [_norm(v) for v in _get_variants(home)]
    away_variants = [_norm(v) for v in _get_variants(away)]
    norm_name = _norm(name_in_source)
    return any(v in norm_name or norm_name in v for v in home_variants + away_variants)


# ===========================================================================
# BÚSQUEDA DE ÁRBITROS (multi-RSS)
# ===========================================================================

def _rss_search(query: str, max_items: int = 8) -> List[Dict]:
    """Fetches Google News RSS results for a query."""
    url = f"https://news.google.com/rss/search?q={requests.utils.quote(query)}&hl=es&gl=ES&ceid=ES:es"
    try:
        r = requests.get(url, headers=RSS_HEADERS, timeout=8)
        if r.status_code != 200:
            return []
        root = ET.fromstring(r.content)
        items = []
        for item in root.findall('.//item')[:max_items]:
            title = item.findtext('title', '') or ''
            desc = item.findtext('description', '') or ''
            desc_clean = re.sub(r'<[^>]+>', '', desc).strip()
            items.append({"title": title, "desc": desc_clean})
        return items
    except Exception as e:
        print(f"  [RSS] Error ({query[:40]}): {e}")
        return []


_REFEREE_KEYWORD_RE = re.compile(
    r'(árbitro|arbitro|referee|arbitre|schiedsrichter|colegiado|fischietto|designa)',
    re.IGNORECASE
)

# Patrones para extraer el nombre del árbitro
_NAME_PATTERNS = [
    # "árbitro: Juan Martínez Gil"
    r'(?:árbitro|arbitro|referee|arbitre|colegiado|fischietto)[:\s]+([A-ZÁÉÍÓÚÑÄÖÜ][a-záéíóúñäöü]+(?:\s+[A-ZÁÉÍÓÚÑÄÖÜ][a-záéíóúñäöü]+){1,3})',
    # "Juan Martínez Gil dirigirá / pitará"
    r'([A-ZÁÉÍÓÚÑ][a-záéíóúñ]+(?:\s+[A-ZÁÉÍÓÚÑ][a-záéíóúñ]+){1,3})\s+(?:será el árbitro|dirigirá|pitará|designado|se encargará)',
    # "dirigirá Juan Martínez Gil"
    r'(?:dirigirá|pitará|designado)\s+([A-ZÁÉÍÓÚÑ][a-záéíóúñ]+(?:\s+[A-ZÁÉÍÓÚÑ][a-záéíóúñ]+){1,3})',
    # German: "Schiedsrichter Felix Brych"
    r'Schiedsrichter[:\s]+([A-ZÄÖÜ][a-zäöü]+(?:\s+[A-ZÄÖÜ][a-zäöü]+){1,2})',
    # Italian: "sarà arbitrato da Daniele Orsato"
    r'sarà arbitrato da\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+){1,2})',
    # "il fischietto: Marco Guida"
    r'il fischietto[:\s]+([A-Z][a-z]+(?:\s+[A-Z][a-z]+){1,2})',
    # English: "referee: Michael Oliver"
    r'referee[:\s]+([A-Z][a-z]+(?:\s+[A-Z][a-z]+){1,3})',
]


def _extract_referee_from_text(text: str, home: str, away: str) -> Optional[str]:
    """Extrae nombre de árbitro de un texto dado."""
    if not _REFEREE_KEYWORD_RE.search(text):
        return None
    for pattern in _NAME_PATTERNS:
        m = re.search(pattern, text)
        if m:
            name = m.group(1).strip()
            # Limpieza
            name = re.sub(r'\s+(el|la|en|de|para|del)\s*$', '', name, flags=re.I).strip()
            parts = name.split()
            if 2 <= len(parts) <= 4 and not any(c.isdigit() for c in name):
                # Evitar confundir con nombre de equipos
                if not _check_alias_match(home, away, name):
                    return name
    return None


def _extract_referee_from_rss(home: str, away: str) -> Optional[str]:
    """
    Extrae el árbitro desde Google News RSS en múltiples idiomas.
    """
    home_variants = _get_variants(home)
    away_variants = _get_variants(away)

    # Usar el nombre más conocido (primer alias si existe)
    h = home_variants[1] if len(home_variants) > 1 else home
    a = away_variants[1] if len(away_variants) > 1 else away

    queries = [
        f'árbitro "{home}" "{away}"',
        f'árbitro "{h}" "{a}"',
        f'referee "{home}" "{away}"',
        f'referee "{h}" "{a}"',
        f'arbitro "{home}" "{away}"',
        f'Schiedsrichter "{h}" "{a}"',
        f'arbitre "{h}" "{a}"',
        f'fischietto "{h}" "{a}"',
    ]

    for q in queries:
        items = _rss_search(q, max_items=6)
        for item in items:
            full = item["title"] + " " + item["desc"]
            name = _extract_referee_from_text(full, home, away)
            if name:
                print(f"  [RSS] Árbitro: {name} (query: {q[:50]})")
                return name

    return None


def fetch_referee(home: str, away: str) -> Optional[Dict]:
    """
    Busca árbitro del partido via Google News RSS multi-idioma.
    SofaScore API no está disponible desde Python (403 Cloudflare).
    """
    print(f"  [Referee Search] {home} vs {away}")
    name = _extract_referee_from_rss(home, away)
    if name:
        h_enc = requests.utils.quote(f'árbitro {home} {away}')
        return {
            "name": name,
            "source": "Google News (prensa deportiva)",
            "verification_link": f"https://news.google.com/search?q={h_enc}",
            "_is_fallback": False
        }
    # Fallback
    return {
        "name": "Por confirmar",
        "source": "Sin datos (buscar manualmente 24h antes del partido)",
        "verification_link": f"https://news.google.com/search?q={requests.utils.quote(f'árbitro {home} {away}')}",
        "_is_fallback": True
    }


# ===========================================================================
# BÚSQUEDA DE ALINEACIONES
# - SofaScore API bloqueado → usamos RSS como indicador de titulares
# - La recuperación real desde DB se hace en LineupFetcher._safe_fallback
# ===========================================================================

def _find_sofa_event(home: str, away: str, timeout: int = 10) -> Optional[Dict]:
    """
    NOTA: SofaScore API devuelve 403 desde Python (Cloudflare TLS fingerprint).
    Esta función retorna None siempre — el sistema usará la alineación de referencia (DB).
    Dejamos el stub por compatibilidad futura si se añade una librería anti-bot.
    """
    print(f"  [SofaScore] No disponible en este entorno — {home} vs {away}")
    return None


def fetch_lineups(home: str, away: str) -> Optional[Dict]:
    """
    Alineaciones: SofaScore no accesible. Devuelve None para que
    LineupFetcher use automáticamente el fallback de la base de datos interna.
    """
    return None
