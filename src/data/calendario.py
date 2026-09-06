"""
Fecha real de un encuentro — La Gema JARG74.

La interfaz pedia la fecha del partido ANTES de saber que equipos se iban a
enfrentar, y la ofrecia por defecto como "hoy a las 21:00". Eso obliga a
acertarla a mano cada vez, y equivocarse tiene consecuencias: el 5 de
septiembre se analizo un Valencia - Barcelona que se jugaba el 6, con lo que la
busqueda del arbitro y la de alineaciones trabajaban sobre un dia que no era el
del partido.

Este modulo pregunta a las fuentes cuando se juega de verdad, para que la fecha
se rellene sola en cuanto se eligen los dos equipos.

SOBRE LA HORA. Los feeds dan la hora en UTC. Convertirla con la hora local del
proceso seria un error silencioso: en Streamlit Cloud el servidor va en UTC, asi
que un partido de las 16:15 peninsulares se mostraria como las 14:15.

La hora se da en CANARIAS, que es donde se usa la aplicacion, y es la que
coincide con lo que el usuario ve en SofaScore o en el movil. Se devuelve
ademas la hora de la competicion como referencia secundaria, porque los
carteles de designaciones del CTA y casi toda la prensa van en hora peninsular:
teniendo las dos delante no hay que hacer la resta mentalmente ni dudar de si
el partido es una hora antes o despues.

Autor: Antigravity - La Gema JARG74
"""

import logging
from datetime import datetime, timedelta, timezone
from typing import Dict, Optional

logger = logging.getLogger(__name__)

# Zona en la que se muestran las horas. Es la del usuario, no la del servidor.
ZONA_USUARIO = ("Atlantic/Canary", "hora canaria")

# Zona en la que se ANUNCIA cada competicion, que se conserva como referencia
# secundaria: es la que aparece en los carteles oficiales y en la prensa.
_ZONAS_COMPETICION = {
    "La Liga": ("Europe/Madrid", "peninsular"),
    "Premier League": ("Europe/London", "de Londres"),
    "Serie A": ("Europe/Rome", "de Italia"),
    "Bundesliga": ("Europe/Berlin", "de Alemania"),
    "Ligue 1": ("Europe/Paris", "de Francia"),
    "UEFA": ("Europe/Madrid", "peninsular"),
}
_ZONA_COMPETICION_POR_DEFECTO = ("Europe/Madrid", "peninsular")

# Cuanto se busca hacia delante al preguntar por el calendario.
DIAS_VISTA = 10


def _zona(liga: str = ""):
    """Zona en la que se MUESTRAN las horas. Siempre la del usuario."""
    return ZONA_USUARIO


def _zona_competicion(liga: str):
    """Zona en la que se anuncia esa competicion, para la referencia."""
    from src.data.referee_database import liga_canonica
    return _ZONAS_COMPETICION.get(liga_canonica(liga),
                                  _ZONA_COMPETICION_POR_DEFECTO)


def _a_utc(utc_iso_o_ts) -> Optional[datetime]:
    """Normaliza a datetime con zona UTC lo que devuelva la fuente."""
    try:
        if isinstance(utc_iso_o_ts, (int, float)):
            return datetime.fromtimestamp(utc_iso_o_ts, tz=timezone.utc)
        texto = str(utc_iso_o_ts).replace("Z", "+00:00")
        momento = datetime.fromisoformat(texto)
        if momento.tzinfo is None:
            momento = momento.replace(tzinfo=timezone.utc)
        return momento
    except (ValueError, TypeError, OSError, OverflowError) as e:
        logger.debug(f"Marca de tiempo ilegible ({utc_iso_o_ts!r}): {e}")
        return None


def _en_zona(momento_utc: datetime, tz_nombre: str) -> datetime:
    from zoneinfo import ZoneInfo
    try:
        return momento_utc.astimezone(ZoneInfo(tz_nombre)).replace(tzinfo=None)
    except Exception:
        # Sin base de datos de zonas horarias es preferible dar la hora UTC
        # que no dar nada, pero se avisa porque la hora ira corrida.
        logger.warning(f"Zona horaria {tz_nombre} no disponible; se da la hora UTC.")
        return momento_utc.replace(tzinfo=None)


def _a_local(utc_iso_o_ts, liga: str = "") -> Optional[datetime]:
    """Pasa una marca de tiempo UTC a la hora canaria."""
    momento = _a_utc(utc_iso_o_ts)
    if momento is None:
        return None
    return _en_zona(momento, ZONA_USUARIO[0])


def _a_hora_competicion(utc_iso_o_ts, liga: str) -> Optional[datetime]:
    """La misma marca de tiempo, en la hora en la que se anuncia el partido."""
    momento = _a_utc(utc_iso_o_ts)
    if momento is None:
        return None
    return _en_zona(momento, _zona_competicion(liga)[0])


