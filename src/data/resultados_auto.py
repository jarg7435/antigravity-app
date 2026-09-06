"""
Sincronización automática de resultados — La Gema JARG74.

Busca el marcador final de los estudios que siguen pendientes, lo vuelca en la
base de datos y dispara la calibración del modelo, sin que haya que teclear
ningún resultado a mano.

POR QUÉ NO SERVÍA LO QUE YA HABÍA
---------------------------------
La interfaz ya tenía un botón "REVISAR RESULTADO (IA Web Access)", pero colgaba
de `web_fetcher.fetch_real_result`, que delega en `api_manager.get_match_result`
y ese solo mira API-Football. Para un partido ya jugado eso no puede funcionar:
el plan gratuito rechaza cualquier fecha fuera de hoy±1 —está comprobado en
`cascada.py`— así que la consulta se iba a la basura justo en el único caso en
el que se usa, que es mirar hacia atrás. De ahí que los marcadores acabaran
metiéndose uno a uno.

Aquí las fuentes son las que sí cubren el pasado:

    1. football-data.org   marcador oficial, `score.fullTime`
    2. SofaScore           `homeScore.display` con `status.type == finished`

TRES COMPROBACIONES ANTES DE DAR UN MARCADOR POR BUENO
------------------------------------------------------
Un resultado equivocado es peor que ninguno: entra en la base, alimenta la
calibración y ensucia el modelo sin que nadie lo note. Por eso no basta con
encontrar "un partido entre estos dos equipos":

1. ORIENTACIÓN. Al buscar "Alavés - Athletic" SofaScore devuelve el
   "Athletic - Alavés" de la vuelta, que es otro partido con otro marcador. Si
   el local encontrado no es nuestro local, se descarta.
2. FECHA. El partido hallado tiene que caer dentro de un día de la fecha
   guardada. Dos equipos se cruzan dos veces por temporada, y más en copa.
3. FINALIZADO. Un partido en juego tiene marcador, y no es el definitivo.

LO QUE NO SE INVENTA
--------------------
Estas fuentes dan goles, no córners ni tarjetas ni remates. Esos campos se
guardan como NULL, no como cero: un cero dice "se midió y salió cero", y el
semáforo lo pintaría como un fallo en un mercado que nadie llegó a medir. El
usuario puede completarlos a mano cuando quiera; mientras tanto, el aprendizaje
se limita al 1X2 y a los goles, que es lo que de verdad se ha comprobado.

Uso:

    from src.data.resultados_auto import sincronizar
    informe = sincronizar(db_manager, learning_engine)
    print(informe.resumen())

Autor: Antigravity - La Gema JARG74
"""

import logging
import unicodedata
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)


# Un partido dura hora y media más el descanso. Con 2.5 horas desde el saque
# inicial, cualquier encuentro está cerrado y publicado.
MARGEN_FIN_HORAS = 2.5

# Días de tolerancia entre la fecha guardada y la de la fuente. Uno basta para
# absorber husos horarios y partidos que empiezan de noche; más abriría la
# puerta al partido de la vuelta.
TOLERANCIA_DIAS = 1

# Palabras que no identifican a nadie y solo estorban al comparar nombres.
# "real" y "deportivo" NO están: son ambiguas, pero quitarlas seria peor,
# porque entonces "Real Madrid" y "Real Sociedad" pasarían a compartirlo todo.
_RUIDO_EQUIPO = {
    "fc", "cf", "cd", "ud", "rc", "rcd", "sd", "ac", "as", "sc", "afc", "cp",
    "club", "de", "del", "la", "el", "los", "las", "futbol", "football",
    "balompie", "futebol", "calcio", "sad", "ssd", "ssc", "ac",
}


@dataclass
class ResultadoAuto:
    """Un marcador encontrado y ya verificado."""

    match_id: str
    home_team: str
    away_team: str
    home_score: int
    away_score: int
    fuente: str
    fecha_fuente: str = ""

    @property
    def winner(self) -> str:
        if self.home_score > self.away_score:
            return "LOCAL"
        if self.away_score > self.home_score:
            return "VISITANTE"
        return "EMPATE"

    def __str__(self) -> str:
        return (f"{self.home_team} {self.home_score}-{self.away_score} "
                f"{self.away_team} ({self.fuente})")


