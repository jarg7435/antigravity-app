"""
Investigador web de designaciones arbitrales — La Gema JARG74.

Este modulo existe porque la aplicacion mostraba arbitros que no eran los
designados. El caso que lo motiva: para Athletic - Atletico de Madrid devolvia
"Ortiz Arias" cuando la designacion oficial del CTA era Munuera Montero.

El origen del fallo no era la falta de fuentes, sino como se leian. Los
scrapers de referee_source_mapper.py descargaban la PORTADA de rfef.es y le
aplicaban esta expresion regular a todo el texto de la pagina:

    ({local}).*?({visitante}).*?:?\\s*([A-Z][a-z]+(?:\\s[A-Z][a-z]+)+)

El `.*?` atraviesa la pagina entera, de modo que enlazaba la palabra "Athletic"
de una noticia con la palabra "Atletico" de otra y se quedaba con el primer par
de palabras capitalizadas que apareciera despues — el nombre de cualquiera. El
resultado tiene forma de nombre propio, asi que ningun filtro posterior lo
detenia.

Este modulo cambia las tres cosas que hacian falta:

1. BUSCA, en lugar de raspar una portada. Consulta varios buscadores y feeds
   de prensa con la consulta concreta del partido, que es lo que hace una
   persona cuando quiere saber quien pita.
2. EXIGE PROXIMIDAD. El nombre tiene que aparecer en la misma frase que los dos
   equipos o que una palabra clave de designacion. No vale que este en la misma
   pagina.
3. EXIGE CORROBORACION. Un solo indicio no basta: se acepta el nombre cuando lo
   confirma una fuente oficial o cuando coinciden dos fuentes independientes. Si
   no se llega a ese listón, se devuelve PENDIENTE con el enlace de consulta.
   Nunca un nombre generico ni el primero que suene.

Politica de coste: por defecto solo usa fuentes gratuitas. Si existe la variable
ANTHROPIC_API_KEY, anade ademas una consulta a Claude con busqueda web, que es
mas precisa; sin esa clave el modulo funciona igual, solo con menos alcance.

Uso:

    from src.data.investigador_web import investigar_arbitro
    r = investigar_arbitro("Athletic Club", "Atletico de Madrid",
                           datetime(2026, 9, 6), "La Liga")
    r["estado"]      # "VERIFICADO" | "PROBABLE" | "PENDIENTE"
    r["name"]        # "Munuera Montero"  (cadena vacia si PENDIENTE)
    r["evidencias"]  # de donde sale, con enlaces

Autor: Antigravity - La Gema JARG74
"""

import os
import re
import unicodedata
import xml.etree.ElementTree as ET
from datetime import datetime
from typing import Dict, List, Optional
from urllib.parse import quote_plus

import requests

from src.data.cache_manager import CacheManager

# -----------------------------------------------------------------------------
# Estados posibles del resultado
# -----------------------------------------------------------------------------

VERIFICADO = "VERIFICADO"   # fuente oficial, o dos fuentes independientes
PROBABLE = "PROBABLE"       # un solo indicio serio; hay que confirmarlo
PENDIENTE = "PENDIENTE"     # no hay designacion publicada, o no es fiable

# Una designacion se publica pocos dias antes. Cachear mas tiempo arriesga
# servir la designacion de la jornada anterior.
TTL_DESIGNACION = 3 * 3600

_CACHE = CacheManager(persist=True, cache_dir="data/cache")

_UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
       "(KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36")

_CABECERAS = {"User-Agent": _UA, "Accept-Language": "es-ES,es;q=0.9,en;q=0.8"}