def _casan(a: str, b: str) -> bool:
    """¿Se refieren al mismo equipo estos dos nombres?"""
    from src.data.investigador_web import _menciona_equipo, _norm
    if not a or not b:
        return False
    return _menciona_equipo(_norm(a), b) or _menciona_equipo(_norm(b), a)


def _desde_football_data(home: str, away: str, liga: str) -> Optional[Dict]:
    try:
        from src.data.football_data_org import FootballDataClient, COMPETITION_CODES
        from src.data.referee_database import liga_canonica
    except Exception:
        return None

    try:
        cliente = FootballDataClient()
        if not cliente.is_configured:
            return None
        codigo = COMPETITION_CODES.get(liga_canonica(liga)) or COMPETITION_CODES.get(liga)
        if not codigo:
            return None
        hoy = datetime.now().date()
        partidos = cliente.get_competition_matches(
            codigo,
            date_from=hoy.isoformat(),
            date_to=(hoy + timedelta(days=DIAS_VISTA)).isoformat(),
        ) or []
    except Exception as e:
        logger.debug(f"[calendario/football-data] {type(e).__name__}: {e}")
        return None

    for m in partidos:
        mh = (m.get("homeTeam") or {}).get("name", "")
        ma = (m.get("awayTeam") or {}).get("name", "")
        if _casan(mh, home) and _casan(ma, away):
            cuando = _a_local(m.get("utcDate"), liga)
            if cuando:
                return {"cuando": cuando,
                        "cuando_competicion": _a_hora_competicion(m.get("utcDate"), liga),
                        "fuente": "football-data.org",
                        "local": mh, "visitante": ma}
    return None


def _desde_sofascore(home: str, away: str, liga: str) -> Optional[Dict]:
    try:
        from src.data.scrapers.sofascore_api import _find_event
        # Sin fecha a proposito: aqui la incognita ES la fecha, asi que
        # _find_event se queda con el enfrentamiento mas proximo a hoy.
        evento = _find_event(home, away)
    except Exception as e:
        logger.debug(f"[calendario/sofascore] {type(e).__name__}: {e}")
        return None

    if not evento:
        return None
    cuando = _a_local(evento.get("startTimestamp"), liga)
    if not cuando:
        return None
    return {
        "cuando": cuando,
        "cuando_competicion": _a_hora_competicion(evento.get("startTimestamp"), liga),
        "fuente": "SofaScore",
        "local": (evento.get("homeTeam") or {}).get("name", ""),
        "visitante": (evento.get("awayTeam") or {}).get("name", ""),
    }


def fecha_del_partido(home: str, away: str, liga: str = "") -> Optional[Dict]:
    """
    Cuando se juega este partido, segun las fuentes.

    Devuelve None si no se encuentra, que es la respuesta honesta: mas vale que
    el usuario ponga la fecha a mano que rellenarsela con una inventada.

    Returns:
        {
          "cuando": datetime,             # sin zona, ya en hora canaria
          "zona": str,                    # "hora canaria"
          "cuando_competicion": datetime, # la misma, en hora de la competicion
          "zona_competicion": str,        # "peninsular", "de Londres"...
          "referencia": str,              # "16:15 peninsular", ya formateado
          "fuente": str,
          "local": str,                   # nombres tal y como los da la fuente,
          "visitante": str,               # para ver con que partido ha casado
        }
    """
    if not home or not away:
        return None

    for buscar in (_desde_football_data, _desde_sofascore):
        try:
            hallazgo = buscar(home, away, liga)
        except Exception as e:
            logger.debug(f"[calendario] {buscar.__name__}: {type(e).__name__}: {e}")
            hallazgo = None
        if hallazgo:
            hallazgo["zona"] = ZONA_USUARIO[1]
            hallazgo["zona_competicion"] = _zona_competicion(liga)[1]

            # La referencia solo se escribe si de verdad aporta algo. Cuando
            # las dos horas coinciden —una competicion que ya se anuncia en la
            # zona del usuario— repetirla seria ruido.
            otra = hallazgo.get("cuando_competicion")
            hallazgo["referencia"] = ""
            if otra and otra != hallazgo["cuando"]:
                hallazgo["referencia"] = (f"{otra:%H:%M} "
                                          f"{hallazgo['zona_competicion']}")

            logger.info(f"[calendario] {home} vs {away}: {hallazgo['cuando']} "
                        f"({hallazgo['zona']}"
                        + (f", {hallazgo['referencia']}" if hallazgo["referencia"] else "")
                        + f") segun {hallazgo['fuente']}")
            return hallazgo

    logger.info(f"[calendario] Sin fecha para {home} vs {away} ({liga})")
    return None
