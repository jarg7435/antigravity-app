"""
Cache Manager para La Gema JARG74
Caché en memoria con TTL por categoría de dato, usado por los clientes de API
para no gastar cuota en datos que no han cambiado.

El plan gratuito de API-Football son 100 requests/día, así que la política de
TTL se ajusta a la volatilidad real de cada dato: un marcador en vivo caduca en
un minuto, el nombre de un equipo no cambia en un mes.

Uso:
    cache = CacheManager(persist=False)
    cache.set("fixtures", "140_2026-02-06", data, "api_football", TTLConfig.FIXTURES_TODAY)
    cache.get("fixtures", "140_2026-02-06")   # None si caducó o no está

Autor: Antigravity - La Gema JARG74
"""

import json
import logging
import os
import threading
import time
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)


class TTLConfig:
    """Tiempos de vida en segundos, por categoría de dato."""

    # Datos en vivo — caducan casi al instante
    LIVE_MATCH = 60

    # Alineaciones — las confirmadas ya no cambian; las previstas sí
    LINEUPS_CONFIRMED = 30 * 60
    LINEUPS_PREDICTED = 10 * 60

    # Fixtures
    FIXTURES_TODAY = 15 * 60
    FIXTURES_WEEK = 6 * 3600

    # Mercados y bajas — se mueven durante la semana previa
    ODDS_PREMATCH = 15 * 60
    INJURIES = 3 * 3600

    # Datos de temporada — estables durante horas
    STANDINGS = 6 * 3600
    SEASON_STATS = 12 * 3600
    REFEREE_STATS = 24 * 3600

    # Datos casi inmutables
    H2H_RECORDS = 7 * 24 * 3600
    TEAM_INFO = 30 * 24 * 3600
    LEAGUE_INFO = 30 * 24 * 3600

    # Usado cuando la llamada no especifica TTL
    DEFAULT = 30 * 60


class CacheManager:
    """
    Caché con TTL por entrada, seguro entre los hilos de Streamlit.

    Las entradas se indexan por (categoría, id). La categoría permite invalidar
    un bloque entero sin tocar el resto (p.ej. todas las alineaciones).
    """

    def __init__(self, persist: bool = False, cache_dir: str = "data/cache",
                 default_ttl: float = TTLConfig.DEFAULT):
        self._store: Dict[str, Dict[str, Any]] = {}
        self._lock = threading.Lock()
        self._default_ttl = default_ttl
        self._persist = persist
        self._path = os.path.join(cache_dir, "api_cache.json")
        self._hits = 0
        self._misses = 0

        if self._persist:
            self._load()

    # =========================================================================
    # API pública
    # =========================================================================

    def get(self, category: str, cache_id: str) -> Optional[Any]:
        """Devuelve el dato cacheado, o None si no está o ya caducó."""
        key = self._key(category, cache_id)
        with self._lock:
            entry = self._store.get(key)
            if entry is None:
                self._misses += 1
                return None

            if time.time() >= entry["expires_at"]:
                del self._store[key]
                self._misses += 1
                logger.debug(f"Cache expirado: {key}")
                return None

            self._hits += 1
            logger.debug(f"Cache hit: {key} (fuente: {entry.get('source')})")
            return entry["data"]

    def set(self, category: str, cache_id: str, data: Any,
            source: str = None, ttl: float = None) -> None:
        """Guarda un dato. Un ttl None usa el TTL por defecto."""
        key = self._key(category, cache_id)
        ttl = self._default_ttl if ttl is None else float(ttl)
        entry = {
            "data": data,
            "source": source,
            "stored_at": time.time(),
            "expires_at": time.time() + ttl,
        }
        with self._lock:
            self._store[key] = entry

        if self._persist:
            self._save()

    def invalidate(self, category: str, cache_id: str = None) -> int:
        """
        Elimina entradas. Sin cache_id borra la categoría entera.
        Devuelve cuántas entradas se eliminaron.
        """
        with self._lock:
            if cache_id is not None:
                keys = [self._key(category, cache_id)]
            else:
                prefix = f"{category}:"
                keys = [k for k in self._store if k.startswith(prefix)]

            borradas = 0
            for k in keys:
                if self._store.pop(k, None) is not None:
                    borradas += 1

        if self._persist and borradas:
            self._save()
        return borradas

    def clear(self) -> None:
        """Vacía la caché completa."""
        with self._lock:
            self._store.clear()
            self._hits = 0
            self._misses = 0
        if self._persist:
            self._save()

    def stats(self) -> Dict[str, Any]:
        """Métricas para el panel de diagnóstico de APIs."""
        with self._lock:
            total = self._hits + self._misses
            return {
                "entradas": len(self._store),
                "hits": self._hits,
                "misses": self._misses,
                "ratio_aciertos": round(self._hits / total, 3) if total else 0.0,
                "persistente": self._persist,
            }

    # =========================================================================
    # Interno
    # =========================================================================

    @staticmethod
    def _key(category: str, cache_id: str) -> str:
        return f"{category}:{cache_id}"

    def _load(self) -> None:
        """Carga la caché de disco descartando lo ya caducado."""
        if not os.path.exists(self._path):
            return
        try:
            with open(self._path, encoding="utf-8") as f:
                guardado = json.load(f)
            ahora = time.time()
            self._store = {
                k: v for k, v in guardado.items()
                if isinstance(v, dict) and v.get("expires_at", 0) > ahora
            }
            logger.info(f"Cache cargada de disco: {len(self._store)} entradas vigentes")
        except Exception as e:
            # Una caché corrupta nunca debe impedir arrancar: se empieza vacía.
            logger.warning(f"No se pudo cargar la cache de disco ({e}); se empieza vacia")
            self._store = {}

    def _save(self) -> None:
        """Vuelca a disco de forma atómica. Nunca propaga errores."""
        try:
            os.makedirs(os.path.dirname(self._path), exist_ok=True)
            tmp = f"{self._path}.tmp"
            with self._lock:
                copia = dict(self._store)
            with open(tmp, "w", encoding="utf-8") as f:
                json.dump(copia, f, ensure_ascii=False, default=str)
            os.replace(tmp, self._path)
        except Exception as e:
            logger.warning(f"No se pudo guardar la cache en disco: {e}")
