"""
Plantillas vigentes por equipo — La Gema JARG74.

Fuente única de verdad sobre quién está HOY en cada club. Existe porque el
sistema venía arrastrando plantillas codificadas a mano en mock_provider.py con
jugadores de 2023-24: al comprobar el Real Betis contra la plantilla real, de
los seis jugadores que mostraba la interfaz solo uno seguía en el club.

Los datos salen de football-data.org, que sí publica la plantilla de la
temporada en curso en su plan gratuito (verificado: 25 jugadores del Betis para
la temporada 2026-08-16 / 2027-05-30). API-Football no sirve aquí: su plan
gratuito solo cubre las temporadas 2022-2024.

Uso típico:

    from src.data import plantillas
    vigentes, descartados = plantillas.filtrar_alineacion(
        ["Rui Silva", "Isco", "Lo Celso"], "Real Betis", "La Liga"
    )
    # vigentes    -> ["Isco", "Lo Celso"]
    # descartados -> ["Rui Silva"]

Autor: Antigravity - La Gema JARG74
"""

import logging
import re
import unicodedata
from datetime import date, datetime
from typing import Dict, List, Optional, Tuple

from src.data.cache_manager import CacheManager, TTLConfig

logger = logging.getLogger(__name__)

# Las plantillas cambian poco fuera del mercado de fichajes, pero un TTL de un
# día evita servir un fichaje reciente como si no existiera.
TTL_PLANTILLA = 24 * 3600

# Inscritos por debajo de los cuales un listado se considera cortado. Una
# plantilla de primera division ronda los 25; con menos de esto no sirve como
# patron con el que acusar a nadie de haberse ido del club.
PLANTILLA_MINIMA = 18

# Caché persistente: sobrevive a los redeploy y ahorra peticiones del plan
# gratuito de football-data.org (10 por minuto).
_CACHE = CacheManager(persist=True, cache_dir="data/cache")

# Mapa equipo -> id de football-data.org, por competición. Se llena bajo demanda.
_IDS_POR_LIGA: Dict[str, Dict[str, int]] = {}


# =============================================================================
# Normalización de nombres
# =============================================================================

def _sin_acentos(texto: str) -> str:
    return "".join(
        c for c in unicodedata.normalize("NFD", texto)
        if unicodedata.category(c) != "Mn"
    )


def _norm(texto: str) -> str:
    """Minúsculas, sin acentos, sin puntuación y con espacios colapsados."""
    if not texto:
        return ""
    t = _sin_acentos(str(texto)).lower()
    t = re.sub(r"[^a-z0-9 ]+", " ", t)
    return re.sub(r"\s+", " ", t).strip()


# Formas juridicas y palabras de relleno. "real" NO entra aqui: distingue a
# Real Madrid de Real Sociedad o Real Betis, y quitarla hacia que "Real Madrid"
# se redujera a "madrid" y casara con "Club Atletico de Madrid".
_RUIDO_EQUIPO = {
    "cf", "fc", "cd", "ud", "rc", "rcd", "sd", "ac", "as", "sc", "afc",
    "club", "balompie", "de", "futbol", "football", "deportivo",
}


def _clave_equipo(nombre: str) -> str:
    """
    Reduce un nombre de equipo a sus palabras distintivas.

    "Real Betis Balompié" y "Real Betis" comparten clave "betis", que es lo que
    permite casar el nombre que usa la app con el que devuelve la API.
    """
    palabras = [p for p in _norm(nombre).split() if p not in _RUIDO_EQUIPO]
    return " ".join(palabras) if palabras else _norm(nombre)


def _casan_equipos(a: str, b: str) -> bool:
    """
    ¿Son el mismo club?

    Se comparan conjuntos de palabras, no subcadenas: "Real Madrid" y "Club
    Atletico de Madrid" comparten la palabra "madrid" pero ninguno de los dos
    conjuntos contiene al otro, asi que no casan. La comparacion por subcadena
    si los confundia.
    """
    ta = set(_clave_equipo(a).split())
    tb = set(_clave_equipo(b).split())
    if not ta or not tb:
        return False
    return ta == tb or ta <= tb or tb <= ta


def esta_en_plantilla(jugador: str, plantilla: List[str]) -> bool:
    """
    ¿Aparece este jugador en la plantilla?

    La comparación es tolerante a propósito: la interfaz maneja nombres cortos
    ("Lo Celso", "Isco") mientras la API devuelve el nombre completo ("Giovani
    Lo Celso", "Isco Alarcón"). Se acepta la coincidencia si un nombre está
    contenido en el otro, o si comparten el apellido.
    """
    return resolver_en_plantilla(jugador, plantilla) is not None