@dataclass
class InformeSincronizacion:
    """Qué se ha revisado y qué se ha volcado."""

    pendientes: int = 0
    sin_jugar: int = 0
    encontrados: List[ResultadoAuto] = field(default_factory=list)
    no_encontrados: List[str] = field(default_factory=list)
    errores: List[str] = field(default_factory=list)
    calibracion: str = ""

    @property
    def guardados(self) -> int:
        return len(self.encontrados)

    def resumen(self) -> str:
        if not self.pendientes:
            return "No hay estudios pendientes de resultado."
        partes = [f"{self.pendientes} estudios pendientes."]
        if self.sin_jugar:
            partes.append(f"{self.sin_jugar} aún no se han jugado.")
        if self.encontrados:
            partes.append(f"{self.guardados} resultados volcados.")
        if self.no_encontrados:
            partes.append(f"{len(self.no_encontrados)} sin marcador publicado todavía.")
        if self.errores:
            partes.append(f"{len(self.errores)} con error.")
        return " ".join(partes)


# =============================================================================
# COTEJO DE EQUIPOS Y FECHAS
# =============================================================================

def _norm(texto: str) -> str:
    base = unicodedata.normalize("NFD", str(texto or ""))
    base = "".join(c for c in base if unicodedata.category(c) != "Mn")
    return base.lower().strip()


def _tokens(nombre: str) -> set:
    """Palabras con las que se reconoce a un equipo, sin formas jurídicas."""
    limpio = "".join(c if c.isalnum() or c.isspace() else " " for c in _norm(nombre))
    return {p for p in limpio.split() if len(p) >= 3 and p not in _RUIDO_EQUIPO}


def mismo_equipo(a: str, b: str) -> bool:
    """
    ¿Estos dos nombres son el mismo club?

    Se exige que las palabras de uno estén TODAS en el otro, no que se toquen en
    alguna. Con una coincidencia suelta bastaba para hermanar "Real Madrid" con
    "Real Sociedad" o con "Real Betis", que comparten la primera palabra y no
    tienen nada que ver.
    """
    ta, tb = _tokens(a), _tokens(b)
    if not ta or not tb:
        return False
    return ta <= tb or tb <= ta


def _a_fecha(valor) -> Optional[datetime]:
    """Normaliza a datetime lo que llegue: datetime, ISO con o sin hora, o None."""
    if isinstance(valor, datetime):
        return valor
    if not valor:
        return None
    texto = str(valor).replace("Z", "").strip()
    for corte in (19, 16, 10):
        try:
            return datetime.fromisoformat(texto[:corte])
        except (ValueError, TypeError):
            continue
    return None


def ya_termino(fecha_partido, ahora: Optional[datetime] = None) -> bool:
    """
    ¿Ha acabado ya este partido?

    Sin fecha se responde que no: preguntar por el marcador de un partido cuya
    fecha no se conoce solo puede traer el de otro.
    """
    f = _a_fecha(fecha_partido)
    if f is None:
        return False
    ahora = ahora or datetime.now()
    return f + timedelta(hours=MARGEN_FIN_HORAS) <= ahora


def _fecha_compatible(esperada, hallada) -> bool:
    """¿La fecha del partido hallado corresponde a la del estudio?"""
    fe, fh = _a_fecha(esperada), _a_fecha(hallada)
    if fe is None or fh is None:
        return True          # sin fecha en la fuente no se puede descartar
    return abs((fh.date() - fe.date()).days) <= TOLERANCIA_DIAS


# =============================================================================
# FUENTES
# =============================================================================