# Portales donde se publica la designacion de cada competicion. Se ofrecen al
# usuario como enlace de consulta cuando la busqueda queda en PENDIENTE, y su
# dominio marca a una fuente como oficial.
#
# OJO con la RFEF: el CTA publica las designaciones de cada jornada dentro de
# una IMAGEN (el cartel "DESIGNACIONES J04"), no como texto. El nombre del
# arbitro no esta en el HTML de la pagina, asi que ningun lector automatico
# puede sacarlo de ahi por muy bien que la descargue. El enlace sirve para que
# lo mire una persona; para la busqueda automatica, la via real es la prensa,
# que si publica los nombres en el titular.
PORTALES_OFICIALES = {
    "La Liga": [
        ("CTA / RFEF — designaciones",
         "https://www.rfef.es/noticias/arbitros/designaciones"),
        ("LaLiga — calendario",
         "https://www.laliga.com/laliga-easports/calendario"),
    ],
    "Premier League": [
        ("Premier League — match officials",
         "https://www.premierleague.com/referees/overview"),
    ],
    "Serie A": [
        ("AIA — designazioni CAN",
         "https://www.aia-figc.it/designazioni/cana/"),
        ("Lega Serie A", "https://www.legaseriea.it/it/serie-a"),
    ],
    "Bundesliga": [
        ("DFB — Schiedsrichter Ansetzungen",
         "https://www.dfb.de/sportl-strukturen/schiedsrichter/ansetzungen/"),
    ],
    "Ligue 1": [
        ("LFP — Ligue 1", "https://www.ligue1.fr/calendrier-resultats"),
    ],
    "UEFA": [
        ("UEFA — match officials", "https://www.uefa.com/"),
    ],
}

# Dominios cuya palabra vale por si sola. Son las federaciones y las ligas: si
# lo dice el CTA, es la designacion, no un rumor de prensa.
_DOMINIOS_OFICIALES = (
    "rfef.es", "laliga.com", "premierleague.com", "aia-figc.it",
    "legaseriea.it", "dfb.de", "bundesliga.com", "lfp.fr", "ligue1.fr",
    "fff.fr", "uefa.com", "cta-rfef.es",
)

# Palabras que anuncian una designacion. Su presencia cerca del nombre es lo que
# distingue "designado para el Athletic - Atletico" de una mencion cualquiera.
_CLAVES_DESIGNACION = (
    "arbitro", "arbitra", "arbitrara", "colegiado", "designacion",
    "designado", "designaciones", "pitara", "pita", "dirigira", "dirige",
    "referee", "official", "designazione", "arbitro di", "schiedsrichter",
    "ansetzung", "arbitre", "arbitrera",
)


def _sin_tildes(texto: str) -> str:
    return "".join(
        c for c in unicodedata.normalize("NFD", str(texto))
        if unicodedata.category(c) != "Mn"
    )


def _norm(texto: str) -> str:
    return re.sub(r"\s+", " ", _sin_tildes(texto).lower()).strip()


def _tokens_equipo(nombre: str) -> List[str]:
    """
    Palabras por las que se reconoce a un equipo en un titular.

    Se quitan las formas juridicas (FC, CD, Club) porque no identifican a
    nadie, y se conservan las de tres letras o mas. "Atletico de Madrid" queda
    como ["atletico", "madrid"], y basta con que aparezca una de ellas.
    """
    ruido = {"fc", "cf", "cd", "ud", "rc", "rcd", "sd", "ac", "as", "sc",
             "afc", "club", "de", "del", "la", "el", "futbol", "football",
             "deportivo", "balompie"}
    palabras = re.sub(r"[^a-z0-9 ]+", " ", _norm(nombre)).split()
    return [p for p in palabras if len(p) >= 3 and p not in ruido]


def _menciona_equipo(texto_norm: str, equipo: str) -> bool:
    tokens = _tokens_equipo(equipo)
    return any(t in texto_norm for t in tokens) if tokens else False


def _es_oficial(url: str) -> bool:
    u = (url or "").lower()
    return any(d in u for d in _DOMINIOS_OFICIALES)


# -----------------------------------------------------------------------------
# Extraccion del nombre con exigencia de proximidad
# -----------------------------------------------------------------------------

def _frases(texto: str) -> List[str]:
    """Trocea en frases. La unidad de proximidad es la frase, no la pagina."""
    limpio = re.sub(r"<[^>]+>", " ", texto or "")
    limpio = re.sub(r"\s+", " ", limpio)
    return [f.strip() for f in re.split(r"(?<=[.!?;•|])\s+|\n", limpio) if f.strip()]


# Particulas que pueden ir DENTRO de un nombre compuesto, nunca en los extremos.
_PARTICULAS_NOMBRE = {
    "de", "del", "la", "las", "los", "y", "van", "von", "di", "da", "dos",
    "ben", "el", "al", "bin", "mac", "mc",
}

# Signos que cierran un nombre: lo que va detras ya es otra cosa.
_CIERRA_NOMBRE = ",;:.!?)»\"'"


