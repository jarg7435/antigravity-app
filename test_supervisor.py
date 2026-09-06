# -*- coding: utf-8 -*-
"""
Pruebas del agente supervisor y del investigador de designaciones.

Cubren los tres fallos que motivaron el encargo:
  1. Arbitro erroneo (Ortiz Arias en lugar de Munuera Montero).
  2. Jugadores traspasados que sobrevivian al filtro de plantilla.
  3. Demarcaciones asignadas por defecto como centrocampista.

Las plantillas se simulan para que la prueba no dependa de la red ni de las
claves de API: lo que se comprueba es la logica de decision, no las fuentes.

Ejecutar:  python test_supervisor.py
"""

import io
import sys

sys.path.insert(0, ".")
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

from src.data import investigador_web as iw
from src.data import plantillas
from src.logic import supervisor as sup
from src.models.base import PlayerPosition

_fallos = []


def comprobar(descripcion, obtenido, esperado):
    ok = obtenido == esperado
    print(f"{'OK ' if ok else 'MAL'} {descripcion}")
    if not ok:
        print(f"      esperado: {esperado!r}")
        print(f"      obtenido: {obtenido!r}")
        _fallos.append(descripcion)


# =============================================================================
# 1. Extraccion de la designacion sobre texto con noticias mezcladas
# =============================================================================
print("\n--- 1. Investigador: extraccion con proximidad ---")

PORTADA = (
    "Ortiz Arias arbitro la final de Copa del Rey la pasada temporada. "
    "El Athletic recibe al Atletico de Madrid este sabado en San Mames. "
    "Designacion del CTA: Munuera Montero dirigira el Athletic - Atletico de Madrid."
)
comprobar("Portada mezclada devuelve el arbitro designado, no otro de la pagina",
          iw._extraer_designacion(PORTADA, "Athletic Club", "Atlético de Madrid", "La Liga"),
          "Munuera Montero")

comprobar("Sin frase que hable del partido no devuelve nada",
          iw._extraer_designacion(
              "Ortiz Arias fue noticia ayer. El Athletic gano. El Atletico ficha.",
              "Athletic Club", "Atlético de Madrid", "La Liga"),
          None)

TRAMPA = ("Ortiz Arias arbitro al Athletic la temporada pasada. "
          "Munuera Montero dirigira el Athletic - Atletico de Madrid del sabado.")
comprobar("Una frase con los dos equipos gana a otra con uno solo",
          iw._extraer_designacion(TRAMPA, "Athletic Club", "Atlético de Madrid", "La Liga"),
          "Munuera Montero")

# Nombres compuestos espanoles. La expresion regular anterior admitia tres
# palabras y una particula, asi que partia "Isidro Diaz de Mera Escuderos" en
# "Isidro Diaz" y "Mera Escuderos"; ninguno de los dos casaba con el censo y la
# designacion del Valencia - Barcelona se perdia entera.
print("  (nombres compuestos)")
for texto, esperado in [
    ("Isidro Díaz de Mera Escuderos, árbitro del Valencia - Barcelona",
     "Isidro Díaz de Mera Escuderos"),
    ("Designaciones J04: Isidro Díaz de Mera dirigirá el Valencia CF - FC Barcelona",
     "Isidro Díaz de Mera"),
    ("El Valencia - Barcelona lo arbitrará Díaz de Mera Escuderos",
     "Díaz de Mera Escuderos"),
    ("Ricardo de Burgos Bengoetxea dirigirá el Valencia - Barcelona",
     "Ricardo de Burgos Bengoetxea"),
    ("Alejandro Hernández Hernández, colegiado del Valencia - Barcelona",
     "Alejandro Hernández Hernández"),
    # "Del" en mayuscula es parte del nombre y no se recorta por delante.
    ("Del Cerro Grande arbitrará el Valencia - Barcelona", "Del Cerro Grande"),
]:
    comprobar(f"    {esperado}",
              iw._extraer_designacion(texto, "Valencia", "FC Barcelona", "La Liga"),
              esperado)

