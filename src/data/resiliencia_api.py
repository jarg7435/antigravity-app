"""
Cortacircuitos de API-Football — La Gema JARG74.

API-Football es la única fuente de pago de la aplicación, y por tanto la única
que se puede caer por motivos ajenos a la red: la suscripción caduca, o el plan
agota su cuota diaria. Cuando eso pasa, la API no deja de existir: sigue
contestando, pero contesta errores. Sin nadie que lleve la cuenta, cada consulta
del árbitro volvía a intentarlo, esperaba su timeout de 15 segundos y fallaba
igual, con lo que la búsqueda automática se eternizaba y acababa en la zona de
emergencia manual aunque SofaScore y football-data.org estuvieran perfectamente.

Este módulo lleva esa cuenta. Registra la última avería, la clasifica y decide
durante cuánto tiempo no merece la pena volver a llamar:

    avería          qué la provoca                        espera
    -------------   -----------------------------------   ---------------------
    SUSCRIPCION     token inválido, plan caducado, "no     6 h (necesita que
                    estás suscrito a esta API"             alguien renueve)
    CUOTA           límite de peticiones agotado           hasta el reset diario
                                                           (medianoche UTC)
    TRANSITORIA     timeout, corte de red, 5xx             5 min, y solo tras
                                                           3 fallos seguidos

Mientras el circuito está abierto, `disponible()` devuelve False y la cascada de
fuentes salta API-Football sin gastar ni una petición ni un segundo de espera:
la consulta se desvía sola a SofaScore, football-data.org y los scrapers de
prensa. La aplicación sigue funcionando en modo degradado, y `resumen()` da el
texto con el que la interfaz lo explica en lugar de un ❌ mudo.

Un acierto cierra el circuito de inmediato, así que en cuanto la suscripción se
renueva la API vuelve a entrar en la cascada sin reiniciar nada.

Autor: Antigravity - La Gema JARG74
"""

import logging
from datetime import datetime, timedelta, timezone
from enum import Enum
from threading import RLock
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)


class Averia(str, Enum):
    """Naturaleza del fallo, que determina cuánto se espera antes de reintentar."""

    SUSCRIPCION = "suscripcion"
    CUOTA = "cuota"
    TRANSITORIA = "transitoria"


# Cuánto se deja de llamar a la API tras cada tipo de avería.
# La cuota es la excepción: no se espera un rato fijo, sino al reset diario.
_ESPERA = {
    Averia.SUSCRIPCION: timedelta(hours=6),
    Averia.TRANSITORIA: timedelta(minutes=5),
}

# Fallos transitorios seguidos que se toleran antes de abrir el circuito. Un
# timeout suelto no significa que la API esté caída, y abrir por uno solo
# apagaría la fuente principal por un hipo de la red.
TOLERANCIA_TRANSITORIA = 3

# Texto que ve el usuario para cada avería. Explica también qué hace el sistema,
# porque el aviso importante no es que la API falle, sino que se sigue operando.
_EXPLICACION = {
    Averia.SUSCRIPCION: (
        "API-Football no acepta la llave (suscripción caducada o plan no "
        "activo). Renuévala en api-football.com y actualiza API_FOOTBALL_KEY "
        "en los secrets."
    ),
    Averia.CUOTA: (
        "API-Football ha agotado la cuota de peticiones del plan. Se restablece "
        "sola en el reset diario."
    ),
    Averia.TRANSITORIA: (
        "API-Football no responde (timeout o error del servidor). Suele ser "
        "pasajero."
    ),
}

_DESVIO = (
    "La consulta se desvía automáticamente a las fuentes secundarias "
    "(SofaScore, football-data.org y la prensa deportiva)."
)


class _Estado:
    """Estado del cortacircuitos. Instancia única por proceso."""

    def __init__(self):
        self._lock = RLock()
        self.averia: Optional[Averia] = None
        self.detalle: str = ""
        self.desde: Optional[datetime] = None
        self.hasta: Optional[datetime] = None
        self.fallos_transitorios: int = 0
        self.ultimo_exito: Optional[datetime] = None


_ESTADO = _Estado()


