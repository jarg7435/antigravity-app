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
que un partido de las 16:15 en Espana se mostraria como las 14:15. Se convierte
por tanto a la zona horaria de la COMPETICION, que es la hora en la que se
anuncia el encuentro, y se devuelve tambien su nombre para poder etiquetarla en
pantalla y que nadie tenga que adivinar de que hora se habla.

Autor: Antigravity - La Gema JARG74
"""

import logging
from datetime import datetime, timedelta, timezone
from typing import Dict, Optional

logger = logging.getLogger(__name__)

# Zona horaria en la que se anuncia cada competicion.
_ZONAS = {
    "La Liga": ("Europe/Madrid", "hora peninsular"),
    "Premier League": ("Europe/London", "hora de Londres"),
    "Serie A": ("Europe/Rome", "hora de Italia"),
    "Bundesliga": ("Europe/Berlin", "hora de Alemania"),
    "Ligue 1": ("Europe/Paris", "hora de Francia"),
    "UEFA": ("Europe/Madrid", "hora peninsular"),
}
_ZONA_POR_DEFECTO = ("Europe/Madrid", "hora peninsular")

# Cuanto se busca hacia delante al preguntar por el calendario.
DIAS_VISTA = 10


def _zona(liga: str):
    from src.data.referee_database import liga_canonica
    return _ZONAS.get(liga_canonica(liga), _ZONA_POR_DEFECTO)


def _a_local(utc_iso_o_ts, liga: str) -> Optional[datetime]:
    """Pasa una marca de tiempo UTC a la hora local de la competicion."""
    from zoneinfo import ZoneInfo

    try:
        if isinstance(utc_iso_o_ts, (int, float)):
            momento = datetime.fromtimestamp(utc_iso_o_ts, tz=timezone.utc)
        else:
            texto = str(utc_iso_o_ts).replace("Z", "+00:00")
            momento = datetime.fromisoformat(texto)
            if momento.tzinfo is None:
                momento = momento.replace(tzinfo=timezone.utc)
    except (ValueError, TypeError, OSError, OverflowError) as e:
        logger.debug(f"Marca de tiempo ilegible ({utc_iso_o_ts!r}): {e}")
        return None

    try:
        local = momento.astimezone(ZoneInfo(_zona(liga)[0]))
    except Exception:
        # Sin base de datos de zonas horarias es preferible dar la hora UTC
        # que no dar nada, pero se avisa porque la hora ira corrida.
        logger.warning("Sin zona horaria disponible; se devuelve la hora UTC.")
        local = momento
    return local.replace(tzinfo=None)


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
                return {"cuando": cuando, "fuente": "football-data.org",
                        "local": mh, "visitante": ma}
    return None


def _desde_sofascore(home: str, away: str, liga: str) -> Optional[Dict]:
    try:
        from src.data.scrapers.sofascore_api import _find_event
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
          "cuando": datetime,   # sin zona, ya en hora de la competicion
          "zona": str,          # etiqueta legible: "hora peninsular"
          "fuente": str,
          "local": str,         # nombres tal y como los da la fuente, para
          "visitante": str,     # que se vea con que partido ha casado
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
            hallazgo["zona"] = _zona(liga)[1]
            logger.info(f"[calendario] {home} vs {away}: {hallazgo['cuando']} "
                        f"({hallazgo['zona']}) segun {hallazgo['fuente']}")
            return hallazgo

    logger.info(f"[calendario] Sin fecha para {home} vs {away} ({liga})")
    return None
