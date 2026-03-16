"""
lineup_fetcher.py — LAGEMA JARG74 Ecosistema 4.0
================================================
Sistema profesional de obtención de alineaciones con:
- Freshness Score (validación temporal de datos)
- Uncertainty Penalty (penalización por calidad de datos)
- Cascada multi-fuente con verificación de integridad
- Logging completo para LearningEngine

Prioridad: P0-Crítico. Sin alineaciones frescas, todo el ecosistema colapsa.
"""

from typing import List, Dict, Optional, Literal
from dataclasses import dataclass
from datetime import datetime, timedelta
from enum import Enum
import time
import logging

from src.data.interface import DataProvider
from src.data.auto_lineup_fetcher import AutoLineupFetcher
from src.data.referee_source_mapper import RefereeSourceMapper
from src.data.multi_source_fetcher import MultiSourceFetcher

# Configuración de logging profesional
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s | %(levelname)-8s | %(message)s',
    datefmt='%H:%M:%S'
)
logger = logging.getLogger(__name__)


class LineupFreshness(Enum):
    """
    Sistema de clasificación temporal de alineaciones.
    Determina la confianza que podemos tener en los datos.
    """
    LIVE = "live"                    # < 1h del partido, fuente oficial
    CONFIRMED = "confirmed"          # 1-24h, prensa verificada múltiple
    PREDICTED = "predicted"          # >24h o modelos estadísticos
    FALLBACK = "fallback"            # Sin datos fiables (último partido histórico)
    STALE = "stale"                  # Datos obsoletos (>7 días o cambio de entrenador)
    
    def get_uncertainty_penalty(self) -> float:
        """Retorna el penalty de incertidumbre para el BPA."""
        penalties = {
            LineupFreshness.LIVE: 0.0,        # Sin penalty
            LineupFreshness.CONFIRMED: 0.08,   # ±8% incertidumbre
            LineupFreshness.PREDICTED: 0.15,   # ±15% incertidumbre  
            LineupFreshness.FALLBACK: 0.25,    # ±25% incertidumbre
            LineupFreshness.STALE: 0.35        # ±35% incertidumbre (casi inútil)
        }
        return penalties.get(self, 0.25)


@dataclass
class LineupResult:
    """
    Estructura tipada y validada para resultados de alineación.
    Garantiza que todos los consumidores tengan metadatos completos.
    """
    home: List[str]
    away: List[str]
    bajas_detectadas: List[str]
    source: str
    count: int
    status: str
    is_official: bool
    freshness: LineupFreshness
    uncertainty_penalty: float
    timestamp: datetime
    match_datetime: Optional[datetime] = None
    verification_link: Optional[str] = None
    metadata: Dict = None
    
    def __post_init__(self):
        if self.metadata is None:
            self.metadata = {}
    
    def to_dict(self) -> Dict:
        """Conversión segura para compatibilidad con código legacy."""
        return {
            'home': self.home,
            'away': self.away,
            'bajas_detectadas': self.bajas_detectadas,
            'source': self.source,
            'count': self.count,
            'status': self.status,
            'is_official': self.is_official,
            'freshness': self.freshness.value,
            'uncertainty_penalty': self.uncertainty_penalty,
            'timestamp': self.timestamp.isoformat(),
            'match_datetime': self.match_datetime.isoformat() if self.match_datetime else None,
            'verification_link': self.verification_link,
            'metadata': self.metadata
        }


