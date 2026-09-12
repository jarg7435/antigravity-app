# -*- coding: utf-8 -*-
"""
Pruebas del listado de equipos por liga (src/data/ligas_equipos.py).

Lo que se comprueba es que el desplegable de equipos ofrezca la foto de la
temporada EN CURSO y solo esa. El fallo que las motiva: el selector seguia
ofreciendo Girona, Mallorca y Real Oviedo —descendidos— y no ofrecia a los
ascendidos, porque cada liga tenia su lista escrita a mano en
mock_provider._init_teams() con un comentario "2025-26" al lado.

Tambien se comprueban dos fugas del filtro por liga que aparecieron al
revisarlo: "premier league" es subcadena de "Israeli Premier League", asi que
el desplegable de la Premier inglesa servia 46 equipos, y el de la Bundesliga
30 por el mismo motivo con la liga austriaca.

Ninguna prueba sale a la red: todas leen data/equipos_ligas.json.

Ejecutar:  python test_ligas_equipos.py
"""

import io
import os
import sys

sys.path.insert(0, os.path.abspath("."))
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

from datetime import date

from src.data import ligas_equipos as LE
from src.data.mock_provider import MockDataProvider

fallos = []


def check(nombre, cond):
    print(("  OK   " if cond else "  FALLA") + f"  {nombre}")
    if not cond:
        fallos.append(nombre)


# El numero de equipos de cada liga: lo unico que no depende de la temporada.
PLAZAS = {
    "La Liga": 20, "Premier League": 20, "Serie A": 20,
    "Bundesliga": 18, "Ligue 1": 18, "Eredivisie": 18, "Primeira Liga": 18,
}

print("\n== La temporada se calcula por el mes, no por el año ==")
check("12/09/2026 es la temporada 2026", LE.temporada_actual(date(2026, 9, 12)) == 2026)
check("15/07/2026, recien abierto el mercado, ya es la 2026",
      LE.temporada_actual(date(2026, 7, 15)) == 2026)
check("31/05/2026, con la liga acabandose, sigue siendo la 2025",
      LE.temporada_actual(date(2026, 5, 31)) == 2025)
check("enero cuenta para la temporada que empezo en agosto",
      LE.temporada_actual(date(2027, 1, 20)) == 2026)
check("la etiqueta se escribe 2026-27", LE.etiqueta_temporada(2026) == "2026-27")

print("\n== El fichero guardado es de la temporada vigente ==")
check(f"temporada guardada: {LE.temporada_del_config()}",
      LE.temporada_del_config() == LE.etiqueta_temporada())
check("y por tanto no esta caducado", LE.config_caducado() is False)

print("\n== Cada liga trae sus plazas completas ==")
for liga, plazas in PLAZAS.items():
    equipos = LE.equipos_de(liga)
    check(f"{liga}: {len(equipos)} equipos (esperados {plazas})",
          len(equipos) == plazas)
    check(f"{liga}: sin nombres repetidos", len(set(equipos)) == len(equipos))

print("\n== La etiqueta de la interfaz se resuelve igual que el nombre interno ==")
check("'La Liga (España)' -> La Liga",
      LE.nombre_interno_liga("La Liga (España)") == "La Liga")
check("'premier league' -> Premier League",
      LE.nombre_interno_liga("premier league") == "Premier League")
check("una liga sin fuente viva devuelve None",
      LE.nombre_interno_liga("Süper Lig (Turquía)") is None)
check("y el listado de esa liga sale vacio en vez de inventado",
      LE.equipos_de("Süper Lig (Turquía)") == [])

print("\n== Cada club lleva su id de football-data.org ==")
# Sin el id no hay plantilla real: es lo que usa plantillas.py para pedirla.
sin_id = [(liga, f["nombre"]) for liga in PLAZAS
          for f in LE._fichas_guardadas(liga) if not f.get("id")]
check("ningun club sin id", not sin_id)
if sin_id:
    print("   sin id:", sin_id[:10])

check("FC Barcelona -> 81", LE.id_oficial("FC Barcelona") == 81)
# Los dos casos que el casado por nombre NO resolvia, y que dejaban a estos
# equipos sin plantilla vigente.
check("Napoles -> 113 (el nombre no casa con 'SSC Napoli')",
      LE.id_oficial("Napoles") == 113)
check("Bolonia -> 103 (el nombre no casa con 'Bologna FC 1909')",
      LE.id_oficial("Bolonia") == 103)
