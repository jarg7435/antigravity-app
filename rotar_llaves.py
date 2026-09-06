# -*- coding: utf-8 -*-
"""
Rotación de las llaves de API — La Gema JARG74.

Sustituye una llave en .env y en .streamlit/secrets.toml a la vez, pero solo
después de comprobar contra la API de verdad que la nueva funciona. Existe
porque las llaves viven en DOS ficheros y bajo Streamlit manda secrets.toml:
cambiar uno y olvidar el otro deja la aplicación funcionando en local y rota en
producción, sin ninguna pista de por qué.

Motivo de la rotación: el fichero .env se subió al repositorio en el commit
90d2f40 y se borró en f839cee, pero un borrado no quita nada del historial. El
repositorio es público, así que las llaves de aquel .env son legibles por
cualquiera en `git show 90d2f40:.env`. Rotarlas es lo que de verdad las anula:
mientras la llave siga siendo válida, da igual lo escondido que esté el fichero.

Uso:

    # Comprobar qué hay que rotar, sin tocar nada
    python rotar_llaves.py

    # Rotar (las llaves nuevas se piden por teclado, no se escriben en la orden
    # para que no queden en el historial del terminal)
    python rotar_llaves.py --rotar football-data
    python rotar_llaves.py --rotar sportmonks
    python rotar_llaves.py --rotar api-football

    # Ensayo: verifica la llave nueva pero no escribe nada
    python rotar_llaves.py --rotar sportmonks --ensayo

Dónde se generan las llaves nuevas:
    football-data.org  https://www.football-data.org/client/register
                       (la cuenta muestra el token en su panel; pedir uno nuevo
                        invalida el anterior)
    Sportmonks         https://my.sportmonks.com/api-tokens
                       (crear token nuevo y BORRAR el viejo, o el filtrado
                        sigue sirviendo)
    API-Football       https://dashboard.api-football.com/profile
                       (sección Account → regenerar la API key)

Después de rotar hay un tercer sitio que este script NO puede tocar: los
secrets de Streamlit Cloud (Settings → Secrets). Se avisa al terminar.

Autor: Antigravity - La Gema JARG74
"""

import argparse
import getpass
import io
import os
import shutil
import sys
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

RUTA_ENV = ".env"
RUTA_SECRETS = ".streamlit/secrets.toml"

# Prefijos de las llaves que quedaron en el historial publico (commit 90d2f40).
# Se comparan solo por el principio para no volver a escribirlas enteras aqui.
FILTRADAS = {
    "API_FOOTBALL_KEY": "1462",
    "FOOTBALL_DATA_API_KEY": "1039",
    "SPORTMONKS_API_TOKEN": "p8r8",
}

# Nombre corto -> (variable, longitud esperada, donde se regenera)
LLAVES = {
    "football-data": (
        "FOOTBALL_DATA_API_KEY", 32,
        "https://www.football-data.org/client/register",
    ),
    "sportmonks": (
        "SPORTMONKS_API_TOKEN", 60,
        "https://my.sportmonks.com/api-tokens",
    ),
    "api-football": (
        "API_FOOTBALL_KEY", 32,
        "https://dashboard.api-football.com/profile",
    ),
}


def _tls():
    """Activa el almacen de certificados del sistema, como hace la app."""
    try:
        from src.utils.tls import activar_tls
        activar_tls()
    except Exception:
        pass


def enmascarar(valor: str) -> str:
    """Un valor reconocible sin llegar a mostrarlo."""
    if not valor:
        return "(vacío)"
    if len(valor) <= 8:
        return f"{valor[:2]}…{valor[-1:]} ({len(valor)} car.)"
    return f"{valor[:4]}…{valor[-2:]} ({len(valor)} car.)"


def leer(ruta: str) -> dict:
    """Pares clave/valor de un .env o un secrets.toml sencillo."""
    valores = {}
    if not os.path.exists(ruta):
        return valores
    for linea in io.open(ruta, encoding="utf-8"):
        linea = linea.strip()
        if not linea or linea.startswith("#") or "=" not in linea:
            continue
        k, _, v = linea.partition("=")
        valores[k.strip()] = v.strip().strip("'\"")
    return valores


def escribir(ruta: str, clave: str, nuevo: str) -> bool:
    """
    Cambia el valor de `clave` conservando el resto del fichero tal cual.

    Se reescribe linea a linea en lugar de volcar un diccionario para no perder
    los comentarios ni el orden, y para respetar el entrecomillado de cada
    fichero: secrets.toml lleva comillas y .env no.
    """
    if not os.path.exists(ruta):
        print(f"  [!] {ruta} no existe; no se toca.")
        return False

    lineas = io.open(ruta, encoding="utf-8").read().splitlines(keepends=True)
    salida, cambiada = [], False
    for linea in lineas:
        desnuda = linea.strip()
        if desnuda and not desnuda.startswith("#") and "=" in desnuda:
            k, _, v = desnuda.partition("=")
            if k.strip() == clave:
                fin = "\n" if linea.endswith("\n") else ""
                comillas = '"' if v.strip().startswith(('"', "'")) else ""
                salida.append(f"{k.strip()}={comillas}{nuevo}{comillas}{fin}")
                cambiada = True
                continue
        salida.append(linea)

    if not cambiada:
        print(f"  [!] {clave} no aparece en {ruta}; no se añade sola.")
        return False

    copia = f"{ruta}.bak-{datetime.now():%Y%m%d-%H%M%S}"
    shutil.copy2(ruta, copia)
    io.open(ruta, "w", encoding="utf-8", newline="").write("".join(salida))
    print(f"  [ok] {ruta} actualizado (copia previa en {os.path.basename(copia)})")
    return True


# =============================================================================
# VERIFICACION CONTRA LA API REAL
# =============================================================================

