import sys
import os
from datetime import datetime

# Add project root to path
sys.path.append(os.getcwd())

from src.models.base import Match, Team, Player, PlayerPosition, PlayerStatus, MatchConditions, Referee, RefereeStrictness
from src.data.mock_provider import MockDataProvider

def reproduce():
    data_provider = MockDataProvider()
    home_team = data_provider.get_team_data("FC Barcelona")
    away_team = data_provider.get_team_data("Real Madrid")
    
    m_id = "repro_match"
    selected_date = datetime.now().date()
    selected_time = "21:00"
    selected_league = "La Liga"
    
    selected_ref = Referee(name="Test Ref", strictness=RefereeStrictness.MEDIUM)
    
    try:
        full_match_datetime = datetime.combine(selected_date, datetime.strptime(selected_time, "%H:%M").time())
    except Exception as e:
        print(f"Error combining datetime: {e}")
        full_match_datetime = datetime.now()

    print(f"Instantiating Match with date type: {type(full_match_datetime)}")
    
    try:
        selected_match = Match(
            id=m_id, 
            home_team=home_team, 
            away_team=away_team, 
            date=full_match_datetime, 
            kickoff_time=selected_time, 
            competition=selected_league,
            conditions=MatchConditions(temperature=15, rain_mm=0, wind_kmh=10, humidity_percent=60),
            referee=selected_ref,
            market_odds={"1": 2.10, "X": 3.40, "2": 4.50}
        )
        print("SUCCESS: Match instantiated successfully!")
    except Exception as e:
        print("FAILURE: Validation failed!")
        import traceback
        traceback.print_exc()
        if hasattr(e, 'errors'):
            print("Pydantic Errors:")
            import json
            print(json.dumps(e.errors(), indent=2))

if __name__ == "__main__":
    reproduce()
