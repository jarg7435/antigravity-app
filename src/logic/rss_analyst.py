"""
RSSAnalyst — Análisis de Prensa via Google News RSS
=====================================================
Busca noticias REALES de cada equipo en Google News RSS
sin necesidad de API de pago. Funciona en Streamlit Cloud.

Proceso:
1. Busca en Google News RSS: "{equipo} lesión baja"
2. Busca en Google News RSS: "{equipo} vestuario entrenador"  
3. Parsea los titulares XML
4. Aplica análisis de sentimiento por palabras clave
5. Devuelve análisis estructurado con impacto numérico
"""

import re
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta
from typing import Dict, List, Tuple
import requests


# ============================================================
# PALABRAS CLAVE PARA ANÁLISIS DE SENTIMIENTO
# ============================================================

NEG_KEYWORDS = {
    # Lesiones / Bajas
    "lesión": -0.05,  "lesionado": -0.05, "baja": -0.04,
    "operación": -0.07, "quirófano": -0.07, "rotura": -0.06,
    "fractura": -0.06, "esguince": -0.03, "muscular": -0.03,
    "descartado": -0.05, "sancionado": -0.04, "expulsado": -0.04,
    # Vestuario / Ambiente
    "crisis": -0.05, "tensión": -0.04, "conflicto": -0.04,
    "bronca": -0.04, "vestuario": -0.02, "problemas": -0.03,
    "malestar": -0.04, "dimisión": -0.06, "destituido": -0.06,
    "destitución": -0.06, "impagos": -0.05, "huelga": -0.05,
    # Resultados negativos
    "derrota": -0.03, "goleada": -0.03, "eliminado": -0.04,
    "colista": -0.03, "descenso": -0.04, "racha": -0.02,
    # Prensa
    "críticas": -0.03, "abucheos": -0.04, "pitada": -0.03,
    "presión": -0.02, "cuestionado": -0.03, "señalado": -0.03,
}

POS_KEYWORDS = {
    # Recuperaciones
    "recuperado": 0.05, "vuelve": 0.04, "alta": 0.04,
    "listo": 0.03, "disponible": 0.03, "entrena": 0.02,
    # Ambiente positivo
    "motivación": 0.04, "confianza": 0.03, "unidad": 0.03,
    "renovación": 0.02, "refuerzo": 0.03, "fichaje": 0.02,
    # Resultados positivos
    "victoria": 0.03, "racha positiva": 0.04, "líder": 0.03,
    "invicto": 0.04, "goleador": 0.02, "clasificado": 0.03,
    # Prensa positiva
    "elogio": 0.03, "ovación": 0.03, "apoyo": 0.02,
}

# Palabras que indican baja confirmada
BAJA_PATTERNS = [
    r"(\w+ \w+) (no (podrá|estará|jugará)|se pierde|es baja|está lesionado)",
    r"baja (confirmada|segura) de (\w+ \w+)",
    r"(\w+ \w+) (descartado|fuera de la convocatoria)",
    r"(\w+ \w+) (se opera|pasará por el quirófano)",
]

DUDA_PATTERNS = [
    r"(\w+ \w+) (es duda|en duda|podría ser baja|apura para)",
    r"duda de (\w+ \w+)",
    r"(\w+ \w+) (no está al 100|arrastra molestias|con molestias)",
]


