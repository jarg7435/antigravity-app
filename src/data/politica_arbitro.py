# -*- coding: utf-8 -*-
"""
Politica de aceptacion de designaciones arbitrales — La Gema JARG74.

Directriz: ante la duda, el campo se deja vacio. Un arbitro equivocado no es un
dato aproximado, es un dato falso que entra en el modelo de tarjetas y en el
analisis estrategico con la misma autoridad que uno bueno, y ahi ya no hay nada
que lo distinga. Un hueco, en cambio, se ve, y se rellena a mano en diez
segundos.

El listón queda asi:

    SE ASIGNA SOLA          la designacion sale del registro del propio partido
                            (API-Football, football-data.org, Sportmonks) o la
                            firma una federacion o liga (dominio oficial).

    NO SE ASIGNA NUNCA      prensa, buscadores web, titulares RSS, respuestas de
                            un modelo con busqueda web, scrapers de portada y
                            cualquier coincidencia por aproximacion — por muchas
                            que sean y por mucho que se repitan entre si.

Lo segundo es la parte que cambia. Antes bastaba con que dos fuentes de prensa
coincidieran para dar un nombre por bueno, y dos medios que copian el mismo
teletipo no son dos fuentes independientes: son una repetida. Asi es como se
asigno un arbitro erroneo por una coincidencia web.

Los candidatos rechazados no se tiran a la basura: viajan en
`candidato_descartado` y en `evidencias`, que es lo que la interfaz enseña en el
log plegable. Se pueden leer, pero no se asignan, y sobre todo no llegan al
modelo.

Autor: Antigravity - La Gema JARG74
"""

import logging
from typing import Dict, Optional

logger = logging.getLogger(__name__)

VERIFICADO = "VERIFICADO"

# Nombres de relleno que las fuentes devuelven cuando no han encontrado nada.
_NOMBRES_VACIOS = {
    "", "-", "?", "n/a", "na", "tbd", "tba", "unknown", "no asignado",
    "por detectar", "por confirmar", "desconocido", "sin asignar", "pendiente",
}

MOTIVO_RECHAZO = ("Se ha encontrado un nombre, pero ninguna fuente oficial ni el "
                  "registro del partido lo confirma, así que no se asigna.")

# Palabras que ninguna persona lleva en el nombre, pero que abundan en los
# titulares de donde se extraen los candidatos. Caso real: buscando el Valencia
# - Barcelona, dos medios devolvian "LaLiga EA Sports", sacado de rotulos de
# programacion de television. Tiene tres palabras capitalizadas, asi que el
# filtro de plausibilidad lo daba por bueno, y no es un club, asi que el filtro
# de equipos tampoco lo paraba. Se comparan palabra a palabra, sin tildes.
_PALABRAS_NO_PERSONA = {
    "laliga", "liga", "ligas", "premier", "bundesliga", "serie", "seriea",
    "ligue", "championship", "champions", "europa", "conference", "uefa",
    "fifa", "rfef", "cta", "ea", "sports", "sport", "santander", "endesa",
    "copa", "supercopa", "eurocopa", "mundial", "jornada", "futbol", "football",
    "calcio", "matchday", "directo", "online", "streaming", "tv",
}


def _sin_tildes(texto: str) -> str:
    import unicodedata
    return "".join(c for c in unicodedata.normalize("NFD", texto)
                   if unicodedata.category(c) != "Mn")


def _nombre_util(nombre) -> bool:
    """
    ¿Es esto el nombre de una persona, y no un relleno ni un trozo de titular?

    Tres cribas encadenadas, cada una para una basura distinta que se ha visto
    de verdad: la forma de nombre propio, los nombres de club —ningun club
    arbitra— y las marcas de competicion de los rotulos de television.
    """
    limpio = str(nombre or "").strip()
    if not limpio or limpio.lower() in _NOMBRES_VACIOS:
        return False

    palabras = {p.strip(".,;:()'\"") for p in _sin_tildes(limpio).lower().split()}
    if palabras & _PALABRAS_NO_PERSONA:
        logger.debug(f"Descartado {limpio!r}: contiene una palabra de competición.")
        return False

    try:
        from src.data.investigador_web import _es_nombre_de_equipo
        if _es_nombre_de_equipo(limpio):
            logger.debug(f"Descartado {limpio!r}: es el nombre de un club.")
            return False
    except Exception as e:
        logger.debug(f"No se pudo comprobar si {limpio!r} es un club: {e}")

    try:
        from src.data.referee_database import es_nombre_plausible
        return bool(es_nombre_plausible(limpio))
    except Exception as e:
        logger.debug(f"No se pudo comprobar la plausibilidad de {limpio!r}: {e}")
        # Sin el filtro disponible se es conservador: no se asigna.
        return False


def es_contrastada(ref: Optional[Dict]) -> bool:
    """
    ¿Se puede asignar esta designacion sin intervencion de nadie?

    Exige las tres cosas a la vez, porque cada una tapa un agujero distinto:
    el estado VERIFICADO (solo lo ponen las fuentes que leen el registro del
    partido o un dominio oficial), la bandera `_is_fallback` en falso, y un
    nombre con forma de nombre. Un titular recortado cumplia las dos primeras
    en alguna rama y entraba igual.
    """
    if not isinstance(ref, dict):
        return False
    if ref.get("_is_fallback") is True:
        return False
    if str(ref.get("estado") or "").upper() != VERIFICADO:
        return False
    if str(ref.get("confianza") or "").upper() == "BAJA":
        return False
    return _nombre_util(ref.get("name"))


def rechazar(ref: Optional[Dict], motivo: str = "") -> Dict:
    """
    Convierte un resultado no contrastado en un hueco limpio.

    Conserva todo lo que sirve para que una persona lo resuelva —enlaces de
    consulta, evidencias, el estado de las APIs— y aparta el nombre a
    `candidato_descartado`, donde no lo puede leer ni el modelo ni la ficha del
    partido.
    """
    from src.models.base import RefereeStrictness

    ref = ref if isinstance(ref, dict) else {}
    descartado = str(ref.get("name") or "").strip()

    salida = {
        "name": "",
        "strictness": RefereeStrictness.MEDIUM,
        "avg_cards": 4.0,
        "source": ref.get("source") or "Designación no confirmada",
        "verification_link": ref.get("verification_link") or "",
        "consultar": ref.get("consultar") or [],
        "evidencias": ref.get("evidencias") or [],
        "estado": "PENDIENTE",
        "_is_fallback": True,
        "motivo": motivo or ref.get("motivo") or MOTIVO_RECHAZO,
    }
    if descartado:
        salida["candidato_descartado"] = descartado
        salida["motivo"] = motivo or MOTIVO_RECHAZO
    if ref.get("degradacion"):
        salida["degradacion"] = ref["degradacion"]
    return salida


def filtrar(ref: Optional[Dict]) -> Dict:
    """
    Paso obligatorio a la salida de cualquier busqueda de arbitro.

    Se aplica al final de la cascada y del fetcher, y no rama por rama, porque
    las ramas se anaden y se olvidan: un `return` nuevo en mitad de una cascada
    de ocho fuentes no se acuerda de la politica. Aqui pasa todo o no pasa nada.
    """
    if es_contrastada(ref):
        return ref

    descartado = str((ref or {}).get("name") or "").strip()
    if descartado:
        logger.info(f"[Política] Descartado «{descartado}»: "
                    f"estado={(ref or {}).get('estado')!r}, "
                    f"fuente={(ref or {}).get('source')!r}")
    return rechazar(ref)
