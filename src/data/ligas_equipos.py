"""
Quien juega en la maxima categoria de cada liga — La Gema JARG74.

Fuente unica de verdad sobre la COMPOSICION de cada competicion, igual que
plantillas.py lo es sobre la composicion de cada club. Existe porque los
listados vivian escritos a mano dentro de mock_provider._init_teams(), con un
comentario "2025-26" al lado: el desplegable seguia ofreciendo Girona, Mallorca
y Real Oviedo, que ya no estan en Primera, y no ofrecia a los ascendidos.

Una lista escrita a mano caduca cada mes de junio sin avisar. Aqui el reparto
es otro:

  1. data/equipos_ligas.json guarda la foto de la temporada, con el nombre
     interno, el nombre oficial y el id de football-data.org de cada club.
  2. Si la temporada del fichero ya no es la vigente, se pide la nueva a
     football-data.org, se reescribe el fichero y se sigue. El cambio de
     temporada se resuelve solo, sin tocar codigo.
  3. Si no hay red (o el plan gratuito dice basta), se sirve lo que haya en el
     fichero avisando de que esta caducado. Es peor que el dato bueno y mejor
     que un desplegable vacio.

Uso tipico:

    from src.data import ligas_equipos
    ligas_equipos.equipos_de("La Liga")          # -> ["Alavés", "Athletic Club", ...]
    ligas_equipos.id_oficial("Napoles")          # -> 113
    ligas_equipos.refrescar("La Liga")           # fuerza la consulta

Autor: Antigravity - La Gema JARG74
"""

import json
import logging
import re
import threading
import unicodedata
from datetime import date
from pathlib import Path
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)

# El fichero se localiza desde este modulo y no desde el directorio de trabajo:
# la app se lanza tanto con `streamlit run app/main.py` como desde la raiz, y
# una ruta relativa fallaba en uno de los dos casos.
RUTA_CONFIG = Path(__file__).resolve().parents[2] / "data" / "equipos_ligas.json"

# Ligas con fuente viva verificada en el plan gratuito de football-data.org
# (competitions/{codigo}/teams?season=YYYY). Las demas siguen sirviendose desde
# src/logic/european_teams.py, que no tiene fuente que las refresque.
LIGAS_DINAMICAS: Dict[str, str] = {
    "La Liga":        "PD",
    "Premier League": "PL",
    "Bundesliga":     "BL1",
    "Serie A":        "SA",
    "Ligue 1":        "FL1",
    "Eredivisie":     "DED",
    "Primeira Liga":  "PPL",
}

# Mes a partir del cual manda la temporada siguiente. Las cinco grandes
# arrancan entre el 15 de agosto y el 1 de septiembre, y football-data.org
# publica la plantilla de la temporada nueva desde principios de julio.
MES_INICIO_TEMPORADA = 7

