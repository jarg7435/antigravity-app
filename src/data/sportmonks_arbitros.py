"""
Conector de designaciones arbitrales de Sportmonks — La Gema JARG74.

Vía complementaria para la cascada de árbitros. Sportmonks ya estaba integrado
—hay cliente, la llave está en los secrets y el panel lo daba por OK— pero
ninguna de las dos cascadas lo consultaba nunca. Este módulo lo conecta.

LO QUE HAY QUE SABER ANTES DE ESPERAR NADA DE ÉL
------------------------------------------------
El plan contratado cubre CUATRO competiciones, comprobado contra la API:

    271   Superliga (Dinamarca)
    501   Premiership (Escocia)
    513   Premiership Play-Offs
    1659  Superliga Play-offs

No incluye LaLiga, Premier, Bundesliga, Serie A ni Ligue 1. Para un partido
español esta fuente no puede aportar nada, y por eso el módulo pregunta primero
qué cubre el plan y se aparta en silencio cuando la liga no entra: gastar una
petición para que conteste vacío solo sirve para consumir cuota y alargar la
búsqueda del árbitro.

Donde sí cubre, el dato es de primera mano. Cada fixture trae sus cuatro
oficiales y el principal es el de `type_id` 6 (los otros tres son asistentes y
cuarto árbitro). Verificado en vivo:

    Rangers - St. Mirren     -> Don Robertson
    St. Johnstone - Celtic   -> Michael MacDermid

Por eso lo que devuelve entra como VERIFICADO, al mismo nivel que
football-data.org: es la designación del propio partido, no un indicio de
prensa.

Uso:

    from src.data import sportmonks_arbitros as sm
    if sm.cubre("Scottish Premiership (Escocia)"):
        r = sm.buscar_arbitro("Rangers", "St. Mirren", fecha, "Scottish Premiership")

Autor: Antigravity - La Gema JARG74
"""

import logging
from datetime import date, datetime, timedelta
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)


# El oficial principal del partido. Los otros tres que devuelve la API son los
# dos asistentes y el cuarto arbitro, que no interesan para el pronostico.
TIPO_ARBITRO_PRINCIPAL = 6

# Dias alrededor de la fecha del partido en los que se busca el fixture. Uno
# basta para absorber husos horarios sin invitar al partido de la vuelta.
MARGEN_DIAS = 1

# Ligas que cubre el plan, leidas una vez por proceso. None = aun sin preguntar.
_LIGAS_CUBIERTAS: Optional[Dict[str, int]] = None


def _cliente():
    from src.data.api_manager import SportmonksClient
    return SportmonksClient()


def _tokens(nombre: str) -> set:
    """Palabras utiles de un nombre de liga, para cotejarlo con el del plan."""
    from src.data.resultados_auto import _norm
    limpio = "".join(c if c.isalnum() or c.isspace() else " " for c in _norm(nombre))
    ruido = {"liga", "league", "division", "primera", "the"}
    return {p for p in limpio.split() if len(p) >= 3 and p not in ruido}


def ligas_cubiertas(refrescar: bool = False) -> Dict[str, int]:
    """
    Competiciones a las que da acceso el plan, como {nombre: id}.

    Se pregunta a la API en lugar de codificarlo aquí: el plan puede cambiar, y
    una lista escrita a mano se queda vieja sin avisar. El resultado se guarda
    para el resto del proceso porque no cambia entre consultas.
    """
    global _LIGAS_CUBIERTAS
    if _LIGAS_CUBIERTAS is not None and not refrescar:
        return _LIGAS_CUBIERTAS

    ligas: Dict[str, int] = {}
    try:
        datos = _cliente()._get("leagues", {"per_page": 100})
        for l in (datos or []):
            if isinstance(l, dict) and l.get("name") and l.get("id"):
                ligas[str(l["name"])] = int(l["id"])
    except Exception as e:
        logger.error(f"[Sportmonks] No se pudo leer la cobertura del plan: {e}")

    _LIGAS_CUBIERTAS = ligas
    if ligas:
        logger.info("[Sportmonks] El plan cubre: %s", ", ".join(ligas))
    return ligas


