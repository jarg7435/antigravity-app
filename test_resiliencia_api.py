# -*- coding: utf-8 -*-
"""
Pruebas del cortacircuitos de API-Football y del desvio a fuentes secundarias.

Comprueban lo que motivo el encargo: con la suscripcion caducada o la cuota
agotada, la aplicacion tiene que seguir dando arbitro y fechas desde SofaScore,
football-data.org y la prensa, sin colgarse esperando a una API que ya sabemos
que no va a contestar.

Los casos de clasificacion son las respuestas REALES de API-Football, copiadas
de sus cuerpos JSON, no inventadas. Ninguna prueba sale a la red.

Ejecutar:  python test_resiliencia_api.py
"""

import io
import os
import sys

sys.path.insert(0, os.path.abspath("."))
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

from src.data import resiliencia_api as R
from src.data import cascada
from datetime import date, timedelta

fallos = []


def check(nombre, cond):
    print(("  OK   " if cond else "  FALLA") + f"  {nombre}")
    if not cond:
        fallos.append(nombre)


print("\n== Clasificacion de respuestas ==")
A = R.Averia
casos = [
    # (nombre, status, errors, cuerpo, esperado)
    ("200 correcto", 200, [], {"response": [1, 2]}, None),
    ("cuota agotada (errors.requests)", 200,
     {"requests": "You have reached the request limit for the day"}, {}, A.CUOTA),
    ("429 too many requests", 429, {}, {}, A.CUOTA),
    ("token invalido", 200, {"token": "invalid api key"}, {}, A.SUSCRIPCION),
    ("RapidAPI no suscrito", 403, {}, {"message": "You are not subscribed to this API."},
     A.SUSCRIPCION),
    ("401 sin autorizar", 401, {}, {}, A.SUSCRIPCION),
    ("suscripcion caducada", 200, {"subscription": "Your subscription has expired"}, {},
     A.SUSCRIPCION),
    ("plan gratuito sin esa fecha", 200,
     {"plan": "Free plans do not have access to this date, try from 2026-09-05"},
     {"response": []}, None),
    ("falta el campo season", 200, {"season": "The Season field is required."},
     {"response": []}, None),
    ("499 timeout de la API", 499, {}, {}, A.TRANSITORIA),
    ("502 caida del servidor", 502, {}, {}, A.TRANSITORIA),
    ("200 con cuerpo vacio", 200, {}, {}, A.TRANSITORIA),
]
for nombre, sc, err, cuerpo, esperado in casos:
    got = R.clasificar_respuesta(status_code=sc, errors=err, cuerpo=cuerpo)
    check(f"{nombre}: {got} == {esperado}", got == esperado)

print("\n== Apertura del circuito ==")
R.reiniciar()
check("arranca disponible", R.disponible())

# Suscripcion: abre a la primera.
R.registrar_averia(A.SUSCRIPCION, "token rechazado")
check("suscripcion abre a la primera", not R.disponible())
check("motivo menciona la suscripcion", "suscripción" in (R.motivo() or "").lower())
check("resumen marca degradada", R.resumen()["degradada"] is True)
check("texto_estado explica el desvio", "SofaScore" in R.texto_estado())

# Un exito lo cierra: suscripcion renovada sin reiniciar la app.
R.registrar_exito()
check("un exito cierra el circuito", R.disponible())

print("\n== Tolerancia a fallos pasajeros ==")
R.reiniciar()
abierto1 = R.registrar_averia(A.TRANSITORIA, "timeout")
abierto2 = R.registrar_averia(A.TRANSITORIA, "timeout")
check("un timeout suelto no apaga la fuente", not abierto1 and R.disponible())
check("dos timeouts tampoco", not abierto2 and R.disponible())
abierto3 = R.registrar_averia(A.TRANSITORIA, "timeout")
check("al tercero si", abierto3 and not R.disponible())

print("\n== Cuota: espera hasta el reset diario ==")
R.reiniciar()
R.registrar_averia(A.CUOTA, "limite diario")
res = R.resumen()
check("cuota deja el circuito abierto", not R.disponible())
check("espera a medianoche UTC", res["hasta"].endswith("00:00:00+00:00"))

print("\n== La espera vence sola ==")
R.reiniciar()
R.registrar_averia(A.SUSCRIPCION, "x")
from datetime import datetime, timezone
R._ESTADO.hasta = datetime.now(timezone.utc) - timedelta(seconds=1)
check("vencida la espera, vuelve a probarse", R.disponible())
check("y el estado queda limpio", R.averia_actual() is None)

print("\n== Desvio automatico en la cascada ==")
R.reiniciar()
hoy = date.today()
tipo_hoy = cascada.clasificar(hoy)
check("con la API sana, hoy entra en su ventana",
      cascada.api_football_puede_responder(tipo_hoy, fecha=hoy))
check("en vivo tambien", cascada.api_football_puede_responder(cascada.TipoConsulta.EN_VIVO))

R.registrar_averia(A.SUSCRIPCION, "caducada")
check("degradada: se descarta hoy",
      not cascada.api_football_puede_responder(tipo_hoy, fecha=hoy))
check("degradada: se descarta el directo",
      not cascada.api_football_puede_responder(cascada.TipoConsulta.EN_VIVO))
check("degradada: se descarta el historico por temporada",
      not cascada.api_football_puede_responder(cascada.TipoConsulta.HISTORICO, temporada=2023))
desc = cascada.describe(tipo_hoy)
check(f"describe() saca a la API del orden: {desc!r}",
      "api_football" not in desc and "fuera de servicio" in desc)

print("\n== El cliente no toca la red con el circuito abierto ==")
R.reiniciar()
R.registrar_averia(A.SUSCRIPCION, "caducada")
from src.data.api_football import APIFootballClient, APIFootballNoDisponible
import time
cli = APIFootballClient(api_key="clave_de_prueba_1234567890")
t0 = time.time()
try:
    cli._request("fixtures", {"date": "2026-09-06"})
    check("deberia haber lanzado APIFootballNoDisponible", False)
except APIFootballNoDisponible as e:
    tardanza = time.time() - t0
    check(f"corta al instante sin salir a la red ({tardanza*1000:.1f} ms)", tardanza < 0.5)
    check("el mensaje explica el desvio", "SofaScore" in str(e))
except Exception as e:
    check(f"excepcion inesperada: {type(e).__name__}: {e}", False)

print("\n== La cache sigue sirviendo con el circuito abierto ==")
R.reiniciar()
cli2 = APIFootballClient(api_key="clave_de_prueba_1234567890")
cli2._cache.set("fixtures_today", "guardado", {"response": ["cacheado"]}, "api_football", 600)
R.registrar_averia(A.SUSCRIPCION, "caducada")
try:
    d = cli2._request("fixtures", {}, cache_category="fixtures_today", cache_id="guardado")
    check("lo ya cacheado se sirve igual", d == {"response": ["cacheado"]})
except Exception as e:
    check(f"la cache deberia responder, pero: {type(e).__name__}", False)

print("\n== multi_source_fetcher no entrega cliente degradado ==")
R.reiniciar()
from src.data import multi_source_fetcher as MSF
R.registrar_averia(A.CUOTA, "cuota agotada")
check("no devuelve cliente", MSF._get_api_football_client() is None)
estado = MSF.get_source_status().get("API-Football", {})
check("y lo registra para el panel", estado.get("ok") is False and "cuota" in (estado.get("motivo") or "").lower())

R.reiniciar()
print("\n" + ("TODO OK" if not fallos else f"FALLAN {len(fallos)}: {fallos}"))
sys.exit(1 if fallos else 0)