def _candidatos_en_frase(frase: str) -> List[str]:
    """
    Nombres propios que aparecen en una frase.

    Antes esto era una expresion regular que admitia como mucho TRES palabras y
    UNA particula. Los nombres de los colegiados espanoles no caben ahi: al
    buscar el Valencia - Barcelona, el titular

        "Isidro Diaz de Mera Escuderos, arbitro del Valencia - Barcelona"

    se partia en dos trozos, "Isidro Diaz" y "Mera Escuderos". Ninguno de los
    dos casa con la entrada "Diaz de Mera" del censo, que exige dos palabras en
    comun, asi que los dos se descartaban y la designacion se perdia pese a
    estar escrita con todas sus letras.

    Ahora se recorren las palabras y se construye la SERIE MAS LARGA de palabras
    con mayuscula inicial, admitiendo particulas por dentro. "Isidro Diaz de
    Mera Escuderos" sale entero.
    """
    from src.data.referee_database import es_nombre_plausible, _NUNCA_NOMBRE

    def clasificar(token: str):
        """(texto_limpio, tipo, cierra) para un token suelto."""
        limpio = token.strip("«»\"'()[]¿?¡!,;:.")
        cierra = bool(token) and token[-1] in _CIERRA_NOMBRE
        if not limpio:
            return None, None, cierra
        if not limpio.replace("-", "").replace("'", "").isalpha():
            return None, None, cierra
        minus = limpio.lower()
        if minus in _NUNCA_NOMBRE:
            return None, None, cierra
        if minus in _PARTICULAS_NOMBRE and not limpio[0].isupper():
            return limpio, "particula", cierra
        if limpio[0].isupper():
            # Una particula en MAYUSCULA es parte del nombre y no se recorta por
            # delante: el colegiado se llama "Del Cerro Grande", no "Cerro
            # Grande". La minuscula si delata relleno de frase ("del Valencia").
            return limpio, "nombre", cierra
        return None, None, cierra

    salida, vistos = [], set()

    def emitir(serie):
        # Por delante solo se recortan las particulas en minuscula, que son
        # relleno de la frase. Por detras se recortan siempre, vayan como
        # vayan: ningun nombre termina en "de" ni en "y".
        r = list(serie)
        while r and r[0][1] == "particula":
            r.pop(0)
        while r and r[-1][0].lower() in _PARTICULAS_NOMBRE:
            r.pop()
        if len(r) < 2:
            return
        palabras = [p[0] for p in r]
        # es_nombre_plausible admite hasta cinco palabras. Una serie mas larga
        # suele ser dos nombres pegados, asi que se ofrecen tambien ventanas
        # mas cortas y que decida el censo cual de ellas es un colegiado.
        tramos = [palabras]
        if len(palabras) > 5:
            tramos = [palabras[i:i + n]
                      for n in (5, 4, 3)
                      for i in range(len(palabras) - n + 1)]
        for tramo in tramos:
            nombre = " ".join(tramo)
            clave = nombre.lower()
            if clave in vistos:
                continue
            if es_nombre_plausible(nombre):
                vistos.add(clave)
                salida.append(nombre)

    serie = []
    for token in frase.split():
        texto, tipo, cierra = clasificar(token)
        if tipo is None:
            emitir(serie)
            serie = []
            continue
        serie.append((texto, tipo))
        if cierra:
            emitir(serie)
            serie = []
    emitir(serie)

    return salida


