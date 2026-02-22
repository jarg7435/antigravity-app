from typing import List, Dict, Any
from src.logic.value_engine import ValueEngine
from src.models.base import PredictionResult, MatchOutcome

class Backtester:
    """
    Simula estrategias de apuesta sobre el historial de partidos para validar el ROI.
    """
    
    def __init__(self, value_engine: ValueEngine):
        self.ve = value_engine

    def run_simulation(self, 
                       historical_pairs: List[tuple], # List[ (PredictionResult, MatchOutcome) ]
                       strategy: str = "fixed_stake",
                       initial_bankroll: float = 10.0) -> Dict[str, Any]:
        """
        Ejecuta la simulación.
        historical_pairs: Lista de tuplas (Predicción, Resultado Real).
        """
        current_balance = initial_bankroll
        results = []
        fixed_stake_amount = initial_bankroll * 0.02 # 2% por apuesta
        
        for pred, outcome in historical_pairs:
            # 1. Buscar oportunidades con el valor asignado en el Match (simulado si no hay cuotas reales)
            # En backtesting, si no hay cuotas, simulamos una cuota justa de mercado
            market_odds = self._simulate_market_odds(pred)
            
            opps = self.ve.find_opportunities(pred, market_odds)
            
            if opps:
                best_opp = opps[0] # Tomamos la de mayor valor
                stake = fixed_stake_amount if strategy == "fixed_stake" else (current_balance * best_opp['suggested_stake_pct'] / 100)
                
                # Verificar si ganamos
                won = (best_opp['market'] == outcome.actual_winner)
                
                if won:
                    profit = stake * (best_opp['odds'] - 1)
                    current_balance += profit
                else:
                    current_balance -= stake
                
                results.append({
                    "match_id": outcome.match_id,
                    "won": won,
                    "stake": stake,
                    "balance": current_balance
                })
        
        roi = ((current_balance - initial_bankroll) / (initial_bankroll if initial_bankroll > 0 else 1)) * 100
        
        return {
            "final_balance": round(current_balance, 2),
            "roi": round(roi, 2),
            "total_bets": len(results),
            "win_rate": round(sum(1 for r in results if r['won']) / len(results) * 100, 2) if results else 0,
            "equity_curve": [r['balance'] for r in results]
        }

    def _simulate_market_odds(self, pred: PredictionResult) -> Dict[str, float]:
        """Simula cuotas de mercado realistas basadas en la probabilidad IA + margen de casa (overround)."""
        # Añadimos un margen del 5% a la casa de apuestas
        margin = 1.05
        return {
            "1": round(1.0 / (pred.win_prob_home * margin), 2),
            "X": round(1.0 / (pred.draw_prob * margin), 2),
            "2": round(1.0 / (pred.win_prob_away * margin), 2)
        }