class LineupQualityValidator:
    """
    Validador independiente de calidad de alineaciones.
    Separa la lógica de validación de la obtención de datos.
    """
    
    # Umbrales de configuración (ajustables según liga)
    LIVE_THRESHOLD_HOURS = 1.0
    CONFIRMED_THRESHOLD_HOURS = 24.0
    STALE_THRESHOLD_DAYS = 7
    
    @classmethod
    def calculate_freshness(
        cls,
        fetch_timestamp: datetime,
        match_datetime: datetime,
        source_type: str,
        is_official: bool,
        has_cross_validation: bool = False
    ) -> LineupFreshness:
        """
        Determina la frescura de los datos basado en múltiples factores.
        
        Args:
            fetch_timestamp: Cuándo se obtuvieron los datos
            match_datetime: Cuándo es el partido
            source_type: Identificador de la fuente (elite, official, fallback, etc)
            is_official: Si viene de fuente oficial (RFEF, Premier, etc)
            has_cross_validation: Si hay confirmación de 2+ fuentes independientes
        """
        if not match_datetime:
            logger.warning("Sin fecha de partido, marcando como FALLBACK")
            return LineupFreshness.FALLBACK
        
        time_to_match = match_datetime - fetch_timestamp
        hours_until_match = time_to_match.total_seconds() / 3600
        
        # LIVE: Menos de 1 hora y fuente oficial
        if hours_until_match <= cls.LIVE_THRESHOLD_HOURS and is_official:
            return LineupFreshness.LIVE
            
        # CONFIRMED: Menos de 24h + (oficial O cruzado con prensa)
        if hours_until_match <= cls.CONFIRMED_THRESHOLD_HOURS:
            if is_official or has_cross_validation:
                return LineupFreshness.CONFIRMED
        
        # PREDICTED: Datos históricos o modelados, pero recientes (< 7 días)
        if hours_until_match <= (cls.STALE_THRESHOLD_DAYS * 24):
            if source_type in ['historical', 'predicted', 'statistical']:
                return LineupFreshness.PREDICTED
            # Si es fallback pero reciente
            return LineupFreshness.FALLBACK
        
        # STALE: Datos muy antiguos o sin contexto temporal
        return LineupFreshness.STALE
    
    @classmethod
    def validate_lineup_integrity(cls, home: List[str], away: List[str]) -> Dict:
        """
        Valida que las alineaciones tengan sentido fútbolístico básico.
        """
        issues = []
        warnings = []
        
        # Validación básica de tamaño
        home_count = len(home) if home else 0
        away_count = len(away) if away else 0
        
        if home_count == 0 and away_count == 0:
            issues.append("Sin datos de ambos equipos")
        elif home_count == 0:
            issues.append("Sin datos equipo local")
        elif away_count == 0:
            issues.append("Sin datos equipo visitante")
        
        # Validación de tamaño típico (11 titulares, pero aceptamos 7-14 por flexibilidad)
        if home_count > 0 and not (7 <= home_count <= 14):
            warnings.append(f"Local: {home_count} jugadores (esperado 7-14)")
        if away_count > 0 and not (7 <= away_count <= 14):
            warnings.append(f"Visitante: {away_count} jugadores (esperado 7-14)")
        
        # Validación de duplicados
        if home and len(home) != len(set(home)):
            issues.append("Jugadores duplicados en local")
        if away and len(away) != len(set(away)):
            issues.append("Jugadores duplicados en visitante")
        
        # Validación de solapamiento (mismo jugador en ambos equipos = error grave)
        if home and away:
            overlap = set(h.lower() for h in home) & set(a.lower() for a in away)
            if overlap:
                issues.append(f"Jugadores en ambos equipos: {overlap}")
        
        return {
            'is_valid': len(issues) == 0,
            'issues': issues,
            'warnings': warnings,
            'home_count': home_count,
            'away_count': away_count
        }