check("se puede buscar tambien por el nombre oficial",
      (LE.ficha_de("Real Betis Balompié") or {}).get("nombre") == "Real Betis")
check("la liga del club se resuelve", LE.liga_de("Real Madrid") == "La Liga")
check("un club que no juega en primera no tiene ficha",
      LE.ficha_de("Equipo Inventado FC") is None)

print("\n== El selector sirve exactamente ese listado ==")
proveedor = MockDataProvider()
for liga, plazas in PLAZAS.items():
    servidos = proveedor.get_teams_by_league(liga)
    check(f"{liga}: el selector sirve {len(servidos)} equipos",
          len(servidos) == plazas)
    check(f"{liga}: y son los del listado",
          sorted(servidos) == sorted(LE.equipos_de(liga)))

print("\n== Los descendidos se quedan fuera y los ascendidos dentro ==")
la_liga = proveedor.get_teams_by_league("La Liga (España)")
for equipo in LE.equipos_de("La Liga"):
    if equipo not in la_liga:
        check(f"{equipo} deberia estar en el desplegable", False)
fuera = [e for e in la_liga if e not in LE.equipos_de("La Liga")]
check("el desplegable de La Liga no añade nada por su cuenta", not fuera)
if fuera:
    print("   de mas:", fuera)

print("\n== El nombre de la liga no se busca por subcadena ==")
# Estas cuatro ligas llevan dentro el nombre de una de las grandes.
colisiones = [
    ("Premier League (Inglaterra)", 20),
    ("Israeli Premier League (Israel)", 14),
    ("Ukrainian Premier League (Ucrania)", 12),
    ("Bundesliga (Alemania)", 18),
    ("Austrian Bundesliga (Austria)", 12),
    ("Super League (Grecia)", 16),
    ("Swiss Super League (Suiza)", 10),
]
for etiqueta, cuantos in colisiones:
    servidos = proveedor.get_teams_by_league(etiqueta)
    check(f"{etiqueta}: {len(servidos)} equipos (esperados {cuantos})",
          len(servidos) == cuantos)

print("\n== Cada equipo declara la liga en la que juega ==")
for liga in PLAZAS:
    ajenos = [n for n in proveedor.get_teams_by_league(liga)
              if proveedor.teams_db[n].league != liga]
    check(f"{liga}: ningun equipo con otra liga apuntada", not ajenos)
    if ajenos:
        print("   ajenos:", ajenos[:5])

print("\n== Los nombres que sirve el selector los entiende el resto de la app ==")
from src.data.scrapers.besoccer_scraper import _get_slug
from src.logic.external_analyst import ExternalAnalyst

con_acento = [n for liga in PLAZAS for n in LE.equipos_de(liga)
              if any(c in _get_slug(n) for c in "áéíóúñçãõäöüàèìòù")]
check("ningun slug de BeSoccer arrastra acentos", not con_acento)
if con_acento:
    print("   con acento:", con_acento[:5])

analista = ExternalAnalyst()
check("Celta de Vigo tiene su prensa local, no una inventada",
      "Faro de Vigo" in analista._get_papers("Celta de Vigo"))
check("Napoles tambien", "Il Mattino" in analista._get_papers("Napoles"))
check("y Bayer Leverkusen", "Kicker" in analista._get_papers("Bayer Leverkusen"))

print("\n== Un club de primera trae jugadores, no relleno ==")
# El equipo se construye con la plantilla vigente cuando hay fuente; sin red
# se queda el molde de once, que es lo que garantiza que el estudio no salga
# con un equipo de cero jugadores.
for nombre in ["Real Madrid", LE.equipos_de("La Liga")[0]]:
    equipo = proveedor.get_team_data(nombre)
    check(f"{nombre}: {len(equipo.players)} jugadores",
          len(equipo.players) >= 11)

print("\n== El resumen para el diagnostico dice la verdad ==")
r = LE.resumen()
check("informa de la temporada guardada", r["temporada"] == LE.temporada_del_config())
check("y de si esta caducada", r["caducado"] is False)
check("y del recuento por liga",
      all(r["ligas"][liga] == plazas for liga, plazas in PLAZAS.items()))

print("\n" + ("TODO OK" if not fallos else f"FALLAN {len(fallos)}: {fallos}"))
sys.exit(1 if fallos else 0)
