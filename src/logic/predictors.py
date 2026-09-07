"""
predictors.py — LAGEMA JARG74 Ecosistema 4.0
=============================================
Motor híbrido de predicción con pesos dinámicos basados en Freshness Score.
Integra: BPA + Poisson + ML con convergencia segura y manejo de errores.

Prioridad: P1-Crítico. Corrige división por cero y mezcla de modelos frágil.
"""

from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass
from datetime import datetime
import logging

import pandas as pd
from src.models.base import Match, PredictionResult
from src.logic.bpa_engine import BPAEngine
from src.logic.external_analyst import ExternalAnalyst
from src.logic.poisson_engine import PoissonEngine
from src.logic.ml_engine import MLEngine
from src.logic.value_engine import ValueEngine
from src.logic import ausencias as _ausencias
from src.logic.calibracion import CalibradorGoles

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s | %(levelname)-8s | %(message)s',
    datefmt='%H:%M:%S'
)
logger = logging.getLogger(__name__)


@dataclass
class ModelWeights:
    """Pesos dinámicos para fusión de modelos."""
    poisson: float = 0.50
    bpa: float = 0.30
    ml: float = 0.20
    
    def validate(self) -> bool:
        """Valida que los pesos sumen aproximadamente 1.0."""
        total = self.poisson + self.bpa + self.ml
        return 0.99 <= total <= 1.01
    
    def normalize(self) -> 'ModelWeights':
        """Normaliza pesos a 1.0 si hay desviación."""
        total = self.poisson + self.bpa + self.ml
        if total == 0:
            return ModelWeights(poisson=0.5, bpa=0.3, ml=0.2)
        return ModelWeights(
            poisson=self.poisson / total,
            bpa=self.bpa / total,
            ml=self.ml / total
        )