def _ahora() -> datetime:
    return datetime.now(timezone.utc)


def _proximo_reset_diario(desde: datetime) -> datetime:
    """Medianoche UTC siguiente, que es cuando API-Football repone la cuota."""
    manana = (desde + timedelta(days=1)).date()
    return datetime(manana.year, manana.month, manana.day, tzinfo=timezone.utc)


# =============================================================================
# CLASIFICACIÓN
# =============================================================================

def clasificar_respuesta(status_code: Optional[int] = None,
                         errors: Any = None,
                         cuerpo: Any = None) -> Optional[Averia]:
    """
    Traduce una respuesta de API-Football a una avería, o None si no lo es.

    API-Football contesta casi siempre con HTTP 200 y mete el problema real en
    el campo "errors", así que mirar solo el código de estado no basta.

    Ojo con los errores de tipo "plan": los devuelve para consultas que el plan
    gratuito no cubre (una fecha fuera de su ventana, la temporada actual), y
    eso NO es una avería. Es una limitación por consulta que `cascada.py` ya
    conoce y evita; abrir el circuito por ella apagaría la API entera por una
    petición mal dirigida.
    """
    claves = set()
    if isinstance(errors, dict):
        claves = {str(k).lower() for k in errors.keys()}
    elif isinstance(errors, str) and errors.strip():
        claves = {"_texto"}

    texto = " ".join(str(v).lower() for v in errors.values()) if isinstance(errors, dict) else str(errors or "").lower()
    if isinstance(cuerpo, dict):
        texto += " " + str(cuerpo.get("message", "")).lower()

    # Cuota agotada: la API lo dice por el campo "requests" o por un 429.
    if claves & {"requests", "ratelimit", "rate_limit"} or status_code == 429:
        return Averia.CUOTA
    if "request limit" in texto or "too many requests" in texto:
        return Averia.CUOTA

    # Suscripción: token inválido, cuenta no suscrita, acceso denegado.
    if claves & {"token", "subscription", "access", "auth"}:
        return Averia.SUSCRIPCION
    if status_code in (401, 403):
        return Averia.SUSCRIPCION
    if "not subscribed" in texto or "invalid api key" in texto or "expired" in texto:
        return Averia.SUSCRIPCION

    # Limitación por consulta, no avería: la cascada ya la esquiva.
    if claves & {"plan", "season", "date", "bug", "_texto"}:
        return None

    # 499 es el timeout que declara la propia API-Football; el resto de 5xx son
    # caídas suyas. Ninguna dice nada de la suscripción, así que son pasajeras.
    if status_code and (status_code == 499 or status_code >= 500):
        return Averia.TRANSITORIA

    # Un 200 sin errores y sin cuerpo es la "sin respuesta" que veía el panel:
    # la API contesta vacío. No se puede distinguir de una caída suya.
    if status_code == 200 and cuerpo is not None and not cuerpo:
        return Averia.TRANSITORIA

    if status_code and status_code != 200:
        return Averia.TRANSITORIA

    return None


# =============================================================================
# REGISTRO
# =============================================================================

def registrar_averia(tipo: Averia, detalle: str = "") -> bool:
    """
    Anota un fallo. Devuelve True si el circuito queda abierto.

    Las averías transitorias necesitan repetirse TOLERANCIA_TRANSITORIA veces
    seguidas para abrirlo; las de cuota y suscripción lo abren a la primera,
    porque el siguiente intento va a fallar igual con total seguridad.
    """
    ahora = _ahora()
    with _ESTADO._lock:
        if tipo == Averia.TRANSITORIA:
            _ESTADO.fallos_transitorios += 1
            if _ESTADO.fallos_transitorios < TOLERANCIA_TRANSITORIA:
                logger.warning(
                    "[Resiliencia] API-Football falló (%d/%d): %s",
                    _ESTADO.fallos_transitorios, TOLERANCIA_TRANSITORIA, detalle[:120]
                )
                return False
            hasta = ahora + _ESPERA[Averia.TRANSITORIA]
        elif tipo == Averia.CUOTA:
            hasta = _proximo_reset_diario(ahora)
        else:
            hasta = ahora + _ESPERA[Averia.SUSCRIPCION]

        _ESTADO.averia = tipo
        _ESTADO.detalle = detalle
        _ESTADO.desde = ahora
        _ESTADO.hasta = hasta

    logger.error(
        "[Resiliencia] API-Football fuera de servicio (%s) hasta %s — %s. %s",
        tipo.value, hasta.isoformat(timespec="minutes"), detalle[:120], _DESVIO
    )
    return True