# Nombre interno de cada club, indexado por su id en football-data.org.
#
# El id es la clave y no el nombre a proposito: la API cambia la denominacion
# ("Barça", "FC Barcelona"), el id no. Y el nombre interno tiene que ser
# EXACTAMENTE el que ya usan el resto de modulos (los ratings de
# mock_provider, los slugs de besoccer_scraper, el mapa de ciudades de
# external_analyst), porque todos ellos indexan por nombre.
#
# Un club que no figure aqui se nombra con lo que devuelva la API. No es un
# error: es lo que permite que un ascendido aparezca sin tocar este fichero.
_NOMBRE_POR_ID: Dict[int, str] = {
    # --- La Liga (PD) ---
    77: "Athletic Club", 78: "Atletico Madrid", 79: "Osasuna", 80: "Espanyol",
    81: "FC Barcelona", 82: "Getafe", 84: "Málaga", 86: "Real Madrid",
    87: "Rayo Vallecano", 88: "Levante", 90: "Real Betis",
    92: "Real Sociedad", 94: "Villarreal", 95: "Valencia", 263: "Alavés",
    285: "Elche", 558: "Celta de Vigo", 559: "Sevilla FC",
    560: "Deportivo La Coruña", 5335: "Racing de Santander",
    # Descendidos que conservan nombre interno por si vuelven a subir.
    298: "Girona", 89: "Mallorca", 1048: "Real Oviedo",

    # --- Premier League (PL) ---
    57: "Arsenal", 58: "Aston Villa", 61: "Chelsea", 62: "Everton",
    63: "Fulham", 64: "Liverpool", 65: "Manchester City",
    66: "Manchester Utd", 67: "Newcastle", 71: "Sunderland",
    73: "Tottenham", 322: "Hull City", 341: "Leeds Utd", 349: "Ipswich Town",
    351: "Nottingham Forest", 354: "Crystal Palace", 397: "Brighton",
    402: "Brentford", 1044: "Bournemouth", 1076: "Coventry City",
    # Descendidos.
    76: "Wolves", 563: "West Ham", 328: "Burnley",

    # --- Serie A (SA) ---
    98: "AC Milan", 99: "Fiorentina", 100: "AS Roma", 102: "Atalanta",
    103: "Bolonia", 104: "Cagliari", 107: "Genoa", 108: "Inter Milan",
    109: "Juventus", 110: "Lazio", 112: "Parma", 113: "Napoles",
    115: "Udinese", 454: "Venezia", 470: "Frosinone", 471: "Sassuolo",
    586: "Torino", 5890: "Lecce", 5911: "Monza", 7397: "Como",

    # --- Bundesliga (BL1) ---
    1: "Koln", 2: "Hoffenheim", 3: "Bayer Leverkusen", 4: "Dortmund",
    5: "Bayern Munich", 6: "Schalke 04", 7: "Hamburgo", 10: "Stuttgart",
    12: "Werder Bremen", 15: "Mainz 05", 16: "Augsburg", 17: "Freiburg",
    18: "Gladbach", 19: "Frankfurt", 28: "Union Berlin", 29: "Paderborn",
    719: "Elversberg", 721: "RB Leipzig",

    # --- Ligue 1 (FL1) ---
    511: "Toulouse", 512: "Brest", 516: "Marseille", 519: "Auxerre",
    521: "Lille", 522: "Nice", 523: "Lyon", 524: "PSG", 525: "Lorient",
    529: "Rennes", 531: "Troyes", 532: "Angers", 533: "Le Havre",
    535: "Le Mans", 546: "Lens", 548: "Monaco", 576: "Strasbourg",
    1045: "Paris FC",

    # --- Eredivisie (DED) ---
    666: "Twente", 670: "Excelsior", 672: "Willem II", 673: "Heerenveen",
    674: "PSV", 675: "Feyenoord", 676: "Utrecht", 677: "Groningen",
    678: "Ajax", 680: "ADO Den Haag", 682: "AZ Alkmaar", 684: "PEC Zwolle",
    718: "Go Ahead Eagles", 1909: "Cambuur", 1912: "Telstar",
    1915: "NEC Nijmegen", 1920: "Fortuna Sittard", 6806: "Sparta Rotterdam",

    # --- Primeira Liga (PPL) ---
    496: "Rio Ave", 498: "Sporting CP", 503: "FC Porto", 582: "Estoril",
    583: "Moreirense", 712: "Arouca", 1903: "Benfica", 5527: "Academico de Viseu",
    5529: "Nacional", 5530: "Santa Clara", 5531: "Famalicao",
    5533: "Gil Vicente", 5543: "Vitoria SC", 5575: "Maritimo",
    5613: "Braga", 6618: "Casa Pia", 7822: "Alverca", 9136: "Estrela da Amadora",
}

_LOCK = threading.Lock()
_CONFIG: Optional[dict] = None
# Ligas ya intentadas en esta sesion, para no repetir la consulta (ni el fallo)
# en cada repintado de Streamlit.
_REFRESCADAS: set = set()


# =============================================================================
# Temporada
# =============================================================================

def temporada_actual(hoy: Optional[date] = None) -> int:
    """
    Año de INICIO de la temporada en curso: 2026 para la 2026-27.

    Es el mismo criterio que usa football-data.org en el parametro `season`.
    """
    hoy = hoy or date.today()
    return hoy.year if hoy.month >= MES_INICIO_TEMPORADA else hoy.year - 1


