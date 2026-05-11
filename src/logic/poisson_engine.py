"""
PoissonEngine v4.1 — Distribución de Probabilidad con Freshness Integration
"""

import math
from typing import Dict, Tuple, List, Optional
from src.models.base import Team


class PoissonEngine:
    """
    Motor estadístico basado en distribución de Poisson.
    """
    
    HOME_ADVANTAGE_FACTOR = 1.15
    AWAY_DISADVANTAGE_FACTOR = 0.90
    BPA_IMPACT_MAX = 0.15
    DEFAULT_RATING = 7.0

    def calculate_poisson_probability(self, lambda_val: float, k: int) -> float:
        if lambda_val <= 0:
            return 1.0 if k == 0 else 0.0
        if k < 0:
            return 0.0
        if k > 20:
            return 0.0
            
        try:
            return (math.exp(-lambda_val) * (lambda_val ** k)) / math.factorial(k)
        except (OverflowError, ValueError):
            return 0.0

    def predict_score_matrix(self, home_lambda: float, away_lambda: float, max_goals: int = 5):
        matrix = {}
        max_goals = min(max_goals, 8)
        
        for h in range(max_goals + 1):
            prob_h = self.calculate_poisson_probability(home_lambda, h)
            if prob_h < 1e-8:
                continue
                
            for a in range(max_goals + 1):
                prob_a = self.calculate_poisson_probability(away_lambda, a)
                if prob_a < 1e-8:
                    continue
                    
                matrix[f"{h}-{a}"] = round(prob_h * prob_a, 8)
        
        total_prob = sum(matrix.values())
        if total_prob > 0 and abs(total_prob - 1.0) > 0.01:
            matrix = {k: round(v / total_prob, 6) for k, v in matrix.items()}
            
        return matrix

    def calculate_match_probabilities(self, home_lambda: float, away_lambda: float, max_goals: int = 8):
        matrix = self.predict_score_matrix(home_lambda, away_lambda, max_goals)
        
        prob_home = prob_draw = prob_away = 0.0
        
        for score, prob in matrix.items():
            try:
                h, a = map(int, score.split("-"))
                if h > a:
                    prob_home += prob
                elif h == a:
                    prob_draw += prob
                else:
                    prob_away += prob
            except ValueError:
                continue
        
        total = prob_home + prob_draw + prob_away
        if total > 0:
            prob_home /= total
            prob_draw /= total
            prob_away /= total
        
        return (round(prob_home, 4), round(prob_draw, 4), round(prob_away, 4))

    def estimate_lambdas(
        self,
        home_team: Team,
        away_team: Team,
        league_avg_goals: float = 1.35,
        home_bpa: float = 0.5,
        away_bpa: float = 0.5,
        lineup_freshness: str = "confirmed",
        missing_key_players_home: int = 0,
        missing_key_players_away: int = 0,
        league_name: Optional[str] = None,
        **kwargs
    ):
        if league_avg_goals <= 0.5:
            league_avg_goals = 1.35

        h_xg = getattr(home_team, 'avg_xg_season', 0)
        h_xg_c = getattr(home_team, 'avg_xg_conceded_season', 0)
        a_xg = getattr(away_team, 'avg_xg_season', 0)
        a_xg_c = getattr(away_team, 'avg_xg_conceded_season', 0)
        
        h_rating = self._get_team_rating(home_team)
        a_rating = self._get_team_rating(away_team)
        
        if h_xg <= 0.1:
            h_xg = league_avg_goals + (h_rating - self.DEFAULT_RATING) * 0.6
        if h_xg_c <= 0.1:
            h_xg_c = max(0.5, league_avg_goals - (h_rating - self.DEFAULT_RATING) * 0.3)
        if a_xg <= 0.1:
            a_xg = league_avg_goals + (a_rating - self.DEFAULT_RATING) * 0.6
        if a_xg_c <= 0.1:
            a_xg_c = max(0.5, league_avg_goals - (a_rating - self.DEFAULT_RATING) * 0.3)

        home_attack = h_xg / league_avg_goals
        away_defense = a_xg_c / league_avg_goals
        away_attack = a_xg / league_avg_goals
        home_defense = h_xg_c / league_avg_goals

        home_lambda = home_attack * away_defense * league_avg_goals * self.HOME_ADVANTAGE_FACTOR
        away_lambda = away_attack * home_defense * league_avg_goals * self.AWAY_DISADVANTAGE_FACTOR

        bpa_diff = home_bpa - away_bpa
        freshness_confidence = self._get_freshness_confidence(lineup_freshness)
        bpa_impact = math.tanh(bpa_diff * 1.5) * self.BPA_IMPACT_MAX * freshness_confidence
        
        home_lambda *= (1.0 + bpa_impact)
        away_lambda *= (1.0 - bpa_impact * 0.7)

        home_lambda *= (0.92 ** missing_key_players_home)
        away_lambda *= (0.92 ** missing_key_players_away)

        if freshness_confidence < 0.5:
            home_min, home_max = 0.6, 2.5
            away_min, away_max = 0.5, 2.0
        else:
            home_min, home_max = 0.4, 4.0
            away_min, away_max = 0.3, 3.5

        home_lambda = max(home_min, min(home_max, home_lambda))
        away_lambda = max(away_min, min(away_max, away_lambda))

        return home_lambda, away_lambda

    def _get_team_rating(self, team: Team):
        players = getattr(team, 'players', [])
        if not players:
            return self.DEFAULT_RATING
        
        ratings = [p.rating_last_5 for p in players if hasattr(p, 'rating_last_5') and p.rating_last_5 > 0]
        return sum(ratings) / len(ratings) if ratings else self.DEFAULT_RATING

    def _get_freshness_confidence(self, freshness: str):
        confidence_map = {
            'live': 1.0, 'confirmed': 0.9, 'predicted': 0.6,
            'fallback': 0.3, 'stale': 0.1
        }
        return confidence_map.get(freshness, 0.5)