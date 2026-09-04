"""
Política de la cascada de fuentes — La Gema JARG74.

Decide en qué orden se consultan las fuentes de datos según el tipo de consulta,
y si merece la pena consultar API-Football siquiera. La regla vive aquí, en un
solo sitio, en lugar de repartida por los módulos que la aplican.

El motivo son los límites del plan gratuito de API-Football, comprobados uno a
uno contra la API real:

    consulta                                   resultado
    ----------------------------------------   ------------------------------
    live=all                                   OK (130 partidos)
    date dentro de hoy±1, SIN liga ni season   OK (454 partidos)
    date + league sin season                   "The Season field is required"
    date fuera de hoy±1 (pasada o futura)      "Free plans do not have access
                                                to this date, try from ..."
    league + season entre 2022 y 2024          OK (38 partidos)
    league + season actual                     "Free plans do not have access
                                                to this season"
    parámetro next                             "Free plans do not have access
                                                to the Next parameter"

De ahí salen las tres reglas:

- EN VIVO: API-Football es la mejor fuente y no tiene restricción, así que va
  primera. football-data.org no ofrece un feed en vivo equivalente.
- PRÓXIMO (hoy y calendario futuro): football-data.org y los scrapers primero.
  API-Football queda de respaldo y solo se intenta si la fecha cae dentro de su
  ventana; fuera de ella no puede responder y la petición se tiraría a la
  basura, que en un plan de 100 al día importa.
- HISTÓRICO: API-Football primero, que es donde su archivo rinde. Debe
  consultarse por liga y temporada, nunca por fecha: la ventana de fechas
  bloquea también el pasado.

Autor: Antigravity - La Gema JARG74
"""

from datetime import date, datetime, timedelta
from enum import Enum
from typing import List, Optional, Union

# Ventana de fechas que acepta el plan gratuito, en días alrededor de hoy.
VENTANA_DIAS = 1

# Temporadas del archivo histórico accesibles en el plan gratuito (inclusive).
TEMPORADA_MIN = 2022
TEMPORADA_MAX = 2024

# Identificadores de fuente usados en los órdenes de prioridad.
API_FOOTBALL = "api_football"
FOOTBALL_DATA = "football_data"
SCRAPERS = "scrapers"


class TipoConsulta(str, Enum):
    """Naturaleza de la consulta, que determina el orden de fuentes."""

    EN_VIVO = "en_vivo"
    PROXIMO = "proximo"      # hoy o cualquier fecha futura
    HISTORICO = "historico"  # cualquier fecha pasada


_ORDEN = {
    TipoConsulta.EN_VIVO:   [API_FOOTBALL, FOOTBALL_DATA, SCRAPERS],
    TipoConsulta.PROXIMO:   [FOOTBALL_DATA, SCRAPERS, API_FOOTBALL],
    TipoConsulta.HISTORICO: [API_FOOTBALL, FOOTBALL_DATA, SCRAPERS],
}


def _a_fecha(valor: Union[str, date, datetime, None]) -> Optional[date]:
    """Normaliza a date lo que llegue: date, datetime, ISO o None."""
    if valor is None:
        return None
    if isinstance(valor, datetime):
        return valor.date()
    if isinstance(valor, date):
        return valor
    try:
        return datetime.fromisoformat(str(valor)[:10]).date()
    except (ValueError, TypeError):
        return None


def clasificar(fecha: Union[str, date, datetime, None] = None,
               en_vivo: bool = False) -> TipoConsulta:
    """
    Tipo de consulta a partir de su fecha.

    Una fecha ausente o ilegible se trata como PROXIMO, que es el caso
    conservador: nunca gasta cuota de API-Football por defecto.
    """
    if en_vivo:
        return TipoConsulta.EN_VIVO

    f = _a_fecha(fecha)
    if f is None:
        return TipoConsulta.PROXIMO

    return TipoConsulta.HISTORICO if f < date.today() else TipoConsulta.PROXIMO


def orden_de_fuentes(tipo: TipoConsulta) -> List[str]:
    """Fuentes a consultar, de mayor a menor prioridad."""
    return list(_ORDEN.get(tipo, _ORDEN[TipoConsulta.PROXIMO]))


def api_football_puede_responder(tipo: TipoConsulta,
                                 fecha: Union[str, date, datetime, None] = None,
                                 temporada: Optional[int] = None) -> bool:
    """
    ¿Tiene sentido gastar una petición de API-Football en esta consulta?

    Devuelve False cuando el plan gratuito la va a rechazar igualmente, para no
    gastar cuota en una llamada condenada a fallar.
    """
    if tipo == TipoConsulta.EN_VIVO:
        return True

    if temporada is not None:
        return TEMPORADA_MIN <= int(temporada) <= TEMPORADA_MAX

    f = _a_fecha(fecha)
    if f is None:
        # Sin fecha no se puede acotar; se asume que no, para no arriesgar cuota.
        return False

    hoy = date.today()
    return abs((f - hoy).days) <= VENTANA_DIAS


def describe(tipo: TipoConsulta) -> str:
    """Texto corto del orden aplicado, para los mensajes de diagnóstico."""
    return " > ".join(orden_de_fuentes(tipo))
