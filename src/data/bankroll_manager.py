import json
import os
from datetime import datetime
from typing import List, Dict, Any, Optional

class BankrollManager:
    """
    Gestiona el capital del usuario y calcula métricas de rentabilidad.
    Persiste los datos en un archivo JSON local.
    VERSION: 6.25.1
    """
    
    def __init__(self, data_dir: str = "data"):
        self.path = os.path.join(data_dir, "bankroll.json")
        if not os.path.exists(data_dir):
            os.makedirs(data_dir)
            
        self.data = self._load_data()

    def _load_data(self) -> Dict[str, Any]:
        if os.path.exists(self.path):
            with open(self.path, 'r') as f:
                return json.load(f)
        return {
            "initial_capital": 10.0,
            "current_balance": 10.0,
            "transactions": [],
            "stats": {
                "total_invested": 0.0,
                "total_profit": 0.0,
                "roi": 0.0,
                "win_rate": 0.0
            }
        }

    def _save_data(self):
        with open(self.path, 'w') as f:
            json.dump(self.data, f, indent=4)

    def deposit(self, amount: float):
        self.data["current_balance"] += amount
        self._save_data()

    def register_bet(self, match_id: str, market: str, odds: float, stake: float, result: Optional[bool] = None):
        """
        Registra una apuesta. Si result es None, se marca como PENDIENTE.
        """
        transaction = {
            "id": f"bet_{len(self.data['transactions'])}",
            "date": datetime.now().isoformat(),
            "match_id": match_id,
            "market": market,
            "odds": odds,
            "stake": stake,
            "status": "PENDING" if result is None else ("WON" if result else "LOST")
        }
        
        if result is not None:
            self._process_settlement(transaction, result)
        else:
            self.data["current_balance"] -= stake
            
        self.data["transactions"].append(transaction)
        self._save_data()

    def settle_bet(self, transaction_id: str, won: bool):
        """
        Marca una apuesta como liquidada (ACERTADA/FALLADA).
        """
        for i, trans in enumerate(self.data["transactions"]):
            if trans["id"] == transaction_id and trans["status"] == "PENDING":
                trans["status"] = "WON" if won else "LOST"
                self._process_settlement(trans, won)
                self._save_data()
                return True
        return False

    def reset_bankroll(self, initial_capital: float = 10.0):
        """
        Reinicia el bankroll con un nuevo capital inicial.
        """
        self.data = {
            "initial_capital": initial_capital,
            "current_balance": initial_capital,
            "transactions": [],
            "stats": {
                "total_invested": 0.0,
                "total_profit": 0.0,
                "roi": 0.0,
                "win_rate": 0.0
            }
        }
        self._save_data()

    def delete_transaction(self, transaction_id: str):
        """
        Elimina una transacción. ¡Atención! No revierte el balance actual (uso para corrección manual).
        """
        self.data["transactions"] = [t for t in self.data["transactions"] if t["id"] != transaction_id]
        self._save_data()

    def _process_settlement(self, transaction: Dict, won: bool):
        stake = transaction["stake"]
        if won:
            profit = stake * (transaction["odds"] - 1)
            self.data["current_balance"] += (stake + profit)
            self.data["stats"]["total_profit"] += profit
        else:
            self.data["stats"]["total_profit"] -= stake
            
        self.data["stats"]["total_invested"] += stake
        self._update_roi()

    def _update_roi(self):
        invested = self.data["stats"]["total_invested"]
        if invested > 0:
            self.data["stats"]["roi"] = (self.data["stats"]["total_profit"] / invested) * 100

    def get_summary(self) -> Dict[str, Any]:
        return {
            "balance": round(self.data["current_balance"], 2),
            "roi": round(self.data["stats"]["roi"], 2),
            "profit": round(self.data["stats"]["total_profit"], 2),
            "invested": round(self.data["stats"]["total_invested"], 2)
        }
