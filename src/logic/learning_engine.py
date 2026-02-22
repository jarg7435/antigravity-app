from src.models.base import MatchOutcome, PredictionResult
from src.logic.bpa_engine import BPAEngine
from src.data.knowledge_base import KnowledgeBase

class LearningEngine:
    """
    Compares predictions with real results and updates the persistent Knowledge Base.
    """
    
    def __init__(self, bpa_engine: BPAEngine):
        self.bpa_engine = bpa_engine
        self.kb = KnowledgeBase()

    def process_result(self, prediction: PredictionResult, outcome: MatchOutcome, home_team_name: str, away_team_name: str) -> str:
        """
        Analyzes discrepancy, updates team-specific factors, and logs stats.
        """
        report = []
        report.append(f"🔄 **Procesando Resultado: {outcome.match_id}**")
        
        # 1. Determine Predicted Winner
        predicted_winner = "EMPATE"
        if prediction.win_prob_home > 0.45: predicted_winner = "LOCAL"
        elif prediction.win_prob_away > 0.45: predicted_winner = "VISITANTE"
        
        success = (predicted_winner == outcome.actual_winner)
        
        if not success:
            report.append(f"❌ Error: Predicho {predicted_winner} vs Real {outcome.actual_winner}")
            self._adjust_team_factors(prediction, outcome, home_team_name, away_team_name, report)
            self.kb.log_result(outcome.match_id, False, f"Missed Winner. {predicted_winner} != {outcome.actual_winner}")
        else:
            report.append(f"✅ Acierto: El sistema predijo correctamente ({outcome.actual_winner}).")
            self.kb.log_result(outcome.match_id, True, "Correct Winner Prediction")
            
        return "\n".join(report)

    def generate_comparison_report(self, prediction: PredictionResult, outcome: MatchOutcome) -> list:
        """
        Generates a structured report for UI display with 🟢/🔴 lights.
        """
        comparison = []
        
        # 1. Winner
        pred_winner = "EMPATE"
        if prediction.win_prob_home > 0.45: pred_winner = "LOCAL"
        elif prediction.win_prob_away > 0.45: pred_winner = "VISITANTE"
        
        is_winner_hit = (pred_winner == outcome.actual_winner)
        comparison.append({
            "Mercado": "Ganador (1X2)",
            "Predicción": pred_winner,
            "Real": outcome.actual_winner,
            "Estado": "🟢 HIT" if is_winner_hit else "🔴 MISS"
        })
        
        # 2. Corners
        self._add_market_comparison(comparison, "Córners", prediction.predicted_corners, outcome.home_corners + outcome.away_corners)
        
        # 3. Cards
        self._add_market_comparison(comparison, "Tarjetas", prediction.predicted_cards, outcome.home_cards + outcome.away_cards)
        
        # 4. Shots
        self._add_market_comparison(comparison, "Remates", prediction.predicted_shots, outcome.home_shots + outcome.away_shots)
        
        return comparison

    def _add_market_comparison(self, comparison_list, market_name, pred_range_str, actual_value):
        """
        Helper to compare a range string (e.g. '8-10') with an actual integer.
        Handles both single values and ranges.
        """
        # Remove emojis if present
        clean_range = pred_range_str.replace("🏠", "").replace("✈️", "").strip()
        
        # Extract numbers from range string like "8-10" or "🏠 4-6 | ✈️ 3-5"
        # We'll simplify to total for the comparative report
        import re
        numbers = [int(n) for n in re.findall(r'\d+', clean_range)]
        
        if not numbers:
            status = "⚪ N/A"
        else:
            # If we have local/away ranges, we sum the averages for a total comparison
            if len(numbers) >= 4:
                min_total = numbers[0] + numbers[2]
                max_total = numbers[1] + numbers[3]
            elif len(numbers) == 2:
                min_total, max_total = numbers[0], numbers[1]
            else:
                min_total = max_total = numbers[0]

            is_hit = min_total <= actual_value <= max_total
            status = "🟢 HIT" if is_hit else "🔴 MISS"
            pred_display = f"{min_total}-{max_total}"
        
        comparison_list.append({
            "Mercado": market_name,
            "Predicción": pred_display if numbers else pred_range_str,
            "Real": str(actual_value),
            "Estado": status
        })

    def _adjust_team_factors(self, prediction, outcome, home_team, away_team, report):
        """
        Adjusts specific team bias in KnowledgeBase.
        """
        adjustment = 0.02
        
        if outcome.actual_winner == "LOCAL" and prediction.win_prob_home < 0.5:
             # Home Team performed better than expected
             self.kb.update_team_factor(home_team, "LOCAL", adjustment)
             report.append(f"📈 Aprendizaje: {home_team} (Local) subestimado. Factor +{adjustment}.")
             
        elif outcome.actual_winner == "VISITANTE" and prediction.win_prob_away < 0.5:
             # Away Team performed better
             self.kb.update_team_factor(away_team, "VISITANTE", adjustment)
             report.append(f"📈 Aprendizaje: {away_team} (Visitante) subestimado. Factor +{adjustment}.")
             
        elif outcome.actual_winner == "EMPATE":
            report.append("⚠️ Empate complejo. Sin ajustes de factor esta vez.")
