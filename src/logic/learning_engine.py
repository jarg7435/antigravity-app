"""
LearningEngine — Motor de Aprendizaje Profundo LAGEMA JARG74
=============================================================
Analiza errores por mercado, detecta patrones sistemáticos
y ajusta los factores del predictor automáticamente.

Mercados analizados:
  - 1X2 (ganador del partido)
  - Córners (rango total)
  - Tarjetas (rango total)
  - Remates (rango total)
  - Remates a puerta

Aprendizajes:
  - Error por magnitud (no solo hit/miss)
  - Sesgo sistemático por equipo y situación
  - Patrón de error por tipo de partido
"""

import re
from typing import List, Tuple, Optional
from src.models.base import MatchOutcome, PredictionResult
from src.logic.bpa_engine import BPAEngine
from src.data.db_manager import DataManager


class LearningEngine:

    # Máximo ajuste por partido para evitar sobre-correcciones
    MAX_DELTA = 0.05
    # Umbral para considerar un error "sistemático"
    SYSTEMATIC_THRESHOLD = 3  # 3 partidos seguidos errando el mismo mercado

    def __init__(self, bpa_engine: BPAEngine, db_manager: DataManager = None):
        self.bpa = bpa_engine
        self.db = db_manager or DataManager()

    # =========================================================================
    # PROCESO PRINCIPAL
    # =========================================================================

    def process_result(self, prediction: PredictionResult, outcome: MatchOutcome,
                       home_team: str, away_team: str, competition: str = "") -> str:
        """
        Análisis completo del error de predicción.
        Retorna informe textual para mostrar en la UI.
        """
        report = [f"## 🔬 Análisis de Aprendizaje: {home_team} vs {away_team}"]

        # 1. Guardar resultado real en BD
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
        })

        # 2. Analizar cada mercado
        learning_records = []
        market_results = {}

        # --- MERCADO 1X2 ---
        r1x2 = self._analyze_1x2(prediction, outcome, home_team, away_team)
        market_results["1X2"] = r1x2
        learning_records.append({
            "match_id": outcome.match_id, "mercado": "1X2",
            "predicho": r1x2["predicho"], "real": outcome.actual_winner,
            "error_magnitud": r1x2["error_magnitud"], "acierto": r1x2["acierto"],
            "ajuste_aplicado": r1x2["ajuste"],
            "home_team": home_team, "away_team": away_team, "competition": competition
        })
        report.append(r1x2["texto"])

        # --- MERCADO CÓRNERS ---
        total_corners = outcome.home_corners + outcome.away_corners
        rc = self._analyze_range_market("Córners", prediction.predicted_corners,
                                        total_corners, outcome.match_id,
                                        home_team, away_team, competition)
        market_results["Córners"] = rc
        learning_records.append(rc["record"])
        report.append(rc["texto"])

        # --- MERCADO TARJETAS ---
        total_cards = outcome.home_cards + outcome.away_cards
        rk = self._analyze_range_market("Tarjetas", prediction.predicted_cards,
                                        total_cards, outcome.match_id,
                                        home_team, away_team, competition)
        market_results["Tarjetas"] = rk
        learning_records.append(rk["record"])
        report.append(rk["texto"])

        # --- MERCADO REMATES ---
        total_shots = outcome.home_shots + outcome.away_shots
        rs = self._analyze_range_market("Remates", prediction.predicted_shots,
                                        total_shots, outcome.match_id,
                                        home_team, away_team, competition)
        market_results["Remates"] = rs
        learning_records.append(rs["record"])
        report.append(rs["texto"])

        # 3. Guardar todos los registros de aprendizaje
        self.db.save_aprendizaje(learning_records)

        # 4. Ajustar factores de equipo
        self._apply_team_adjustments(r1x2, home_team, away_team)

        # 5. Ajustar sesgos de mercado si hay patrón sistemático
        bias_report = self._detect_and_fix_systematic_bias(home_team, away_team)
        if bias_report:
            report.append(f"\n### 🧠 Patrón Detectado y Corregido\n{bias_report}")

        # 6. Resumen final
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

    # =========================================================================
    # ANÁLISIS POR MERCADO
    # =========================================================================

    def _analyze_1x2(self, prediction, outcome, home_team, away_team) -> dict:
        """Analiza el mercado ganador y calcula la magnitud del error."""
        pred_winner = "EMPATE"
        if prediction.win_prob_home > 0.45:   pred_winner = "LOCAL"
        elif prediction.win_prob_away > 0.45: pred_winner = "VISITANTE"

        acierto = (pred_winner == outcome.actual_winner)

        # Magnitud del error: diferencia de probabilidades entre predicho y real
        if outcome.actual_winner == "LOCAL":
            real_prob = prediction.win_prob_home
        elif outcome.actual_winner == "VISITANTE":
            real_prob = prediction.win_prob_away
        else:
            real_prob = 1.0 - prediction.win_prob_home - prediction.win_prob_away

        # Error = qué tan lejos estaba la prob del ganador real de ser dominante (>0.45)
        error_magnitud = round(max(0, 0.45 - real_prob) if not acierto else 0, 3)

        # Calcular ajuste
        ajuste = 0.0
        texto = ""
        if acierto:
            texto = f"✅ **1X2:** Acierto — {pred_winner} ({outcome.home_score}-{outcome.away_score})"
        else:
            ajuste = min(self.MAX_DELTA, error_magnitud * 0.5)
            texto = (
                f"❌ **1X2:** Error — Predicho: **{pred_winner}** | Real: **{outcome.actual_winner}** "
                f"({outcome.home_score}-{outcome.away_score})\n"
                f"   → Magnitud del error: {error_magnitud:.3f} | Ajuste aplicado: {ajuste:.3f}"
            )

        return {
            "predicho": pred_winner, "real": outcome.actual_winner,
            "acierto": acierto, "error_magnitud": error_magnitud,
            "ajuste": ajuste, "texto": texto
        }

    def _analyze_range_market(self, nombre: str, pred_range_str: str,
                               actual: int, match_id: str,
                               home_team: str, away_team: str,
                               competition: str) -> dict:
        """Analiza un mercado de rango (córners, tarjetas, remates)."""
        nums = [int(n) for n in re.findall(r'\d+', pred_range_str or "")]

        if len(nums) >= 4:
            # Formato "Local X-Y | Visitante A-B"
            min_t = nums[0] + nums[2]
            max_t = nums[1] + nums[3]
        elif len(nums) == 2:
            min_t, max_t = nums[0], nums[1]
        elif len(nums) == 1:
            min_t = max_t = nums[0]
        else:
            return {
                "acierto": False, "error_magnitud": 0, "texto": f"⚪ **{nombre}:** Sin datos",
                "record": {"match_id": match_id, "mercado": nombre, "predicho": "N/A",
                           "real": str(actual), "error_magnitud": 0, "acierto": False,
                           "ajuste_aplicado": 0, "home_team": home_team,
                           "away_team": away_team, "competition": competition}
            }

        acierto = min_t <= actual <= max_t
        mid_pred = (min_t + max_t) / 2
        error_magnitud = round(abs(actual - mid_pred), 1)

        # Dirección del error
        if actual < min_t:
            direccion = f"SOBREESTIMADO por {min_t - actual}"
        elif actual > max_t:
            direccion = f"SUBESTIMADO por {actual - max_t}"
        else:
            direccion = "dentro del rango"

        if acierto:
            texto = f"✅ **{nombre}:** Acierto — Predicho: {min_t}-{max_t} | Real: {actual}"
        else:
            texto = (
                f"❌ **{nombre}:** Error — Predicho: {min_t}-{max_t} | Real: {actual} "
                f"({direccion}) | Error medio: {error_magnitud}"
            )

        return {
            "acierto": acierto, "error_magnitud": error_magnitud,
            "predicho": f"{min_t}-{max_t}", "real": str(actual),
            "texto": texto, "mid_pred": mid_pred, "actual": actual,
            "record": {
                "match_id": match_id, "mercado": nombre,
                "predicho": f"{min_t}-{max_t}", "real": str(actual),
                "error_magnitud": error_magnitud, "acierto": acierto,
                "ajuste_aplicado": 0, "home_team": home_team,
                "away_team": away_team, "competition": competition
            }
        }

    # =========================================================================
    # AJUSTES DE FACTORES
    # =========================================================================

    def _apply_team_adjustments(self, r1x2: dict, home_team: str, away_team: str):
        """Ajusta los factores de equipo según el error del mercado 1X2."""
        if r1x2["acierto"]:
            # Refuerzo positivo suave
            self.db.update_team_factor(home_team, "sesgo_local", 0.005)
            self.db.update_team_factor(away_team, "sesgo_visitante", 0.005)
            return

        delta = min(self.MAX_DELTA, r1x2["ajuste"])
        real = r1x2["real"]

        if real == "LOCAL":
            # El local ganó pero no lo predijimos → subestimamos al local
            self.db.update_team_factor(home_team, "sesgo_local", +delta)
            self.db.update_team_factor(away_team, "sesgo_visitante", -delta * 0.5)

        elif real == "VISITANTE":
            # El visitante ganó pero no lo predijimos → subestimamos al visitante
            self.db.update_team_factor(away_team, "sesgo_visitante", +delta)
            self.db.update_team_factor(home_team, "sesgo_local", -delta * 0.5)

        elif real == "EMPATE":
            # Fue empate pero predijimos ganador → ambos sobreestimados
            self.db.update_team_factor(home_team, "sesgo_empate", +delta * 0.5)
            self.db.update_team_factor(away_team, "sesgo_empate", +delta * 0.5)

    def _detect_and_fix_systematic_bias(self, home_team: str, away_team: str) -> str:
        """
        Detecta si algún equipo tiene un sesgo sistemático acumulado
        que supere el umbral y avisa sobre el patrón detectado.
        """
        mensajes = []
        for equipo in [home_team, away_team]:
            factor = self.db.get_team_factor(equipo)
            sesgo_l = float(factor.get("sesgo_local", 0))
            sesgo_v = float(factor.get("sesgo_visitante", 0))
            partidos = int(factor.get("total_partidos", 0))

            if partidos < 2:
                continue  # Necesitamos al menos 2 partidos

            if abs(sesgo_l) > 0.08:
                dir_txt = "sobreestimado" if sesgo_l < 0 else "subestimado"
                mensajes.append(
                    f"⚠️ **{equipo} (Local):** {dir_txt} sistemáticamente "
                    f"(sesgo acumulado: {sesgo_l:+.3f} en {partidos} partidos). "
                    f"El sistema ha auto-corregido este factor."
                )

            if abs(sesgo_v) > 0.08:
                dir_txt = "sobreestimado" if sesgo_v < 0 else "subestimado"
                mensajes.append(
                    f"⚠️ **{equipo} (Visitante):** {dir_txt} sistemáticamente "
                    f"(sesgo acumulado: {sesgo_v:+.3f} en {partidos} partidos). "
                    f"El sistema ha auto-corregido este factor."
                )

        return "\n".join(mensajes) if mensajes else ""

    # =========================================================================
    # INFORME COMPARATIVO (para la tabla semáforo de la UI)
    # =========================================================================

    def generate_comparison_report(self, prediction: PredictionResult,
                                   outcome: MatchOutcome) -> list:
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
            if len(nums) >= 4: min_t, max_t = nums[0]+nums[2], nums[1]+nums[3]
            elif len(nums) == 2: min_t, max_t = nums[0], nums[1]
            elif len(nums) == 1: min_t = max_t = nums[0]
            else:
                comparison.append({"Mercado": nombre, "Predicción": "N/A", "Real": str(actual), "Estado": "⚪ N/A"})
                return
            hit = min_t <= actual <= max_t
            comparison.append({
                "Mercado": nombre,
                "Predicción": f"{min_t}-{max_t}",
                "Real": str(actual),
                "Estado": "🟢 HIT" if hit else f"🔴 MISS ({'+' if actual > max_t else ''}{actual - (min_t+max_t)//2:+d} del centro)"
            })

        add_market("Córners", prediction.predicted_corners, outcome.home_corners + outcome.away_corners)
        add_market("Tarjetas", prediction.predicted_cards, outcome.home_cards + outcome.away_cards)
        add_market("Remates", prediction.predicted_shots, outcome.home_shots + outcome.away_shots)
        return comparison

    # =========================================================================
    # DASHBOARD DE APRENDIZAJE (para la UI)
    # =========================================================================

    def get_learning_dashboard(self) -> dict:
        """
        Datos para el Dashboard Histórico de Aprendizaje.
        """
        stats = self.db.get_total_stats()
        team_factors = self.db.get_all_team_factors()

        # Equipos más difíciles de predecir (mayor sesgo acumulado)
        problematicos = [
            t for t in team_factors
            if abs(float(t.get("sesgo_local", 0))) > 0.03
            or abs(float(t.get("sesgo_visitante", 0))) > 0.03
        ]

        return {
            "stats": stats,
            "team_factors": team_factors[:15],  # Top 15 equipos con más partidos
            "equipos_problematicos": problematicos[:5],
            "modo_bd": self.db.modo
        }