def resolver_en_plantilla(jugador: str, plantilla: List[str]) -> Optional[str]:
    """
    A quien de la plantilla corresponde este nombre, si es que a alguien.

    Devuelve el nombre tal y como figura en el listado de inscritos, o None.
    Se resuelve SIEMPRE contra la plantilla entera y nunca miembro a miembro:
    la regla del apellido de abajo solo tiene sentido si puede ver a todos los
    demas. Comprobar de uno en uno la anulaba —en una lista de un solo elemento
    cualquier apellido es unico— y asi es como "Sergio Garcia" se resolvia como
    "Pablo Garcia" y heredaba su demarcacion.
    """
    j = _norm(jugador)
    if not j:
        return None

    palabras_j = set(j.split())

    # Primera pasada: coincidencia literal o por contencion de palabras. La
    # contencion se comprueba sobre palabras completas y no sobre la cadena,
    # porque "Ander" estaba contenido en "Anderson" y los daba por el mismo.
    for miembro in plantilla:
        m = _norm(miembro)
        if not m:
            continue
        palabras_m = set(m.split())
        if j == m or palabras_j <= palabras_m or palabras_m <= palabras_j:
            return miembro

    # Segunda pasada: apellido compartido. Solo se acepta si ese apellido
    # identifica a UN unico miembro de la plantilla. Antes bastaba con que
    # coincidiera, y en un equipo con dos Garcia cualquiera de los dos valia
    # por el otro: un traspasado sobrevivia al filtro gracias a su homonimo.
    if len(palabras_j) >= 2:
        apellido = _norm(jugador).split()[-1]
        if len(apellido) >= 4:
            portadores = [m for m in plantilla if apellido in _norm(m).split()]
            if len(portadores) == 1:
                return portadores[0]

    return None


# =============================================================================
# Acceso a football-data.org
# =============================================================================

def _codigo_competicion(liga: Optional[str]) -> Optional[str]:
    if not liga:
        return None
    from src.data.football_data_org import COMPETITION_CODES
    if liga in COMPETITION_CODES:
        return COMPETITION_CODES[liga]
    for nombre, codigo in COMPETITION_CODES.items():
        if _norm(nombre) == _norm(liga):
            return codigo
    return None


def _cliente():
    try:
        from src.data.football_data_org import FootballDataClient
        cliente = FootballDataClient()
        return cliente if cliente.is_configured else None
    except Exception as e:
        logger.warning(f"No se pudo crear el cliente de football-data.org: {e}")
        return None


def _id_de_equipo(equipo: str, liga: str) -> Optional[int]:
    """Id de football-data.org del equipo, cacheando el listado de la liga."""
    codigo = _codigo_competicion(liga)
    if not codigo:
        return None

    if codigo not in _IDS_POR_LIGA:
        cacheado = _CACHE.get("equipos_liga", codigo)
        if cacheado is None:
            cliente = _cliente()
            if not cliente:
                return None
            try:
                datos = cliente._get(f"competitions/{codigo}/teams") or {}
            except Exception as e:
                logger.warning(f"Error listando equipos de {codigo}: {e}")
                return None
            cacheado = {t.get("name", ""): t.get("id") for t in datos.get("teams", [])}
            _CACHE.set("equipos_liga", codigo, cacheado, "football-data.org", TTL_PLANTILLA)
        _IDS_POR_LIGA[codigo] = cacheado

    equipos = _IDS_POR_LIGA[codigo].items()
    clave = _clave_equipo(equipo)

    # Primero coincidencia exacta de clave, luego la mas laxa por subconjunto.
    for nombre, id_equipo in equipos:
        if _clave_equipo(nombre) == clave:
            return id_equipo
    for nombre, id_equipo in equipos:
        if _casan_equipos(equipo, nombre):
            return id_equipo

    logger.info(f"Equipo no encontrado en football-data.org: {equipo} ({liga})")
    return None


