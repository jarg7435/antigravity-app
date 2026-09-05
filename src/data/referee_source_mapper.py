"""
Fuentes de designacion arbitral por competicion — La Gema JARG74.

QUE CAMBIO Y POR QUE
--------------------
Este modulo contenia un scraper por liga, y los cinco hacian lo mismo:
descargar la PORTADA de la federacion y aplicarle esta expresion regular al
texto completo de la pagina:

    ({local}).*?({visitante}).*?:?\\s*([A-Z][a-z]+(?:\\s[A-Z][a-z]+)+)

El `.*?` recorre la pagina entera sin limite, asi que enlazaba la palabra
"Athletic" de una noticia con la palabra "Atletico" de otra completamente
distinta y se quedaba con el primer par de palabras capitalizadas que viniera
detras. Ese par podia ser cualquier nombre propio de la portada. De ahi salio
mostrar a Ortiz Arias como arbitro del Athletic - Atletico de Madrid cuando la
designacion del CTA era Munuera Montero: el nombre tiene forma perfecta de
nombre de persona, de modo que ningun filtro posterior podia detectar el error.

El problema no era la fuente, era el metodo. Buscar la designacion exige
buscar, no raspar una portada: consultar por el partido concreto, exigir que el
nombre aparezca en una frase que hable de ese partido y no darlo por bueno
hasta que lo corrobore una segunda fuente. Eso es lo que hace
src/data/investigador_web.py, y este modulo delega ahi.

Se conserva la clase RefereeSourceMapper con su interfaz de siempre —
get_scraper(liga).fetch_referee(local, visitante, fecha) — para no romper a
quien ya la llama (MultiSourceFetcher y LineupFetcher). Lo que cambia es lo que
hay debajo.

Autor: Antigravity - La Gema JARG74
"""

from datetime import datetime
from typing import Dict

from src.models.base import RefereeStrictness


class RefereeSourceMapper:
    """
    Enruta cada competicion a su fuente de designaciones.

    Los portales oficiales viven ahora en investigador_web.PORTALES_OFICIALES,
    que es tambien quien decide que dominios cuentan como oficiales. Aqui se
    exponen por compatibilidad con el codigo que leia LEAGUE_SOURCES.
    """

    LEAGUE_SOURCES = {
        "La Liga": "https://www.rfef.es/noticias/arbitros/designaciones",
        "Premier League": "https://www.premierleague.com/referees/overview",
        "Serie A": "https://www.aia-figc.it/designazioni/cana/",
        "Bundesliga": "https://www.dfb.de/sportl-strukturen/schiedsrichter/ansetzungen/",
        "Ligue 1": "https://www.ligue1.fr/calendrier-resultats",
    }

    @classmethod
    def _normalize_league(cls, league: str) -> str:
        """Nombre canonico de la competicion, tolerante a las variantes de la UI."""
        from src.data.referee_database import liga_canonica

        canonica = liga_canonica(league)
        if canonica and canonica != "UEFA":
            return canonica
        if canonica == "UEFA":
            return "UEFA"
        return (league or "").strip()

    @classmethod
    def get_scraper(cls, league: str):
        """
        Buscador de designaciones para esa competicion.

        Ya no hay una clase por liga: el comportamiento correcto es el mismo
        para todas —buscar el partido concreto y corroborar— y solo cambia el
        portal oficial, que el investigador resuelve por su cuenta a partir del
        nombre de la liga. Mantener cinco copias de la misma logica fue
        justamente lo que propago el mismo fallo a las cinco.
        """
        return BuscadorDesignaciones(cls._normalize_league(league))


class BuscadorDesignaciones:
    """
    Adaptador entre la interfaz antigua de scraper y el investigador web.

    Traduce el veredicto del investigador (VERIFICADO / PROBABLE / PENDIENTE) al
    diccionario que espera la cascada, conservando el estado: un PROBABLE sale
    marcado como fallback para que el supervisor pida confirmarlo, en lugar de
    colarse como dato bueno.
    """

    def __init__(self, league: str = ""):
        self.league = league or ""

    def fetch_referee(self, home_team: str, away_team: str,
                      match_date: datetime = None) -> Dict:
        try:
            from src.data import investigador_web as iw
        except Exception as e:
            print(f"⚠️ Investigador web no disponible: {e}")
            return self._sin_designacion()

        try:
            veredicto = iw.investigar_arbitro(home_team, away_team,
                                              match_date or datetime.now(),
                                              self.league)
        except Exception as e:
            print(f"⚠️ Búsqueda de designación falló: {type(e).__name__}: {e}")
            return self._sin_designacion()

        if veredicto.get("estado") == iw.PENDIENTE or not veredicto.get("name"):
            return self._sin_designacion(veredicto)

        return iw.a_formato_cascada(veredicto)

    def _sin_designacion(self, veredicto: Dict = None) -> Dict:
        """
        Respuesta cuando no hay designacion publicada.

        Nunca devuelve un nombre. La version anterior tenia un _fallback_referee
        por scraper que al menos ya no inventaba, pero el codigo que llamaba no
        podia distinguir "no la hay todavia" de "no he sabido encontrarla"; aqui
        se dice cual de las dos cosas es.
        """
        veredicto = veredicto or {}
        consultar = veredicto.get("consultar") or []
        if not consultar:
            try:
                from src.data.investigador_web import _enlaces_de_consulta
                consultar = _enlaces_de_consulta(self.league)
            except Exception:
                consultar = []

        return {
            "name": "",
            "strictness": RefereeStrictness.MEDIUM,
            "avg_cards": 4.0,
            "source": "Designación no publicada todavía",
            "verification_link": consultar[0]["url"] if consultar else "",
            "consultar": consultar,
            "estado": "PENDIENTE",
            "motivo": veredicto.get(
                "motivo",
                "Ninguna fuente publica todavía la designación de este partido."),
            "_is_fallback": True,
        }


# -----------------------------------------------------------------------------
# Compatibilidad: nombres antiguos que otros modulos pueden seguir importando.
# Todos apuntan al mismo buscador; la liga la lleva el investigador.
# -----------------------------------------------------------------------------

class BaseRefereeScraper(BuscadorDesignaciones):
    """Alias historico. Toda la logica esta en BuscadorDesignaciones."""


class LaLigaRefereeScraper(BuscadorDesignaciones):
    def __init__(self):
        super().__init__("La Liga")


class PremierLeagueRefereeScraper(BuscadorDesignaciones):
    def __init__(self):
        super().__init__("Premier League")


class SerieARefereeScraper(BuscadorDesignaciones):
    def __init__(self):
        super().__init__("Serie A")


class BundesligaRefereeScraper(BuscadorDesignaciones):
    def __init__(self):
        super().__init__("Bundesliga")


class Ligue1RefereeScraper(BuscadorDesignaciones):
    def __init__(self):
        super().__init__("Ligue 1")


class InternationalRefereePoolScraper(BuscadorDesignaciones):
    def __init__(self):
        super().__init__("UEFA")


class FallbackRefereeScraper(BuscadorDesignaciones):
    def __init__(self):
        super().__init__("")
