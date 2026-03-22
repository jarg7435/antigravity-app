"""
test_team_matching.py - Verifica que los nombres de equipos en español
se resuelven correctamente en SofaScore (árbitros y alineaciones).
Ejecutar con: python test_team_matching.py
"""
import sys
import os
sys.path.insert(0, os.path.dirname(__file__))

from src.data.scrapers.sofascore_api import (
    _get_variants, _team_matches, _find_sofa_event, fetch_referee, fetch_lineups
)

# =========================================================
# Partidos de prueba (usando nombres como los escribe el usuario en la app)
# =========================================================
TEST_MATCHES = [
    # Bundesliga
    ("Colonia",       "Bayer Leverkusen",  "Bundesliga"),
    ("Bayern Munich", "Dortmund",           "Bundesliga"),
    ("RB Leipzig",    "Frankfurt",          "Bundesliga"),
    # La Liga
    ("Real Madrid",   "FC Barcelona",       "La Liga"),
    ("Atletico Madrid","Sevilla FC",         "La Liga"),
    # Serie A
    ("AC Milan",      "Napoles",            "Serie A"),
    ("Inter Milan",   "AS Roma",            "Serie A"),
    # Premier League
    ("Arsenal",       "Manchester City",    "Premier League"),
    ("Tottenham",     "Chelsea",            "Premier League"),
    # Ligue 1
    ("PSG",           "Lyon",              "Ligue 1"),
]

def separator(title):
    print(f"\n{'='*60}")
    print(f"  {title}")
    print('='*60)

def test_aliases():
    separator("1. ALIAS Y VARIANTES DE NOMBRES")
    tests = [
        ("Colonia", ["FC Köln", "Cologne", "Köln"]),
        ("Napoles", ["Napoli", "SSC Napoli"]),
        ("Bayern Munich", ["Bayern München", "FC Bayern"]),
        ("Inter Milan", ["Inter", "FC Internazionale"]),
        ("Dortmund", ["Borussia Dortmund", "BVB"]),
    ]
    for name, expected in tests:
        variants = _get_variants(name)
        hits = [e for e in expected if any(e in v for v in variants)]
        ok = len(hits) == len(expected)
        print(f"  {'✅' if ok else '❌'} {name:25} → {variants}")

def test_matching():
    separator("2. NORMALIZACIÓN DE ACENTOS Y MATCHING")
    pairs = [
        ("Colonia",      "FC Köln",           True),
        ("Bayern Munich","Bayern München",      True),
        ("Napoles",      "Napoli",             True),  # via alias
        ("Real Madrid",  "Real Madrid",         True),
        ("Dortmund",     "Borussia Dortmund",   True),
        ("Man City",     "Manchester City",     False),  # should NOT match (alias needed)
    ]
    for q, s, expected in pairs:
        result = _team_matches(q, s)
        ok = result == expected
        print(f"  {'✅' if ok else '❌'} '{q}' vs '{s}' → {result} (esperado: {expected})")

def test_sofa_events():
    separator("3. BÚSQUEDA DE EVENTOS EN SOFASCORE (requiere internet)")
    for home, away, league in TEST_MATCHES:
        try:
            ev = _find_sofa_event(home, away)
            if ev:
                hn = ev.get("homeTeam", {}).get("name", "?")
                an = ev.get("awayTeam", {}).get("name", "?")
                status = ev.get("status", {}).get("type", "?")
                eid = ev.get("id", "?")
                print(f"  ✅ [{league}] {home} vs {away}")
                print(f"     → SofaScore: {hn} vs {an} | Status: {status} | ID: {eid}")
            else:
                print(f"  ❌ [{league}] {home} vs {away} → NO ENCONTRADO")
        except Exception as e:
            print(f"  ⚠️  [{league}] {home} vs {away} → ERROR: {e}")

def test_referees():
    separator("4. BÚSQUEDA DE ÁRBITROS (muestra de 3 partidos)")
    sample = TEST_MATCHES[:4]
    for home, away, league in sample:
        try:
            ref = fetch_referee(home, away)
            if ref:
                name = ref.get("name", "?")
                source = ref.get("source", "?")
                link = ref.get("verification_link", "")
                print(f"  [{league}] {home} vs {away}")
                print(f"     → Árbitro: {name} | Fuente: {source}")
                if link:
                    print(f"     → Link: {link}")
            else:
                print(f"  ❌ [{league}] {home} vs {away} → Sin árbitro")
        except Exception as e:
            print(f"  ⚠️  [{league}] {home} vs {away} → ERROR: {e}")

if __name__ == "__main__":
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
    print("\n[TEST] LAGEMA --- Test de Resolucion de Equipos y Arbitros")
    print("=" * 60)
    test_aliases()
    test_matching()
    test_sofa_events()
    test_referees()
    print("\n[OK] Test finalizado.")
