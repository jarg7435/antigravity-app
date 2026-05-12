"""
MultiSourceFetcher — Cascada de fuentes para árbitros y alineaciones
=====================================================================
VERSIÓN 2.0 — Ahora usa APIs REALES como fuente primaria

Árbitros  → 1.API-Football (OFICIAL)  2.Sportmonks  3.SofaScore  4.RSS  5.LigaScraper  6.Manual
Alineaciones → 1.API-Football (OFICIAL)  2.SofaScore  3.LigaScraper  4.BeSoccer  5.BD interna

CAMBIO CRÍTICO vs v1:
  - Antes: usaba scraping/Claude/RSS como fuente 1 (poco fiable)
  - Ahora: usa API-Football y Sportmonks como fuente 1 y 2 (DATOS VERÍDICOS)
  - Solo cae a scraping cuando las APIs no responden
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


class MultiSourceFetcher:

    # =========================================================================
    # ÁRBITROS — cascada de 7 fuentes (APIs REALES primero)
    # =========================================================================
    def fetch_referee(self, home, away, match_date, league):
        """
        Busca árbitro con prioridad en APIs REALES de pago.
        
        Orden de cascada:
          1. API-Football: fixture.referee (DATO OFICIAL de la API)
          2. Sportmonks: base de datos de árbitros con estadísticas
          3. football-data.org: árbitro en competiciones europeas
          4. SofaScore: scraping (si APIs fallan)
          5. Google News RSS: prensa (último recurso automatizado)
          6. Liga scraper: scraper específico por liga
          7. BeSoccer: scraping
          8. Manual: el usuario introduce el nombre
        """
        logger.info(f"[MSF] ÁRBITRO: {home} vs {away} | {league}")
        safe_date = match_date if match_date else datetime.now()
        sofa_link = None

        # Calcular horas para el partido
        try:
            hours = (safe_date - datetime.now()).total_seconds() / 3600
        except Exception:
            hours = 999

        # ── FUENTE 1: API-Football (DATO OFICIAL) ─────────────────────────
        # El campo fixture.referee contiene el árbitro asignado oficialmente
        try:
            from src.data.api_manager import APIManager
            api = APIManager()
            
            # Buscar el partido por fecha y equipos
            date_str = safe_date.strftime("%Y-%m-%d") if safe_date else None
            if date_str:
                fixtures = api.api_football.get_fixtures(date=date_str)
                if fixtures:
                    for f in fixtures:
                        ht = f.get("teams", {}).get("home", {}).get("name", "")
                        at = f.get("teams", {}).get("away", {}).get("name", "")
                        # Matching flexible de equipos
                        if (home.lower() in ht.lower() or ht.lower() in home.lower() or
                            away.lower() in at.lower() or at.lower() in away.lower() or
                            home.lower() in at.lower() or away.lower() in ht.lower()):
                            referee_name = f.get("fixture", {}).get("referee", "")
                            fixture_id = f.get("fixture", {}).get("id")
                            if referee_name and len(referee_name.split()) >= 2:
                                logger.info(f"  [1-API-Football] ✅ {referee_name} (OFICIAL)")
                                result = {
                                    "name": referee_name,
                                    "source": "API-Football (Oficial)",
                                    "verification_link": f"https://www.api-football.com/",
                                    "_is_fallback": False
                                }
                                # Intentar obtener stats del árbitro via Sportmonks
                                try:
                                    ref_data = api.get_referee_data(referee_name)
                                    if ref_data:
                                        result["referee_details"] = ref_data
                                except Exception:
                                    pass
                                return _enrich(result)
                            
                            # Partido encontrado pero sin árbitro asignado aún
                            if fixture_id:
                                logger.info(f"  [1-API-Football] Partido encontrado (ID: {fixture_id}) pero sin árbitro asignado")
        except Exception as e:
            logger.debug(f"  [1-API-Football] {e}")

        # ── FUENTE 2: Sportmonks (Base de datos de árbitros) ──────────────
        try:
            from src.data.api_manager import APIManager
            api = APIManager()
            # Intentar buscar árbitro en Sportmonks por partido
            # Sportmonks tiene datos más completos de árbitros
            ref_data = api.get_referee_data(f"{home} {away}")
            if ref_data and ref_data.get("name"):
                logger.info(f"  [2-Sportmonks] ✅ {ref_data['name']}")
                return _enrich({
                    "name": ref_data["name"],
                    "source": "Sportmonks",
                    "verification_link": ref_data.get("common_name", ""),
                    "_is_fallback": False
                })
        except Exception as e:
            logger.debug(f"  [2-Sportmonks] {e}")

        # ── FUENTE 3: football-data.org (Competiciones europeas) ──────────
        try:
            from src.data.api_manager import APIManager
            api = APIManager()
            norm_league = _norm_league(league)
            comp_code = api._get_competition_code(norm_league)
            if comp_code:
                date_str = safe_date.strftime("%Y-%m-%d") if safe_date else None
                if date_str:
                    matches = api.football_data.get_competition_matches(
                        comp_code, date_from=date_str, date_to=date_str
                    )
                    for m in matches:
                        ht = m.get("homeTeam", {}).get("name", "")
                        at = m.get("awayTeam", {}).get("name", "")
                        if (home.lower() in ht.lower() or away.lower() in at.lower()):
                            referees = m.get("referees", [])
                            for ref in referees:
                                ref_name = ref.get("name", "")
                                if ref_name and len(ref_name.split()) >= 2:
                                    logger.info(f"  [3-football-data.org] ✅ {ref_name}")
                                    return _enrich({
                                        "name": ref_name,
                                        "source": "football-data.org",
                                        "verification_link": None,
                                        "_is_fallback": False
                                    })
        except Exception as e:
            logger.debug(f"  [3-football-data.org] {e}")

        # ── FUENTE 4: SofaScore API (scraping) ───────────────────────────
        try:
            from src.data.scrapers.sofascore_api import fetch_referee as sf_ref
            sf = sf_ref(home, away)
            if sf:
                sofa_link = sf.get("verification_link")
                if sf.get("name") and not sf.get("_is_fallback"):
                    logger.info(f"  [4-SofaScore] ✅ {sf['name']}")
                    return _enrich(sf)
        except Exception as e:
            logger.debug(f"  [4-SofaScore] {e}")

        # ── FUENTE 5: Claude API con web_search ──────────────────────────
        if hours < 48:
            try:
                from src.data.scrapers.sofascore_api import fetch_referee_via_claude
                r = fetch_referee_via_claude(home, away, league)
                if r and r.get("name"):
                    logger.info(f"  [5-Claude] ✅ {r['name']}")
                    return _enrich(r)
            except Exception as e:
                logger.debug(f"  [5-Claude] {e}")

        # ── FUENTE 6: Google News RSS ────────────────────────────────────
        try:
            from src.data.scrapers.sofascore_api import fetch_referee_rss
            rss = fetch_referee_rss(home, away)
            if rss and rss.get("name"):
                logger.info(f"  [6-RSS] ✅ {rss['name']}")
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
            if bs and bs.get("name"):
                logger.info(f"  [8-BeSoccer] ✅ {bs['name']}")
                if sofa_link: bs.setdefault("verification_link", sofa_link)
                return _enrich(bs)
        except Exception as e:
            logger.debug(f"  [8-BeSoccer] {e}")

        # ── FALLBACK: pedir al usuario ────────────────────────────────────
        from src.models.base import RefereeStrictness
        logger.warning("  [MSF] ❌ No encontrado en ninguna fuente")
        return {
            "name": "Por Detectar",
            "strictness": RefereeStrictness.MEDIUM,
            "avg_cards": 4.0,
            "source": "Introduce el árbitro manualmente",
            "verification_link": sofa_link or "https://www.sofascore.com",
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
          2. SofaScore: scraping
          3. Liga scraper
          4. BeSoccer
          5. BD interna
        """
        logger.info(f"[MSF] ALINEACIÓN: {home} vs {away} | {league}")
        safe_date = match_date if match_date else datetime.now()

        # ── FUENTE 1: API-Football (ALINEACIONES OFICIALES) ───────────────
        try:
            from src.data.api_manager import APIManager
            api = APIManager()
            
            date_str = safe_date.strftime("%Y-%m-%d") if safe_date else None
            if date_str:
                fixtures = api.api_football.get_fixtures(date=date_str)
                if fixtures:
                    for f in fixtures:
                        ht = f.get("teams", {}).get("home", {}).get("name", "")
                        at = f.get("teams", {}).get("away", {}).get("name", "")
                        if (home.lower() in ht.lower() or ht.lower() in home.lower() or
                            away.lower() in at.lower() or at.lower() in away.lower()):
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
                                        
                                        # Determinar si es home o away
                                        is_home = (home.lower() in team_name.lower() or 
                                                  team_name.lower() in home.lower())
                                        
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
