
import sys
import os
from datetime import datetime

# Add the project root directory to Python path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '.')))

from src.models.base import Match, Team, Player, PlayerPosition, PlayerStatus, MatchConditions, Referee, RefereeStrictness
from src.logic.predictors import Predictor
from src.logic.bpa_engine import BPAEngine

def create_mock_team(name, league, xg=1.35):
    p_list = [
        Player(id=f"{name}_{i}", name=f"Player {i}", team_name=name, 
               position=PlayerPosition.MIDFIELDER, status=PlayerStatus.TITULAR, 
               rating_last_5=7.5) for i in range(11)
    ]
    return Team(name=name, league=league, players=p_list, avg_xg_season=xg)

def test_predictions():
    bpa = BPAEngine()
    predictor = Predictor(bpa)
    
    # Scenario 1: Premier League - High xG Match (Man City vs Liverpool)
    home_pl = create_mock_team("Man City", "Premier League", xg=2.5)
    away_pl = create_mock_team("Liverpool", "Premier League", xg=2.3)
    match_pl = Match(
        id="PL_HIGH_XG", home_team=home_pl, away_team=away_pl, 
        date=datetime.now(), competition="Premier League",
        referee=Referee(name="Michael Oliver", avg_cards=3.5, strictness=RefereeStrictness.LOW)
    )
    
    # Scenario 2: La Liga - Low xG Match (Getafe vs Mallorca) - Strict Ref
    home_la = create_mock_team("Getafe", "La Liga", xg=0.8)
    away_la = create_mock_team("Mallorca", "La Liga", xg=0.7)
    match_la = Match(
        id="LA_LOW_XG", home_team=home_la, away_team=away_la, 
        date=datetime.now(), competition="La Liga",
        referee=Referee(name="Gil Manzano", avg_cards=6.2, strictness=RefereeStrictness.HIGH)
    )
    
    pred_pl = predictor.predict_match(match_pl)
    pred_la = predictor.predict_match(match_la)
    
    print("\n" + "="*50)
    print("SCENARIO 1: PREMIER LEAGUE (High xG, Permissive Ref)")
    print(f"Teams: {match_pl.home_team.name} vs {match_pl.away_team.name}")
    print(f"Expected Goals (Lambdas Sum): {pred_pl.total_goals_expected}")
    print(f"Corners: {pred_pl.predicted_corners.replace('🏠', 'H').replace('✈️', 'A')}")
    print(f"Cards:   {pred_pl.predicted_cards.replace('🏠', 'H').replace('✈️', 'A')}")
    print(f"Shots:   {pred_pl.predicted_shots.replace('🏠', 'H').replace('✈️', 'A')}")
    print(f"Ref:     {match_pl.referee.name} (Avg Cards: {match_pl.referee.avg_cards})")
    
    print("\n" + "="*50)
    print("SCENARIO 2: LA LIGA (Low xG, Strict Ref)")
    print(f"Teams: {match_la.home_team.name} vs {match_la.away_team.name}")
    print(f"Expected Goals (Lambdas Sum): {pred_la.total_goals_expected}")
    print(f"Corners: {pred_la.predicted_corners.replace('🏠', 'H').replace('✈️', 'A')}")
    print(f"Cards:   {pred_la.predicted_cards.replace('🏠', 'H').replace('✈️', 'A')}")
    print(f"Shots:   {pred_la.predicted_shots.replace('🏠', 'H').replace('✈️', 'A')}")
    print(f"Ref:     {match_la.referee.name} (Avg Cards: {match_la.referee.avg_cards})")
    print("="*50 + "\n")

    # Basic Validations
    try:
        # PL should have more shots/corners than La Liga in these scenarios
        h_shots_pl = int(pred_pl.predicted_shots.split("|")[0].strip().split("-")[1])
        h_shots_la = int(pred_la.predicted_shots.split("|")[0].strip().split("-")[1])
        assert h_shots_pl > h_shots_la, f"Expected more shots in PL high xG match ({h_shots_pl}) than La Liga low xG match ({h_shots_la})"
        
        # La Liga should have more cards due to ref and league baseline
        h_cards_la = int(pred_la.predicted_cards.split("|")[0].strip().split("-")[1])
        h_cards_pl = int(pred_pl.predicted_cards.split("|")[0].strip().split("-")[1])
        assert h_cards_la > h_cards_pl, f"Expected more cards in La Liga with Gil Manzano ({h_cards_la}) than PL with Oliver ({h_cards_pl})"
        
        print("VERIFICATION SUCCESS: Predictions vary realistically based on match context.")
    except AssertionError as e:
        print(f"❌ VERIFICATION FAILED: {e}")

if __name__ == "__main__":
    test_predictions()
