"""
sofascore_api.py — SofaScore API universal (sin JS)
====================================================
Busca partidos, árbitros y alineaciones para CUALQUIER liga.
Funciona en Streamlit Cloud. No requiere Playwright.
"""
import requests
import re
from typing import Optional, Dict, List
from datetime import datetime, timedelta

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
    "Accept": "application/json",
    "Referer": "https://www.sofascore.com/",
    "Origin": "https://www.sofascore.com",
}

# Mapa de nombres alternativos para equipos
TEAM_ALIASES = {
    "atletico madrid": ["atletico", "atlético de madrid", "atlético madrid"],
    "manchester utd": ["manchester united", "man utd", "man united"],
    "manchester city": ["man city"],
    "bayer leverkusen": ["leverkusen", "b. leverkusen"],
    "bayern munich": ["fc bayern", "bayern münchen", "fc bayern münchen", "bavière"],
    "borussia dortmund": ["dortmund", "bvb"],
    "rb leipzig": ["red bull leipzig", "rasenballsport leipzig"],
    "real madrid": ["r. madrid"],
    "fc barcelona": ["barcelona", "barça"],
    "paris sg": ["psg", "paris saint-germain", "paris sg"],
    "ac milan": ["milan"],
    "inter milan": ["inter", "internazionale"],
    "sporting cp": ["sporting", "sporting clube"],
    "fc porto": ["porto"],
}

def _normalize_team(name: str) -> str:
    """Normaliza nombre de equipo para comparación."""
    n = name.lower().strip()
    n = re.sub(r'\s+', ' ', n)
    # Quitar prefijos comunes
    n = re.sub(r'^(fc |cf |sd |rc |rcd |cd |ud |ca |at\. )', '', n)
    return n

def _teams_match(search_name: str, sofa_name: str) -> bool:
    """Comprueba si dos nombres de equipo son el mismo."""
    sn = _normalize_team(search_name)
    sfn = _normalize_team(sofa_name)
    
    # Coincidencia exacta
    if sn == sfn:
        return True
    
    # Uno contiene al otro (mínimo 5 chars para evitar falsos positivos)
    if len(sn) >= 5 and sn in sfn:
        return True
    if len(sfn) >= 5 and sfn in sn:
        return True
    
    # Comprobar aliases
    for canonical, aliases in TEAM_ALIASES.items():
        names_set = {canonical} | set(aliases)
        if sn in names_set and sfn in names_set:
            return True
    
    # Palabra clave más larga (no "fc", "cf", etc.)
    stop_words = {"fc", "cf", "rc", "sc", "ac", "as", "ss", "if", "sk", "fk", "bk"}
    sn_words = [w for w in sn.split() if len(w) > 2 and w not in stop_words]
    sfn_words = [w for w in sfn.split() if len(w) > 2 and w not in stop_words]
    
    if sn_words and sfn_words:
        # Si la palabra más larga coincide
        sn_main = max(sn_words, key=len)
        sfn_main = max(sfn_words, key=len)
        if len(sn_main) >= 4 and (sn_main in sfn_main or sfn_main in sn_main):
            return True
    
    return False

def _find_event(home: str, away: str, timeout: int = 12) -> Optional[Dict]:
    """
    Busca el partido en SofaScore con matching robusto.
    Prioriza partidos en juego o recientes sobre futuros.
    """
    try:
        # Intentar con ambos nombres
        for query in [f"{home} {away}", home, away]:
            q = query.replace(" ", "%20")
            url = f"https://api.sofascore.com/api/v1/search/events?q={q}"
            resp = requests.get(url, headers=HEADERS, timeout=timeout)
            if resp.status_code != 200:
                continue
            
            events = resp.json().get("events", [])
            if not events:
                continue
            
            # Ordenar: primero inprogress, luego finished, luego notstarted
            STATUS_PRIORITY = {"inprogress": 0, "finished": 1, "notstarted": 2}
            events_sorted = sorted(
                events,
                key=lambda e: STATUS_PRIORITY.get(
                    e.get("status", {}).get("type", ""), 3
                )
            )
            
            for ev in events_sorted[:15]:
                hn = ev.get("homeTeam", {}).get("name", "")
                an = ev.get("awayTeam", {}).get("name", "")
                
                if _teams_match(home, hn) and _teams_match(away, an):
                    return ev
                # Invertir local/visitante (por si está invertido)
                if _teams_match(home, an) and _teams_match(away, hn):
                    return ev
            
            # Si encontramos con query=home, parar
            if query == home:
                break
                
    except Exception as e:
        print(f"[SofaScore] find_event error: {e}")
    return None


