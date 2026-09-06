# -*- coding: utf-8 -*-
"""
Pruebas de la sincronizacion automatica de resultados.

Lo que se comprueba es lo que puede salir caro: que NO se vuelque un marcador
equivocado. Un resultado erroneo es peor que ninguno, porque entra en la base,
alimenta la calibracion y ensucia el modelo sin que nadie lo note.

Las fuentes se simulan para que la prueba no dependa de la red ni de las claves.

Ejecutar:  python test_resultados_auto.py
"""

import io
import os
import shutil
import sqlite3
import sys
import tempfile
from datetime import datetime, timedelta

sys.path.insert(0, os.path.abspath("."))
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

from src.data import resultados_auto as RA

_fallos = []


def check(desc, cond):
    print(("  OK   " if cond else "  FALLA") + f"  {desc}")
    if not cond:
        _fallos.append(desc)


# =============================================================================
print("--- 1. Cotejo de nombres de equipo ---")
# El riesgo esta en los clubes que comparten la primera palabra: con una
# coincidencia suelta bastaba para hermanar Real Madrid con Real Sociedad.
for a, b, esperado in [
    ("Real Madrid", "Real Madrid CF", True),
    ("Alavés", "Deportivo Alavés", True),
    ("Atletico Madrid", "Club Atlético de Madrid", True),
    ("RAYO VALLECANO", "Rayo Vallecano", True),
    ("Celta de Vigo", "RC Celta de Vigo", True),
    ("Osasuna", "CA Osasuna", True),
    ("Real Madrid", "Real Sociedad", False),
    ("Real Madrid", "Real Betis", False),
    ("Real Madrid", "Club Atlético de Madrid", False),
    ("Athletic Club", "Club Atlético de Madrid", False),
]:
    check(f"{a!r} == {b!r} -> {esperado}", RA.mismo_equipo(a, b) is esperado)


# =============================================================================
print("\n--- 2. Un partido no ha terminado hasta que ha terminado ---")
ahora = datetime(2026, 9, 6, 20, 0)
for fecha, esperado, nota in [
    (datetime(2026, 9, 6, 21, 0), False, "empieza dentro de una hora"),
    (datetime(2026, 9, 6, 19, 30), False, "acaba de empezar"),
    (datetime(2026, 9, 6, 17, 0), True, "empezo hace tres horas"),
    (datetime(2026, 9, 5, 21, 0), True, "fue ayer"),
    ("2026-09-05T21:00:00", True, "fecha en texto ISO"),
    ("2026-09-06", True, "solo fecha, sin hora"),
    (None, False, "sin fecha no se pregunta"),
    ("", False, "fecha vacia"),
    ("no es una fecha", False, "fecha ilegible"),
]:
    check(f"{nota} -> terminado={esperado}",
          RA.ya_termino(fecha, ahora) is esperado)


# =============================================================================
print("\n--- 3. Lo que NO debe darse por bueno ---")

FECHA = datetime(2026, 2, 6, 21, 0)


def fuente_falsa(respuesta):
    """Sustituye las dos fuentes por una que responde lo que se le diga."""
    RA.FUENTES = (("prueba", lambda *a, **k: respuesta),)


_originales = RA.FUENTES

# 3a. Partido invertido: el hallado es el de la vuelta.
# Caso real: buscando "Alavés - Athletic", SofaScore devuelve el
# "Athletic - Alavés" de la otra jornada, que es otro partido con otro
# marcador. Sin comprobar la orientacion, ese resultado entraba del reves.
import src.data.scrapers.sofascore_api as _sofa

_find_original = _sofa._find_event


def _evento(local, visitante, estado="finished", gh=2, ga=0):
    return {"homeTeam": {"name": local}, "awayTeam": {"name": visitante},
            "status": {"type": estado},
            "homeScore": {"display": gh}, "awayScore": {"display": ga},
            "startTimestamp": None}


# El de la vuelta: mismos equipos, lados cambiados.
_sofa._find_event = lambda h, a, f=None, **k: _evento("Athletic Club", "Deportivo Alavés")
check("un partido con los lados cambiados se rechaza",
      RA.buscar_en_sofascore("Alavés", "Athletic Club", FECHA) is None)

