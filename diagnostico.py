# -*- coding: utf-8 -*-
"""
Diagnostico de un partido — La Gema JARG74.

Comprueba, sin pasar por la interfaz, las tres cosas que la aplicacion tiene que
resolver antes de poder analizar un encuentro:

    1. La FECHA real del partido.
    2. La DESIGNACION arbitral, con las evidencias en las que se apoya.
    3. Las PLANTILLAS vigentes, mostrando el listado de inscritos entero para
       poder ver si la fuente lo devuelve completo o corto.

Y termina pasando todo eso por el agente supervisor, que es la puerta que
decide si el estudio puede calcularse.

Existe porque la aplicacion desplegada esta detras del codigo de acceso y se
pinta por websocket, asi que no hay forma de comprobarla desde fuera. Esto
recorre exactamente el mismo camino que la app, pero por consola, y ademas
ensena las pruebas en lugar de solo el resultado.

USO

    python diagnostico.py
    python diagnostico.py "Valencia" "FC Barcelona"
    python diagnostico.py "Valencia" "FC Barcelona" "La Liga"
    python diagnostico.py "Valencia" "FC Barcelona" "La Liga" --sin-alineacion

La ultima opcion se salta la busqueda de alineaciones, que es la parte lenta.

OJO CON LAS CLAVES: la aplicacion, cuando corre bajo Streamlit, lee
.streamlit/secrets.toml. Este script corre fuera de Streamlit, asi que lee .env.
Si los dos ficheros no tienen las mismas claves, aqui vera una cosa y la app
otra, y el diagnostico enganaria. Lo primero que se comprueba es justo eso.

Autor: Antigravity - La Gema JARG74
"""

import io
import os
import sys
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# La consola de Windows va en cp1252 y se atraganta con los acentos y los
# simbolos. Sin esto, el diagnostico se cae al imprimir el primer nombre propio.
try:
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
except Exception:
    pass

try:
    from dotenv import load_dotenv
    load_dotenv()
except Exception:
    pass


ANCHO = 74


def titulo(texto):
    print("\n" + "=" * ANCHO)
    print(f" {texto}")
    print("=" * ANCHO)


def bien(texto):
    print(f"  [OK]    {texto}")


def mal(texto):
    print(f"  [FALLO] {texto}")


def aviso(texto):
    print(f"  [AVISO] {texto}")


def dato(clave, valor):
    print(f"          {clave:<26} {valor}")


# =============================================================================
# 0. Configuracion
# =============================================================================

def revisar_claves():
    titulo("0. CLAVES Y CONFIGURACION")

    necesarias = {
        "FOOTBALL_DATA_API_KEY": "plantillas, calendario y árbitro (la más importante)",
        "API_FOOTBALL_KEY": "respaldo para partidos de hoy±1 día",
        "ANTHROPIC_API_KEY": "opcional: búsqueda web asistida",
    }
    for clave, para_que in necesarias.items():
        valor = os.environ.get(clave, "").strip()
        if valor:
            bien(f"{clave} presente en .env ({para_que})")
        elif clave == "ANTHROPIC_API_KEY":
            aviso(f"{clave} ausente — {para_que}. No hace falta.")
        else:
            mal(f"{clave} AUSENTE en .env — {para_que}")

    # El desajuste entre .env y secrets.toml es una trampa clasica: la app usa
    # uno y este script el otro.
    ruta_secrets = os.path.join(".streamlit", "secrets.toml")
    if os.path.exists(ruta_secrets):
        try:
            with open(ruta_secrets, encoding="utf-8") as f:
                en_secrets = {l.split("=")[0].strip()
                              for l in f if "=" in l and not l.strip().startswith("#")}
            faltan = [c for c in ("FOOTBALL_DATA_API_KEY", "API_FOOTBALL_KEY")
                      if c in en_secrets and not os.environ.get(c)]
            if faltan:
                aviso(f"{', '.join(faltan)} está en secrets.toml pero no en .env: "
                      f"la app la usará y este script no.")
            else:
                bien("Las claves de .env y de secrets.toml concuerdan.")
        except Exception as e:
            aviso(f"No se ha podido leer {ruta_secrets}: {e}")


# =============================================================================
# 1. Fecha del partido
# =============================================================================

