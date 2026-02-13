
import sys
import os
from datetime import datetime
sys.path.append(os.path.abspath(os.curdir))

from src.logic.predictors import Predictor
from src.logic.bpa_engine import BPAEngine
from src.models.base import Match, Team, Player, PlayerPosition, PlayerStatus, MatchConditions, Referee, RefereeStrictness

def test_full_prediction():
    bpa_engine = BPAEngine()
    predictor = Predictor(bpa_engine)
    
    # Create manual teams exactly like main.py
    h_name = "Equipo Local FC"
    p_list_h = [Player(id=f"h{i}", name=f"Jugador {i}", team_name=h_name, position=PlayerPosition.MIDFIELDER, status=PlayerStatus.TITULAR, rating_last_5=7.0) for i in range(11)]
    home_team = Team(name=h_name, league="Manual", players=p_list_h, tactical_style="Equilibrado")
    
    a_name = "Rival FC"
    p_list_a = [Player(id=f"a{i}", name=f"Jugador {i}", team_name=a_name, position=PlayerPosition.MIDFIELDER, status=PlayerStatus.TITULAR, rating_last_5=7.0) for i in range(11)]
    away_team = Team(name=a_name, league="Manual", players=p_list_a, tactical_style="Contragolpe")
    
    match = Match(
        id="test_match",
        home_team=home_team,
        away_team=away_team,
        date=datetime.now(),
        kickoff_time="21:00",
        competition="Liga Extra (Manual)",
        conditions=MatchConditions(temperature=15, rain_mm=0, wind_kmh=10, humidity_percent=60),
        referee=Referee(name="Por Detectar", strictness=RefereeStrictness.MEDIUM),
        market_odds={"1": 2.10, "X": 3.40, "2": 4.50}
    )
    
    print(f"--- RUNNING PREDICT_MATCH ---")
    result = predictor.predict_match(match)
    
    print(f"total_goals_expected: {result.total_goals_expected}")
    print(f"both_teams_to_score_prob: {result.both_teams_to_score_prob}")
    print(f"score_prediction: {result.score_prediction}")
    print(f"Win Probs: H={result.win_prob_home}, D={result.draw_prob}, A={result.win_prob_away}")
    
    top_5 = sorted(result.poisson_matrix.items(), key=lambda x: x[1], reverse=True)[:5]
    print(f"Top 5 Poisson: {top_5}")

if __name__ == "__main__":
    test_full_prediction()
