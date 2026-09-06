"""
Penalización dinámica por ausencias críticas — La Gema JARG74.

Compara los jugadores clave que el modelo da por titulares con el once
confirmado de última hora y traduce lo que falta en dos coeficientes que
corrigen el xG, más una rebaja de la confianza del pronóstico.

POR QUÉ HACE FALTA
------------------
El motor ya tenía media penalización, pero desconectada de los dos extremos:

- `PoissonEngine.estimate_lambdas` acepta `missing_key_players_home/away` y
  aplica 0.92 por cada uno... pero `Predictor._safe_poisson_calculation` nunca
  se los pasaba. El parámetro estaba muerto: siempre valía 0.
- `Validator.validate_lineup` sí detecta los nodos clave que faltan, pero su
  resultado se pintaba en la interfaz y no entraba en el cálculo.

Resultado: el once confirmado no movía ni un decimal de la predicción. Se podía
caer el portero titular una hora antes y el pronóstico salía idéntico.

LA IDEA QUE CAMBIA EL MODELO
----------------------------
Contar ausentes y aplicarles a todos el mismo 0.92 mete en el mismo saco cosas
que no se parecen: que falte el portero titular no reduce los goles que marcas,
sino que aumenta los que encajas. Aquí se separan los dos efectos:

    coef_ataque  (<= 1.0)  multiplica el lambda PROPIO
                           lo bajan los finalizadores y creadores ausentes
    coef_encaje  (>= 1.0)  multiplica el lambda del RIVAL
                           lo suben el portero y los defensas ausentes

De modo que el lambda local acaba siendo:

    lambda_local = base * coef_ataque(local) * coef_encaje(visitante)

Además, el peso de cada ausencia se escala por la calidad del jugador dentro de
su propia plantilla: perder al mejor delantero no es perder al tercero.

SOBRE LAS CONSTANTES
--------------------
Los pesos de PESO_ROL son un juicio de modelado, no una medición. Se han
elegido conservadores a propósito —un portero suplente cuesta del orden de un
15% de gol encajado, no un 30%— porque una penalización exagerada hace más daño
que no penalizar: mueve el pronóstico a un sitio donde no hay ni mercado ni
realidad. El módulo `calibracion.py` corrige con los resultados reales el sesgo
que quede.

NUNCA PENALIZAR POR FALTA DE DATOS
----------------------------------
Si no hay once confirmado con el que comparar, el informe sale con
`comparable=False` y coeficientes neutros. No saber quién juega no es lo mismo
que saber que falta alguien, y castigar la ignorancia convertiría cada partido
sin alineación publicada en un pronóstico artificialmente pesimista.

Autor: Antigravity - La Gema JARG74
"""

import logging
import unicodedata
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Sequence

from src.models.base import NodeRole, Player, PlayerStatus, Team

logger = logging.getLogger(__name__)


# Peso de cada rol, como (impacto ofensivo, impacto defensivo). Son la fracción
# de xG que se mueve cuando falta ese jugador siendo el mejor de su puesto.
#
# NodeRole tiene alias que comparten valor (PORTERO es KEEPER, DELANTERO es
# FINALIZER...), asi que las seis entradas de aqui cubren el enum entero.
PESO_ROL: Dict[NodeRole, tuple] = {
    NodeRole.KEEPER:    (0.00, 0.15),   # no marca; encajar depende mucho de él
    NodeRole.DEFENSIVE: (0.01, 0.07),
    NodeRole.CREATOR:   (0.10, 0.03),   # crea juego; algo de repliegue también
    NodeRole.FINALIZER: (0.12, 0.00),
    NodeRole.TACTICAL:  (0.04, 0.04),   # el entrenador, si se modela
    NodeRole.NONE:      (0.03, 0.02),   # rol sin determinar: efecto testimonial
}

