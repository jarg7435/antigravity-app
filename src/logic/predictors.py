from typing import Dict, List, Optional
import pandas as pd
from src.models.base import Match, PredictionResult
from src.logic.bpa_engine import BPAEngine
from src.logic.external_analyst import ExternalAnalyst
from src.logic.poisson_engine import PoissonEngine
from src.logic.ml_engine import MLEngine
from src.logic.value_engine import ValueEngine

class Predictor:
    """
    Motor híbrido que combina BPA, Regresión Poisson y Machine Learning (XGBoost/RF).
    """
    
    def __init__(self, bpa_engine: BPAEngine):
        self.bpa_engine = bpa_engine
        self.external_analyst = ExternalAnalyst()
        self.poisson = PoissonEngine()
        self.ml = MLEngine()
        self.value_engine = ValueEngine()

    def predict_match(self, match: Match) -> PredictionResult:
        # 1. External & Stat Markets (NOW FIRST to calibrate model)
        intel = self.external_analyst.get_detailed_intelligence(match)
        analysis_text = intel["report"]
        press_impact = intel["impact"]

        # 2. BPA Analysis (Adjusted by Intelligence)
        bpa_res = self.bpa_engine.calculate_match_bpa(match, press_modifiers=press_impact)
        bpa_h, bpa_a = bpa_res['home_bpa'], bpa_res['away_bpa']

        # 3. Poisson Statistics (Goals & Lambdas con Integración BPA)
        h_lambda, a_lambda = self.poisson.estimate_lambdas(match.home_team, match.away_team, home_bpa=bpa_h, away_bpa=bpa_a)
        p_matrix = self.poisson.predict_score_matrix(h_lambda, a_lambda)
        p_home, p_draw, p_away = self.poisson.calculate_match_probabilities(h_lambda, a_lambda)

        # 4. Machine Learning (Ensemble classification)
        ml_probs = self.ml.predict_probabilities(None, league=match.competition) 

        # 5. Hybrid Blending (Fusión de modelos — pesos suman 1.0)
        # BPA convierte la ventaja en probabilidad adicional (clamped ±0.20)
        bpa_diff = max(-0.20, min(0.20, (bpa_h - bpa_a) * 0.5))
        bpa_prob_home = max(0.05, 0.35 + bpa_diff)
        bpa_prob_draw = max(0.05, 0.30 - abs(bpa_diff) * 0.3)
        bpa_prob_away = max(0.05, 0.35 - bpa_diff)

        # Pesos: Poisson 50% (más fiable), BPA 30%, ML 20%
        final_home = (p_home * 0.50) + (bpa_prob_home * 0.30) + (ml_probs['LOCAL'] * 0.20)
        final_draw = (p_draw * 0.50) + (bpa_prob_draw * 0.30) + (ml_probs['EMPATE'] * 0.20)
        final_away = (p_away * 0.50) + (bpa_prob_away * 0.30) + (ml_probs['VISITANTE'] * 0.20)

        # Normalize
        total = final_home + final_draw + final_away
        
        # 6. Secondary Markets (using Lambdas for intensity)
        stats = self.external_analyst.calculate_stat_markets(match, bpa_h, bpa_a, h_lambda=h_lambda, a_lambda=a_lambda)
        
        # Determine the most likely score
        score_pred = "0-0"
        if p_matrix:
            score_pred = max(p_matrix, key=p_matrix.get)

        # Robust referee name access
        ref_name = "No asignado"
        if match.referee:
            if isinstance(match.referee, dict):
                ref_name = match.referee.get("name", "No asignado")
            else:
                ref_name = getattr(match.referee, "name", "No asignado")

        pred = PredictionResult(
            match_id=match.id,
            bpa_home=bpa_h,
            bpa_away=bpa_a,
            win_prob_home=round(final_home/total, 4),
            draw_prob=round(final_draw/total, 4),
            win_prob_away=round(final_away/total, 4),
            poisson_matrix=p_matrix,
            total_goals_expected=round(h_lambda + a_lambda, 2),
            total_goals_range=stats.get("total_goals_range", "0-0"),
            both_teams_to_score_prob=round(1.0 - (self.poisson.calculate_poisson_probability(h_lambda, 0) * self.poisson.calculate_poisson_probability(a_lambda, 0)), 4),
            score_prediction=score_pred,
            predicted_cards=f"🏠 {stats['cards'][0]} | ✈️ {stats['cards'][1]}",
            predicted_corners=f"🏠 {stats['corners'][0]} | ✈️ {stats['corners'][1]}",
            predicted_shots=f"🏠 {stats['shots'][0]} | ✈️ {stats['shots'][1]}",
            predicted_shots_on_target=f"🏠 {stats['shots_on_target'][0]} | ✈️ {stats['shots_on_target'][1]}",
            confidence_score=self._calc_confidence(final_home/total, final_away/total, bpa_h, bpa_a, p_home, p_away),
            external_analysis_summary=analysis_text,
            referee_name=ref_name
        )

        # 6. Value Betting Detection
        if match.market_odds:
            pred.value_opportunities = self.value_engine.find_opportunities(pred, match.market_odds)
            
        return pred

    def _calc_confidence(self, home_prob, away_prob, bpa_h=0.5, bpa_a=0.5, p_home=0.33, p_away=0.33) -> float:
        """
        Calcula confianza real basada en convergencia de modelos (0.0 a 1.0).
        Alta confianza = BPA, Poisson y probabilidades finales apuntan al mismo resultado.
        """
        # ¿Coinciden BPA y Poisson en el ganador?
        bpa_agrees   = (bpa_h > bpa_a) == (p_home > p_away) and abs(bpa_h - bpa_a) > 0.03
        # ¿Hay diferencia clara en probabilidades finales?
        clear_winner = abs(home_prob - away_prob) > 0.08
        # ¿El modelo no está demasiado cerca del empate?
        not_a_toss   = max(home_prob, away_prob) > 0.38

        score = 0.40  # Base
        if bpa_agrees:   score += 0.25
        if clear_winner: score += 0.20
        if not_a_toss:   score += 0.15
        return round(min(score, 1.0), 2)
