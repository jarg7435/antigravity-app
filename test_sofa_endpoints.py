"""Test des endpoints de SofaScore API."""
import requests
import json
from datetime import date

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36',
    'Accept': 'application/json',
    'Accept-Language': 'es-ES,es;q=0.9',
    'Referer': 'https://www.sofascore.com/',
}

print("=== TEST: /search/teams ===")
r = requests.get('https://api.sofascore.com/api/v1/search/teams?q=Bayern&limit=5', headers=HEADERS, timeout=10)
print(f'Status: {r.status_code}')
if r.status_code == 200:
    teams = r.json().get('teams', [])
    print(f'Equipos encontrados: {len(teams)}')
    for t in teams[:3]:
        print(f'  ID={t.get("id")}, Name={t.get("name")}, Sport={t.get("sport", {}).get("name")}')
else:
    print(f'Body: {r.text[:300]}')

print()
today = date.today().isoformat()
print(f"=== TEST: /scheduled-events/{today} ===")
r2 = requests.get(f'https://api.sofascore.com/api/v1/sport/football/scheduled-events/{today}', headers=HEADERS, timeout=10)
print(f'Status: {r2.status_code}')
if r2.status_code == 200:
    events = r2.json().get('events', [])
    print(f'Eventos hoy: {len(events)}')
    for ev in events[:5]:
        hn = ev.get("homeTeam", {}).get("name", "?")
        an = ev.get("awayTeam", {}).get("name", "?")
        league = ev.get("tournament", {}).get("name", "?")
        print(f'  {hn} vs {an} | Liga: {league}')
else:
    print(f'Body: {r2.text[:300]}')

# Test get team by ID (FC Koln = 1053)
print()
print("=== TEST: /team/1053/events/next/5 ===")
r3 = requests.get('https://api.sofascore.com/api/v1/team/1053/events/next/5', headers=HEADERS, timeout=10)
print(f'Status: {r3.status_code}')
if r3.status_code == 200:
    events = r3.json().get('events', [])
    print(f'Eventos: {len(events)}')
    for ev in events[:3]:
        hn = ev.get("homeTeam", {}).get("name", "?")
        an = ev.get("awayTeam", {}).get("name", "?")
        print(f'  {hn} vs {an}')
else:
    print(f'Body: {r3.text[:200]}')
