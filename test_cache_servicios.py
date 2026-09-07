# -*- coding: utf-8 -*-
"""
Pruebas de la deteccion de servicios cacheados rancios.

Reproducen el fallo que se dio en produccion: st.cache_resource guarda el
OBJETO, no la clase, asi que al anadir metodos nuevos sin cambiar la clave de
cache Streamlit seguia devolviendo la instancia construida con la clase vieja.
La interfaz nueva llamaba a un metodo que ese objeto no tenia y saltaba

    'DataManager' object has no attribute 'get_pendientes_para_resultado'

con el metodo escrito, probado y desplegado.

Ejecutar:  python test_cache_servicios.py
"""

import io
import os
import re
import sys

sys.path.insert(0, os.path.abspath("."))
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

_fallos = []


def check(desc, cond):
    print(("  OK   " if cond else "  FALLA") + f"  {desc}")
    if not cond:
        _fallos.append(desc)


# =============================================================================
print("--- 1. Los servicios reales tienen lo que la interfaz les pide ---")

from src.data.db_manager import DataManager
from src.logic.bpa_engine import BPAEngine
from src.logic.calibracion import CalibradorGoles
from src.logic.learning_engine import LearningEngine
from src.logic.predictors import Predictor

# La misma lista que comprueba main.py al arrancar.
METODOS_DB = ("get_pendientes_para_resultado", "get_calibracion",
              "get_pares_prediccion_resultado")

for m in METODOS_DB:
    check(f"DataManager.{m}", hasattr(DataManager, m))

# El resto de la cadena que recorre el boton de sincronizacion.
for clase, metodos in (
    (DataManager, ("save_resultado", "save_aprendizaje", "get_prediction")),
    (LearningEngine, ("registrar_1x2_automatico", "_recalibrar_goles",
                      "_analyze_1x2", "_apply_team_adjustments")),
    (CalibradorGoles, ("calibrar", "factores", "estado", "refrescar")),
):
    for m in metodos:
        check(f"{clase.__name__}.{m}", hasattr(clase, m))

check("Predictor expone el calibrador",
      "calibrador" in Predictor.__init__.__code__.co_names
      or hasattr(Predictor(BPAEngine()), "calibrador"))


# =============================================================================
print("\n--- 2. La comprobacion de main.py detecta un servicio rancio ---")

# Se lee la funcion de main.py sin importar el modulo entero: main.py es una
# aplicacion Streamlit y ejecutarla aqui pediria el codigo de acceso.
fuente = io.open("app/main.py", encoding="utf-8").read()

bloque = re.search(
    r"^_METODOS_DB = .*?^def _servicios_al_dia.*?\n\n",
    fuente, re.S | re.M)
check("se encuentra la comprobacion en main.py", bloque is not None)

if bloque:
    ambito = {}
    exec(bloque.group(0), ambito)
    al_dia = ambito["_servicios_al_dia"]

    class ServicioNuevo:
        def get_pendientes_para_resultado(self): pass
        def get_calibracion(self): pass
        def get_pares_prediccion_resultado(self): pass

    class ServicioViejo:
        """El DataManager de antes: no conoce los metodos nuevos."""
        def get_calibracion(self): pass

    class PredictorNuevo:
        calibrador = object()
        def recalcular_por_once(self): pass

    class PredictorViejo:
        """El Predictor de antes: tiene el calibrador pero no el recalculo."""
        calibrador = object()

    def paquete(db, pred):
        return (None, db, None, pred, None, None, None)

    check("un paquete al dia se acepta",
          al_dia(paquete(ServicioNuevo(), PredictorNuevo())) is True)
    check("el DataManager rancio se detecta (el fallo real)",
          al_dia(paquete(ServicioViejo(), PredictorNuevo())) is False)
    check("un Predictor al que le falta un metodo nuevo tambien",
          al_dia(paquete(ServicioNuevo(), PredictorViejo())) is False)
    check("un paquete con otra forma no revienta",
          al_dia(("solo", "tres", "cosas")) is False)
    check("y None tampoco", al_dia(None) is False)

    # Los servicios de verdad tienen que pasar la comprobacion.
    check("los servicios reales pasan",
          al_dia(paquete(DataManager(), Predictor(BPAEngine()))) is True)


# =============================================================================
print("\n--- 3. La clave de cache se movio con el codigo nuevo ---")
# Si se anaden metodos a un servicio y esto no sube, Streamlit sirve el objeto
# viejo y la interfaz se rompe sin avisar hasta que alguien pulsa el boton.
version = re.search(r'^CURRENT_VERSION = "([^"]+)"', fuente, re.M)
check("CURRENT_VERSION esta declarada", version is not None)
if version:
    print(f"      version actual: {version.group(1)}")
    check("ya no es la 6.70.2 con la que se rompio",
          version.group(1) != "6.70.2")

check("main.py rehace la cache si detecta servicios rancios",
      "get_services.clear()" in fuente)


# =============================================================================
print("\n" + "=" * 62)
if _fallos:
    print(f"FALLOS: {len(_fallos)}")
    for f in _fallos:
        print(f"  - {f}")
    sys.exit(1)
print("Todas las comprobaciones han pasado.")
