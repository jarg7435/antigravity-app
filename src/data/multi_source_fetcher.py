"""
MultiSourceFetcher — Cascada de fuentes para árbitros y alineaciones
=====================================================================
Árbitros → 0.Investigador web  0b.Football-Data  1.Claude  2.SofaScore  3.RSS
           4.LigaScraper  5.BeSoccer  resp.API-Football  6.Manual
Alineaciones → 1.SofaScore  2.LigaScraper  3.BeSoccer  resp.API-Football  4.BD interna

El investigador web (src/data/investigador_web.py) va el primero porque es la
unica fuente que corrobora antes de contestar: solo devuelve un nombre si lo
respalda una fuente oficial o dos fuentes independientes. Las demas devuelven
el primer nombre que encuentran, y cortar la cascada con un nombre sin
confirmar es como se llego a mostrar un arbitro que no era el designado.

ORDEN DE FUENTES: lo fija src/data/cascada.py. Para arbitros y alineaciones de
proximos partidos, football-data.org y los scrapers van primero y API-Football
queda de respaldo, porque su plan gratuito no cubre el calendario futuro.
"""
from datetime import datetime
from typing import Dict, Optional

from src.data import cascada as _cascada


def _norm_league(league):
    n = league.lower().split("(")[0].strip().replace("ea sports","").replace("santander","").strip()
    if "la liga" in n or "primera" in n or "espa" in n: return "La Liga"
    # La escocesa va ANTES que la inglesa. "Scottish Premiership" contiene
    # "premier", asi que caia en la regla de abajo y todo un partido escoces se
    # trataba como de la Premier inglesa: el scraper de liga equivocado, el
    # codigo "PL" en football-data.org y el id 39 en API-Football.
    if "scottish" in n or "escoc" in n: return "Scottish Premiership"
    if "premier" in n: return "Premier League"
    if "serie a" in n or "italia" in n: return "Serie A"
    if "bundesliga" in n or "german" in n: return "Bundesliga"
    if "ligue 1" in n or "france" in n: return "Ligue 1"
    if "champions" in n or "uefa" in n: return "Champions League"
    return n


def _get_liga_scraper(league):
    norm = _norm_league(league)
    try:
        if norm == "La Liga":
            from src.data.scrapers.la_liga import LaLigaDataScraper; return LaLigaDataScraper()
        if norm == "Premier League":
            from src.data.scrapers.premier_league import PremierLeagueDataScraper; return PremierLeagueDataScraper()
        if norm == "Serie A":
            from src.data.scrapers.serie_a import SerieADataScraper; return SerieADataScraper()
        if norm == "Bundesliga":
            from src.data.scrapers.bundesliga import BundesligaDataScraper; return BundesligaDataScraper()
        if norm == "Ligue 1":
            from src.data.scrapers.ligue1 import Ligue1DataScraper; return Ligue1DataScraper()
    except Exception as e:
        print(f"  [MSF] liga scraper error: {e}")
    return None


def _arbitro_valido(nombre, fuente):
    """
    ¿Aceptamos este nombre como arbitro designado?

    Se aplica a TODAS las fuentes, no solo a la prensa. Una fuente que devuelve
    basura y "acierta" corta la cascada antes de llegar a las siguientes: asi
    es como un fragmento de titular ("que no vio") se mostro como arbitro
    designado en lugar de dejar que respondieran BeSoccer o el scraper de liga.
    """
    from src.data.referee_database import es_nombre_plausible
    if es_nombre_plausible(nombre):
        return True
    print(f"  [{fuente}] descartado, no parece un nombre: {nombre!r}")
    return False


def _enrich(ref, estado="PROBABLE"):
    """
    Anade el perfil estadistico del arbitro y fija su estado de verificacion.

    El estado por defecto es PROBABLE y no confirmado, porque las fuentes que
    pasan por aqui (SofaScore, prensa, scrapers de liga, BeSoccer) devuelven el
    primer nombre que encuentran sin contrastarlo con nadie. Antes esta funcion
    ponia _is_fallback=False a todo lo que le llegara, con lo que un titular
    sobre otro partido salia de la cascada indistinguible de una designacion
    oficial. Solo el investigador web, football-data.org y API-Football, que
    leen el dato de un feed del propio partido, pasan VERIFICADO.

    Ojo con enrich_referee: pone _is_fallback=False en cuanto reconoce el
    nombre en la base local, y eso significa "sabemos quien es", nunca "esta
    designado para este partido". Por eso el estado se aplica DESPUES.
    """
    try:
        from src.data.referee_database import enrich_referee
        ref = enrich_referee(ref)
    except Exception:
        from src.models.base import RefereeStrictness
        ref.setdefault("strictness", RefereeStrictness.MEDIUM)
        ref.setdefault("avg_cards", 4.0)

    ref["estado"] = ref.get("estado") or estado
    ref["_is_fallback"] = ref["estado"] != "VERIFICADO"

    # Todo resultado lleva el estado de API-Football, no solo el "Por Detectar"
    # del final. La interfaz decide con esto si avisar de que la busqueda se
    # hizo sin la fuente de pago, y la cascada corta en cuanto una fuente
    # responde: si el dato solo se pegara al final, el aviso no aparecia nunca
    # en los casos en los que una secundaria si encuentra algo.
    try:
        from src.data import resiliencia_api as _res
        ref.setdefault("degradacion", _res.resumen())
    except Exception:
        pass
    return ref