def cubre(liga: str) -> Optional[int]:
    """
    Id de la competición si el plan la cubre, o None.

    El cotejo va por palabras porque los nombres no coinciden literalmente: la
    aplicación dice "Scottish Premiership (Escocia)" y Sportmonks dice
    "Premiership" a secas. Entre varias candidatas gana la más parecida en
    numero de palabras, y las eliminatorias quedan al final para que
    "Premiership Play-Offs" no le gane a "Premiership" en un partido de liga
    regular.
    """
    if not liga:
        return None

    pedidas = _tokens(liga)
    if not pedidas:
        return None

    candidatas = []
    for nombre, ident in (ligas_cubiertas() or {}).items():
        suyas = _tokens(nombre)
        if not suyas:
            continue
        if suyas <= pedidas or pedidas <= suyas:
            eliminatoria = any(p in nombre.lower() for p in ("play", "off"))
            candidatas.append((eliminatoria, abs(len(suyas) - len(pedidas)), ident, nombre))

    if not candidatas:
        return None
    candidatas.sort()
    logger.info("[Sportmonks] '%s' -> '%s' (id %s)", liga, candidatas[0][3], candidatas[0][2])
    return candidatas[0][2]


def _a_fecha(valor) -> Optional[date]:
    if isinstance(valor, datetime):
        return valor.date()
    if isinstance(valor, date):
        return valor
    if not valor:
        return None
    try:
        return datetime.fromisoformat(str(valor)[:19].replace("Z", "")).date()
    except (ValueError, TypeError):
        try:
            return datetime.fromisoformat(str(valor)[:10]).date()
        except (ValueError, TypeError):
            return None


def _arbitro_principal(fixture: dict) -> Optional[str]:
    """Nombre del colegiado principal de un fixture, o None."""
    for oficial in (fixture.get("referees") or []):
        if oficial.get("type_id") != TIPO_ARBITRO_PRINCIPAL:
            continue
        persona = oficial.get("referee") or {}
        nombre = persona.get("display_name") or persona.get("name") or ""
        if nombre.strip():
            return nombre.strip()
    return None


def _es_nuestro_partido(fixture: dict, home: str, away: str) -> bool:
    """
    ¿Este fixture enfrenta a nuestros dos equipos?

    Se comprueba que los DOS aparezcan entre los participantes. No se mira quién
    es local: para saber quién pita da igual el orden, y exigirlo descartaría el
    partido cuando la API devuelve los participantes en otro orden, cosa que
    hace.
    """
    from src.data.resultados_auto import mismo_equipo

    nombres = [p.get("name", "") for p in (fixture.get("participants") or [])
               if isinstance(p, dict)]
    if len(nombres) < 2:
        return False
    return (any(mismo_equipo(home, n) for n in nombres)
            and any(mismo_equipo(away, n) for n in nombres))


def buscar_arbitro(home: str, away: str, fecha, liga: str = "") -> Optional[Dict]:
    """
    Designación del partido según Sportmonks, o None.

    Devuelve None sin tocar la red cuando el plan no cubre la competición, que
    es el caso de todos los partidos españoles.
    """
    liga_id = cubre(liga)
    if liga_id is None:
        logger.info("[Sportmonks] '%s' fuera del plan; no se consulta.", liga)
        return None

    f = _a_fecha(fecha)
    if f is None:
        return None

    desde = (f - timedelta(days=MARGEN_DIAS)).isoformat()
    hasta = (f + timedelta(days=MARGEN_DIAS)).isoformat()

    try:
        fixtures = _cliente().get_fixtures_con_arbitros(desde, hasta, liga_id)
    except Exception as e:
        logger.error(f"[Sportmonks] Error consultando fixtures: {e}")
        return None

    for fx in (fixtures or []):
        if not _es_nuestro_partido(fx, home, away):
            continue
        nombre = _arbitro_principal(fx)
        if not nombre:
            # El partido esta, pero aun sin designar. Es informacion util: no
            # tiene sentido seguir preguntando a esta fuente por el.
            logger.info("[Sportmonks] Partido encontrado sin designacion todavia.")
            return None

        from src.models.base import RefereeStrictness
        return {
            "name": nombre,
            "strictness": RefereeStrictness.MEDIUM,
            "avg_cards": 4.0,
            "estado": "VERIFICADO",
            "motivo": "Confirmado por Sportmonks (designación oficial del partido).",
            "source": "Sportmonks (oficial)",
            "verification_link": "https://www.sofascore.com",
            "_is_fallback": False,
            "confidence": "HIGH",
            "fixture_id": fx.get("id"),
        }

    return None
