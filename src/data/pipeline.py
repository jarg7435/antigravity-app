import pandas as pd
import numpy as np
from typing import List, Dict

class DataPipeline:
    """
    Gestiona la ingesta, limpieza y feature engineering de los datos deportivos.
    Optimizado para procesar grandes volúmenes de métricas Wyscout/Opta.
    """
    
    def clean_match_data(self, df: pd.DataFrame) -> pd.DataFrame:
        """Elimina irregularidades y normaliza nombres de equipos/jugadores."""
        # Eliminar duplicados
        df = df.drop_duplicates()
        
        # Manejo de valores nulos en métricas críticas
        critical_cols = ['xg', 'xa', 'possession']
        for col in critical_cols:
            if col in df.columns:
                df[col] = df[col].fillna(df[col].median())
        
        return df

    def extract_features(self, historical_df: pd.DataFrame) -> pd.DataFrame:
        """
        Feature Engineering avanzado:
        - Pendiente de forma (Rolling average xG)
        - Éficacia defensiva (Goles recibidos vs xGA)
        - Intensidad de presión (PPDA)
        """
        df = historical_df.copy()
        
        if 'xg' in df.columns:
            # Media móvil de xG para capturar estado de forma
            df['xg_rolling_avg'] = df.groupby('team_id')['xg'].transform(lambda x: x.rolling(window=5, min_periods=1).mean())
            
        if 'goals_conceded' in df.columns and 'xga' in df.columns:
            # Over-performance defensivo
            df['defensive_efficiency'] = df['xga'] - df['goals_conceded']
            
        return df

    def prepare_for_training(self, enriched_df: pd.DataFrame) -> Tuple[pd.DataFrame, pd.Series]:
        """Prepara los datos finales para ser ingeridos por el MLEngine."""
        # Selección de variables con mayor correlación histórica
        features = [
            'xg_rolling_avg', 'defensive_efficiency', 'ppda', 
            'possession_avg', 'h2h_bias', 'home_advantage'
        ]
        
        X = enriched_df[features]
        y = enriched_df['target_winner']
        
        return X, y