# Estado de la ultima inicializacion de cada fuente.
# La cascada ignora a proposito las fuentes que fallan y sigue con la siguiente,
# asi que sin este registro una fuente caida es invisible desde la interfaz.
_ESTADO_FUENTES: Dict[str, Dict] = {}


def _marcar_fuente(nombre: str, ok: bool, motivo: str = None):
    _ESTADO_FUENTES[nombre] = {
        "ok": ok,
        "motivo": motivo,
        "ts": datetime.now().isoformat(timespec="seconds"),
    }


def get_source_status() -> Dict[str, Dict]:
    """Resultado de la ultima inicializacion de cada fuente, para diagnostico."""
    return dict(_ESTADO_FUENTES)


def _get_api_football_client():
    """
    Inicializa lazy del cliente API-Football.

    Devuelve None tambien cuando el cortacircuitos esta abierto: con la
    suscripcion caducada o la cuota agotada no hay cliente que valga, y quien
    llama ya sabe seguir sin el. El motivo queda registrado para que el panel
    de estado lo explique en lugar de dar la fuente por ausente sin mas.
    """
    try:
        from src.data import resiliencia_api as _res
        if not _res.disponible():
            _marcar_fuente("API-Football", False, _res.texto_estado())
            return None

        from src.data.api_football import cliente_compartido
        client = cliente_compartido()
        if client.is_configured:
            _marcar_fuente("API-Football", True)
            return client
        _marcar_fuente("API-Football", False, "sin API_FOOTBALL_KEY configurada")
    except Exception as e:
        print(f"  [MSF] API-Football init error: {e}")
        _marcar_fuente("API-Football", False, f"{type(e).__name__}: {e}")
    return None


def _get_football_data_client():
    """Inicializa lazy del cliente Football-Data.org."""
    try:
        from src.data.football_data_org import FootballDataClient
        client = FootballDataClient()
        if client.is_configured:
            _marcar_fuente("Football-Data.org", True)
            return client
        _marcar_fuente("Football-Data.org", False, "sin FOOTBALL_DATA_API_KEY configurada")
    except Exception as e:
        print(f"  [MSF] Football-Data.org init error: {e}")
        _marcar_fuente("Football-Data.org", False, f"{type(e).__name__}: {e}")
    return None


def _motivo_omision(tipo) -> str:
    """
    Por que se salta API-Football en esta consulta.

    Distingue las dos causas, que se estaban confundiendo en el log: una es la
    ventana del plan gratuito, que es normal y esperada, y la otra es que la
    fuente esta caida. Solo la segunda es una averia que haya que arreglar.
    """
    from src.data import resiliencia_api as _res
    if not _res.disponible():
        _marcar_fuente("API-Football", False, _res.texto_estado())
        return _res.texto_estado()
    return f"fuera del alcance del plan ({tipo.value})"


def _norm_team_name(name):
    """Normaliza nombre de equipo para comparación fuzzy."""
    if not name:
        return ""
    n = name.lower().strip()
    # Quitar prefijos comunes
    for prefix in ["fc ", "cf ", "cd ", "ud ", "rcd ", "real ", "athletic "]:
        n = n.replace(prefix, "")
    return n.strip()


