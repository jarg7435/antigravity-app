import numpy as np
from typing import Dict, List, Optional
from src.models.base import PredictionResult

class ValueEngine:
    """
    Calcula el valor esperado de una apuesta comparando probabilidades IA con cuotas de mercado.
    Implementa el Criterio de Kelly para gestión de riesgo.
    """

    def calculate_value(self, ia_prob: float, market_decimal_odds: float) -> float:
        """
        Calcula el valor esperado (EV).
        EV = (IA_Prob * Cuota) - 1
        """
        if market_decimal_odds <= 1.0: return 0.0
        return (ia_prob * market_decimal_odds) - 1.0

    def get_kelly_stake(self, ia_prob: float, market_decimal_odds: float, fractional_kelly: float = 0.25) -> float:
        """
        Calcula el porcentaje de bankroll a apostar según el Criterio de Kelly.
        f* = (p * (b + 1) - 1) / b
        Donde:
        p = Probabilidad IA
        b = Cuota decimal - 1
        fractional_kelly = Multiplicador para reducir volatilidad (default 1/4 Kelly).
        """
        if market_decimal_odds <= 1.0 or ia_prob <= 0: return 0.0
        
        b = market_decimal_odds - 1.0
        p = ia_prob
        q = 1.0 - p
        
        kelly_pct = (p * (b + 1) - 1) / b
        
        # Aplicar Fractional Kelly y asegurar que no sea negativo
        return max(0.0, kelly_pct * fractional_kelly)

    def find_opportunities(self, prediction: PredictionResult, market_odds: Dict[str, float]) -> List[Dict]:
        """
        Escanea todos los mercados de una predicción buscando valor.
        market_odds: {"1": 2.10, "X": 3.40, "2": 4.50}
        """
        opportunities = []
        
        mapping = {
            "1": prediction.win_prob_home,
            "X": prediction.draw_prob,
            "2": prediction.win_prob_away
        }
        
        for market, odd in market_odds.items():
            if market in mapping:
                prob = mapping[market]
                value = self.calculate_value(prob, odd)
                
                if value > 0.05: # Solo si hay > 5% de valor
                    stake = self.get_kelly_stake(prob, odd)
                    opportunities.append({
                        "market": market,
                        "ia_prob": prob,
                        "odds": odd,
                        "value_pct": round(value * 100, 2),
                        "suggested_stake_pct": round(stake * 100, 2),
                        "roi_projected": round(value * 100, 2)
                    })
        
        return sorted(opportunities, key=lambda x: x['value_pct'], reverse=True)
