# -*- coding: utf-8 -*-
"""
Pruebas de la directriz de maxima exigencia: sin falsos positivos de arbitro.

La regla que se comprueba es una sola, y en los dos sentidos: se asigna sola la
designacion que firma una fuente oficial o que sale del registro del propio
partido, y NO se asigna ninguna otra cosa —prensa, buscadores, titulares, un
modelo con busqueda web, scrapers de portada— por muchas que coincidan.

El caso que la motiva esta abajo con nombres reales: al buscar el Athletic -
Atletico de Madrid, la prensa devolvia "Ortiz Arias" y la designacion del CTA
era Munuera Montero. Con la regla anterior —dos fuentes de prensa de acuerdo
bastaban— ese nombre se asignaba solo. Ahora se queda en candidato descartado.

Ninguna prueba sale a la red.

Ejecutar:  python test_politica_arbitro.py
"""

import io
import os
import sys

sys.path.insert(0, os.path.abspath("."))
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

from src.data import politica_arbitro as P
from src.data import investigador_web as IW
from src.logic import busqueda_arbitro as B

fallos = []


def check(nombre, cond):
    print(("  OK   " if cond else "  FALLA") + f"  {nombre}")
    if not cond:
        fallos.append(nombre)


print("\n== Solo pasa lo contrastado ==")
pasan = [
    ("registro del partido (API-Football)",
     {"name": "Jesús Gil Manzano", "estado": "VERIFICADO", "_is_fallback": False,
      "source": "API-Football (oficial)"}),
    ("oficiales del partido (football-data.org)",
     {"name": "Munuera Montero", "estado": "VERIFICADO", "_is_fallback": False,
      "source": "football-data.org (oficiales del partido)"}),
    ("fuente oficial con confianza ALTA",
     {"name": "Del Cerro Grande", "estado": "VERIFICADO", "_is_fallback": False,
      "confianza": "ALTA", "source": "rfef.es"}),
]
for nombre, ref in pasan:
    check(f"{nombre}: se asigna", P.es_contrastada(ref) is True)
    check(f"{nombre}: el filtro no lo toca", P.filtrar(ref) is ref)

print("\n== No pasa nada mas ==")
no_pasan = [
    ("prensa sin confirmar (PROBABLE)",
     {"name": "Ortiz Arias", "estado": "PROBABLE", "_is_fallback": True,
      "source": "Marca + AS"}),
    ("PROBABLE con la bandera mal puesta",
     {"name": "Ortiz Arias", "estado": "PROBABLE", "_is_fallback": False,
      "source": "Google News"}),
    ("VERIFICADO pero marcado como fallback",
     {"name": "Ortiz Arias", "estado": "VERIFICADO", "_is_fallback": True}),
    ("VERIFICADO con confianza BAJA",
     {"name": "Ortiz Arias", "estado": "VERIFICADO", "_is_fallback": False,
      "confianza": "BAJA"}),
    ("sin estado ninguno",
     {"name": "Ortiz Arias", "_is_fallback": False}),
    ("trozo de titular que parece nombre",
     {"name": "que no vio", "estado": "VERIFICADO", "_is_fallback": False}),
    ("nombre de club colado por la prensa",
     {"name": "LaLiga EA Sports", "estado": "VERIFICADO", "_is_fallback": False}),
    ("relleno de la cascada",
     {"name": "Por Detectar", "estado": "VERIFICADO", "_is_fallback": False}),
    ("nada en absoluto", None),
    ("diccionario vacio", {}),
]
for nombre, ref in no_pasan:
    check(f"{nombre}: NO se asigna", P.es_contrastada(ref) is False)
    salida = P.filtrar(ref)
    check(f"{nombre}: el campo queda vacio", salida["name"] == "")
    check(f"{nombre}: marcado como pendiente",
          salida["_is_fallback"] is True and salida["estado"] == "PENDIENTE")

print("\n== El candidato rechazado se guarda, no se tira ==")
salida = P.filtrar({"name": "Ortiz Arias", "estado": "PROBABLE", "_is_fallback": True,
                    "source": "Marca + AS",
                    "evidencias": [{"name": "Ortiz Arias", "fuente": "Marca",
                                    "url": "https://x", "oficial": False}],
                    "verification_link": "https://www.rfef.es"})
check("el nombre sale de 'name'", salida["name"] == "")
check("y queda en 'candidato_descartado'",
      salida.get("candidato_descartado") == "Ortiz Arias")
check("las evidencias se conservan para poder mirarlas",
      len(salida.get("evidencias") or []) == 1)
check("y el enlace de consulta tambien",
      salida.get("verification_link") == "https://www.rfef.es")
check("el motivo explica que falta confirmacion oficial",
      "oficial" in salida["motivo"].lower())