def _extraer_designacion(texto: str, home: str, away: str,
                         liga: str = "", solo_fuerte: bool = False) -> Optional[str]:
    """
    Nombre del arbitro designado, exigiendo que la frase hable del partido.

    Una frase sirve si menciona a los dos equipos, o si menciona a uno de ellos
    junto a una palabra clave de designacion. Sin ese anclaje se devuelve None:
    es preferible no saber a repetir el error de tomar un nombre de otra
    noticia de la misma pagina.
    """
    from src.data.referee_database import pertenece_al_censo

    # Las frases se clasifican por lo bien que anclan al partido, y se recorren
    # en ese orden. Importa: una frase que nombra a los DOS equipos habla casi
    # con seguridad de este encuentro, mientras que "Ortiz Arias arbitro al
    # Athletic la temporada pasada" nombra a uno solo y habla de otra cosa. Sin
    # esta prioridad, la segunda podia ganarle a la designacion real solo por
    # aparecer antes en la pagina.
    fuertes, debiles = [], []
    for frase in _frases(texto):
        fn = _norm(frase)
        tiene_local = _menciona_equipo(fn, home)
        tiene_visit = _menciona_equipo(fn, away)
        tiene_clave = any(k in fn for k in _CLAVES_DESIGNACION)

        if tiene_local and tiene_visit:
            fuertes.append(frase)
        elif (tiene_local or tiene_visit) and tiene_clave:
            debiles.append(frase)

    if solo_fuerte and not fuertes:
        return None

    mejor_debil = None

    for frase in (fuertes if solo_fuerte else fuertes + debiles):
        for candidato in _candidatos_en_frase(frase):
            # Un candidato que resulta ser el nombre de un equipo no vale.
            cn = _norm(candidato)
            if _menciona_equipo(cn, home) or _menciona_equipo(cn, away):
                continue

            en_censo = pertenece_al_censo(candidato, liga)
            if en_censo is True:
                return candidato          # colegiado real de esa competicion
            if mejor_debil is None:
                # Se guarda tambien cuando el censo dice que NO lo conoce. El
                # censo local son 21 nombres de LaLiga y cada temporada asciende
                # gente: descartar en silencio a quien no figure en el convertia
                # "no lo tengo fichado" en "no existe". Se devuelve como ultimo
                # recurso, y el veredicto lo dejara en PROBABLE para que el
                # supervisor pida confirmarlo.
                mejor_debil = candidato

    return mejor_debil


# -----------------------------------------------------------------------------
# Fuentes gratuitas
# -----------------------------------------------------------------------------

def _consultas(home: str, away: str, liga: str) -> List[str]:
    return [
        f"árbitro designado {home} {away}",
        f"designación arbitral {home} {away} {liga}",
        f"quién arbitra {home} {away}",
        f"referee appointed {home} {away}",
    ]


def _fuente_google_news(home, away, liga, timeout=10) -> List[Dict]:
    """Titulares y entradillas de prensa a traves del RSS publico de Google News."""
    articulos = []
    vistos = set()
    for consulta in _consultas(home, away, liga):
        url = (f"https://news.google.com/rss/search?q={quote_plus(consulta)}"
               f"&hl=es&gl=ES&ceid=ES:es")
        try:
            r = requests.get(url, headers={**_CABECERAS,
                                           "Accept": "application/rss+xml, text/xml"},
                             timeout=timeout)
            if r.status_code != 200:
                continue
            raiz = ET.fromstring(r.content)
        except Exception as e:
            print(f"  [investigador/news] {consulta[:32]}: {type(e).__name__}")
            continue

        for item in raiz.findall(".//item")[:12]:
            enlace = item.findtext("link", "") or ""
            if enlace and enlace in vistos:
                continue
            vistos.add(enlace)
            articulos.append((item.findtext("title", "") or "",
                              item.findtext("description", "") or "",
                              enlace))

    # Se agotan TODAS las consultas antes de decidir. Parar en la primera que
    # devolviera algo era un atajo caro: la consulta "arbitro Athletic Atletico"
    # traia primero un titular del Barcelona - Athletic, y como ya habia
    # articulos no se llegaba a lanzar "designacion arbitral ...", que es la que
    # devuelve el titular del partido correcto.

    def _recoger(solo_fuerte):
        salida = []
        for titulo, desc, enlace in articulos:
            nombre = _extraer_designacion(f"{titulo}. {desc}", home, away, liga,
                                          solo_fuerte=solo_fuerte)
            if nombre:
                medio = titulo.rsplit(" - ", 1)[-1] if " - " in titulo else "Google News"
                salida.append({
                    "name": nombre,
                    "fuente": f"Prensa · {medio}",
                    "url": enlace,
                    "oficial": _es_oficial(enlace),
                    "extracto": titulo[:160],
                    # Un titular que solo nombra a uno de los dos equipos puede
                    # estar hablando de otro partido. Se marca para que el
                    # veredicto no lo promocione nunca por si solo.
                    "anclaje": "fuerte" if solo_fuerte else "débil",
                })
        return salida

    # Dos pasadas, y esto es lo que evita el fallo original. Un titular como
    # "Ortiz Arias, el arbitro del FC Barcelona - Athletic" nombra a UN equipo
    # del partido que buscamos y lleva la palabra "arbitro", asi que ancla en
    # debil y colaba un arbitro de otro encuentro. Los titulares que nombran a
    # los DOS equipos hablan de este partido, asi que se agotan primero y solo
    # se baja al anclaje debil si ninguno responde.
    hallazgos = _recoger(solo_fuerte=True)
    if hallazgos:
        return hallazgos
    return _recoger(solo_fuerte=False)


