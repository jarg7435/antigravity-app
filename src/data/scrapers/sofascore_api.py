"""
sofascore_api.py — Búsqueda de árbitros y alineaciones
Cascada simple: intenta cada fuente, si falla pasa a la siguiente.
"""
import re
import requests
import xml.etree.ElementTree as ET
from typing import Optional, Dict, List

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
    "Accept": "application/json",
    "Referer": "https://www.sofascore.com/",
}
RSS_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    "Accept": "application/rss+xml, text/xml, */*",
}

# Lista completa de árbitros conocidos — se buscan directamente en el texto
KNOWN_REFEREES = [
    # La Liga
    "Martínez Munuera","Gil Manzano","Jesús Gil Manzano","Sánchez Martínez",
    "Hernández Hernández","Munuera Montero","Del Cerro Grande","Figueroa Vázquez",
    "Trujillo Suárez","Pizarro Gómez","Melero López","Díaz de Mera",
    "Ricardo de Burgos","Burgos Bengoetxea","Cuadra Fernández","Mateu Lahoz",
    "Ortiz Arias","González Fuertes","Ais Reig","Estrada Fernández",
    "Isidro Díaz de Mera","Pulido Santana","Adrián Cordero","José Sánchez",
    # Premier
    "Michael Oliver","Anthony Taylor","Craig Pawson","Paul Tierney",
    "Simon Hooper","Stuart Attwell","Andy Madley","Robert Jones",
    "Darren England","Thomas Bramall","Sam Barrott","Tim Robinson",
    # Bundesliga
    "Felix Brych","Deniz Aytekin","Tobias Stieler","Marco Fritz",
    "Daniel Schlager","Harm Osmers","Patrick Ittrich","Benjamin Cortus",
    "Christian Dingert","Bastian Dankert",
    # Serie A
    "Daniele Orsato","Marco Guida","Davide Massa","Maurizio Mariani",
    "Gianluca Manganiello","Fabio Maresca","Simone Sozza","Juan Luca Sacchi",
    "Livio Marinelli","Francesco Fourneau","Michael Fabbri","Luca Massimi",
    # Ligue 1
    "Clément Turpin","François Letexier","Benoît Bastien","Willy Delajod",
    "Ruddy Buquet","Florent Batta","Hakim Ben El Hadj","Johan Hamel",
    # UEFA/Internacional
    "Szymon Marciniak","Danny Makkelie","Istvan Kovacs","Artur Soares Dias",
    "Slavko Vincic","Glenn Nyberg","Felix Zwayer","Clement Turpin",
]

# Variantes de nombre de equipos para matching
TEAM_ALIASES = {
    "FC Barcelona": ["Barcelona","Barça","Barca"],
    "Atletico Madrid": ["Atlético Madrid","Atletico de Madrid","Atleti"],
    "Atlético Madrid": ["Atletico Madrid","Atleti"],
    "Bayer Leverkusen": ["Bayer 04 Leverkusen","Leverkusen"],
    "Bayern Munich": ["Bayern München","FC Bayern","Bayern"],
    "Manchester Utd": ["Manchester United","Man Utd","Man United"],
    "Manchester City": ["Man City"],
    "Dortmund": ["Borussia Dortmund","BVB"],
    "Gladbach": ["Borussia M'gladbach","Mönchengladbach"],
    "Frankfurt": ["Eintracht Frankfurt"],
    "Mainz 05": ["Mainz","FSV Mainz 05"],
    "Hamburgo": ["Hamburger SV","HSV"],
    "Koln": ["FC Köln","Köln","Cologne"],
    "St. Pauli": ["FC St. Pauli"],
    "Inter Milan": ["Inter","FC Internazionale","Internazionale"],
    "AC Milan": ["Milan"],
    "Napoles": ["Napoli","SSC Napoli"],
    "AS Roma": ["Roma"],
    "Bolonia": ["Bologna"],
    "PSG": ["Paris Saint-Germain","Paris SG"],
    "Marseille": ["Olympique Marseille","OM"],
    "Lyon": ["Olympique Lyonnais","OL"],
    "Newcastle": ["Newcastle United"],
    "Tottenham": ["Tottenham Hotspur","Spurs"],
    "Wolves": ["Wolverhampton Wanderers","Wolverhampton"],
    "West Ham": ["West Ham United"],
    "Sevilla FC": ["Sevilla"],
    "Celta de Vigo": ["Celta Vigo","RC Celta"],
    "Athletic Club": ["Athletic Bilbao","Athletic"],
    "Rayo Vallecano": ["Rayo"],
    "Bodø/Glimt": ["Bodo/Glimt","FK Bodo/Glimt"],
    "Sporting CP": ["Sporting","Sporting de Portugal"],
    "Red Star Belgrade": ["Crvena zvezda"],
}


