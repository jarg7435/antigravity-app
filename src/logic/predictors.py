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
        # 1. BPA Analysis (Core legacy logic)
        bpa_res = self.bpa_engine.calculate_match_bpa(match)
        bpa_h, bpa_a = bpa_res['home_bpa'], bpa_res['away_bpa']

        # 2. Poisson Statistics (Goals & Lambdas con Integración BPA)
        h_lambda, a_lambda = self.poisson.estimate_lambdas(match.home_team, match.away_team, home_bpa=bpa_h, away_bpa=bpa_a)
        p_matrix = self.poisson.predict_score_matrix(h_lambda, a_lambda)
        p_home, p_draw, p_away = self.poisson.calculate_match_probabilities(h_lambda, a_lambda)

        # 3. Machine Learning (Ensemble classification)
        ml_probs = self.ml.predict_probabilities(None) 

        # 4. Hybrid Blending (Fusión de modelos)
        final_home = (ml_probs['LOCAL'] * 0.4) + (p_home * 0.4) + (0.35 + (bpa_h - bpa_a) * 0.2)
        final_draw = (ml_probs['EMPATE'] * 0.4) + (p_draw * 0.4) + (0.30)
        final_away = (ml_probs['VISITANTE'] * 0.4) + (p_away * 0.4) + (0.35 - (bpa_h - bpa_a) * 0.2)
        
        # Normalize
        total = final_home + final_draw + final_away
        
        # 5. External & Stat Markets
        analysis_text = self.external_analyst.analyze_match(match)
        stats = self.external_analyst.calculate_stat_markets(match, bpa_h, bpa_a)
        
        # Determine the most likely score
        score_pred = "0-0"
        if p_matrix:
            score_pred = max(p_matrix, key=p_matrix.get)

        pred = PredictionResult(
            match_id=match.id,
            bpa_home=bpa_h,
            bpa_away=bpa_a,
            win_prob_home=round(final_home/total, 4),
            draw_prob=round(final_draw/total, 4),
            win_prob_away=round(final_away/total, 4),
            poisson_matrix=p_matrix,
            total_goals_expected=round(h_lambda + a_lambda, 2),
            both_teams_to_score_prob=round(1.0 - (self.poisson.calculate_poisson_probability(h_lambda, 0) * self.poisson.calculate_poisson_probability(a_lambda, 0)), 4),
            score_prediction=score_pred,
            predicted_cards=f"🏠 {stats['cards'][0]} | ✈️ {stats['cards'][1]}",
            predicted_corners=f"🏠 {stats['corners'][0]} | ✈️ {stats['corners'][1]}",
            predicted_shots=f"🏠 {stats['shots'][0]} | ✈️ {stats['shots'][1]}",
            predicted_shots_on_target=f"🏠 {stats['shots_on_target'][0]} | ✈️ {stats['shots_on_target'][1]}",
            confidence_score=self._calc_confidence(final_home, final_away),
            external_analysis_summary=analysis_text,
            referee_name=match.referee.name if match.referee else "No asignado"
        )

        # 6. Value Betting Detection
        if match.market_odds:
            pred.value_opportunities = self.value_engine.find_opportunities(pred, match.market_odds)
            
        return pred

    def _calc_confidence(self, home, away) -> float:
        # Confidence based on model agreement
        return round(abs(home - away) + 0.5, 2)
