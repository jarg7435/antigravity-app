import sqlite3
import json
from datetime import datetime
from typing import List, Optional
from src.models.base import Match, PredictionResult

class DataManager:
    def __init__(self, db_path="data/lagema.db"):
        self.db_path = db_path
        self._init_db()

    def _init_db(self):
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()
        
        # Matches Table: Stores full match object as JSON
        c.execute('''
            CREATE TABLE IF NOT EXISTS matches (
                id TEXT PRIMARY KEY,
                date TEXT,
                competition TEXT,
                home_team TEXT,
                away_team TEXT,
                data_json TEXT
            )
        ''')

        # Predictions Table
        c.execute('''
            CREATE TABLE IF NOT EXISTS predictions (
                match_id TEXT PRIMARY KEY,
                prediction_json TEXT,
                created_at TEXT
            )
        ''')
        
        conn.commit()
        conn.close()

    def save_match(self, match: Match):
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()
        data = match.model_dump_json()
        
        c.execute('''
            INSERT OR REPLACE INTO matches (id, date, competition, home_team, away_team, data_json)
            VALUES (?, ?, ?, ?, ?, ?)
        ''', (match.id, match.date.isoformat(), match.competition, match.home_team.name, match.away_team.name, data))
        
        conn.commit()
        conn.close()

    def get_match(self, match_id: str) -> Optional[Match]:
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()
        c.execute('SELECT data_json FROM matches WHERE id = ?', (match_id,))
        row = c.fetchone()
        conn.close()
        
        if row:
            return Match.model_validate_json(row[0])
        return None

    def get_recent_matches(self, limit=10) -> List[Match]:
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()
        c.execute('SELECT data_json FROM matches ORDER BY date DESC LIMIT ?', (limit,))
        rows = c.fetchall()
        conn.close()
        
        return [Match.model_validate_json(r[0]) for r in rows]

    def save_prediction(self, prediction: PredictionResult):
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()
        data = prediction.model_dump_json()
        
        c.execute('''
            INSERT OR REPLACE INTO predictions (match_id, prediction_json, created_at)
            VALUES (?, ?, ?)
        ''', (prediction.match_id, data, datetime.now().isoformat()))
        
        conn.commit()
        conn.close()

    def get_prediction(self, match_id: str) -> Optional[PredictionResult]:
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()
        c.execute('SELECT prediction_json FROM predictions WHERE match_id = ?', (match_id,))
        row = c.fetchone()
        conn.close()
        
        if row:
            return PredictionResult.model_validate_json(row[0])
        return None