def _fuente_duckduckgo(home, away, liga, timeout=10) -> List[Dict]:
    """
    Buscador web general, por la version HTML sin JavaScript.

    Se usa DuckDuckGo y no Google porque su endpoint html no exige clave ni
    acepta el raspado de la pagina de resultados de Google, que ademas lo
    prohibe en sus condiciones.
    """
    hallazgos = []
    for consulta in _consultas(home, away, liga)[:2]:
        try:
            r = requests.post("https://html.duckduckgo.com/html/",
                              data={"q": consulta}, headers=_CABECERAS,
                              timeout=timeout)
            if r.status_code != 200:
                continue
        except Exception as e:
            print(f"  [investigador/ddg] {consulta[:32]}: {type(e).__name__}")
            continue

        try:
            from bs4 import BeautifulSoup
            sopa = BeautifulSoup(r.text, "html.parser")
            resultados = sopa.select(".result")[:12]
        except Exception:
            resultados = []

        for res in resultados:
            titulo_el = res.select_one(".result__a")
            frag_el = res.select_one(".result__snippet")
            titulo = titulo_el.get_text(" ", strip=True) if titulo_el else ""
            frag = frag_el.get_text(" ", strip=True) if frag_el else ""
            enlace = titulo_el.get("href", "") if titulo_el else ""
            nombre = _extraer_designacion(f"{titulo}. {frag}", home, away, liga)
            if nombre:
                hallazgos.append({
                    "name": nombre,
                    "fuente": "Búsqueda web · DuckDuckGo",
                    "url": enlace,
                    "oficial": _es_oficial(enlace),
                    "extracto": (titulo or frag)[:160],
                })
        if hallazgos:
            break
    return hallazgos


def _fuente_sofascore(home, away, timeout=8) -> List[Dict]:
    """
    Ficha del partido en SofaScore, que publica el arbitro cuando ya consta.

    Es la fuente mas limpia de las gratuitas: da el nombre en un campo propio,
    sin necesidad de interpretar texto.
    """
    try:
        from src.data.scrapers.sofascore_api import fetch_referee as sofa_ref
        r = sofa_ref(home, away)
    except Exception as e:
        print(f"  [investigador/sofascore] {type(e).__name__}: {e}")
        return []

    if not r or not r.get("name"):
        return []
    return [{
        "name": r["name"],
        "fuente": "SofaScore (ficha del partido)",
        "url": r.get("verification_link", ""),
        "oficial": False,
        "extracto": "Campo 'referee' de la ficha oficial del encuentro.",
    }]


def _fuente_football_data(home, away, liga, timeout=10) -> List[Dict]:
    """
    football-data.org, que expone los oficiales del partido en su plan gratuito.

    Cuenta como fuente oficial: los nombres salen del feed de la competicion,
    no de un titular.
    """
    try:
        from src.data.football_data_org import FootballDataClient, COMPETITION_CODES
        from src.data.referee_database import liga_canonica
    except Exception:
        return []

    try:
        cliente = FootballDataClient()
        if not cliente.is_configured:
            return []
        codigo = COMPETITION_CODES.get(liga_canonica(liga)) or COMPETITION_CODES.get(liga)
        if not codigo:
            return []
        partidos = cliente.get_upcoming_matches(codigo) or cliente.get_matches_today(codigo) or []
    except Exception as e:
        print(f"  [investigador/football-data] {type(e).__name__}: {e}")
        return []

    for m in partidos:
        mh = (m.get("homeTeam") or {}).get("name", "")
        ma = (m.get("awayTeam") or {}).get("name", "")
        if not (_menciona_equipo(_norm(mh), home) and _menciona_equipo(_norm(ma), away)):
            continue
        try:
            detalle = cliente.get_match_with_referees(m.get("id")) or {}
        except Exception:
            continue
        for oficial in detalle.get("referees", []) or []:
            if oficial.get("role") in ("REFEREE", None, ""):
                nombre = (oficial.get("name") or "").strip()
                if nombre:
                    return [{
                        "name": nombre,
                        "fuente": "football-data.org (oficiales del partido)",
                        "url": "https://www.football-data.org/",
                        "oficial": True,
                        "extracto": f"{mh} vs {ma} — rol REFEREE.",
                    }]
        break
    return []


