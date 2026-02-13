import pandas as pd
from src.data.mock_provider import MockDataProvider
from src.data.db_manager import DataManager
from src.logic.bpa_engine import BPAEngine
from src.logic.predictors import Predictor
from src.logic.validator import Validator
from src.models.base import Match, MatchConditions

def run_verification():
    print("----- ANTIGRAVITY V6.0 SYSTEM VERIFICATION -----")
    
    # 1. Initialize
    print("[1] Initializing Modules...")
    provider = MockDataProvider()
    db = DataManager()
    bpa = BPAEngine()
    predictor = Predictor(bpa)
    validator = Validator()
    
    # 2. Get Data
    print("[2] Fetching Teams and Creating Match...")
    home_team = provider.get_team_data("Real Madrid")
    away_team = provider.get_team_data("FC Barcelona")
    
    match = Match(
        id="RMA_BAR_20260206",
        home_team=home_team,
        away_team=away_team,
        date=pd.to_datetime("today"),
        competition="La Liga",
        conditions=MatchConditions(temperature=15, rain_mm=0, wind_kmh=10, humidity_percent=60)
    )
    print(f"    Match Created: {match.home_team.name} vs {match.away_team.name}")
    
    # 3. Validation Simulation
    print("[3] Running Blindaje V6.0 check...")
    # Simulate missing 'Vinicius Jr'
    mock_lineup = [p.name for p in match.home_team.players if p.name != "Vinicius Jr"]
    validation = validator.validate_lineup(match.home_team, mock_lineup)
    
    if validation['alerts']:
        print("    Lineup Alerts Triggered (Expected):")
        for a in validation['alerts']:
            print(f"      - {a}")
    else:
        print("ERROR: Validation failed to detect missing player.")
        
    # 4. Prediction
    print("[4] Generating Predictions...")
    result = predictor.predict_match(match)
    print(f"    BPA Home: {result.bpa_home} | BPA Away: {result.bpa_away}")
    print(f"    P1 Win Probs: Home={result.win_prob_home:.2f} Draw={result.draw_prob:.2f} Away={result.win_prob_away:.2f}")
    
    # 5. Database
    print("[5] Saving to Database...")
    try:
        db.save_match(match)
        db.save_prediction(result)
        
        # Verify load
        loaded = db.get_match(match.id)
        if loaded:
            print(f"    Match saved & loaded successfully: {loaded.id}")
        else:
             print("ERROR: Failed to load match from DB.")
             
    except Exception as e:
        print(f"ERROR: Database error: {e}")
        
    print("\n----- VERIFICATION COMPLETE -----")

if __name__ == "__main__":
    run_verification()
