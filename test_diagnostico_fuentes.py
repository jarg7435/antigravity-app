# -*- coding: utf-8 -*-
"""
Pruebas del diagnostico de conectividad de las fuentes.

El boton "Diagnosticar APIs" llamaba a MultiSourceFetcher.diagnose_connectivity,
que nunca se llego a escribir. Aqui se comprueba el metodo y, sobre todo, que
respeta el contrato que espera la barra lateral: un diccionario por fuente con
"status" y "detail", donde solo OK y LIMITED tienen color propio.

Las sondas se simulan: la prueba no sale a la red.

Ejecutar:  python test_diagnostico_fuentes.py
"""

import io
import os
import re
import sys

sys.path.insert(0, os.path.abspath("."))
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

from src.data import multi_source_fetcher as MSF

_fallos = []


def check(desc, cond):
    print(("  OK   " if cond else "  FALLA") + f"  {desc}")
    if not cond:
        _fallos.append(desc)


class _Respuesta:
    """Respuesta HTTP de mentira."""

    def __init__(self, status_code=200, texto="", json_data=None, contenido=b""):
        self.status_code = status_code
        self.text = texto
        self._json = json_data if json_data is not None else {}
        self.content = contenido

    def json(self):
        return self._json


# =============================================================================
print("--- 1. El metodo existe y respeta el contrato de la interfaz ---")

check("MultiSourceFetcher.diagnose_connectivity existe",
      hasattr(MSF.MultiSourceFetcher, "diagnose_connectivity"))

diag = MSF.MultiSourceFetcher().diagnose_connectivity(incluir=["Claude (búsqueda web)"])
check("devuelve un diccionario", isinstance(diag, dict))
check("con una entrada por fuente pedida", len(diag) == 1)
_info = next(iter(diag.values()))
check("cada entrada trae 'status' y 'detail'",
      isinstance(_info, dict) and "status" in _info and "detail" in _info)
check("y ambos son texto",
      isinstance(_info["status"], str) and isinstance(_info["detail"], str))

# La barra lateral pinta verde OK, ambar LIMITED y rojo cualquier otra cosa; y
# trata una clave "error" en el nivel superior como fallo del diagnostico.
check("no mete un 'error' de nivel superior cuando va bien", "error" not in diag)
check("los estados son los que la interfaz sabe pintar",
      MSF.OK == "OK" and MSF.LIMITED == "LIMITED")


# =============================================================================
print("\n--- 2. Cada sonda distingue sano, limitado y caido ---")

_get_original = None
_post_original = None
import requests as _req
_get_original, _post_original = _req.get, _req.post


def con_respuesta(resp=None, excepcion=None):
    """Sustituye requests.get/post por algo que responde lo que se le diga."""
    def _falso(*a, **k):
        if excepcion:
            raise excepcion
        return resp
    _req.get = _falso
    _req.post = _falso


# --- football-data.org
con_respuesta(_Respuesta(200))
check("football-data 200 -> OK", MSF._diag_football_data()["status"] == MSF.OK)
con_respuesta(_Respuesta(429))
check("football-data 429 -> LIMITED (se repone solo)",
      MSF._diag_football_data()["status"] == MSF.LIMITED)
con_respuesta(_Respuesta(403))
check("football-data 403 -> ERROR (llave rechazada)",
      MSF._diag_football_data()["status"] == MSF.ERROR)
con_respuesta(excepcion=OSError("sin red"))
_r = MSF._diag_football_data()
check(f"football-data sin red -> ERROR sin propagar ({_r['detail'][:28]}…)",
      _r["status"] == MSF.ERROR)

# --- SofaScore: el 200 vacio es el caso importante.
con_respuesta(_Respuesta(200, json_data={"results": [
    {"type": "event", "entity": {"homeTeam": {"name": "A"}, "awayTeam": {"name": "B"}}}]}))
check("SofaScore con partidos -> OK", MSF._diag_sofascore()["status"] == MSF.OK)
# Esta fuente estuvo meses devolviendo 200 sin un solo partido tras cambiar el
# formato del JSON. Un diagnostico que solo mire el codigo la da por sana.
con_respuesta(_Respuesta(200, json_data={"results": []}))
_r = MSF._diag_sofascore()
check(f"SofaScore 200 pero SIN partidos -> LIMITED ({_r['detail'][:40]}…)",
      _r["status"] == MSF.LIMITED)
