# -*- coding: utf-8 -*-
"""
Búsqueda automática de la designación arbitral — La Gema JARG74.

El botón «Buscar Árbitro Auto» llamaba a la cascada de fuentes dentro de un
`try` que terminaba pintando en pantalla `type(e).__name__: e`. Cualquier
tropiezo —el timeout de una fuente lenta, una competición que el plan
contratado no cubre, o un descuido del propio código— acababa como el mismo
error críptico, sin decirle a quien lo lee que la aplicación ya tiene un campo
para escribir el nombre a mano justo debajo.

Este módulo se queda con esa parte. Recibe la consulta ya preparada, la ejecuta,
y pase lo que pase devuelve un diccionario de árbitro válido para la interfaz:
nunca propaga la excepción. Cuando no hay designación, clasifica el motivo

    motivo             qué lo provoca
    ----------------   --------------------------------------------------------
    TIEMPO_AGOTADO     la fuente no contestó dentro de su plazo
    SIN_CONEXION       no se pudo llegar a la fuente (red, DNS, TLS)
    FUERA_DE_PLAN      la competición no entra en el plan contratado, o la
                       suscripción está caducada o sin cuota
    SIN_DESIGNACION    las fuentes contestaron, pero ninguna publica el árbitro
    FALLO_FUENTE       la fuente respondió algo que no se pudo interpretar

y adjunta en `mensaje_usuario` la frase que guía hacia la entrada manual. El
detalle técnico no se pierde: viaja en el registro, que la interfaz enseña
plegado en «Ver log de búsqueda» para quien quiera saber qué pasó de verdad.

Autor: Antigravity - La Gema JARG74
"""

import logging
from enum import Enum
from typing import Callable, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)


# La frase que ve el usuario. Es siempre la misma pase lo que pase, porque para
# quien está delante de la pantalla todos estos fallos significan lo mismo:
# esta vez toca escribirlo a mano.
MENSAJE_MANUAL = ("Árbitro no disponible en fuentes automáticas. "
                  "Por favor, introduzca el nombre manualmente en el campo inferior.")


class Motivo(str, Enum):
    """Por qué no hay designación automática."""

    TIEMPO_AGOTADO = "tiempo_agotado"
    SIN_CONEXION = "sin_conexion"
    FUERA_DE_PLAN = "fuera_de_plan"
    SIN_DESIGNACION = "sin_designacion"
    FALLO_FUENTE = "fallo_fuente"


# Segunda línea del aviso: explica el porqué sin tecnicismos. La primera línea
# siempre es MENSAJE_MANUAL.
EXPLICACION = {
    Motivo.TIEMPO_AGOTADO: "Las fuentes automáticas tardaron demasiado en responder.",
    Motivo.SIN_CONEXION: "No se ha podido contactar con las fuentes automáticas.",
    Motivo.FUERA_DE_PLAN: "Esta competición no está cubierta por el plan de datos activo.",
    Motivo.SIN_DESIGNACION: "Ninguna fuente publica todavía la designación de este partido.",
    Motivo.FALLO_FUENTE: "Las fuentes automáticas devolvieron una respuesta que no se pudo leer.",
}

# Nombres que la cascada usa como relleno cuando no ha encontrado nada. Tratar
# uno de estos como árbitro válido es lo que llevaba «Por Detectar» hasta la
# ficha del partido.
_NOMBRES_VACIOS = {
    "", "-", "?", "n/a", "na", "tbd", "tba", "unknown", "no asignado",
    "por detectar", "por confirmar", "desconocido", "sin asignar",
}

# Pistas en el texto del error. Se mira el mensaje además del tipo porque las
# fuentes envuelven sus fallos: un timeout de SofaScore llega como RuntimeError
# con "read timed out" dentro.
_PISTAS_TIEMPO = ("timeout", "timed out", "tiempo de espera", "deadline")
_PISTAS_CONEXION = ("connection", "conexion", "conexión", "unreachable", "dns",
                    "max retries", "ssl", "certificate", "network", "socket")
_PISTAS_PLAN = ("not subscribed", "subscription", "suscripcion", "suscripción",
                "plan", "quota", "cuota", "rate limit", "no cubre",
                "fuera del plan", "not allowed", "forbidden", "unauthorized",
                "401", "402", "403", "429")


def _texto(exc: BaseException) -> str:
    return f"{type(exc).__name__}: {exc}".lower()


def clasificar(exc: BaseException) -> Motivo:
    """
    Naturaleza del fallo, a partir del tipo de excepción y de su mensaje.

    El orden importa: un "read timed out" envuelto en un ConnectionError sigue
    siendo un plazo agotado, y un 403 por plan caducado no es un problema de red
    aunque llegue por HTTP.
    """
    texto = _texto(exc)

    if isinstance(exc, TimeoutError) or any(p in texto for p in _PISTAS_TIEMPO):
        return Motivo.TIEMPO_AGOTADO
    if any(p in texto for p in _PISTAS_PLAN):
        return Motivo.FUERA_DE_PLAN
    if isinstance(exc, (ConnectionError, OSError)) or any(p in texto for p in _PISTAS_CONEXION):
        return Motivo.SIN_CONEXION
    return Motivo.FALLO_FUENTE


def hay_designacion(resultado: Optional[Dict]) -> bool:
    """
    ¿Trae este resultado un árbitro que se pueda asignar solo?

    La decisión no se toma aquí: la dicta `politica_arbitro`, que es el único
    sitio donde se define qué es una designación contrastada, para que la
    interfaz y la cascada no puedan discrepar. Esta capa solo añade su propia
    red por si el módulo no estuviera disponible, y entonces se es conservador:
    sin poder comprobar la política, no se asigna nada.
    """
    if not isinstance(resultado, dict):
        return False
    try:
        from src.data.politica_arbitro import es_contrastada
        return es_contrastada(resultado)
    except Exception as e:
        logger.warning(f"No se pudo aplicar la política de árbitro: {e}")
        return False