# El nuestro, en el orden correcto.
_sofa._find_event = lambda h, a, f=None, **k: _evento("Deportivo Alavés", "Athletic Club")
_ok = RA.buscar_en_sofascore("Alavés", "Athletic Club", FECHA)
check("y el que tiene los lados bien se acepta", _ok is not None)
check(f"con el marcador del lado correcto {_ok}",
      _ok and _ok["home_score"] == 2 and _ok["away_score"] == 0)

# Un partido en juego tiene marcador, pero no el definitivo.
_sofa._find_event = lambda h, a, f=None, **k: _evento(
    "Deportivo Alavés", "Athletic Club", estado="inprogress", gh=1, ga=0)
check("un partido en juego no se da por terminado",
      RA.buscar_en_sofascore("Alavés", "Athletic Club", FECHA) is None)

_sofa._find_event = _find_original

# 3b. Fecha que no corresponde: es otro enfrentamiento entre los mismos.
fuente_falsa({"home_score": 3, "away_score": 0, "fuente": "prueba",
              "fecha": "2026-05-20T21:00:00"})
r = RA.buscar_resultado("x", "Celta de Vigo", "Osasuna", FECHA, "La Liga")
check("un marcador de otra fecha se descarta", r is None)

# 3c. Fecha compatible: se acepta.
fuente_falsa({"home_score": 1, "away_score": 2, "fuente": "prueba",
              "fecha": "2026-02-06T21:00:00"})
r = RA.buscar_resultado("x", "Celta de Vigo", "Osasuna", FECHA, "La Liga")
check("un marcador de la fecha correcta se acepta", r is not None)
check("y el ganador se deduce bien", r and r.winner == "VISITANTE")

# 3d. Una fuente que no encuentra nada no inventa.
fuente_falsa(None)
check("sin datos no se devuelve nada",
      RA.buscar_resultado("x", "A", "B", FECHA, "La Liga") is None)

# 3e. Una fuente que revienta no tumba la busqueda.
def _explota(*a, **k):
    raise RuntimeError("la fuente ha fallado")
RA.FUENTES = (("rota", _explota),)
check("una fuente rota se salta sin propagar el error",
      RA.buscar_resultado("x", "A", "B", FECHA, "La Liga") is None)

RA.FUENTES = _originales


# =============================================================================
print("\n--- 4. Volcado completo sobre una base temporal ---")

tmp = tempfile.mkdtemp()
ruta = os.path.join(tmp, "sync.db")

from src.data.db_manager import DataManager
from src.logic.bpa_engine import BPAEngine
from src.logic.learning_engine import LearningEngine
from src.models.base import (Match, MatchConditions, PredictionResult, Referee,
                             Team)

db = DataManager(db_path=ruta)
le = LearningEngine(BPAEngine(), db)

AYER = datetime.now() - timedelta(days=1)
MANANA = datetime.now() + timedelta(days=1)

for mid, home, away, fecha in [
    ("jugado", "Celta de Vigo", "Osasuna", AYER),
    ("futuro", "Real Madrid", "FC Barcelona", MANANA),
]:
    db.save_match(Match(id=mid, home_team=Team(name=home, league="La Liga"),
                        away_team=Team(name=away, league="La Liga"),
                        date=fecha, competition="La Liga",
                        conditions=MatchConditions(), referee=Referee(name="X")))
    db.save_prediction(PredictionResult(
        match_id=mid, bpa_home=.5, bpa_away=.5,
        win_prob_home=.5, draw_prob=.3, win_prob_away=.2,
        total_goals_expected=2.4, both_teams_to_score_prob=.5,
        lambda_home=1.4, lambda_away=1.0,
        predicted_corners="🏠 4-6 | ✈️ 3-5", predicted_cards="🏠 2-4 | ✈️ 2-3",
        predicted_shots="🏠 10-14 | ✈️ 8-12"))

fuente_falsa({"home_score": 1, "away_score": 2, "fuente": "prueba", "fecha": ""})
inf = RA.sincronizar(db, le)
RA.FUENTES = _originales

print("   ", inf.resumen())
check("revisa los dos estudios", inf.pendientes == 2)
check("no toca el partido de mañana", inf.sin_jugar == 1)
check("vuelca uno solo", inf.guardados == 1)
check("sin errores", not inf.errores)