comprobar("Un nombre compuesto ajeno al partido sigue sin colarse",
          iw._extraer_designacion("Isidro Díaz de Mera arbitró la final de Copa.",
                                  "Valencia", "FC Barcelona", "La Liga"),
          None)


# =============================================================================
# 2. Corroboracion: cuando se acepta un nombre y cuando no
# =============================================================================
print("\n--- 2. Investigador: reglas de corroboracion ---")

PRENSA = {"name": "Munuera Montero", "fuente": "Prensa · Marca",
          "url": "https://marca.com/x", "oficial": False, "extracto": ""}
SOFA = {"name": "Juan Martínez Munuera Montero", "fuente": "SofaScore (ficha)",
        "url": "https://sofascore.com/y", "oficial": False, "extracto": ""}
OFICIAL = {"name": "Munuera Montero", "fuente": "football-data.org",
           "url": "https://api.football-data.org/", "oficial": True, "extracto": ""}

comprobar("Una sola fuente de prensa queda en PROBABLE",
          iw._dictaminar([PRENSA], "La Liga")["estado"], iw.PROBABLE)
comprobar("Dos fuentes independientes dan VERIFICADO",
          iw._dictaminar([PRENSA, SOFA], "La Liga")["estado"], iw.VERIFICADO)
comprobar("Una fuente oficial sola ya da VERIFICADO",
          iw._dictaminar([OFICIAL], "La Liga")["estado"], iw.VERIFICADO)
comprobar("Un arbitro de otra liga se degrada a PROBABLE",
          iw._dictaminar([{**PRENSA, "name": "Michael Oliver"}], "La Liga")["estado"],
          iw.PROBABLE)
comprobar("Sin hallazgos, PENDIENTE y sin nombre",
          iw._dictaminar([], "La Liga")["name"], "")


# =============================================================================
# 3. Plantillas: traspasados, homonimos y demarcaciones
# =============================================================================
print("\n--- 3. Plantillas: filtro estricto ---")

PLANTILLA_BETIS = [
    {"nombre": "Álvaro Valles", "posicion": "Goalkeeper"},
    {"nombre": "Héctor Bellerín", "posicion": "Right-Back"},
    {"nombre": "Marc Bartra", "posicion": "Centre-Back"},
    {"nombre": "Giovani Lo Celso", "posicion": "Attacking Midfield"},
    {"nombre": "Isco Alarcón", "posicion": "Midfield"},
    {"nombre": "Cucho Hernández", "posicion": "Centre-Forward"},
    {"nombre": "Pablo García", "posicion": "Offence"},
    {"nombre": "Sergio García", "posicion": ""},          # sin demarcacion
]
_original_detallada = plantillas.plantilla_detallada
_original_actual = plantillas.plantilla_actual
plantillas.plantilla_detallada = lambda equipo, liga=None: list(PLANTILLA_BETIS)
plantillas.plantilla_actual = lambda equipo, liga=None: [j["nombre"] for j in PLANTILLA_BETIS]

informe = plantillas.auditar_alineacion(
    ["Isco", "Lo Celso", "Rui Silva", "Cucho Hernández"], "Real Betis", "La Liga")
comprobar("El traspasado (Rui Silva) se descarta",
          informe["descartados"], ["Rui Silva"])
comprobar("Los vigentes se conservan con nombre corto",
          informe["vigentes"], ["Isco", "Lo Celso", "Cucho Hernández"])
comprobar("La auditoria se marca como realizada", informe["verificada"], True)

comprobar("Apellido compartido por dos de la plantilla no basta (dos García)",
          plantillas.esta_en_plantilla("Andrés García",
                                       [j["nombre"] for j in PLANTILLA_BETIS]),
          False)
comprobar("Apellido unico si identifica (Bellerín)",
          plantillas.esta_en_plantilla("Bellerín",
                                       [j["nombre"] for j in PLANTILLA_BETIS]),
          True)

comprobar("Portero se mapea como portero, no como centrocampista",
          plantillas.posicion_de("Álvaro Valles", "Real Betis", "La Liga"),
          PlayerPosition.GOALKEEPER)
