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

    # =========================================================================
    # API PÚBLICA — Panel de Estudios Guardados
    # =========================================================================

    def get_all_studies(self, limit: int = 50) -> List[dict]:
        """
        Devuelve todos los estudios guardados con su estado:
        - PENDIENTE: predicción guardada pero sin resultado real
        - COMPLETADO: predicción + resultado real introducido
        """
        studies = []

        if self.use_supabase:
            try:
                # Obtener predicciones ordenadas
                preds = self._sb_get("predictions",
                    "select=match_id,created_at&order=created_at.desc&limit=50")
                if not preds:
                    preds = []

                # Obtener resultados ya validados
                res_ids = set()
                try:
                    resultados = self._sb_get("resultados", "select=match_id")
                    res_ids = {r["match_id"] for r in (resultados or [])}
                except Exception:
                    pass

                # Obtener todos los matches — Supabase guarda todo en data_json
                all_matches_raw = self._sb_get("matches",
                    "select=id,data_json&order=date.desc&limit=200") or []
                matches_map = {}
                for m in all_matches_raw:
                    mid_m = m.get("id","")
                    try:
                        mdata = json.loads(m.get("data_json","{}"))
                        ht = mdata.get("home_team",{})
                        at = mdata.get("away_team",{})
                        matches_map[mid_m] = {
                            "home_team": ht.get("name","?") if isinstance(ht,dict) else str(ht),
                            "away_team": at.get("name","?") if isinstance(at,dict) else str(at),
                            "date": str(mdata.get("date",""))[:10],
                            "competition": mdata.get("competition","")
                        }
                    except Exception:
                        matches_map[mid_m] = {"home_team":"?","away_team":"?","date":"","competition":""}

                for p in preds:
                    mid = p.get("match_id", "")
                    if not mid:
                        continue
                    m = matches_map.get(mid)
                    if m:
                        home = m.get("home_team", "?")
                        away = m.get("away_team", "?")
                        date = (m.get("date") or "")[:10]
                        comp = m.get("competition", "")
                    else:
                        # Sin datos de partido, mostrar igual con match_id
                        home = mid[:12]
                        away = "?"
                        date = (p.get("created_at") or "")[:10]
                        comp = ""
                    studies.append({
                        "match_id": mid,
                        "home_team": home,
                        "away_team": away,
                        "date": date,
                        "competition": comp,
                        "status": "✅ COMPLETADO" if mid in res_ids else "🟡 PENDIENTE",
                        "created_at": (p.get("created_at") or "")[:16]
                    })
            except Exception as e:
                print(f"[DB] Error get_all_studies Supabase: {e}")
        else:
            try:
                conn = sqlite3.connect(self.db_path)
                # Predicciones
                rows = conn.execute('''
                    SELECT p.match_id, p.created_at,
                           m.home_team, m.away_team, m.date, m.competition
                    FROM predictions p
                    LEFT JOIN matches m ON p.match_id = m.id
                    ORDER BY p.created_at DESC LIMIT ?
                ''', (limit,)).fetchall()
                # IDs ya validados
                res_rows = conn.execute('SELECT match_id FROM resultados').fetchall()
                res_ids = {r[0] for r in res_rows}
                conn.close()
                for row in rows:
                    mid, created, home, away, date, comp = row
                    studies.append({
                        "match_id": mid,
                        "home_team": home or "?",
                        "away_team": away or "?",
                        "date": (date or "")[:10],
                        "competition": comp or "",
                        "status": "✅ COMPLETADO" if mid in res_ids else "🟡 PENDIENTE",
                        "created_at": (created or "")[:16]
                    })
            except Exception as e:
                print(f"[DB] Error get_all_studies: {e}")

        return studies
    def delete_study(self, match_id: str) -> bool:
        """
        Elimina un estudio (predicción + partido) de la BD.
        NO borra el resultado real si ya estaba validado.
        """
        try:
            if self.use_supabase:
                # Borrar predicción
                url_pred = f"{self.supabase_url}/rest/v1/predictions?match_id=eq.{match_id}"
                headers = {**self._sb_headers(), "Prefer": "return=minimal"}
                import requests as _req
                _req.delete(url_pred, headers=headers, timeout=10)
                # Borrar partido
                url_match = f"{self.supabase_url}/rest/v1/matches?id=eq.{match_id}"
                _req.delete(url_match, headers=headers, timeout=10)
            else:
                conn = sqlite3.connect(self.db_path)
                conn.execute("DELETE FROM predictions WHERE match_id=?", (match_id,))
                conn.execute("DELETE FROM matches WHERE id=?", (match_id,))
                conn.commit()
                conn.close()
            print(f"[DB] ✅ Estudio eliminado: {match_id}")
            return True
        except Exception as e:
            print(f"[DB] Error delete_study: {e}")
            return False

    def get_semaforo_history(self, limit: int = 100) -> List[dict]:
        """
        Devuelve historial completo de semáforos por partido.
        Primero busca en tabla aprendizaje (datos detallados).
        Si está vacía, reconstruye los semáforos desde resultados+predictions.
        """
        from collections import OrderedDict
        import json, re

        results = []
        try:
            # 1. Intentar desde tabla aprendizaje (datos completos)
            if self.use_supabase:
                rows = self._sb_get("aprendizaje",
                    f"select=match_id,mercado,predicho,real,acierto,home_team,away_team,competition,created_at"
                    f"&order=created_at.desc&limit={limit*4}")
            else:
                conn = sqlite3.connect(self.db_path)
                raw = conn.execute(
                    "SELECT match_id,mercado,predicho,real,acierto,home_team,away_team,competition,created_at "
                    "FROM aprendizaje ORDER BY created_at DESC LIMIT ?", (limit*4,)).fetchall()
                conn.close()
                rows = [{"match_id":r[0],"mercado":r[1],"predicho":r[2],"real":r[3],
                         "acierto":r[4],"home_team":r[5],"away_team":r[6],
                         "competition":r[7],"created_at":r[8]} for r in raw]

            if rows:
                partidos = OrderedDict()
                for row in rows:
                    mid = row.get("match_id","")
                    if mid not in partidos:
                        partidos[mid] = {
                            "match_id": mid,
                            "home_team": row.get("home_team","?"),
                            "away_team": row.get("away_team","?"),
                            "competition": row.get("competition",""),
                            "created_at": (row.get("created_at") or "")[:10],
                            "mercados": {}
                        }
                    mercado = row.get("mercado","")
                    partidos[mid]["mercados"][mercado] = {
                        "predicho": row.get("predicho",""),
                        "real": row.get("real",""),
                        "acierto": bool(row.get("acierto",0))
                    }
                return list(partidos.values())[:limit]

            # 2. FALLBACK: reconstruir desde resultados + predictions + matches
            print("[DB] aprendizaje vacío — reconstruyendo semáforos desde resultados")
            if self.use_supabase:
                res_rows = self._sb_get("resultados",
                    "select=match_id,home_score,away_score,winner,corners,cards,shots,created_at"
                    "&order=created_at.desc&limit=50") or []
                # Supabase guarda matches como data_json — deserializar
                raw_matches = self._sb_get("matches", "select=id,data_json") or []
                all_matches = {}
                for m in raw_matches:
                    mid = m.get("id","")
                    try:
                        mdata = json.loads(m.get("data_json","{}"))
                        # Extraer home/away del JSON del Match
                        ht = mdata.get("home_team",{})
                        at = mdata.get("away_team",{})
                        home_name = ht.get("name","?") if isinstance(ht,dict) else str(ht)
                        away_name = at.get("name","?") if isinstance(at,dict) else str(at)
                        all_matches[mid] = {
                            "id": mid,
                            "home_team": home_name,
                            "away_team": away_name,
                            "competition": mdata.get("competition",""),
                            "date": mdata.get("date","")
                        }
                    except Exception:
                        all_matches[mid] = {"id":mid,"home_team":"?","away_team":"?","competition":"","date":""}
                all_preds = {p["match_id"]: p for p in (self._sb_get("predictions",
                    "select=match_id,prediction_json") or [])}
            else:
                conn = sqlite3.connect(self.db_path)
                r_raw = conn.execute(
                    "SELECT match_id,home_score,away_score,winner,corners,cards,shots,created_at "
                    "FROM resultados ORDER BY created_at DESC LIMIT 50").fetchall()
                res_rows = [{"match_id":r[0],"home_score":r[1],"away_score":r[2],
                             "winner":r[3],"corners":r[4],"cards":r[5],
                             "shots":r[6],"created_at":r[7]} for r in r_raw]
                m_raw = conn.execute("SELECT id,home_team,away_team,competition,date FROM matches").fetchall()
                all_matches = {r[0]:{"id":r[0],"home_team":r[1],"away_team":r[2],
                                     "competition":r[3],"date":r[4]} for r in m_raw}
                p_raw = conn.execute("SELECT match_id,prediction_json FROM predictions").fetchall()
                all_preds = {r[0]:{"match_id":r[0],"prediction_json":r[1]} for r in p_raw}
                conn.close()

            for res in res_rows:
                mid = res.get("match_id","")
                match = all_matches.get(mid, {})
                pred_row = all_preds.get(mid, {})
                pred_json = {}
                try:
                    pred_json = json.loads(pred_row.get("prediction_json","{}"))
                except Exception:
                    pass

                home = match.get("home_team","?")
                away = match.get("away_team","?")
                comp = match.get("competition","")
                fecha = (res.get("created_at") or "")[:10]

                real_winner = res.get("winner","")
                real_corners = int(res.get("corners") or 0)
                real_cards = int(res.get("cards") or 0)
                real_shots = int(res.get("shots") or 0)

                mercados = {}

                # 1X2
                pred_winner = "EMPATE"
                ph = float(pred_json.get("win_prob_home",0))
                pa = float(pred_json.get("win_prob_away",0))
                if ph > 0.45: pred_winner = "LOCAL"
                elif pa > 0.45: pred_winner = "VISITANTE"
                mercados["1X2"] = {
                    "predicho": pred_winner,
                    "real": real_winner,
                    "acierto": pred_winner == real_winner
                }

                # Córners
                def parse_range(s):
                    nums = re.findall(r"\d+", str(s or ""))
                    if len(nums) >= 2: return int(nums[0]), int(nums[1])
                    if len(nums) == 1: return int(nums[0]), int(nums[0])
                    return None, None

                for key, pred_key, real_val in [
                    ("Córners",  "predicted_corners", real_corners),
                    ("Tarjetas", "predicted_cards",   real_cards),
                    ("Remates",  "predicted_shots",   real_shots),
                ]:
                    lo, hi = parse_range(pred_json.get(pred_key,""))
                    if lo is not None:
                        hit = lo <= real_val <= hi
                        mercados[key] = {
                            "predicho": f"{lo}-{hi}",
                            "real": str(real_val),
                            "acierto": hit
                        }

                results.append({
                    "match_id": mid,
                    "home_team": home,
                    "away_team": away,
                    "competition": comp,
                    "created_at": fecha,
                    "mercados": mercados
                })

        except Exception as e:
            print(f"[DB] Error get_semaforo_history: {e}")
        return results[:limit]
