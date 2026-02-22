import pandas as pd
from typing import Dict, Any
from src.logic.ml_engine import MLEngine
from src.data.db_manager import DataManager
from src.data.pipeline import DataPipeline

class TrainingManager:
    """
    Orquestador para el entrenamiento continuo de los modelos de LAGEMA JARG74.
    Automatiza el ciclo: Cargar -> Procesar -> Entrenar -> Evaluar.
    """
    
    def __init__(self, db_manager: DataManager, ml_engine: MLEngine):
        self.db = db_manager
        self.ml = ml_engine
        self.pipeline = DataPipeline()

    def run_full_training_cycle(self) -> Dict[str, Any]:
        """
        Ejecuta un ciclo completo de entrenamiento con datos de la base de datos.
        """
        # 1. Cargar datos históricos
        # Nota: En un entorno real, esto vendría de self.db.get_all_matches()
        # Para la demostración, generamos un dataset sintético realista
        data = self._generate_synthetic_historical_data(n_matches=200)
        
        # 2. Pipeline de Feature Engineering
        clean_data = self.pipeline.clean_match_data(data)
        features_df = self.pipeline.extract_features(clean_data)
        
        # 3. Entrenamiento
        metrics = self.ml.train(features_df)
        
        # 4. Validación Cruzada
        X = features_df.drop(columns=['target_winner', 'match_id'])
        y = features_df['target_winner']
        cv_metrics = self.ml.cross_validate(X, y)
        
        return {
            "training_metrics": metrics,
            "cv_metrics": cv_metrics,
            "samples_analyzed": len(features_df)
        }

    def _generate_synthetic_historical_data(self, n_matches=100) -> pd.DataFrame:
        """Genera un dataset sintético para calibración inicial."""
        import numpy as np
        np.random.seed(74)
        
        data = []
        for i in range(n_matches):
            home_xg = np.random.uniform(0.5, 3.0)
            away_xg = np.random.uniform(0.5, 2.5)
            
            # Lógica simple para determinar ganador real
            if home_xg > away_xg + 1.0: winner = 1 # Local
            elif away_xg > home_xg + 1.0: winner = 2 # Visitante
            else: winner = 0 # Empate
            
            data.append({
                "match_id": f"hist_{i}",
                "home_xg": home_xg,
                "away_xg": away_xg,
                "home_possession": np.random.uniform(40, 60),
                "ppda": np.random.uniform(7, 15),
                "target_winner": winner
            })
            
        return pd.DataFrame(data)
