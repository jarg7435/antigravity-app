"""
Bucle de aprendizaje post-partido — La Gema JARG74.

Mide el error entre los goles que el modelo estimó y los que se marcaron de
verdad, y corrige el sesgo de forma incremental para las jornadas siguientes.

QUÉ HABÍA Y QUÉ FALTABA
-----------------------
`learning_engine.py` ya cerraba un bucle, pero sobre otra cosa: acierto o fallo
por mercado (1X2, córners, tarjetas, remates) y sesgos POR EQUIPO en
`factores_equipo`. Nadie miraba la magnitud del error de goles del modelo
entero. Las dos tablas que hacían falta estaban ahí —`predictions` con lo que se
esperaba y `resultados` con lo que pasó— pero no se cruzaban nunca.

Esa es la diferencia entre las dos correcciones, y por eso conviven:

    factores_equipo   "el Betis en casa marca más de lo que digo"
    calibracion       "yo estimo largo de goles en general"

La segunda es la que arregla un modelo descalibrado. Un sesgo global de +0.3
goles por partido no se ve mirando aciertos: el 1X2 puede seguir saliendo bien
mientras todos los mercados de goles salen mal.

CÓMO CORRIGE
------------
Para cada lado se compara la media de goles estimados con la real:

    objetivo = media(goles reales) / media(goles estimados)

y el factor vigente se mueve hacia ese objetivo un PASO cada vez, en lugar de
saltar del tirón. Es deliberado: con 12 partidos, saltar al objetivo convierte
una racha en una ley. El paso corto tarda más en llegar y, a cambio, no se va
detrás del ruido.

TRES FRENOS, POR EL MISMO MOTIVO
--------------------------------
Un bucle que se ajusta solo puede irse a cualquier parte si nadie lo sujeta:

1. MUESTRAS_MINIMAS antes de aplicar nada. Con cuatro partidos no se distingue
   un sesgo de una racha.
2. PASO de 0.25: cada calibración recorre un cuarto de la distancia.
3. FACTOR_MIN/MAX: el factor nunca sale de ±15%. Si el modelo se equivoca más
   que eso, el problema no es la calibración y taparlo con un multiplicador
   sería esconder el fallo de verdad.

Uso:

    from src.logic.calibracion import CalibradorGoles
    cal = CalibradorGoles(db_manager)
    informe = cal.calibrar()          # mide, ajusta y guarda
    f_local, f_visit = cal.factores() # lo que aplica el motor Poisson

Autor: Antigravity - La Gema JARG74
"""

import json
import logging
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

# Nombres con los que viajan los parámetros a la tabla `calibracion`.
PARAM_LOCAL = "factor_goles_local"
PARAM_VISITANTE = "factor_goles_visitante"

# Partidos con resultado que hacen falta antes de tocar nada.
MUESTRAS_MINIMAS = 8

# Fracción de la distancia al objetivo que se recorre en cada calibración.
PASO = 0.25

# Hasta dónde puede llegar la corrección. Más allá, el problema no es el sesgo.
FACTOR_MIN, FACTOR_MAX = 0.85, 1.15


@dataclass
class MedicionLado:
    """Error del modelo en un lado del marcador (local o visitante)."""

    lado: str
    muestras: int = 0
    media_estimada: float = 0.0
    media_real: float = 0.0
    error_absoluto_medio: float = 0.0

    @property
    def sesgo(self) -> float:
        """Goles de más (positivo) o de menos (negativo) que estima el modelo."""
        return self.media_estimada - self.media_real

    @property
    def objetivo(self) -> float:
        """Factor que igualaría las dos medias."""
        if self.media_estimada <= 0.01:
            return 1.0
        return self.media_real / self.media_estimada


