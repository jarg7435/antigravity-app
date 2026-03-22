from datetime import datetime
from src.data.scrapers.la_liga import fetch_lineup_futbolfantasy, fetch_lineup_rf

def test_lineups():
    home = "Rayo Vallecano"
    away = "Athletic Club"
    
    print(f"--- Testing FutbolFantasy for {home} vs {away} ---")
    ff_res = fetch_lineup_futbolfantasy(home, away)
    print(f"Result: {ff_res}")
    
    print(f"\n--- Testing Resultados-Futbol for {home} vs {away} ---")
    rf_res = fetch_lineup_rf(home, away)
    print(f"Result: {rf_res}")

if __name__ == "__main__":
    test_lineups()