class LineupFetcher:
    """
    Fetches official lineups and referee data from elite multi-source pipeline.
    Versión 4.0: Con Freshness Score y validación de calidad integrada.
    """
    
    def __init__(self, data_provider: DataProvider):
        self.data_provider = data_provider
        self.auto_fetcher = AutoLineupFetcher(data_provider)
        self.ms_fetcher = MultiSourceFetcher()
        self.validator = LineupQualityValidator()
        logger.info("LineupFetcher v4.0 inicializado con sistema Freshness Score")

    def fetch_confirmed_lineup(self, team_name: str, match_time: str) -> List[str]:
        """
        [LEGACY] Mantiene compatibilidad con código anterior.
        Recomendado: Usar fetch_smart_lineup() en su lugar.
        """
        logger.warning("Usando método legacy fetch_confirmed_lineup. Considere migrar.")
        print(f"[*] Checking lineups 1 hour before {match_time}...")
        time.sleep(1.0)
        
        team = self.data_provider.get_team_data(team_name)
        return [p.name for p in team.players[:11]] if team and team.players else []

    def _safe_fallback(self, source_msg: str, home_team_name: str, away_team_name: str, 
                       match_datetime: datetime) -> LineupResult:
        """
        Fallback controlado con metadatos completos y timestamp.
        NUNCA retorna datos sin contexto de frescura.
        """
        logger.warning(f"Activando fallback: {source_msg}")
        
        try:
            home_last = self.data_provider.get_last_match_lineup(home_team_name)
            away_last = self.data_provider.get_last_match_lineup(away_team_name)
            
            # Verificar antigüedad del fallback
            last_match_date = self.data_provider.get_last_match_date(home_team_name)
            days_since_last = 999
            
            if last_match_date and isinstance(last_match_date, datetime):
                days_since_last = (datetime.now() - last_match_date).days
            
            freshness = LineupFreshness.STALE if days_since_last > 30 else LineupFreshness.FALLBACK
            
        except Exception as e:
            logger.error(f"Error en fallback: {e}")
            home_last, away_last = [], []
            freshness = LineupFreshness.STALE
        
        return LineupResult(
            home=home_last,
            away=away_last,
            bajas_detectadas=[],
            source=f"{source_msg} (Fallback)",
            count=len(home_last) + len(away_last),
            status='fallback',
            is_official=False,
            freshness=freshness,
            uncertainty_penalty=freshness.get_uncertainty_penalty(),
            timestamp=datetime.now(),
            match_datetime=match_datetime,
            metadata={'fallback_reason': source_msg, 'days_since_last_match': days_since_last if 'days_since_last' in locals() else None}
        )

    def fetch_smart_lineup(self, home_team_name: str, away_team_name: str, 
                          match_datetime: datetime, league: str) -> Dict:
        """
        Estrategia inteligente de obtención con Freshness Score y validación.
        
        Retorna Dict (para compatibilidad legacy) pero internamente usa LineupResult.
        """
        logger.info(f"Iniciando fetch_smart_lineup: {home_team_name} vs {away_team_name}")
        
        # Normalización robusta de fecha
        if not isinstance(match_datetime, datetime):
            try:
                if hasattr(match_datetime, 'hour'):
                    match_datetime = datetime.combine(match_datetime, datetime.min.time())
                else:
                    match_datetime = datetime.now() + timedelta(days=1)
                    logger.warning(f"Fecha inválida, usando mañana como default: {match_datetime}")
            except Exception as e:
                logger.error(f"Error normalizando fecha: {e}")
                return self._safe_fallback("Error fecha inválida", home_team_name, 
                                         away_team_name, match_datetime).to_dict()

        now = datetime.now()
        time_until_match = match_datetime - now
        hours_until_match = time_until_match.total_seconds() / 3600

        # =================================================================
        # ESTRATEGIA: Más de 1 hora del partido (Pre-partido)
        # =================================================================
        if hours_until_match > 1.0:
            logger.info(f"Modo PRE-PARTIDO ({hours_until_match:.1f}h hasta el match)")
            
            # Intento 1: MultiSourceFetcher (Elite → Official)
            try:
                ms_result = self.ms_fetcher.fetch_lineup(
                    home_team_name, away_team_name, match_datetime, league
                )
                
                if ms_result and (ms_result.get('home') or ms_result.get('away')):
                    # Validar integridad antes de procesar
                    integrity = self.validator.validate_lineup_integrity(
                        ms_result.get('home', []), 
                        ms_result.get('away', [])
                    )
                    
                    if not integrity['is_valid']:
                        logger.warning(f"Integridad cuestionable: {integrity['issues']}")
                    
                    # Calcular freshness
                    is_fallback = ms_result.get('_is_fallback', False)
                    source_type = 'fallback' if is_fallback else 'elite'
                    
                    freshness = self.validator.calculate_freshness(
                        fetch_timestamp=datetime.now(),
                        match_datetime=match_datetime,
                        source_type=source_type,
                        is_official=not is_fallback,
                        has_cross_validation=ms_result.get('cross_validated', False)
                    )
                    
                    result = LineupResult(
                        home=ms_result.get('home', []),
                        away=ms_result.get('away', []),
                        bajas_detectadas=ms_result.get('bajas', []),
                        source=ms_result.get('source', 'MultiSourceFetcher'),
                        count=len(ms_result.get('home', [])) + len(ms_result.get('away', [])),
                        status='predicted_multi_source',
                        is_official=not is_fallback,
                        freshness=freshness,
                        uncertainty_penalty=freshness.get_uncertainty_penalty(),
                        timestamp=datetime.now(),
                        match_datetime=match_datetime,
                        verification_link=ms_result.get('verification_link'),
                        metadata={
                            'integrity_check': integrity,
                            'is_fallback_source': is_fallback
                        }
                    )
                    
                    logger.info(f"✅ MultiSource exitoso. Freshness: {freshness.value}, "
                              f"Penalty: {result.uncertainty_penalty}")
                    return result.to_dict()
                    
            except Exception as e:
                logger.error(f"MultiSourceFetcher falló: {e}")
            
            # Intento 2: Fallback a BD interna con metadata clara
            logger.info("Usando BD interna (alineación tipo/previa)")
            return self._safe_fallback('BD Interna (alineación tipo)', 
                                     home_team_name, away_team_name, 
                                     match_datetime).to_dict()

        # =================================================================
        # ESTRATEGIA: Dentro de 1 hora (Live/Confirmado)
        # =================================================================
        else:
            logger.info(f"Modo LIVE/CONFIRMADO ({hours_until_match:.1f}h hasta el match)")
            
            # Intento 1: MultiSourceFetcher (prioridad máxima a oficiales)
            try:
                ms_result = self.ms_fetcher.fetch_lineup(
                    home_team_name, away_team_name, match_datetime, league
                )
                
                if ms_result and (ms_result.get('home') or ms_result.get('away')):
                    is_fallback = ms_result.get('_is_fallback', False)
                    
                    # En modo live, solo aceptamos no-fallback o confirmed
                    if not is_fallback:
                        freshness = LineupFreshness.LIVE if hours_until_match <= 0.5 else LineupFreshness.CONFIRMED
                        
                        result = LineupResult(
                            home=ms_result['home'],
                            away=ms_result['away'],
                            bajas_detectadas=ms_result.get('bajas', []),
                            source=ms_result.get('source', 'Official'),
                            count=len(ms_result['home']) + len(ms_result['away']),
                            status='confirmed',
                            is_official=True,
                            freshness=freshness,
                            uncertainty_penalty=freshness.get_uncertainty_penalty(),
                            timestamp=datetime.now(),
                            match_datetime=match_datetime,
                            verification_link=ms_result.get('verification_link'),
                            metadata={'source_tier': 'official_live'}
                        )
                        
                        logger.info(f"✅ Alineación LIVE confirmada. Freshness: {freshness.value}")
                        return result.to_dict()
                    else:
                        logger.warning("MultiSource retornó fallback en modo live, intentando AutoFetcher...")
                        
            except Exception as e:
                logger.error(f"MultiSource en modo live falló: {e}")

            # Intento 2: AutoLineupFetcher (respaldo)
            try:
                res = self.auto_fetcher.fetch_lineups_auto(
                    home_team_name, away_team_name, match_datetime, league
                )
                
                if res and res.get('count', 0) >= 11:  # Mínimo 11 jugadores total
                    integrity = self.validator.validate_lineup_integrity(
                        res.get('home', []), res.get('away', [])
                    )
                    
                    if integrity['is_valid']:
                        freshness = LineupFreshness.CONFIRMED if hours_until_match <= 0.5 else LineupFreshness.PREDICTED
                        
                        result = LineupResult(
                            home=res.get('home', []),
                            away=res.get('away', []),
                            bajas_detectadas=res.get('bajas_detectadas', []),
                            source='AutoLineupFetcher',
                            count=res['count'],
                            status='confirmed',
                            is_official=True,
                            freshness=freshness,
                            uncertainty_penalty=freshness.get_uncertainty_penalty(),
                            timestamp=datetime.now(),
                            match_datetime=match_datetime,
                            metadata={'integrity_check': integrity}
                        )
                        
                        logger.info(f"✅ AutoFetcher exitoso. Freshness: {freshness.value}")
                        return result.to_dict()
                    else:
                        logger.warning(f"AutoFetcher integridad fallida: {integrity['issues']}")
                        
            except Exception as e:
                logger.error(f"AutoFetcher falló: {e}")

            # Último recurso: Fallback explícito
            logger.error("Todas las fuentes fallaron en modo live. Usando fallback de emergencia.")
            return self._safe_fallback('BD Interna (fuentes web no disponibles)', 
                                     home_team_name, away_team_name,
                                     match_datetime).to_dict()

    def fetch_match_referee(self, home_team: str, away_team: str, 
                           match_date: datetime, league: str) -> dict:
        """
        Obtiene árbitro con cascada multi-fuente y verificación de prensa.
        """
        logger.info(f"[MultiSource] Buscando árbitro: {home_team} vs {away_team}")
        
        # 1. Primary: MultiSourceFetcher
        result = self.ms_fetcher.fetch_referee(home_team, away_team, match_date, league)
        
        # 2. Para La Liga: verificación adicional en prensa deportiva
        if league and league.lower() in ['la liga', 'primera', 'laliga', 'laliga santander']:
            if result.get('_is_fallback') or not result.get('name'):
                logger.info("[Prensa] Intentando verificación en prensa deportiva...")
                try:
                    press_ref = self.ms_fetcher.fetch_referee_press(home_team, away_team, league)
                    if press_ref and press_ref.get('name') and "To be determined" not in press_ref.get('name', ''):
                        result = press_ref
                        result['verified_by_press'] = True
                        logger.info(f"[Prensa] ✅ Confirmado: {result['name']}")
                except Exception as e:
                    logger.debug(f"Prensa fetch falló: {e}")
        
        # 3. Fallback a RefereeSourceMapper legacy
        if result.get('_is_fallback') or not result.get('name'):
            try:
                old_scraper = RefereeSourceMapper.get_scraper(league)
                old_result = old_scraper.fetch_referee(home_team, away_team, match_date)
                if old_result and old_result.get('name') and old_result.get('name') not in ['Por Detectar', 'TBD', '']:
                    old_result.setdefault('_is_fallback', False)
                    result = old_result
                    logger.info(f"[Legacy] Árbitro encontrado: {result['name']}")
            except Exception as e:
                logger.debug(f"Legacy scraper falló: {e}")
        
        # Logging final
        flag = "[POOL-FALLBACK]" if result.get('_is_fallback') else "[VERIFICADO]"
        logger.info(f"{flag} Árbitro: {result.get('name', 'No asignado')} | "
                   f"Fuente: {result.get('source', 'Unknown')}")
        
        # Garantizar campos mínimos
        result.setdefault('name', 'No asignado')
        result.setdefault('source', 'Unknown')
        result.setdefault('_is_fallback', True)
        result.setdefault('verification_link', None)
        
        return result

    def fetch_injuries(self, league: str) -> Dict:
        """Obtiene reporte de lesiones para una liga."""
        logger.info(f"Obteniendo lesiones para: {league}")
        try:
            return self.auto_fetcher.fetch_injuries_auto(league) or {}
        except Exception as e:
            logger.error(f"Error obteniendo lesiones: {e}")
            return {}

    def fetch_from_url(self, url: str, home_team_name: str, away_team_name: str) -> dict:
        """
        Scraping de URL externa con validación de integridad.
        [Mantiene compatibilidad con versión anterior pero agrega validación]
        """
        import requests
        from bs4 import BeautifulSoup
        import re
        
        logger.info(f"📡 Scraping URL: {url}")
        
        extracted_names = set()
        
        try:
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
            }
            resp = requests.get(url, headers=headers, timeout=10)
            resp.raise_for_status()
            html = resp.text
            soup = BeautifulSoup(html, 'html.parser')
            
            # Manejo de redirección a página principal
            page_title = soup.title.string if soup.title else ""
            if "Football Lineups" in page_title or len(soup.find_all(class_='lineup-row')) > 5:
                logger.warning("Detectada redirección a página principal, buscando match ID...")
                
                home_simple = home_team_name.split()[0] if home_team_name else ""
                away_simple = away_team_name.split()[0] if away_team_name else ""
                
                found_id = None
                rows = soup.find_all(class_='lineup-row')
                
                for row in rows:
                    row_text = row.get_text()
                    if home_simple in row_text and away_simple in row_text:
                        link = row.find('a', class_='view-lineups')
                        if link and link.get('id'):
                            found_id = link.get('id')
                            logger.info(f"Match ID encontrado: {found_id}")
                            break
                
                if found_id:
                    ajax_url = f"https://www.sportsgambler.com/lineups/lineups-load2.php?id={found_id}"
                    logger.info(f"Fetching AJAX: {ajax_url}")
                    resp_ajax = requests.get(ajax_url, headers=headers, timeout=10)
                    if resp_ajax.status_code == 200:
                        html = resp_ajax.text
                        soup = BeautifulSoup(html, 'html.parser')
                    else:
                        logger.error(f"AJAX falló: {resp_ajax.status_code}")
                else:
                    logger.error("No se encontró match ID en página principal")

            # Extracción de nombres (múltiples estrategias)
            # Estrategia A: Links de jugadores
            for a in soup.find_all('a', href=True):
                href = a['href'].lower()
                if 'jugadores/' in href or 'player/' in href:
                    name = a.get_text().strip()
                    if name and len(name.split()) > 1:
                        extracted_names.add(name)
                    else:
                        slug = href.split('/')[-1].replace("-", " ").title()
                        if len(slug) > 3:
                            extracted_names.add(slug)

            # Estrategia B: Alt tags de imágenes
            for img in soup.find_all('img', alt=True):
                alt = img['alt'].strip()
                if alt and len(alt.split()) > 1:
                    if not any(x in alt.lower() for x in ["escudo", "logo", "estadio", "entrenador"]):
                        extracted_names.add(alt)

            # Estrategia C: Regex fallback
            raw_regex = re.findall(r'>\s*([A-Z][a-z]+(?:\s[A-Z][a-z]+)+)\s*<', html)
            for name in raw_regex:
                extracted_names.add(name)

            # Estrategia D: Spans específicos
            for span in soup.find_all('span', class_='player-name'):
                name = span.get_text().strip()
                if name and len(name.split()) > 1:
                    extracted_names.add(name)

        except Exception as e:
            logger.error(f"Scraping falló: {e}")
            return {
                "error": f"Scraping failed: {str(e)}", 
                "home": [], 
                "away": [],
                "freshness": LineupFreshness.STALE.value,
                "uncertainty_penalty": LineupFreshness.STALE.get_uncertainty_penalty()
            }

        # Clasificación fuzzy contra roster conocido
        found_home = []
        found_away = []
        
        try:
            team_home = self.data_provider.get_team_data(home_team_name)
            team_away = self.data_provider.get_team_data(away_team_name)
        except Exception as e:
            logger.error(f"Error obteniendo datos de equipos: {e}")
            team_home, team_away = None, None

        def fuzzy_match(scraped_name: str, roster) -> Optional[str]:
            if not roster or not scraped_name:
                return None
                
            scraped_tokens = set(scraped_name.lower().split())
            if not scraped_tokens:
                return None
            
            for p in roster.players if hasattr(roster, 'players') else roster:
                player_name = p.name if hasattr(p, 'name') else str(p)
                p_tokens = set(player_name.lower().split())
                
                if p_tokens.issubset(scraped_tokens) or scraped_tokens.issubset(p_tokens):
                    return player_name
                if len(scraped_tokens.intersection(p_tokens)) >= 1:
                    return player_name
            return None

        # Procesar home
        if team_home:
            for scraped in extracted_names:
                match = fuzzy_match(scraped, team_home)
                if match and match not in found_home:
                    found_home.append(match)
                    
        # Procesar away
        if team_away:
            for scraped in extracted_names:
                match = fuzzy_match(scraped, team_away)
                if match and match not in found_away:
                    found_away.append(match)
        
        # Validación de integridad
        integrity = self.validator.validate_lineup_integrity(found_home, found_away)
        
        if not found_home and not found_away:
            return {
                "error": "No se detectaron jugadores conocidos en el enlace.",
                "home": [],
                "away": [],
                "freshness": LineupFreshness.STALE.value,
                "uncertainty_penalty": LineupFreshness.STALE.get_uncertainty_penalty(),
                "integrity": integrity
            }
        
        # Determinar freshness basado en calidad
        freshness = (LineupFreshness.CONFIRMED if integrity['is_valid'] and len(found_home) >= 7 and len(found_away) >= 7 
                    else LineupFreshness.PREDICTED)
        
        return {
            "home": sorted(found_home),
            "away": sorted(found_away),
            "source": url,
            "count": len(found_home) + len(found_away),
            "freshness": freshness.value,
            "uncertainty_penalty": freshness.get_uncertainty_penalty(),
            "integrity": integrity,
            "timestamp": datetime.now().isoformat()
        }

    def extract_from_image(self, image_bytes: bytes, home_team_name: str, 
                          away_team_name: str) -> dict:
        """
        OCR de imagen con validación de integridad y metadatos completos.
        """
        try:
            import pytesseract
            from PIL import Image
            import io
        except ImportError:
            logger.error("pytesseract o PIL no instalados")
            return {
                "error": "OCR dependencies not installed",
                "home": [],
                "away": [],
                "freshness": LineupFreshness.STALE.value
            }
        
        logger.info(f"📸 Procesando imagen OCR: {home_team_name} vs {away_team_name}")
        
        try:
            img = Image.open(io.BytesIO(image_bytes))
            text = pytesseract.image_to_string(img, lang='spa+eng')
            
            lines = text.split('\n')
            extracted_names = set()
            
            for line in lines:
                clean = line.strip()
                if len(clean.split()) >= 2 and re.match(r'^[A-Z][a-z\u00C0-\u017F]+(?:\s[A-Z][a-z\u00C0-\u017F]+)+$', clean):
                    extracted_names.add(clean)
                else:
                    matches = re.findall(r'([A-Z][a-z\u00C0-\u017F]+(?:\s[A-Z][a-z\u00C0-\u017F]+)+)', clean)
                    for m in matches:
                        extracted_names.add(m)

            if not extracted_names:
                words = re.findall(r'\b[A-Z][a-z\u00C0-\u017F]+\b', text)
                extracted_names = set(words)

        except Exception as e:
            logger.error(f"OCR falló: {e}")
            return {
                "error": f"OCR failed: {str(e)}",
                "home": [],
                "away": [],
                "freshness": LineupFreshness.STALE.value
            }

        # Clasificación fuzzy (mismo método que fetch_from_url)
        found_home = []
        found_away = []
        
        try:
            team_home = self.data_provider.get_team_data(home_team_name)
            team_away = self.data_provider.get_team_data(away_team_name)
        except Exception as e:
            logger.error(f"Error obteniendo equipos: {e}")
            team_home, team_away = None, None

        def fuzzy_match(scraped_name, roster):
            if not roster:
                return None
            scraped_tokens = set(scraped_name.lower().split())
            if not scraped_tokens:
                return None
            for p in (roster.players if hasattr(roster, 'players') else roster):
                player_name = p.name if hasattr(p, 'name') else str(p)
                p_tokens = set(player_name.lower().split())
                if p_tokens.issubset(scraped_tokens) or scraped_tokens.issubset(p_tokens):
                    return player_name
                if len(scraped_tokens.intersection(p_tokens)) >= 1:
                    return player_name
            return None

        if team_home:
            for scraped in extracted_names:
                match = fuzzy_match(scraped, team_home)
                if match and match not in found_home:
                    found_home.append(match)
                    
        if team_away:
            for scraped in extracted_names:
                match = fuzzy_match(scraped, team_away)
                if match and match not in found_away:
                    found_away.append(match)
        
        integrity = self.validator.validate_lineup_integrity(found_home, found_away)
        
        if not found_home and not found_away:
            return {
                "error": "No se reconocieron jugadores conocidos en la imagen.",
                "home": [],
                "away": [],
                "freshness": LineupFreshness.STALE.value,
                "uncertainty_penalty": LineupFreshness.STALE.get_uncertainty_penalty()
            }
        
        freshness = LineupFreshness.CONFIRMED if integrity['is_valid'] else LineupFreshness.PREDICTED
        
        return {
            "home": sorted(found_home),
            "away": sorted(found_away),
            "count": len(found_home) + len(found_away),
            "freshness": freshness.value,
            "uncertainty_penalty": freshness.get_uncertainty_penalty(),
            "integrity": integrity,
            "method": "OCR",
            "timestamp": datetime.now().isoformat()
        }