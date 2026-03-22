"""Test de accesibilidad de fuentes alternativas de datos de fútbol."""
import requests

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36',
    'Accept-Language': 'es-ES,es;q=0.9,en;q=0.8',
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
}

sources = [
    ("WorldFootball.net - La Liga jornada", 
     "https://www.worldfootball.net/schedule/esp-primera-division-2025-2026-spieltag/28/"),
    ("WorldFootball.net - Bundesliga",
     "https://www.worldfootball.net/schedule/bundesliga-2025-2026-spieltag/27/"),
    ("WorldFootball.net - Serie A",
     "https://www.worldfootball.net/schedule/ita-serie-a-2025-2026-spieltag/27/"),
    ("BeSoccer - La Liga",
     "https://www.besoccer.com/competition/matches/primera_division/2026"),
    ("BeSoccer - match search",
     "https://www.besoccer.com/match/real-madrid/atletico-madrid/2026"),
    ("FootyStats - La Liga",
     "https://footystats.org/spain/laliga"),
    ("FootyStats - fixtures",
     "https://footystats.org/spain/laliga/fixtures"),
    ("LeagueSpy",
     "https://leaguespy.com/football/fixtures"),
]

for name, url in sources:
    try:
        r = requests.get(url, headers=HEADERS, timeout=10)
        size = len(r.text) if r.status_code == 200 else 0
        print(f"{'OK' if r.status_code == 200 else 'FAIL':4} | {r.status_code} | {size:7d} bytes | {name}")
        if r.status_code == 200 and size > 1000:
            # Show first referee-related mention
            import re
            arb_match = re.search(r'(arbitr|referee|schiedsrichter).{0,80}', r.text, re.I)
            if arb_match:
                print(f"          >> {arb_match.group(0)[:80]}")
    except Exception as e:
        print(f"ERR  | --- | ------- | {name} -> {e}")