comprobar("Right-Back se mapea a defensa",
          plantillas.posicion_de("Bellerín", "Real Betis", "La Liga"),
          PlayerPosition.DEFENDER)
comprobar("Offence se mapea a delantero",
          plantillas.posicion_de("Pablo García", "Real Betis", "La Liga"),
          PlayerPosition.FORWARD)
comprobar("Sin demarcacion en la fuente devuelve None, no MIDFIELDER",
          plantillas.posicion_de("Sergio García", "Real Betis", "La Liga"),
          None)

# Sin plantilla de referencia la auditoria debe declararse no verificada.
plantillas.plantilla_actual = lambda equipo, liga=None: []
plantillas.plantilla_detallada = lambda equipo, liga=None: []
sin_ref = plantillas.auditar_alineacion(["Isco", "Rui Silva"], "Real Betis", "La Liga")
comprobar("Sin listado de inscritos, la auditoria NO se da por verificada",
          sin_ref["verificada"], False)
comprobar("Sin listado no se descarta a nadie a ciegas",
          sin_ref["descartados"], [])


# =============================================================================
# 4. Supervisor: que bloquea y que deja pasar
# =============================================================================
print("\n--- 4. Supervisor: veredictos ---")

plantillas.plantilla_detallada = lambda equipo, liga=None: list(PLANTILLA_BETIS)
plantillas.plantilla_actual = lambda equipo, liga=None: [j["nombre"] for j in PLANTILLA_BETIS]

ONCE_OK = ["Álvaro Valles", "Héctor Bellerín", "Marc Bartra", "Giovani Lo Celso",
           "Isco Alarcón", "Cucho Hernández", "Pablo García"]

ARB_VERIFICADO = {"name": "Munuera Montero", "estado": "VERIFICADO",
                  "source": "football-data.org", "_is_fallback": False,
                  "motivo": "Confirmado por fuente oficial.", "en_censo": True}
ARB_PROBABLE = {"name": "Munuera Montero", "estado": "PROBABLE",
                "source": "Prensa · Marca", "_is_fallback": True,
                "motivo": "Solo lo publica una fuente.", "en_censo": True}
ARB_PENDIENTE = {"name": "", "estado": "PENDIENTE", "source": "Sin publicar",
                 "_is_fallback": True, "motivo": "Aún no hay designación."}

r = sup.supervisar("Real Betis", "Sevilla FC", "La Liga", None,
                   ARB_VERIFICADO, ONCE_OK, ONCE_OK, revisar_temporada=False)
comprobar("Arbitro verificado + onces vigentes -> no bloquea", r.bloqueado, False)

r = sup.supervisar("Real Betis", "Sevilla FC", "La Liga", None,
                   ARB_PROBABLE, ONCE_OK, ONCE_OK, revisar_temporada=False)
comprobar("Arbitro solo PROBABLE -> bloquea", r.bloqueado, True)
comprobar("  y lo dice con el codigo correcto",
          [i.codigo for i in r.graves], ["ARB_SIN_CONFIRMAR"])

r = sup.supervisar("Real Betis", "Sevilla FC", "La Liga", None,
                   ARB_PENDIENTE, ONCE_OK, ONCE_OK, revisar_temporada=False)
comprobar("Designacion sin publicar -> bloquea",
          [i.codigo for i in r.graves], ["ARB_PENDIENTE"])

r = sup.supervisar("Real Betis", "Sevilla FC", "La Liga", None,
                   {**ARB_VERIFICADO, "name": "Michael Oliver", "en_censo": None},
                   ONCE_OK, ONCE_OK, revisar_temporada=False)
comprobar("Arbitro de otra liga -> bloquea por censo",
          [i.codigo for i in r.graves], ["ARB_FUERA_CENSO"])

r = sup.supervisar("Real Betis", "Sevilla FC", "La Liga", None,
                   {"name": "Munuera Montero", "source": "Introducido manualmente",
                    "_is_fallback": False},
                   ONCE_OK, ONCE_OK, revisar_temporada=False)
comprobar("Confirmacion manual desbloquea", r.bloqueado, False)