def etiqueta_temporada(inicio: Optional[int] = None) -> str:
    """2026 -> "2026-27"."""
    inicio = temporada_actual() if inicio is None else int(inicio)
    return f"{inicio}-{str(inicio + 1)[-2:]}"


# =============================================================================
# Normalizacion de nombres de liga
# =============================================================================

def _sin_acentos(texto: str) -> str:
    return "".join(
        c for c in unicodedata.normalize("NFD", str(texto))
        if unicodedata.category(c) != "Mn"
    )


def _norm(texto: str) -> str:
    t = _sin_acentos(texto).lower()
    t = re.sub(r"[^a-z0-9 ]+", " ", t)
    return re.sub(r"\s+", " ", t).strip()


def nombre_interno_liga(liga: str) -> Optional[str]:
    """
    Etiqueta de la interfaz -> nombre interno de la liga.

    "La Liga (España)" y "la liga" se resuelven igual; lo que no sea una de las
    ligas con fuente viva devuelve None.
    """
    if not liga:
        return None
    bruto = str(liga).split("(")[0].strip()
    objetivo = _norm(bruto)
    for interno in LIGAS_DINAMICAS:
        if _norm(interno) == objetivo:
            return interno
    return None


def ligas_cubiertas() -> List[str]:
    """Ligas con listado dinamico, en el orden en que se declararon."""
    return list(LIGAS_DINAMICAS)


# =============================================================================
# Fichero de configuracion
# =============================================================================

def _config_vacia() -> dict:
    return {"temporada_inicio": 0, "temporada": "", "fuente": "", "ligas": {}}


def _cargar_config(recargar: bool = False) -> dict:
    global _CONFIG
    with _LOCK:
        if _CONFIG is not None and not recargar:
            return _CONFIG
        try:
            with open(RUTA_CONFIG, encoding="utf-8") as f:
                datos = json.load(f)
            if not isinstance(datos.get("ligas"), dict):
                raise ValueError("falta el bloque 'ligas'")
            _CONFIG = datos
        except FileNotFoundError:
            logger.warning(f"No hay listado de equipos en {RUTA_CONFIG}; "
                           f"se intentara pedirlo a football-data.org")
            _CONFIG = _config_vacia()
        except Exception as e:
            logger.error(f"Listado de equipos ilegible ({RUTA_CONFIG}): {e}")
            _CONFIG = _config_vacia()
        return _CONFIG


def _guardar_config(config: dict) -> bool:
    """
    Escribe el fichero. Devuelve si lo consiguio.

    En Streamlit Cloud el disco puede ser de solo lectura, y eso no es motivo
    para romper nada: el dato ya esta en memoria y se usa igual, solo que la
    proxima ejecucion volvera a preguntar a la API.
    """
    try:
        RUTA_CONFIG.parent.mkdir(parents=True, exist_ok=True)
        with open(RUTA_CONFIG, "w", encoding="utf-8") as f:
            json.dump(config, f, ensure_ascii=False, indent=2, sort_keys=False)
            f.write("\n")
        return True
    except Exception as e:
        logger.warning(f"No se pudo guardar {RUTA_CONFIG}: {e}")
        return False


def temporada_del_config() -> str:
    """Etiqueta de la temporada que hay guardada, o "" si no hay nada."""
    return _cargar_config().get("temporada", "")


def config_caducado() -> bool:
    """¿La foto guardada es de una temporada anterior a la vigente?"""
    return int(_cargar_config().get("temporada_inicio") or 0) < temporada_actual()


# =============================================================================
# Consulta a football-data.org
# =============================================================================

def _cliente():
    try:
        from src.data.football_data_org import FootballDataClient
        cliente = FootballDataClient()
        return cliente if cliente.is_configured else None
    except Exception as e:
        logger.warning(f"No se pudo crear el cliente de football-data.org: {e}")
        return None


# Formas juridicas que sobran cuando hay que inventar un nombre legible para un
# club que no figura en _NOMBRE_POR_ID.
_RUIDO_NOMBRE = re.compile(
    r"^(?:AFC|AC|ACF|AJ|AS|ASD|BSC|CA|CD|CF|CFC|CS|FC|GD|SC|SS|SSC|SV|TSG|UD|US|VfB|VfL)\s+"
    r"|\s+(?:AFC|AC|BC|CF|CFC|FC|SC|SV|Calcio|Calcio\s+1913)$",
    re.IGNORECASE,
)