def _find_fixture_id(af_client, home, away, league, match_date):
    """
    Busca el fixture_id de un partido en API-Football buscando por equipos y fecha.
    Este ID es necesario para obtener árbitro y alineaciones oficiales.
    """
    if not af_client:
        return None

    from src.data.api_football import LEAGUE_IDS
    league_id = LEAGUE_IDS.get(_norm_league(league))

    # Estrategia 1: Buscar por fecha si tenemos liga
    if league_id and match_date:
        try:
            date_str = None
            if hasattr(match_date, 'strftime'):
                date_str = match_date.strftime("%Y-%m-%d")
            elif isinstance(match_date, str):
                date_str = match_date[:10]

            if date_str:
                fixtures = af_client.get_fixtures_by_date_range(
                    date_str, date_str, league_id
                )
                for f in fixtures:
                    fh = f.get("teams", {}).get("home", {}).get("name", "")
                    fa = f.get("teams", {}).get("away", {}).get("name", "")
                    if (_norm_team_name(fh) in _norm_team_name(home) or
                        _norm_team_name(home) in _norm_team_name(fh)):
                        if (_norm_team_name(fa) in _norm_team_name(away) or
                            _norm_team_name(away) in _norm_team_name(fa)):
                            return f.get("fixture", {}).get("id")
        except Exception as e:
            print(f"  [MSF] Buscar fixture por fecha falló: {e}")

    # Estrategia 2: Buscar próximos fixtures de la liga
    if league_id:
        try:
            next_fixtures = af_client.get_next_fixtures(league_id, next_n=20)
            for f in next_fixtures:
                fh = f.get("teams", {}).get("home", {}).get("name", "")
                fa = f.get("teams", {}).get("away", {}).get("name", "")
                if (_norm_team_name(fh) in _norm_team_name(home) or
                    _norm_team_name(home) in _norm_team_name(fh)):
                    if (_norm_team_name(fa) in _norm_team_name(away) or
                        _norm_team_name(away) in _norm_team_name(fa)):
                        return f.get("fixture", {}).get("id")
        except Exception as e:
            print(f"  [MSF] Buscar fixture próximos falló: {e}")

    # Estrategia 3: Buscar equipos por nombre y luego H2H
    try:
        home_teams = af_client.search_team(home)
        away_teams = af_client.search_team(away)
        if home_teams and away_teams:
            home_id = home_teams[0].get("team", {}).get("id")
            away_id = away_teams[0].get("team", {}).get("id")
            if home_id and away_id:
                h2h = af_client.get_h2h(home_id, away_id, last_n=5)
                for f in h2h:
                    status = f.get("fixture", {}).get("status", {}).get("short", "")
                    if status in ("NS", "TBD", "1H", "2H", "HT", "ET", "P", "BT", "LIVE"):
                        return f.get("fixture", {}).get("id")
                # Si no hay próximos, usar el último como referencia
                if h2h:
                    return h2h[0].get("fixture", {}).get("id")
    except Exception as e:
        print(f"  [MSF] Buscar fixture por H2H falló: {e}")

    return None


# =============================================================================
# DIAGNOSTICO DE CONECTIVIDAD
# =============================================================================

# Segundos por sonda. Corto a proposito: esto se pulsa desde la barra lateral y
# son seis fuentes seguidas. Una que tarde diez segundos es, para el caso, una
# fuente que no sirve.
ESPERA_DIAGNOSTICO = 8

# Los tres estados que sabe pintar la interfaz. Cualquier otro sale en rojo.
OK = "OK"
LIMITED = "LIMITED"
ERROR = "ERROR"


def _estado(status, detalle):
    return {"status": status, "detail": detalle}


def _diag_api_football():
    """
    Estado de la fuente de pago.

    Se pregunta primero al cortacircuitos, que es quien sabe si la suscripcion
    esta caida, y solo se sale a la red si dice que la fuente esta viva: si ya
    consta como averiada, gastar una peticion para confirmarlo no aporta nada.
    """
    try:
        from src.data import resiliencia_api as _res
        if not _res.disponible():
            resumen = _res.resumen()
            estado = LIMITED if resumen.get("averia") == "cuota" else ERROR
            return _estado(estado, resumen.get("motivo") or "fuera de servicio")

        from src.data.api_football import diagnosticar
        d = diagnosticar()
        if d["ok"]:
            return _estado(OK, f"plan {d['plan']}, {d['peticiones']} peticiones hoy")
        if d["causa"] == "cuota_agotada":
            return _estado(LIMITED, d["mensaje"][:120])
        return _estado(ERROR, d["mensaje"][:120])
    except Exception as e:
        return _estado(ERROR, f"{type(e).__name__}: {str(e)[:90]}")


def _diag_football_data():
    """football-data.org: se pide una competicion pequena y se mira el codigo."""
    try:
        from src.data.api_manager import FootballDataClient
        cliente = FootballDataClient()
        if not getattr(cliente, "api_key", ""):
            return _estado(ERROR, "sin FOOTBALL_DATA_API_KEY configurada")
        import requests
        r = requests.get("https://api.football-data.org/v4/competitions/PD",
                         headers={"X-Auth-Token": cliente.api_key},
                         timeout=ESPERA_DIAGNOSTICO)
        if r.status_code == 200:
            return _estado(OK, "responde y acepta la llave")
        if r.status_code == 429:
            return _estado(LIMITED, "limite de peticiones alcanzado; se repone solo")
        if r.status_code in (401, 403):
            return _estado(ERROR, f"llave rechazada (HTTP {r.status_code})")
        return _estado(ERROR, f"HTTP {r.status_code}")
    except Exception as e:
        return _estado(ERROR, f"{type(e).__name__}: {str(e)[:90]}")


