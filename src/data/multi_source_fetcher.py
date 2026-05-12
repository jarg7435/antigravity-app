"""
MultiSourceFetcher — Cascada de fuentes para árbitros y alineaciones
=====================================================================
VERSIÓN 3.0 — Fuentes REALES verificadas + sin árbitros aleatorios

Árbitros  → 1.API-Football  2.football-data.org  3.Sportmonks
            4.FutbolFantasy Designaciones  5.SofaScore
            6.Google News RSS  7.LigaScraper  8.BeSoccer
Alineaciones → 1.API-Football  2.football-data.org  3.SofaScore
            4.LigaScraper  5.BeSoccer  6.BD interna

CAMBIO CRÍTICO vs v2:
  - football-data.org como fuente 2 (FUNCIONA para partidos finalizados)
  - FutbolFantasy Designaciones como fuente 4 (mejor para La Liga)
  - Eliminado random.choice en fallbacks (causaba árbitros incorrectos)
  - Sin árbitro aleatorio si no se encuentra → "No Detectado"
  - Mejor matching de equipos con normalización
  - Diagnóstico de conectividad API
"""
from datetime import datetime
from typing import Dict, Optional
import logging

logger = logging.getLogger("LAGEMA_MSF")


def _norm_league(league):
    n = league.lower().split("(")[0].strip().replace("ea sports","").replace("santander","").strip()
    if "la liga" in n or "primera" in n or "espa" in n: return "La Liga"
    if "premier" in n: return "Premier League"
    if "serie a" in n or "italia" in n: return "Serie A"
    if "bundesliga" in n or "german" in n: return "Bundesliga"
    if "ligue 1" in n or "france" in n: return "Ligue 1"
    if "champions" in n or "uefa" in n: return "Champions League"
    return n


# Mapping de ligas a IDs de API-Football
LEAGUE_ID_MAP = {
    "La Liga": 140,
    "Premier League": 39,
    "Bundesliga": 78,
    "Serie A": 135,
    "Ligue 1": 61,
    "Champions League": 2,
    "Europa League": 3,
    "Conference League": 848,
}

# Mapping de ligas a códigos football-data.org
FD_COMPETITION_CODES = {
    "La Liga": "PD",
    "Premier League": "PL",
    "Bundesliga": "BL1",
    "Serie A": "SA",
    "Ligue 1": "FL1",
    "Champions League": "CL",
    "Europa League": "EL",
    "Conference League": "EC",
}


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
        logger.debug(f"liga scraper error: {e}")
    return None


def _enrich(ref):
    try:
        from src.data.referee_database import enrich_referee
        ref = enrich_referee(ref)
    except Exception:
        from src.models.base import RefereeStrictness
        ref.setdefault("strictness", RefereeStrictness.MEDIUM)
        ref.setdefault("avg_cards", 4.0)
    ref.setdefault("_is_fallback", False)
    return ref


def _team_matches(query_name, api_name):
    """Matching flexible de nombres de equipos."""
    q = query_name.lower().strip()
    a = api_name.lower().strip()
    if q == a:
        return True
    # Quitar prefijos comunes
    import re
    q_clean = re.sub(r'^(rc|fc|cf|cd|sd|ac|as|ssc)\s+', '', q).strip()
    a_clean = re.sub(r'^(rc|fc|cf|cd|sd|ac|as|ssc)\s+', '', a).strip()
    if q_clean == a_clean:
        return True
    if q in a or a in q:
        return True
    # Matching por palabras clave (>4 chars)
    q_words = {w for w in q.split() if len(w) > 3}
    a_words = {w for w in a.split() if len(w) > 3}
    if q_words and a_words and len(q_words & a_words) >= 1:
        return True
    return False