def revisar_fecha(local, visitante, liga):
    titulo("1. FECHA DEL PARTIDO")
    print(f"  Buscando cuándo se juega {local} - {visitante} ({liga})...\n")

    try:
        from src.data.calendario import fecha_del_partido
        hallazgo = fecha_del_partido(local, visitante, liga)
    except Exception as e:
        mal(f"La búsqueda falló: {type(e).__name__}: {e}")
        return None

    if not hallazgo:
        mal("Ninguna fuente sabe cuándo se juega este partido.")
        print("          En la app, la fecha NO se rellenará sola y tendrás que")
        print("          ponerla a mano. Causas posibles: el partido está a más de")
        print("          10 días vista, los nombres de los equipos no casan con los")
        print("          de la fuente, o falta FOOTBALL_DATA_API_KEY.")
        return None

    bien(f"Encontrado en {hallazgo['fuente']}")
    dato("Fecha:", hallazgo["cuando"].strftime("%d/%m/%Y"))
    dato(f"Hora ({hallazgo['zona']}):", hallazgo["cuando"].strftime("%H:%M"))
    if hallazgo.get("referencia"):
        dato("Referencia:", hallazgo["referencia"])
    dato("Casó con:", f"{hallazgo['local']} vs {hallazgo['visitante']}")
    print("\n          Esto es lo que la app pondrá sola en fecha y hora.")
    return hallazgo["cuando"]


# =============================================================================
# 2. Designacion arbitral
# =============================================================================

def revisar_arbitro(local, visitante, liga, cuando):
    titulo("2. DESIGNACIÓN ARBITRAL")
    print(f"  Investigando quién pita el {local} - {visitante}...\n")

    try:
        from src.data import investigador_web as iw
        # Sin cache: interesa ver lo que responden las fuentes AHORA.
        veredicto = iw.investigar_arbitro(local, visitante, cuando, liga,
                                          usar_cache=False)
    except Exception as e:
        mal(f"La investigación falló: {type(e).__name__}: {e}")
        return None

    estado = veredicto.get("estado")
    if estado == "VERIFICADO":
        bien(f"VERIFICADO: {veredicto['name']}")
    elif estado == "PROBABLE":
        aviso(f"PROBABLE (sin confirmar): {veredicto['name']}")
    else:
        mal("PENDIENTE: ninguna fuente publica todavía la designación.")

    if veredicto.get("motivo"):
        dato("Motivo:", veredicto["motivo"])

    evidencias = veredicto.get("evidencias") or []
    print(f"\n  Evidencias encontradas ({len(evidencias)}):")
    if not evidencias:
        print("          Ninguna. Si sabes que la designación ya está publicada,")
        print("          es que ningún titular la menciona con los dos equipos, o")
        print("          que la noticia queda fuera de la ventana de fechas.")
    for e in evidencias:
        marca = "OFICIAL" if e.get("oficial") else e.get("anclaje", "-")
        print(f"    · {e.get('name')}  [{marca}]  — {e.get('fuente')}")
        if e.get("extracto"):
            print(f"      «{e['extracto']}»")
        if e.get("url"):
            print(f"      {e['url']}")

    consultar = veredicto.get("consultar") or []
    if consultar and estado != "VERIFICADO":
        print("\n  Consulta manual:")
        for c in consultar:
            print(f"    · {c['nombre']}: {c['url']}")

    try:
        from src.data.investigador_web import a_formato_cascada
        return a_formato_cascada(veredicto)
    except Exception:
        return None


# =============================================================================
# 3. Plantillas vigentes
# =============================================================================

def revisar_plantilla(equipo, liga, once):
    """Muestra el listado de inscritos ENTERO y contra que se ha contrastado."""
    from src.data import plantillas

    print(f"\n  --- {equipo} ---")
    try:
        detalle = plantillas.plantilla_detallada(equipo, liga)
    except Exception as e:
        mal(f"No se ha podido obtener la plantilla: {type(e).__name__}: {e}")
        return

    if not detalle:
        mal(f"football-data.org no devuelve plantilla para {equipo}.")
        print("          Sin listado no se puede contrastar nada, y el supervisor")
        print("          bloqueará el análisis por ONCE_SIN_REFERENCIA.")
        return

    bien(f"Listado de inscritos: {len(detalle)} jugadores")
    if len(detalle) < 18:
        aviso(f"Solo {len(detalle)} jugadores. Una plantilla de primera división "
              f"ronda los 25: este listado parece INCOMPLETO.")

    for j in detalle:
        pos = j.get("posicion") or "(sin demarcación)"
        print(f"    · {j['nombre']:<32} {pos}")

    if not once:
        return

    print(f"\n  Contraste del once ({len(once)} jugadores):")
    informe = plantillas.auditar_alineacion(once, equipo, liga)
    for jugador in once:
        resuelto = plantillas.resolver_en_plantilla(
            jugador, [j["nombre"] for j in detalle])
        if resuelto:
            dem = plantillas.demarcacion_de(jugador, equipo, liga)
            etiqueta = dem["posicion"].value if dem["posicion"] else "SIN DEMARCACIÓN"
            print(f"    [OK]    {jugador:<24} -> {resuelto:<30} {etiqueta}")
        else:
            print(f"    [FUERA] {jugador:<24} -> no aparece en el listado")

    if informe["descartados"]:
        if informe.get("listado_dudoso"):
            aviso(f"{len(informe['descartados'])} de {len(once)} sin casar. "
                  f"Con esa proporción se sospecha del LISTADO, no de los "
                  f"jugadores.")
        else:
            aviso(f"{len(informe['descartados'])} sin casar: "
                  f"{', '.join(informe['descartados'])}")
    else:
        bien("Todos los jugadores del once están en el listado.")