def plantilla_actual(equipo: str, liga: str = None) -> List[str]:
    """
    Nombres de la plantilla vigente del equipo.

    Devuelve lista vacía si no se puede determinar, que es la respuesta honesta:
    preferimos no saber a servir una plantilla de hace dos temporadas.
    """
    if not equipo:
        return []

    clave = _clave_equipo(equipo)
    cacheado = _CACHE.get("plantilla", clave)
    if cacheado is not None:
        return list(cacheado)

    id_equipo = _id_de_equipo(equipo, liga)
    if not id_equipo:
        return []

    cliente = _cliente()
    if not cliente:
        return []

    try:
        datos = cliente._get(f"teams/{id_equipo}") or {}
    except Exception as e:
        logger.warning(f"Error obteniendo plantilla de {equipo}: {e}")
        return []

    detalle = [
        {"nombre": j.get("name", ""), "posicion": j.get("position") or ""}
        for j in datos.get("squad", []) if j.get("name")
    ]
    if detalle:
        _CACHE.set("plantilla_detalle", clave, detalle, "football-data.org", TTL_PLANTILLA)
        logger.info(f"Plantilla vigente de {equipo}: {len(detalle)} jugadores")

    jugadores = [j["nombre"] for j in detalle]
    if jugadores:
        _CACHE.set("plantilla", clave, jugadores, "football-data.org", TTL_PLANTILLA)

    return jugadores


# =============================================================================
# Validación de alineaciones
# =============================================================================