def _diag_sofascore():
    """SofaScore: el mismo buscador de eventos que usa la cascada."""
    try:
        import requests
        from src.data.scrapers.sofascore_api import HEADERS
        r = requests.get(
            "https://api.sofascore.com/api/v1/search/events?q=barcelona",
            headers=HEADERS, timeout=ESPERA_DIAGNOSTICO)
        if r.status_code != 200:
            return _estado(ERROR, f"HTTP {r.status_code}")
        datos = r.json()
        # Un 200 con una respuesta que no trae partidos es la senal de que han
        # vuelto a cambiar la forma del JSON, que es justo como esta fuente
        # estuvo meses sin aportar nada sin que se notara.
        from src.data.scrapers.sofascore_api import _eventos_de_respuesta
        n = len(_eventos_de_respuesta(datos))
        if n:
            return _estado(OK, f"responde y devuelve partidos ({n} en la prueba)")
        return _estado(LIMITED, "responde, pero no devuelve partidos: revisar el formato")
    except Exception as e:
        return _estado(ERROR, f"{type(e).__name__}: {str(e)[:90]}")


def _diag_prensa_rss():
    """Google News RSS, de donde salen las designaciones de la prensa."""
    try:
        import requests
        import xml.etree.ElementTree as ET
        from src.data.scrapers.sofascore_api import RSS_HEADERS
        r = requests.get(
            "https://news.google.com/rss/search?q=arbitro&hl=es&gl=ES&ceid=ES:es",
            headers=RSS_HEADERS, timeout=ESPERA_DIAGNOSTICO)
        if r.status_code != 200:
            return _estado(ERROR, f"HTTP {r.status_code}")
        n = len(ET.fromstring(r.content).findall(".//item"))
        if n:
            return _estado(OK, f"responde ({n} titulares en la prueba)")
        return _estado(LIMITED, "responde, pero sin titulares")
    except Exception as e:
        return _estado(ERROR, f"{type(e).__name__}: {str(e)[:90]}")


def _diag_buscador_web():
    """DuckDuckGo, que es lo que usa el investigador de designaciones."""
    try:
        import requests
        r = requests.post("https://html.duckduckgo.com/html/",
                          data={"q": "arbitro designado"},
                          headers={"User-Agent": "Mozilla/5.0"},
                          timeout=ESPERA_DIAGNOSTICO)
        if r.status_code != 200:
            return _estado(ERROR, f"HTTP {r.status_code}")
        if "result" in r.text:
            return _estado(OK, "responde con resultados")
        return _estado(LIMITED, "responde, pero sin resultados legibles")
    except Exception as e:
        return _estado(ERROR, f"{type(e).__name__}: {str(e)[:90]}")


def _diag_besoccer():
    """BeSoccer, ultimo recurso de la cascada de arbitros."""
    try:
        import requests
        r = requests.get("https://es.besoccer.com/",
                         headers={"User-Agent": "Mozilla/5.0"},
                         timeout=ESPERA_DIAGNOSTICO)
        if r.status_code == 200:
            return _estado(OK, "responde")
        if r.status_code in (403, 429):
            return _estado(LIMITED, f"bloquea el acceso automatico (HTTP {r.status_code})")
        return _estado(ERROR, f"HTTP {r.status_code}")
    except Exception as e:
        return _estado(ERROR, f"{type(e).__name__}: {str(e)[:90]}")


def _diag_sportmonks():
    """
    Sportmonks: no basta con que responda, hay que saber QUE cubre.

    El plan contratado solo da acceso a la Superliga danesa y a la Premiership
    escocesa. Un diagnostico que dijera "OK" a secas haria pensar que esta
    fuente puede aportar algo en LaLiga, y no puede.
    """
    try:
        from src.data import sportmonks_arbitros as _sm
        ligas = _sm.ligas_cubiertas(refrescar=True)
        if not ligas:
            return _estado(ERROR, "no responde o la llave no es valida")
        nombres = ", ".join(sorted(ligas))
        return _estado(OK, f"responde; el plan cubre {len(ligas)}: {nombres}")
    except Exception as e:
        return _estado(ERROR, f"{type(e).__name__}: {str(e)[:90]}")


def _diag_claude():
    """
    Consulta a Claude con busqueda web. Es opcional en la cascada.

    Aqui solo se mira si hay clave: una llamada de verdad cuesta dinero, y un
    diagnostico no deberia gastar por comprobarse.
    """
    import os
    if os.getenv("ANTHROPIC_API_KEY", "").strip():
        return _estado(OK, "clave configurada (no se consulta por no gastar)")
    return _estado(LIMITED, "sin ANTHROPIC_API_KEY; la cascada sigue sin esta fuente")


# Orden de la cascada de arbitros, para que el panel se lea como se consulta.
SONDAS = (
    ("Investigador web (DuckDuckGo)", _diag_buscador_web),
    ("football-data.org", _diag_football_data),
    ("Sportmonks", _diag_sportmonks),
    ("Claude (búsqueda web)", _diag_claude),
    ("SofaScore", _diag_sofascore),
    ("Prensa (Google News)", _diag_prensa_rss),
    ("BeSoccer", _diag_besoccer),
    ("API-Football (respaldo)", _diag_api_football),
)