def fetch_referee(home: str, away: str) -> Optional[Dict]:
    """Árbitro desde SofaScore. Funciona para todas las ligas."""
    try:
        ev = _find_event(home, away)
        if not ev:
            print(f"[SofaScore] Partido no encontrado: {home} vs {away}")
            return None
        
        eid = ev.get("id")
        if not eid:
            return None
        
        detail = requests.get(
            f"https://api.sofascore.com/api/v1/event/{eid}",
            headers=HEADERS, timeout=8
        )
        if detail.status_code != 200:
            return None
        
        event_data = detail.json().get("event", {})
        ref = event_data.get("referee", {})
        ref_name = ref.get("name", "")
        
        status = event_data.get("status", {}).get("type", "")
        hn = ev.get("homeTeam", {}).get("name", home)
        an = ev.get("awayTeam", {}).get("name", away)
        
        print(f"[SofaScore] Partido encontrado: {hn} vs {an} (status: {status})")
        print(f"[SofaScore] Árbitro: {ref_name or 'No disponible'}")
        
        if ref_name and len(ref_name.split()) >= 2:
            return {
                "name": ref_name,
                "source": "SofaScore",
                "verification_link": f"https://www.sofascore.com/es/partido/{eid}",
                "_is_fallback": False,
                "event_id": eid,
                "match_status": status
            }
        
        # Si el partido existe pero no hay árbitro aún
        return {
            "name": "Por confirmar",
            "source": f"SofaScore (partido: {hn} vs {an})",
            "verification_link": f"https://www.sofascore.com/es/partido/{eid}",
            "_is_fallback": True,
            "event_id": eid
        }
        
    except Exception as e:
        print(f"[SofaScore] fetch_referee error: {e}")
    return None


def fetch_lineups(home: str, away: str) -> Optional[Dict]:
    """Alineaciones desde SofaScore. Disponible 1h antes y durante el partido."""
    try:
        ev = _find_event(home, away)
        if not ev:
            print(f"[SofaScore] Partido no encontrado para alineaciones: {home} vs {away}")
            return None
        
        eid = ev.get("id")
        if not eid:
            return None
        
        status = ev.get("status", {}).get("type", "")
        hn = ev.get("homeTeam", {}).get("name", home)
        an = ev.get("awayTeam", {}).get("name", away)
        print(f"[SofaScore] Buscando alineaciones: {hn} vs {an} (status: {status})")
        
        resp = requests.get(
            f"https://api.sofascore.com/api/v1/event/{eid}/lineups",
            headers=HEADERS, timeout=8
        )
        if resp.status_code != 200:
            print(f"[SofaScore] Lineups API: {resp.status_code}")
            return None
        
        lu = resp.json()
        
        def _extract_starters(side):
            """Extrae solo titulares (position != None o jerseyNumber <= 11)."""
            players = lu.get(side, {}).get("players", [])
            starters = []
            subs = []
            for p in players:
                p_data = p.get("player", {})
                name = p_data.get("name", "") or p_data.get("shortName", "")
                if not name:
                    continue
                # Titulares: tienen posición asignada y jersey ≤ 11 generalmente
                jersey = p.get("jerseyNumber", 99)
                pos = p.get("position", None)
                substitute = p.get("substitute", True)
                if not substitute:
                    starters.append(name)
                else:
                    subs.append(name)
            return starters, subs
        
        home_s, home_subs = _extract_starters("home")
        away_s, away_subs = _extract_starters("away")
        
        # Si no hay titulares separados, tomar los primeros 11
        if not home_s and not away_s:
            def _all_players(side):
                players = lu.get(side, {}).get("players", [])
                names = []
                for p in players:
                    p_data = p.get("player", {})
                    name = p_data.get("name", "") or p_data.get("shortName", "")
                    if name:
                        names.append(name)
                return names
            home_s = _all_players("home")[:11]
            away_s = _all_players("away")[:11]
        
        if home_s or away_s:
            is_confirmed = status in ["inprogress", "finished"]
            return {
                "home": home_s,
                "away": away_s,
                "home_subs": home_subs,
                "away_subs": away_subs,
                "source": "SofaScore",
                "verification_link": f"https://www.sofascore.com/es/partido/{eid}",
                "_is_fallback": False,
                "is_official": is_confirmed,
                "match_status": status
            }
        
        print(f"[SofaScore] Sin alineaciones aún para evento {eid}")
        return None
        
    except Exception as e:
        print(f"[SofaScore] fetch_lineups error: {e}")
    return None


def fetch_injuries(team_name: str) -> List[Dict]:
    """Lesionados/dudosos desde SofaScore para un equipo."""
    injuries = []
    try:
        resp = requests.get(
            f"https://api.sofascore.com/api/v1/search/teams?q={team_name.replace(' ', '%20')}",
            headers=HEADERS, timeout=8
        )
        if resp.status_code == 200:
            teams = resp.json().get("teams", [])
            team_id = None
            for t in teams[:5]:
                if _teams_match(team_name, t.get("name", "")):
                    team_id = t.get("id")
                    break
            if team_id:
                resp2 = requests.get(
                    f"https://api.sofascore.com/api/v1/team/{team_id}/players",
                    headers=HEADERS, timeout=8
                )
                if resp2.status_code == 200:
                    for p in resp2.json().get("players", []):
                        status = p.get("player", {}).get("injurySection", "")
                        if status:
                            injuries.append({
                                "name": p.get("player", {}).get("name", ""),
                                "status": status
                            })
    except Exception as e:
        print(f"[SofaScore] fetch_injuries error: {e}")
    return injuries