CON_TRASPASADO = ONCE_OK + ["Rui Silva"]
r = sup.supervisar("Real Betis", "Sevilla FC", "La Liga", None,
                   ARB_VERIFICADO, CON_TRASPASADO, ONCE_OK, revisar_temporada=False)
comprobar("Un traspasado en el once -> bloquea",
          [i.codigo for i in r.graves], ["ONCE_TRASPASADOS"])
comprobar("  y nombra al jugador",
          [i.detalle for i in r.graves][0], ["Rui Silva"])

r = sup.supervisar("Real Betis", "Sevilla FC", "La Liga", None,
                   ARB_VERIFICADO, ONCE_OK + ["Sergio García"], ONCE_OK,
                   revisar_temporada=False)
comprobar("Demarcacion desconocida avisa pero NO bloquea", r.bloqueado, False)
comprobar("  y queda registrada como aviso",
          [i.codigo for i in r.leves], ["DEMARCACION_DESCONOCIDA"])

# De quien sospechar cuando falla medio once lo decide el TAMANO del listado.
# Con un listado corto (aqui 8 inscritos) el patron no sirve y el sospechoso es
# el propio listado.
ONCE_AJENO = ONCE_OK[:5] + ["Fulano Uno", "Mengano Dos", "Zutano Tres", "Perengano Cuatro"]
r = sup.supervisar("Real Betis", "Sevilla FC", "La Liga", None,
                   ARB_VERIFICADO, ONCE_AJENO, ONCE_OK, revisar_temporada=False)
comprobar("Listado corto + 4 fallos -> se sospecha del listado",
          [i.codigo for i in r.graves], ["ONCE_LISTADO_DUDOSO"])

# Pero con un listado COMPLETO la conclusion es la contraria, y este es el caso
# real: football-data.org devolvia 27 jugadores del Barcelona —plantilla sana— y
# los cuatro que no casaban ya no estaban en el club. Quien servia datos viejos
# era la fuente de alineaciones. Con la regla anterior, que solo miraba la
# proporcion, se habria culpado al listado y tapado el problema de verdad.
PLANTILLA_LARGA = [{"nombre": f"Jugador Inscrito {i:02d}", "posicion": "Midfield"}
                   for i in range(1, 25)]
plantillas.plantilla_detallada = lambda equipo, liga=None: list(PLANTILLA_LARGA)
plantillas.plantilla_actual = lambda equipo, liga=None: [j["nombre"] for j in PLANTILLA_LARGA]

ONCE_LARGO = [j["nombre"] for j in PLANTILLA_LARGA[:5]] + [
    "Fulano Uno", "Mengano Dos", "Zutano Tres", "Perengano Cuatro"]
_inf = plantillas.auditar_alineacion(ONCE_LARGO, "FC Barcelona", "La Liga")
comprobar("Listado de 24 inscritos NO se marca como dudoso",
          _inf["listado_dudoso"], False)
r = sup.supervisar("FC Barcelona", "Sevilla FC", "La Liga", None,
                   ARB_VERIFICADO, ONCE_LARGO, ONCE_LARGO, revisar_temporada=False)
comprobar("...y los jugadores se senalan como ausentes del club",
          sorted({i.codigo for i in r.graves}), ["ONCE_TRASPASADOS"])

plantillas.plantilla_detallada = lambda equipo, liga=None: list(PLANTILLA_BETIS)
plantillas.plantilla_actual = lambda equipo, liga=None: [j["nombre"] for j in PLANTILLA_BETIS]

# Uno o dos si son un traspaso plausible y se senalan como tales.
r = sup.supervisar("Real Betis", "Sevilla FC", "La Liga", None,
                   ARB_VERIFICADO, ONCE_OK + ["Rui Silva"], ONCE_OK,
                   revisar_temporada=False)
comprobar("1 de 8 sin casar -> se senala al jugador",
          [i.codigo for i in r.graves], ["ONCE_TRASPASADOS"])

# El listado usado queda a la vista para poder auditarlo.
comprobar("El listado de inscritos se muestra en las comprobaciones",
          any("Listado de inscritos" in c for c in r.comprobaciones), True)