class MultiSourceFetcher:

    def diagnose_connectivity(self, incluir=None):
        """
        Estado de conexion de todas las fuentes de la cascada.

        Sondea cada una contra su endpoint REAL, el mismo que usa la busqueda,
        en lugar de mirar si hay una clave configurada. La diferencia importa:
        SofaScore estuvo meses devolviendo 200 sin un solo partido porque habian
        cambiado la forma del JSON, y cualquier comprobacion que solo mirase el
        codigo de estado lo habria dado por sano.

        Devuelve un diccionario listo para la barra lateral:

            {"SofaScore": {"status": "OK", "detail": "responde y devuelve..."}}

        con tres estados: OK (verde), LIMITED (ambar, la fuente responde pero
        no sirve del todo) y ERROR (rojo). Una sonda que falle no tumba a las
        demas: se anota su error y se sigue.

        Args:
            incluir: nombres a sondear. Por defecto, todas.
        """
        resultados = {}
        for nombre, sonda in SONDAS:
            if incluir is not None and nombre not in incluir:
                continue
            try:
                resultados[nombre] = sonda()
            except Exception as e:
                resultados[nombre] = _estado(
                    ERROR, f"la sonda fallo: {type(e).__name__}: {str(e)[:70]}")
        return resultados

    # =========================================================================
    # ÁRBITROS — cascada de 7 fuentes (API-Football es FUENTE 0)
    # =========================================================================
    def fetch_referee(self, home, away, match_date, league):
        print(f"\n[MSF] ÁRBITRO: {home} vs {away} | {league}")
        safe_date = match_date if match_date else datetime.now()
        sofa_link = None
        _pendiente_investigador = None

        # Calcular horas para el partido
        try:
            hours = (safe_date - datetime.now()).total_seconds() / 3600
        except Exception:
            hours = 999

        # ── FUENTE 0: Investigador web ────────────────────────────────────────
        # Va primero porque es la unica que corrobora antes de responder: exige
        # fuente oficial o dos fuentes independientes de acuerdo. Las de mas
        # abajo devuelven el primer nombre que encuentran, y cortar la cascada
        # con un nombre sin confirmar es exactamente como se llego a mostrar un
        # arbitro que no era el designado.
        try:
            from src.data import investigador_web as _iw
            veredicto = _iw.investigar_arbitro(home, away, safe_date, league)
            if veredicto.get("estado") == _iw.VERIFICADO:
                print(f"  [0-Investigador] ✅ {veredicto['name']} — {veredicto['motivo']}")
                return _iw.a_formato_cascada(veredicto)
            # PROBABLE y PENDIENTE se guardan y se deciden al final: puede que
            # una fuente posterior corrobore el mismo nombre.
            _pendiente_investigador = veredicto
            print(f"  [0-Investigador] {veredicto.get('estado')}: "
                  f"{veredicto.get('motivo', '')}")
        except Exception as e:
            _pendiente_investigador = None
            print(f"  [0-Investigador] Error: {type(e).__name__}: {e}")

        # ── FUENTE 0b: Football-Data.org (verificación adicional) ─────────────
        fd_client = _get_football_data_client()
        if fd_client:
            try:
                from src.data.football_data_org import COMPETITION_CODES
                comp_code = COMPETITION_CODES.get(_norm_league(league))
                if comp_code:
                    # Buscar partido con árbitro en Football-Data.org
                    matches = fd_client.get_upcoming_matches(comp_code)
                    if not matches:
                        matches = fd_client.get_matches_today(comp_code)
                    for m in (matches or []):
                        mh = m.get("homeTeam", {}).get("shortName", "") or m.get("homeTeam", {}).get("name", "")
                        ma = m.get("awayTeam", {}).get("shortName", "") or m.get("awayTeam", {}).get("name", "")
                        if (_norm_team_name(mh) in _norm_team_name(home) or
                            _norm_team_name(home) in _norm_team_name(mh)):
                            if (_norm_team_name(ma) in _norm_team_name(away) or
                                _norm_team_name(away) in _norm_team_name(ma)):
                                # Obtener árbitros del partido
                                match_id = m.get("id")
                                if match_id:
                                    try:
                                        match_detail = fd_client.get_match_with_referees(match_id)
                                        if match_detail and match_detail.get("referees"):
                                            for ref_info in match_detail["referees"]:
                                                if ref_info.get("role") in ("REFEREE", None, ""):
                                                    ref_name = ref_info.get("name", "")
                                                    if ref_name and _arbitro_valido(ref_name, "0b-FootballData"):
                                                        print(f"  [0b-FootballData] ✅ {ref_name}")
                                                        from src.models.base import RefereeStrictness
                                                        return _enrich({
                                                            "name": ref_name,
                                                            "strictness": RefereeStrictness.MEDIUM,
                                                            "avg_cards": 4.0,
                                                            "estado": "VERIFICADO",
                                                            "motivo": "Confirmado por football-data.org (oficiales del partido).",
                                                            "source": "Football-Data.org (oficial)",
                                                            "verification_link": f"https://www.sofascore.com",
                                                            "_is_fallback": False,
                                                            "confidence": "HIGH",
                                                        })
                                    except Exception as e2:
                                        print(f"  [0b-FootballData] match detail error: {e2}")
                                break
            except Exception as e:
                print(f"  [0b-FootballData] Error: {e}")

        # ── FUENTE 0c: Sportmonks ────────────────────────────────────────────
        # Va con las oficiales porque lee la designacion del propio partido, no
        # un indicio de prensa. El modulo se aparta solo cuando el plan no cubre
        # la competicion, que es el caso de todos los partidos espanoles, asi
        # que en LaLiga esta fuente no cuesta ni una peticion.
        try:
            from src.data import sportmonks_arbitros as _sm
            sm_ref = _sm.buscar_arbitro(home, away, safe_date, league)
            if sm_ref and _arbitro_valido(sm_ref["name"], "0c-Sportmonks"):
                print(f"  [0c-Sportmonks] ✅ {sm_ref['name']}")
                _marcar_fuente("Sportmonks", True)
                return _enrich(sm_ref)
        except Exception as e:
            print(f"  [0c-Sportmonks] Error: {type(e).__name__}: {e}")
            _marcar_fuente("Sportmonks", False, f"{type(e).__name__}: {e}")

        # ── FUENTE 1: Claude API con web_search ──────────────────────────────
        if hours < 48:
            try:
                from src.data.scrapers.sofascore_api import fetch_referee_via_claude
                r = fetch_referee_via_claude(home, away, league)
                if r and r.get("name") and _arbitro_valido(r["name"], "1-Claude"):
                    print(f"  [1-Claude] ✅ {r['name']}")
                    return _enrich(r)
            except Exception as e:
                print(f"  [1-Claude] {e}")

        # ── FUENTE 2: SofaScore API ───────────────────────────────────────────
        try:
            from src.data.scrapers.sofascore_api import fetch_referee as sf_ref
            sf = sf_ref(home, away, safe_date)
            if sf:
                sofa_link = sf.get("verification_link")
                if sf.get("name") and not sf.get("_is_fallback") and _arbitro_valido(sf["name"], "2-SofaScore"):
                    print(f"  [2-SofaScore] ✅ {sf['name']}")
                    return _enrich(sf)
        except Exception as e:
            print(f"  [2-SofaScore] {e}")

        # ── FUENTE 3: Google News RSS ─────────────────────────────────────────
        try:
            from src.data.scrapers.sofascore_api import fetch_referee_rss
            rss = fetch_referee_rss(home, away, league)
            if rss and rss.get("name") and _arbitro_valido(rss["name"], "3-RSS"):
                print(f"  [3-RSS] {rss['name']} (sin corroborar)")
                if sofa_link: rss.setdefault("verification_link", sofa_link)
                return _enrich(rss, estado="PROBABLE")
        except Exception as e:
            print(f"  [3-RSS] {e}")

        # ── FUENTE 4: Scraper específico de liga ─────────────────────────────
        try:
            scraper = _get_liga_scraper(league)
            if scraper:
                r = scraper.fetch_referee(home, away, safe_date)
                name = r.get("name","")
                if (name and name not in ["Por Detectar", ""] and not r.get("_is_fallback")
                        and _arbitro_valido(name, "4-LigaScraper")):
                    print(f"  [4-LigaScraper] ✅ {name}")
                    if sofa_link: r.setdefault("verification_link", sofa_link)
                    return _enrich(r)
        except Exception as e:
            print(f"  [4-LigaScraper] {e}")

        # ── FUENTE 5: BeSoccer ────────────────────────────────────────────────
        try:
            from src.data.scrapers.besoccer_scraper import fetch_referee as bs_ref
            bs = bs_ref(home, away)
            if bs and bs.get("name") and _arbitro_valido(bs["name"], "5-BeSoccer"):
                print(f"  [5-BeSoccer] ✅ {bs['name']}")
                if sofa_link: bs.setdefault("verification_link", sofa_link)
                return _enrich(bs)
        except Exception as e:
            print(f"  [5-BeSoccer] {e}")

        # ── RESPALDO: API-Football ────────────────────────────────────────────
        # Baja de primera fuente a respaldo por politica de cascada: el plan
        # gratuito no cubre calendario futuro, asi que gastar aqui una peticion
        # de las 100 diarias solo tiene sentido dentro de su ventana de fechas.
        _tipo = _cascada.clasificar(safe_date)
        if not _cascada.api_football_puede_responder(_tipo, fecha=safe_date):
            _motivo_af = _motivo_omision(_tipo)
            print(f"  [resp-API-Football] Omitida: {_motivo_af}")
        else:
            af_client = _get_api_football_client()
            if af_client:
                try:
                    fixture_id = _find_fixture_id(af_client, home, away, league, safe_date)
                    if fixture_id:
                        ref_data = af_client.get_referee_from_fixture(fixture_id)
                        if ref_data and ref_data.get("name"):
                            ref_name = ref_data["name"]
                            print(f"  [resp-API-Football] ✅ {ref_name} (fixture_id={fixture_id})")
                            # Obtener perfil estadístico del árbitro
                            try:
                                profile = af_client.compute_referee_profile(ref_name)
                                avg_cards = profile.get("avg_cards", "?")
                                strictness = profile.get("strictness", "MEDIUM")
                                matches_count = profile.get("matches_count", 0)
                            except Exception:
                                avg_cards = "?"
                                strictness = "MEDIUM"
                                matches_count = 0

                            # Mapear strictness al formato de la app
                            from src.models.base import RefereeStrictness
                            strict_map = {
                                "HIGH": RefereeStrictness.HIGH,
                                "LOW": RefereeStrictness.LOW,
                                "MEDIUM": RefereeStrictness.MEDIUM,
                            }
                            ref_result = {
                                "name": ref_name,
                                "estado": "VERIFICADO",
                                "motivo": "Confirmado por API-Football (dato oficial del fixture).",
                                "strictness": strict_map.get(strictness, RefereeStrictness.MEDIUM),
                                "avg_cards": avg_cards if avg_cards != "?" else 4.0,
                                "source": f"API-Football (oficial)",
                                "verification_link": f"https://www.sofascore.com",
                                "_is_fallback": False,
                                "fixture_id": fixture_id,
                                "profile": profile if 'profile' in dir() else {},
                                "confidence": ref_data.get("confidence", "HIGH"),
                            }
                            return _enrich(ref_result)
                    else:
                        print(f"  [resp-API-Football] No se encontró fixture_id para {home} vs {away}")
                except Exception as e:
                    print(f"  [resp-API-Football] Error: {e}")


        # ── FALLBACK: pedir al usuario ────────────────────────────────────────
        # Si el investigador tenia un candidato sin corroborar, se devuelve
        # marcado como PROBABLE en lugar de tirarlo: el supervisor lo pedira
        # confirmar, que es mejor que no dar ninguna pista.
        if _pendiente_investigador and _pendiente_investigador.get("name"):
            from src.data import investigador_web as _iw
            print(f"  [MSF] Sin confirmar; se devuelve el candidato del investigador "
                  f"({_pendiente_investigador['name']}) para validación manual")
            salida = _iw.a_formato_cascada(_pendiente_investigador)
            if sofa_link:
                salida.setdefault("verification_link", sofa_link)
            # Esta salida no pasa por _enrich, asi que el estado de la API se
            # adjunta aqui: es la rama que se toma cuando el investigador tiene
            # candidato pero nadie lo corrobora, justo el caso en el que saber
            # que faltaba la fuente de pago explica la falta de corroboracion.
            from src.data import resiliencia_api as _res_p
            salida.setdefault("degradacion", _res_p.resumen())
            return salida

        from src.models.base import RefereeStrictness
        from src.data import resiliencia_api as _res
        print(f"  [MSF] ❌ No encontrado en ninguna fuente")
        consultar = (_pendiente_investigador or {}).get("consultar", [])

        # El motivo cambia segun API-Football estuviera disponible o no, y la
        # diferencia importa: si la fuente de pago esta caida, el usuario tiene
        # que saber que la busqueda se hizo solo con las secundarias, y que no
        # encontrar al arbitro no significa que no este designado.
        _degradado = _res.resumen()
        if _degradado["degradada"]:
            motivo = ("Ninguna de las fuentes secundarias publica todavía la "
                      "designación. " + _res.texto_estado())
        else:
            motivo = "Ninguna fuente publica todavía la designación de este partido."

        return {
            "name": "Por Detectar",
            "strictness": RefereeStrictness.MEDIUM,
            "avg_cards": 4.0,
            "source": "Introduce el árbitro manualmente",
            "verification_link": sofa_link or "https://www.sofascore.com",
            "_is_fallback": True,
            "estado": "PENDIENTE",
            "motivo": motivo,
            "consultar": consultar,
            "degradacion": _degradado,
        }

    # =========================================================================
    # ALINEACIONES — cascada de 5 fuentes (API-Football es FUENTE 0)
    # =========================================================================
    def fetch_lineup(self, home, away, match_date, league):
        print(f"\n[MSF] ALINEACIÓN: {home} vs {away} | {league}")
        safe_date = match_date if match_date else datetime.now()

        # ── FUENTE 1: SofaScore API ───────────────────────────────────────────
        try:
            from src.data.scrapers.sofascore_api import fetch_lineups as sf_lu
            sf = sf_lu(home, away, safe_date)
            if sf and (sf.get("home") or sf.get("away")):
                sf.setdefault("bajas", [])
                print(f"  [1-SofaScore] ✅ {len(sf.get('home',[]))}+{len(sf.get('away',[]))}")
                return sf
        except Exception as e:
            print(f"  [1-SofaScore] {e}")

        # ── FUENTE 2: Scraper específico de liga ─────────────────────────────
        try:
            scraper = _get_liga_scraper(league)
            if scraper:
                r = scraper.fetch_lineup(home, away, safe_date)
                if r.get("home") or r.get("away"):
                    r.setdefault("bajas", [])
                    print(f"  [2-LigaScraper] ✅ {len(r.get('home',[]))}+{len(r.get('away',[]))}")
                    return r
        except Exception as e:
            print(f"  [2-LigaScraper] {e}")

        # ── FUENTE 3: BeSoccer ────────────────────────────────────────────────
        try:
            from src.data.scrapers.besoccer_scraper import fetch_lineup as bs_lu
            bs = bs_lu(home, away)
            if bs.get("home") or bs.get("away"):
                print(f"  [3-BeSoccer] ✅ {len(bs.get('home',[]))}+{len(bs.get('away',[]))}")
                return bs
        except Exception as e:
            print(f"  [3-BeSoccer] {e}")

        # ── RESPALDO: API-Football ────────────────────────────────────────────
        # Baja de primera fuente a respaldo por politica de cascada: el plan
        # gratuito no cubre calendario futuro, asi que gastar aqui una peticion
        # de las 100 diarias solo tiene sentido dentro de su ventana de fechas.
        _tipo = _cascada.clasificar(safe_date)
        if not _cascada.api_football_puede_responder(_tipo, fecha=safe_date):
            _motivo_af = _motivo_omision(_tipo)
            print(f"  [resp-API-Football] Omitida: {_motivo_af}")
        else:
            # af_client se leia aqui sin haberse creado nunca en esta funcion:
            # solo existia en fetch_referee. Era un NameError que reventaba la
            # obtencion de alineaciones cada vez que la fecha caia dentro de la
            # ventana de API-Football, justo cuando esta fuente podia responder.
            af_client = _get_api_football_client()
            if af_client:
                try:
                    fixture_id = _find_fixture_id(af_client, home, away, league, safe_date)
                    if fixture_id:
                        lineups = af_client.get_lineups(fixture_id)
                        if lineups and len(lineups) >= 2:
                            home_players = []
                            away_players = []
                            home_formation = ""
                            away_formation = ""

                            for team_lu in lineups:
                                team_name = team_lu.get("team", {}).get("name", "")
                                formation = team_lu.get("formation", "")
                                starters = []
                                for p in team_lu.get("startXI", []):
                                    pname = p.get("player", {}).get("name", "")
                                    if pname:
                                        starters.append(pname)

                                if (_norm_team_name(team_name) in _norm_team_name(home) or
                                    _norm_team_name(home) in _norm_team_name(team_name)):
                                    home_players = starters
                                    home_formation = formation
                                else:
                                    away_players = starters
                                    away_formation = formation

                            if home_players or away_players:
                                print(f"  [resp-API-Football] ✅ {len(home_players)}+{len(away_players)} jugadores (formaciones: {home_formation}/{away_formation})")
                                return {
                                    "home": home_players,
                                    "away": away_players,
                                    "bajas": [],
                                    "source": f"API-Football (oficial) — {home_formation} vs {away_formation}",
                                    "is_official": True,
                                    "verification_link": "https://www.sofascore.com",
                                    "_is_fallback": False,
                                    "formation_home": home_formation,
                                    "formation_away": away_formation,
                                }

                        # Si solo hay alineaciones predichas
                        if lineups and len(lineups) == 1:
                            team_lu = lineups[0]
                            starters = [p.get("player", {}).get("name", "") for p in team_lu.get("startXI", [])]
                            starters = [s for s in starters if s]
                            team_name = team_lu.get("team", {}).get("name", "")
                            formation = team_lu.get("formation", "")
                            if starters:
                                is_home = (_norm_team_name(team_name) in _norm_team_name(home) or
                                          _norm_team_name(home) in _norm_team_name(team_name))
                                result = {
                                    "bajas": [],
                                    "source": f"API-Football (parcial) — {formation}",
                                    "is_official": True,
                                    "verification_link": "https://www.sofascore.com",
                                    "_is_fallback": False,
                                }
                                if is_home:
                                    result["home"] = starters
                                    result["away"] = []
                                else:
                                    result["home"] = []
                                    result["away"] = starters
                                print(f"  [resp-API-Football] ✅ Parcial: {len(starters)} jugadores de {team_name}")
                                return result
                except Exception as e:
                    print(f"  [resp-API-Football] Error: {e}")


        # ── FUENTE 4: Sin datos web ───────────────────────────────────────────
        print(f"  [MSF] Sin alineaciones disponibles en fuentes web")
        return {
            "home": [], "away": [], "bajas": [],
            "source": "No disponible — se usará BD interna",
            "verification_link": "https://www.sofascore.com",
            "_is_fallback": True
        }
