"""
Predictor v4.1 — Motor Híbrido con Freshness Awareness
======================================================
Integra LineupFetcher, BPAEngine v4.1, y LearningEngine.
COMPATIBILIDAD: Mantiene import original 'from src.logic.bpa_engine import BPAEngine'
"""

import math
import logging
from typing import Dict, List, Optional, Tuple

from src.models.base import Match, PredictionResult
from src.logic.bpa_engine import BPAEngine  # Mismo import, nueva implementación
from src.logic.external_analyst import ExternalAnalyst
from src.logic.poisson_engine import PoissonEngine
from src.logic.ml_engine import MLEngine
from src.logic.value_engine import ValueEngine
from src.logic.learning_engine import LearningEngine

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class Predictor:
    """
    Motor predictivo híbrido v4.1 con Freshness Awareness.
    """
    
    WEIGHT_CONFIG = {
        'live': {'poisson': 0.50, 'bpa': 0.30, 'ml': 0.20},
        'confirmed': {'poisson': 0.50, 'bpa': 0.30, 'ml': 0.20},
        'predicted': {'poisson': 0.60, 'bpa': 0.25, 'ml': 0.15},
        'fallback': {'poisson': 0.70, 'bpa': 0.20, 'ml': 0.10},
        'stale': {'poisson': 0.75, 'bpa': 0.15, 'ml': 0.10}
    }

    def __init__(self, bpa_engine: Optional[BPAEngine] = None):
        self.bpa_engine = bpa_engine or BPAEngine()
        self.external_analyst = ExternalAnalyst()
        self.poisson = PoissonEngine()
        self.ml = MLEngine()
        self.value_engine = ValueEngine()
        self.learning = LearningEngine(self.bpa_engine)
        logger.info("Predictor v4.1 inicializado")

    def predict_match(
        self, 
        match: Match, 
        lineup_data: Optional[Dict] = None
    ) -> PredictionResult:
        """
        Genera predicción completa con metadatos de calidad.
        """
        # Extraer metadatos de alineación
        freshness = self._extract_freshness(lineup_data)
        uncertainty_penalty = lineup_data.get('uncertainty_penalty', 0.25) if lineup_data else 0.25
        
        logger.info(f"Prediciendo {match.home_team.name} vs {match.away_team.name} | "
                   f"Freshness: {freshness}")

        # 1. Inteligencia Externa
        intel = self.external_analyst.get_detailed_intelligence(match, freshness)
        analysis_text = intel.get("report", "Sin análisis externo")
        press_impact = intel.get("impact", {'home': 1.0, 'away': 1.0})

        # 2. BPA con nuevos parámetros
        bpa_res = self.bpa_engine.calculate_match_bpa(
            match,
            press_modifiers=press_impact,
            lineup_uncertainty=uncertainty_penalty,
            lineup_data=lineup_data
        )
        bpa_h, bpa_a = bpa_res['home_bpa'], bpa_res['away_bpa']

        # 3. Poisson
        h_lambda, a_lambda = self.poisson.estimate_lambdas(
            match.home_team,
            match.away_team,
            home_bpa=bpa_h,
            away_bpa=bpa_a,
            lineup_freshness=freshness
        )
        
        p_matrix = self.poisson.predict_score_matrix(h_lambda, a_lambda, max_goals=6)
        p_home, p_draw, p_away = self.poisson.calculate_match_probabilities(h_lambda, a_lambda)

        # 4. ML con features
        ml_features = self._extract_ml_features(match, bpa_res, h_lambda, a_lambda, lineup_data)
        ml_probs = self._get_ml_probabilities(ml_features, match.competition)

        # 5. Fusión Híbrida Adaptativa
        weights = self.WEIGHT_CONFIG.get(freshness, self.WEIGHT_CONFIG['fallback'])
        
        effective_bpa_weight = weights['bpa'] * (1 - uncertainty_penalty)
        bpa_excess = weights['bpa'] - effective_bpa_weight
        
        adjusted_weights = {
            'poisson': weights['poisson'] + (bpa_excess * 0.7),
            'bpa': effective_bpa_weight,
            'ml': weights['ml'] + (bpa_excess * 0.3)
        }

        bpa_diff = bpa_h - bpa_a
        bpa_prob_home, bpa_prob_draw, bpa_prob_away = self._calculate_bpa_probabilities(bpa_diff)

        final_home = (
            p_home * adjusted_weights['poisson'] +
            bpa_prob_home * adjusted_weights['bpa'] +
            ml_probs.get('LOCAL', 0.33) * adjusted_weights['ml']
        )
        final_draw = (
            p_draw * adjusted_weights['poisson'] +
            bpa_prob_draw * adjusted_weights['bpa'] +
            ml_probs.get('EMPATE', 0.33) * adjusted_weights['ml']
        )
        final_away = (
            p_away * adjusted_weights['poisson'] +
            bpa_prob_away * adjusted_weights['bpa'] +
            ml_probs.get('VISITANTE', 0.33) * adjusted_weights['ml']
        )

        # Normalización segura
        total = final_home + final_draw + final_away
        if total == 0 or not (0.5 < total < 2.0):
            logger.error(f"Normalización inválida: {total}")
            final_home = final_draw = final_away = 0.333
            total = 1.0
        
        norm_home = final_home / total
        norm_draw = final_draw / total
        norm_away = final_away / total

        # 6. Mercados secundarios
        stats = self.external_analyst.calculate_stat_markets(
            match, bpa_h, bpa_a, h_lambda=h_lambda, a_lambda=a_lambda
        )

        score_pred = max(p_matrix, key=p_matrix.get) if p_matrix else "0-0"

        # 7. Confianza
        confidence = self._calc_confidence_v2(
            norm_home, norm_away, bpa_res, p_home, p_away,
            uncertainty_penalty, freshness
        )

        # 8. Construir resultado
        pred = PredictionResult(
            match_id=match.id,
            bpa_home=bpa_h,
            bpa_away=bpa_a,
            win_prob_home=round(norm_home, 4),
            draw_prob=round(norm_draw, 4),
            win_prob_away=round(norm_away, 4),
            poisson_matrix=p_matrix,
            total_goals_expected=round(h_lambda + a_lambda, 2),
            total_goals_range=stats.get("total_goals_range", f"{int(h_lambda+a_lambda-0.5)}-{int(h_lambda+a_lambda+1.5)}"),
            both_teams_to_score_prob=round(
                1.0 - (self.poisson.calculate_poisson_probability(h_lambda, 0) * 
                       self.poisson.calculate_poisson_probability(a_lambda, 0)), 4
            ),
            score_prediction=score_pred,
            predicted_cards=f"🏠 {stats['cards'][0]} | ✈️ {stats['cards'][1]}",
            predicted_corners=f"🏠 {stats['corners'][0]} | ✈️ {stats['corners'][1]}",
            predicted_shots=f"🏠 {stats['shots'][0]} | ✈️ {stats['shots'][1]}",
            predicted_shots_on_target=f"🏠 {stats['shots_on_target'][0]} | ✈️ {stats['shots_on_target'][1]}",
            confidence_score=confidence,
            external_analysis_summary=analysis_text,
            referee_name=self._extract_referee_name(match),
            lineup_freshness=freshness,
            uncertainty_penalty=uncertainty_penalty,
            data_quality_score=round(1 - uncertainty_penalty, 2),
            model_weights_used=adjusted_weights,
            bpa_validation=bpa_res.get('data_quality', {})
        )

        if match.market_odds and confidence > 0.5:
            pred.value_opportunities = self.value_engine.find_opportunities(pred, match.market_odds)
            
        return pred

    def _extract_freshness(self, lineup_data: Optional[Dict]) -> str:
        if not lineup_data:
            return 'fallback'
        freshness = lineup_data.get('freshness', 'fallback')
        valid = ['live', 'confirmed', 'predicted', 'fallback', 'stale']
        return freshness if freshness in valid else 'fallback'

    def _extract_ml_features(self, match, bpa_res, h_lambda, a_lambda, lineup_data):
        return {
            'home_form': getattr(match.home_team, 'form_last_5', 0.5),
            'away_form': getattr(match.away_team, 'form_last_5', 0.5),
            'bpa_diff': bpa_res['home_bpa'] - bpa_res['away_bpa'],
            'bpa_sum': bpa_res['home_bpa'] + bpa_res['away_bpa'],
            'lambda_diff': h_lambda - a_lambda,
            'total_lambda': h_lambda + a_lambda,
            'lineup_quality': 1 - (lineup_data.get('uncertainty_penalty', 0.25) if lineup_data else 0.25),
            'home_players_count': len(lineup_data.get('home', [])) if lineup_data else 11,
            'away_players_count': len(lineup_data.get('away', [])) if lineup_data else 11,
            'is_home': 1,
            'days_rest_home': getattr(match.home_team, 'days_rest', 5),
            'days_rest_away': getattr(match.away_team, 'days_rest', 5),
            'critical_roles_missing_home': len(
                bpa_res.get('data_quality', {}).get('home_validation', {}).get('missing_critical_roles', [])
            ),
            'critical_roles_missing_away': len(
                bpa_res.get('data_quality', {}).get('away_validation', {}).get('missing_critical_roles', [])
            )
        }

    def _get_ml_probabilities(self, features, league):
        try:
            probs = self.ml.predict_probabilities(features, league=league)
            if not isinstance(probs, dict) or not all(k in probs for k in ['LOCAL', 'EMPATE', 'VISITANTE']):
                raise ValueError("Formato inválido")
            return probs
        except Exception as e:
            logger.warning(f"ML falló: {e}")
            return {'LOCAL': 0.40, 'EMPATE': 0.30, 'VISITANTE': 0.30}

    def _calculate_bpa_probabilities(self, bpa_diff):
        adjusted_diff = math.tanh(bpa_diff * 2) * 0.20
        home_logit = 0.35 + adjusted_diff
        draw_logit = 0.30 - abs(adjusted_diff) * 0.3
        away_logit = 0.35 - adjusted_diff
        
        exp_h, exp_d, exp_a = math.exp(home_logit), math.exp(draw_logit), math.exp(away_logit)
        total = exp_h + exp_d + exp_a
        
        return (exp_h/total, exp_d/total, exp_a/total)

    def _calc_confidence_v2(self, home_prob, away_prob, bpa_res, p_home, p_away, uncertainty_penalty, freshness):
        score = 0.40
        
        bpa_fav_home = bpa_res['home_bpa'] > bpa_res['away_bpa']
        poisson_fav_home = p_home > p_away
        models_agree = bpa_fav_home == poisson_fav_home
        
        if models_agree:
            agreement_strength = abs(bpa_res['home_bpa'] - bpa_res['away_bpa']) + abs(p_home - p_away)
            score += min(0.25, agreement_strength * 0.3)
        
        prob_diff = abs(home_prob - away_prob)
        if prob_diff > 0.15:
            score += 0.20
        elif prob_diff > 0.08:
            score += 0.10
            
        if max(home_prob, away_prob) > 0.40:
            score += 0.10
            
        quality_penalty = uncertainty_penalty * 0.6
        missing_roles = (
            len(bpa_res.get('data_quality', {}).get('home_validation', {}).get('missing_critical_roles', [])) +
            len(bpa_res.get('data_quality', {}).get('away_validation', {}).get('missing_critical_roles', []))
        )
        role_penalty = missing_roles * 0.05
        
        return round(max(0.1, min(1.0, score - quality_penalty - role_penalty)), 2)

    def _extract_referee_name(self, match):
        if not match.referee:
            return "No asignado"
        if isinstance(match.referee, dict):
            return match.referee.get("name", "No asignado")
        return getattr(match.referee, "name", "No asignado")