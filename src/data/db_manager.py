"""
DataManager — Persistencia Real para LAGEMA JARG74
===================================================
Usa Supabase (PostgreSQL gratuito) como base de datos principal.
Si no está configurado, usa SQLite local como fallback.

Para activar Supabase, añade en Streamlit Cloud Secrets:
    SUPABASE_URL = "https://XXXXXX.supabase.co"
    SUPABASE_KEY = "eyJXXXXXX..."
"""

import os
import json
import sqlite3
from datetime import datetime
from typing import List, Optional, Dict
import requests
from src.models.base import Match, PredictionResult


class DataManager:

    def __init__(self, db_path="data/lagema.db"):
        self.db_path = db_path
        self.supabase_url = os.environ.get("SUPABASE_URL", "").rstrip("/")
        self.supabase_key = os.environ.get("SUPABASE_KEY", "")
        self.use_supabase = bool(self.supabase_url and self.supabase_key)

        if self.use_supabase:
            print("[DB] ✅ Usando Supabase (persistencia permanente)")
            self._init_supabase()
        else:
            print("[DB] ⚠️ Usando SQLite local (se borra en redeploy)")
            self._init_sqlite()

    # =========================================================================
    # SUPABASE (persistencia real)
    # =========================================================================

    def _sb_headers(self):
        return {
            "apikey": self.supabase_key,
            "Authorization": f"Bearer {self.supabase_key}",
            "Content-Type": "application/json",
            "Prefer": "return=minimal"
        }

    def _init_supabase(self):
        """Verifica que las tablas existen. Créalas en el dashboard de Supabase con el SQL de abajo."""
        pass  # Las tablas se crean manualmente en Supabase (ver instrucciones)

    def _sb_get(self, table, filters=""):
        url = f"{self.supabase_url}/rest/v1/{table}?{filters}"
        r = requests.get(url, headers=self._sb_headers(), timeout=10)
        if r.status_code == 200:
            return r.json()
        return []

    def _sb_upsert(self, table, data):
        url = f"{self.supabase_url}/rest/v1/{table}"
        headers = {**self._sb_headers(), "Prefer": "resolution=merge-duplicates,return=minimal"}
        r = requests.post(url, headers=headers, json=data, timeout=10)
        return r.status_code in (200, 201)

    # =========================================================================
    # SQLITE (fallback local)
    # =========================================================================

    def _init_sqlite(self):
        os.makedirs("data", exist_ok=True)
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()
        c.execute('''CREATE TABLE IF NOT EXISTS matches (
            id TEXT PRIMARY KEY, date TEXT, competition TEXT,
            home_team TEXT, away_team TEXT, data_json TEXT)''')
        c.execute('''CREATE TABLE IF NOT EXISTS predictions (
            match_id TEXT PRIMARY KEY, prediction_json TEXT, created_at TEXT)''')
        c.execute('''CREATE TABLE IF NOT EXISTS resultados (
            match_id TEXT PRIMARY KEY, home_score INTEGER, away_score INTEGER,
            winner TEXT, corners INTEGER, cards INTEGER, shots INTEGER,
            shots_on_target INTEGER, home_corners INTEGER, away_corners INTEGER,
            home_cards INTEGER, away_cards INTEGER, home_shots INTEGER, away_shots INTEGER,
            home_shots_on_target INTEGER, away_shots_on_target INTEGER,
            created_at TEXT)''')
        c.execute('''CREATE TABLE IF NOT EXISTS aprendizaje (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            match_id TEXT, mercado TEXT, predicho TEXT, real TEXT,
            error_magnitud REAL, acierto INTEGER, ajuste_aplicado REAL,
            home_team TEXT, away_team TEXT, competition TEXT, created_at TEXT)''')
        c.execute('''CREATE TABLE IF NOT EXISTS factores_equipo (
            equipo TEXT PRIMARY KEY, sesgo_local REAL DEFAULT 0.0,
            sesgo_visitante REAL DEFAULT 0.0, sesgo_empate REAL DEFAULT 0.0,
            sesgo_corners REAL DEFAULT 0.0, sesgo_cards REAL DEFAULT 0.0,
            total_partidos INTEGER DEFAULT 0, aciertos INTEGER DEFAULT 0,
            updated_at TEXT)''')
        conn.commit()
        conn.close()

    # =========================================================================
    # API PÚBLICA — Matches
    # =========================================================================

    def save_match(self, match: Match):
        data_json = match.model_dump_json()
        if self.use_supabase:
            self._sb_upsert("matches", {
                "id": match.id, "date": match.date.isoformat(),
                "competition": match.competition,
                "home_team": match.home_team.name,
                "away_team": match.away_team.name,
                "data_json": data_json
            })
        else:
            conn = sqlite3.connect(self.db_path)
            conn.execute('''INSERT OR REPLACE INTO matches
                (id, date, competition, home_team, away_team, data_json)
                VALUES (?,?,?,?,?,?)''',
                (match.id, match.date.isoformat(), match.competition,
                 match.home_team.name, match.away_team.name, data_json))
            conn.commit(); conn.close()

    def get_match(self, match_id: str) -> Optional[Match]:
        if self.use_supabase:
            rows = self._sb_get("matches", f"id=eq.{match_id}&select=data_json")
            if rows: return Match.model_validate_json(rows[0]["data_json"])
        else:
            conn = sqlite3.connect(self.db_path)
            r = conn.execute('SELECT data_json FROM matches WHERE id=?', (match_id,)).fetchone()
            conn.close()
            if r: return Match.model_validate_json(r[0])
        return None

    def get_recent_matches(self, limit=20) -> List[Match]:
        if self.use_supabase:
            rows = self._sb_get("matches", f"select=data_json&order=date.desc&limit={limit}")
            return [Match.model_validate_json(r["data_json"]) for r in rows]
        else:
            conn = sqlite3.connect(self.db_path)
            rows = conn.execute('SELECT data_json FROM matches ORDER BY date DESC LIMIT ?', (limit,)).fetchall()
            conn.close()
            return [Match.model_validate_json(r[0]) for r in rows]

    # =========================================================================
    # API PÚBLICA — Predictions
    # =========================================================================

    def save_prediction(self, prediction: PredictionResult):
        data_json = prediction.model_dump_json()
        if self.use_supabase:
            self._sb_upsert("predictions", {
                "match_id": prediction.match_id,
                "prediction_json": data_json,
                "created_at": datetime.now().isoformat()
            })
        else:
            conn = sqlite3.connect(self.db_path)
            conn.execute('''INSERT OR REPLACE INTO predictions (match_id, prediction_json, created_at)
                VALUES (?,?,?)''', (prediction.match_id, data_json, datetime.now().isoformat()))
            conn.commit(); conn.close()

    def get_prediction(self, match_id: str) -> Optional[PredictionResult]:
        if self.use_supabase:
            rows = self._sb_get("predictions", f"match_id=eq.{match_id}&select=prediction_json")
            if rows: return PredictionResult.model_validate_json(rows[0]["prediction_json"])
        else:
            conn = sqlite3.connect(self.db_path)
            r = conn.execute('SELECT prediction_json FROM predictions WHERE match_id=?', (match_id,)).fetchone()
            conn.close()
            if r: return PredictionResult.model_validate_json(r[0])
        return None

    # =========================================================================
    # API PÚBLICA — Resultados Reales
    # =========================================================================

    def save_resultado(self, match_id: str, data: dict):
        now = datetime.now().isoformat()
        if self.use_supabase:
            self._sb_upsert("resultados", {"match_id": match_id, **data, "created_at": now})
        else:
            conn = sqlite3.connect(self.db_path)
            conn.execute('''INSERT OR REPLACE INTO resultados
                (match_id, home_score, away_score, winner, corners, cards, shots,
                 shots_on_target, home_corners, away_corners, home_cards, away_cards,
                 home_shots, away_shots, home_shots_on_target, away_shots_on_target, created_at)
                VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)''', (
                match_id,
                data.get("home_score", 0), data.get("away_score", 0), data.get("winner", ""),
                data.get("corners", 0), data.get("cards", 0), data.get("shots", 0),
                data.get("shots_on_target", 0),
                data.get("home_corners", 0), data.get("away_corners", 0),
                data.get("home_cards", 0), data.get("away_cards", 0),
                data.get("home_shots", 0), data.get("away_shots", 0),
                data.get("home_shots_on_target", 0), data.get("away_shots_on_target", 0),
                now
            ))
            conn.commit(); conn.close()

    # =========================================================================
    # API PÚBLICA — Registro de Aprendizaje (errores por mercado)
    # =========================================================================

    def save_aprendizaje(self, records: List[dict]):
        """Guarda los registros de análisis de error por mercado."""
        now = datetime.now().isoformat()
        if self.use_supabase:
            for rec in records:
                self._sb_upsert("aprendizaje", {**rec, "created_at": now})
        else:
            conn = sqlite3.connect(self.db_path)
            for rec in records:
                conn.execute('''INSERT INTO aprendizaje
                    (match_id, mercado, predicho, real, error_magnitud, acierto,
                     ajuste_aplicado, home_team, away_team, competition, created_at)
                    VALUES (?,?,?,?,?,?,?,?,?,?,?)''', (
                    rec.get("match_id"), rec.get("mercado"), rec.get("predicho"),
                    rec.get("real"), rec.get("error_magnitud", 0),
                    1 if rec.get("acierto") else 0,
                    rec.get("ajuste_aplicado", 0),
                    rec.get("home_team"), rec.get("away_team"),
                    rec.get("competition"), now
                ))
            conn.commit(); conn.close()

    def get_aprendizaje_stats(self) -> Dict:
        """Estadísticas de aprendizaje por mercado."""
        stats = {}
        if self.use_supabase:
            rows = self._sb_get("aprendizaje", "select=mercado,acierto,error_magnitud")
        else:
            conn = sqlite3.connect(self.db_path)
            rows = conn.execute(
                'SELECT mercado, acierto, error_magnitud FROM aprendizaje'
            ).fetchall()
            conn.close()
            rows = [{"mercado": r[0], "acierto": r[1], "error_magnitud": r[2]} for r in rows]

        mercados = {}
        for row in rows:
            m = row.get("mercado", "desconocido")
            if m not in mercados:
                mercados[m] = {"total": 0, "aciertos": 0, "error_total": 0.0}
            mercados[m]["total"] += 1
            mercados[m]["aciertos"] += int(row.get("acierto", 0))
            mercados[m]["error_total"] += float(row.get("error_magnitud") or 0)

        for m, d in mercados.items():
            d["precision"] = round(d["aciertos"] / d["total"] * 100, 1) if d["total"] > 0 else 0
            d["error_medio"] = round(d["error_total"] / d["total"], 2) if d["total"] > 0 else 0
        return mercados

    # =========================================================================
    # API PÚBLICA — Factores de Equipo
    # =========================================================================

    def get_team_factor(self, team_name: str) -> dict:
        defaults = {
            "equipo": team_name, "sesgo_local": 0.0, "sesgo_visitante": 0.0,
            "sesgo_empate": 0.0, "sesgo_corners": 0.0, "sesgo_cards": 0.0,
            "total_partidos": 0, "aciertos": 0
        }
        if self.use_supabase:
            rows = self._sb_get("factores_equipo", f"equipo=eq.{requests.utils.quote(team_name)}")
            return rows[0] if rows else defaults
        else:
            conn = sqlite3.connect(self.db_path)
            r = conn.execute(
                'SELECT * FROM factores_equipo WHERE equipo=?', (team_name,)
            ).fetchone()
            conn.close()
            if r:
                cols = ["equipo","sesgo_local","sesgo_visitante","sesgo_empate",
                        "sesgo_corners","sesgo_cards","total_partidos","aciertos","updated_at"]
                return dict(zip(cols, r))
            return defaults

    def update_team_factor(self, team_name: str, campo: str, delta: float):
        now = datetime.now().isoformat()
        current = self.get_team_factor(team_name)
        current[campo] = round(float(current.get(campo, 0.0)) + delta, 4)
        current["updated_at"] = now
        current["total_partidos"] = int(current.get("total_partidos", 0)) + 1

        if self.use_supabase:
            self._sb_upsert("factores_equipo", current)
        else:
            conn = sqlite3.connect(self.db_path)
            conn.execute('''INSERT OR REPLACE INTO factores_equipo
                (equipo, sesgo_local, sesgo_visitante, sesgo_empate,
                 sesgo_corners, sesgo_cards, total_partidos, aciertos, updated_at)
                VALUES (?,?,?,?,?,?,?,?,?)''', (
                team_name,
                current.get("sesgo_local", 0.0), current.get("sesgo_visitante", 0.0),
                current.get("sesgo_empate", 0.0), current.get("sesgo_corners", 0.0),
                current.get("sesgo_cards", 0.0), current.get("total_partidos", 0),
                current.get("aciertos", 0), now
            ))
            conn.commit(); conn.close()

    def get_all_team_factors(self) -> List[dict]:
        if self.use_supabase:
            return self._sb_get("factores_equipo", "order=total_partidos.desc")
        else:
            conn = sqlite3.connect(self.db_path)
            rows = conn.execute(
                'SELECT * FROM factores_equipo ORDER BY total_partidos DESC'
            ).fetchall()
            conn.close()
            cols = ["equipo","sesgo_local","sesgo_visitante","sesgo_empate",
                    "sesgo_corners","sesgo_cards","total_partidos","aciertos","updated_at"]
            return [dict(zip(cols, r)) for r in rows]

    def get_total_stats(self) -> dict:
        """Estadísticas globales del sistema."""
        stats = self.get_aprendizaje_stats()
        total = sum(v["total"] for v in stats.values())
        hits_1x2 = stats.get("1X2", {}).get("aciertos", 0)
        total_1x2 = stats.get("1X2", {}).get("total", 1)
        return {
            "total_partidos": total,
            "precision_1x2": stats.get("1X2", {}).get("precision", 0),
            "precision_corners": stats.get("Córners", {}).get("precision", 0),
            "precision_cards": stats.get("Tarjetas", {}).get("precision", 0),
            "mercados": stats
        }

    @property
    def modo(self):
        return "☁️ Supabase" if self.use_supabase else "💾 SQLite Local"
