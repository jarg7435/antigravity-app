from typing import List, Dict
from src.models.base import Team, Player, NodeRole, PlayerStatus

class Validator:
    """
    Implements 'Blindaje V5.0' logic: Validates alignment against predictions.
    """
    
    @staticmethod
    def validate_lineup(predicted_team: Team, confirmed_lineup_names: List[str]) -> Dict[str, List[str]]:
        """
        Compares confirmed lineup names against the predicted team's key nodes.
        Returns a dict with 'alerts' and 'missing_nodes'.
        """
        alerts = []
        missing_nodes = []
        
        # Normalize names for comparison (simple lowercase check)
        confirmed_set = {name.lower() for name in confirmed_lineup_names}
        
        for player in predicted_team.players:
            # We only care about Key Nodes and Titulars for critical alerts
            if player.node_role != NodeRole.NONE and player.status == PlayerStatus.TITULAR:
                if player.name.lower() not in confirmed_set:
                    # CRITICAL MISS
                    alert_msg = f"CRÍTICO: El jugador clave '{player.name}' ({player.node_role.value}) NO está en la alineación confirmada."
                    alerts.append(alert_msg)
                    missing_nodes.append(player.name)
        
        return {
            "alerts": alerts,
            "missing_key_players": missing_nodes
        }

    @staticmethod
    def suggest_replacements(team: Team, missing_player_name: str) -> Player:
        """
        Finds a suitable replacement from the bench (Suplente) with same position.
        """
        missing_player = next((p for p in team.players if p.name == missing_player_name), None)
        if not missing_player:
            return None
            
        # Find best sub in same position
        candidates = [p for p in team.players 
                      if p.position == missing_player.position 
                      and p.status == PlayerStatus.SUPLENTE]
        
        # Sort by rating (simple heuristic)
        candidates.sort(key=lambda p: p.rating_last_5, reverse=True)
        
        return candidates[0] if candidates else None
