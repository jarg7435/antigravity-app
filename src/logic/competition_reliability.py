"""
CompetitionReliability — Fiabilidad Cross-Competition para LAGEMA JARG74
========================================================================
Resuelve el problema CRÍTICO: las predicciones en competiciones europeas
(Champions, Europa, Conference) son menos fiables que en ligas domésticas
porque los equipos se enfrentan entre ligas diferentes.

Factores que reduce la fiabilidad:
  - Menos historial H2H entre equipos de diferentes ligas
  - Diferencia de nivel entre ligas (coeficiente UEFA)
  - Motivación variable (liga vs copa europea)
  - Rotaciones de plantilla en competiciones secundarias
  - Factor campo neutral (finales, supercopas)

Uso:
    from src.logic.competition_reliability import CompetitionReliability
    cr = CompetitionReliability()
    reliability = cr.get_match_reliability("Champions League", "La Liga", "Premier League")
    # → {"reliability": 0.72, "factors": {...}, "adjustments": {...}}
"""

import logging
from typing import Dict, Optional, Any
from enum import Enum

logger = logging.getLogger("LAGEMA_COMPETITION")


class CompetitionTier(int, Enum):
    """Nivel de la competición según coeficiente UEFA."""
    ELITE = 1       # Champions League
    HIGH = 2        # Europa League, top-5 ligas domésticas
    MEDIUM = 3      # Conference League, ligas secundarias
    LOW = 4         # Copas nacionales, ligas menores


class LeagueStrength(float, Enum):
    """Fuerza relativa de las ligas según coeficiente UEFA 2025-26."""
    PREMIER_LEAGUE = 1.00
    LA_LIGA = 0.95
    BUNDESLIGA = 0.88
    SERIE_A = 0.87
    LIGUE_1 = 0.82
    EREDIVISIE = 0.72
    PRIMEIRA_LIGA = 0.70
    SUPER_LIG = 0.62
    BELGIAN_PRO = 0.65
    SCOTTISH = 0.58
    CHAMPIONSHIP = 0.60
    SEGUNDA = 0.55
    OTHER = 0.50