class MultiSourceFetcher:

    # =========================================================================
    # ÁRBITROS — cascada de 8 fuentes (APIs REALES primero)
    # =========================================================================
    def fetch_referee(self, home, away, match_date, league):
        """
        Busca árbitro con prioridad en APIs REALES.
        
        Orden de cascada:
          1. football-data.org (CONFIRMADO FUNCIONAL — árbitros reales)
          2. API-Football: fixture.referee (si suscripción activa)
          3. Sportmonks: base de datos de árbitros
          4. FutbolFantasy Designaciones (La Liga específico)
          5. SofaScore: scraping
          6. Google News RSS: prensa (último recurso automatizado)
          7. Liga scraper: scraper específico por liga
          8. BeSoccer: scraping
          
        IMPORTANTE: NUNCA devuelve árbitro aleatorio.
        Si no se encuentra, devuelve "No Detectado" con _is_fallback=True.
        """
        logger.info(f"[MSF] ÁRBITRO: {home} vs {away} | {league}")
        safe_date = match_date if match_date else datetime.now()
        sofa_link = None

        # Calcular horas para el partido
        try:
            hours = (safe_date - datetime.now()).total_seconds() / 3600
        except Exception:
            hours = 999

        # ── FUENTE 1: football-data.org (CONFIRMADO FUNCIONAL) ──────────
        try:
            from src.data.api_manager import APIManager
            api = APIManager()
            norm_league = _norm_league(league)
            comp_code = FD_COMPETITION_CODES.get(norm_league)
            if comp_code:
                date_str = safe_date.strftime("%Y-%m-%d") if safe_date else None
                if date_str:
                    # Buscar en rango +/-3 días
                    from datetime import timedelta
                    date_from = (safe_date - timedelta(days=3)).strftime("%Y-%m-%d")
                    date_to = (safe_date + timedelta(days=3)).strftime("%Y-%m-%d")
                    matches = api.football_data.get_competition_matches(
                        comp_code, date_from=date_from, date_to=date_to
                    )
                    for m in matches:
                        ht = m.get("homeTeam", {}).get("shortName", m.get("homeTeam", {}).get("name", ""))
                        at = m.get("awayTeam", {}).get("shortName", m.get("awayTeam", {}).get("name", ""))
                        if _team_matches(home, ht) and _team_matches(away, at):
                            referees = m.get("referees", [])
                            for ref in referees:
                                ref_name = ref.get("name", "")
                                ref_role = ref.get("role", "") or ref.get("nationality", "")
                                if ref_name and len(ref_name.split()) >= 2:
                                    logger.info(f"  [1-football-data.org] ✅ {ref_name} (role: {ref_role})")
                                    return _enrich({
                                        "name": ref_name,
                                        "source": f"football-data.org ({ref_role or 'árbitro'})",
                                        "verification_link": None,
                                        "_is_fallback": False
                                    })
        except Exception as e:
            logger.debug(f"  [1-football-data.org] {e}")

        # ── FUENTE 2: API-Football (DATO OFICIAL si suscripción activa) ─
        try:
            from src.data.api_manager import APIManager
            api = APIManager()
            
            date_str = safe_date.strftime("%Y-%m-%d") if safe_date else None
            league_id = LEAGUE_ID_MAP.get(_norm_league(league))
            if date_str:
                fixtures = api.api_football.get_fixtures(date=date_str, league_id=league_id)
                if fixtures:
                    for f in fixtures:
                        ht = f.get("teams", {}).get("home", {}).get("name", "")
                        at = f.get("teams", {}).get("away", {}).get("name", "")
                        if _team_matches(home, ht) and _team_matches(away, at):
                            referee_name = f.get("fixture", {}).get("referee", "")
                            fixture_id = f.get("fixture", {}).get("id")
                            if referee_name and len(referee_name.split()) >= 2:
                                logger.info(f"  [2-API-Football] ✅ {referee_name} (OFICIAL)")
                                result = {
                                    "name": referee_name,
                                    "source": "API-Football (Oficial)",
                                    "verification_link": f"https://www.api-football.com/",
                                    "_is_fallback": False
                                }
                                try:
                                    ref_data = api.get_referee_data(referee_name)
                                    if ref_data:
                                        result["referee_details"] = ref_data
                                except Exception:
                                    pass
                                return _enrich(result)
                            
                            if fixture_id:
                                logger.info(f"  [2-API-Football] Partido encontrado (ID: {fixture_id}) pero sin árbitro asignado")
                else:
                    logger.warning("  [2-API-Football] ❌ Sin fixtures (suscripción expirada o sin conexión)")
        except Exception as e:
            logger.debug(f"  [2-API-Football] {e}")

        # ── FUENTE 3: Sportmonks (Base de datos de árbitros) ──────────────
        try:
            from src.data.api_manager import APIManager
            api = APIManager()
            # Buscar por fixture en Sportmonks (no por nombre de árbitro)
            date_str = safe_date.strftime("%Y-%m-%d") if safe_date else None
            if date_str:
                # Intentar buscar fixture por fecha
                import requests
                sm_key = api.sportmonks.api_token
                if sm_key:
                    r = requests.get(
                        f"https://api.sportmonks.com/v3/football/fixtures/between/{date_str}/{date_str}",
                        params={"api_token": sm_key},
                        timeout=10
                    )
                    if r.status_code == 200:
                        fixtures = r.json().get("data", [])
                        for fx in fixtures:
                            fx_name = fx.get("name", "").lower()
                            if home.lower().split()[0] in fx_name and away.lower().split()[0] in fx_name:
                                fx_id = fx.get("id")
                                # Obtener detalles del fixture
                                r2 = requests.get(
                                    f"https://api.sportmonks.com/v3/football/fixtures/{fx_id}",
                                    params={"api_token": sm_key, "include": "referee"},
                                    timeout=10
                                )
                                if r2.status_code == 200:
                                    fd = r2.json().get("data", {})
                                    ref_data = fd.get("referee", {})
                                    if ref_data:
                                        ref_name = ref_data.get("common_name") or ref_data.get("name", "")
                                        if ref_name and len(ref_name.split()) >= 2:
                                            logger.info(f"  [3-Sportmonks] ✅ {ref_name}")
                                            return _enrich({
                                                "name": ref_name,
                                                "source": "Sportmonks",
                                                "verification_link": None,
                                                "_is_fallback": False
                                            })
        except Exception as e:
            logger.debug(f"  [3-Sportmonks] {e}")

        # ── FUENTE 4: FutbolFantasy Designaciones (La Liga) ──────────────
        norm_league = _norm_league(league)
        if norm_league == "La Liga":
            try:
                from src.data.scrapers.la_liga import fetch_referee_designaciones
                ref = fetch_referee_designaciones(home, away)
                if ref and ref.get("name") and len(ref["name"].split()) >= 2:
                    logger.info(f"  [4-FutbolFantasy Designaciones] ✅ {ref['name']}")
                    return _enrich(ref)
            except Exception as e:
                logger.debug(f"  [4-FutbolFantasy Designaciones] {e}")

        # ── FUENTE 5: SofaScore API (scraping) ───────────────────────────
        try:
            from src.data.scrapers.sofascore_api import fetch_referee as sf_ref
            sf = sf_ref(home, away)
            if sf:
                sofa_link = sf.get("verification_link")
                if sf.get("name") and not sf.get("_is_fallback"):
                    logger.info(f"  [5-SofaScore] ✅ {sf['name']}")
                    return _enrich(sf)
        except Exception as e:
            logger.debug(f"  [5-SofaScore] {e}")

        # ── FUENTE 5b: Claude API con web_search ──────────────────────────
        if hours < 48:
            try:
                from src.data.scrapers.sofascore_api import fetch_referee_via_claude
                r = fetch_referee_via_claude(home, away, league)
                if r and r.get("name") and len(r["name"].split()) >= 2:
                    logger.info(f"  [5b-Claude] ✅ {r['name']}")
                    return _enrich(r)
            except Exception as e:
                logger.debug(f"  [5b-Claude] {e}")

        # ── FUENTE 6: Google News RSS ────────────────────────────────────
        try:
            from src.data.scrapers.sofascore_api import fetch_referee_rss
            rss = fetch_referee_rss(home, away)
            if rss and rss.get("name") and len(rss["name"].split()) >= 2:
                # ADVERTENCIA: RSS puede dar árbitros de noticias antiguas
                # Marcar como verificación pendiente
                rss["verification_status"] = "UNVERIFIED"
                logger.info(f"  [6-RSS] ⚠️ {rss['name']} (VERIFICAR)")
                if sofa_link: rss.setdefault("verification_link", sofa_link)
                return _enrich(rss)
        except Exception as e:
            logger.debug(f"  [6-RSS] {e}")

        # ── FUENTE 7: Scraper específico de liga ─────────────────────────
        try:
            scraper = _get_liga_scraper(league)
            if scraper:
                r = scraper.fetch_referee(home, away, safe_date)
                name = r.get("name", "")
                if name and name not in ["Por Detectar", ""] and not r.get("_is_fallback"):
                    logger.info(f"  [7-LigaScraper] ✅ {name}")
                    if sofa_link: r.setdefault("verification_link", sofa_link)
                    return _enrich(r)
        except Exception as e:
            logger.debug(f"  [7-LigaScraper] {e}")

        # ── FUENTE 8: BeSoccer ────────────────────────────────────────────
        try:
            from src.data.scrapers.besoccer_scraper import fetch_referee as bs_ref
            bs = bs_ref(home, away)
            if bs and bs.get("name") and len(bs["name"].split()) >= 2:
                logger.info(f"  [8-BeSoccer] ✅ {bs['name']}")
                if sofa_link: bs.setdefault("verification_link", sofa_link)
                return _enrich(bs)
        except Exception as e:
            logger.debug(f"  [8-BeSoccer] {e}")

        # ── FALLBACK: NO se encontró — pedir al usuario ──────────────────
        # NUNCA asignamos árbitro aleatorio
        from src.models.base import RefereeStrictness
        logger.warning("  [MSF] ❌ No encontrado en ninguna fuente — solicitar manual")
        return {
            "name": "No Detectado",
            "strictness": RefereeStrictness.MEDIUM,
            "avg_cards": 4.0,
            "source": "Introduce el árbitro manualmente",
            "verification_link": sofa_link or "https://www.rfef.es/noticias/arbitros/designaciones",
            "_is_fallback": True
        }

    def fetch_referee_press(self, home, away, league):
        """Búsqueda adicional en prensa deportiva (para La Liga)."""
        try:
            from src.data.scrapers.sofascore_api import fetch_referee_rss
            return fetch_referee_rss(home, away)
        except Exception:
            return None

    # =========================================================================
    # ALINEACIONES — cascada con APIs REALES primero
    # =========================================================================
    def fetch_lineup(self, home, away, match_date, league):
        """
        Busca alineaciones con prioridad en APIs REALES.
        
        Orden de cascada:
          1. API-Football: alineaciones confirmadas (1-2h antes)
          2. football-data.org
          3. SofaScore: scraping
          4. Liga scraper
          5. BeSoccer
          6. BD interna
        """
        logger.info(f"[MSF] ALINEACIÓN: {home} vs {away} | {league}")
        safe_date = match_date if match_date else datetime.now()

        # ── FUENTE 1: API-Football (ALINEACIONES OFICIALES) ───────────────
        try:
            from src.data.api_manager import APIManager
            api = APIManager()
            
            date_str = safe_date.strftime("%Y-%m-%d") if safe_date else None
            league_id = LEAGUE_ID_MAP.get(_norm_league(league))
            if date_str:
                fixtures = api.api_football.get_fixtures(date=date_str, league_id=league_id)
                if fixtures:
                    for f in fixtures:
                        ht = f.get("teams", {}).get("home", {}).get("name", "")
                        at = f.get("teams", {}).get("away", {}).get("name", "")
                        if _team_matches(home, ht) and _team_matches(away, at):
                            fixture_id = f.get("fixture", {}).get("id")
                            if fixture_id:
                                lineups = api.api_football.get_lineups(fixture_id)
                                if lineups and len(lineups) >= 2:
                                    home_players = []
                                    away_players = []
                                    
                                    for lineup in lineups:
                                        team_name = lineup.get("team", {}).get("name", "")
                                        formation = lineup.get("formation", "")
                                        start_xi = [p.get("player", {}).get("name", "") 
                                                   for p in lineup.get("startXI", [])]
                                        
                                        is_home = _team_matches(home, team_name)
                                        
                                        if is_home:
                                            home_players = start_xi
                                        else:
                                            away_players = start_xi
                                    
                                    if home_players or away_players:
                                        logger.info(f"  [1-API-Football] ✅ {len(home_players)}+{len(away_players)} (OFICIAL)")
                                        return {
                                            "home": home_players,
                                            "away": away_players,
                                            "bajas": [],
                                            "source": "API-Football (Oficial)",
                                            "verification_link": f"https://www.api-football.com/",
                                            "_is_fallback": False,
                                            "is_official": True,
                                            "formation_home": lineups[0].get("formation", "") if lineups else "",
                                            "formation_away": lineups[1].get("formation", "") if len(lineups) > 1 else "",
                                        }
        except Exception as e:
            logger.debug(f"  [1-API-Football] {e}")

        # ── FUENTE 2: SofaScore API ───────────────────────────────────────
        try:
            from src.data.scrapers.sofascore_api import fetch_lineups as sf_lu
            sf = sf_lu(home, away)
            if sf and (sf.get("home") or sf.get("away")):
                sf.setdefault("bajas", [])
                logger.info(f"  [2-SofaScore] ✅ {len(sf.get('home',[]))}+{len(sf.get('away',[]))}")
                return sf
        except Exception as e:
            logger.debug(f"  [2-SofaScore] {e}")

        # ── FUENTE 3: Scraper específico de liga ─────────────────────────
        try:
            scraper = _get_liga_scraper(league)
            if scraper:
                r = scraper.fetch_lineup(home, away, safe_date)
                if r.get("home") or r.get("away"):
                    r.setdefault("bajas", [])
                    logger.info(f"  [3-LigaScraper] ✅ {len(r.get('home',[]))}+{len(r.get('away',[]))}")
                    return r
        except Exception as e:
            logger.debug(f"  [3-LigaScraper] {e}")

        # ── FUENTE 4: BeSoccer ────────────────────────────────────────────
        try:
            from src.data.scrapers.besoccer_scraper import fetch_lineup as bs_lu
            bs = bs_lu(home, away)
            if bs.get("home") or bs.get("away"):
                logger.info(f"  [4-BeSoccer] ✅ {len(bs.get('home',[]))}+{len(bs.get('away',[]))}")
                return bs
        except Exception as e:
            logger.debug(f"  [4-BeSoccer] {e}")

        # ── FUENTE 5: Sin datos web ───────────────────────────────────────
        logger.warning("  [MSF] Sin alineaciones disponibles en fuentes web")
        return {
            "home": [], "away": [], "bajas": [],
            "source": "No disponible — se usará BD interna",
            "verification_link": "https://www.sofascore.com",
            "_is_fallback": True
        }

    # =========================================================================
    # DIAGNÓSTICO DE CONECTIVIDAD
    # =========================================================================
    def diagnose_connectivity(self):
        """
        Verifica qué APIs están realmente conectadas y devolviendo datos.
        Retorna dict con estado de cada fuente.
        """
        results = {}
        
        # 1. API-Football
        try:
            from src.data.api_manager import APIManager
            api = APIManager()
            status = api.api_football._get("status")
            if status and status.get("response"):
                results["api_football"] = {
                    "status": "OK",
                    "detail": "API-Football conectada y con suscripción activa"
                }
            else:
                results["api_football"] = {
                    "status": "ERROR",
                    "detail": "API-Football NO disponible (suscripción expirada o sin conexión)"
                }
        except Exception as e:
            results["api_football"] = {"status": "ERROR", "detail": str(e)[:100]}
        
        # 2. football-data.org
        try:
            from src.data.api_manager import APIManager
            api = APIManager()
            r = api.football_data._get("competitions/PD/matches", {"limit": 1})
            if r:
                results["football_data_org"] = {
                    "status": "OK",
                    "detail": "football-data.org conectada. NOTA: árbitros solo para partidos FINALIZADOS"
                }
            else:
                results["football_data_org"] = {
                    "status": "ERROR", 
                    "detail": "football-data.org sin respuesta"
                }
        except Exception as e:
            results["football_data_org"] = {"status": "ERROR", "detail": str(e)[:100]}
        
        # 3. Sportmonks
        try:
            from src.data.api_manager import APIManager
            api = APIManager()
            r = api.sportmonks._get("leagues", {"limit": 1})
            if r:
                has_data = bool(r) if isinstance(r, list) else bool(r.get("data", r))
                results["sportmonks"] = {
                    "status": "OK" if has_data else "LIMITED",
                    "detail": "Sportmonks conectada" + ("" if has_data else " (plan limitado)")
                }
            else:
                results["sportmonks"] = {
                    "status": "ERROR",
                    "detail": "Sportmonks sin respuesta"
                }
        except Exception as e:
            results["sportmonks"] = {"status": "ERROR", "detail": str(e)[:100]}
        
        return results
