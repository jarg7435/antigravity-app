import json
import os
from typing import Dict, List
from datetime import datetime

class KnowledgeBase:
    """
    Manages persistent learning data:
    - Team-specific bias factors (e.g., 'Sunderland' overperforms at home).
    - League-wide factors.
    - Historical accuracy logs.
    """
    
    DB_PATH = "data/knowledge_base.json"
    
    def __init__(self):
        self.data = self._load_db()

    def _load_db(self) -> dict:
        if not os.path.exists("data"):
            os.makedirs("data")
            
        if not os.path.exists(self.DB_PATH):
            return {
                "factores_equipo": {},   # { "Real Madrid": {"sesgo_local": 0.05, "sesgo_visitante": 0.0} }
                "registro_historico": [],    # [ { "match": "RxB", "success": true, "timestamp": ... } ]
                "estadisticas": {"total": 0, "hits": 0, "misses": 0}
            }
            
        try:
            with open(self.DB_PATH, "r") as f:
                return json.load(f)
        except:
            return {"team_factors": {}, "history_log": [], "stats": {"total": 0, "hits": 0, "misses": 0}}

    def save(self):
        with open(self.DB_PATH, "w") as f:
            json.dump(self.data, f, indent=4)

    def get_team_factor(self, team_name: str, site: str) -> float:
        # returns adjustment factor (e.g. +0.05) if exists
        tf = self.data["factores_equipo"].get(team_name, {})
        if site == "LOCAL": return tf.get("sesgo_local", 0.0)
        if site == "VISITANTE": return tf.get("sesgo_visitante", 0.0)
        return 0.0

    def update_team_factor(self, team_name: str, site: str, delta: float):
        if team_name not in self.data["factores_equipo"]:
            self.data["factores_equipo"][team_name] = {"sesgo_local": 0.0, "sesgo_visitante": 0.0}
        
        key = "sesgo_local" if site == "LOCAL" else "sesgo_visitante"
        current = self.data["factores_equipo"][team_name][key]
        self.data["factores_equipo"][team_name][key] = round(current + delta, 4)
        self.save()

    def log_result(self, match_id: str, success: bool, details: str):
        self.data["registro_historico"].append({
            "timestamp": datetime.now().isoformat(),
            "match_id": match_id,
            "success": success,
            "detalles": details
        })
        self.data["estadisticas"]["total"] += 1
        if success: self.data["estadisticas"]["hits"] += 1
        else: self.data["estadisticas"]["misses"] += 1
        self.save()

    def get_stats(self):
        return self.data["estadisticas"]
        
    def get_factors(self):
        return self.data["factores_equipo"]
