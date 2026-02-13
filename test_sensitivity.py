
import sys
import os
sys.path.append(os.getcwd())

from src.models.base import Team, Match, MatchConditions, Referee, RefereeStrictness, Player, PlayerPosition, NodeRole, PlayerStatus
from src.logic.predictors import Predictor
from src.logic.bpa_engine import BPAEngine
from datetime import datetime

def create_mock_team(name, xg_val):
    players = []
    for i in range(11):
        players.append(Player(
            id=f"{name}_{i}", name=f"{name} Player {i}", team_name=name,
            position=PlayerPosition.FORWARD, node_role=NodeRole.FINALIZER,
            status=PlayerStatus.TITULAR, rating_last_5=7.5, goals_xg_last_5=xg_val
        ))
    return Team(name=name, league="Test League", players=players)

bpa = BPAEngine()
predictor = Predictor(bpa)

# Case 1: Strong Home vs Weak Away, Strict Referee
home = create_mock_team("StrongCity", 2.5)
away = create_mock_team("WeakTown", 0.5)
conds = MatchConditions(temperature=20, rain_mm=0, wind_kmh=5, humidity_percent=50)

match1 = Match(
    id="m1", home_team=home, away_team=away, date=datetime.now(),
    competition="Test", referee=Referee(name="StrictRef", strictness=RefereeStrictness.HIGH),
    conditions=conds
)

# Case 2: Same Match, Permissive Referee
match2 = Match(
    id="m2", home_team=home, away_team=away, date=datetime.now(),
    competition="Test", referee=Referee(name="LaxRef", strictness=RefereeStrictness.LOW),
    conditions=conds
)

res1 = predictor.predict_match(match1)
res2 = predictor.predict_match(match2)

print(f"--- CASE 1: STRICT REF ---")
print(f"Goals: {res1.predicted_goals_home} vs {res1.predicted_goals_away}")
print(f"Corners: {res1.predicted_corners_home} vs {res1.predicted_corners_away}")
print(f"Cards: {res1.predicted_cards_home} vs {res1.predicted_cards_away}")
print(f"Shots: {res1.predicted_shots_home} vs {res1.predicted_shots_away}")

print(f"\n--- CASE 2: PERMISSIVE REF ---")
print(f"Cards: {res2.predicted_cards_home} vs {res2.predicted_cards_away}")

if res1.predicted_cards_home != res2.predicted_cards_home:
    print("\n✅ VARIABILITY DETECTED: Cards changed with referee!")
else:
    print("\n❌ NO VARIABILITY: Cards remained same despite referee change.")
