"""
sofascore_api.py — SofaScore API universal (árbitros + alineaciones)
====================================================================
Funciona sin JS en Streamlit Cloud.
Incluye normalización robusta de nombres de equipos.
"""
import requests
from typing import Optional, Dict, List

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
    "Accept": "application/json",
    "Accept-Language": "es-ES,es;q=0.9",
    "Referer": "https://www.sofascore.com/",
    "Origin": "https://www.sofascore.com",
}

# Alias de equipos: nombre app → variantes que usa SofaScore
TEAM_ALIASES = {
    "Bayer Leverkusen":    ["Bayer 04 Leverkusen", "Bayer Leverkusen", "Leverkusen"],
    "Atletico Madrid":     ["Atlético Madrid", "Atletico de Madrid", "Atletico Madrid"],
    "Atlético Madrid":     ["Atlético Madrid", "Atletico de Madrid"],
    "Manchester Utd":      ["Manchester United", "Man United", "Man Utd"],
    "Manchester City":     ["Manchester City", "Man City"],
    "Borussia Dortmund":   ["Dortmund", "BVB", "Borussia Dortmund"],
    "Dortmund":            ["Borussia Dortmund", "BVB", "Dortmund"],
    "RB Leipzig":          ["RB Leipzig", "Rasenballsport Leipzig"],
    "Gladbach":            ["Borussia M'gladbach", "Borussia Mönchengladbach", "M'gladbach"],
    "Union Berlin":        ["1. FC Union Berlin", "Union Berlin"],
    "Frankfurt":           ["Eintracht Frankfurt", "Frankfurt"],
    "Mainz 05":            ["Mainz", "FSV Mainz 05", "Mainz 05"],
    "Hamburgo":            ["Hamburger SV", "Hamburg", "HSV"],
    "Koln":                ["FC Köln", "Koln", "Cologne"],
    "St. Pauli":           ["FC St. Pauli", "St. Pauli"],
    "Bayern Munich":       ["Bayern München", "Bayern Munich", "FC Bayern München"],
    "FC Barcelona":        ["Barcelona", "FC Barcelona"],
    "Real Betis":          ["Real Betis", "Betis"],
    "Sevilla FC":          ["Sevilla", "Sevilla FC"],
    "Celta de Vigo":       ["Celta Vigo", "Celta de Vigo", "RC Celta"],
    "Athletic Club":       ["Athletic Club", "Athletic Bilbao", "Athletic"],
    "Rayo Vallecano":      ["Rayo Vallecano", "Rayo"],
    "AC Milan":            ["Milan", "AC Milan"],
    "Inter Milan":         ["Inter", "Inter Milan", "FC Internazionale"],
    "Napoles":             ["Napoli", "SSC Napoli"],
    "AS Roma":             ["Roma", "AS Roma"],
    "Bolonia":             ["Bologna", "Bolonia"],
    "PSG":                 ["Paris Saint-Germain", "PSG", "Paris SG"],
    "Marseille":           ["Olympique Marseille", "Marseille", "OM"],
    "Lyon":                ["Olympique Lyonnais", "Lyon", "OL"],
    "Newcastle":           ["Newcastle United", "Newcastle"],
    "Tottenham":           ["Tottenham Hotspur", "Tottenham", "Spurs"],
    "Wolves":              ["Wolverhampton Wanderers", "Wolves", "Wolverhampton"],
    "West Ham":            ["West Ham United", "West Ham"],
    "Nottingham Forest":   ["Nottingham Forest", "Notts Forest"],
    "Brighton":            ["Brighton & Hove Albion", "Brighton"],
    "Crystal Palace":      ["Crystal Palace"],
    "Bodø/Glimt":          ["Bodø/Glimt", "Bodo/Glimt", "FK Bodo/Glimt"],
    "Sporting CP":         ["Sporting CP", "Sporting", "Sporting Clube de Portugal"],
    "Red Star Belgrade":   ["Red Star Belgrade", "Crvena zvezda", "FK Crvena zvezda"],
}


def _get_variants(name: str) -> List[str]:
    """Devuelve todas las variantes de nombre a probar."""
    variants = [name]
    if name in TEAM_ALIASES:
        variants.extend(TEAM_ALIASES[name])
    # Añadir versión sin artículos y sin acentos
    clean = name.replace("FC ", "").replace("CF ", "").replace("CD ", "").strip()
    if clean != name:
        variants.append(clean)
    return list(dict.fromkeys(variants))  # deduplicar manteniendo orden


def _team_matches(query: str, sofa_name: str) -> bool:
    """Comprueba si un nombre de equipo coincide con el de SofaScore."""
    q = query.lower().strip()
    s = sofa_name.lower().strip()
    
    # Coincidencia exacta o inclusión
    if q == s or q in s or s in q:
        return True
    
    # Comparar por palabras significativas (>3 letras)
    q_words = {w for w in q.split() if len(w) > 3}
    s_words = {w for w in s.split() if len(w) > 3}
    if q_words and s_words:
        common = q_words & s_words
        if len(common) >= 1 and len(common) / max(len(q_words), len(s_words)) >= 0.5:
            return True
    
    return False


