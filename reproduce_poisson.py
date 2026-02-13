
import sys
import os
sys.path.append(os.path.abspath(os.path.join(os.curdir)))

from src.logic.poisson_engine import PoissonEngine
from src.models.base import Team, Player, PlayerPosition, PlayerStatus

def test_poisson():
    engine = PoissonEngine()
    
    # Create manual teams
    h_name = "Equipo Local FC"
    p_list_h = [Player(id=f"h{i}", name=f"Jugador {i}", team_name=h_name, position=PlayerPosition.MIDFIELDER, status=PlayerStatus.TITULAR, rating_last_5=7.0) for i in range(11)]
    home_team = Team(name=h_name, league="Manual", players=p_list_h, tactical_style="Equilibrado")
    
    a_name = "Rival FC"
    p_list_a = [Player(id=f"a{i}", name=f"Jugador {i}", team_name=a_name, position=PlayerPosition.MIDFIELDER, status=PlayerStatus.TITULAR, rating_last_5=7.0) for i in range(11)]
    away_team = Team(name=a_name, league="Manual", players=p_list_a, tactical_style="Contragolpe")
    
    print(f"--- TESTING ESTIMATE_LAMBDAS ---")
    h_lambda, a_lambda = engine.estimate_lambdas(home_team, away_team)
    print(f"Lambdas: {h_lambda}, {a_lambda}")
    
    print(f"--- TESTING SCORE MATRIX ---")
    matrix = engine.predict_score_matrix(h_lambda, a_lambda)
    print(f"Matrix 0-0: {matrix.get('0-0')}")
    
    print(f"--- TESTING PROBABILITIES ---")
    p_h, p_d, p_a = engine.calculate_match_probabilities(h_lambda, a_lambda)
    print(f"Probs: H={p_h}, D={p_d}, A={p_a}")

if __name__ == "__main__":
    test_poisson()