# Salida de emergencia: con la alineacion confirmada a mano, el once deja de
# bloquear, pero el arbitro y la temporada se siguen comprobando igual.
r = sup.supervisar("Real Betis", "Sevilla FC", "La Liga", None,
                   ARB_VERIFICADO, ONCE_AJENO, ONCE_OK, revisar_temporada=False,
                   alineacion_verificada=True)
comprobar("Confirmar la alineacion a mano desbloquea el once", r.bloqueado, False)

r = sup.supervisar("Real Betis", "Sevilla FC", "La Liga", None,
                   ARB_PROBABLE, ONCE_AJENO, ONCE_OK, revisar_temporada=False,
                   alineacion_verificada=True)
comprobar("...pero NO desbloquea un árbitro sin confirmar",
          [i.codigo for i in r.graves], ["ARB_SIN_CONFIRMAR"])

# Un nombre que llega sin decir como se ha verificado no puede aprobarse: era
# la via por la que salian arbitros tomados de noticias de otros partidos.
r = sup.supervisar("Real Betis", "Sevilla FC", "La Liga", None,
                   {"name": "Munuera Montero", "source": "Google News",
                    "_is_fallback": False},
                   ONCE_OK, ONCE_OK, revisar_temporada=False)
comprobar("Árbitro sin procedencia declarada -> bloquea",
          [i.codigo for i in r.graves], ["ARB_SIN_PROCEDENCIA"])

plantillas.plantilla_actual = lambda equipo, liga=None: []
plantillas.plantilla_detallada = lambda equipo, liga=None: []
r = sup.supervisar("Real Betis", "Sevilla FC", "La Liga", None,
                   ARB_VERIFICADO, ONCE_OK, ONCE_OK, revisar_temporada=False)
comprobar("Sin listado de inscritos -> bloquea (no se da por bueno)",
          sorted({i.codigo for i in r.graves}), ["ONCE_SIN_REFERENCIA"])

plantillas.plantilla_detallada = _original_detallada
plantillas.plantilla_actual = _original_actual


# =============================================================================
# 6. Calendario: la fecha del partido y su hora local
# =============================================================================
print("\n--- 6. Calendario: hora canaria, no la del servidor ---")

from src.data import calendario as cal

# El caso real: el Valencia - Barcelona empezaba a las 14:15 UTC. Son las 15:15
# en Canarias, que es donde se usa la aplicacion y lo que marca el SofaScore del
# usuario, y las 16:15 peninsulares, que es lo que pone el cartel del CTA.
# Convertirlo con la hora del proceso daria 14:15 en Streamlit Cloud, que va en
# UTC, y el partido apareceria una hora antes de lo que toca.
comprobar("14:15 UTC son las 15:15 en Canarias",
          cal._a_local("2026-09-06T14:15:00Z", "La Liga (España)").strftime("%Y-%m-%d %H:%M"),
          "2026-09-06 15:15")
comprobar("...y las 16:15 peninsulares, que es la referencia del cartel",
          cal._a_hora_competicion("2026-09-06T14:15:00Z", "La Liga").strftime("%H:%M"),
          "16:15")
comprobar("En enero, sin horario de verano, son las 14:15 canarias",
          cal._a_local("2026-01-06T14:15:00Z", "La Liga").strftime("%H:%M"), "14:15")
comprobar("La Premier: 14:00 UTC son las 15:00 canarias",
          cal._a_local("2026-09-06T14:00:00Z", "Premier League").strftime("%H:%M"), "15:00")
comprobar("...y tambien las 15:00 en Londres, misma hora que Canarias",
          cal._a_hora_competicion("2026-09-06T14:00:00Z", "Premier League").strftime("%H:%M"),
          "15:00")
comprobar("La Serie A: 18:45 UTC son las 19:45 canarias",
          cal._a_local("2026-09-06T18:45:00Z", "Serie A").strftime("%H:%M"), "19:45")
comprobar("...y las 20:45 en Italia",
          cal._a_hora_competicion("2026-09-06T18:45:00Z", "Serie A").strftime("%H:%M"),
          "20:45")