def _fuente_claude(home, away, liga, timeout=40) -> List[Dict]:
    """
    Refuerzo opcional: Claude con busqueda web.

    Solo se activa si existe ANTHROPIC_API_KEY. Es la fuente que mas se parece
    a consultar un buscador a mano, pero tiene coste por llamada, asi que el
    modulo esta pensado para funcionar sin ella.
    """
    clave = os.environ.get("ANTHROPIC_API_KEY", "").strip()
    if not clave:
        return []

    hoy = datetime.now().strftime("%d/%m/%Y")
    prompt = (
        f"Hoy es {hoy}. Busca en la web quién es el árbitro designado para el "
        f"partido {home} contra {away} de {liga}.\n"
        f"Responde en una sola línea con este formato exacto:\n"
        f"NOMBRE | URL_DE_LA_FUENTE\n"
        f"Si no encuentras una designación publicada, responde exactamente: "
        f"PENDIENTE\n"
        f"No inventes ningún nombre bajo ninguna circunstancia."
    )
    try:
        resp = requests.post(
            "https://api.anthropic.com/v1/messages",
            headers={"x-api-key": clave, "anthropic-version": "2023-06-01",
                     "content-type": "application/json"},
            json={"model": "claude-haiku-4-5-20251001", "max_tokens": 300,
                  "tools": [{"type": "web_search_20250305", "name": "web_search"}],
                  "messages": [{"role": "user", "content": prompt}]},
            timeout=timeout,
        )
        if resp.status_code != 200:
            print(f"  [investigador/claude] HTTP {resp.status_code}")
            return []
        texto = "".join(b.get("text", "") for b in resp.json().get("content", [])
                        if b.get("type") == "text").strip()
    except Exception as e:
        print(f"  [investigador/claude] {type(e).__name__}: {e}")
        return []

    if not texto or "PENDIENTE" in texto.upper():
        return []

    linea = texto.splitlines()[0]
    partes = [p.strip() for p in linea.split("|")]
    nombre = partes[0] if partes else ""
    url = partes[1] if len(partes) > 1 else ""

    from src.data.referee_database import es_nombre_plausible
    if not es_nombre_plausible(nombre):
        print(f"  [investigador/claude] descartado, no parece un nombre: {nombre!r}")
        return []

    return [{
        "name": nombre,
        "fuente": "Búsqueda web asistida (Claude)",
        "url": url,
        "oficial": _es_oficial(url),
        "extracto": linea[:160],
    }]


# -----------------------------------------------------------------------------
# Corroboracion y veredicto
# -----------------------------------------------------------------------------

def _misma_persona(a: str, b: str) -> bool:
    """
    ¿Dos formas del mismo nombre?

    Las fuentes alternan "Munuera Montero" y "Juan Martinez Munuera", asi que
    la comparacion es por palabras compartidas y no por igualdad literal.
    """
    from src.data.referee_database import _tokens_apellido
    ta, tb = _tokens_apellido(a), _tokens_apellido(b)
    if not ta or not tb:
        return False
    comunes = ta & tb
    return len(comunes) >= 2 or ta <= tb or tb <= ta


def _agrupar(hallazgos: List[Dict]) -> List[List[Dict]]:
    """Agrupa los hallazgos que se refieren a la misma persona."""
    grupos: List[List[Dict]] = []
    for h in hallazgos:
        for g in grupos:
            if _misma_persona(h["name"], g[0]["name"]):
                g.append(h)
                break
        else:
            grupos.append([h])
    return grupos


def _nombre_mas_completo(grupo: List[Dict]) -> str:
    """De las variantes de un mismo arbitro, la que mas informacion aporta."""
    return max((h["name"] for h in grupo), key=lambda n: (len(n.split()), len(n)))


def _enlaces_de_consulta(liga: str) -> List[Dict]:
    from src.data.referee_database import liga_canonica
    portales = PORTALES_OFICIALES.get(liga_canonica(liga), [])
    if not portales:
        portales = [("SofaScore", "https://www.sofascore.com")]
    return [{"nombre": n, "url": u} for n, u in portales]


