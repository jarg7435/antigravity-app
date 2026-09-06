# -*- coding: utf-8 -*-
"""
Pruebas de la penalizacion dinamica por ausencias criticas.

Comprueban lo que motivo el modulo: que el once confirmado de ultima hora mueva
de verdad el pronostico, y que lo mueva en la direccion correcta —que falte el
portero sube los goles del RIVAL, que falte el delantero baja los PROPIOS—, sin
penalizar nunca por no tener datos.

Ejecutar:  python test_ausencias.py
"""
import io, os, sys
sys.path.insert(0, os.path.abspath("."))
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

from datetime import datetime
from src.data.mock_provider import MockDataProvider
from src.logic import ausencias as A
from src.logic.bpa_engine import BPAEngine
from src.logic.predictors import Predictor
from src.models.base import Match, MatchConditions, Referee

fallos = []
def check(d, c):
    print(("  OK   " if c else "  FALLA") + f"  {d}")
    if not c: fallos.append(d)

prov = MockDataProvider()
local = prov.teams_db["Athletic Club"]
visit = prov.teams_db["Alavés"]
once_local = [p.name for p in local.players]
once_visit = [p.name for p in visit.players]

print("Once local previsto:", ", ".join(once_local))
print("Roles:", ", ".join(f"{p.name}={p.node_role.value}" for p in local.players[:3]))

print("\n== 1. Once completo: no penaliza ==")
inf = A.evaluar(local, once_local)
check("comparable", inf.comparable)
check("sin ausentes", not inf.hay_ausencias)
check(f"coef_ataque neutro ({inf.coef_ataque})", inf.coef_ataque == 1.0)
check(f"coef_encaje neutro ({inf.coef_encaje})", inf.coef_encaje == 1.0)

print("\n== 2. Falta el PORTERO: sube el encaje, no baja el ataque ==")
portero = next(p for p in local.players if p.node_role.value == "Portero")
sin_portero = [n for n in once_local if n != portero.name]
sin_portero.append("Suplente Cualquiera")   # entra el suplente, siguen siendo 11
inf_gk = A.evaluar(local, sin_portero)
print("   ", inf_gk.resumen())
check(f"detecta al portero ({portero.name})",
      any(a.nombre == portero.name for a in inf_gk.ausentes))
check(f"coef_encaje > 1 ({inf_gk.coef_encaje:.3f})", inf_gk.coef_encaje > 1.0)
check(f"coef_ataque intacto ({inf_gk.coef_ataque:.3f})", inf_gk.coef_ataque == 1.0)
check("baja la confianza", inf_gk.penalizacion_confianza > 0)

print("\n== 3. Falta un DELANTERO: baja el ataque, no sube el encaje ==")
delantero = next(p for p in local.players if p.node_role.value == "Finalizador")
sin_del = [n for n in once_local if n != delantero.name] + ["Suplente Cualquiera"]
inf_d = A.evaluar(local, sin_del)
print("   ", inf_d.resumen())
check(f"coef_ataque < 1 ({inf_d.coef_ataque:.3f})", inf_d.coef_ataque < 1.0)
check(f"coef_encaje intacto ({inf_d.coef_encaje:.3f})", inf_d.coef_encaje == 1.0)

print("\n== 4. Sin once confirmado: NO se penaliza ==")
for caso, once in [("None", None), ("vacio", []), ("solo 3", once_local[:3])]:
    i = A.evaluar(local, once)
    check(f"{caso}: comparable=False y coeficientes neutros",
          (not i.comparable) and i.coef_ataque == 1.0 and i.coef_encaje == 1.0
          and i.penalizacion_confianza == 0.0)

print("\n== 5. Topes: aunque falte el equipo entero ==")
inf_x = A.evaluar(local, ["Fulano %d" % i for i in range(11)])
print(f"    ausentes={len(inf_x.ausentes)} ataque={inf_x.coef_ataque:.3f} encaje={inf_x.coef_encaje:.3f}")
check(f"coef_ataque no baja de {A.COEF_ATAQUE_MIN}", inf_x.coef_ataque >= A.COEF_ATAQUE_MIN)
check(f"coef_encaje no sube de {A.COEF_ENCAJE_MAX}", inf_x.coef_encaje <= A.COEF_ENCAJE_MAX)
check(f"penalizacion acotada a {A.PENALIZACION_CONFIANZA_MAX}",
      inf_x.penalizacion_confianza <= A.PENALIZACION_CONFIANZA_MAX)

print("\n== 6. Cotejo de nombres abreviados (SofaScore) ==")
abreviado = []
for n in once_local:
    trozos = n.split()
    abreviado.append(f"{trozos[0][0]}. {' '.join(trozos[1:])}" if len(trozos) > 1 else n)
inf_ab = A.evaluar(local, abreviado)
print("    abreviado:", ", ".join(abreviado[:4]), "...")
check(f"no inventa ausencias por la abreviatura ({len(inf_ab.ausentes)} ausentes)",
      len(inf_ab.ausentes) <= 1)

print("\n== 7. El motor de verdad: el once mueve la prediccion ==")
pred_engine = Predictor(BPAEngine())
def partido():
    return Match(id="t1", home_team=local.model_dump(), away_team=visit.model_dump(),
                 date=datetime(2026, 9, 6, 21, 0), competition="La Liga",
                 conditions=MatchConditions(), referee=Referee(name="X"))

base = pred_engine.predict_match(partido(), once_local=once_local, once_visitante=once_visit)
roto = pred_engine.predict_match(partido(), once_local=sin_portero, once_visitante=once_visit)

print(f"    once completo : lambda {base.lambda_home:.3f}-{base.lambda_away:.3f}  conf {base.confidence_score}")
print(f"    sin portero   : lambda {roto.lambda_home:.3f}-{roto.lambda_away:.3f}  conf {roto.confidence_score}")
check("el visitante marca MAS sin el portero local", roto.lambda_away > base.lambda_away)
check("el local marca IGUAL (no era su ataque)", abs(roto.lambda_home - base.lambda_home) < 1e-6)
check("la confianza BAJA", roto.confidence_score < base.confidence_score)
check("se guardan los lambdas", base.lambda_home > 0 and base.lambda_away > 0)
check("se guarda el informe de ausencias", bool(roto.ausencias.get("local", {}).get("ausentes")))
check("se guarda la trazabilidad de pesos", bool(base.model_weights_used))

print("\n== 8. Sin once, la prediccion no cambia respecto a antes ==")
neutro = pred_engine.predict_match(partido())
check("sin once no hay penalizacion", neutro.penalizacion_ausencias == 0.0)
check("y los lambdas son los del once completo",
      abs(neutro.lambda_home - base.lambda_home) < 1e-6)

print("\n" + ("TODO OK" if not fallos else f"FALLAN {len(fallos)}: {fallos}"))
sys.exit(1 if fallos else 0)
