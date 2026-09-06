# -*- coding: utf-8 -*-
"""
Pruebas del bucle de aprendizaje post-partido (calibracion de goles).

Se apoyan en una BD de mentira para no depender de datos reales: lo que se
comprueba es que, ante un sesgo CONOCIDO, el factor se mueve en la direccion
correcta, poco a poco y sin salirse nunca del rango.

Ejecutar:  python test_calibracion_goles.py
"""
import io, json, os, sys
sys.path.insert(0, os.path.abspath("."))
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

from src.logic import calibracion as C

fallos = []
def check(d, c):
    print(("  OK   " if c else "  FALLA") + f"  {d}")
    if not c: fallos.append(d)


class BDFalsa:
    """DataManager de mentira: guarda en memoria y sirve los pares que le den."""
    def __init__(self, pares):
        self.pares = pares
        self.guardado = {}
    def get_calibracion(self):
        return dict(self.guardado)
    def save_calibracion(self, parametro, valor, muestras, error_medio=0.0, sesgo=0.0):
        self.guardado[parametro] = {"parametro": parametro, "valor": valor,
                                    "muestras": muestras, "error_medio": error_medio,
                                    "sesgo": sesgo, "updated_at": "hoy"}
    def get_pares_prediccion_resultado(self, limit=500):
        return list(self.pares)


def pares(n, lam_h, lam_a, real_h, real_a, con_lambdas=True):
    salida = []
    for i in range(n):
        pred = {"total_goals_expected": lam_h + lam_a}
        if con_lambdas:
            pred["lambda_home"] = lam_h
            pred["lambda_away"] = lam_a
        salida.append({"prediction_json": json.dumps(pred),
                       "home_score": real_h, "away_score": real_a,
                       "created_at": f"2026-09-{i+1:02d}"})
    return salida


print("== 1. Sin muestras suficientes no se toca nada ==")
bd = BDFalsa(pares(3, 1.5, 1.2, 2, 1))
cal = C.CalibradorGoles(bd)
inf = cal.calibrar()
check("no aplicada", not inf.aplicada)
check(f"lo dice: {inf.motivo}", "8" in inf.motivo)
check("no ha escrito en la BD", bd.guardado == {})
check("los factores siguen neutros", cal.factores() == (1.0, 1.0))

print("\n== 2. El modelo estima CORTO: el factor sube ==")
# estima 1.0-1.0, se marcan 1.5-1.5 -> objetivo 1.5, acotado a 1.15
bd = BDFalsa(pares(20, 1.0, 1.0, 2, 1))
cal = C.CalibradorGoles(bd)
inf = cal.calibrar()
print("   ", inf.resumen())
check("aplicada", inf.aplicada)
check(f"factor local sube ({inf.factor_local_despues:.4f})", inf.factor_local_despues > 1.0)
check(f"factor visitante no baja ({inf.factor_visitante_despues:.4f})",
      inf.factor_visitante_despues >= 1.0)
check("sesgo local negativo (estima menos de lo real)", inf.local.sesgo < 0)

print("\n== 3. El modelo estima LARGO: el factor baja ==")
bd = BDFalsa(pares(20, 2.5, 2.5, 1, 1))
cal = C.CalibradorGoles(bd)
inf = cal.calibrar()
print("   ", inf.resumen())
check(f"factor local baja ({inf.factor_local_despues:.4f})", inf.factor_local_despues < 1.0)
check("sesgo local positivo", inf.local.sesgo > 0)

print("\n== 4. El paso es incremental, no salta al objetivo ==")
bd = BDFalsa(pares(20, 1.0, 1.0, 2, 2))   # objetivo 2.0, absurdo a proposito
cal = C.CalibradorGoles(bd)
i1 = cal.calibrar(); f1 = i1.factor_local_despues
i2 = cal.calibrar(); f2 = i2.factor_local_despues
print(f"    tras 1 pasada: {f1:.4f} | tras 2: {f2:.4f}")
check("la primera pasada no llega al objetivo (2.0)", f1 < 1.20)
check("la segunda avanza o se queda en el tope", f2 >= f1)
check(f"nunca supera el tope {C.FACTOR_MAX}", f2 <= C.FACTOR_MAX)
check("avisa de que ha topado", any("límite" in a for a in i2.avisos))

print("")
print("== 4b. Sesgo SUAVE: se ve el paso del 25% sin topar ==")
# estima 1.00, real 1.10 -> objetivo 1.10; el paso deberia dar ~1.025, ~1.044...
bd = BDFalsa(pares(20, 1.0, 1.0, 1.1, 1.1))
cal = C.CalibradorGoles(bd)
sec = []
for _ in range(4):
    sec.append(round(cal.calibrar().factor_local_despues, 4))
print("    secuencia:", sec)
check("crece paso a paso, sin saltar al objetivo", sec[0] < sec[1] < sec[2] < sec[3])
check(f"el primer paso es ~25% del camino ({sec[0]})", 1.020 < sec[0] < 1.030)
check("converge por debajo del objetivo (1.10)", sec[-1] < 1.10)
print("")
print("\n== 5. Nunca sale del rango, ni con datos absurdos ==")
for lh, la, rh, ra in [(0.1, 0.1, 9, 9), (5.0, 5.0, 0, 0), (1.0, 1.0, 0, 0)]:
    bd = BDFalsa(pares(30, lh, la, rh, ra))
    cal = C.CalibradorGoles(bd)
    for _ in range(30):          # se insiste hasta la saciedad
        cal.calibrar()
    fl, fv = cal.factores()
    check(f"est {lh}-{la} real {rh}-{ra} -> factores {fl:.3f}/{fv:.3f} dentro de rango",
          C.FACTOR_MIN <= fl <= C.FACTOR_MAX and C.FACTOR_MIN <= fv <= C.FACTOR_MAX)

print("\n== 6. Historial antiguo sin lambdas: se aprovecha igual ==")
bd = BDFalsa(pares(20, 1.3, 1.1, 2, 1, con_lambdas=False))
cal = C.CalibradorGoles(bd)
inf = cal.calibrar()
check("se puede calibrar con solo total_goals_expected", inf.aplicada)
check(f"usa {inf.muestras} muestras", inf.muestras == 20)

print("\n== 7. Basura en la BD no revienta el bucle ==")
bd = BDFalsa([
    {"prediction_json": "no es json", "home_score": 1, "away_score": 0},
    {"prediction_json": None, "home_score": 1, "away_score": 0},
    {"prediction_json": json.dumps({}), "home_score": 1, "away_score": 0},
    {"prediction_json": json.dumps({"lambda_home": 1.2, "lambda_away": 1.0}),
     "home_score": None, "away_score": 0},
])
cal = C.CalibradorGoles(bd)
inf = cal.calibrar()
check("descarta lo ilegible sin fallar", inf.muestras == 0 and not inf.aplicada)

print("\n== 8. estado() describe lo que se aplica ==")
bd = BDFalsa(pares(20, 1.0, 1.0, 2, 1))
cal = C.CalibradorGoles(bd); cal.calibrar()
e = cal.estado()
print("   ", {k: (round(v, 4) if isinstance(v, float) else v) for k, v in e.items()})
check("marca la calibracion como activa", e["activa"] is True)
check("informa de las muestras", e["muestras"] == 20)

print("\n" + ("TODO OK" if not fallos else f"FALLAN {len(fallos)}: {fallos}"))
sys.exit(1 if fallos else 0)
