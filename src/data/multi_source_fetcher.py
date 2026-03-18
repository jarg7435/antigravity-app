"""
MultiSourceFetcher — Cascada de fuentes para árbitros y alineaciones
=====================================================================
Árbitros  → 1.Claude API  2.SofaScore  3.RSS  4.LigaScraper  5.BeSoccer  6.Manual
Alineaciones → 1.SofaScore  2.LigaScraper  3.BeSoccer  4.BD interna
"""
from datetime import datetime
from typing import Dict, Optional


def _norm_league(league):
    n = league.lower().split("(")[0].strip().replace("ea sports","").replace("santander","").strip()
    if "la liga" in n or "primera" in n or "espa" in n: return "La Liga"
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
    # ÁRBITROS — cascada de 5 fuentes
    # =========================================================================
    def fetch_referee(self, home, away, match_date, league):
        print(f"\n[MSF] ÁRBITRO: {home} vs {away} | {league}")
        safe_date = match_date if match_date else datetime.now()
        sofa_link = None

        # Calcular horas para el partido
        try:
            hours = (safe_date - datetime.now()).total_seconds() / 3600
        except Exception:
            hours = 999

        # ── FUENTE 1: Claude API con web_search ──────────────────────────────
        # Usa la misma búsqueda que harías en Google: "árbitro Barcelona Sevilla"
        # Solo cuando hay API key y el partido es en <48h (árbitro ya publicado)
        if hours < 48:
            try:
                from src.data.scrapers.sofascore_api import fetch_referee_via_claude
                r = fetch_referee_via_claude(home, away, league)
                if r and r.get("name"):
                    print(f"  [1-Claude] ✅ {r['name']}")
                    return _enrich(r)
            except Exception as e:
                print(f"  [1-Claude] {e}")

        # ── FUENTE 2: SofaScore API ───────────────────────────────────────────
        try:
            from src.data.scrapers.sofascore_api import fetch_referee as sf_ref
            sf = sf_ref(home, away)
            if sf:
                sofa_link = sf.get("verification_link")
                if sf.get("name") and not sf.get("_is_fallback"):
                    print(f"  [2-SofaScore] ✅ {sf['name']}")
                    return _enrich(sf)
        except Exception as e:
            print(f"  [2-SofaScore] {e}")

        # ── FUENTE 3: Google News RSS ─────────────────────────────────────────
        try:
            from src.data.scrapers.sofascore_api import fetch_referee_rss
            rss = fetch_referee_rss(home, away)
            if rss and rss.get("name"):
                print(f"  [3-RSS] ✅ {rss['name']}")
                if sofa_link: rss.setdefault("verification_link", sofa_link)
                return _enrich(rss)
        except Exception as e:
            print(f"  [3-RSS] {e}")

        # ── FUENTE 4: Scraper específico de liga ─────────────────────────────
        try:
            scraper = _get_liga_scraper(league)
            if scraper:
                r = scraper.fetch_referee(home, away, safe_date)
                name = r.get("name","")
                if name and name not in ["Por Detectar",""] and not r.get("_is_fallback"):
                    print(f"  [4-LigaScraper] ✅ {name}")
                    if sofa_link: r.setdefault("verification_link", sofa_link)
                    return _enrich(r)
        except Exception as e:
            print(f"  [4-LigaScraper] {e}")

        # ── FUENTE 5: BeSoccer ────────────────────────────────────────────────
        try:
            from src.data.scrapers.besoccer_scraper import fetch_referee as bs_ref
            bs = bs_ref(home, away)
            if bs and bs.get("name"):
                print(f"  [5-BeSoccer] ✅ {bs['name']}")
                if sofa_link: bs.setdefault("verification_link", sofa_link)
                return _enrich(bs)
        except Exception as e:
            print(f"  [5-BeSoccer] {e}")

        # ── FALLBACK: pedir al usuario ────────────────────────────────────────
        from src.models.base import RefereeStrictness
        print(f"  [MSF] ❌ No encontrado en ninguna fuente")
        return {
            "name": "Por Detectar",
            "strictness": RefereeStrictness.MEDIUM,
            "avg_cards": 4.0,
            "source": "Introduce el árbitro manualmente",
            "verification_link": sofa_link or "https://www.sofascore.com",
            "_is_fallback": True
        }

    # =========================================================================
    # ALINEACIONES — cascada de 4 fuentes
    # =========================================================================
    def fetch_lineup(self, home, away, match_date, league):
        print(f"\n[MSF] ALINEACIÓN: {home} vs {away} | {league}")
        safe_date = match_date if match_date else datetime.now()

        # ── FUENTE 1: SofaScore API ───────────────────────────────────────────
        try:
            from src.data.scrapers.sofascore_api import fetch_lineups as sf_lu
            sf = sf_lu(home, away)
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

        # ── FUENTE 4: Sin datos web ───────────────────────────────────────────
        print(f"  [MSF] Sin alineaciones disponibles en fuentes web")
        return {
            "home": [], "away": [], "bajas": [],
            "source": "No disponible — se usará BD interna",
            "verification_link": "https://www.sofascore.com",
            "_is_fallback": True
        }
