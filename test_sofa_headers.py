"""Test alternative SofaScore headers and endpoint variations."""
import requests

# Test different header combinations
tests = [
    ("Mobile App headers", {
        'User-Agent': 'SofaScore/167 CFNetwork/1399 Darwin/22.1.0',
        'Accept': 'application/json',
        'X-EventId': '1',
    }),
    ("Browser + Origin", {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36',
        'Accept': 'application/json, text/plain, */*',
        'Accept-Language': 'en-US,en;q=0.9',
        'Origin': 'https://www.sofascore.com',
        'Referer': 'https://www.sofascore.com/',
        'Cache-Control': 'no-cache',
    }),
    ("Curl-like", {
        'User-Agent': 'curl/7.68.0',
        'Accept': '*/*',
    }),
]

url = 'https://api.sofascore.com/api/v1/sport/football/scheduled-events/2026-03-14'

for name, headers in tests:
    print(f"\n--- {name} ---")
    try:
        r = requests.get(url, headers=headers, timeout=8)
        print(f"Status: {r.status_code}")
        if r.status_code == 200:
            events = r.json().get('events', [])
            print(f"Events: {len(events)}")
            for ev in events[:2]:
                print(f"  {ev.get('homeTeam', {}).get('name')} vs {ev.get('awayTeam', {}).get('name')}")
        else:
            print(f"Body: {r.text[:150]}")
    except Exception as e:
        print(f"Error: {e}")

# Test the public SofaScore app API endpoint 
print("\n--- Public app endpoint ---")
r2 = requests.get(
    'https://www.sofascore.com/api/v1/sport/football/scheduled-events/2026-03-14',
    headers={'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'},
    timeout=8
)
print(f"Status: {r2.status_code}")
if r2.status_code == 200:
    j = r2.json()
    events = j.get('events', [])
    print(f"Events: {len(events)}")
