from src.models.base import Match, Team, Player, NodeRole, PlayerStatus
from src.data.knowledge_base import KnowledgeBase

class BPAEngine:
    """
    Logic for calculating Balance de Presión Avanzada (BPA).
    """
    
    def __init__(self):
        self.kb = KnowledgeBase()
    
    # Node Weights defined in Phase 2
    WEIGHTS = {
        NodeRole.FINALIZER: 0.35,
        NodeRole.CREATOR: 0.25,
        NodeRole.DEFENSIVE: 0.20,
        NodeRole.KEEPER: 0.15,
        NodeRole.TACTICAL: 0.05
    }

    # Contextual Factors
    FACTOR_HOME = 1.10
    FACTOR_AWAY = 0.95
    FACTOR_BAD_WEATHER = 0.90 # Applied generally if conditions are bad
    FACTOR_MOTIVATION_HIGH = 1.15

    def calculate_match_bpa(self, match: Match) -> dict:
        """
        Calculates BPA for both teams in a match.
        Returns: {'home_bpa': float, 'away_bpa': float, 'details': dict}
        """
        bpa_home = self._calculate_team_bpa(match.home_team, is_home=True, conditions=match.conditions)
        bpa_away = self._calculate_team_bpa(match.away_team, is_home=False, conditions=match.conditions)
        
        return {
            "home_bpa": round(bpa_home, 4),
            "away_bpa": round(bpa_away, 4),
            "advantage": self._determine_advantage(bpa_home, bpa_away)
        }

    def _calculate_team_bpa(self, team: Team, is_home: bool, conditions) -> float:
        total_score = 0.0
        
        for player in team.players:
            if player.node_role == NodeRole.NONE:
                continue
                
            weight = self.WEIGHTS.get(player.node_role, 0)
            status_val = self._get_status_value(player.status)
            form_val = player.rating_last_5 / 10.0 # Normalized 0-1
            
            # BPA Component = Weight * Status * Form
            node_score = weight * status_val * form_val
            total_score += node_score

        # Apply Contextual Factors
        context_factor = self.FACTOR_HOME if is_home else self.FACTOR_AWAY
        
        # New: Team Fatigue Factor (Back-to-back logic)
        # Assuming Team object has a 'days_rest' property (calculated from fixtures)
        days_rest = getattr(team, 'days_rest', 5)
        if days_rest < 4:
            context_factor *= 0.92 # Fatigue penalty
            
        # New: H2H Historical Advantage
        # Assuming Team object has 'h2h_bias' for the specific match-up
        h2h_bias = getattr(team, 'h2h_bias', 1.0)
        context_factor *= h2h_bias
        
        # New: Knowledge Base Bias
        kb_bias = self.kb.get_team_factor(team.name, "LOCAL" if is_home else "VISITANTE")
        context_factor += kb_bias

        if team.motivation_level > 1.0:
            context_factor *= self.FACTOR_MOTIVATION_HIGH
            
        if conditions:
            # Enhanced weather check: Tactical mismatch
            # Example: Tiki-Taka suffers more in heavy rain
            if conditions.rain_mm > 5:
                if team.tactical_style == "Tiki-Taka":
                    context_factor *= 0.85
                else:
                    context_factor *= self.FACTOR_BAD_WEATHER

            if conditions.wind_kmh > 30:
                context_factor *= self.FACTOR_BAD_WEATHER

        return total_score * context_factor

    def _get_status_value(self, status: PlayerStatus) -> float:
        if status == PlayerStatus.TITULAR:
            return 1.0
        elif status == PlayerStatus.DUDA:
            return 0.5
        elif status == PlayerStatus.BAJA:
            return 0.0
        return 0.25 # Suplente might play

    def _determine_advantage(self, bpa_home, bpa_away) -> str:
        diff = bpa_home - bpa_away
        if diff > 0.1: return "Ventaja Local (Clara)"
        if diff > 0.05: return "Ventaja Local (Moderada)"
        if diff < -0.1: return "Ventaja Visitante (Clara)"
        if diff < -0.05: return "Ventaja Visitante (Moderada)"
        return "Equilibrado"
