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

    def estimate_lambdas(self, home_team: Team, away_team: Team, league_avg_goals: float = 1.35) -> Tuple[float, float]:
        """
        Estima los parámetros lambda (goles esperados) ajustados por:
        - Fuerza Ofensiva/Defensiva de temporada.
        - Estado de forma (xG últimos partidos).
        - Factor campo.
        """
        # Simplificación para Fase 1: Usar promedios de temporada si están disponibles
        home_attack = (home_team.avg_xg_season / league_avg_goals) if league_avg_goals > 0 else 1.0
        away_defense = (away_team.avg_xg_conceded_season / league_avg_goals) if league_avg_goals > 0 else 1.0
        
        away_attack = (away_team.avg_xg_season / league_avg_goals) if league_avg_goals > 0 else 1.0
        home_defense = (home_team.avg_xg_conceded_season / league_avg_goals) if league_avg_goals > 0 else 1.0
        
        # Factor Campo (Heredado de BPA but applied to Poisson)
        home_lambda = home_attack * home_defense * league_avg_goals * 1.10 # 10% home advantage
        away_lambda = away_attack * away_defense * league_avg_goals * 0.95 # 5% away penalty
        
        return home_lambda, away_lambda