def revisar_plantillas(local, visitante, liga, cuando, buscar_once):
    titulo("3. PLANTILLAS VIGENTES")

    once_local, once_visitante = [], []
    if buscar_once:
        print("  Buscando la alineación probable (esto tarda)...")
        try:
            from src.data.mock_provider import MockDataProvider
            from src.logic.lineup_fetcher import LineupFetcher
            fetcher = LineupFetcher(MockDataProvider())
            res = fetcher.fetch_smart_lineup(local, visitante,
                                             cuando or datetime.now(), liga)
            once_local = res.get("home") or []
            once_visitante = res.get("away") or []
            bien(f"Alineación obtenida de: {res.get('source', '?')}")
            dato("Local:", ", ".join(once_local) or "(vacía)")
            dato("Visitante:", ", ".join(once_visitante) or "(vacía)")
        except Exception as e:
            mal(f"No se ha podido obtener la alineación: {type(e).__name__}: {e}")
    else:
        aviso("Búsqueda de alineaciones omitida (--sin-alineacion).")

    revisar_plantilla(local, liga, once_local)
    revisar_plantilla(visitante, liga, once_visitante)
    return once_local, once_visitante


# =============================================================================
# 4. Veredicto del supervisor
# =============================================================================

def revisar_supervisor(local, visitante, liga, cuando, arbitro, once_l, once_v):
    titulo("4. VEREDICTO DEL AGENTE SUPERVISOR")
    print("  Es la puerta que decide si el estudio puede calcularse.\n")

    try:
        from src.logic.supervisor import supervisar
        informe = supervisar(home=local, away=visitante, liga=liga, fecha=cuando,
                             arbitro=arbitro, once_local=once_l,
                             once_visitante=once_v)
    except Exception as e:
        mal(f"El supervisor falló: {type(e).__name__}: {e}")
        return

    if informe.veredicto == "APTO":
        bien(f"{informe.veredicto} — {informe.resumen()}")
    elif informe.veredicto == "ADVERTIDO":
        aviso(f"{informe.veredicto} — {informe.resumen()}")
    else:
        mal(f"{informe.veredicto} — {informe.resumen()}")

    for inc in informe.incidencias:
        marca = "GRAVE" if inc.gravedad == "grave" else "aviso"
        print(f"\n    [{marca}] ({inc.ambito}) {inc.mensaje}")
        if inc.solucion:
            print(f"            -> {inc.solucion}")
        for d in inc.detalle[:12]:
            print(f"               · {d}")

    if informe.bloqueado:
        print("\n  En la app, el botón CALCULAR PREDICCIÓN estará deshabilitado.")
        print("  Si la alineación es correcta pese al aviso, marca la casilla")
        print("  «He revisado la alineación y es correcta» para desbloquearlo.")


# =============================================================================

def main():
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    buscar_once = "--sin-alineacion" not in sys.argv

    local = args[0] if len(args) > 0 else "Valencia"
    visitante = args[1] if len(args) > 1 else "FC Barcelona"
    liga = args[2] if len(args) > 2 else "La Liga"

    print("=" * ANCHO)
    print(f" DIAGNÓSTICO — {local} vs {visitante} ({liga})")
    print(f" {datetime.now():%d/%m/%Y %H:%M}")
    print("=" * ANCHO)

    revisar_claves()
    cuando = revisar_fecha(local, visitante, liga)
    arbitro = revisar_arbitro(local, visitante, liga, cuando)
    once_l, once_v = revisar_plantillas(local, visitante, liga, cuando, buscar_once)
    revisar_supervisor(local, visitante, liga, cuando, arbitro, once_l, once_v)

    print("\n" + "=" * ANCHO)
    print(" Fin del diagnóstico. Si algo sale [FALLO], copia esta salida entera:")
    print(" lleva las evidencias necesarias para saber qué fuente ha fallado.")
    print("=" * ANCHO)


if __name__ == "__main__":
    main()