# Topes duros. Ninguna combinación de bajas puede hundir el modelo: por muchas
# ausencias que haya, el equipo sigue saliendo a jugar con once.
COEF_ATAQUE_MIN = 0.70
COEF_ENCAJE_MAX = 1.30

# Rebaja de confianza por unidad de impacto acumulado, y su tope. La confianza
# es lo que decide si se apuesta: cuando el once real no es el previsto, bajarla
# es más importante que acertar el xG.
CONFIANZA_POR_IMPACTO = 0.55
PENALIZACION_CONFIANZA_MAX = 0.35

# Jugadores confirmados por debajo de los cuales el once no es comparable. Con
# menos, lo que hay es un listado incompleto, y todo el que no aparezca daria un
# falso ausente.
MINIMO_ONCE_COMPARABLE = 7

# Cuánto puede pesar un jugador por su calidad relativa dentro de la plantilla.
# Acotado para que una plantilla con notas raras no dispare la penalización.
CALIDAD_MIN, CALIDAD_MAX = 0.6, 1.5


@dataclass
class Ausencia:
    """Un jugador clave que el modelo esperaba y el once confirmado no trae."""

    nombre: str
    rol: NodeRole
    calidad: float          # su nota relativa dentro de la plantilla
    impacto_ataque: float   # cuánto xG propio se pierde
    impacto_encaje: float   # cuánto xG rival se gana

    @property
    def impacto_total(self) -> float:
        return self.impacto_ataque + self.impacto_encaje

    def describe(self) -> str:
        parte = []
        if self.impacto_ataque > 0.001:
            parte.append(f"−{self.impacto_ataque:.0%} ataque")
        if self.impacto_encaje > 0.001:
            parte.append(f"+{self.impacto_encaje:.0%} encaje")
        return f"{self.nombre} ({self.rol.value}): " + ", ".join(parte or ["impacto menor"])


@dataclass
class InformeAusencias:
    """Lo que falta en un equipo y lo que eso le hace al pronóstico."""

    equipo: str
    ausentes: List[Ausencia] = field(default_factory=list)
    coef_ataque: float = 1.0
    coef_encaje: float = 1.0
    penalizacion_confianza: float = 0.0
    comparable: bool = True
    motivo: str = ""

    @property
    def hay_ausencias(self) -> bool:
        return bool(self.ausentes)

    @property
    def critica(self) -> bool:
        """¿Falta alguien tan importante como para desconfiar del pronóstico?"""
        return any(a.impacto_total >= 0.08 for a in self.ausentes)

    def resumen(self) -> str:
        if not self.comparable:
            return f"{self.equipo}: sin once confirmado que comparar ({self.motivo})."
        if not self.ausentes:
            return f"{self.equipo}: el once confirmado coincide con el previsto."
        cabeza = ", ".join(a.nombre for a in self.ausentes[:3])
        resto = f" y {len(self.ausentes) - 3} más" if len(self.ausentes) > 3 else ""
        return (f"{self.equipo}: faltan {cabeza}{resto} — "
                f"ataque ×{self.coef_ataque:.2f}, encaje ×{self.coef_encaje:.2f}")

    def a_dict(self) -> dict:
        """Forma serializable, para guardarla junto a la predicción."""
        return {
            "equipo": self.equipo,
            "comparable": self.comparable,
            "motivo": self.motivo,
            "coef_ataque": round(self.coef_ataque, 4),
            "coef_encaje": round(self.coef_encaje, 4),
            "penalizacion_confianza": round(self.penalizacion_confianza, 4),
            "ausentes": [
                {
                    "nombre": a.nombre,
                    "rol": a.rol.value,
                    "impacto_ataque": round(a.impacto_ataque, 4),
                    "impacto_encaje": round(a.impacto_encaje, 4),
                }
                for a in self.ausentes
            ],
        }


# =============================================================================
# COTEJO DE NOMBRES
# =============================================================================