def _variants(name):
    v = [name] + TEAM_ALIASES.get(name, [])
    clean = re.sub(r'^(FC|CF|CD|RC|FK|AC|AS|SSC|FSV|SD)\s+', '', name).strip()
    if clean != name: v.append(clean)
    return list(dict.fromkeys(v))


def _matches(query, sofa_name):
    q, s = query.lower(), sofa_name.lower()
    if q == s or q in s or s in q: return True
    qw = {w for w in q.split() if len(w) > 3}
    sw = {w for w in s.split() if len(w) > 3}
    return bool(qw & sw)


def _find_event(home, away, timeout=10):
    """Encuentra el partido en SofaScore mediante estrategia insistente."""
    hv, av = _variants(home), _variants(away)
    
    # Estrategia agresiva de insistencia:
    # 1. Combinaciones cruzadas (Fiorentina Inter)
    # 2. Solo local (Fiorentina)
    # 3. Solo visitante (Inter)
    queries = []
    for h in hv[:2]:
        for a in av[:2]:
            queries.append(f"{h} {a}")
    queries.extend(hv[:2])
    queries.extend(av[:2])
    
    # Limpiar duplicados manteniendo el orden
    unique_queries = []
    for q in queries:
        if q not in unique_queries:
            unique_queries.append(q)

    for q in unique_queries:
        try:
            r = requests.get(
                f"https://api.sofascore.com/api/v1/search/events?q={requests.utils.quote(q)}",
                headers=HEADERS, timeout=timeout
            )
            if r.status_code != 200: continue
            events = r.json().get("events", [])
            for ev in events[:20]:  # Buscar más profundo
                hn = ev.get("homeTeam", {}).get("name", "")
                an = ev.get("awayTeam", {}).get("name", "")
                
                # Check if matches home AND away robustly
                home_match = any(_matches(v, hn) for v in hv) or any(_matches(v, an) for v in hv)
                away_match = any(_matches(v, an) for v in av) or any(_matches(v, hn) for v in av)
                
                if home_match and away_match:
                    print(f"  [SofaScore] Búsqueda Insistente: Partido encontrado con query '{q}': {hn} vs {an}")
                    return ev
        except Exception as e:
            print(f"  [SofaScore] find_event error on '{q}': {e}")
            
    return None


def _expandir_nombre(texto, ini, fin):
    """
    Amplia un tramo de texto a las palabras propias contiguas.

    Partiendo de un arbitro conocido, incorpora las palabras vecinas que van en
    mayuscula o son particulas ("de", "del"), de modo que "Hernandez Hernandez"
    dentro de "Alejandro Hernandez Hernandez" devuelva el nombre completo.
    """
    particulas = {"de", "del", "la"}

    from src.data.referee_database import _NUNCA_NOMBRE

    def es_parte(palabra):
        # Un token terminado en dos puntos, coma o punto y coma es una
        # frontera: "Arbitro: Alejandro ..." no debe absorber "Arbitro".
        if palabra[-1] in ":;,":
            return False
        limpia = palabra.strip(".,;:()[]«»\"'")
        if not limpia or not limpia.replace("-", "").replace("'", "").isalpha():
            return False
        if limpia.lower() in _NUNCA_NOMBRE:
            return False
        return limpia[0].isupper() or limpia.lower() in particulas

    # Tokens con sus posiciones dentro del texto original
    tokens = [(m.start(), m.end(), m.group()) for m in re.finditer(r'\S+', texto)]
    dentro = [i for i, (a, b, _) in enumerate(tokens) if a < fin and b > ini]
    if not dentro:
        return texto[ini:fin]

    primero, ultimo = dentro[0], dentro[-1]
    while primero > 0 and es_parte(tokens[primero - 1][2]) and (ultimo - primero) < 4:
        primero -= 1
    while ultimo < len(tokens) - 1 and es_parte(tokens[ultimo + 1][2]) and (ultimo - primero) < 4:
        ultimo += 1

    # No terminar en particula
    while ultimo > primero and tokens[ultimo][2].lower() in particulas:
        ultimo -= 1

    return texto[tokens[primero][0]:tokens[ultimo][1]].strip(".,;:")


