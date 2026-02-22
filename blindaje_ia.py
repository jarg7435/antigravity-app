import re
from typing import List, Dict, Optional
from src.models.base import Match, Team, Player, NodeRole

class BlindajeIA:
    """
    Expert Module for Cross-Referencing Elite Sources (The Big 5)
    and calculating Factor C (Confidence Variable).
    """
    
    SOURCES = {
        "La Liga": ["Fútbol Fantasy", "Diario AS", "Marca"],
        "Premier League": ["Premier Injuries", "The Athletic"],
        "Serie A": ["La Gazzetta dello Sport", "SOS Fanta"],
        "Bundesliga": ["Kicker", "Ligainsider"],
        "Ligue 1": ["L'Équipe", "RMC Sport"]
    }

    KEYWORDS = {
        "negative": [
            "lesión", "lesionado", "duda", "molestias", "al margen", "no entrena",
            "injury", "doubtful", "unfit", "out", "sidelined", "not training",
            "infortunio", "indisponibile", "dubbio", "differenziato",
            "verletzt", "fraglich", "ausfall", "einzeltraining",
            "blessé", "incertain", "forfait", "ménagé"
        ],
        "positive": [
            "titular", "confirmado", "entrena con el grupo",
            "confirmed", "starting", "fit", "training with team",
            "titolare", "confermato",
            "startelf", "bereit",
            "titulaire", "confirmé"
        ]
    }

    def __init__(self):
        pass

    def calculate_factor_c(self, match: Match, team: Team) -> float:
        """
        Calculates the Factor C (Confidence) for a team based on external reports.
        Factor C starts at 1.0 and is penalized if 'Anchor Nodes' have issues.
        """
        factor_c = 1.0
        
        # Identify Anchor Nodes (Finalizers and Creators)
        anchor_nodes = [p for p in team.players if p.node_role in [NodeRole.FINALIZER, NodeRole.CREATOR]]
        
        # Check if we have elite reports for this match
        # (This assumes the external analyst or fetcher populated match.elite_reports)
        # For now, we simulate the logic of checking keywords in available context
        
        for player in anchor_nodes:
            player_report = self._get_player_status_from_context(player, match)
            if player_report == "HIGH_RISK":
                factor_c *= 0.85 # 15% penalty per key player with issues
            elif player_report == "MEDIUM_RISK":
                factor_c *= 0.93 # 7% penalty for doubts
                
        return round(max(0.5, factor_c), 4)

    def _get_player_status_from_context(self, player: Player, match: Match) -> str:
        """
        Mock/Internal logic to scan reports for keywords about a specific player.
        """
        # In a real integration, Match would have a 'scraped_context' field
        context = getattr(match, 'external_analysis_summary', "").lower()
        
        if player.name.lower() in context:
            # Check for negative keywords near the name
            for kw in self.KEYWORDS["negative"]:
                if kw in context:
                    # Check both directions (name followed by kw, or kw followed by name)
                    patterns = [
                        rf"{re.escape(player.name.lower())}[^.]*?{re.escape(kw)}",
                        rf"{re.escape(kw)}[^.]*?{re.escape(player.name.lower())}"
                    ]
                    for pattern in patterns:
                        match_obj = re.search(pattern, context)
                        if match_obj and len(match_obj.group(0)) < 40:
                            print(f"DEBUG: Found negative match for {player.name}: {pattern}")
                            return "HIGH_RISK"
                    
            for kw in self.KEYWORDS["positive"]:
                 if kw in context:
                    patterns = [
                        rf"{re.escape(player.name.lower())}.{{0,60}}{re.escape(kw)}",
                        rf"{re.escape(kw)}.{{0,60}}{re.escape(player.name.lower())}"
                    ]
                    for pattern in patterns:
                        if re.search(pattern, context):
                            return "SAFE"
                     
        return "NEUTRAL"

    def get_elite_sources(self, league: str) -> List[str]:
        return self.SOURCES.get(league, [])