comprobar("Una marca de tiempo ilegible no revienta, devuelve None",
          cal._a_local("no-es-una-fecha", "La Liga"), None)
comprobar("Sin equipos no se inventa fecha",
          cal.fecha_del_partido("", "", "La Liga"), None)
comprobar("La zona que se muestra es siempre la canaria",
          cal._zona("La Liga (España)")[1], "hora canaria")
comprobar("La zona de referencia de LaLiga es la peninsular",
          cal._zona_competicion("La Liga (España)")[1], "peninsular")


# =============================================================================
# 7. Prensa: la fecha manda
# =============================================================================
print("\n--- 7. Prensa: acotar por fecha y quitar el medio ---")

import xml.etree.ElementTree as _ET
from datetime import date as _date

# Titulares REALES devueltos por el RSS de Google News al buscar el
# Valencia - Barcelona del 06/09/2026. Sin acotar por fecha, el feed mezcla
# noticias de cualquier epoca y de otros partidos.
TITULAR_BUENO = ("Díaz de Mera, árbitro del Valencia - Barcelona, "
                 "y Miguel Sesma del Espanyol - Sevilla - IUSPORT")
TITULAR_MEDIO = "Estos son el árbitro y el VAR del Barça - Valencia - El Periódico"
TITULAR_COPA = ("¿Quién es Alberto Undiano Mallenco, árbitro de la final de la "
                "Copa del Rey entre Barcelona - Valencia? - Goal.com")

comprobar("El titular de la designacion da el arbitro correcto",
          iw._extraer_designacion(iw._sin_medio(TITULAR_BUENO),
                                  "Valencia", "FC Barcelona", "La Liga"),
          "Díaz de Mera")

# Google News anade " - Medio" al final de cada titular, y de ahi salia
# "El Periodico" como nombre de arbitro.
comprobar("El nombre del medio ya no se toma por un arbitro",
          iw._extraer_designacion(iw._sin_medio(TITULAR_MEDIO),
                                  "Valencia", "FC Barcelona", "La Liga"),
          None)
comprobar("...y el corte es por la ULTIMA raya, no por la de los equipos",
          iw._sin_medio("Estos son el árbitro y el VAR del Barça - Valencia - El Periódico"),
          "Estos son el árbitro y el VAR del Barça - Valencia")

# Este es el caso que ningun analisis del texto puede resolver: nombra a los dos
# equipos del partido buscado y da un arbitro, pero es de otra temporada. Solo
# la fecha lo descarta.
comprobar("Un titular de otra temporada SI pasa el filtro de texto...",
          iw._extraer_designacion(iw._sin_medio(TITULAR_COPA),
                                  "Valencia", "FC Barcelona", "La Liga"),
          "Alberto Undiano Mallenco")

_desde, _hasta = iw._ventana(_date(2026, 9, 6))
comprobar("...pero su fecha queda fuera de la ventana del partido",
          _desde <= _date(2025, 4, 20) <= _hasta, False)
comprobar("La vispera del partido si entra",
          _desde <= _date(2026, 9, 5) <= _hasta, True)
comprobar("El dia siguiente tambien, por las cronicas",
          _desde <= _date(2026, 9, 7) <= _hasta, True)
comprobar("Dos semanas antes, no",
          _desde <= _date(2026, 8, 23) <= _hasta, False)

_item = _ET.fromstring(
    "<item><pubDate>Sat, 05 Sep 2026 15:38:34 GMT</pubDate></item>")
comprobar("Se lee la fecha de publicacion del feed",
          iw._publicado(_item), _date(2026, 9, 5))
comprobar("Un item sin fecha no revienta",
          iw._publicado(_ET.fromstring("<item/>")), None)

