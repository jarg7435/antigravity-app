"""
Compatibilidad de entrypoint — La Gema JARG74.

El entrypoint real es app/main.py. Este fichero existía como copia completa y
desactualizada de la interfaz (v6.70.1 frente a la 6.72.0 de app/main.py), lo
que obligaba a mantener dos UIs en paralelo.

Se conserva reducido a un redirector porque el fichero de arranque de Streamlit
Cloud se configura en el panel web, no en el repositorio: así la aplicación
servida es siempre la actual, apunte el despliegue a la raíz o a app/main.py.
"""

import os
import runpy
import sys

_RAIZ = os.path.dirname(os.path.abspath(__file__))
if _RAIZ not in sys.path:
    sys.path.insert(0, _RAIZ)

runpy.run_path(os.path.join(_RAIZ, "app", "main.py"), run_name="__main__")