def probar_football_data(llave: str):
    import requests
    r = requests.get("https://api.football-data.org/v4/competitions/PD",
                     headers={"X-Auth-Token": llave}, timeout=20)
    if r.status_code == 200:
        return True, f"OK — {r.json().get('name', 'competición leída')}"
    return False, f"HTTP {r.status_code}: {r.text[:120]}"


def probar_sportmonks(llave: str):
    import requests
    r = requests.get("https://api.sportmonks.com/v3/football/leagues",
                     params={"api_token": llave, "per_page": 1}, timeout=20)
    if r.status_code == 200:
        return True, f"OK — {len(r.json().get('data', []))} liga(s) leída(s)"
    return False, f"HTTP {r.status_code}: {r.text[:120]}"


def probar_api_football(llave: str):
    from src.data.api_football import diagnosticar
    d = diagnosticar(api_key=llave)
    return d["ok"], d["mensaje"]


PRUEBAS = {
    "FOOTBALL_DATA_API_KEY": probar_football_data,
    "SPORTMONKS_API_TOKEN": probar_sportmonks,
    "API_FOOTBALL_KEY": probar_api_football,
}


# =============================================================================
# ACCIONES
# =============================================================================

def estado():
    """Qué llaves siguen siendo las filtradas, sin mostrar ningún valor."""
    env, sec = leer(RUTA_ENV), leer(RUTA_SECRETS)
    print(f"\n{'LLAVE':24} {'.env':20} {'secrets.toml':20} ESTADO")
    print("-" * 78)
    pendientes = []
    for corto, (var, _, _) in LLAVES.items():
        e, s = env.get(var, ""), sec.get(var, "")
        prefijo = FILTRADAS.get(var, "")
        filtrada = bool(prefijo) and (e[:4] == prefijo or s[:4] == prefijo)
        if filtrada:
            marca = "!! FILTRADA — rotar"
            pendientes.append(corto)
        elif e and s and e != s:
            marca = "!! difiere entre ficheros"
        elif not e or not s:
            marca = "!! falta en algún fichero"
        else:
            marca = "ok"
        print(f"{var:24} {enmascarar(e):20} {enmascarar(s):20} {marca}")

    print()
    if pendientes:
        print("Hay que rotar:", ", ".join(pendientes))
        for corto in pendientes:
            print(f"  python rotar_llaves.py --rotar {corto}")
    else:
        print("Ninguna llave filtrada en uso.")
    return 1 if pendientes else 0


def rotar(corto: str, ensayo: bool = False) -> int:
    if corto not in LLAVES:
        print(f"Llave desconocida: {corto}. Opciones: {', '.join(LLAVES)}")
        return 2

    var, largo, donde = LLAVES[corto]
    actual = leer(RUTA_ENV).get(var, "")

    print(f"\nRotando {var}")
    print(f"  valor actual : {enmascarar(actual)}")
    print(f"  se genera en : {donde}")
    print("\nPega la llave NUEVA (no se muestra al escribirla, y no queda en el")
    print("historial del terminal). Enter en blanco para abortar.")

    try:
        nueva = getpass.getpass("  llave nueva: ").strip().strip("'\"")
    except (KeyboardInterrupt, EOFError):
        print("\nAbortado.")
        return 1

    if not nueva:
        print("Abortado: no se ha introducido nada.")
        return 1

    prefijo = FILTRADAS.get(var, "")
    if prefijo and nueva[:4] == prefijo:
        print("Abortado: esa es la llave FILTRADA, no una nueva.")
        return 1
    if nueva == actual:
        print("Abortado: es la misma que ya está puesta.")
        return 1
    if len(nueva) != largo:
        print(f"  [!] Aviso: se esperaban {largo} caracteres y tiene {len(nueva)}.")
        if input("      ¿Continuar igualmente? [s/N] ").strip().lower() != "s":
            print("Abortado.")
            return 1

    print("\n  Comprobando contra la API antes de escribir nada...")
    _tls()
    try:
        vale, detalle = PRUEBAS[var](nueva)
    except Exception as e:
        vale, detalle = False, f"{type(e).__name__}: {str(e)[:120]}"

    print(f"  {'[ok]' if vale else '[!!]'} {detalle}")
    if not vale:
        print("\nNo se escribe nada: una llave que no responde dejaría la app peor")
        print("que ahora. Revisa que la hayas copiado entera y vuelve a intentarlo.")
        return 1

    if ensayo:
        print("\n--ensayo: la llave es válida, pero no se escribe nada.")
        return 0

    print()
    ok_env = escribir(RUTA_ENV, var, nueva)
    ok_sec = escribir(RUTA_SECRETS, var, nueva)

    if ok_env and ok_sec:
        print(f"\n{var} rotada: {enmascarar(actual)} -> {enmascarar(nueva)}")
        print("\nFALTA UN SITIO, y sin él producción se queda como estaba:")
        print("  Streamlit Cloud -> Settings -> Secrets -> pega el mismo valor.")
        print("\nY en el proveedor: BORRA o revoca la llave vieja. Mientras siga")
        print("activa, la que está en el historial público sigue sirviendo.")
        return 0

    print("\n[!] Rotación incompleta. Revisa los avisos de arriba.")
    return 1


def main():
    p = argparse.ArgumentParser(
        description="Rota las llaves de API en .env y secrets.toml a la vez.")
    p.add_argument("--rotar", metavar="LLAVE",
                   help=f"cuál rotar: {', '.join(LLAVES)}")
    p.add_argument("--ensayo", action="store_true",
                   help="verifica la llave nueva pero no escribe nada")
    args = p.parse_args()

    if not args.rotar:
        return estado()
    return rotar(args.rotar, ensayo=args.ensayo)


if __name__ == "__main__":
    sys.exit(main())
