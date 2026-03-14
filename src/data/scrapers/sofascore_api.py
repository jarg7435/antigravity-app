"""
sofascore_api.py — Búsqueda de árbitros y alineaciones
=======================================================
Estrategia dual:
1. SofaScore API (JSON directo, sin JS)
2. Google News RSS como respaldo para árbitros
   (mismo método que usa rss_analyst - funciona en Streamlit Cloud)
"""
import re
import requests
import xml.etree.ElementTree as ET
from typing import Optional, Dict, List

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
    "Accept": "application/json",
    "Accept-Language": "es-ES,es;q=0.9",
    "Referer": "https://www.sofascore.com/",
}

RSS_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    "Accept": "application/rss+xml, application/xml, text/xml, */*",
}

# Alias de nombres de equipos: app → SofaScore
TEAM_ALIASES = {
    "Bayer Leverkusen":    ["Bayer 04 Leverkusen", "Leverkusen"],
    "Bayern Munich":       ["Bayern München", "FC Bayern München", "FC Bayern"],
    "Atletico Madrid":     ["Atlético Madrid", "Atletico de Madrid"],
    "Atlético Madrid":     ["Atletico Madrid", "Atletico de Madrid"],
    "Manchester Utd":      ["Manchester United", "Man Utd", "Man United"],
    "Manchester City":     ["Man City"],
    "Dortmund":            ["Borussia Dortmund", "BVB"],
    "RB Leipzig":          ["Rasenballsport Leipzig"],
    "Gladbach":            ["Borussia M'gladbach", "Borussia Mönchengladbach"],
    "Union Berlin":        ["1. FC Union Berlin"],
    "Frankfurt":           ["Eintracht Frankfurt"],
    "Mainz 05":            ["FSV Mainz 05", "Mainz"],
    "Hamburgo":            ["Hamburger SV", "HSV"],
    "Koln":                ["FC Köln", "Cologne", "Köln"],
    "St. Pauli":           ["FC St. Pauli"],
    "FC Barcelona":        ["Barcelona"],
    "Sevilla FC":          ["Sevilla"],
    "Celta de Vigo":       ["Celta Vigo", "RC Celta"],
    "Athletic Club":       ["Athletic Bilbao", "Athletic"],
    "Rayo Vallecano":      ["Rayo"],
    "AC Milan":            ["Milan"],
    "Inter Milan":         ["Inter", "FC Internazionale"],
    "Napoles":             ["Napoli", "SSC Napoli"],
    "AS Roma":             ["Roma"],
    "Bolonia":             ["Bologna"],
    "PSG":                 ["Paris Saint-Germain", "Paris SG"],
    "Marseille":           ["Olympique Marseille", "OM"],
    "Lyon":                ["Olympique Lyonnais", "OL"],
    "Newcastle":           ["Newcastle United"],
    "Tottenham":           ["Tottenham Hotspur", "Spurs"],
    "Wolves":              ["Wolverhampton Wanderers", "Wolverhampton"],
    "West Ham":            ["West Ham United"],
    "Nottingham Forest":   ["Notts Forest"],
    "Brighton":            ["Brighton & Hove Albion"],
    "Bodø/Glimt":          ["Bodo/Glimt", "FK Bodo/Glimt"],
    "Sporting CP":         ["Sporting", "Sporting Clube de Portugal"],
    "Red Star Belgrade":   ["Crvena zvezda", "FK Crvena zvezda"],
}


def _get_variants(name: str) -> List[str]:
    variants = [name]
    if name in TEAM_ALIASES:
        variants.extend(TEAM_ALIASES[name])
    clean = re.sub(r'^(FC|CF|CD|RC|FK|AC|AS|SSC|FSV)\s+', '', name).strip()
    if clean != name:
        variants.append(clean)
    return list(dict.fromkeys(variants))


def _team_matches(query: str, sofa_name: str) -> bool:
    q = query.lower().strip()
    s = sofa_name.lower().strip()
    if q == s or q in s or s in q:
        return True
    q_words = {w for w in q.split() if len(w) > 3}
    s_words = {w for w in s.split() if len(w) > 3}
    if q_words and s_words and (q_words & s_words):
        return True
    return False