def investigar_arbitro(home: str, away: str, fecha: datetime = None,
                       liga: str = "", usar_cache: bool = True) -> Dict:
    """
    Busca en la web quien pita un partido y devuelve un veredicto razonado.

    A diferencia de los scrapers anteriores, nunca devuelve un nombre "por si
    acaso". El resultado incluye siempre el estado y las evidencias, de modo
    que la interfaz pueda distinguir un dato confirmado de una suposicion.

    Returns:
        {
          "estado": VERIFICADO | PROBABLE | PENDIENTE,
          "name": str,                  # vacio si PENDIENTE
          "confianza": "ALTA"|"MEDIA"|"BAJA",
          "en_censo": True|False|None,  # None = liga sin censo comprobable
          "evidencias": [ {name, fuente, url, oficial, extracto} ],
          "consultar": [ {nombre, url} ],
          "motivo": str,                # por que ese estado, en una linea
          "source": str,                # compatibilidad con la cascada previa
          "verification_link": str,
          "_is_fallback": bool,
        }
    """
    fecha = fecha or datetime.now()
    clave_cache = _norm(f"{home}|{away}|{fecha:%Y-%m-%d}|{liga}")

    if usar_cache:
        guardado = _CACHE.get("designacion_arbitral", clave_cache)
        if guardado is not None:
            return dict(guardado)

    print(f"\n[investigador] Designación arbitral: {home} vs {away} | {liga}")

    hallazgos: List[Dict] = []
    for nombre_fuente, funcion in (
        ("football-data.org", lambda: _fuente_football_data(home, away, liga)),
        ("SofaScore", lambda: _fuente_sofascore(home, away)),
        ("Prensa (RSS)", lambda: _fuente_google_news(home, away, liga)),
        ("Buscador web", lambda: _fuente_duckduckgo(home, away, liga)),
        ("Claude web_search", lambda: _fuente_claude(home, away, liga)),
    ):
        try:
            nuevos = funcion() or []
        except Exception as e:
            print(f"  [investigador] {nombre_fuente} falló: {type(e).__name__}: {e}")
            nuevos = []
        if nuevos:
            print(f"  [investigador] {nombre_fuente}: {[n['name'] for n in nuevos]}")
        hallazgos.extend(nuevos)

    resultado = _dictaminar(hallazgos, liga)
    resultado["consultar"] = _enlaces_de_consulta(liga)

    if usar_cache:
        _CACHE.set("designacion_arbitral", clave_cache, resultado,
                   "investigador_web", TTL_DESIGNACION)
    return resultado


