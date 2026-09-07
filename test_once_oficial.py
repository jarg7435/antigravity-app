# -*- coding: utf-8 -*-
"""
Pruebas del conector de Sportmonks y del recalculo por once oficial.

Las dos mejoras del ultimo encargo:

  1. Sportmonks como via complementaria de designaciones. Lo importante aqui es
     que se aparte cuando el plan no cubre la competicion: solo da acceso a la
     Superliga danesa y a la Premiership escocesa, asi que en LaLiga no puede
     aportar nada y gastar una peticion para comprobarlo seria tirar cuota.

  2. Recalculo de piezas criticas al confirmar el once oficial. Lo que se
     comprueba es que corrige lo que depende del once y NO toca lo que costo
     salir a la red.

No se sale a la red: la API se simula.

Ejecutar:  python test_once_oficial.py
"""

import io
import os
import sys
from datetime import datetime

sys.path.insert(0, os.path.abspath("."))
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

_fallos = []


def check(desc, cond):
    print(("  OK   " if cond else "  FALLA") + f"  {desc}")
    if not cond:
        _fallos.append(desc)


# =============================================================================
print("--- 1. Sportmonks: que cubre el plan y que no ---")

from src.data import sportmonks_arbitros as SM

# Cobertura real, tal cual la devuelve la API con la llave configurada.
SM._LIGAS_CUBIERTAS = {
    "Superliga": 271, "Premiership": 501,
    "Premiership Play-Offs": 513, "Superliga Play-offs": 1659,
}

for liga, esperado in [
    ("Scottish Premiership (Escocia)", 501),
    ("Superliga (Dinamarca)", 271),
    ("La Liga (España)", None),
    ("Premier League (Inglaterra)", None),   # ojo: NO debe casar con Premiership
    ("Serie A (Italia)", None),
    ("Bundesliga (Alemania)", None),
    ("", None),
]:
    check(f"{liga or '(vacío)':32} -> {esperado}", SM.cubre(liga) == esperado)

# La liga regular gana a su eliminatoria: si no, un partido de temporada normal
# se buscaria en el cuadro de play-offs.
check("la liga regular gana al play-off", SM.cubre("Premiership") == 501)


print("\n--- 2. Sportmonks: lectura de la designación ---")

FIXTURE = {
    "id": 19713942,
    "name": "Rangers vs St. Mirren",
    "participants": [{"name": "St. Mirren"}, {"name": "Rangers"}],
    "referees": [
        {"type_id": 7, "referee": {"display_name": "Calum Spence"}},   # asistente
        {"type_id": 6, "referee": {"display_name": "Don Robertson"}},  # principal
        {"type_id": 8, "referee": {"display_name": "Ross Anderson"}},
    ],
}

check("se coge al principal (type_id 6), no al primero de la lista",
      SM._arbitro_principal(FIXTURE) == "Don Robertson")
check("un fixture sin designar devuelve None",
      SM._arbitro_principal({"referees": []}) is None)
check("y uno con solo asistentes tambien",
      SM._arbitro_principal({"referees": [{"type_id": 7,
                                           "referee": {"display_name": "X"}}]}) is None)

# El orden de los participantes lo decide la API, no nosotros: exigir que el
# local vaya primero descartaria partidos validos.
check("reconoce el partido aunque los equipos vengan al revés",
      SM._es_nuestro_partido(FIXTURE, "Rangers", "St. Mirren"))
check("y en el orden natural también",
      SM._es_nuestro_partido(FIXTURE, "St. Mirren", "Rangers"))
check("un partido de otros equipos no cuela",
      not SM._es_nuestro_partido(FIXTURE, "Celtic", "Hearts"))


print("\n--- 3. Sportmonks no gasta una petición fuera de su plan ---")

_llamadas = {"n": 0}


class _ClienteEspia:
    def get_fixtures_con_arbitros(self, d1, d2, liga_id=None):
        _llamadas["n"] += 1
        return [FIXTURE]


_cliente_original = SM._cliente
SM._cliente = lambda: _ClienteEspia()

r = SM.buscar_arbitro("Alavés", "Athletic Club", datetime(2026, 9, 6), "La Liga (España)")
check("LaLiga: devuelve None...", r is None)
check("...y NO llega a consultar la API", _llamadas["n"] == 0)

r = SM.buscar_arbitro("Rangers", "St. Mirren", datetime(2026, 9, 9),
                      "Scottish Premiership (Escocia)")
check("Escocia: sí consulta", _llamadas["n"] == 1)
check(f"y devuelve al árbitro ({r['name'] if r else None})",
      r and r["name"] == "Don Robertson")
