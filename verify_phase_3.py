from src.logic.value_engine import ValueEngine
from src.data.bankroll_manager import BankrollManager
from src.models.base import PredictionResult

def verify_phase_3():
    print("--- Verificacion de Fase 3: Optimizacion y Apuestas ---")
    
    ve = ValueEngine()
    bm = BankrollManager("data_test") # Usar directorio de test
    
    # 1. Simular una prediccion de la IA
    pred = PredictionResult(
        match_id="test_001",
        bpa_home=8.5,
        bpa_away=7.2,
        win_prob_home=0.65,
        draw_prob=0.20,
        win_prob_away=0.15,
        total_goals_expected=2.5,
        both_teams_to_score_prob=0.55,
        score_prediction="2-0",
        confidence_score=0.85
    )
    
    # 2. Simular cuotas de mercado atractivas (Valor detectado)
    # Si la IA dice 65% (cuota justa 1.53) y el mercado ofrece 2.10
    market_odds = {"1": 2.10, "X": 3.40, "2": 4.50}
    
    opps = ve.find_opportunities(pred, market_odds)
    
    print(f"\nOportunidades de Valor:")
    for opp in opps:
        print(f"- Mercado {opp['market']}: Valor {opp['value_pct']}% | Cuota {opp['odds']} | Stake {opp['suggested_stake_pct']}%")

    # 3. Registrar apuesta y simular resultado
    if opps:
        best = opps[0]
        print(f"\nRegistrando apuesta de {best['suggested_stake_pct']}% del bankroll...")
        bm.register_bet("test_001", best['market'], best['odds'], 100.0, result=True) # Ganada
        
        summary = bm.get_summary()
        print(f"\nResumen Bankroll:")
        print(f"- Balance: {summary['balance']}€")
        print(f"- ROI: {summary['roi']}%")
        print(f"- Profit: {summary['profit']}€")

    if summary['roi'] > 0:
        print("\n✅ VERIFICACION EXITOSA: Sistema de valor y ROI operativos.")
    else:
        print("\n❌ FALLO: El ROI no se calculo correctamente.")

if __name__ == "__main__":
    verify_phase_3()