class CompetitionReliability:
    """
    Calcula la fiabilidad de una predicción según el tipo de competición
    y la combinación de ligas de los equipos involucrados.
    
    La fiabilidad base es 1.0 (máxima confianza) y se reducen
    multiplicativamente por cada factor de incertidumbre.
    """

    # Mapeo de competiciones a tiers
    COMPETITION_TIERS = {
        "Champions League": CompetitionTier.ELITE,
        "Champions": CompetitionTier.ELITE,
        "UEFA Champions League": CompetitionTier.ELITE,
        "Europa League": CompetitionTier.HIGH,
        "UEFA Europa League": CompetitionTier.HIGH,
        "Conference League": CompetitionTier.MEDIUM,
        "UEFA Conference League": CompetitionTier.MEDIUM,
        "La Liga": CompetitionTier.HIGH,
        "La Liga (España)": CompetitionTier.HIGH,
        "Premier League": CompetitionTier.HIGH,
        "Premier League (Inglaterra)": CompetitionTier.HIGH,
        "Bundesliga": CompetitionTier.HIGH,
        "Bundesliga (Alemania)": CompetitionTier.HIGH,
        "Serie A": CompetitionTier.HIGH,
        "Serie A (Italia)": CompetitionTier.HIGH,
        "Ligue 1": CompetitionTier.HIGH,
        "Ligue 1 (Francia)": CompetitionTier.HIGH,
        "Eredivisie": CompetitionTier.MEDIUM,
        "Primeira Liga": CompetitionTier.MEDIUM,
        "Süper Lig": CompetitionTier.MEDIUM,
        "Copa Libertadores": CompetitionTier.HIGH,
        "Copa Sudamericana": CompetitionTier.MEDIUM,
        "Segunda División": CompetitionTier.LOW,
        "Championship": CompetitionTier.MEDIUM,
    }

    # Mapeo de nombres de liga a fuerza
    LEAGUE_STRENGTH_MAP = {
        "Premier League": LeagueStrength.PREMIER_LEAGUE,
        "Premier League (Inglaterra)": LeagueStrength.PREMIER_LEAGUE,
        "La Liga": LeagueStrength.LA_LIGA,
        "La Liga (España)": LeagueStrength.LA_LIGA,
        "Bundesliga": LeagueStrength.BUNDESLIGA,
        "Bundesliga (Alemania)": LeagueStrength.BUNDESLIGA,
        "Serie A": LeagueStrength.SERIE_A,
        "Serie A (Italia)": LeagueStrength.SERIE_A,
        "Ligue 1": LeagueStrength.LIGUE_1,
        "Ligue 1 (Francia)": LeagueStrength.LIGUE_1,
        "Eredivisie": LeagueStrength.EREDIVISIE,
        "Primeira Liga": LeagueStrength.PRIMEIRA_LIGA,
        "Süper Lig": LeagueStrength.SUPER_LIG,
        "Belgian Pro League": LeagueStrength.BELGIAN_PRO,
        "Scottish Premiership": LeagueStrength.SCOTTISH,
        "Championship": LeagueStrength.CHAMPIONSHIP,
        "Segunda División": LeagueStrength.SEGUNDA,
    }

    # Factor de ventaja local por competición
    HOME_ADVANTAGE_BY_COMPETITION = {
        CompetitionTier.ELITE: 1.05,     # Menos ventaja en Champions (equipos acostumbrados)
        CompetitionTier.HIGH: 1.10,      # Normal en ligas domésticas
        CompetitionTier.MEDIUM: 1.12,    # Más ventaja en ligas menores
        CompetitionTier.LOW: 1.15,       # Mucha ventaja en categorías bajas
    }

    # Factor de motivación por tipo de competición
    MOTIVATION_FACTORS = {
        "Champions League": 1.05,         # Máxima motivación
        "UEFA Champions League": 1.05,
        "Champions": 1.05,
        "Europa League": 1.02,            # Alta motivación pero no máxima
        "UEFA Europa League": 1.02,
        "Conference League": 0.98,        # Menor motivación para equipos top
        "UEFA Conference League": 0.98,
        "Copa Libertadores": 1.05,        # Máxima motivación sudamericana
        "Copa Sudamericana": 1.00,
    }

    def __init__(self):
        self.logger = logger

    def get_match_reliability(self, competition: str, 
                               home_league: str = None,
                               away_league: str = None,
                               is_knockout: bool = False,
                               is_final: bool = False,
                               matchday: int = None) -> Dict[str, Any]:
        """
        Calcula la fiabilidad de la predicción para un partido específico.
        
        Args:
            competition: Nombre de la competición
            home_league: Liga del equipo local
            away_league: Liga del equipo visitante
            is_knockout: Si es partido de eliminación directa
            is_final: Si es una final
            matchday: Jornada (fase de grupos vs eliminatorias)
        
        Returns:
            {
                "reliability": float (0.0-1.0),
                "confidence_penalty": float (0.0-0.5),
                "factors": dict con desglose de cada factor,
                "adjustments": dict con ajustes recomendados,
                "warnings": list de advertencias
            }
        """
        factors = {}
        warnings = []
        reliability = 1.0
        tier = self.COMPETITION_TIERS.get(competition, CompetitionTier.MEDIUM)

        # ================================================================
        # FACTOR 1: Cross-League Penalty (equipos de diferentes ligas)
        # ================================================================
        cross_league_penalty = 0.0
        is_cross_league = False

        if home_league and away_league and home_league != away_league:
            is_cross_league = True
            # Diferencia de fuerza entre ligas
            home_strength = self._get_league_strength(home_league)
            away_strength = self._get_league_strength(away_league)
            strength_diff = abs(float(home_strength) - float(away_strength))

            # Mayor diferencia = mayor incertidumbre
            # Pero la incertidumbre máxima es cuando las ligas son similares
            # (porque no hay referencia clara de cómo se comparan)
            if strength_diff < 0.1:
                # Ligas muy parecidas: incertidumbre moderada
                cross_league_penalty = 0.05
            elif strength_diff < 0.2:
                # Diferencia apreciable: más incertidumbre
                cross_league_penalty = 0.08
            else:
                # Gran diferencia: el fuerte suele ganar, menos incertidumbre
                cross_league_penalty = 0.06

            factors["cross_league"] = {
                "penalty": cross_league_penalty,
                "home_league_strength": float(home_strength),
                "away_league_strength": float(away_strength),
                "strength_diff": strength_diff
            }
            reliability -= cross_league_penalty

            if strength_diff > 0.3:
                stronger = home_league if home_strength > away_strength else away_league
                warnings.append(
                    f"Diferencia significativa de nivel: {stronger} es claramente superior"
                )

        # ================================================================
        # FACTOR 2: Tipo de Competición
        # ================================================================
        comp_penalty = 0.0
        if tier == CompetitionTier.ELITE:
            # Champions: datos más disponibles, pero más impredecible
            comp_penalty = 0.03
        elif tier == CompetitionTier.HIGH:
            # Ligas top: máxima fiabilidad
            comp_penalty = 0.0
        elif tier == CompetitionTier.MEDIUM:
            # Ligas menores o Conference: menos datos
            comp_penalty = 0.05
        elif tier == CompetitionTier.LOW:
            # Categorías bajas: muchos datos desconocidos
            comp_penalty = 0.10

        factors["competition_tier"] = {
            "tier": tier.name,
            "penalty": comp_penalty
        }
        reliability -= comp_penalty

        # ================================================================
        # FACTOR 3: Fase del Torneo (solo competiciones europeas)
        # ================================================================
        phase_penalty = 0.0
        if is_cross_league or tier in (CompetitionTier.ELITE, CompetitionTier.HIGH):
            if is_final:
                # Final: campo neutral, máxima presión, imprevisible
                phase_penalty = 0.10
                warnings.append("Final: campo neutral y presión máxima reducen fiabilidad")
            elif is_knockout:
                # Eliminatoria: más conservadurismo, menos goles
                phase_penalty = 0.04
            elif matchday and matchday <= 3:
                # Fase de grupos inicio: todavía sin referencia
                phase_penalty = 0.05
            elif matchday and matchday >= 5:
                # Fase de grupos final: todo se decide, más predecible
                phase_penalty = 0.01

        factors["tournament_phase"] = {
            "is_knockout": is_knockout,
            "is_final": is_final,
            "matchday": matchday,
            "penalty": phase_penalty
        }
        reliability -= phase_penalty

        # ================================================================
        # FACTOR 4: H2H Availability
        # ================================================================
        h2h_penalty = 0.0
        if is_cross_league:
            # Equipos de diferentes ligas: poco H2H histórico
            h2h_penalty = 0.07
            factors["h2h_availability"] = {
                "available": False,
                "penalty": h2h_penalty,
                "note": "Equipos de diferentes ligas: historial H2H limitado o inexistente"
            }
        else:
            factors["h2h_availability"] = {
                "available": True,
                "penalty": 0.0
            }
        reliability -= h2h_penalty

        # ================================================================
        # FACTOR 5: Motivación
        # ================================================================
        motivation = self.MOTIVATION_FACTORS.get(competition, 1.0)
        motivation_penalty = max(0, 1.0 - motivation) * 0.05  # Pequeño ajuste

        factors["motivation"] = {
            "factor": motivation,
            "penalty": motivation_penalty
        }
        reliability -= motivation_penalty

        # ================================================================
        # CÁLCULO FINAL
        # ================================================================
        reliability = max(0.30, min(1.0, reliability))  # Clamp entre 0.30 y 1.0
        confidence_penalty = 1.0 - reliability

        # Ajustes recomendados
        adjustments = self._generate_adjustments(reliability, tier, is_cross_league, is_knockout)

        return {
            "reliability": round(reliability, 3),
            "confidence_penalty": round(confidence_penalty, 3),
            "is_cross_league": is_cross_league,
            "competition_tier": tier.name,
            "factors": factors,
            "adjustments": adjustments,
            "warnings": warnings
        }

    def get_weight_adjustments(self, reliability: float) -> Dict[str, float]:
        """
        Ajusta los pesos del predictor según la fiabilidad.
        
        Cuando la fiabilidad es baja:
          - Más peso a Poisson (modelo estadístico puro)
          - Menos peso a BPA (depende de datos de equipos)
          - Menos peso a ML (menos datos de entrenamiento)
        
        Cuando la fiabilidad es alta:
          - Más peso a BPA (datos fiables)
          - ML puede aportar más
        """
        if reliability >= 0.90:
            # Máxima confianza: pesos estándar
            return {
                "poisson": 0.45,
                "bpa": 0.35,
                "ml": 0.20,
                "confidence_floor": 0.70
            }
        elif reliability >= 0.80:
            # Buena confianza: ligeramente más Poisson
            return {
                "poisson": 0.50,
                "bpa": 0.30,
                "ml": 0.20,
                "confidence_floor": 0.60
            }
        elif reliability >= 0.70:
            # Confianza moderada: Poisson domina
            return {
                "poisson": 0.55,
                "bpa": 0.28,
                "ml": 0.17,
                "confidence_floor": 0.50
            }
        elif reliability >= 0.60:
            # Baja confianza: Poisson fuerte, ML mínimo
            return {
                "poisson": 0.60,
                "bpa": 0.25,
                "ml": 0.15,
                "confidence_floor": 0.40
            }
        else:
            # Muy baja confianza: Poisson casi exclusivo
            return {
                "poisson": 0.70,
                "bpa": 0.20,
                "ml": 0.10,
                "confidence_floor": 0.30
            }

    def get_home_advantage(self, competition: str) -> float:
        """Obtiene el factor de ventaja local para una competición."""
        tier = self.COMPETITION_TIERS.get(competition, CompetitionTier.MEDIUM)
        return self.HOME_ADVANTAGE_BY_COMPETITION.get(tier, 1.10)

    def _get_league_strength(self, league_name: str) -> float:
        """Obtiene la fuerza relativa de una liga."""
        strength = self.LEAGUE_STRENGTH_MAP.get(league_name)
        if strength:
            return float(strength)
        return float(LeagueStrength.OTHER)

    def _generate_adjustments(self, reliability: float, tier: CompetitionTier,
                               is_cross_league: bool, is_knockout: bool) -> Dict[str, Any]:
        """Genera ajustes recomendados para el predictor."""
        weight_adj = self.get_weight_adjustments(reliability)

        adjustments = {
            "weight_adjustments": weight_adj,
            "home_advantage_modifier": self.HOME_ADVANTAGE_BY_COMPETITION.get(tier, 1.10),
            "goals_expectation_modifier": 1.0,
            "draw_probability_boost": 0.0,
        }

        # Ajustes para cross-league
        if is_cross_league:
            # En cross-league, los empates son más probables
            adjustments["draw_probability_boost"] = round((1.0 - reliability) * 0.08, 3)
            # Los goles tienden a ser menos predecibles
            adjustments["goals_expectation_modifier"] = round(1.0 - (1.0 - reliability) * 0.1, 3)

        # Ajustes para eliminatorias
        if is_knockout:
            # Más conservadurismo, menos goles esperados
            adjustments["goals_expectation_modifier"] = 0.92
            adjustments["draw_probability_boost"] += 0.03

        # Ajuste de confianza mínimo
        adjustments["min_confidence"] = weight_adj["confidence_floor"]

        return adjustments
