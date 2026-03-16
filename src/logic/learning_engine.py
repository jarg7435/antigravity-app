"""
LearningEngine — Motor de Aprendizaje Profundo LAGEMA JARG74 v4.1
==================================================================
Correcciones:
- Lógica de rangos corregida (home/away separados luego sumados)
- Validación de existencia de factores antes de UPDATE
- Ponderación por freshness de alineación
- Decay temporal de errores implementado
"""

import re
import math
from datetime import datetime, timedelta
from typing import List, Dict, Tuple, Optional
from src.models.base import MatchOutcome, PredictionResult
from src.logic.bpa_engine import BPAEngine
from src.data.db_manager import DataManager


class LearningEngine:
    MAX_DELTA = 0.05
    SYSTEMATIC_THRESHOLD = 3
    DECAY_DAYS = 30  # Días para que un error pierda relevancia

    def __init__(self, bpa_engine: BPAEngine, db_manager: DataManager = None):
        self.bpa = bpa_engine
        self.db = db_manager or DataManager()

    def process_result(self, prediction: PredictionResult, outcome: MatchOutcome,
                       home_team: str, away_team: str, competition: str = "",
                       lineup_freshness: str = "confirmed") -> str:
        """
        lineup_freshness: 'live', 'confirmed', 'predicted', 'fallback', 'stale'
        Afecta la ponderación del aprendizaje (errores con datos malos pesan menos)
        """
        # Peso del aprendizaje según calidad de datos
        freshness_weights = {
            'live': 1.0, 'confirmed': 0.9, 'predicted': 0.6, 
            'fallback': 0.3, 'stale': 0.1
        }
        learning_weight = freshness_weights.get(lineup_freshness, 0.5)
        
        report = [f"## 🔬 Análisis de Aprendizaje: {home_team} vs {away_team}"]
        report.append(f"📊 Peso del aprendizaje: {learning_weight:.0%} (freshness: {lineup_freshness})")

        self.db.save_resultado(outcome.match_id, {
            "home_score": outcome.home_score, "away_score": outcome.away_score,
            "winner": outcome.actual_winner,
            "corners": outcome.home_corners + outcome.away_corners,
            "cards": outcome.home_cards + outcome.away_cards,
            "shots": outcome.home_shots + outcome.away_shots,
            "shots_on_target": outcome.home_shots_on_target + outcome.away_shots_on_target,
            "home_corners": outcome.home_corners, "away_corners": outcome.away_corners,
            "home_cards": outcome.home_cards, "away_cards": outcome.away_cards,
            "home_shots": outcome.home_shots, "away_shots": outcome.away_shots,
            "home_shots_on_target": outcome.home_shots_on_target,
            "away_shots_on_target": outcome.away_shots_on_target,
            "lineup_freshness": lineup_freshness,  # Nuevo: trazabilidad
        })

        learning_records = []
        market_results = {}

        # --- MERCADO 1X2 ---
        r1x2 = self._analyze_1x2(prediction, outcome, home_team, away_team, learning_weight)
        market_results["1X2"] = r1x2
        learning_records.append({
            "match_id": outcome.match_id, "mercado": "1X2",
            "predicho": r1x2["predicho"], "real": outcome.actual_winner,
            "error_magnitud": r1x2["error_magnitud"], "acierto": r1x2["acierto"],
            "ajuste_aplicado": r1x2["ajuste"],
            "home_team": home_team, "away_team": away_team, 
            "competition": competition, "lineup_freshness": lineup_freshness
        })
        report.append(r1x2["texto"])

        # --- MERCADOS DE RANGO (CÓRNERS, TARJETAS, REMATES) ---
        markets_config = [
            ("Córners", prediction.predicted_corners, 
             outcome.home_corners + outcome.away_corners),
            ("Tarjetas", prediction.predicted_cards, 
             outcome.home_cards + outcome.away_cards),
            ("Remates", prediction.predicted_shots, 
             outcome.home_shots + outcome.away_shots),
        ]
        
        for nombre, pred_str, actual in markets_config:
            r = self._analyze_range_market_v2(nombre, pred_str, actual, outcome.match_id,
                                              home_team, away_team, competition, 
                                              learning_weight, lineup_freshness)
            market_results[nombre] = r
            learning_records.append(r["record"])
            report.append(r["texto"])

        # Guardar con transacción (lista o individual según implementación DB)
        for record in learning_records:
            self.db.save_aprendizaje(record)  # Uno por uno para mejor trazabilidad

        self._apply_team_adjustments_v2(r1x2, home_team, away_team, learning_weight)
        
        bias_report = self._detect_and_fix_systematic_bias_v2(home_team, away_team)
        if bias_report:
            report.append(f"\n### 🧠 Patrón Detectado y Corregido\n{bias_report}")

        hits = sum(1 for r in market_results.values() if r.get("acierto"))
        total_mkts = len(market_results)
        pct = round(hits / total_mkts * 100)
        report.append(f"\n---\n**📊 Resumen: {hits}/{total_mkts} mercados acertados ({pct}%)**")

        stats = self.db.get_total_stats()
        if stats["total_partidos"] > 0:
            report.append(
                f"**📈 Histórico global — 1X2: {stats['precision_1x2']}% | "
                f"Córners: {stats['precision_corners']}% | "
                f"Tarjetas: {stats['precision_cards']}%**"
            )

        return "\n".join(report)

    def _analyze_1x2(self, prediction, outcome, home_team, away_team, 
                     learning_weight: float = 1.0) -> dict:
        """Versión con ponderación por calidad de datos."""
        pred_winner = "EMPATE"
        if prediction.win_prob_home > 0.45:   pred_winner = "LOCAL"
        elif prediction.win_prob_away > 0.45: pred_winner = "VISITANTE"

        acierto = (pred_winner == outcome.actual_winner)

        if outcome.actual_winner == "LOCAL":
            real_prob = prediction.win_prob_home
        elif outcome.actual_winner == "VISITANTE":
            real_prob = prediction.win_prob_away
        else:
            real_prob = 1.0 - prediction.win_prob_home - prediction.win_prob_away

        error_magnitud = round(max(0, 0.45 - real_prob) if not acierto else 0, 3)
        
        # Ajuste ponderado por calidad de datos
        ajuste = 0.0
        texto = ""
        if acierto:
            texto = f"✅ **1X2:** Acierto — {pred_winner} ({outcome.home_score}-{outcome.away_score})"
            # Refuerzo positivo más fuerte si datos eran buenos
            ajuste = 0.005 * learning_weight
        else:
            ajuste = min(self.MAX_DELTA, error_magnitud * 0.5 * learning_weight)
            texto = (
                f"❌ **1X2:** Error — Predicho: **{pred_winner}** | Real: **{outcome.actual_winner}** "
                f"({outcome.home_score}-{outcome.away_score})\n"
                f"   → Magnitud: {error_magnitud:.3f} | Peso: {learning_weight:.0%} | "
                f"Ajuste: {ajuste:.3f}"
            )

        return {
            "predicho": pred_winner, "real": outcome.actual_winner,
            "acierto": acierto, "error_magnitud": error_magnitud,
            "ajuste": ajuste, "texto": texto
        }

    def _analyze_range_market_v2(self, nombre: str, pred_range_str: str,
                                  actual: int, match_id: str,
                                  home_team: str, away_team: str,
                                  competition: str, learning_weight: float,
                                  lineup_freshness: str) -> dict:
        """
        VERSIÓN CORREGIDA: Lógica de rangos home/away separada luego sumada.
        """
        nums = [int(n) for n in re.findall(r'\d+', pred_range_str or "")]
        
        # Parseo correcto: "🏠 8-12 | ✈️ 4-6" → home=[8,12], away=[4,6]
        home_range, away_range = None, None
        
        if len(nums) >= 4:
            # Formato completo: home_min, home_max, away_min, away_max
            home_range = (nums[0], nums[1])
            away_range = (nums[2], nums[3])
        elif len(nums) == 2:
            # Formato simplificado: total_min, total_max
            home_range = (0, nums[1])  # Distribución desconocida
            away_range = (0, nums[1])
        elif len(nums) == 1:
            home_range = (0, nums[0])
            away_range = (0, nums[0])
        else:
            return {
                "acierto": False, "error_magnitud": 0, 
                "texto": f"⚪ **{nombre}:** Sin datos válidos",
                "record": {"match_id": match_id, "mercado": nombre, 
                           "predicho": "N/A", "real": str(actual),
                           "error_magnitud": 0, "acierto": False,
                           "ajuste_aplicado": 0, "home_team": home_team,
                           "away_team": away_team, "competition": competition,
                           "lineup_freshness": lineup_freshness}
            }

        # Calcular rango total CORRECTAMENTE
        min_total = home_range[0] + away_range[0]
        max_total = home_range[1] + away_range[1]
        
        # Rango extendido por incertidumbre (±1 por cada equipo no confirmado)
        if lineup_freshness in ['predicted', 'fallback', 'stale']:
            extension = 2 if lineup_freshness == 'stale' else 1
            min_total = max(0, min_total - extension)
            max_total = max_total + extension

        acierto = min_total <= actual <= max_total
        mid_pred = (min_total + max_total) / 2
        error_magnitud = round(abs(actual - mid_pred), 1)

        # Dirección del error (para ajuste)
        if actual < min_total:
            direccion = f"SOBREESTIMADO por {min_total - actual}"
            error_pct = (min_total - actual) / max(min_total, 1)
        elif actual > max_total:
            direccion = f"SUBESTIMADO por {actual - max_total}"
            error_pct = (actual - max_total) / max(max_total, 1)
        else:
            direccion = "dentro del rango"
            error_pct = 0

        if acierto:
            texto = f"✅ **{nombre}:** Acierto — Pred: {min_total}-{max_total} | Real: {actual}"
        else:
            texto = (
                f"❌ **{nombre}:** Error — Pred: {min_total}-{max_total} | Real: {actual} "
                f"({direccion}) | Error medio: {error_magnitud}"
            )

        return {
            "acierto": acierto, "error_magnitud": error_magnitud,
            "predicho": f"{min_total}-{max_total}", "real": str(actual),
            "texto": texto, "mid_pred": mid_pred, "actual": actual,
            "error_pct": error_pct,  # Para ajustes proporcionales
            "record": {
                "match_id": match_id, "mercado": nombre,
                "predicho": f"{min_total}-{max_total}", "real": str(actual),
                "error_magnitud": error_magnitud, "acierto": acierto,
                "ajuste_aplicado": 0, "home_team": home_team,
                "away_team": away_team, "competition": competition,
                "lineup_freshness": lineup_freshness,
                "error_pct": error_pct
            }
        }

    def _apply_team_adjustments_v2(self, r1x2: dict, home_team: str, 
                                    away_team: str, learning_weight: float):
        """Ajustes ponderados por calidad de datos."""
        if r1x2["acierto"]:
            # Refuerzo proporcional a la calidad de datos
            delta = 0.005 * learning_weight
            self.db.update_team_factor(home_team, "sesgo_local", delta)
            self.db.update_team_factor(away_team, "sesgo_visitante", delta)
            return

        delta = min(self.MAX_DELTA, r1x2["ajuste"])
        real = r1x2["real"]

        # Validar que el factor existe antes de actualizar
        self._ensure_factor_exists(home_team, "sesgo_local")
        self._ensure_factor_exists(home_team, "sesgo_empate")
        self._ensure_factor_exists(away_team, "sesgo_visitante")
        self._ensure_factor_exists(away_team, "sesgo_empate")

        if real == "LOCAL":
            self.db.update_team_factor(home_team, "sesgo_local", +delta)
            self.db.update_team_factor(away_team, "sesgo_visitante", -delta * 0.5)
        elif real == "VISITANTE":
            self.db.update_team_factor(away_team, "sesgo_visitante", +delta)
            self.db.update_team_factor(home_team, "sesgo_local", -delta * 0.5)
        elif real == "EMPATE":
            self.db.update_team_factor(home_team, "sesgo_empate", +delta * 0.5)
            self.db.update_team_factor(away_team, "sesgo_empate", +delta * 0.5)

    def _ensure_factor_exists(self, team: str, factor: str):
        """NUEVO: Garantiza que el factor de equipo existe en BD."""
        try:
            current = self.db.get_team_factor(team)
            if factor not in current:
                self.db.init_team_factor(team, factor, 0.0)
        except Exception as e:
            # Fallback: asumir que la BD maneja la creación automática
            pass

    def _detect_and_fix_systematic_bias_v2(self, home_team: str, away_team: str) -> str:
        """Versión con decay temporal de errores."""
        mensajes = []
        
        for equipo in [home_team, away_team]:
            factor = self.db.get_team_factor(equipo)
            sesgo_l = float(factor.get("sesgo_local", 0))
            sesgo_v = float(factor.get("sesgo_visitante", 0))
            partidos = int(factor.get("total_partidos", 0))
            last_update = factor.get("last_update")
            
            # Decay temporal: errores viejos pierden peso
            if last_update:
                days_since = (datetime.now() - datetime.fromisoformat(last_update)).days
                decay = math.exp(-days_since / self.DECAY_DAYS)
                sesgo_l *= decay
                sesgo_v *= decay

            if partidos < 2:
                continue

            # Umbral adaptativo: más partidos = umbral más estricto
            threshold = max(0.05, 0.08 - (partidos * 0.002))

            if abs(sesgo_l) > threshold:
                dir_txt = "sobreestimado" if sesgo_l < 0 else "subestimado"
                mensajes.append(
                    f"⚠️ **{equipo} (Local):** {dir_txt} sistemáticamente "
                    f"(sesgo: {sesgo_l:+.3f}, umbral: {threshold:.3f}, "
                    f"partidos: {partidos}). Auto-corrección aplicada."
                )
                # Resetear sesgo después de detectar (para evitar acumulación infinita)
                self.db.update_team_factor(equipo, "sesgo_local", -sesgo_l * 0.5)

            if abs(sesgo_v) > threshold:
                dir_txt = "sobreestimado" if sesgo_v < 0 else "subestimado"
                mensajes.append(
                    f"⚠️ **{equipo} (Visitante):** {dir_txt} sistemáticamente "
                    f"(sesgo: {sesgo_v:+.3f}, umbral: {threshold:.3f}, "
                    f"partidos: {partidos}). Auto-corrección aplicada."
                )
                self.db.update_team_factor(equipo, "sesgo_visitante", -sesgo_v * 0.5)

        return "\n".join(mensajes) if mensajes else ""

    def generate_comparison_report(self, prediction: PredictionResult,
                                   outcome: MatchOutcome) -> list:
        """Mantiene compatibilidad pero usa lógica corregida."""
        comparison = []

        pred_winner = "EMPATE"
        if prediction.win_prob_home > 0.45:   pred_winner = "LOCAL"
        elif prediction.win_prob_away > 0.45: pred_winner = "VISITANTE"
        acierto_1x2 = pred_winner == outcome.actual_winner
        comparison.append({
            "Mercado": "Ganador (1X2)",
            "Predicción": pred_winner,
            "Real": f"{outcome.actual_winner} ({outcome.home_score}-{outcome.away_score})",
            "Estado": "🟢 HIT" if acierto_1x2 else "🔴 MISS"
        })

        def add_market(nombre, pred_str, actual):
            nums = [int(n) for n in re.findall(r'\d+', pred_str or "")]
            
            # Lógica corregida igual que _analyze_range_market_v2
            if len(nums) >= 4:
                min_t = nums[0] + nums[2]  # home_min + away_min
                max_t = nums[1] + nums[3]  # home_max + away_max
            elif len(nums) >= 2:
                min_t, max_t = nums[0], nums[1]
            elif len(nums) == 1:
                min_t = max_t = nums[0]
            else:
                comparison.append({"Mercado": nombre, "Predicción": "N/A", 
                                "Real": str(actual), "Estado": "⚪ N/A"})
                return
            
            hit = min_t <= actual <= max_t
            desviacion = actual - (min_t + max_t) // 2
            comparison.append({
                "Mercado": nombre,
                "Predicción": f"{min_t}-{max_t}",
                "Real": str(actual),
                "Estado": "🟢 HIT" if hit else f"🔴 MISS ({desviacion:+d} del centro)"
            })

        add_market("Córners", prediction.predicted_corners, 
                  outcome.home_corners + outcome.away_corners)
        add_market("Tarjetas", prediction.predicted_cards, 
                  outcome.home_cards + outcome.away_cards)
        add_market("Remates", prediction.predicted_shots, 
                  outcome.home_shots + outcome.away_shots)
        
        return comparison

    def get_learning_dashboard(self) -> dict:
        """Dashboard mejorado con métricas de calidad."""
        stats = self.db.get_total_stats()
        team_factors = self.db.get_all_team_factors()

        # Calcular tendencia (últimos 10 partidos vs histórico)
        recent_stats = self.db.get_stats_last_n(10) if hasattr(self.db, 'get_stats_last_n') else stats
        
        problematicos = [
            t for t in team_factors
            if abs(float(t.get("sesgo_local", 0))) > 0.03
            or abs(float(t.get("sesgo_visitante", 0))) > 0.03
        ]

        return {
            "stats": stats,
            "recent_stats": recent_stats,
            "trend": "📈 Mejorando" if recent_stats.get("precision_1x2", 0) > stats.get("precision_1x2", 0) else "📉 Estable/Declive",
            "team_factors": team_factors[:15],
            "equipos_problematicos": problematicos[:5],
            "modo_bd": getattr(self.db, 'modo', 'unknown')
        }