# Titulares de programacion, que son mayoria al buscar un partido del dia.
# Producian el candidato "LaLiga EA Sports", con mayusculas impecables y forma
# de nombre propio.
print("  (titulares de programacion)")
for programacion in [
    "Valencia - Barcelona: TV, horario y cómo ver LaLiga EA Sports online",
    "Valencia – FC Barcelona: horario y dónde ver hoy por TV el partido de fútbol de LaLiga EA Sports",
]:
    comprobar(f"    no da candidato: {programacion[:40]}...",
              iw._extraer_designacion(programacion, "Valencia", "FC Barcelona", "La Liga"),
              None)

# Y aunque colara, el censo tiene que pesar mas que el numero de medios: la
# basura salia en dos y el arbitro real en uno, y ganaba la basura.
_MEZCLA = [
    {"name": "Díaz de Mera", "fuente": "Prensa · IUSPORT", "url": "",
     "oficial": False, "extracto": "", "anclaje": "fuerte"},
    {"name": "LaLiga EA Sports", "fuente": "Prensa · Diario AS", "url": "",
     "oficial": False, "extracto": "", "anclaje": "fuerte"},
    {"name": "LaLiga EA Sports", "fuente": "Prensa · La Vanguardia", "url": "",
     "oficial": False, "extracto": "", "anclaje": "fuerte"},
]
comprobar("Un colegiado del censo gana a un intruso con mas medios",
          iw._dictaminar(_MEZCLA, "La Liga")["name"], "Díaz de Mera")


# =============================================================================
# 8. El proveedor de equipos sirve la plantilla vigente
# =============================================================================
print("\n--- 8. MockDataProvider: plantilla vigente, no la escrita a mano ---")

from src.data.mock_provider import MockDataProvider
from src.models.base import NodeRole

# Listado agrupado por demarcacion, tal y como lo devuelve football-data.org.
PLANTILLA_FD = (
    [{"nombre": f"Portero {i}", "posicion": "Goalkeeper"} for i in range(1, 4)] +
    [{"nombre": f"Defensa {i}", "posicion": "Defence"} for i in range(1, 9)] +
    [{"nombre": f"Medio {i}", "posicion": "Midfield"} for i in range(1, 9)] +
    [{"nombre": f"Punta {i}", "posicion": "Offence"} for i in range(1, 9)]
)
plantillas.plantilla_detallada = lambda equipo, liga=None: list(PLANTILLA_FD)

_dp = MockDataProvider()
_equipo = _dp.get_team_data("FC Barcelona")
_nombres = [p.name for p in _equipo.players]

comprobar("Los jugadores escritos a mano desaparecen",
          any(n in _nombres for n in
              ["Iñaki Peña", "Iñigo Martínez", "Casadó", "Lewandowski"]),
          False)
comprobar("El once sale del listado vigente", _nombres[0], "Portero 1")

# Coger los once primeros del listado daba tres porteros y ocho defensas,
# porque la fuente lo devuelve agrupado por demarcacion.
_reparto = [p.position.value for p in _equipo.players]
comprobar("Un solo portero", _reparto.count("Portero"), 1)
comprobar("Cuatro defensas", _reparto.count("Defensa"), 4)
comprobar("Tres centrocampistas", _reparto.count("Centrocampista"), 3)
comprobar("Tres delanteros", _reparto.count("Delantero"), 3)

# El nodo del BPA lo decide la demarcacion, no el orden de la lista.
comprobar("El portero es nodo Portero",
          _equipo.players[0].node_role, NodeRole.KEEPER)
comprobar("El delantero es nodo Finalizador",
          _equipo.players[-1].node_role, NodeRole.FINALIZER)

# Sin listado vigente se conserva lo que hubiera: mejor eso que un equipo vacio.
plantillas.plantilla_detallada = lambda equipo, liga=None: []
_dp2 = MockDataProvider()
comprobar("Sin plantilla vigente, el equipo no se queda vacio",
          len(_dp2.get_team_data("FC Barcelona").players) > 0, True)

plantillas.plantilla_detallada = _original_detallada
plantillas.plantilla_actual = _original_actual


# =============================================================================
print("\n" + "=" * 62)
if _fallos:
    print(f"FALLOS: {len(_fallos)}")
    for f in _fallos:
        print(f"  - {f}")
    sys.exit(1)
print("Todas las comprobaciones han pasado.")
