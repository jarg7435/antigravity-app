"""
BPAEngine v4.1 — Balance de Presión Avanzada con Lineup Awareness
=================================================================
Integraciones:
- LineupUncertainty: Penaliza BPA si alineación es stale/fallback
- RoleValidation: Verifica que los roles asignados existen en la alineación real
- DynamicWeighting: Ajusta pesos si faltan jugadores clave (Finalizers/Creators)

COMPATIBILIDAD: Mantiene API original para no romper imports existentes.
"""

import math
from typing import Dict, List, Optional, Set
from src.models.base import Match, Team, Player, NodeRole, PlayerStatus
from src.data.knowledge_base import KnowledgeBase
from src.logic.blindaje_ia import BlindajeIA


class BPAEngine:
    """
    Motor de cálculo de Balance de Presión Avanzada (BPA) v4.1.
    Ahora consciente de la calidad de datos de alineación.
    """
    
    # Pesos base por rol (suman 1.0)
    WEIGHTS = {
        NodeRole.FINALIZER: 0.35,
        NodeRole.CREATOR: 0.25,
        NodeRole.DEFENSIVE: 0.20,
        NodeRole.KEEPER: 0.15,
        NodeRole.TACTICAL: 0.05
    }
    
    # Factores contextuales
    FACTOR_HOME = 1.10
    FACTOR_AWAY = 0.95
    FACTOR_BAD_WEATHER = 0.90
    FACTOR_MOTIVATION_HIGH = 1.15
    
    # Penalización por ausencia de roles críticos
    CRITICAL_ROLES = {NodeRole.FINALIZER, NodeRole.CREATOR}
    ROLE_ABSENCE_PENALTY = 0.15

    def __init__(self):
        self.kb = KnowledgeBase()
        self.blindaje = BlindajeIA()
        self._lineup_cache = {}

    def calculate_match_bpa(
        self, 
        match: Match, 
        press_modifiers: Optional[Dict] = None,
        lineup_uncertainty: float = 0.0,
        lineup_data: Optional[Dict] = None
    ) -> Dict:
        """
        Calcula BPA para ambos equipos con awareness de calidad de datos.
        
        Args:
            match: Objeto Match con datos de equipos
            press_modifiers: {'home': float, 'away': float} de ExternalAnalyst
            lineup_uncertainty: Penalty de 0-35% según freshness de alineación
            lineup_data: Dict con 'home', 'away', 'bajas_detectadas' de LineupFetcher
            
        Returns:
            Dict con home_bpa, away_bpa, advantage, y metadatos de calidad
        """
        press_modifiers = press_modifiers or {}
        h_mod = press_modifiers.get('home', 1.0)
        a_mod = press_modifiers.get('away', 1.0)
        
        # Validar alineaciones contra roles esperados
        home_validation = self._validate_lineup_roles(
            match.home_team, 
            lineup_data.get('home', []) if lineup_data else [],
            lineup_data.get('bajas_detectadas', []) if lineup_data else []
        )
        away_validation = self._validate_lineup_roles(
            match.away_team,
            lineup_data.get('away', []) if lineup_data else [],
            lineup_data.get('bajas_detectadas', []) if lineup_data else []
        )
        
        # Calcular BPA con validación integrada
        bpa_home = self._calculate_team_bpa_v2(
            team=match.home_team,
            is_home=True,
            conditions=match.conditions,
            press_mod=h_mod,
            lineup_uncertainty=lineup_uncertainty,
            validation=home_validation
        )
        
        bpa_away = self._calculate_team_bpa_v2(
            team=match.away_team,
            is_home=False,
            conditions=match.conditions,
            press_mod=a_mod,
            lineup_uncertainty=lineup_uncertainty,
            validation=away_validation
        )
        
        # Ajuste por diferencial de calidad de datos entre equipos
        if lineup_data and lineup_data.get('freshness'):
            freshness = lineup_data.get('freshness')
            if freshness in ['fallback', 'stale']:
                diff = abs(bpa_home - bpa_away)
                if diff > 0.1:
                    adjustment = 1.0 - (lineup_uncertainty * 0.5)
                    if bpa_home > bpa_away:
                        bpa_home *= adjustment
                        bpa_away /= adjustment
                    else:
                        bpa_away *= adjustment
                        bpa_home /= adjustment

        return {
            "home_bpa": round(bpa_home, 4),
            "away_bpa": round(bpa_away, 4),
            "advantage": self._determine_advantage(bpa_home, bpa_away),
            "data_quality": {
                "lineup_uncertainty": lineup_uncertainty,
                "home_validation": home_validation,
                "away_validation": away_validation,
                "confidence_adjusted": 1.0 - lineup_uncertainty
            }
        }

    def _validate_lineup_roles(
        self, 
        team: Team, 
        actual_lineup: List[str], 
        bajas: List[str]
    ) -> Dict:
        """
        Valida que los roles asignados a jugadores estén presentes en alineación real.
        """
        if not actual_lineup:
            return {
                "valid": False,
                "roles_present": set(),
                "missing_critical_roles": self.CRITICAL_ROLES,
                "penalty": len(self.CRITICAL_ROLES) * self.ROLE_ABSENCE_PENALTY,
                "note": "Sin datos de alineación real"
            }
        
        lineup_lower = {name.lower().strip() for name in actual_lineup}
        bajas_lower = {name.lower().strip() for name in bajas}
        
        roles_present = set()
        missing_players = []
        
        for player in team.players:
            player_name = player.name.lower().strip()
            
            is_present = any(
                player_name in lineup_name or lineup_name in player_name 
                for lineup_name in lineup_lower
            )
            
            is_baja = any(
                player_name in baja_name or baja_name in player_name
                for baja_name in bajas_lower
            )
            
            if is_present and not is_baja and player.node_role != NodeRole.NONE:
                roles_present.add(player.node_role)
            elif player.node_role in self.CRITICAL_ROLES and (not is_present or is_baja):
                missing_players.append((player.name, player.node_role))
        
        missing_critical = self.CRITICAL_ROLES - roles_present
        penalty = len(missing_critical) * self.ROLE_ABSENCE_PENALTY
        
        return {
            "valid": len(missing_critical) == 0,
            "roles_present": roles_present,
            "missing_critical_roles": missing_critical,
            "missing_players": missing_players,
            "penalty": min(penalty, 0.30)
        }

    def _calculate_team_bpa_v2(
        self,
        team: Team,
        is_home: bool,
        conditions,
        press_mod: float = 1.0,
        lineup_uncertainty: float = 0.0,
        validation: Optional[Dict] = None
    ) -> float:
        """
        Versión mejorada del cálculo BPA con validación de alineación.
        """
        total_score = 0.0
        active_players = 0
        
        for player in team.players:
            if player.node_role == NodeRole.NONE:
                continue
                
            if validation and validation.get("missing_players"):
                player_missing = any(
                    mp[0] == player.name for mp in validation["missing_players"]
                )
                if player_missing:
                    continue
            
            weight = self.WEIGHTS.get(player.node_role, 0)
            status_val = self._get_status_value(player.status)
            form_val = max(0.1, min(1.0, player.rating_last_5 / 10.0))
            
            node_score = weight * status_val * form_val
            total_score += node_score
            active_players += 1
        
        if active_players == 0:
            total_score = 0.5
            
        if validation:
            total_score *= (1.0 - validation.get("penalty", 0))
        
        context_factor = self.FACTOR_HOME if is_home else self.FACTOR_AWAY
        
        days_rest = getattr(team, 'days_rest', 5)
        if days_rest < 3:
            context_factor *= 0.88
        elif days_rest < 4:
            context_factor *= 0.92
            
        h2h_bias = getattr(team, 'h2h_bias', 1.0)
        context_factor *= max(0.9, min(1.1, h2h_bias))
        
        try:
            kb_bias = self.kb.get_team_factor(team.name, "LOCAL" if is_home else "VISITANTE")
            context_factor *= (1.0 + max(-0.1, min(0.1, kb_bias)))
        except Exception:
            pass
        
        if getattr(team, 'motivation_level', 1.0) > 1.0:
            context_factor *= self.FACTOR_MOTIVATION_HIGH
            
        if conditions:
            context_factor = self._apply_weather_factors(context_factor, conditions, team)
        
        factor_c = getattr(team, 'factor_c', 1.0)
        uncertainty_factor = 1.0 - (lineup_uncertainty * 0.5)
        
        final_bpa = total_score * context_factor * factor_c * press_mod * uncertainty_factor
        
        return max(0.2, min(0.9, final_bpa))

    def _apply_weather_factors(self, base_factor: float, conditions, team: Team) -> float:
        factor = base_factor
        
        if isinstance(conditions, dict):
            try:
                from src.models.base import MatchConditions
                conditions = MatchConditions(**{
                    k: v for k, v in conditions.items() 
                    if k in MatchConditions.model_fields
                })
            except Exception:
                return factor
        
        if hasattr(conditions, 'rain_mm') and conditions.rain_mm > 5:
            if getattr(team, 'tactical_style', '') == "Tiki-Taka":
                factor *= 0.85
            else:
                factor *= self.FACTOR_BAD_WEATHER
                
        if hasattr(conditions, 'wind_kmh') and conditions.wind_kmh > 30:
            factor *= self.FACTOR_BAD_WEATHER
            
        return factor

    def _get_status_value(self, status: PlayerStatus) -> float:
        status_map = {
            PlayerStatus.TITULAR: 1.0,
            PlayerStatus.DUDA: 0.5,
            PlayerStatus.BAJA: 0.0,
            PlayerStatus.SUPLENTE: 0.25
        }
        return status_map.get(status, 0.25)

    def _determine_advantage(self, bpa_home: float, bpa_away: float) -> str:
        diff = bpa_home - bpa_away
        abs_diff = abs(diff)
        
        if abs_diff < 0.05:
            return "Equilibrado"
        
        direction = "Local" if diff > 0 else "Visitante"
        
        if abs_diff > 0.15:
            return f"Ventaja {direction} (Decisiva)"
        elif abs_diff > 0.08:
            return f"Ventaja {direction} (Clara)"
        else:
            return f"Ventaja {direction} (Moderada)"

    def calculate_bpa_with_fallback(
        self,
        match: Match,
        press_modifiers: Optional[Dict] = None,
        lineup_data: Optional[Dict] = None
    ) -> Dict:
        try:
            uncertainty = lineup_data.get('uncertainty_penalty', 0.25) if lineup_data else 0.25
            return self.calculate_match_bpa(match, press_modifiers, uncertainty, lineup_data)
        except Exception as e:
            return {
                "home_bpa": 0.5,
                "away_bpa": 0.5,
                "advantage": "Equilibrado (Error de cálculo)",
                "data_quality": {
                    "error": str(e),
                    "lineup_uncertainty": 1.0,
                    "fallback_used": True
                }
            }