con_respuesta(_Respuesta(503))
check("SofaScore 503 -> ERROR", MSF._diag_sofascore()["status"] == MSF.ERROR)

# --- Prensa (RSS)
con_respuesta(_Respuesta(200, contenido=b"<rss><channel><item><title>x</title></item></channel></rss>"))
check("prensa con titulares -> OK", MSF._diag_prensa_rss()["status"] == MSF.OK)
con_respuesta(_Respuesta(200, contenido=b"<rss><channel></channel></rss>"))
check("prensa sin titulares -> LIMITED",
      MSF._diag_prensa_rss()["status"] == MSF.LIMITED)
con_respuesta(_Respuesta(200, contenido=b"esto no es xml"))
check("prensa con XML roto -> ERROR sin reventar",
      MSF._diag_prensa_rss()["status"] == MSF.ERROR)

# --- Buscador web
con_respuesta(_Respuesta(200, texto='<div class="result">algo</div>'))
check("buscador con resultados -> OK", MSF._diag_buscador_web()["status"] == MSF.OK)
con_respuesta(_Respuesta(200, texto="pagina vacia"))
check("buscador sin resultados -> LIMITED",
      MSF._diag_buscador_web()["status"] == MSF.LIMITED)

# --- BeSoccer: bloquear al robot no es lo mismo que estar caido.
con_respuesta(_Respuesta(200))
check("besoccer 200 -> OK", MSF._diag_besoccer()["status"] == MSF.OK)
con_respuesta(_Respuesta(403))
check("besoccer 403 -> LIMITED (bloquea el acceso automatico)",
      MSF._diag_besoccer()["status"] == MSF.LIMITED)

_req.get, _req.post = _get_original, _post_original


# =============================================================================
print("\n--- 3. API-Football se apoya en el cortacircuitos ---")
from src.data import resiliencia_api as R

R.reiniciar()
R.registrar_averia(R.Averia.CUOTA, "cuota agotada")
_r = MSF._diag_api_football()
check(f"cuota agotada -> LIMITED, no rojo ({_r['detail'][:40]}…)",
      _r["status"] == MSF.LIMITED)

R.reiniciar()
R.registrar_averia(R.Averia.SUSCRIPCION, "llave rechazada")
_r = MSF._diag_api_football()
check("suscripcion caida -> ERROR", _r["status"] == MSF.ERROR)
check("y no sale a la red a confirmarlo (responde al instante)",
      "fuera de servicio" in _r["detail"] or "suscripción" in _r["detail"].lower())
R.reiniciar()


# =============================================================================
print("\n--- 4. Una sonda rota no tumba el diagnostico ---")


def _explota():
    raise RuntimeError("la sonda ha reventado")


_sondas_originales = MSF.SONDAS
MSF.SONDAS = (("Rota", _explota), ("Buena", lambda: MSF._estado(MSF.OK, "bien")))
diag = MSF.MultiSourceFetcher().diagnose_connectivity()
check("se informan las dos fuentes", len(diag) == 2)
check("la rota sale en rojo, no revienta", diag["Rota"]["status"] == MSF.ERROR)
check("y la buena sigue informandose", diag["Buena"]["status"] == MSF.OK)
MSF.SONDAS = _sondas_originales


# =============================================================================
print("\n--- 5. Se sondean las fuentes que usa la cascada ---")
nombres = [n for n, _ in MSF.SONDAS]
print("     ", " | ".join(nombres))
for esperada in ["SofaScore", "football-data.org", "API-Football (respaldo)"]:
    check(f"se diagnostica {esperada}", esperada in nombres)

fuente_main = io.open("app/main.py", encoding="utf-8").read()
check("la interfaz sigue llamando a diagnose_connectivity",
      "msf.diagnose_connectivity()" in fuente_main)


# =============================================================================
print("\n" + "=" * 62)
if _fallos:
    print(f"FALLOS: {len(_fallos)}")
    for f in _fallos:
        print(f"  - {f}")
    sys.exit(1)
print("Todas las comprobaciones han pasado.")
