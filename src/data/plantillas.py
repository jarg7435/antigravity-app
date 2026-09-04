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
    j = _norm(jugador)
    if not j:
        return False

    for miembro in plantilla:
        m = _norm(miembro)
        if not m:
            continue
        if j == m or j in m or m in j:
            return True

        # Apellido compartido, exigiendo longitud para no casar por azar.
        apellido = j.split()[-1]
        if len(apellido) >= 4 and apellido in m.split():
            return True

    return False


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

    jugadores = [j.get("name", "") for j in datos.get("squad", []) if j.get("name")]
    if jugadores:
        _CACHE.set("plantilla", clave, jugadores, "football-data.org", TTL_PLANTILLA)
        logger.info(f"Plantilla vigente de {equipo}: {len(jugadores)} jugadores")

    return jugadores


# =============================================================================
# Validación de alineaciones
# =============================================================================

def filtrar_alineacion(jugadores: List[str], equipo: str,
                       liga: str = None) -> Tuple[List[str], List[str]]:
    """
    Separa una alineación en jugadores vigentes y jugadores que ya no están.

    Si no se puede obtener la plantilla, se devuelve la alineación intacta: sin
    plantilla de referencia no hay motivo para descartar a nadie.

    Returns:
        (vigentes, descartados)
    """
    if not jugadores:
        return [], []

    plantilla = plantilla_actual(equipo, liga)
    if not plantilla:
        return list(jugadores), []

    vigentes, descartados = [], []
    for jugador in jugadores:
        (vigentes if esta_en_plantilla(jugador, plantilla) else descartados).append(jugador)

    if descartados:
        logger.warning(
            f"{equipo}: {len(descartados)} jugador(es) ya no estan en plantilla: "
            f"{', '.join(descartados)}"
        )
    return vigentes, descartados


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