def _norm(texto: str) -> str:
    """Minúsculas sin tildes ni puntuación, para comparar nombres."""
    base = unicodedata.normalize("NFD", str(texto or ""))
    base = "".join(c for c in base if unicodedata.category(c) != "Mn")
    return " ".join(base.lower().replace(".", " ").replace("-", " ").split())


def _compatibles(a_norm: str, b_norm: str) -> bool:
    """
    ¿Estos dos nombres normalizados designan a la misma persona?

    Acepta que uno venga recortado —"J. García" por "Joan García"— pero exige
    que la inicial coincida cuando los dos la declaran. Sin ese veto, en una
    plantilla con dos hermanos del mismo apellido el presente tapaba al
    ausente: "I. Williams" casaba con "N. Williams" y la baja de Iñaki
    desaparecia del informe.
    """
    if a_norm == b_norm:
        return True
    ia, apellidos_a = _partes(a_norm)
    ib, apellidos_b = _partes(b_norm)
    if not apellidos_a or not apellidos_b:
        return False
    # Uno de los dos puede venir recortado: basta con que los apellidos de uno
    # esten contenidos en los del otro.
    if not (apellidos_a <= apellidos_b or apellidos_b <= apellidos_a):
        return False
    if ia and ib and ia != ib:
        return False
    return True


def _esta_en_el_once(jugador: str, once: Sequence[str]) -> bool:
    """
    ¿Este jugador aparece en el once confirmado?

    Se apoya en `plantillas.resolver_en_plantilla`, que ya sabe casar las
    abreviaturas con las que SofaScore publica los onces, pero su respuesta se
    verifica con `_compatibles`: aquella funcion resuelve un nombre contra una
    plantilla entera y da por bueno el apellido cuando solo hay un candidato,
    que es lo correcto para lo suyo y demasiado laxo para esto. Aqui la
    pregunta es otra —si falta ESTE jugador— y un cotejo de mas oculta una baja.

    Importa acertar en las dos direcciones: un fallo por defecto inventa una
    ausencia que no existe y penaliza un pronostico correcto; uno por exceso
    tapa la baja del portero titular, que es justo lo que hay que detectar.
    """
    if not jugador or not once:
        return False

    objetivo = _norm(jugador)
    if not objetivo:
        return False

    nombres = [_norm(n) for n in once]
    if objetivo in nombres:
        return True

    try:
        from src.data.plantillas import resolver_en_plantilla
        resuelto = resolver_en_plantilla(jugador, list(once))
        if resuelto and _compatibles(objetivo, _norm(resuelto)):
            return True
    except Exception:
        pass

    return any(_compatibles(objetivo, candidato) for candidato in nombres)


def _partes(nombre_norm: str):
    """(inicial del nombre de pila, apellidos) de un nombre ya normalizado."""
    trozos = nombre_norm.split()
    if not trozos:
        return None, set()
    if len(trozos) == 1:
        return None, {trozos[0]}
    return trozos[0][0], {t for t in trozos[1:] if len(t) > 2}


# =============================================================================
# JUGADORES CLAVE
# =============================================================================

def _calidad_relativa(jugador: Player, plantilla: Sequence[Player]) -> float:
    """
    Nota del jugador comparada con la de su propia plantilla.

    Sirve para que perder al mejor delantero pese más que perder al tercero.
    Cuando todas las notas son iguales —el caso de las plantillas construidas
    sin datos— devuelve 1.0 y el peso del rol manda solo.
    """
    notas = [p.rating_last_5 for p in plantilla
             if getattr(p, "rating_last_5", 0) and p.rating_last_5 > 0]
    if not notas:
        return 1.0
    media = sum(notas) / len(notas)
    if media <= 0:
        return 1.0
    propia = getattr(jugador, "rating_last_5", 0) or media
    return max(CALIDAD_MIN, min(CALIDAD_MAX, propia / media))