def _find_sofa_event(home: str, away: str, timeout: int = 10) -> Optional[Dict]:
    """Busca evento en SofaScore con matching robusto."""
    home_variants = _get_variants(home)
    away_variants = _get_variants(away)

    queries = [f"{home} {away}", f"{home_variants[0]} {away_variants[0]}"]
    if len(home.split()) > 1:
        queries.append(f"{home.split()[-1]} {away.split()[-1]}")

    for query in queries:
        try:
            url = f"https://api.sofascore.com/api/v1/search/events?q={requests.utils.quote(query)}"
            r = requests.get(url, headers=HEADERS, timeout=timeout)
            if r.status_code != 200:
                continue
            events = r.json().get("events", [])
            for ev in events[:10]:
                hn = ev.get("homeTeam", {}).get("name", "")
                an = ev.get("awayTeam", {}).get("name", "")
                home_ok = any(_team_matches(v, hn) for v in home_variants)
                away_ok = any(_team_matches(v, an) for v in away_variants)
                if home_ok and away_ok:
                    print(f"  [SofaScore] Partido encontrado: {hn} vs {an} (ID:{ev.get('id')})")
                    return ev
        except Exception as e:
            print(f"  [SofaScore] find_event error: {e}")
    return None


def _extract_referee_from_rss(home: str, away: str) -> Optional[str]:
    """
    Extrae el nombre del árbitro desde Google News RSS.
    Mismo método que rss_analyst — funciona en Streamlit Cloud.
    """
    # Palabras clave para encontrar árbitros en titulares
    referee_keywords = [
        "árbitro", "arbitro", "referee", "arbitre", "schiedsrichter",
        "designaci", "pita", "dirige", "impartirá"
    ]

    queries = [
        f'árbitro {home} {away}',
        f'referee {home} {away}',
        f'arbitro {home} {away}',
    ]

    for q in queries:
        try:
            url = f"https://news.google.com/rss/search?q={requests.utils.quote(q)}&hl=es&gl=ES&ceid=ES:es"
            r = requests.get(url, headers=RSS_HEADERS, timeout=8)
            if r.status_code != 200:
                continue

            root = ET.fromstring(r.content)
            items = root.findall('.//item')

            for item in items[:5]:
                title = item.findtext('title', '') or ''
                desc  = item.findtext('description', '') or ''
                text  = (title + ' ' + desc).lower()

                # Verificar que la noticia habla de árbitros
                if not any(kw in text for kw in referee_keywords):
                    continue

                # Patrón: nombres propios mayúsculas tras "árbitro" / "referee"
                # Ej: "árbitro Jesús Gil Manzano" o "dirigirá Michael Oliver"
                patterns = [
                    r'árbitro[:\s]+([A-ZÁÉÍÓÚÑ][a-záéíóúñ]+(?:\s+[A-ZÁÉÍÓÚÑ][a-záéíóúñ]+){1,3})',
                    r'arbitro[:\s]+([A-ZÁÉÍÓÚÑ][a-záéíóúñ]+(?:\s+[A-ZÁÉÍÓÚÑ][a-záéíóúñ]+){1,3})',
                    r'referee[:\s]+([A-Z][a-z]+(?:\s+[A-Z][a-z]+){1,3})',
                    r'arbitre[:\s]+([A-Z][a-záéíóú]+(?:\s+[A-Z][a-záéíóú]+){1,3})',
                    r'dirigir[áa]\s+([A-ZÁÉÍÓÚÑ][a-záéíóúñ]+(?:\s+[A-ZÁÉÍÓÚÑ][a-záéíóúñ]+){1,3})',
                    r'pita[rá]+\s+([A-ZÁÉÍÓÚÑ][a-záéíóúñ]+(?:\s+[A-ZÁÉÍÓÚÑ][a-záéíóúñ]+){1,3})',
                ]
                full_text = title + ' ' + desc
                for pattern in patterns:
                    m = re.search(pattern, full_text, re.IGNORECASE)
                    if m:
                        name = m.group(1).strip()
                        # Validar que parece un nombre real (2-4 palabras, sin números)
                        parts = name.split()
                        if 2 <= len(parts) <= 4 and not any(c.isdigit() for c in name):
                            print(f"  [RSS] Árbitro encontrado en noticias: {name}")
                            return name

        except Exception as e:
            print(f"  [RSS] referee error ({q}): {e}")

    return None


