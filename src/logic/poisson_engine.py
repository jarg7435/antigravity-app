"""
PoissonEngine v4.1 — Distribución de Probabilidad con Freshness Integration
============================================================================
Correcciones:
- BPA impact suavizado con tanh (evita extremos)
- Integración con LineupFreshness para ajuste de lambdas
- Ajuste por bajas detectadas en alineación
"""

import math
from typing import Dict, Tuple, List, Optional
from src.models.base import Team


class PoissonEngine:
    """
    Motor estadístico basado en distribución de Poisson para predicción
    de resultados de fútbol, con integración de datos de alineación.
    """
    
    # Constantes de ajuste
    HOME_ADVANTAGE_FACTOR = 1.15
    AWAY_DISADVANTAGE_FACTOR = 0.90
    BPA_IMPACT_MAX = 0.15  # Máximo 15% de impacto (vs 50%+ anterior)
    
    # Fallback ratings
    DEFAULT_RATING = 7.0
    RATING_TO_GOALS_SLOPE = 0.6
    RATING_TO_CONCEDED_SLOPE = 0.3

    def calculate_poisson_probability(self, lambda_val: float, k: int) -> float:
        """
        Calcula P(X=k) dado un parámetro lambda.
        Maneja edge cases de forma segura.
        """
        if lambda_val <= 0:
            return 1.0 if k == 0 else 0.0
        if k < 0:
            return 0.0
        if k > 20:  # Optimización: probabilidad negligible
            return 0.0
            
        try:
            return (math.exp(-lambda_val) * (lambda_val ** k)) / math.factorial(k)
        except (OverflowError, ValueError):
            return 0.0

    def predict_score_matrix(
        self, 
        home_lambda: float, 
        away_lambda: float, 
        max_goals: int = 5
    ) -> Dict[str, float]:
        """
        Genera matriz de probabilidades para resultados exactos.
        """
        matrix = {}
        
        # Limitar max_goals para evitar cálculos innecesarios
        max_goals = min(max_goals, 8)
        
        for h in range(max_goals + 1):
            prob_h = self.calculate_poisson_probability(home_lambda, h)
            if prob_h < 0.0001:  # Optimización
                continue
                
            for a in range(max_goals + 1):
                prob_a = self.calculate_poisson_probability(away_lambda, a)
                if prob_a < 0.0001:
                    continue
                    
                matrix[f"{h}-{a}"] = round(prob_h * prob_a, 6)
        
        # Normalizar para que sume 1.0
        total_prob = sum(matrix.values())
        if total_prob > 0 and abs(total_prob - 1.0) > 0.01:
            matrix = {k: round(v / total_prob, 6) for k, v in matrix.items()}
            
        return matrix

    def calculate_match_probabilities(
        self, 
        home_lambda: float, 
        away_lambda: float,
        max_goals: int = 8
    ) -> Tuple[float, float, float]:
        """
        Calcula probabilidades 1X2 basándose en el modelo Poisson.
        """
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
        
        # Normalizar
        total = prob_home + prob_draw + prob_away
        if total > 0:
            prob_home /= total
            prob_draw /= total
            prob_away /= total
        
        return (
            round(prob_home, 4),
            round(prob_draw, 4),
            round(prob_away, 4)
        )

    def estimate_lambdas(
        self,
        home_team: Team,
        away_team: Team,
        league_avg_goals: float = 1.35,
        home_bpa: float = 0.5,
        away_bpa: float = 0.5,
        lineup_freshness: str = "confirmed",
        missing_key_players_home: int = 0,
        missing_key_players_away: int = 0
    ) -> Tuple[float, float]:
        """
        Estima parámetros lambda (goles esperados) con múltiples ajustes.
        
        Args:
            lineup_freshness: Afecta cuánto confiamos en los ajustes tácticos (BPA)
            missing_key_players: Número de jugadores clave faltantes por equipo
        """
        # 0. Validar liga
        if league_avg_goals <= 0.5:
            league_avg_goals = 1.35
            import logging
            logging.warning(f"League avg goals inválido, usando default {league_avg_goals}")

        # 1. Obtener stats base (xG) con fallback a ratings
        h_xg, h_xg_c = self._get_team_stats(home_team)
        a_xg, a_xg_c = self._get_team_stats(away_team)

        # 2. Calcular fuerzas relativas
        home_attack = h_xg / league_avg_goals
        away_defense = a_xg_c / league_avg_goals
        away_attack = a_xg / league_avg_goals
        home_defense = h_xg_c / league_avg_goals

        # 3. Lambdas base (sin BPA)
        home_lambda = home_attack * away_defense * league_avg_goals * self.HOME_ADVANTAGE_FACTOR
        away_lambda = away_attack * home_defense * league_avg_goals * self.AWAY_DISADVANTAGE_FACTOR

        # 4. Ajuste por BPA (VERSIÓN CORREGIDA - Suavizado)
        # Usar tanh para limitar impacto y aplicar confidence según freshness
        bpa_diff = home_bpa - away_bpa
        
        # Factor de confianza según calidad de alineación
        freshness_confidence = self._get_freshness_confidence(lineup_freshness)
        
        # Impacto suavizado: diff=0.6 → impacto≈0.12 (12%), no 60%
        bpa_impact = math.tanh(bpa_diff * 1.5) * self.BPA_IMPACT_MAX * freshness_confidence
        
        home_lambda *= (1.0 + bpa_impact)
        away_lambda *= (1.0 - bpa_impact * 0.7)  # Asimetría realista

        # 5. Ajuste por bajas de jugadores clave
        # Cada jugador clave ausente reduce lambda en ~8%
        home_lambda *= (0.92 ** missing_key_players_home)
        away_lambda *= (0.92 ** missing_key_players_away)

        # 6. Clamping adaptativo según calidad de datos
        # Si datos son malos, restringir más los rangos (menos volatilidad)
        if freshness_confidence < 0.5:
            # Datos stale: limitar a rangos más conservadores
            home_min, home_max = 0.6, 2.5
            away_min, away_max = 0.5, 2.0
        else:
            home_min, home_max = 0.4, 4.0
            away_min, away_max = 0.3, 3.5

        home_lambda = max(home_min, min(home_max, home_lambda))
        away_lambda = max(away_min, min(away_max, away_lambda))

        return round(home_lambda, 2), round(away_lambda, 2)

    def _get_team_stats(self, team: Team) -> Tuple[float, float]:
        """
        Obtiene xG y xG conceded, con fallback a estimación por rating.
        """
        h_xg = getattr(team, 'avg_xg_season', 0)
        h_xg_c = getattr(team, 'avg_xg_conceded_season', 0)
        
        rating = self._get_team_rating(team)
        
        # Fallback si no hay datos xG
        if h_xg <= 0.1:
            # Rating 7.0 → 1.35 goles, Rating 9.0 → 2.55 goles
            h_xg = league_avg_goals + (rating - self.DEFAULT_RATING) * self.RATING_TO_GOALS_SLOPE
            
        if h_xg_c <= 0.1:
            # Rating alto → menos goles concedidos
            h_xg_c = max(0.5, league_avg_goals - (rating - self.DEFAULT_RATING) * self.RATING_TO_CONCEDED_SLOPE)
            
        return h_xg, h_xg_c

    def _get_team_rating(self, team: Team) -> float:
        """
        Calcula rating promedio del equipo basado en jugadores.
        """
        players = getattr(team, 'players', [])
        if not players:
            return self.DEFAULT_RATING
        
        ratings = [
            p.rating_last_5 for p in players 
            if hasattr(p, 'rating_last_5') and p.rating_last_5 > 0
        ]
        
        if not ratings:
            return self.DEFAULT_RATING
            
        return sum(ratings) / len(ratings)

    def _get_freshness_confidence(self, freshness: str) -> float:
        """
        Convierte freshness en factor de confianza para ajustes tácticos.
        """
        confidence_map = {
            'live': 1.0,
            'confirmed': 0.9,
            'predicted': 0.6,
            'fallback': 0.3,
            'stale': 0.1
        }
        return confidence_map.get(freshness, 0.5)

    def calculate_expected_goals_distribution(
        self,
        lambda_val: float,
        max_goals: int = 5
    ) -> List[Tuple[int, float]]:
        """
        Retorna distribución completa de probabilidades de goles.
        Útil para mercados de over/under y handicaps asiáticos.
        """
        distribution = []
        cumulative = 0.0
        
        for k in range(max_goals + 1):
            prob = self.calculate_poisson_probability(lambda_val, k)
            cumulative += prob
            distribution.append((k, round(prob, 4), round(cumulative, 4)))
            
        return distribution

    def calculate_over_under_probability(
        self,
        home_lambda: float,
        away_lambda: float,
        threshold: float
    ) -> Tuple[float, float]:
        """
        Calcula probabilidades para mercados Over/Under.
        
        Returns:
            (over_prob, under_prob)
        """
        total_lambda = home_lambda + away_lambda
        
        # Para umbrales decimales (ej: 2.5), usar suma de probabilidades
        if threshold % 1 != 0:
            threshold_int = int(threshold)
            under_prob = 0.0
            for h in range(threshold_int + 1):
                for a in range(threshold_int + 1 - h):
                    under_prob += (
                        self.calculate_poisson_probability(home_lambda, h) *
                        self.calculate_poisson_probability(away_lambda, a)
                    )
        else:
            # Umbral entero: usar CDF directo
            under_prob = 0.0
            for k in range(int(threshold) + 1):
                under_prob += self.calculate_poisson_probability(total_lambda, k)
        
        return round(1 - under_prob, 4), round(under_prob, 4)