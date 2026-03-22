import sys
import os
from datetime import datetime

# Add project root to path
sys.path.append(os.getcwd())

from src.data.multi_source_fetcher import MultiSourceFetcher
from src.logic.lineup_fetcher import LineupFetcher

class MockDataProvider:
    def get_team_data(self, name): return None
    def get_last_match_lineup(self, name): return []

def test_fetches():
    print("Testing Referee Fetching...")
    fetcher = MultiSourceFetcher()
    
    # Test La Liga (Real Madrid vs Barcelona - classic example)
    print("\nTesting La Liga Referee (Real Madrid vs Barcelona):")
    res = fetcher.fetch_referee("Real Madrid", "Barcelona", datetime.now(), "La Liga")
    print(f"Result: {res}")
    
    print("\nTesting Lineup Fetching (Real Madrid vs Barcelona):")
    lu = fetcher.fetch_lineup("Real Madrid", "Barcelona", datetime.now(), "La Liga")
    print(f"Lineup Result: {len(lu.get('home', []))} home players, {len(lu.get('away', []))} away players")
    print(f"Source: {lu.get('source')}")

if __name__ == "__main__":
    try:
        test_fetches()
    except Exception as e:
        print(f"Error during test: {e}")
