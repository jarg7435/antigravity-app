"""
test_api_connection.py — Verifica la conexión con las 3 APIs
=============================================================
Ejecutar desde la raíz del proyecto:
  python test_api_connection.py
  
Este script prueba:
  1. API-Football (auto-detecta Direct vs RapidAPI)
  2. football-data.org
  3. Sportmonks
  
Y verifica que se pueden obtener:
  - Fixtures de La Liga
  - Árbitros de un partido
  - Alineaciones de un partido
"""

import os
import sys
from dotenv import load_dotenv

# Asegurar path correcto
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

load_dotenv()

def test_api_football_key_detection():
    """Test 1: Auto-detección del tipo de API key"""
    from src.data.api_manager import _detect_api_key_type
    
    key = os.environ.get("API_FOOTBALL_KEY", "")
    key_type = _detect_api_key_type(key)
    
    print(f"\n{'='*60}")
    print(f"🔍 API Key Detection")
    print(f"{'='*60}")
    print(f"  Key (últimos 8): ...{key[-8:]}" if key else "  ❌ Sin API key")
    print(f"  Tipo detectado: {key_type}")
    
    return key_type

def test_api_football():
    """Test 2: Conexión con API-Football"""
    print(f"\n{'='*60}")
    print(f"⚽ API-Football Test")
    print(f"{'='*60}")
    
    from src.data.api_manager import APIFootballClient
    
    client = APIFootballClient()
    print(f"  Modo configurado: {client.key_type}")
    print(f"  Endpoint: {client.BASE_URL}")
    print(f"  Headers: {list(client.session.headers.keys())}")
    
    # Probe
    mode = client._probe_connection()
    print(f"  Modo funcional: {mode}")
    
    if mode == "failed":
        print(f"  ❌ API-Football NO DISPONIBLE")
        return False
    
    # Test: obtener fixtures de La Liga
    print(f"\n  📋 Test: Fixtures La Liga (2025-05-10)...")
    fixtures = client.get_fixtures(date="2025-05-10", league_id=140)
    print(f"  Resultados: {len(fixtures)} partidos")
    
    if fixtures:
        for f in fixtures[:3]:
            ht = f.get("teams", {}).get("home", {}).get("name", "?")
            at = f.get("teams", {}).get("away", {}).get("name", "?")
            referee = f.get("fixture", {}).get("referee", "Sin árbitro")
            fid = f.get("fixture", {}).get("id", "?")
            status = f.get("fixture", {}).get("status", {}).get("short", "?")
            print(f"    • {ht} vs {at} (ID={fid}, status={status})")
            print(f"      Árbitro: {referee}")
        
        # Test alineaciones del primer partido
        first_fid = fixtures[0].get("fixture", {}).get("id")
        if first_fid:
            print(f"\n  📋 Test: Alineaciones (fixture_id={first_fid})...")
            lineups = client.get_lineups(first_fid)
            if lineups:
                for lu in lineups:
                    team = lu.get("team", {}).get("name", "?")
                    formation = lu.get("formation", "?")
                    xi = [p.get("player", {}).get("name", "?") for p in lu.get("startXI", [])]
                    print(f"    • {team} ({formation}): {len(xi)} titulares")
                    if xi:
                        print(f"      {', '.join(xi[:5])}...")
            else:
                print(f"    ⚠️ Sin alineaciones (partido no jugado o muy antiguo)")
    else:
        print(f"  ⚠️ No se encontraron partidos (puede ser fecha sin partidos)")
    
    # Test: lista de árbitros
    print(f"\n  👨‍⚖️ Test: Árbitros La Liga...")
    referees = client.get_referees(league_id=140)
    print(f"  Árbitros encontrados: {len(referees)}")
    if referees:
        for ref in referees[:3]:
            print(f"    • {ref.get('name', '?')} ({ref.get('nationality', '?')})")
    
    print(f"\n  ✅ API-Football FUNCIONAL en modo {mode}")
    return True