check("marcado como VERIFICADO (es la designación del partido)",
      r and r["estado"] == "VERIFICADO" and r["_is_fallback"] is False)

SM._cliente = _cliente_original


# =============================================================================
print("\n--- 4. Recálculo por once oficial ---")

from src.data.mock_provider import MockDataProvider
from src.logic.bpa_engine import BPAEngine
from src.logic.predictors import Predictor
from src.models.base import Match, MatchConditions, Referee

prov = MockDataProvider()
local, visit = prov.teams_db["Athletic Club"], prov.teams_db["Alavés"]
once_local = [p.name for p in local.players]
once_visit = [p.name for p in visit.players]

partido = Match(id="t", home_team=local.model_dump(), away_team=visit.model_dump(),
                date=datetime(2026, 9, 6, 21, 0), competition="La Liga",
                conditions=MatchConditions(), referee=Referee(name="X"))

motor = Predictor(BPAEngine())
base = motor.predict_match(partido, once_local=once_local, once_visitante=once_visit)

# Se cae el portero local una hora antes.
portero = next(p for p in local.players if p.node_role.value == "Portero")
sin_portero = [n for n in once_local if n != portero.name] + ["Suplente X"]

nueva, cambios = motor.recalcular_por_once(base, partido, sin_portero, once_visit)

print(f"      antes:  λ {base.lambda_home:.3f}-{base.lambda_away:.3f}  conf {base.confidence_score}")
print(f"      ahora:  λ {nueva.lambda_home:.3f}-{nueva.lambda_away:.3f}  conf {nueva.confidence_score}")

check("el recálculo se aplica", cambios["aplicado"])
check(f"detecta al portero ausente ({cambios.get('ausentes')})",
      portero.name in (cambios.get("ausentes") or []))
check("el visitante marca MÁS sin el portero local",
      nueva.lambda_away > base.lambda_away)
check("el local marca IGUAL (no era su ataque)",
      abs(nueva.lambda_home - base.lambda_home) < 1e-6)
check("la confianza BAJA", nueva.confidence_score < base.confidence_score)
check("las probabilidades siguen sumando 1",
      abs(nueva.win_prob_home + nueva.draw_prob + nueva.win_prob_away - 1.0) < 0.02)

# Lo caro es la red: el analisis de prensa y los BPA que salen de el no se
# rehacen, porque las bajas ya estaban contadas y no cambian al publicarse el
# once. Si esto se tocara, el recalculo "ligero" no seria ligero.
check("NO se rehace el análisis de prensa",
      nueva.external_analysis_summary == base.external_analysis_summary)
check("NI los BPA, que salen de ese análisis",
      nueva.bpa_home == base.bpa_home and nueva.bpa_away == base.bpa_away)
check("el estudio original no se modifica (se trabaja sobre copia)",
      base.confidence_score != nueva.confidence_score
      and base.lambda_away != nueva.lambda_away)


print("\n--- 5. El recálculo es idempotente y reversible ---")
# Volver a aplicar el MISMO once no debe mover nada mas: los coeficientes viejos
# se dividen, no se acumulan. Sin eso, cada confirmacion penalizaria otra vez.
otra, _ = motor.recalcular_por_once(nueva, partido, sin_portero, once_visit)
check(f"repetirlo no vuelve a penalizar ({otra.lambda_away:.3f})",
      abs(otra.lambda_away - nueva.lambda_away) < 1e-6)

# Y si aparece el once completo, se vuelve al punto de partida.
vuelta, _ = motor.recalcular_por_once(nueva, partido, once_local, once_visit)
check(f"con el once completo se vuelve al original ({vuelta.lambda_away:.3f})",
      abs(vuelta.lambda_away - base.lambda_away) < 1e-6)


print("\n--- 6. Lo que no se puede recalcular se dice, no se inventa ---")
_, c = motor.recalcular_por_once(base, partido, [], [])
check(f"sin once comparable no se toca nada ({c['motivo']})", not c["aplicado"])

viejo = base.model_copy(deep=True)
viejo.lambda_home = 0.0
viejo.lambda_away = 0.0
_, c = motor.recalcular_por_once(viejo, partido, sin_portero, once_visit)
check(f"un estudio sin λ guardados lo dice ({c['motivo'][:44]}…)", not c["aplicado"])

_, c = motor.recalcular_por_once(None, partido, sin_portero, once_visit)
check("sin estudio previo no revienta", not c["aplicado"])


# =============================================================================
print("\n" + "=" * 62)
if _fallos:
    print(f"FALLOS: {len(_fallos)}")
    for f in _fallos:
        print(f"  - {f}")
    sys.exit(1)
print("Todas las comprobaciones han pasado.")