def registrar_averia_por_excepcion(exc: BaseException) -> bool:
    """Anota un fallo de red (timeout, conexión, respuesta ilegible)."""
    return registrar_averia(
        Averia.TRANSITORIA, f"{type(exc).__name__}: {str(exc)[:120]}"
    )


def registrar_exito() -> None:
    """
    Anota una respuesta buena: cierra el circuito y borra la avería.

    Es lo que devuelve la API a la cascada en cuanto se renueva la suscripción,
    sin tener que reiniciar la aplicación.
    """
    with _ESTADO._lock:
        recuperada = _ESTADO.averia is not None
        _ESTADO.averia = None
        _ESTADO.detalle = ""
        _ESTADO.desde = None
        _ESTADO.hasta = None
        _ESTADO.fallos_transitorios = 0
        _ESTADO.ultimo_exito = _ahora()
    if recuperada:
        logger.info("[Resiliencia] API-Football vuelve a responder; circuito cerrado.")


def reiniciar() -> None:
    """Borra todo el estado. Para los tests y para el reseteo manual."""
    with _ESTADO._lock:
        _ESTADO.averia = None
        _ESTADO.detalle = ""
        _ESTADO.desde = None
        _ESTADO.hasta = None
        _ESTADO.fallos_transitorios = 0
        _ESTADO.ultimo_exito = None


# =============================================================================
# CONSULTA
# =============================================================================

def disponible() -> bool:
    """
    ¿Merece la pena llamar a API-Football ahora mismo?

    False mientras el circuito esté abierto. La espera se comprueba aquí, así
    que el circuito se cierra solo al vencer sin que nadie tenga que barrerlo.
    """
    with _ESTADO._lock:
        if _ESTADO.averia is None:
            return True
        if _ESTADO.hasta and _ahora() >= _ESTADO.hasta:
            _ESTADO.averia = None
            _ESTADO.detalle = ""
            _ESTADO.desde = None
            _ESTADO.hasta = None
            _ESTADO.fallos_transitorios = 0
            logger.info("[Resiliencia] Vencida la espera; se vuelve a probar API-Football.")
            return True
        return False


def averia_actual() -> Optional[Averia]:
    """Avería vigente, o None si la API está operativa."""
    return None if disponible() else _ESTADO.averia


def motivo() -> Optional[str]:
    """Explicación corta de por qué no se está usando API-Football."""
    tipo = averia_actual()
    if tipo is None:
        return None
    return _EXPLICACION.get(tipo, "API-Football no está disponible.")


def resumen() -> Dict[str, Any]:
    """
    Estado completo, para el panel de diagnóstico y los logs de búsqueda.

    Devuelve siempre las mismas claves, con `degradada` como bandera principal.
    """
    tipo = averia_actual()
    with _ESTADO._lock:
        return {
            "degradada": tipo is not None,
            "averia": tipo.value if tipo else None,
            "motivo": _EXPLICACION.get(tipo) if tipo else None,
            "desvio": _DESVIO if tipo else None,
            "detalle": _ESTADO.detalle if tipo else "",
            "desde": _ESTADO.desde.isoformat(timespec="seconds") if tipo and _ESTADO.desde else None,
            "hasta": _ESTADO.hasta.isoformat(timespec="seconds") if tipo and _ESTADO.hasta else None,
            "ultimo_exito": (_ESTADO.ultimo_exito.isoformat(timespec="seconds")
                             if _ESTADO.ultimo_exito else None),
        }


def texto_estado() -> str:
    """Una línea para la interfaz, con el desvío incluido cuando toca."""
    tipo = averia_actual()
    if tipo is None:
        return "API-Football operativa."
    return f"{_EXPLICACION[tipo]} {_DESVIO}"