def _estado_resiliencia() -> Tuple[Dict, List[str]]:
    """Estado del cortacircuitos de API-Football, para el aviso y el registro."""
    registro: List[str] = []
    try:
        from src.data import resiliencia_api as _res
        degradacion = _res.resumen()
        if degradacion.get("degradada"):
            registro.append(f"⚠️ {_res.texto_estado()}")
        return degradacion, registro
    except Exception as e:
        logger.debug(f"No se pudo leer el estado de resiliencia: {e}")
        return {}, registro


def _enlace_de_consulta(liga: str) -> str:
    """Portal oficial donde mirar la designación a mano."""
    try:
        from src.data.investigador_web import _enlaces_de_consulta
        enlaces = _enlaces_de_consulta(liga)
        if enlaces:
            return enlaces[0]["url"]
    except Exception as e:
        logger.debug(f"No se pudo resolver el enlace de consulta: {e}")
    return "https://www.sofascore.com"


def sin_designacion(motivo: Motivo, liga: str = "",
                    detalle: str = "", degradacion: Optional[Dict] = None) -> Dict:
    """
    Ficha de árbitro vacía pero completa, lista para pintar.

    Lleva las mismas claves que una designación encontrada para que la interfaz
    no tenga que distinguir casos, más `mensaje_usuario` y `motivo_codigo`.
    """
    return {
        "name": "",
        "source": "Sin designación en fuentes automáticas",
        "verification_link": _enlace_de_consulta(liga),
        "_is_fallback": True,
        "estado": "PENDIENTE",
        "motivo_codigo": motivo.value,
        "motivo": EXPLICACION[motivo],
        "mensaje_usuario": MENSAJE_MANUAL,
        "detalle_tecnico": detalle,
        "degradacion": degradacion or {},
    }


def _detallar(resultado: Optional[Dict]) -> List[str]:
    """Traza legible de lo que contestó la cascada."""
    if not isinstance(resultado, dict):
        return ["Las fuentes no devolvieron ningún resultado."]

    lineas = [f"Estado: {resultado.get('estado', '—')}",
              f"Fuente: {resultado.get('source', '?')}"]
    if resultado.get("motivo"):
        lineas.append(f"Motivo: {resultado['motivo']}")
    for ev in resultado.get("evidencias", []) or []:
        oficial = " [OFICIAL]" if ev.get("oficial") else ""
        lineas.append(f"  · {ev.get('name')} — {ev.get('fuente')}{oficial}")
        if ev.get("url"):
            lineas.append(f"    {ev['url']}")
    if not resultado.get("evidencias"):
        lineas.append("  · Sin evidencias web; ninguna fuente publica todavía la designación.")
    return lineas


def buscar_designacion(consultar: Callable[[], Optional[Dict]],
                       liga: str = "") -> Tuple[Dict, List[str]]:
    """
    Ejecuta la búsqueda automática y devuelve (ficha_de_arbitro, registro).

    `consultar` es la llamada a la cascada ya preparada con sus argumentos. Se
    invoca aquí dentro, y no fuera, para que también quede cubierto lo que falle
    al montarla: construir el fetcher, leer una credencial, importar un módulo.

    Nunca lanza. El registro es la traza para el log plegable de la interfaz.
    """
    degradacion, registro = _estado_resiliencia()

    try:
        resultado = consultar()
    except Exception as e:
        motivo = clasificar(e)
        detalle = f"{type(e).__name__}: {e}"
        logger.warning(f"[Árbitro] Búsqueda automática fallida ({motivo.value}): {detalle}")
        registro.append(f"⚠️ {EXPLICACION[motivo]}")
        registro.append(f"   Detalle técnico: {detalle}")
        registro.append(f"→ {MENSAJE_MANUAL}")
        return sin_designacion(motivo, liga, detalle, degradacion), registro

    registro.extend(_detallar(resultado))

    if hay_designacion(resultado):
        resultado.setdefault("degradacion", degradacion)
        resultado["mensaje_usuario"] = ""
        return resultado, registro

    # Un candidato que la política ha rechazado se cuenta en el log, con su
    # nombre y el porqué. Ahí se puede leer y contrastar; en la ficha no entra.
    descartado = str((resultado or {}).get("candidato_descartado") or "").strip()
    if descartado:
        registro.append(f"✋ Candidato descartado: «{descartado}» — sin confirmación "
                        f"oficial ni registro del partido que lo respalde.")

    motivo = Motivo.SIN_DESIGNACION
    if degradacion.get("degradada"):
        # La única fuente de pago está fuera de servicio: el partido puede tener
        # árbitro publicado y no haberlo visto nadie. Decirlo así evita que se
        # entienda como «todavía no hay designación».
        motivo = Motivo.FUERA_DE_PLAN
    detalle = str((resultado or {}).get("motivo") or "").strip()
    registro.append(f"→ {MENSAJE_MANUAL}")
    ficha = sin_designacion(motivo, liga, detalle, degradacion)
    if isinstance(resultado, dict):
        # Las evidencias descartadas se conservan: son lo que explica por qué se
        # rechazó un nombre que alguna fuente sí daba.
        if resultado.get("evidencias"):
            ficha["evidencias"] = resultado["evidencias"]
        if resultado.get("verification_link"):
            ficha["verification_link"] = resultado["verification_link"]
        if descartado:
            ficha["candidato_descartado"] = descartado
    return ficha, registro