def _nombre_legible(equipo: dict) -> str:
    """Nombre presentable para un club sin entrada propia en el mapa."""
    corto = (equipo.get("shortName") or "").strip()
    largo = (equipo.get("name") or "").strip()
    base = corto or largo
    limpio = _RUIDO_NOMBRE.sub("", base).strip()
    return limpio or base or largo


def _fichas_desde_api(liga: str, temporada: int) -> Optional[List[dict]]:
    """
    Listado de la liga segun football-data.org, o None si no se pudo obtener.

    Cada ficha lleva el nombre interno, el oficial y el id, para que
    plantillas.py pueda pedir la plantilla sin volver a resolver el nombre.
    """
    codigo = LIGAS_DINAMICAS.get(liga)
    if not codigo:
        return None
    cliente = _cliente()
    if not cliente:
        logger.info(f"Sin llave de football-data.org: no se puede refrescar {liga}")
        return None

    try:
        datos = cliente._get(f"competitions/{codigo}/teams",
                             params={"season": temporada})
    except Exception as e:
        logger.warning(f"Error pidiendo los equipos de {liga}: {e}")
        return None

    equipos = (datos or {}).get("teams") or []
    if not equipos:
        logger.warning(f"football-data.org no devolvio equipos de {liga} "
                       f"({codigo}, temporada {temporada})")
        return None

    # Un nombre ya asignado a mano en el fichero pesa mas que el de la API: si
    # alguien renombro un club para casarlo con el resto de la aplicacion, un
    # refresco no debe deshacerlo.
    previos = {f.get("id"): f.get("nombre")
               for f in _fichas_guardadas(liga) if f.get("id")}

    fichas = []
    for t in equipos:
        id_equipo = t.get("id")
        nombre = (_NOMBRE_POR_ID.get(id_equipo)
                  or previos.get(id_equipo)
                  or _nombre_legible(t))
        fichas.append({
            "nombre": nombre,
            "oficial": (t.get("name") or nombre).strip(),
            "id": id_equipo,
        })

    fichas.sort(key=lambda f: _norm(f["nombre"]))
    return fichas


# =============================================================================
# API del modulo
# =============================================================================

def _fichas_guardadas(liga: str) -> List[dict]:
    bloque = _cargar_config().get("ligas", {}).get(liga) or {}
    return [f for f in (bloque.get("equipos") or []) if f.get("nombre")]


def refrescar(liga: Optional[str] = None, temporada: Optional[int] = None,
              guardar: bool = True) -> Dict[str, List[str]]:
    """
    Pide los listados a football-data.org y reescribe el fichero.

    Args:
        liga: una liga concreta, o None para todas las cubiertas.
        temporada: año de inicio; por defecto la temporada en curso.
        guardar: False para comprobar sin escribir en disco.

    Returns:
        {liga: [nombres]} con lo que se haya podido refrescar. Una liga que
        falle no sale en el resultado y conserva lo que hubiera guardado.
    """
    temporada = temporada_actual() if temporada is None else int(temporada)
    objetivo = [liga] if liga else list(LIGAS_DINAMICAS)
    objetivo = [nombre_interno_liga(x) or x for x in objetivo]

    config = dict(_cargar_config())
    config.setdefault("ligas", {})
    ligas = dict(config["ligas"])
    logrado: Dict[str, List[str]] = {}

    for nombre_liga in objetivo:
        if nombre_liga not in LIGAS_DINAMICAS:
            logger.info(f"{nombre_liga} no tiene fuente viva; se omite")
            continue
        fichas = _fichas_desde_api(nombre_liga, temporada)
        if not fichas:
            continue
        ligas[nombre_liga] = {
            "codigo": LIGAS_DINAMICAS[nombre_liga],
            "equipos": fichas,
        }
        logrado[nombre_liga] = [f["nombre"] for f in fichas]

    if not logrado:
        return {}

    config["ligas"] = ligas
    # La temporada solo se sella cuando se han refrescado TODAS las ligas
    # cubiertas EN ESTA llamada. Sellarla tras refrescar una sola dejaria las
    # otras seis, que siguen siendo de la temporada pasada, marcadas como
    # vigentes y nadie volveria a pedirlas.
    if set(LIGAS_DINAMICAS) <= set(logrado):
        config["temporada_inicio"] = temporada
        config["temporada"] = etiqueta_temporada(temporada)
    config["fuente"] = ("football-data.org — "
                        "competitions/{codigo}/teams?season=" + str(temporada))
    config["actualizado"] = date.today().isoformat()

    global _CONFIG
    with _LOCK:
        _CONFIG = config
    if guardar:
        _guardar_config(config)

    return logrado