def fetch_referee(home: str, away: str) -> Optional[Dict]:
    """
    Busca árbitro: primero SofaScore API, luego Google News RSS.
    """
    # 1. SofaScore API
    try:
        ev = _find_sofa_event(home, away)
        if ev:
            eid = ev.get("id")
            r = requests.get(
                f"https://api.sofascore.com/api/v1/event/{eid}",
                headers=HEADERS, timeout=8
            )
            if r.status_code == 200:
                referee = r.json().get("event", {}).get("referee", {})
                ref_name = referee.get("name", "")
                if ref_name and len(ref_name.split()) >= 2:
                    return {
                        "name": ref_name,
                        "source": "SofaScore",
                        "verification_link": f"https://www.sofascore.com/es/partido/{eid}",
                        "_is_fallback": False
                    }
                else:
                    # Partido encontrado, árbitro no asignado aún
                    print(f"  [SofaScore] Árbitro no asignado aún para ID {eid}")
                    sofa_link = f"https://www.sofascore.com/es/partido/{eid}"
                    # Intentar RSS antes de devolver fallback
                    rss_name = _extract_referee_from_rss(home, away)
                    if rss_name:
                        return {
                            "name": rss_name,
                            "source": "Google News",
                            "verification_link": sofa_link,
                            "_is_fallback": False
                        }
                    return {
                        "name": "Por confirmar",
                        "source": "SofaScore (árbitro no asignado aún)",
                        "verification_link": sofa_link,
                        "_is_fallback": True
                    }
    except Exception as e:
        print(f"  [SofaScore] fetch_referee error: {e}")

    # 2. Google News RSS
    try:
        rss_name = _extract_referee_from_rss(home, away)
        if rss_name:
            return {
                "name": rss_name,
                "source": "Google News",
                "verification_link": f"https://news.google.com/search?q={requests.utils.quote(f'árbitro {home} {away}')}",
                "_is_fallback": False
            }
    except Exception as e:
        print(f"  [RSS] referee error: {e}")

    return None


def fetch_lineups(home: str, away: str) -> Optional[Dict]:
    """
    Busca alineaciones en SofaScore API.
    """
    try:
        ev = _find_sofa_event(home, away)
        if not ev:
            return None

        eid = ev.get("id")
        r = requests.get(
            f"https://api.sofascore.com/api/v1/event/{eid}/lineups",
            headers=HEADERS, timeout=8
        )

        if r.status_code == 404:
            return {
                "home": [], "away": [], "source": "SofaScore",
                "verification_link": f"https://www.sofascore.com/es/partido/{eid}",
                "_is_fallback": True, "not_available_yet": True
            }

        if r.status_code != 200:
            return None

        lu = r.json()

        def _extract(side):
            players = lu.get(side, {}).get("players", [])
            result = []
            for p in players:
                pdata = p.get("player", {})
                name = pdata.get("shortName") or pdata.get("name", "")
                pos = p.get("position", "")
                if name and pos not in ["S", "substitute"]:
                    result.append(name)
            return result[:11]

        home_p = _extract("home")
        away_p = _extract("away")

        if not home_p and not away_p:
            def _all(side):
                players = lu.get(side, {}).get("players", [])
                return [p.get("player", {}).get("name", "")
                        for p in players if p.get("player", {}).get("name")][:11]
            home_p = _all("home")
            away_p = _all("away")

        if home_p or away_p:
            is_live = ev.get("status", {}).get("type", "") in ["inprogress", "finished"]
            return {
                "home": home_p, "away": away_p,
                "source": "SofaScore",
                "verification_link": f"https://www.sofascore.com/es/partido/{eid}",
                "_is_fallback": False,
                "is_official": is_live
            }

    except Exception as e:
        print(f"  [SofaScore] fetch_lineups error: {e}")

    return None