class RSSAnalyst:
    """
    Analista de prensa usando Google News RSS.
    No requiere API key. Funciona en Streamlit Cloud.
    """

    HEADERS = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        "Accept": "application/rss+xml, application/xml, text/xml",
        "Accept-Language": "es-ES,es;q=0.9",
    }

    # Búsquedas específicas por tipo de información
    SEARCH_QUERIES = [
        "{team} lesión baja descartado",
        "{team} vestuario entrenador noticias",
        "{team} partido resultado forma",
    ]

    def fetch_google_news_rss(self, query: str, max_items: int = 8) -> List[Dict]:
        """
        Obtiene titulares de Google News RSS para una búsqueda.
        Retorna lista de {title, source, date, snippet}
        """
        encoded = requests.utils.quote(query)
        url = f"https://news.google.com/rss/search?q={encoded}&hl=es&gl=ES&ceid=ES:es"

        try:
            resp = requests.get(url, headers=self.HEADERS, timeout=8)
            if resp.status_code != 200:
                return []

            # Parsear XML
            root = ET.fromstring(resp.content)
            channel = root.find('channel')
            if channel is None:
                return []

            items = []
            cutoff = datetime.now() - timedelta(days=7)  # Solo últimos 7 días

            for item in channel.findall('item')[:max_items]:
                title = item.findtext('title', '') or ''
                source = item.findtext('source', '') or ''
                pub_date_str = item.findtext('pubDate', '') or ''
                description = item.findtext('description', '') or ''

                # Filtrar por fecha reciente
                try:
                    from email.utils import parsedate_to_datetime
                    pub_date = parsedate_to_datetime(pub_date_str)
                    if pub_date.replace(tzinfo=None) < cutoff:
                        continue
                except:
                    pass

                # Limpiar HTML del description
                clean_desc = re.sub(r'<[^>]+>', '', description).strip()

                items.append({
                    "title": title,
                    "source": source,
                    "date": pub_date_str[:16] if pub_date_str else "",
                    "snippet": clean_desc[:200] if clean_desc else title
                })

            return items

        except Exception as e:
            print(f"[RSSAnalyst] Error fetch RSS '{query}': {e}")
            return []

    def analyze_team(self, team_name: str, papers: List[str]) -> Dict:
        """
        Análisis completo de un equipo via RSS.
        Devuelve análisis estructurado compatible con ExternalAnalyst.
        """
        print(f"    [RSS] Buscando noticias: {team_name}")

        all_items = []
        for query_tpl in self.SEARCH_QUERIES:
            query = query_tpl.format(team=team_name)
            items = self.fetch_google_news_rss(query, max_items=6)
            all_items.extend(items)
            if len(all_items) >= 15:
                break

        if not all_items:
            print(f"    [RSS] Sin noticias encontradas para {team_name}")
            return self._empty_analysis()

        # Combinar todos los textos para análisis
        full_text = " ".join(
            (item["title"] + " " + item["snippet"]).lower()
            for item in all_items
        ).lower()

        # Análisis de sentimiento
        moral = 0.0
        for kw, val in NEG_KEYWORDS.items():
            if kw in full_text:
                moral += val
        for kw, val in POS_KEYWORDS.items():
            if kw in full_text:
                moral += val

        # Clamp entre -0.15 y +0.15
        moral = max(-0.15, min(0.15, round(moral, 3)))

        # Detectar bajas y dudas en titulares
        bajas = self._extract_players(full_text, BAJA_PATTERNS)
        dudas = self._extract_players(full_text, DUDA_PATTERNS)

        # Seleccionar noticias más relevantes
        noticias_clave = self._select_relevant_headlines(all_items, team_name)

        # Estado del vestuario
        neg_count = sum(1 for kw in ["crisis", "tensión", "conflicto", "bronca",
                                      "malestar", "dimisión", "destituido"]
                        if kw in full_text)
        pos_count = sum(1 for kw in ["motivación", "confianza", "unidad", "elogio"]
                        if kw in full_text)

        if neg_count >= 2:
            estado_vestuario = "negativo"
            desc_vestuario = self._build_vestuario_desc(full_text, "negativo")
        elif pos_count >= 2:
            estado_vestuario = "positivo"
            desc_vestuario = self._build_vestuario_desc(full_text, "positivo")
        else:
            estado_vestuario = "neutro"
            desc_vestuario = "Sin incidencias relevantes en el vestuario esta semana."

        # Relación con la prensa
        if any(kw in full_text for kw in ["críticas", "abucheos", "pitada", "cuestionado"]):
            relacion_prensa = "tensa"
        elif any(kw in full_text for kw in ["elogio", "apoyo", "ovación"]):
            relacion_prensa = "buena"
        else:
            relacion_prensa = "normal"

        # Sensaciones recientes
        if any(kw in full_text for kw in ["victoria", "invicto", "racha positiva", "líder"]):
            sensaciones = "positivas"
            desc_reciente = self._build_forma_desc(full_text, "positivas")
        elif any(kw in full_text for kw in ["derrota", "colista", "descenso", "eliminado"]):
            sensaciones = "negativas"
            desc_reciente = self._build_forma_desc(full_text, "negativas")
        else:
            sensaciones = "neutras"
            desc_reciente = "Resultados recientes sin tendencia clara definida."

        # Impacto final
        if moral > 0.03:
            impacto = "positivo"
        elif moral < -0.03:
            impacto = "negativo"
        else:
            impacto = "neutro"

        # Fuentes encontradas
        sources_found = list(set(
            item["source"] for item in all_items if item.get("source")
        ))[:3]

        print(f"    [RSS] ✅ {team_name}: {len(all_items)} noticias | moral={moral:+.3f} | {len(bajas)} bajas")

        return {
            "bajas_confirmadas": bajas[:3],
            "dudas": dudas[:3],
            "estado_vestuario": estado_vestuario,
            "descripcion_vestuario": desc_vestuario,
            "relacion_prensa": relacion_prensa,
            "sensaciones_recientes": sensaciones,
            "descripcion_reciente": desc_reciente,
            "noticias_clave": noticias_clave[:3],
            "impacto_partido": impacto,
            "resumen": f"{len(all_items)} noticias analizadas. {len(bajas)} bajas detectadas.",
            "puntuacion_moral": moral,
            "fuentes_rss": sources_found,
            "_via_rss": True
        }

    def _extract_players(self, text: str, patterns: List[str]) -> List[str]:
        """Extrae nombres de jugadores de los titulares."""
        found = []
        for pattern in patterns:
            matches = re.findall(pattern, text, re.IGNORECASE)
            for match in matches:
                if isinstance(match, tuple):
                    name = match[0].strip()
                else:
                    name = match.strip()
                # Filtrar nombres válidos (2 palabras, no stopwords)
                words = name.split()
                if len(words) >= 2 and all(len(w) > 2 for w in words):
                    # Capitalizar
                    name = " ".join(w.capitalize() for w in words)
                    if name not in found:
                        found.append(name)
        return found[:4]

    def _select_relevant_headlines(self, items: List[Dict], team_name: str) -> List[str]:
        """Selecciona los titulares más relevantes."""
        relevant = []
        priority_words = ["lesión", "baja", "vestuario", "entrenador", "victoria",
                          "derrota", "sanción", "renovación", "fichaje", "crisis"]

        # Primero los de mayor relevancia
        for item in items:
            title = item.get("title", "")
            title_lower = title.lower()
            if any(pw in title_lower for pw in priority_words):
                # Limpiar el título (quitar " - Nombre del medio" al final)
                clean = re.sub(r'\s*[-–]\s*\S+\s*$', '', title).strip()
                if clean and clean not in relevant:
                    relevant.append(clean)

        # Si no hay suficientes, añadir los primeros
        for item in items:
            if len(relevant) >= 3:
                break
            title = item.get("title", "")
            clean = re.sub(r'\s*[-–]\s*\S+\s*$', '', title).strip()
            if clean and clean not in relevant:
                relevant.append(clean)

        return relevant[:3]

    def _build_vestuario_desc(self, text: str, tipo: str) -> str:
        if tipo == "negativo":
            if "destituido" in text or "dimisión" in text:
                return "Situación crítica en el banquillo, con rumores de destitución del entrenador."
            if "impagos" in text:
                return "Problemas económicos en el club afectan al ambiente del vestuario."
            if "tensión" in text or "conflicto" in text:
                return "Tensiones internas en el vestuario detectadas en prensa esta semana."
            return "Ambiente de presión en el equipo según la prensa local."
        else:
            if "renovación" in text:
                return "Noticias de renovaciones generan buen ambiente en el vestuario."
            if "motivación" in text or "confianza" in text:
                return "El vestuario transmite confianza y buenas sensaciones según la prensa."
            return "Buen ambiente interno en el club esta semana."

    def _build_forma_desc(self, text: str, tipo: str) -> str:
        if tipo == "positivas":
            if "invicto" in text:
                return "El equipo llega invicto en sus últimos partidos, con moral alta."
            if "líder" in text:
                return "Lideran la clasificación, en un momento óptimo de forma."
            return "Buenas sensaciones en los últimos resultados del equipo."
        else:
            if "descenso" in text:
                return "El equipo está en zona de descenso, con gran presión sobre el vestuario."
            if "eliminado" in text:
                return "Eliminación reciente que puede afectar anímicamente al grupo."
            return "Malos resultados recientes generan dudas sobre el estado del equipo."

    def _empty_analysis(self) -> Dict:
        return {
            "bajas_confirmadas": [], "dudas": [],
            "estado_vestuario": "neutro",
            "descripcion_vestuario": "Sin acceso a noticias recientes.",
            "relacion_prensa": "normal", "sensaciones_recientes": "neutras",
            "descripcion_reciente": "Sin datos disponibles.",
            "noticias_clave": [], "impacto_partido": "neutro",
            "resumen": "Sin noticias disponibles.", "puntuacion_moral": 0.0,
            "_via_rss": True
        }