def jugadores_clave(equipo: Team) -> List[Player]:
    """
    Los que el modelo da por titulares y cuya baja mueve el pronóstico.

    Se toman los titulares con rol asignado. El portero entra siempre que
    exista, aunque su rol no se haya podido determinar: es la única posición
    donde el suplente cambia el partido por sí solo.
    """
    plantilla = list(getattr(equipo, "players", []) or [])
    clave = []
    for p in plantilla:
        estado = getattr(p, "status", PlayerStatus.TITULAR)
        if estado not in (PlayerStatus.TITULAR, PlayerStatus.DUDA):
            continue
        rol = getattr(p, "node_role", NodeRole.NONE)
        es_portero = (rol == NodeRole.KEEPER or
                      getattr(getattr(p, "position", None), "value", "") == "Portero")
        if rol != NodeRole.NONE or es_portero:
            clave.append(p)
    return clave


# =============================================================================
# EVALUACION
# =============================================================================

def evaluar(equipo: Team, once_confirmado: Optional[Sequence[str]]) -> InformeAusencias:
    """
    Compara el once previsto con el confirmado y calcula la penalización.

    Args:
        equipo: el equipo tal y como lo tiene el modelo (plantilla con roles).
        once_confirmado: nombres del once de última hora. Si viene vacío o
            demasiado corto, no se penaliza nada.

    Returns:
        InformeAusencias con los coeficientes ya acotados.
    """
    nombre_equipo = getattr(equipo, "name", "?")
    informe = InformeAusencias(equipo=nombre_equipo)

    once = [n for n in (once_confirmado or []) if str(n).strip()]
    if len(once) < MINIMO_ONCE_COMPARABLE:
        informe.comparable = False
        informe.motivo = (f"solo {len(once)} jugadores confirmados, hacen falta "
                          f"{MINIMO_ONCE_COMPARABLE}")
        return informe

    plantilla = list(getattr(equipo, "players", []) or [])
    clave = jugadores_clave(equipo)
    if not clave:
        informe.comparable = False
        informe.motivo = "el modelo no tiene jugadores clave para este equipo"
        return informe

    for jugador in clave:
        if _esta_en_el_once(jugador.name, once):
            continue
        rol = getattr(jugador, "node_role", NodeRole.NONE)
        ofensivo, defensivo = PESO_ROL.get(rol, PESO_ROL[NodeRole.NONE])
        calidad = _calidad_relativa(jugador, plantilla)
        informe.ausentes.append(Ausencia(
            nombre=jugador.name,
            rol=rol,
            calidad=calidad,
            impacto_ataque=ofensivo * calidad,
            impacto_encaje=defensivo * calidad,
        ))

    # Las bajas se suman, pero el efecto conjunto se acota: once ausencias no
    # dejan a un equipo sin marcar, entre otras cosas porque quien sale a jugar
    # tambien es futbolista profesional.
    total_ataque = sum(a.impacto_ataque for a in informe.ausentes)
    total_encaje = sum(a.impacto_encaje for a in informe.ausentes)

    informe.coef_ataque = max(COEF_ATAQUE_MIN, 1.0 - total_ataque)
    informe.coef_encaje = min(COEF_ENCAJE_MAX, 1.0 + total_encaje)
    informe.penalizacion_confianza = min(
        PENALIZACION_CONFIANZA_MAX,
        (total_ataque + total_encaje) * CONFIANZA_POR_IMPACTO
    )

    # Se ordenan por impacto para que la interfaz enseñe primero lo que importa.
    informe.ausentes.sort(key=lambda a: a.impacto_total, reverse=True)

    if informe.ausentes:
        logger.info("[Ausencias] %s", informe.resumen())
    return informe


def evaluar_partido(home_team: Team, away_team: Team,
                    once_local: Optional[Sequence[str]] = None,
                    once_visitante: Optional[Sequence[str]] = None):
    """Los dos informes de un partido, en el orden (local, visitante)."""
    return evaluar(home_team, once_local), evaluar(away_team, once_visitante)