def equipos_de(liga: str) -> List[str]:
    """
    Nombres internos de los equipos de la maxima categoria de esa liga.

    Devuelve lista vacia para una liga sin fuente viva, para que quien llame
    pueda recurrir a su propio listado en vez de recibir un dato inventado.
    """
    nombre_liga = nombre_interno_liga(liga)
    if not nombre_liga:
        return []

    # Foto caducada: se pide la nueva una sola vez por sesion y por liga.
    if config_caducado() and nombre_liga not in _REFRESCADAS:
        _REFRESCADAS.add(nombre_liga)
        temporada = temporada_actual()
        logger.info(f"Listado de {nombre_liga} es de la temporada "
                    f"{temporada_del_config() or 'desconocida'}; "
                    f"pidiendo la {etiqueta_temporada(temporada)}")
        if not refrescar(nombre_liga, temporada):
            logger.warning(f"No se pudo actualizar {nombre_liga}: se sirve el "
                           f"listado de {temporada_del_config() or 'temporada desconocida'}")

    return [f["nombre"] for f in _fichas_guardadas(nombre_liga)]


def ficha_de(equipo: str, liga: Optional[str] = None) -> Optional[dict]:
    """
    Ficha guardada de un club: {"nombre", "oficial", "id", "liga"}.

    Busca por nombre interno y, si no lo encuentra, por nombre oficial.
    """
    if not equipo:
        return None
    objetivo = _norm(equipo)
    ligas = _cargar_config().get("ligas", {})
    candidatas = [nombre_interno_liga(liga) or liga] if liga else list(ligas)

    for nombre_liga in candidatas:
        if nombre_liga not in ligas:
            continue
        for f in _fichas_guardadas(nombre_liga):
            if _norm(f["nombre"]) == objetivo or _norm(f.get("oficial", "")) == objetivo:
                return {**f, "liga": nombre_liga}
    return None


def id_oficial(equipo: str, liga: Optional[str] = None) -> Optional[int]:
    """Id de football-data.org del club, o None si no consta."""
    ficha = ficha_de(equipo, liga)
    return ficha.get("id") if ficha else None


def liga_de(equipo: str) -> Optional[str]:
    """Liga en la que consta el club esta temporada."""
    ficha = ficha_de(equipo)
    return ficha.get("liga") if ficha else None


def resumen() -> dict:
    """Estado del listado, para el panel de diagnostico."""
    config = _cargar_config()
    return {
        "temporada": config.get("temporada") or "desconocida",
        "temporada_vigente": etiqueta_temporada(),
        "caducado": config_caducado(),
        "actualizado": config.get("actualizado", ""),
        "fuente": config.get("fuente", ""),
        "ruta": str(RUTA_CONFIG),
        "ligas": {liga: len(_fichas_guardadas(liga)) for liga in LIGAS_DINAMICAS},
    }


if __name__ == "__main__":  # pragma: no cover
    # `python -m src.data.ligas_equipos` fuerza el refresco y deja el fichero
    # listo para versionar.
    logging.basicConfig(level=logging.INFO,
                        format="%(levelname)s %(name)s: %(message)s")
    resultado = refrescar()
    for nombre_liga, nombres in resultado.items():
        print(f"\n{nombre_liga} ({len(nombres)}):")
        print("  " + " | ".join(nombres))
    if not resultado:
        print("No se pudo refrescar ninguna liga.")
    print(f"\nTemporada sellada: {temporada_del_config() or 'ninguna'}")
