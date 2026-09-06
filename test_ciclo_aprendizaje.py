# -*- coding: utf-8 -*-
"""
Ciclo completo sobre una BD temporal: predecir -> guardar -> registrar
resultado -> comprobar que la calibracion se dispara sola y se aplica.
"""
import io, os, sys, tempfile, shutil
sys.path.insert(0, os.path.abspath("."))
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

from datetime import datetime

fallos = []
def check(d, c):
    print(("  OK   " if c else "  FALLA") + f"  {d}")
    if not c: fallos.append(d)

tmp = tempfile.mkdtemp()
ruta = os.path.join(tmp, "prueba.db")

from src.data.db_manager import DataManager
from src.data.mock_provider import MockDataProvider
from src.logic.bpa_engine import BPAEngine
from src.logic.learning_engine import LearningEngine
from src.logic.calibracion import CalibradorGoles, MUESTRAS_MINIMAS
from src.models.base import MatchOutcome, PredictionResult

db = DataManager(db_path=ruta)
le = LearningEngine(BPAEngine(), db)

print("== 1. El calibrador arranca neutro ==")
check("factores neutros sin historial", le.calibrador.factores() == (1.0, 1.0))

print("\n== 2. Se registran partidos en los que el modelo estimo LARGO ==")
# El modelo decia 2.0-1.6 y siempre acabo 1-0: estima de mas.
for i in range(MUESTRAS_MINIMAS + 4):
    mid = f"p{i}"
    db.save_prediction(PredictionResult(
        match_id=mid, bpa_home=.5, bpa_away=.5,
        win_prob_home=.5, draw_prob=.3, win_prob_away=.2,
        total_goals_expected=3.6, both_teams_to_score_prob=.5,
        lambda_home=2.0, lambda_away=1.6,
        predicted_corners="🏠 4-6 | ✈️ 3-5", predicted_cards="🏠 2-4 | ✈️ 2-3",
        predicted_shots="🏠 10-14 | ✈️ 8-12",
    ))
    le.process_result(
        db.get_prediction(mid),
        MatchOutcome(match_id=mid, home_score=1, away_score=0,
                     home_corners=5, away_corners=4, home_cards=2, away_cards=2,
                     home_shots=11, away_shots=9, actual_winner="LOCAL"),
        "Equipo A", "Equipo B", "La Liga")

print("\n== 3. La calibracion se ha disparado sola ==")
cal = CalibradorGoles(db)
est = cal.estado()
print("   ", {k: (round(v, 4) if isinstance(v, float) else v) for k, v in est.items()})
check("hay calibracion activa", est["activa"])
check(f"factor local < 1 ({est['factor_local']:.4f}) — estimaba de mas",
      est["factor_local"] < 1.0)
check(f"factor visitante < 1 ({est['factor_visitante']:.4f})",
      est["factor_visitante"] < 1.0)
check(f"usa las {est['muestras']} muestras", est["muestras"] >= MUESTRAS_MINIMAS)
check("detecta el sesgo positivo (largo)", (est["sesgo_local"] or 0) > 0)

print("\n== 4. El informe al usuario lo cuenta ==")
texto = le._recalibrar_goles()
print("   ", texto[:200])
check("el informe menciona el ajuste", "factor" in texto.lower())

print("\n== 5. Un predictor nuevo aplica ya esa correccion ==")
from src.logic.predictors import Predictor
from src.models.base import Match, MatchConditions, Referee
prov = MockDataProvider()
local, visit = prov.teams_db["Athletic Club"], prov.teams_db["Alavés"]

pred_engine = Predictor(BPAEngine())
pred_engine.calibrador = CalibradorGoles(db)      # apuntando a la BD de prueba
partido = Match(id="nuevo", home_team=local.model_dump(), away_team=visit.model_dump(),
                date=datetime(2026, 9, 6, 21, 0), competition="La Liga",
                conditions=MatchConditions(), referee=Referee(name="X"))
con_cal = pred_engine.predict_match(partido)

pred_neutro = Predictor(BPAEngine())
pred_neutro.calibrador = None                      # sin calibracion
sin_cal = pred_neutro.predict_match(partido)

print(f"    sin calibrar: {sin_cal.lambda_home:.3f}-{sin_cal.lambda_away:.3f}")
print(f"    calibrado   : {con_cal.lambda_home:.3f}-{con_cal.lambda_away:.3f}")
check("el modelo calibrado estima MENOS goles", con_cal.lambda_home < sin_cal.lambda_home)
check("y tambien del lado visitante", con_cal.lambda_away < sin_cal.lambda_away)

shutil.rmtree(tmp, ignore_errors=True)
print("\n" + ("TODO OK" if not fallos else f"FALLAN {len(fallos)}: {fallos}"))
sys.exit(1 if fallos else 0)