class Predictor:
    """
    Motor híbrido que combina BPA, Regresión Poisson y Machine Learning.
    Versión 4.0: Pesos dinámicos por Freshness Score y protección contra errores.
    """
    
    # Pesos base por defecto
    DEFAULT_WEIGHTS = ModelWeights(poisson=0.50, bpa=0.30, ml=0.20)
    
    # Penalizaciones por freshness (reducen peso del modelo afectado)
    FRESHNESS_PENALTIES = {
        'live': {'bpa': 1.0, 'poisson': 1.0, 'ml': 1.0},      # Sin penalización
        'confirmed': {'bpa': 0.9, 'poisson': 1.0, 'ml': 0.9},  # BPA y ML ligeramente penalizados
        'predicted': {'bpa': 0.6, 'poisson': 1.1, 'ml': 0.7},  # BPA penalizado, Poisson gana
        'fallback': {'bpa': 0.3, 'poisson': 1.2, 'ml': 0.5},   # BPA casi ignorado
        'stale': {'bpa': 0.1, 'poisson': 1.3, 'ml': 0.3},      # Solo Poisson es fiable
    }
    
    def __init__(self, bpa_engine: BPAEngine):
        self.bpa_engine = bpa_engine
        self.external_analyst = ExternalAnalyst()
        self.poisson = PoissonEngine()
        self.ml = MLEngine()
        self.value_engine = ValueEngine()
        # La calibracion se lee de la BD una vez y se cachea: es un parametro
        # global que solo cambia cuando se procesa un resultado nuevo.
        try:
            self.calibrador = CalibradorGoles()
        except Exception as e:
            logger.error(f"No se pudo inicializar el calibrador: {e}")
            self.calibrador = None
        logger.info("Predictor v4.0 inicializado con pesos dinámicos")

    def _calculate_dynamic_weights(self, freshness: str, lineup_quality: Dict) -> ModelWeights:
        """
        Calcula pesos dinámicos basados en calidad de datos de alineación.
        
        Args:
            freshness: 'live', 'confirmed', 'predicted', 'fallback', 'stale'
            lineup_quality: Metadata adicional de calidad (integridad, etc)
        """
        base = self.DEFAULT_WEIGHTS
        penalties = self.FRESHNESS_PENALTIES.get(freshness, self.FRESHNESS_PENALTIES['fallback'])
        
        # Aplicar penalizaciones
        new_weights = ModelWeights(
            poisson=base.poisson * penalties['poisson'],
            bpa=base.bpa * penalties['bpa'],
            ml=base.ml * penalties['ml']
        )
        
        # Penalización adicional si hay problemas de integridad
        if lineup_quality.get('integrity_issues'):
            new_weights.bpa *= 0.5  # Reducir BPA si hay problemas de integridad
            new_weights.poisson *= 1.1  # Transferir a Poisson
        
        # Penalizar ML si no está entrenado
        if not self.ml.is_trained:
            new_weights.ml *= 0.3
            new_weights.poisson *= 1.15
        
        normalized = new_weights.normalize()
        logger.info(f"Pesos dinámicos [{freshness}]: Poisson={normalized.poisson:.2f}, "
                   f"BPA={normalized.bpa:.2f}, ML={normalized.ml:.2f}")
        return normalized

    def _safe_bpa_calculation(self, match: Match, press_modifiers: Dict) -> Tuple[float, float, Dict]:
        """
        Calcula BPA con protección contra valores inválidos.
        
        Returns:
            (bpa_home, bpa_away, metadata)
        """
        try:
            bpa_res = self.bpa_engine.calculate_match_bpa(match, press_modifiers=press_modifiers)
            
            # Validar estructura de retorno
            if not isinstance(bpa_res, dict):
                logger.error(f"BPA retornó tipo inválido: {type(bpa_res)}")
                return 0.5, 0.5, {'error': 'invalid_return_type'}
            
            bpa_h = float(bpa_res.get('home_bpa', 0.5))
            bpa_a = float(bpa_res.get('away_bpa', 0.5))
            
            # Validar rangos
            if not (0 <= bpa_h <= 1 and 0 <= bpa_a <= 1):
                logger.warning(f"BPA fuera de rango: home={bpa_h}, away={bpa_a}. Clamping.")
                bpa_h = max(0, min(1, bpa_h))
                bpa_a = max(0, min(1, bpa_a))
            
            # Evitar ambos en cero
            if bpa_h == 0 and bpa_a == 0:
                logger.warning("BPA retornó 0-0, usando valores neutros")
                bpa_h, bpa_a = 0.5, 0.5
            
            return bpa_h, bpa_a, {'valid': True}
            
        except Exception as e:
            logger.error(f"Error en cálculo BPA: {e}")
            return 0.5, 0.5, {'error': str(e)}

    def _safe_poisson_calculation(self, match: Match, bpa_h: float, bpa_a: float,
                                  inf_local=None, inf_visitante=None,
                                  lineup_freshness: str = 'confirmed') -> Tuple:
        """
        Calcula Poisson con manejo de errores y lambdas seguros.

        Aqui entran las dos correcciones nuevas. Antes esta funcion llamaba a
        estimate_lambdas sin pasarle ni la frescura de la alineacion ni las
        bajas, de modo que sus parametros `missing_key_players_*` y
        `lineup_freshness` se quedaban en sus valores por defecto y no hacian
        nada: el once confirmado no movia un decimal del pronostico.
        """
        neutro = _ausencias.InformeAusencias(equipo="")
        inf_local = inf_local or neutro
        inf_visitante = inf_visitante or neutro

        factor_l, factor_v = 1.0, 1.0
        if self.calibrador is not None:
            try:
                factor_l, factor_v = self.calibrador.factores()
            except Exception as e:
                logger.error(f"No se pudieron leer los factores de calibración: {e}")

        try:
            h_lambda, a_lambda = self.poisson.estimate_lambdas(
                match.home_team, 
                match.away_team, 
                home_bpa=bpa_h, 
                away_bpa=bpa_a,
                league_name=match.competition,  # Nuevo: pasar nombre de liga
                lineup_freshness=lineup_freshness,
                coef_ataque_home=inf_local.coef_ataque,
                coef_ataque_away=inf_visitante.coef_ataque,
                coef_encaje_home=inf_local.coef_encaje,
                coef_encaje_away=inf_visitante.coef_encaje,
                factor_calibracion_home=factor_l,
                factor_calibracion_away=factor_v,
            )
            
            # Validar lambdas
            if h_lambda <= 0 or a_lambda <= 0:
                logger.warning(f"Lambdas inválidos: {h_lambda}, {a_lambda}. Usando defaults.")
                h_lambda = max(0.5, h_lambda)
                a_lambda = max(0.5, a_lambda)
            
            p_matrix = self.poisson.predict_score_matrix(h_lambda, a_lambda)
            p_home, p_draw, p_away = self.poisson.calculate_match_probabilities(h_lambda, a_lambda)
            
            # Validar probabilidades Poisson
            total_poisson = p_home + p_draw + p_away
            if abs(total_poisson - 1.0) > 0.1 or total_poisson == 0:
                logger.warning(f"Probabilidades Poisson inválidas: {total_poisson}. Normalizando.")
                if total_poisson > 0:
                    p_home /= total_poisson
                    p_draw /= total_poisson
                    p_away /= total_poisson
                else:
                    p_home, p_draw, p_away = 0.33, 0.34, 0.33
            
            return (h_lambda, a_lambda, p_matrix, p_home, p_draw, p_away), None
            
        except Exception as e:
            logger.error(f"Error en cálculo Poisson: {e}")
            return None, str(e)

    def _safe_ml_calculation(self, match: Match) -> Tuple[Dict, Optional[str]]:
        """
        Obtiene probabilidades del ML con validación.
        """
        try:
            ml_probs = self.ml.predict_probabilities(None, league=match.competition)
            
            # Validar estructura
            required_keys = ['LOCAL', 'EMPATE', 'VISITANTE']
            if not all(k in ml_probs for k in required_keys):
                logger.warning(f"ML retornó keys incompletas: {ml_probs.keys()}")
                # Completar con defaults si faltan
                for k in required_keys:
                    ml_probs.setdefault(k, 0.33)
            
            # Validar que no sean todos iguales (indica fallback por defecto)
            values = [ml_probs['LOCAL'], ml_probs['EMPATE'], ml_probs['VISITANTE']]
            if len(set(values)) == 1:
                logger.info("ML en modo default (sin entrenar), reduciendo peso")
            
            return ml_probs, None
            
        except Exception as e:
            logger.error(f"Error en cálculo ML: {e}")
            return {'LOCAL': 0.33, 'EMPATE': 0.34, 'VISITANTE': 0.33}, str(e)

    def _blend_probabilities(
        self, 
        p_home: float, p_draw: float, p_away: float,
        bpa_h: float, bpa_a: float,
        ml_probs: Dict,
        weights: ModelWeights
    ) -> Tuple[float, float, float]:
        """
        Mezcla probabilidades de los tres modelos con convergencia segura.
        
        Fórmula: 
        - Poisson aporta probabilidades base (1X2)
        - BPA aporta ventaja relativa convertida a probabilidad
        - ML aporta clasificación supervisada
        """
        # Convertir BPA a probabilidad adicional (clamped ±0.20 como en versión original)
        bpa_diff = max(-0.20, min(0.20, (bpa_h - bpa_a) * 0.5))
        
        # Probabilidades base desde BPA (centro en 0.35-0.30-0.35)
        bpa_prob_home = max(0.05, min(0.95, 0.35 + bpa_diff))
        bpa_prob_draw = max(0.05, min(0.90, 0.30 - abs(bpa_diff) * 0.3))
        bpa_prob_away = max(0.05, min(0.95, 0.35 - bpa_diff))
        
        # Normalizar BPA a 1.0
        bpa_total = bpa_prob_home + bpa_prob_draw + bpa_prob_away
        bpa_prob_home /= bpa_total
        bpa_prob_draw /= bpa_total
        bpa_prob_away /= bpa_total
        
        # ML probabilidades
        ml_home = ml_probs.get('LOCAL', 0.33)
        ml_draw = ml_probs.get('EMPATE', 0.34)
        ml_away = ml_probs.get('VISITANTE', 0.33)
        
        # Mezcla ponderada
        final_home = (p_home * weights.poisson) + (bpa_prob_home * weights.bpa) + (ml_home * weights.ml)
        final_draw = (p_draw * weights.poisson) + (bpa_prob_draw * weights.bpa) + (ml_draw * weights.ml)
        final_away = (p_away * weights.poisson) + (bpa_prob_away * weights.bpa) + (ml_away * weights.ml)
        
        # Normalización final
        total = final_home + final_draw + final_away
        if total == 0:
            logger.error("Total de probabilidades es 0 después de mezcla. Usando equiprobable.")
            return 0.33, 0.34, 0.33
        
        return final_home / total, final_draw / total, final_away / total

    def predict_match(self, match: Match, lineup_freshness: str = 'confirmed', 
                     lineup_quality: Optional[Dict] = None,
                     once_local: Optional[List[str]] = None,
                     once_visitante: Optional[List[str]] = None) -> PredictionResult:
        """
        Predicción completa con pesos dinámicos y manejo de errores robusto.
        
        Args:
            match: Objeto Match con datos del partido
            lineup_freshness: Calidad de alineación ('live', 'confirmed', 'predicted', 'fallback', 'stale')
            lineup_quality: Metadata adicional de calidad (integridad, etc)
            once_local: nombres del once confirmado del equipo local, si lo hay
            once_visitante: idem del visitante

        Los dos onces son opcionales a proposito: sin ellos la prediccion sale
        como siempre. Cuando llegan, se comparan con los titulares que el modelo
        daba por hechos y las ausencias criticas corrigen el xG y bajan la
        confianza. No pasarlos no penaliza: no saber quien juega no es lo mismo
        que saber que falta alguien.
        """
        if lineup_quality is None:
            lineup_quality = {}

        # 0. Ausencias criticas respecto al once confirmado
        try:
            inf_local, inf_visitante = _ausencias.evaluar_partido(
                match.home_team, match.away_team, once_local, once_visitante)
        except Exception as e:
            logger.error(f"Error evaluando ausencias: {e}")
            inf_local = _ausencias.InformeAusencias(equipo=match.home_team.name,
                                                    comparable=False, motivo=str(e)[:80])
            inf_visitante = _ausencias.InformeAusencias(equipo=match.away_team.name,
                                                        comparable=False, motivo=str(e)[:80])
        
        logger.info(f"Iniciando predicción para {match.home_team.name} vs {match.away_team.name} "
                   f"(freshness: {lineup_freshness})")
        
        # 1. Calcular pesos dinámicos
        weights = self._calculate_dynamic_weights(lineup_freshness, lineup_quality)
        
        # 2. Inteligencia externa (con awareness de freshness)
        try:
            intel = self.external_analyst.get_detailed_intelligence(match, freshness=lineup_freshness)
            analysis_text = intel["report"]
            press_impact = intel["impact"]
        except Exception as e:
            logger.error(f"Error obteniendo inteligencia externa: {e}")
            analysis_text = "Análisis de prensa no disponible"
            press_impact = {"home": 0, "away": 0}
        
        # 3. BPA Analysis (con protección)
        bpa_h, bpa_a, bpa_metadata = self._safe_bpa_calculation(match, press_impact)
        
        # 4. Poisson Statistics (con protección y ausencias aplicadas)
        poisson_result, poisson_error = self._safe_poisson_calculation(
            match, bpa_h, bpa_a, inf_local, inf_visitante, lineup_freshness)
        
        if poisson_error:
            # Fallback: usar solo BPA con distribución equiprobable ajustada
            logger.warning("Usando fallback Poisson (distribución equiprobable ajustada por BPA)")
            h_lambda, a_lambda = 1.3, 1.1
            p_matrix = {}
            p_home, p_draw, p_away = 0.33, 0.34, 0.33
        else:
            h_lambda, a_lambda, p_matrix, p_home, p_draw, p_away = poisson_result
        
        # 5. Machine Learning (con protección)
        ml_probs, ml_error = self._safe_ml_calculation(match)
        
        # 6. Hybrid Blending (mezcla segura)
        final_home, final_draw, final_away = self._blend_probabilities(
            p_home, p_draw, p_away,
            bpa_h, bpa_a,
            ml_probs,
            weights
        )
        
        # 7. Mercados secundarios (usando lambdas e inteligencia)
        try:
            stats = self.external_analyst.calculate_stat_markets(
                match, bpa_h, bpa_a, h_lambda=h_lambda, a_lambda=a_lambda
            )
        except Exception as e:
            logger.error(f"Error calculando mercados secundarios: {e}")
            stats = {
                "total_goals_range": "1-2",
                "corners": ("4-6", "3-5"),
                "cards": ("2-4", "2-3"),
                "shots": ("10-14", "8-12"),
                "shots_on_target": ("3-5", "2-4")
            }
        
        # 8. Score prediction más probable
        score_pred = "0-0"
        if p_matrix:
            try:
                score_pred = max(p_matrix, key=p_matrix.get)
            except Exception:
                score_pred = f"{int(h_lambda)}-{int(a_lambda)}"
        
        # 9. Referee name seguro
        ref_name = "No asignado"
        if match.referee:
            if isinstance(match.referee, dict):
                ref_name = match.referee.get("name", "No asignado")
            else:
                ref_name = getattr(match.referee, "name", "No asignado")
        
        # 10. Calcular confianza real, rebajada por las ausencias criticas.
        # Cuando el once real no es el previsto, bajar la confianza importa mas
        # que afinar el xG: es lo que evita apostar a ciegas sobre un equipo que
        # no es el que se modelo.
        confidence = self._calc_confidence(final_home, final_away, bpa_h, bpa_a, p_home, p_away)
        penalizacion = round(
            inf_local.penalizacion_confianza + inf_visitante.penalizacion_confianza, 4)
        if penalizacion > 0:
            confidence = round(max(0.05, confidence - penalizacion), 2)
            logger.info(f"Confianza rebajada {penalizacion:.2f} por ausencias críticas")
        
        # 11. Construir resultado
        pred = PredictionResult(
            match_id=match.id,
            bpa_home=bpa_h,
            bpa_away=bpa_a,
            win_prob_home=round(final_home, 4),
            draw_prob=round(final_draw, 4),
            win_prob_away=round(final_away, 4),
            poisson_matrix=p_matrix,
            total_goals_expected=round(h_lambda + a_lambda, 2),
            total_goals_range=stats.get("total_goals_range", "1-2"),
            both_teams_to_score_prob=self._calc_btts_prob(h_lambda, a_lambda),
            score_prediction=score_pred,
            predicted_cards=f"🏠 {stats['cards'][0]} | ✈️ {stats['cards'][1]}",
            predicted_corners=f"🏠 {stats['corners'][0]} | ✈️ {stats['corners'][1]}",
            predicted_shots=f"🏠 {stats['shots'][0]} | ✈️ {stats['shots'][1]}",
            predicted_shots_on_target=f"🏠 {stats['shots_on_target'][0]} | ✈️ {stats['shots_on_target'][1]}",
            confidence_score=confidence,
            external_analysis_summary=analysis_text,
            referee_name=ref_name,
            freshness_score=lineup_freshness,  # Nuevo: guardar freshness usado
            model_weights_used={               # Nuevo: trazabilidad
                'poisson': weights.poisson,
                'bpa': weights.bpa,
                'ml': weights.ml
            },
            # Los lambdas por separado: el bucle de calibracion los necesita
            # para saber si el modelo va largo en casa, fuera, o en los dos.
            lambda_home=round(h_lambda, 3),
            lambda_away=round(a_lambda, 3),
            ausencias={
                "local": inf_local.a_dict(),
                "visitante": inf_visitante.a_dict(),
            },
            penalizacion_ausencias=penalizacion,
        )

        # 12. Value Betting Detection
        if match.market_odds:
            try:
                pred.value_opportunities = self.value_engine.find_opportunities(pred, match.market_odds)
            except Exception as e:
                logger.error(f"Error en value betting: {e}")
                pred.value_opportunities = []
        
        logger.info(f"Predicción completada: H={final_home:.2%}, D={final_draw:.2%}, A={final_away:.2%}")
        return pred

    def recalcular_por_once(self, prediccion: PredictionResult, match: Match,
                            once_local: Optional[List[str]] = None,
                            once_visitante: Optional[List[str]] = None
                            ) -> Tuple[PredictionResult, Dict]:
        """
        Rehace SOLO lo que cambia al conocerse el once oficial.

        Existe para que se pueda trabajar con antelacion sin perder rigor: el
        estudio se calcula con horas de margen y, cuando una hora antes aparece
        la alineacion de verdad, se corrige lo que esa alineacion afecta en
        lugar de repetir el analisis entero.

        QUE SE REHACE Y QUE NO, Y POR QUE

        Lo caro del pronostico no son los numeros, es la red. El analisis de
        prensa y lesiones (`get_detailed_intelligence`) sale a buscar noticias y
        partes medicos, y de ahi salen los BPA. Eso no cambia porque se confirme
        el once —las bajas ya estaban contadas— y se conserva tal cual.

        Lo que si cambia es todo lo que cuelga de quien juega:

            ausencias -> lambdas -> Poisson -> mezcla -> confianza -> mercados

        y eso se recalcula entero. Todo local: ni una peticion de red.

        Los lambdas nuevos salen de los viejos por proporcion, no volviendo a
        estimarlos: el lambda guardado ya lleva dentro los coeficientes de
        ausencias que se aplicaron entonces, asi que basta dividir por aquellos
        y multiplicar por los nuevos. Asi la correccion es exacta y no arrastra
        diferencias por recalcular la base.

        Returns:
            (prediccion corregida, resumen de lo que ha cambiado)
        """
        cambios = {"aplicado": False, "motivo": "", "antes": {}, "despues": {}}

        if prediccion is None:
            cambios["motivo"] = "no hay ningún estudio previo que corregir"
            return prediccion, cambios

        lambda_h = float(getattr(prediccion, "lambda_home", 0) or 0)
        lambda_a = float(getattr(prediccion, "lambda_away", 0) or 0)
        if lambda_h <= 0 or lambda_a <= 0:
            # Estudios anteriores a que se guardaran los lambdas por separado.
            cambios["motivo"] = ("el estudio guardado no trae los goles esperados "
                                 "por lado; recalcúlalo entero")
            return prediccion, cambios

        # 1. Ausencias con el once nuevo.
        try:
            inf_local, inf_visit = _ausencias.evaluar_partido(
                match.home_team, match.away_team, once_local, once_visitante)
        except Exception as e:
            logger.error(f"Error evaluando ausencias en el recálculo: {e}")
            cambios["motivo"] = f"no se pudieron evaluar las ausencias: {e}"
            return prediccion, cambios

        if not (inf_local.comparable or inf_visit.comparable):
            cambios["motivo"] = "el once confirmado no es comparable todavía"
            return prediccion, cambios

        # 2. Coeficientes que se aplicaron entonces, para dividirlos.
        previos = getattr(prediccion, "ausencias", None) or {}

        def _coef(bloque, clave):
            try:
                return float((previos.get(bloque) or {}).get(clave, 1.0)) or 1.0
            except (TypeError, ValueError):
                return 1.0

        viejo_h = _coef("local", "coef_ataque") * _coef("visitante", "coef_encaje")
        viejo_a = _coef("visitante", "coef_ataque") * _coef("local", "coef_encaje")
        nuevo_h = inf_local.coef_ataque * inf_visit.coef_encaje
        nuevo_a = inf_visit.coef_ataque * inf_local.coef_encaje

        cambios["antes"] = {"lambda_home": round(lambda_h, 3),
                            "lambda_away": round(lambda_a, 3),
                            "confianza": prediccion.confidence_score,
                            "1x2": (prediccion.win_prob_home, prediccion.draw_prob,
                                    prediccion.win_prob_away)}

        h_lambda = max(0.4, min(4.0, lambda_h * (nuevo_h / viejo_h)))
        a_lambda = max(0.3, min(3.5, lambda_a * (nuevo_a / viejo_a)))

        # 3. Poisson con los lambdas corregidos.
        try:
            p_matrix = self.poisson.predict_score_matrix(h_lambda, a_lambda)
            p_home, p_draw, p_away = self.poisson.calculate_match_probabilities(
                h_lambda, a_lambda)
        except Exception as e:
            logger.error(f"Poisson falló en el recálculo: {e}")
            cambios["motivo"] = f"el cálculo de Poisson falló: {e}"
            return prediccion, cambios

        # 4. Mezcla con los MISMOS pesos y los MISMOS BPA del estudio original:
        # el analisis de prensa que los produjo no ha cambiado.
        ml_probs, _ = self._safe_ml_calculation(match)
        pesos_guardados = getattr(prediccion, "model_weights_used", None) or {}
        pesos = ModelWeights(
            poisson=float(pesos_guardados.get("poisson", self.DEFAULT_WEIGHTS.poisson)),
            bpa=float(pesos_guardados.get("bpa", self.DEFAULT_WEIGHTS.bpa)),
            ml=float(pesos_guardados.get("ml", self.DEFAULT_WEIGHTS.ml)),
        ).normalize()

        final_home, final_draw, final_away = self._blend_probabilities(
            p_home, p_draw, p_away,
            prediccion.bpa_home, prediccion.bpa_away,
            ml_probs, pesos)

        # 5. Confianza, con la penalizacion de las ausencias nuevas.
        penalizacion = round(inf_local.penalizacion_confianza
                             + inf_visit.penalizacion_confianza, 4)
        confianza = self._calc_confidence(final_home, final_away,
                                          prediccion.bpa_home, prediccion.bpa_away,
                                          p_home, p_away)
        if penalizacion > 0:
            confianza = round(max(0.05, confianza - penalizacion), 2)

        # 6. Mercados que dependen de los goles. Son locales.
        try:
            stats = self.external_analyst.calculate_stat_markets(
                match, prediccion.bpa_home, prediccion.bpa_away,
                h_lambda=h_lambda, a_lambda=a_lambda)
        except Exception as e:
            logger.error(f"Mercados secundarios fallaron en el recálculo: {e}")
            stats = {}

        marcador = prediccion.score_prediction
        if p_matrix:
            try:
                marcador = max(p_matrix, key=p_matrix.get)
            except Exception:
                pass

        # 7. Se escribe sobre una copia: si algo falla arriba, el estudio
        # original queda intacto.
        nueva = prediccion.model_copy(deep=True)
        nueva.lambda_home = round(h_lambda, 3)
        nueva.lambda_away = round(a_lambda, 3)
        nueva.total_goals_expected = round(h_lambda + a_lambda, 2)
        nueva.poisson_matrix = p_matrix
        nueva.win_prob_home = round(final_home, 4)
        nueva.draw_prob = round(final_draw, 4)
        nueva.win_prob_away = round(final_away, 4)
        nueva.both_teams_to_score_prob = self._calc_btts_prob(h_lambda, a_lambda)
        nueva.score_prediction = marcador
        nueva.confidence_score = confianza
        nueva.penalizacion_ausencias = penalizacion
        nueva.ausencias = {"local": inf_local.a_dict(),
                           "visitante": inf_visit.a_dict()}
        nueva.freshness_score = "confirmed"
        if stats.get("total_goals_range"):
            nueva.total_goals_range = stats["total_goals_range"]

        cambios["aplicado"] = True
        cambios["despues"] = {"lambda_home": nueva.lambda_home,
                              "lambda_away": nueva.lambda_away,
                              "confianza": nueva.confidence_score,
                              "1x2": (nueva.win_prob_home, nueva.draw_prob,
                                      nueva.win_prob_away)}
        cambios["ausentes"] = ([a.nombre for a in inf_local.ausentes]
                               + [a.nombre for a in inf_visit.ausentes])
        logger.info("Recálculo por once oficial: λ %.2f-%.2f → %.2f-%.2f, "
                    "confianza %.2f → %.2f",
                    lambda_h, lambda_a, h_lambda, a_lambda,
                    cambios["antes"]["confianza"], confianza)
        return nueva, cambios

    def _calc_confidence(self, home_prob: float, away_prob: float, 
                        bpa_h: float = 0.5, bpa_a: float = 0.5,
                        p_home: float = 0.33, p_away: float = 0.33) -> float:
        """
        Calcula confianza real basada en convergencia de modelos (0.0 a 1.0).
        """
        # ¿Coinciden BPA y Poisson en el ganador?
        bpa_agrees = (bpa_h > bpa_a) == (p_home > p_away) and abs(bpa_h - bpa_a) > 0.03
        
        # ¿Hay diferencia clara en probabilidades finales?
        clear_winner = abs(home_prob - away_prob) > 0.08
        
        # ¿El modelo no está demasiado cerca del empate?
        not_a_toss = max(home_prob, away_prob) > 0.38
        
        # ¿Datos de alineación son de calidad?
        quality_data = bpa_h != 0.5 or bpa_a != 0.5  # No son valores default

        score = 0.40  # Base
        if bpa_agrees:   score += 0.25
        if clear_winner: score += 0.20
        if not_a_toss:   score += 0.15
        if quality_data: score += 0.10
        
        return round(min(score, 1.0), 2)
    
    def _calc_btts_prob(self, h_lambda: float, a_lambda: float) -> float:
        """Calcula probabilidad de ambos equipos marcan (BTTS)."""
        try:
            prob_h_zero = self.poisson.calculate_poisson_probability(h_lambda, 0)
            prob_a_zero = self.poisson.calculate_poisson_probability(a_lambda, 0)
            return round(1.0 - (prob_h_zero * prob_a_zero), 4)
        except Exception:
            return 0.5  # Default si falla