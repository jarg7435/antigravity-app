"""
test_multi_league.py — Verificación de fuentes en múltiples ligas europeas
==========================================================================
Valida que la cascada (FF -> BeSoccer -> WorldFootball -> RSS) 
funcione para ligas principales y secundarias sugeridas por el usuario.
"""
import sys
from datetime import datetime
sys.path.insert(0, '.')
from src.data.multi_source_fetcher import MultiSourceFetcher

def test_match(home, away, league, date=None):
    print(f"\n{'='*60}")
    print(f" TEST: {home} vs {away} ({league})")
    print(f"{'='*60}")
    
    msf = MultiSourceFetcher()
    match_date = date or datetime.now()
    
    # 1. Probar Árbitro
    ref = msf.fetch_referee(home, away, match_date, league)
    print(f" --> ÁRBITRO: {ref.get('name')} | Fuente: {ref.get('source')}")
    if ref.get('avg_yellow'):
        print(f"     Stats: {ref.get('avg_yellow')} amarillas/partido")
    
    # 2. Probar Alineación
    lineup = msf.fetch_lineup(home, away, match_date, league)
    print(f" --> LINEUP: {len(lineup.get('home',[]))} + {len(lineup.get('away',[]))} jugadores")
    print(f"     Fuente: {lineup.get('source')}")

if __name__ == "__main__":
    # Partidos de ejemplo para el fin de semana (simulados si no hay reales hoy)
    test_cases = [
        # Ligas Principales
        ("Real Madrid", "Atletico Madrid", "La Liga"),
        ("Bayern Munich", "Dortmund", "Bundesliga"),
        ("Arsenal", "Manchester City", "Premier League"),
        
        # Ligas Secundarias solicitadas
        ("Bodo/Glimt", "Molde", "Superliga"), # Dinamarca/Noruega
        ("Salzburgo", "Sturm Graz", "Bundesliga AT"), # Austria
        ("Legia Varsovia", "Lech Poznan", "Ekstraklasa"), # Polonia
    ]
    
    for h, a, l in test_cases:
        try:
            test_match(h, a, l)
        except Exception as e:
            print(f"Error en {h}-{a}: {e}")

    print(f"\n{'='*60}")
    print(" VERIFICACIÓN FINALIZADA")
    print(f"{'='*60}")