print("\n== El caso real: Athletic - Atletico ==")
# Dos medios de prensa de acuerdo. Con la regla anterior esto era VERIFICADO y
# se asignaba solo; era el agujero por el que entro un arbitro que no era.
hallazgos_prensa = [
    {"name": "Ortiz Arias", "fuente": "Marca", "url": "https://www.marca.com/x",
     "oficial": False, "extracto": "Ortiz Arias arbitrará el Athletic - Atlético",
     "anclaje": "fuerte"},
    {"name": "Ortiz Arias", "fuente": "AS", "url": "https://as.com/y",
     "oficial": False, "extracto": "Ortiz Arias, designado para el Athletic - Atlético",
     "anclaje": "fuerte"},
]
veredicto = IW._dictaminar(hallazgos_prensa, "La Liga")
check("dos medios de prensa ya NO son VERIFICADO",
      veredicto["estado"] == IW.PROBABLE)
check("y por tanto no se asigna solo", veredicto["_is_fallback"] is True)
check("el motivo dice que ninguna es oficial",
      "oficial" in veredicto["motivo"].lower())
check("la politica lo rechaza tambien en formato cascada",
      P.es_contrastada(IW.a_formato_cascada(veredicto)) is False)

# La misma noticia, pero firmada por el CTA: eso si se asigna.
hallazgos_oficiales = hallazgos_prensa + [
    {"name": "Munuera Montero", "fuente": "rfef.es",
     "url": "https://www.rfef.es/noticias/arbitros/designaciones",
     "oficial": True, "extracto": "Munuera Montero, designado para el Athletic - Atlético",
     "anclaje": "fuerte"},
]
veredicto_of = IW._dictaminar(hallazgos_oficiales, "La Liga")
check("con firma oficial si hay VERIFICADO",
      veredicto_of["estado"] == IW.VERIFICADO)
check("y gana el nombre del CTA, no el de la prensa",
      veredicto_of["name"] == "Munuera Montero")
check("la politica lo deja pasar",
      P.es_contrastada(IW.a_formato_cascada(veredicto_of)) is True)

print("\n== Un solo indicio de prensa sigue sin bastar ==")
uno = IW._dictaminar([hallazgos_prensa[0]], "La Liga")
check("PROBABLE", uno["estado"] == IW.PROBABLE)
check("no se asigna", P.es_contrastada(IW.a_formato_cascada(uno)) is False)

print("\n== La interfaz usa exactamente la misma regla ==")
for nombre, ref in no_pasan:
    check(f"{nombre}: la interfaz tampoco lo pinta",
          B.hay_designacion(ref) is False)
for nombre, ref in pasan:
    check(f"{nombre}: la interfaz si lo pinta", B.hay_designacion(ref) is True)

print("\n== De punta a punta: candidato rechazado -> campo limpio ==")
crudo = {"name": "Ortiz Arias", "estado": "PROBABLE", "_is_fallback": True,
         "source": "Marca + AS", "motivo": "Coinciden 2 fuentes de prensa"}
ficha, registro = B.buscar_designacion(lambda: P.filtrar(crudo), "La Liga (España)")
check("el campo del arbitro queda vacio", ficha["name"] == "")
check("se pide introducirlo a mano",
      ficha["mensaje_usuario"] == B.MENSAJE_MANUAL)
check("el log dice a quien se descarto y por que",
      any("Ortiz Arias" in linea for linea in registro))
check("el descarte viaja en la ficha para el supervisor",
      ficha.get("candidato_descartado") == "Ortiz Arias")

print("\n== El modelo nunca recibe un nombre sin confirmar ==")
# Es la consecuencia que importa: lo que la ficha del partido acaba usando.
for nombre, ref in no_pasan:
    ficha = P.filtrar(ref)
    usado = (ficha.get("name") or "").strip()
    check(f"{nombre}: no llega nombre al modelo", usado == "")

print("\n== Lo que escribe una persona si vale ==")
# Es la salida que ofrece el aviso, asi que tiene que pasar la politica: si no,
# el usuario teclearia el nombre y la aplicacion seguiria diciendo que falta.
manual = {"name": "Jesús Gil Manzano", "source": "Introducido manualmente",
          "_is_fallback": False, "estado": "VERIFICADO", "confianza": "ALTA"}
check("la entrada manual se acepta", P.es_contrastada(manual) is True)
check("y la interfaz la pinta", B.hay_designacion(manual) is True)
check("pero un club escrito a mano no cuela",
      P.es_contrastada({**manual, "name": "Real Madrid"}) is False)

print("\n== Ningun colegiado real de la base local se rechaza ==")
from src.data.referee_database import REFEREE_DB
rechazados = [n for n in REFEREE_DB if not P._nombre_util(n)]
check(f"los {len(REFEREE_DB)} nombres de la BD pasan el filtro", not rechazados)
if rechazados:
    print("   rechazados:", rechazados[:10])

print("\n" + ("TODO OK" if not fallos else f"FALLAN {len(fallos)}: {fallos}"))
sys.exit(1 if fallos else 0)