def _extract_from_text(text):
    """
    Extrae el nombre del arbitro de un texto de prensa.

    Los patrones exigen mayuscula inicial en cada palabra del nombre, y por eso
    NO se aplica re.IGNORECASE al conjunto: ese flag anulaba las clases
    [A-ZAEIOUN][a-zaeioun]+ y hacia que cualquier palabra en minuscula valiera
    como nombre. Asi es como la aplicacion llego a mostrar "que no vio" como
    arbitro designado. La insensibilidad a mayusculas se limita a la palabra
    clave mediante (?i:...).

    Devuelve None si lo extraido no tiene forma de nombre propio.
    """
    from src.data.referee_database import es_nombre_plausible

    tl = text.lower()

    # 1. Arbitro conocido como ancla, expandiendo a las palabras propias
    # contiguas. La lista contiene fragmentos ("Hernandez Hernandez",
    # "Ricardo de Burgos"), y devolverlos tal cual truncaba el nombre real.
    coincidencias = [ref for ref in KNOWN_REFEREES if ref.lower() in tl]
    if coincidencias:
        mejor = max(coincidencias, key=len)
        idx = tl.find(mejor.lower())
        completo = _expandir_nombre(text, idx, idx + len(mejor))
        return completo if es_nombre_plausible(completo) else text[idx:idx + len(mejor)]

    # 2. Patrones sobre el texto original, respetando mayusculas
    NOMBRE = r'([A-ZÁÉÍÓÚÑ][a-záéíóúñ]+(?:\s+(?:de|del|la)\s+|\s+)[A-ZÁÉÍÓÚÑ][a-záéíóúñ]+(?:\s+[A-ZÁÉÍÓÚÑ][a-záéíóúñ]+)?)'
    patrones = [
        r'(?i:árbitro|arbitro|colegiado)[:\s]+' + NOMBRE,
        r'(?i:pitará|pitara|dirigirá|dirigira|pita|dirige|arbitrará|arbitrara)\s+' + NOMBRE,
        NOMBRE + r'\s+(?i:pitará|pitara|dirigirá|dirigira|será el árbitro|sera el arbitro)',
    ]
    for patron in patrones:
        m = re.search(patron, text)
        if not m:
            continue
        candidato = m.group(1).strip()
        if es_nombre_plausible(candidato):
            return candidato

    return None



# =============================================================================
# FUENTE 1: SofaScore API
# =============================================================================
def fetch_referee(home, away):
    try:
        ev = _find_event(home, away)
        if not ev:
            return None
        eid = ev.get("id")
        r = requests.get(f"https://api.sofascore.com/api/v1/event/{eid}",
                         headers=HEADERS, timeout=8)
        if r.status_code == 200:
            referee = r.json().get("event", {}).get("referee", {})
            name = referee.get("name", "")
            if name and len(name.split()) >= 2:
                return {"name": name, "source": "SofaScore",
                        "verification_link": f"https://www.sofascore.com/es/partido/{eid}",
                        "_is_fallback": False}
            # Partido encontrado pero árbitro no asignado aún
            return {"name": "", "source": "SofaScore",
                    "verification_link": f"https://www.sofascore.com/es/partido/{eid}",
                    "_is_fallback": True}
    except Exception as e:
        print(f"  [SofaScore] referee: {e}")
    return None


