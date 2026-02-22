import math
from typing import Dict, Tuple
from src.models.base import Team

class PoissonEngine:
    """
    Motor estadístico basado en la distribución de Poisson para predecir 
    resultados de fútbol mediante fuerza ofensiva y defensiva.
    """
    
    def calculate_poisson_probability(self, lambda_val: float, k: int) -> float:
        """Calcula P(X=k) dado un parámetro lambda."""
        if lambda_val <= 0: return 0.0 if k > 0 else 1.0
        return (math.exp(-lambda_val) * (lambda_val**k)) / math.factorial(k)

    def predict_score_matrix(self, home_lambda: float, away_lambda: float, max_goals: int = 5) -> Dict[str, float]:
        """Genera una matriz de probabilidades para resultados exactos."""
        matrix = {}
        for h in range(max_goals + 1):
            for a in range(max_goals + 1):
                prob_h = self.calculate_poisson_probability(home_lambda, h)
                prob_a = self.calculate_poisson_probability(away_lambda, a)
                matrix[f"{h}-{a}"] = round(prob_h * prob_a, 4)
        return matrix

    def calculate_match_probabilities(self, home_lambda: float, away_lambda: float) -> Tuple[float, float, float]:
        """Calcula probabilidades 1X2 basándose en el modelo Poisson."""
        matrix = self.predict_score_matrix(home_lambda, away_lambda, max_goals=8)
        prob_home = 0.0
        prob_draw = 0.0
        prob_away = 0.0
        
        for score, prob in matrix.items():
            h, a = map(int, score.split("-"))
            if h > a: prob_home += prob
            elif h == a: prob_draw += prob
            else: prob_away += prob
            
        return round(prob_home, 4), round(prob_draw, 4), round(prob_away, 4)

    def estimate_lambdas(self, home_team: Team, away_team: Team, league_avg_goals: float = 1.35, home_bpa: float = 0.5, away_bpa: float = 0.5) -> Tuple[float, float]:
        """
        Estima los parámetros lambda (goles esperados) ajustados por:
        - Fuerza Ofensiva/Defensiva de temporada.
        - Balance de Presión Avanzada (BPA).
        - Factor campo.
        """
        # 0. Safety Check: If league avg is invalid, assume standard
        if league_avg_goals <= 0.5: league_avg_goals = 1.35
        
        # 1. Get Base Stats (Try to use real data first)
        h_xg = home_team.avg_xg_season
        h_xg_c = home_team.avg_xg_conceded_season
        a_xg = away_team.avg_xg_season
        a_xg_c = away_team.avg_xg_conceded_season
        
        # 2. Fallback Logic: If stats are 0, estimate from Team Rating (e.g., 8.5/10 -> ~2.0 goals)
        # Rating 7.0 (Avg) -> 1.35 goals
        # Rating 9.0 (Elite) -> 2.5 goals
        if h_xg <= 0.1:
            h_rating = self._get_team_rating(home_team)
            h_xg = 1.35 + (h_rating - 7.0) * 0.6
        
        if h_xg_c <= 0.1:
            h_rating = self._get_team_rating(home_team)
            # Higher rating = fewer conceded. 7.0 -> 1.35. 9.0 -> 0.8
            h_xg_c = max(0.5, 1.35 - (h_rating - 7.0) * 0.3)
            
        if a_xg <= 0.1:
            a_rating = self._get_team_rating(away_team)
            a_xg = 1.35 + (a_rating - 7.0) * 0.6
            
        if a_xg_c <= 0.1:
            a_rating = self._get_team_rating(away_team)
            a_xg_c = max(0.5, 1.35 - (a_rating - 7.0) * 0.3)

        # 3. Calculate Attack/Defense Strength
        home_attack = h_xg / league_avg_goals
        away_defense = a_xg_c / league_avg_goals
        
        away_attack = a_xg / league_avg_goals
        home_defense = h_xg_c / league_avg_goals
        
        # 4. Calculate Expected Goals (Lambda)
        # Home Goals = Home Attack * Away Defense * League Avg * Home Factor
        home_lambda = home_attack * away_defense * league_avg_goals * 1.15
        
        # Away Goals = Away Attack * Home Defense * League Avg
        away_lambda = away_attack * home_defense * league_avg_goals * 0.90
        
        # 5. BPA Unification: Apply BPA Dominance
        # If BPA is higher, increase lambda. Impact: +/- 25% max based on study
        bpa_diff = home_bpa - away_bpa
        home_lambda *= (1.0 + (bpa_diff * 1.5)) # Stronger study influence
        away_lambda *= (1.0 - (bpa_diff * 1.0))
        
        # 6. Final Safety: Clamping (Reinforced to avoid 0.00)
        home_lambda = max(0.4, min(5.0, home_lambda))
        away_lambda = max(0.3, min(4.5, away_lambda))
        
        return round(home_lambda, 2), round(away_lambda, 2)

    def _get_team_rating(self, team: Team) -> float:
        """Helper to get an average rating from players if available, or assume 7.0"""
        if not team.players:
            return 7.0
        
        # Average rating of top 11 (or all)
        ratings = [p.rating_last_5 for p in team.players if p.rating_last_5 > 0]
        if not ratings: return 7.0
        
        return sum(ratings) / len(ratings)