def test_football_data_org():
    """Test 3: Conexión con football-data.org"""
    print(f"\n{'='*60}")
    print(f"⚽ football-data.org Test")
    print(f"{'='*60}")
    
    from src.data.api_manager import FootballDataClient
    
    client = FootballDataClient()
    key = os.environ.get("FOOTBALL_DATA_API_KEY", "")
    print(f"  Key (últimos 8): ...{key[-8:]}" if key else "  ❌ Sin key")
    
    # Test: obtener partidos de La Liga
    print(f"\n  📋 Test: Partidos La Liga (última semana)...")
    from datetime import datetime, timedelta
    today = datetime.now()
    week_ago = today - timedelta(days=7)
    
    matches = client.get_competition_matches(
        "PD", 
        date_from=week_ago.strftime("%Y-%m-%d"),
        date_to=today.strftime("%Y-%m-%d")
    )
    print(f"  Resultados: {len(matches)} partidos")
    
    if matches:
        for m in matches[:3]:
            ht = m.get("homeTeam", {}).get("shortName", "?")
            at = m.get("awayTeam", {}).get("shortName", "?")
            status = m.get("status", "?")
            refs = m.get("referees", [])
            ref_names = [r.get("name", "?") for r in refs if r.get("role") == "REFEREE"]
            print(f"    • {ht} vs {at} ({status})")
            if ref_names:
                print(f"      Árbitro: {', '.join(ref_names)}")
            else:
                print(f"      Árbitro: (no disponible)")
    else:
        print(f"  ⚠️ Sin partidos encontrados")
    
    print(f"\n  ✅ football-data.org FUNCIONAL")
    return True

def test_sportmonks():
    """Test 4: Conexión con Sportmonks"""
    print(f"\n{'='*60}")
    print(f"⚽ Sportmonks Test")
    print(f"{'='*60}")
    
    from src.data.api_manager import SportmonksClient
    
    client = SportmonksClient()
    key = os.environ.get("SPORTMONKS_API_TOKEN", "")
    print(f"  Key (últimos 8): ...{key[-8:]}" if key else "  ❌ Sin key")
    
    # Test: buscar equipo
    print(f"\n  📋 Test: Buscar 'Real Madrid'...")
    team = client.get_team_by_name("Real Madrid")
    if team:
        print(f"    • Encontrado: {team.get('name', '?')} (ID: {team.get('id', '?')})")
    else:
        print(f"    ⚠️ No encontrado (posible plan limitado)")
    
    # Test: buscar árbitro
    print(f"\n  👨‍⚖️ Test: Buscar árbitro 'Gil Manzano'...")
    ref = client.get_referee_by_name("Gil Manzano")
    if ref:
        print(f"    • Encontrado: {ref.get('name', '?')} / {ref.get('common_name', '?')}")
    else:
        print(f"    ⚠️ No encontrado (posible plan limitado)")
    
    print(f"\n  ✅ Sportmonks FUNCIONAL")
    return True

def test_full_diagnosis():
    """Test completo con APIManager"""
    print(f"\n{'='*60}")
    print(f"🏥 Diagnóstico Completo APIManager")
    print(f"{'='*60}")
    
    from src.data.api_manager import APIManager
    
    api = APIManager()
    diag = api.diagnose()
    
    for api_name, info in diag.items():
        status = info.get("status", "?")
        emoji = "✅" if status == "OK" else "❌"
        print(f"  {emoji} {api_name}: {status}")
        if status == "OK":
            for k, v in info.items():
                if k != "status":
                    print(f"     • {k}: {v}")
        else:
            print(f"     • detail: {info.get('detail', '?')}")

if __name__ == "__main__":
    print("🚀 LAGEMA JARG74 — Test de Conexión APIs")
    print("=" * 60)
    
    try:
        test_api_football_key_detection()
    except Exception as e:
        print(f"❌ Error en detección de key: {e}")
    
    try:
        test_api_football()
    except Exception as e:
        print(f"❌ Error en API-Football: {e}")
    
    try:
        test_football_data_org()
    except Exception as e:
        print(f"❌ Error en football-data.org: {e}")
    
    try:
        test_sportmonks()
    except Exception as e:
        print(f"❌ Error en Sportmonks: {e}")
    
    try:
        test_full_diagnosis()
    except Exception as e:
        print(f"❌ Error en diagnóstico: {e}")
    
    print(f"\n{'='*60}")
    print(f"🏁 Test completado")
