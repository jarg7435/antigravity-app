"""
sofascore_api.py — Módulo universal SofaScore API
=================================================
Fuente primaria para árbitros y alineaciones de CUALQUIER liga.
No requiere JavaScript. Funciona en Streamlit Cloud.
"""
import requests
from typing import Optional, Dict, List
from datetime import datetime

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    "Accept": "application/json",
    "Referer": "https://www.sofascore.com/",
}

def _find_event(home: str, away: str, timeout: int = 10) -> Optional[Dict]:
    """Busca el evento en SofaScore y devuelve el dict del evento más relevante."""
    try:
        q = f"{home} {away}".replace(" ", "%20")
        url = f"https://api.sofascore.com/api/v1/search/events?q={q}"
        resp = requests.get(url, headers=HEADERS, timeout=timeout)
        if resp.status_code != 200:
            return None
        events = resp.json().get("events", [])
        home_kw = home.lower().split()[0]
        away_kw = away.lower().split()[0]
        for ev in events[:8]:
            hn = ev.get("homeTeam", {}).get("name", "").lower()
            an = ev.get("awayTeam", {}).get("name", "").lower()
            if (home_kw in hn or hn in home.lower()) and \
               (away_kw in an or an in away.lower()):
                return ev
        # Segundo intento con solo el equipo local
        for ev in events[:5]:
            hn = ev.get("homeTeam", {}).get("name", "").lower()
            if home_kw in hn or hn in home.lower():
                return ev
    except Exception as e:
        print(f"[SofaScore] find_event error: {e}")
    return None


def fetch_referee(home: str, away: str) -> Optional[Dict]:
    """
    Devuelve árbitro desde SofaScore API.
    Funciona para TODAS las ligas.
    """
    try:
        ev = _find_event(home, away)
        if not ev:
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
        ref = detail.json().get("event", {}).get("referee", {})
        ref_name = ref.get("name", "")
        if ref_name and len(ref_name.split()) >= 2:
            return {
                "name": ref_name,
                "source": "SofaScore",
                "verification_link": f"https://www.sofascore.com/es/partido/{eid}",
                "_is_fallback": False,
                "event_id": eid
            }
    except Exception as e:
        print(f"[SofaScore] fetch_referee error: {e}")
    return None


def fetch_lineups(home: str, away: str) -> Optional[Dict]:
    """
    Devuelve alineaciones desde SofaScore API.
    Funciona para TODAS las ligas. Solo disponible cuando están publicadas.
    """
    try:
        ev = _find_event(home, away)
        if not ev:
            return None
        eid = ev.get("id")
        if not eid:
            return None
        resp = requests.get(
            f"https://api.sofascore.com/api/v1/event/{eid}/lineups",
            headers=HEADERS, timeout=8
        )
        if resp.status_code != 200:
            return None
        lu = resp.json()
        def _extract(side):
            players = lu.get(side, {}).get("players", [])
            return [p.get("player", {}).get("name", "") for p in players
                    if p.get("player", {}).get("name") and
                    p.get("playerColor") is not None]  # solo titulares confirmados
        home_p = _extract("home")
        away_p = _extract("away")
        if not home_p and not away_p:
            # Intentar sin filtro de titulares
            def _extract_all(side):
                players = lu.get(side, {}).get("players", [])
                return [p.get("player", {}).get("name", "") for p in players
                        if p.get("player", {}).get("name")]
            home_p = _extract_all("home")[:11]
            away_p = _extract_all("away")[:11]

        if home_p or away_p:
            return {
                "home": home_p,
                "away": away_p,
                "source": "SofaScore",
                "verification_link": f"https://www.sofascore.com/es/partido/{eid}",
                "_is_fallback": False,
                "is_official": ev.get("status", {}).get("type", "") in ["inprogress", "finished"]
            }
    except Exception as e:
        print(f"[SofaScore] fetch_lineups error: {e}")
    return None


def fetch_injuries(team_name: str, team_id: Optional[int] = None) -> List[Dict]:
    """
    Devuelve lista de lesionados/dudosos desde SofaScore.
    """
    injuries = []
    try:
        # Buscar ID del equipo si no se tiene
        if not team_id:
            resp = requests.get(
                f"https://api.sofascore.com/api/v1/search/teams?q={team_name.replace(' ', '%20')}",
                headers=HEADERS, timeout=8
            )
            if resp.status_code == 200:
                teams = resp.json().get("teams", [])
                for t in teams[:3]:
                    if team_name.lower().split()[0] in t.get("name", "").lower():
                        team_id = t.get("id")
                        break
        if team_id:
            resp2 = requests.get(
                f"https://api.sofascore.com/api/v1/team/{team_id}/players",
                headers=HEADERS, timeout=8
            )
            if resp2.status_code == 200:
                players = resp2.json().get("players", [])
                for p in players:
                    status = p.get("player", {}).get("injurySection", "")
                    if status and status != "":
                        injuries.append({
                            "name": p.get("player", {}).get("name", ""),
                            "status": status
                        })
    except Exception as e:
        print(f"[SofaScore] fetch_injuries error: {e}")
    return injuries