def _dictaminar(hallazgos: List[Dict], liga: str) -> Dict:
    """
    Convierte los indicios en un veredicto.

    La regla es deliberadamente exigente, porque el fallo que este modulo
    corrige consistia en aceptar el primer nombre disponible:

      VERIFICADO  una fuente oficial, o dos fuentes independientes de acuerdo,
                  y el nombre no contradice al censo de la competicion.
      PROBABLE    un unico indicio serio. Se muestra, pero marcado como sin
                  confirmar, y el supervisor exigira validacion manual.
      PENDIENTE   nada solido. Se devuelve sin nombre.
    """
    from src.data.referee_database import pertenece_al_censo

    base = {
        "name": "",
        "estado": PENDIENTE,
        "confianza": "BAJA",
        "en_censo": None,
        "evidencias": [],
        "motivo": "",
        "source": "Investigador web",
        "verification_link": "",
        "_is_fallback": True,
    }

    if not hallazgos:
        base["motivo"] = ("Ninguna fuente publica todavía la designación de este "
                          "partido.")
        return base

    grupos = _agrupar(hallazgos)
    # El grupo mas respaldado gana: primero por numero de fuentes oficiales,
    # luego por numero de fuentes distintas.
    def peso(g):
        return (sum(1 for h in g if h["oficial"]),
                len({h["fuente"] for h in g}))

    grupos.sort(key=peso, reverse=True)
    grupo = grupos[0]

    nombre = _nombre_mas_completo(grupo)
    fuentes = {h["fuente"] for h in grupo}
    oficiales = [h for h in grupo if h["oficial"]]
    en_censo = pertenece_al_censo(nombre, liga)

    base["name"] = nombre
    base["evidencias"] = grupo
    base["en_censo"] = en_censo
    base["verification_link"] = next(
        (h["url"] for h in grupo if h["url"]), "")
    base["source"] = " + ".join(sorted(fuentes))

    if en_censo is False:
        # La competicion tiene censo y este nombre no esta en el. Puede ser un
        # colegiado recien ascendido, asi que no se descarta: se degrada.
        base["estado"] = PROBABLE
        base["confianza"] = "BAJA"
        base["_is_fallback"] = True
        base["motivo"] = (f"«{nombre}» no figura en el censo de colegiados de "
                          f"{liga} que maneja la aplicación. Confírmalo antes "
                          f"de usarlo.")
        return base

    if oficiales:
        base["estado"] = VERIFICADO
        base["confianza"] = "ALTA"
        base["_is_fallback"] = False
        base["motivo"] = f"Confirmado por fuente oficial: {oficiales[0]['fuente']}."
        return base

    # Un titular que solo nombra a uno de los dos equipos puede estar hablando
    # de otro partido, y varios de ellos pueden equivocarse igual: es
    # exactamente lo que pasaba con "Ortiz Arias, el árbitro del FC Barcelona -
    # Athletic Club" al buscar el Athletic - Atlético. Por muchos que coincidan,
    # un grupo entero de anclajes débiles no llega a confirmación.
    solo_debiles = grupo and all(h.get("anclaje") == "débil" for h in grupo)

    if len(fuentes) >= 2 and not solo_debiles:
        base["estado"] = VERIFICADO
        base["confianza"] = "ALTA"
        base["_is_fallback"] = False
        base["motivo"] = ("Coinciden " + str(len(fuentes)) +
                          " fuentes independientes: " + ", ".join(sorted(fuentes)) + ".")
        return base

    if solo_debiles:
        base["estado"] = PROBABLE
        base["confianza"] = "BAJA"
        base["_is_fallback"] = True
        base["motivo"] = (
            f"«{nombre}» solo aparece en titulares que no nombran a los dos "
            f"equipos de este partido, así que podrían referirse a otro "
            f"encuentro. Verifícalo antes de usarlo.")
        return base

    base["estado"] = PROBABLE
    base["confianza"] = "MEDIA"
    base["_is_fallback"] = True
    base["motivo"] = (f"Solo lo publica una fuente ({next(iter(fuentes))}). "
                      f"Hace falta una segunda confirmación.")
    return base


def a_formato_cascada(resultado: Dict) -> Dict:
    """
    Adapta el veredicto al diccionario que espera MultiSourceFetcher.

    Se mantiene la forma antigua (name / source / strictness / avg_cards /
    _is_fallback) para no obligar a reescribir a quien ya consume la cascada,
    y se anaden los campos nuevos del veredicto.
    """
    from src.data.referee_database import enrich_referee
    from src.models.base import RefereeStrictness

    if resultado.get("estado") == PENDIENTE or not resultado.get("name"):
        return {
            "name": "",
            "strictness": RefereeStrictness.MEDIUM,
            "avg_cards": 4.0,
            "source": "Designación no publicada todavía",
            "verification_link": (resultado.get("consultar") or [{}])[0].get("url", ""),
            "_is_fallback": True,
            "estado": PENDIENTE,
            "motivo": resultado.get("motivo", ""),
            "evidencias": resultado.get("evidencias", []),
            "consultar": resultado.get("consultar", []),
        }

    salida = {
        "name": resultado["name"],
        "source": resultado.get("source", "Investigador web"),
        "verification_link": resultado.get("verification_link", ""),
        "_is_fallback": resultado.get("_is_fallback", True),
        "estado": resultado.get("estado"),
        "confianza": resultado.get("confianza"),
        "en_censo": resultado.get("en_censo"),
        "motivo": resultado.get("motivo", ""),
        "evidencias": resultado.get("evidencias", []),
        "consultar": resultado.get("consultar", []),
    }
    try:
        salida = enrich_referee(salida)
    except Exception:
        salida.setdefault("strictness", RefereeStrictness.MEDIUM)
        salida.setdefault("avg_cards", 4.0)
    # enrich_referee pone _is_fallback=False al encontrar al arbitro en la base
    # local. Eso dice que lo conocemos, no que este confirmado para ESTE
    # partido, asi que el veredicto manda.
    salida["_is_fallback"] = resultado.get("_is_fallback", True)
    return salida