def buscar_en_football_data(home: str, away: str, fecha, competicion: str
                            ) -> Optional[Dict]:
    """Marcador oficial en football-data.org, si cubre esa competición."""
    f = _a_fecha(fecha)
    if f is None:
        return None

    try:
        from src.data.football_data_org import COMPETITION_CODES
        from src.data.api_manager import FootballDataClient
    except Exception as e:
        logger.error(f"[ResultadosAuto] football-data no disponible: {e}")
        return None

    # "La Liga (España)" -> "La Liga"
    liga = str(competicion or "").split(" (")[0].strip()
    codigo = COMPETITION_CODES.get(liga)
    if not codigo:
        return None

    cliente = FootballDataClient()
    if not getattr(cliente, "api_key", ""):
        return None

    desde = (f - timedelta(days=TOLERANCIA_DIAS)).date().isoformat()
    hasta = (f + timedelta(days=TOLERANCIA_DIAS)).date().isoformat()
    try:
        partidos = cliente.get_competition_matches(
            codigo, date_from=desde, date_to=hasta, status="FINISHED") or []
    except Exception as e:
        logger.error(f"[ResultadosAuto] football-data: {e}")
        return None

    for p in partidos:
        ht = p.get("homeTeam", {}) or {}
        at = p.get("awayTeam", {}) or {}
        nombre_h = ht.get("shortName") or ht.get("name") or ""
        nombre_a = at.get("shortName") or at.get("name") or ""
        # La orientacion se respeta: local con local y visitante con visitante.
        if not (mismo_equipo(home, nombre_h) and mismo_equipo(away, nombre_a)):
            continue
        marcador = ((p.get("score") or {}).get("fullTime") or {})
        gh, ga = marcador.get("home"), marcador.get("away")
        if gh is None or ga is None:
            continue
        return {"home_score": int(gh), "away_score": int(ga),
                "fecha": p.get("utcDate", ""), "fuente": "football-data.org"}
    return None


def buscar_en_sofascore(home: str, away: str, fecha) -> Optional[Dict]:
    """Marcador en SofaScore, que cubre lo que football-data.org no alcanza."""
    f = _a_fecha(fecha)
    try:
        from src.data.scrapers.sofascore_api import _find_event
        evento = _find_event(home, away, f)
    except Exception as e:
        logger.error(f"[ResultadosAuto] SofaScore: {e}")
        return None

    if not evento:
        return None

    estado = ((evento.get("status") or {}).get("type") or "").lower()
    if estado != "finished":
        return None

    nombre_h = (evento.get("homeTeam") or {}).get("name", "")
    nombre_a = (evento.get("awayTeam") or {}).get("name", "")
    # El buscador de SofaScore devuelve el partido de la vuelta con la misma
    # facilidad que el de la ida: sin esta comprobacion, el marcador entraria
    # del reves.
    if not (mismo_equipo(home, nombre_h) and mismo_equipo(away, nombre_a)):
        return None

    gh = (evento.get("homeScore") or {}).get("display")
    ga = (evento.get("awayScore") or {}).get("display")
    if gh is None or ga is None:
        return None

    marca = evento.get("startTimestamp")
    fecha_ev = ""
    if marca:
        try:
            fecha_ev = datetime.fromtimestamp(int(marca)).isoformat()
        except Exception:
            pass

    return {"home_score": int(gh), "away_score": int(ga),
            "fecha": fecha_ev, "fuente": "SofaScore"}


FUENTES = (
    ("football-data.org", buscar_en_football_data),
    ("SofaScore", buscar_en_sofascore),
)


def buscar_resultado(match_id: str, home: str, away: str, fecha,
                     competicion: str = "") -> Optional[ResultadoAuto]:
    """
    Marcador final del partido, probando las fuentes en orden.

    Devuelve None si ninguna lo publica todavía, que es distinto de un error:
    un partido recién acabado puede tardar en aparecer.
    """
    for nombre, funcion in FUENTES:
        try:
            if funcion is buscar_en_football_data:
                bruto = funcion(home, away, fecha, competicion)
            else:
                bruto = funcion(home, away, fecha)
        except Exception as e:
            logger.error(f"[ResultadosAuto] {nombre} falló: {e}")
            continue

        if not bruto:
            continue

        if not _fecha_compatible(fecha, bruto.get("fecha")):
            logger.info(
                "[ResultadosAuto] %s: %s descartado, la fecha (%s) no es la del "
                "estudio (%s); parece otro enfrentamiento.",
                nombre, match_id, bruto.get("fecha"), fecha)
            continue

        return ResultadoAuto(
            match_id=match_id, home_team=home, away_team=away,
            home_score=bruto["home_score"], away_score=bruto["away_score"],
            fuente=bruto.get("fuente", nombre), fecha_fuente=str(bruto.get("fecha", "")),
        )
    return None