fila = sqlite3.connect(ruta).execute(
    "SELECT home_score, away_score, winner, corners, cards, shots "
    "FROM resultados WHERE match_id='jugado'").fetchone()
check(f"el marcador se guarda bien {fila[:3]}", fila[:3] == (1, 2, "VISITANTE"))
# Un cero diria "se midio y salio cero", y el semaforo lo pintaria como fallo
# en un mercado que nadie llego a medir.
check("cornes, tarjetas y remates quedan SIN MEDIR, no a cero",
      fila[3] is None and fila[4] is None and fila[5] is None)

apr = sqlite3.connect(ruta).execute(
    "SELECT mercado FROM aprendizaje WHERE match_id='jugado'").fetchall()
check(f"solo se aprende del 1X2, que es lo comprobado {apr}",
      apr == [("1X2",)])

sem = db.get_semaforo_history(limit=5)
mercados = sem[0]["mercados"] if sem else {}
check(f"el semaforo no inventa fallos de corners {list(mercados)}",
      list(mercados) == ["1X2"])

print("\n--- 5. Idempotencia: no se vuelca dos veces ---")
fuente_falsa({"home_score": 4, "away_score": 4, "fuente": "prueba", "fecha": ""})
inf2 = RA.sincronizar(db, le)
RA.FUENTES = _originales
check("el ya volcado desaparece de los pendientes", inf2.pendientes == 1)
check("y no se vuelve a guardar", inf2.guardados == 0)
fila2 = sqlite3.connect(ruta).execute(
    "SELECT home_score, away_score FROM resultados WHERE match_id='jugado'").fetchone()
check(f"el marcador original se respeta {fila2}", fila2 == (1, 2))

shutil.rmtree(tmp, ignore_errors=True)


# =============================================================================
print("\n--- 6. Estudios guardados con el vocabulario antiguo ---")
# Los estudios de versiones anteriores usaban otros nombres de campo y no
# cargaban: fallaban por total_goals_expected, que antes era total_goals_xg.
# Sin traducirlos, el bucle de aprendizaje se quedaba sin historial.
from src.data.db_manager import _traducir_prediccion_antigua
from src.models.base import PredictionResult as PR

ANTIGUA = {
    "match_id": "viejo", "bpa_home": 0.5, "bpa_away": 0.5,
    "win_prob_home": 0.41, "draw_prob": 0.30, "win_prob_away": 0.29,
    "both_teams_to_score_prob": 0.5,
    "total_goals_xg": 2.6,                    # antes se llamaba asi
    "confidence_level": "Medium",             # era una etiqueta, no un numero
    "predicted_goals_home": [1.0, 2.0],       # era un RANGO, no un valor
    "predicted_goals_away": [0.0, 1.0],
    "predicted_corners_home": "4-6", "predicted_corners_away": "3-5",
}
t = _traducir_prediccion_antigua(ANTIGUA)
check(f"total_goals_xg -> total_goals_expected ({t.get('total_goals_expected')})",
      t.get("total_goals_expected") == 2.6)
check(f"la etiqueta de confianza pasa a numero ({t.get('confidence_score')})",
      isinstance(t.get("confidence_score"), float))
check(f"el rango de goles da su centro ({t.get('lambda_home')})",
      t.get("lambda_home") == 1.5)
check("los corners se recomponen en una cadena",
      "4-6" in str(t.get("predicted_corners")))
try:
    cargada = PR(**t)
    check("la prediccion antigua ya carga", cargada.total_goals_expected == 2.6)
except Exception as e:
    check(f"la prediccion antigua ya carga ({type(e).__name__})", False)

# Y una prediccion actual no se toca.
ACTUAL = {"match_id": "n", "bpa_home": .5, "bpa_away": .5, "win_prob_home": .4,
          "draw_prob": .3, "win_prob_away": .3, "total_goals_expected": 2.4,
          "both_teams_to_score_prob": .5, "lambda_home": 1.4, "lambda_away": 1.0}
check("una prediccion actual pasa intacta",
      _traducir_prediccion_antigua(ACTUAL)["lambda_home"] == 1.4)


# =============================================================================
print("\n" + "=" * 62)
if _fallos:
    print(f"FALLOS: {len(_fallos)}")
    for f in _fallos:
        print(f"  - {f}")
    sys.exit(1)
print("Todas las comprobaciones han pasado.")
