"""
Verifica la configuración de secretos sin exponer ningún valor.

Uso:  python verify_secrets.py

Comprueba que las 4 claves estén presentes en .env y en .streamlit/secrets.toml,
que no queden los valores filtrados ni el PIN por defecto, y que ambos ficheros
coincidan (bajo Streamlit, secrets.toml sobreescribe a .env).
"""

import os
import sys

CLAVES = ["ACCESS_CODE", "API_FOOTBALL_KEY", "FOOTBALL_DATA_API_KEY", "SPORTMONKS_API_TOKEN"]

# Prefijos de las llaves que se filtraron en el historial de git (commit c3c82cb).
FILTRADAS = {
    "API_FOOTBALL_KEY": "1462",
    "FOOTBALL_DATA_API_KEY": "1039",
    "SPORTMONKS_API_TOKEN": "p8r8",
}
PIN_INSEGURO = {"1234", "0000", "admin", "password"}


def _leer_env(ruta=".env"):
    valores = {}
    if not os.path.exists(ruta):
        return valores
    for linea in open(ruta, encoding="utf-8"):
        linea = linea.strip()
        if not linea or linea.startswith("#") or "=" not in linea:
            continue
        k, _, v = linea.partition("=")
        valores[k.strip()] = v.strip().strip("'\"")
    return valores


def _leer_secrets(ruta=".streamlit/secrets.toml"):
    valores = {}
    if not os.path.exists(ruta):
        return valores
    for linea in open(ruta, encoding="utf-8"):
        linea = linea.strip()
        if not linea or linea.startswith("#") or "=" not in linea:
            continue
        k, _, v = linea.partition("=")
        valores[k.strip()] = v.strip().strip("'\"")
    return valores


def main():
    env = _leer_env()
    sec = _leer_secrets()
    problemas = []

    print("Fichero              ACCESS_CODE  API_FOOTBALL  FOOTBALL_DATA  SPORTMONKS")
    for nombre, datos in ((".env", env), ("secrets.toml", sec)):
        marcas = ["   OK   " if datos.get(k) else "  FALTA " for k in CLAVES]
        print(f"{nombre:20} " + "".join(f"{m:>13}" for m in marcas))

    print()
    for k in CLAVES:
        for nombre, datos in ((".env", env), ("secrets.toml", sec)):
            v = datos.get(k)
            if not v:
                problemas.append(f"{k} ausente en {nombre}")
                continue
            if v.startswith("TU_"):
                problemas.append(f"{k} en {nombre} sigue con el texto de la plantilla")
            if k in FILTRADAS and v[:4] == FILTRADAS[k]:
                problemas.append(f"{k} en {nombre} SIGUE SIENDO LA LLAVE FILTRADA")
            if k == "ACCESS_CODE" and v in PIN_INSEGURO:
                problemas.append(f"ACCESS_CODE en {nombre} es un PIN inseguro")

        if env.get(k) and sec.get(k) and env[k] != sec[k]:
            problemas.append(f"{k} DIFIERE entre .env y secrets.toml "
                             f"(bajo Streamlit gana secrets.toml)")

    if problemas:
        print("PROBLEMAS DETECTADOS:")
        for p in problemas:
            print(f"  [!] {p}")
        return 1

    print("Todo correcto: 4 claves presentes en ambos ficheros, sin valores")
    print("filtrados, sin PIN inseguro y sin discrepancias entre ficheros.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