def _find_event(home: str, away: str, timeout: int = 10) -> Optional[Dict]:
    """
    Busca el evento en SofaScore con matching robusto de nombres.
    Prueba múltiples variantes de nombre hasta encontrar el partido.
    """
    home_variants = _get_variants(home)
    away_variants = _get_variants(away)
    
    # Intentar con diferentes combinaciones de búsqueda
    search_queries = [
        f"{home} {away}",
        f"{home_variants[0]} {away_variants[0]}",
    ]
    # Añadir búsquedas con apellidos/nombres cortos
    if len(home.split()) > 1:
        search_queries.append(f"{home.split()[0]} {away.split()[0]}")
    
    for query in search_queries:
        try:
            url = f"https://api.sofascore.com/api/v1/search/events?q={query.replace(' ', '%20')}"
            resp = requests.get(url, headers=HEADERS, timeout=timeout)
            if resp.status_code != 200:
                continue
            
            events = resp.json().get("events", [])
            
            for ev in events[:10]:
                hn = ev.get("homeTeam", {}).get("name", "")
                an = ev.get("awayTeam", {}).get("name", "")
                
                # Comprobar con todas las variantes
                home_ok = any(_team_matches(v, hn) for v in home_variants)
                away_ok = any(_team_matches(v, an) for v in away_variants)
                
                if home_ok and away_ok:
                    return ev
                    
        except Exception as e:
            print(f"[SofaScore] find_event error ({query}): {e}")
    
    return None


def fetch_referee(home: str, away: str) -> Optional[Dict]:
    """
    Devuelve árbitro desde SofaScore API para cualquier liga.
    """
    try:
        ev = _find_event(home, away)
        if not ev:
            print(f"[SofaScore] Partido no encontrado: {home} vs {away}")
            return None
        
        eid = ev.get("id")
        if not eid:
            return None
        
        resp = requests.get(
            f"https://api.sofascore.com/api/v1/event/{eid}",
            headers=HEADERS, timeout=8
        )
        if resp.status_code != 200:
            return None
        
        event_data = resp.json().get("event", {})
        referee = event_data.get("referee", {})
        ref_name = referee.get("name", "")
        
        if ref_name and len(ref_name.split()) >= 2:
            print(f"[SofaScore] ✅ Árbitro: {ref_name}")
            return {
                "name": ref_name,
                "source": "SofaScore",
                "verification_link": f"https://www.sofascore.com/es/partido/{eid}",
                "_is_fallback": False,
                "event_id": eid
            }
        else:
            print(f"[SofaScore] Partido encontrado (ID:{eid}) pero árbitro no asignado aún")
            # Devolver el link para verificar manualmente
            return {
                "name": "Por confirmar",
                "source": "SofaScore (árbitro no asignado aún)",
                "verification_link": f"https://www.sofascore.com/es/partido/{eid}",
                "_is_fallback": True,
                "event_id": eid
            }
            
    except Exception as e:
        print(f"[SofaScore] fetch_referee error: {e}")
    return None


def fetch_lineups(home: str, away: str) -> Optional[Dict]:
    """
    Devuelve alineaciones desde SofaScore API para cualquier liga.
    """
    try:
        ev = _find_event(home, away)
        if not ev:
            print(f"[SofaScore] Partido no encontrado para alineaciones: {home} vs {away}")
            return None
        
        eid = ev.get("id")
        if not eid:
            return None
        
        resp = requests.get(
            f"https://api.sofascore.com/api/v1/event/{eid}/lineups",
            headers=HEADERS, timeout=8
        )
        
        if resp.status_code == 404:
            print(f"[SofaScore] Alineaciones no publicadas aún (404) — partido ID {eid}")
            return {
                "home": [], "away": [], "source": "SofaScore",
                "verification_link": f"https://www.sofascore.com/es/partido/{eid}",
                "_is_fallback": True,
                "not_available_yet": True,
                "event_id": eid
            }
        
        if resp.status_code != 200:
            return None
            
        lu = resp.json()
        
        def _extract(side):
            players = lu.get(side, {}).get("players", [])
            result = []
            for p in players:
                pdata = p.get("player", {})
                name = pdata.get("shortName") or pdata.get("name", "")
                # Solo titulares (position != substitute)
                pos = p.get("position", "")
                if name and pos not in ["S", "substitute"]:
                    result.append(name)
            return result[:11]
        
        home_p = _extract("home")
        away_p = _extract("away")
        
        # Si no hay titulares, coger todos
        if not home_p and not away_p:
            def _extract_all(side):
                players = lu.get(side, {}).get("players", [])
                return [p.get("player", {}).get("name", "") 
                        for p in players if p.get("player", {}).get("name")][:11]
            home_p = _extract_all("home")
            away_p = _extract_all("away")
        
        if home_p or away_p:
            is_confirmed = ev.get("status", {}).get("type", "") in ["inprogress", "finished"]
            print(f"[SofaScore] ✅ Alineaciones: {len(home_p)} + {len(away_p)} jugadores")
            return {
                "home": home_p,
                "away": away_p,
                "source": "SofaScore",
                "verification_link": f"https://www.sofascore.com/es/partido/{eid}",
                "_is_fallback": False,
                "is_official": is_confirmed,
                "event_id": eid
            }
            
    except Exception as e:
        print(f"[SofaScore] fetch_lineups error: {e}")
    return None