def auditar_alineacion(jugadores: List[str], equipo: str,
                       liga: str = None) -> Dict:
    """
    Contrasta una alineacion con el listado de inscritos vigente.

    Devuelve el resultado Y si ha podido comprobarse, que son dos cosas
    distintas que antes se confundian: filtrar_alineacion devolvia la
    alineacion intacta cuando no lograba la plantilla, y quien la llamaba no
    tenia forma de distinguir "todos vigentes" de "no he podido mirarlo". Por
    ahi seguian entrando los fichajes obsoletos cada vez que la API fallaba.

    Returns:
        {
          "vigentes": [...],        # aparecen en el listado de inscritos
          "descartados": [...],     # no aparecen en el listado
          "verificada": bool,       # False = no hay listado de referencia
          "plantilla": int,         # tamano del listado consultado
          "nombres": [...],         # el listado en si, para poder auditarlo
          "listado_dudoso": bool,   # demasiados fallos: sospecha del listado
          "motivo": str,            # explicacion cuando no se ha podido verificar
        }
    """
    base = {"vigentes": list(jugadores or []), "descartados": [],
            "verificada": False, "plantilla": 0, "nombres": [],
            "listado_dudoso": False, "motivo": ""}

    if not jugadores:
        base["verificada"] = True
        return base

    plantilla = plantilla_actual(equipo, liga)
    if not plantilla:
        base["motivo"] = (
            f"No se ha podido obtener el listado de inscritos vigente de "
            f"{equipo}. Sin esa referencia no se puede garantizar que no haya "
            f"jugadores traspasados en la alineación."
        )
        logger.warning(base["motivo"])
        return base

    vigentes, descartados = [], []
    for jugador in jugadores:
        (vigentes if esta_en_plantilla(jugador, plantilla) else descartados).append(jugador)

    # ¿De quien hay que sospechar cuando falla medio once: del listado o de la
    # alineacion? La respuesta la da el TAMANO del listado, no el numero de
    # fallos.
    #
    # Se probo primero con la proporcion sola —mas de un tercio sin casar,
    # luego el listado es malo— y con datos reales resulto ser al reves. Para el
    # Valencia - Barcelona del 06/09/2026, football-data.org devolvia 27
    # jugadores del Barcelona, una plantilla completa y sana, y los cuatro que
    # no casaban simplemente ya no estaban en el club: quien servia datos viejos
    # era la fuente de alineaciones, no la de plantillas. Marcar aquel listado
    # como sospechoso habria tapado el problema de verdad.
    #
    # Una plantilla de primera division ronda los 25 inscritos. Por debajo de
    # PLANTILLA_MINIMA el listado esta claramente cortado y no sirve de patron;
    # por encima, si un jugador no aparece es que no esta.
    umbral = max(2, -(-len(jugadores) // 3))          # un tercio, redondeando
    listado_dudoso = (len(descartados) > umbral
                      and len(plantilla) < PLANTILLA_MINIMA)

    if descartados:
        logger.warning(
            f"{equipo}: {len(descartados)}/{len(jugadores)} no aparecen en el "
            f"listado de {len(plantilla)} inscritos: {', '.join(descartados)}"
            + ("  [listado sospechoso]" if listado_dudoso else "")
        )

    return {"vigentes": vigentes, "descartados": descartados,
            "verificada": True, "plantilla": len(plantilla),
            "nombres": list(plantilla), "listado_dudoso": listado_dudoso,
            "motivo": ""}


def filtrar_alineacion(jugadores: List[str], equipo: str,
                       liga: str = None) -> Tuple[List[str], List[str]]:
    """
    Separa una alineación en jugadores vigentes y jugadores que ya no están.

    Se mantiene por compatibilidad con quien ya la usa. Para saber ademas si la
    comprobacion ha llegado a hacerse, usa auditar_alineacion.

    Returns:
        (vigentes, descartados)
    """
    informe = auditar_alineacion(jugadores, equipo, liga)
    return informe["vigentes"], informe["descartados"]


def temporada_vigente(liga: str = None) -> Optional[Dict]:
    """Fechas de la temporada en curso segun football-data.org, para auditoria."""
    codigo = _codigo_competicion(liga)
    if not codigo:
        return None
    cliente = _cliente()
    if not cliente:
        return None
    try:
        datos = cliente._get(f"competitions/{codigo}") or {}
    except Exception:
        return None
    temporada = datos.get("currentSeason") or {}
    return {
        "inicio": temporada.get("startDate"),
        "fin": temporada.get("endDate"),
        "jornada": temporada.get("currentMatchday"),
    }


# =============================================================================
# Posiciones
# =============================================================================

# football-data.org usa etiquetas en ingles, unas genericas ("Defence") y otras
# especificas ("Centre-Back", "Left Winger"). Se resuelven por palabra clave.
_MAPA_POSICION = (
    ("goalkeeper", "GOALKEEPER"), ("keeper", "GOALKEEPER"),
    ("defence", "DEFENDER"), ("defender", "DEFENDER"), ("back", "DEFENDER"),
    ("midfield", "MIDFIELDER"),
    ("offence", "FORWARD"), ("forward", "FORWARD"), ("winger", "FORWARD"),
    ("striker", "FORWARD"), ("attack", "FORWARD"),
)


def plantilla_detallada(equipo: str, liga: str = None) -> List[Dict]:
    """Plantilla vigente con la posicion de cada jugador."""
    if not equipo:
        return []
    clave = _clave_equipo(equipo)
    cacheado = _CACHE.get("plantilla_detalle", clave)
    if cacheado is None:
        plantilla_actual(equipo, liga)          # rellena ambas caches
        cacheado = _CACHE.get("plantilla_detalle", clave) or []
    return list(cacheado)


def demarcacion_de(jugador: str, equipo: str, liga: str = None) -> Dict:
    """
    Demarcacion del jugador segun el listado de inscritos, con su procedencia.

    Devuelve tambien POR QUE no se ha podido determinar, que es lo que permite
    a la interfaz escribir "sin demarcación" en lugar de rellenar el hueco con
    un centrocampista imaginario.

    Returns:
        {
          "posicion": PlayerPosition | None,
          "etiqueta": str,    # lo que dice la fuente ("Centre-Back", "Offence")
          "motivo": str,      # vacio si se ha determinado
        }
    """
    from src.models.base import PlayerPosition

    detalle = plantilla_detallada(equipo, liga)
    if not detalle:
        return {"posicion": None, "etiqueta": "",
                "motivo": f"Sin listado de inscritos vigente de {equipo}."}

    # Se resuelve contra el listado completo, no miembro a miembro: ver
    # resolver_en_plantilla.
    nombre_inscrito = resolver_en_plantilla(jugador, [m["nombre"] for m in detalle])
    if nombre_inscrito is None:
        return {"posicion": None, "etiqueta": "",
                "motivo": f"{jugador} no aparece en el listado de inscritos de {equipo}."}

    miembro = next(m for m in detalle if m["nombre"] == nombre_inscrito)
    etiqueta = (miembro.get("posicion") or "").strip()
    clave_texto = etiqueta.lower()
    for clave, nombre_enum in _MAPA_POSICION:
        if clave in clave_texto:
            return {"posicion": getattr(PlayerPosition, nombre_enum),
                    "etiqueta": etiqueta, "motivo": ""}

    return {"posicion": None, "etiqueta": etiqueta,
            "motivo": (f"La fuente da la demarcación como «{etiqueta}», que no "
                       f"se corresponde con ninguna conocida.")
                      if etiqueta else
                      f"{nombre_inscrito} figura sin demarcación en el listado."}


def posicion_de(jugador: str, equipo: str, liga: str = None):
    """
    Posicion real del jugador segun la plantilla vigente.

    Devuelve un PlayerPosition, o None si no se puede determinar. Existe porque
    la interfaz asignaba MIDFIELDER a todos los jugadores por defecto y
    mostraba a Oblak como centrocampista. Para saber ademas el motivo, usa
    demarcacion_de.
    """
    return demarcacion_de(jugador, equipo, liga)["posicion"]