@dataclass
class InformeCalibracion:
    """Resultado de una pasada de calibración."""

    muestras: int = 0
    aplicada: bool = False
    motivo: str = ""
    local: Optional[MedicionLado] = None
    visitante: Optional[MedicionLado] = None
    factor_local_antes: float = 1.0
    factor_local_despues: float = 1.0
    factor_visitante_antes: float = 1.0
    factor_visitante_despues: float = 1.0
    avisos: List[str] = field(default_factory=list)

    def resumen(self) -> str:
        if not self.aplicada:
            return f"Sin calibrar: {self.motivo}"
        partes = [f"{self.muestras} partidos analizados."]
        for med, antes, despues in (
            (self.local, self.factor_local_antes, self.factor_local_despues),
            (self.visitante, self.factor_visitante_antes, self.factor_visitante_despues),
        ):
            if not med:
                continue
            direccion = "largo" if med.sesgo > 0 else "corto"
            partes.append(
                f"{med.lado}: el modelo va {direccion} {abs(med.sesgo):.2f} goles "
                f"(estima {med.media_estimada:.2f}, real {med.media_real:.2f}); "
                f"factor {antes:.3f} → {despues:.3f}."
            )
        return " ".join(partes)


class CalibradorGoles:
    """
    Mide el error de goles del modelo y ajusta su escala de forma incremental.

    No toca la base de datos hasta que hay muestras suficientes, y guarda junto
    al factor cuántas lo respaldan, para que la interfaz pueda decir si lo que
    aplica está fundado o es todavía provisional.
    """

    def __init__(self, db_manager=None):
        if db_manager is None:
            from src.data.db_manager import DataManager
            db_manager = DataManager()
        self.db = db_manager
        self._cache: Optional[Tuple[float, float]] = None

    # -------------------------------------------------------------------
    # LECTURA
    # -------------------------------------------------------------------

    def factores(self) -> Tuple[float, float]:
        """
        Factores vigentes (local, visitante), listos para el motor Poisson.

        Devuelve (1.0, 1.0) mientras no haya calibración guardada, que es el
        comportamiento de siempre: sin datos, no se corrige nada.
        """
        if self._cache is not None:
            return self._cache

        local = visitante = 1.0
        try:
            guardados = self.db.get_calibracion() or {}
            local = self._acotar(guardados.get(PARAM_LOCAL, {}).get("valor", 1.0))
            visitante = self._acotar(guardados.get(PARAM_VISITANTE, {}).get("valor", 1.0))
        except Exception as e:
            logger.error(f"[Calibración] No se pudieron leer los factores: {e}")

        self._cache = (local, visitante)
        return self._cache

    def refrescar(self):
        """Olvida los factores cacheados; se releerán en la próxima consulta."""
        self._cache = None

    def estado(self) -> Dict:
        """Lo que aplica ahora mismo, para el panel de diagnóstico."""
        local, visitante = self.factores()
        guardados = {}
        try:
            guardados = self.db.get_calibracion() or {}
        except Exception:
            pass
        fila_l = guardados.get(PARAM_LOCAL, {})
        fila_v = guardados.get(PARAM_VISITANTE, {})
        muestras = max(int(fila_l.get("muestras") or 0), int(fila_v.get("muestras") or 0))
        return {
            "factor_local": local,
            "factor_visitante": visitante,
            "muestras": muestras,
            "activa": muestras >= MUESTRAS_MINIMAS and (local != 1.0 or visitante != 1.0),
            "actualizado": fila_l.get("updated_at") or fila_v.get("updated_at"),
            "sesgo_local": fila_l.get("sesgo"),
            "sesgo_visitante": fila_v.get("sesgo"),
            "error_local": fila_l.get("error_medio"),
            "error_visitante": fila_v.get("error_medio"),
        }

    # -------------------------------------------------------------------
    # MEDICION
    # -------------------------------------------------------------------

    @staticmethod
    def _acotar(valor) -> float:
        try:
            return max(FACTOR_MIN, min(FACTOR_MAX, float(valor)))
        except (TypeError, ValueError):
            return 1.0

    @staticmethod
    def _lambdas_de(prediccion: dict) -> Optional[Tuple[float, float]]:
        """
        Goles estimados por lado a partir de una predicción guardada.

        Se prefieren `lambda_home`/`lambda_away`, que es el dato exacto que usó
        el motor. Las predicciones anteriores a que se guardaran no los tienen,
        y para esas se reparte `total_goals_expected` con la ventaja de campo
        que aplica el propio motor, en lugar de tirarlas: son el historial que
        arranca la calibración.
        """
        h = prediccion.get("lambda_home")
        a = prediccion.get("lambda_away")
        if isinstance(h, (int, float)) and isinstance(a, (int, float)) and h > 0 and a > 0:
            return float(h), float(a)

        total = prediccion.get("total_goals_expected")
        if not isinstance(total, (int, float)) or total <= 0:
            return None
        # 54/46 es el reparto local/visitante que produce el motor con sus
        # factores de campo. Es una aproximación, y solo para el historial viejo.
        return float(total) * 0.54, float(total) * 0.46

    def medir(self, limite: int = 500) -> Tuple[MedicionLado, MedicionLado, int]:
        """
        Compara goles estimados y reales sobre el historial disponible.

        Returns:
            (medición local, medición visitante, partidos utilizables)
        """
        local = MedicionLado(lado="Local")
        visitante = MedicionLado(lado="Visitante")

        try:
            pares = self.db.get_pares_prediccion_resultado(limit=limite) or []
        except Exception as e:
            logger.error(f"[Calibración] No se pudo leer el historial: {e}")
            return local, visitante, 0

        est_h, est_a, real_h, real_a = [], [], [], []
        for par in pares:
            crudo = par.get("prediction_json")
            if not crudo:
                continue
            try:
                pred = json.loads(crudo) if isinstance(crudo, str) else dict(crudo)
            except Exception:
                continue

            lambdas = self._lambdas_de(pred)
            if not lambdas:
                continue
            gh, ga = par.get("home_score"), par.get("away_score")
            if gh is None or ga is None:
                continue

            est_h.append(lambdas[0])
            est_a.append(lambdas[1])
            real_h.append(float(gh))
            real_a.append(float(ga))

        n = len(est_h)
        if n:
            local.muestras = visitante.muestras = n
            local.media_estimada = sum(est_h) / n
            local.media_real = sum(real_h) / n
            local.error_absoluto_medio = sum(abs(e - r) for e, r in zip(est_h, real_h)) / n
            visitante.media_estimada = sum(est_a) / n
            visitante.media_real = sum(real_a) / n
            visitante.error_absoluto_medio = sum(abs(e - r) for e, r in zip(est_a, real_a)) / n

        return local, visitante, n

    # -------------------------------------------------------------------
    # AJUSTE
    # -------------------------------------------------------------------

    def calibrar(self, limite: int = 500) -> InformeCalibracion:
        """
        Mide, ajusta un paso hacia el objetivo y guarda. Devuelve el informe.

        Es idempotente en el sentido que importa: llamarla dos veces seguidas
        sin partidos nuevos acerca el factor al mismo objetivo, no lo dispara.
        """
        local, visitante, n = self.medir(limite)
        informe = InformeCalibracion(muestras=n, local=local, visitante=visitante)

        antes_l, antes_v = self.factores()
        informe.factor_local_antes = antes_l
        informe.factor_visitante_antes = antes_v
        informe.factor_local_despues = antes_l
        informe.factor_visitante_despues = antes_v

        if n < MUESTRAS_MINIMAS:
            informe.motivo = (f"hacen falta {MUESTRAS_MINIMAS} partidos con resultado "
                              f"y hay {n}")
            return informe

        despues_l = self._acotar(antes_l + PASO * (local.objetivo - antes_l))
        despues_v = self._acotar(antes_v + PASO * (visitante.objetivo - antes_v))

        if despues_l in (FACTOR_MIN, FACTOR_MAX) or despues_v in (FACTOR_MIN, FACTOR_MAX):
            informe.avisos.append(
                "La corrección ha topado con su límite (±15%). Un sesgo tan grande "
                "no se arregla escalando goles: revisa los datos de entrada del "
                "modelo antes de fiarte del ajuste."
            )

        self.db.save_calibracion(PARAM_LOCAL, despues_l, n,
                                 local.error_absoluto_medio, local.sesgo)
        self.db.save_calibracion(PARAM_VISITANTE, despues_v, n,
                                 visitante.error_absoluto_medio, visitante.sesgo)
        self.refrescar()

        informe.factor_local_despues = despues_l
        informe.factor_visitante_despues = despues_v
        informe.aplicada = True
        logger.info("[Calibración] %s", informe.resumen())
        return informe