# =============================================================================
# FUENTE 2: Google News RSS — busca "árbitro EQUIPO1 EQUIPO2"
# =============================================================================
def fetch_referee_rss(home, away):
    """Busca el árbitro en Google News RSS — mismo método que rss_analyst."""
    queries = [
        f"árbitro {home} {away}",
        f"árbitro partido {home} {away}",
        f"{home} {away} árbitro designado",
        f"referee {home} {away}",
    ]
    for q in queries:
        try:
            url = f"https://news.google.com/rss/search?q={requests.utils.quote(q)}&hl=es&gl=ES&ceid=ES:es"
            r = requests.get(url, headers=RSS_HEADERS, timeout=8)
            if r.status_code != 200:
                continue
            root = ET.fromstring(r.content)
            for item in root.findall('.//item')[:10]:
                title = item.findtext('title', '') or ''
                desc  = item.findtext('description', '') or ''
                name = _extract_from_text(title + ' ' + desc)
                if name:
                    print(f"  [RSS] Árbitro: {name} (de: {title[:50]})")
                    return {"name": name, "source": "Google News",
                            "verification_link": item.findtext('link',''),
                            "_is_fallback": False}
        except Exception as e:
            print(f"  [RSS] {q[:30]}: {e}")
    return None


# =============================================================================
# FUENTE 3: Claude API con web_search (si ANTHROPIC_API_KEY disponible)
# =============================================================================
def fetch_referee_via_claude(home, away, league=""):
    import os, requests as _r, re as _re
    from datetime import datetime as _dt
    api_key = os.environ.get("ANTHROPIC_API_KEY", "")
    if not api_key:
        return None
    try:
        today = _dt.now().strftime("%d/%m/%Y")
        prompt = (
            f"Busca: árbitro {home} {away} hoy {today}\n"
            f"Responde SOLO con el nombre del árbitro. Ejemplo: Martínez Munuera"
        )
        resp = _r.post(
            "https://api.anthropic.com/v1/messages",
            headers={"x-api-key": api_key, "anthropic-version": "2023-06-01",
                     "content-type": "application/json"},
            json={"model": "claude-haiku-4-5-20251001", "max_tokens": 50,
                  "tools": [{"type": "web_search_20250305", "name": "web_search"}],
                  "messages": [{"role": "user", "content": prompt}]},
            timeout=30
        )
        if resp.status_code != 200:
            return None
        full = ""
        for block in resp.json().get("content", []):
            if block.get("type") == "text":
                full += block.get("text", "")
        full = _re.sub(r'[\*\'".,;:\n\r]', ' ', full).strip()
        # Extraer nombre del texto de Claude
        name = _extract_from_text(full)
        if not name:
            # Intentar directamente si la respuesta es corta
            words = full.split()
            if 2 <= len(words) <= 4 and all(w[0].isupper() for w in words if w):
                name = full
        if name:
            print(f"  [Claude] Árbitro: {name}")
            return {"name": name, "source": "Claude API",
                    "verification_link": None, "_is_fallback": False}
    except Exception as e:
        print(f"  [Claude] {e}")
    return None


# =============================================================================
# ALINEACIONES — SofaScore
# =============================================================================
def fetch_lineups(home, away):
    try:
        ev = _find_event(home, away)
        if not ev:
            return None
        eid = ev.get("id")
        r = requests.get(f"https://api.sofascore.com/api/v1/event/{eid}/lineups",
                         headers=HEADERS, timeout=8)
        if r.status_code == 404:
            return {"home": [], "away": [], "source": "SofaScore",
                    "verification_link": f"https://www.sofascore.com/es/partido/{eid}",
                    "_is_fallback": True, "not_available_yet": True}
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
            return result[:11] or [p.get("player",{}).get("name","")
                                    for p in players if p.get("player",{}).get("name")][:11]
        hp, ap = _extract("home"), _extract("away")
        if hp or ap:
            is_live = ev.get("status", {}).get("type", "") in ["inprogress", "finished"]
            return {"home": hp, "away": ap, "source": "SofaScore",
                    "verification_link": f"https://www.sofascore.com/es/partido/{eid}",
                    "_is_fallback": False, "is_official": is_live}
    except Exception as e:
        print(f"  [SofaScore] lineups: {e}")
    return None
