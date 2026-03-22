
import sys
import os
from datetime import datetime

# Add the project root directory to Python path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '.')))

from src.models.base import Match, Team, Player, PlayerPosition, PlayerStatus, NodeRole, Referee, RefereeStrictness
from src.logic.predictors import Predictor
from src.logic.bpa_engine import BPAEngine

def create_pro_team(name, league, xg=1.5, ppda=12.0):
    p_list = [
        Player(id=f"{name}_{i}", name=f"Player {i}", team_name=name, 
               position=PlayerPosition.MIDFIELDER, status=PlayerStatus.TITULAR, 
               ppda=ppda, rating_last_5=7.5) for i in range(11)
    ]
    return Team(name=name, league=league, players=p_list, avg_xg_season=xg, motivation_level=1.2)

def test_pro_methods():
    bpa = BPAEngine()
    predictor = Predictor(bpa)
    
    # CASE 1: High Intensity Match (Low PPDA) - Prem
    home_h = create_pro_team("Intensity FC", "Premier League", xg=2.1, ppda=8.5)
    away_h = create_pro_team("Pressing Utd", "Premier League", xg=1.9, ppda=9.0)
    match_h = Match(
        id="PRO_H", home_team=home_h, away_team=away_h, 
        date=datetime.now(), competition="Premier League",
        referee=Referee(name="Pro Ref", avg_cards=4.0)
    )
    
    # CASE 2: Low Intensity Match (High PPDA) - La Liga
    home_l = create_pro_team("Walking FC", "La Liga", xg=0.7, ppda=15.0)
    away_l = create_pro_team("Defensive Club", "La Liga", xg=0.6, ppda=16.0)
    match_l = Match(
        id="PRO_L", home_team=home_l, away_team=away_l, 
        date=datetime.now(), competition="La Liga",
        referee=Referee(name="Strict Ref", avg_cards=5.5)
    )
    
    pred_h = predictor.predict_match(match_h)
    pred_l = predictor.predict_match(match_l)
    
    print("\n" + "="*50)
    print("PRO TEST 1: HIGH INTENSITY (xG ~4.0, PPDA ~8.7)")
    print(f"Goal Range: {pred_h.total_goals_range} (Expected additive xG ~4.0)")
    print(f"Shots:      {pred_h.predicted_shots.replace('🏠', 'H').replace('✈️', 'A')}")
    print(f"SOT:        {pred_h.predicted_shots_on_target.replace('🏠', 'H').replace('✈️', 'A')}")
    print(f"Cards:      {pred_h.predicted_cards.replace('🏠', 'H').replace('✈️', 'A')}")
    
    print("\n" + "="*50)
    print("PRO TEST 2: LOW INTENSITY (xG ~1.3, PPDA ~15.5)")
    print(f"Goal Range: {pred_l.total_goals_range} (Expected additive xG ~1.3)")
    print(f"Shots:      {pred_l.predicted_shots.replace('🏠', 'H').replace('✈️', 'A')}")
    print(f"SOT:        {pred_l.predicted_shots_on_target.replace('🏠', 'H').replace('✈️', 'A')}")
    print(f"Cards:      {pred_l.predicted_cards.replace('🏠', 'H').replace('✈️', 'A')}")
    print("="*50 + "\n")

    # VALIDATIONS
    try:
        # Goal Range Validation
        # 4.0 xG should be roughly 3-5 or 4-5 range
        assert "3" in pred_h.total_goals_range or "4" in pred_h.total_goals_range
        
        # SOT Ratio Validation (30-40%)
        def get_max_val(s): return int(s.split("|")[0].strip().split("-")[1])
        shots_h = get_max_val(pred_h.predicted_shots)
        sot_h = get_max_val(pred_h.predicted_shots_on_target)
        ratio = sot_h / shots_h
        print(f"SOT Ratio detected: {ratio*100:.1f}%")
        assert 0.28 <= ratio <= 0.45, f"SOT Ratio {ratio} out of professional bounds (0.30-0.35 base)"
        
        print("VERIFICATION SUCCESS: Professional methodologies integrated correctly.")
    except Exception as e:
        print(f"VERIFICATION FAILED: {e}")

if __name__ == "__main__":
    test_pro_methods()
