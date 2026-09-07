# -*- coding: utf-8 -*-
"""
Pruebas del manejo de fallos de «Buscar Arbitro Auto».

Comprueban lo que motivo el encargo: en un partido de La Liga sin designacion
volcada todavia, el boton pintaba «Error en la busqueda: NameError...» en vez
de encaminar hacia el campo manual que la aplicacion ya tiene debajo.

Cubren los tres finales que hay que capturar limpiamente —timeout, resultado
vacio y competicion fuera del plan— mas el descuido de programacion, que era el
caso real de la captura. Ninguna prueba sale a la red.

Ejecutar:  python test_busqueda_arbitro.py
"""

import io
import os
import sys

sys.path.insert(0, os.path.abspath("."))
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

from src.logic import busqueda_arbitro as B
from src.data import resiliencia_api as R

fallos = []


def check(nombre, cond):
    print(("  OK   " if cond else "  FALLA") + f"  {nombre}")
    if not cond:
        fallos.append(nombre)


def revienta(exc):
    def _consultar():
        raise exc
    return _consultar


print("\n== Clasificacion de averias ==")
try:
    import requests
    _TIMEOUT_REAL = requests.exceptions.ReadTimeout(
        "HTTPSConnectionPool(host='api-football-v1.p.rapidapi.com', port=443): "
        "Read timed out. (read timeout=15)")
    _CONEXION_REAL = requests.exceptions.ConnectionError(
        "HTTPSConnectionPool(host='www.sofascore.com', port=443): Max retries exceeded")
except Exception:
    _TIMEOUT_REAL = TimeoutError("read timed out")
    _CONEXION_REAL = ConnectionError("Max retries exceeded")

casos = [
    ("timeout de requests", _TIMEOUT_REAL, B.Motivo.TIEMPO_AGOTADO),
    ("TimeoutError pelado", TimeoutError(), B.Motivo.TIEMPO_AGOTADO),
    ("timeout envuelto en RuntimeError", RuntimeError("SofaScore: read timed out"),
     B.Motivo.TIEMPO_AGOTADO),
    ("plan sin la competicion", RuntimeError("You are not subscribed to this API"),
     B.Motivo.FUERA_DE_PLAN),
    ("403 del proveedor", RuntimeError("HTTP 403 Forbidden"), B.Motivo.FUERA_DE_PLAN),
    ("cuota agotada", RuntimeError("429 rate limit exceeded"), B.Motivo.FUERA_DE_PLAN),
    ("liga fuera del plan de Sportmonks", ValueError("El plan no cubre 'La Liga'"),
     B.Motivo.FUERA_DE_PLAN),
    ("red caida", _CONEXION_REAL, B.Motivo.SIN_CONEXION),
    ("descuido de programacion", NameError("name 'match_datetime' is not defined"),
     B.Motivo.FALLO_FUENTE),
]
for nombre, exc, esperado in casos:
    check(f"{nombre} -> {esperado.value}", B.clasificar(exc) is esperado)

print("\n== Ninguna excepcion llega a la pantalla ==")
R.reiniciar()
for nombre, exc, esperado in casos:
    ficha, registro = B.buscar_designacion(revienta(exc), "La Liga (España)")
    ok = (ficha["_is_fallback"] is True
          and ficha["mensaje_usuario"] == B.MENSAJE_MANUAL
          and ficha["motivo_codigo"] == esperado.value
          and ficha["motivo"] == B.EXPLICACION[esperado])
    check(f"{nombre}: ficha limpia con aviso manual", ok)
    check(f"{nombre}: el detalle tecnico queda en el log",
          any(type(exc).__name__ in linea for linea in registro))

print("\n== El texto es el pedido, palabra por palabra ==")
check("mensaje exacto",
      B.MENSAJE_MANUAL == ("Árbitro no disponible en fuentes automáticas. "
                           "Por favor, introduzca el nombre manualmente en el campo inferior."))
check("y no se cuela el error crudo en el mensaje",
      "Error en la búsqueda" not in B.MENSAJE_MANUAL)

print("\n== Resultado vacio: se trata como no encontrado, no como arbitro ==")
vacios = [
    ("None", None),
    ("dict vacio", {}),
    ("nombre en blanco", {"name": "   ", "_is_fallback": False}),
    ("relleno 'Por Detectar'", {"name": "Por Detectar", "_is_fallback": False}),
    ("relleno 'No asignado'", {"name": "No asignado", "_is_fallback": False}),
    ("marcado como fallback", {"name": "Jesús Gil Manzano", "_is_fallback": True}),
]
for nombre, resultado in vacios:
    check(f"{nombre}: no cuenta como designacion", B.hay_designacion(resultado) is False)
    ficha, _ = B.buscar_designacion(lambda r=resultado: r, "La Liga (España)")
    check(f"{nombre}: aviso manual en pantalla",
          ficha["mensaje_usuario"] == B.MENSAJE_MANUAL
          and ficha["motivo_codigo"] == B.Motivo.SIN_DESIGNACION.value)

print("\n== Un arbitro de verdad pasa intacto ==")
bueno = {"name": "Jesús Gil Manzano", "source": "football-data.org (oficiales del partido)",
         "_is_fallback": False, "estado": "VERIFICADO"}
check("se reconoce", B.hay_designacion(bueno) is True)
ficha, registro = B.buscar_designacion(lambda: dict(bueno), "La Liga (España)")
check("mismo nombre y fuente",
      ficha["name"] == "Jesús Gil Manzano"
      and "football-data.org" in ficha["source"])
check("sin aviso de entrada manual", ficha["mensaje_usuario"] == "")
check("el log cuenta lo que hizo la cascada",
      any("football-data.org" in linea for linea in registro))

print("\n== Con API-Football caida se dice que es cosa del plan ==")
R.reiniciar()
R.registrar_averia(R.Averia.SUSCRIPCION, "plan caducado")
ficha, registro = B.buscar_designacion(lambda: {}, "La Liga (España)")
check("motivo: fuera del plan, no 'aun no publicada'",
      ficha["motivo_codigo"] == B.Motivo.FUERA_DE_PLAN.value)
check("la degradacion viaja con la ficha",
      (ficha.get("degradacion") or {}).get("degradada") is True)
check("y el log lo explica", any("API-Football" in linea for linea in registro))
R.reiniciar()

print("\n== La ficha trae todo lo que la interfaz pinta ==")
ficha, _ = B.buscar_designacion(revienta(TimeoutError()), "La Liga (España)")
for clave in ("name", "source", "verification_link", "_is_fallback", "estado",
              "motivo", "motivo_codigo", "mensaje_usuario", "degradacion"):
    check(f"clave '{clave}'", clave in ficha)
check("el enlace de consulta manual apunta a algun sitio",
      str(ficha["verification_link"]).startswith("http"))

print("\n" + ("TODO OK" if not fallos else f"FALLAN {len(fallos)}: {fallos}"))
sys.exit(1 if fallos else 0)