# =============================================================================
# SINCRONIZACION
# =============================================================================

def sincronizar(db_manager=None, learning_engine=None, limite: int = 100,
                ahora: Optional[datetime] = None) -> InformeSincronizacion:
    """
    Vuelca el marcador de todos los estudios pendientes ya jugados.

    Args:
        db_manager: DataManager. Si no se pasa, se crea uno.
        learning_engine: LearningEngine con el que registrar cada resultado y
            recalibrar. Si no se pasa, se crea uno.
        limite: cuántos pendientes revisar como mucho.
        ahora: momento de referencia, para poder probarlo sin esperar.

    Returns:
        InformeSincronizacion con lo encontrado y lo que dijo la calibración.
    """
    informe = InformeSincronizacion()

    if db_manager is None:
        from src.data.db_manager import DataManager
        db_manager = DataManager()

    try:
        pendientes = db_manager.get_pendientes_para_resultado(limit=limite) or []
    except Exception as e:
        informe.errores.append(f"No se pudieron leer los pendientes: {e}")
        return informe

    informe.pendientes = len(pendientes)
    if not pendientes:
        return informe

    if learning_engine is None:
        try:
            from src.logic.bpa_engine import BPAEngine
            from src.logic.learning_engine import LearningEngine
            learning_engine = LearningEngine(BPAEngine(), db_manager)
        except Exception as e:
            informe.errores.append(f"No se pudo crear el motor de aprendizaje: {e}")
            learning_engine = None

    for est in pendientes:
        mid = est.get("match_id", "")
        home, away = est.get("home_team", ""), est.get("away_team", "")
        fecha, liga = est.get("date", ""), est.get("competition", "")

        if not ya_termino(fecha, ahora):
            informe.sin_jugar += 1
            continue

        try:
            hallado = buscar_resultado(mid, home, away, fecha, liga)
        except Exception as e:
            informe.errores.append(f"{mid}: {type(e).__name__}: {str(e)[:80]}")
            continue

        if not hallado:
            informe.no_encontrados.append(f"{home} vs {away}")
            continue

        try:
            _volcar(db_manager, learning_engine, hallado, liga)
            informe.encontrados.append(hallado)
            logger.info("[ResultadosAuto] Volcado %s", hallado)
        except Exception as e:
            informe.errores.append(f"{mid}: al guardar — {type(e).__name__}: {str(e)[:80]}")

    # La calibracion se dispara UNA vez al final, no por cada partido: mide
    # sobre el historial entero, asi que llamarla diez veces seguidas solo daria
    # diez pasos hacia el mismo sitio y convertiria una jornada en una ley.
    if informe.encontrados and learning_engine is not None:
        try:
            informe.calibracion = learning_engine._recalibrar_goles()
        except Exception as e:
            informe.errores.append(f"Al recalibrar: {type(e).__name__}: {str(e)[:80]}")

    return informe


def _volcar(db_manager, learning_engine, res: ResultadoAuto, competicion: str):
    """
    Guarda el marcador y registra el aprendizaje que se puede comprobar.

    Los córners, tarjetas y remates van a None y no a cero. La diferencia no es
    cosmética: cero significa "se midió y salió cero", y con eso el semáforo
    marcaría como fallado un mercado que nadie ha llegado a medir, además de
    hundir la precisión histórica con partidos que nunca se comprobaron.
    """
    db_manager.save_resultado(res.match_id, {
        "home_score": res.home_score,
        "away_score": res.away_score,
        "winner": res.winner,
        "corners": None, "cards": None, "shots": None, "shots_on_target": None,
        "home_corners": None, "away_corners": None,
        "home_cards": None, "away_cards": None,
        "home_shots": None, "away_shots": None,
        "home_shots_on_target": None, "away_shots_on_target": None,
    })

    if learning_engine is None:
        return
    try:
        learning_engine.registrar_1x2_automatico(res, competicion)
    except Exception as e:
        logger.error(f"[ResultadosAuto] No se pudo registrar el 1X2 de {res.match_id}: {e}")
