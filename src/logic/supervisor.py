"""
Agente supervisor — La Gema JARG74.

Capa de verificacion que se interpone entre los datos y la pantalla de estudio.
Existe porque la aplicacion no tenia ningun sitio donde comprobar la coherencia
del conjunto: cada fuente decidia por su cuenta si su respuesta valia, y la
interfaz pintaba lo que llegara. Asi convivian sin contradiccion aparente un
arbitro que no era el designado, un once con jugadores traspasados y once
centrocampistas.

El supervisor recibe el material completo de un partido y emite un veredicto:

    APTO       todo cuadra; se puede renderizar el estudio.
    ADVERTIDO  hay defectos menores; se renderiza, pero senalados.
    BLOQUEADO  hay un defecto que invalida el analisis; no se renderiza.

Que es un defecto grave y que es uno menor esta decidido de forma explicita en
GRAVEDAD, no repartido por el codigo:

    graves   arbitro sin confirmar para ESTE partido, jugador traspasado en el
             once, alineacion que no ha podido contrastarse con el listado de
             inscritos, temporada incoherente.
    leves    demarcacion no determinada, alineacion incompleta, arbitro fuera
             del censo local pero confirmado por fuente oficial.

Un bloqueo nunca es un callejon sin salida: cada incidencia lleva su
`solucion`, que dice exactamente que hacer para levantarlo (casi siempre,
confirmar el dato a mano).

Uso:

    from src.logic.supervisor import supervisar
    informe = supervisar(home="Athletic Club", away="Atlético de Madrid",
                         liga="La Liga", fecha=match_datetime,
                         arbitro=ref_dict, once_local=[...], once_visitante=[...])
    if informe.bloqueado:
        ...  # mostrar informe.incidencias y no calcular

Autor: Antigravity - La Gema JARG74
"""

import logging
from dataclasses import dataclass, field
from datetime import date, datetime
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)

APTO = "APTO"
ADVERTIDO = "ADVERTIDO"
BLOQUEADO = "BLOQUEADO"

GRAVE = "grave"
LEVE = "leve"

# Minimo de titulares contrastados por equipo para que un analisis se sostenga.
# Por debajo de esto la prediccion se calcula sobre un equipo que no es el que
# va a jugar.
MINIMO_TITULARES = 7


@dataclass
class Incidencia:
    """Un defecto concreto, con su explicacion y su salida."""

    codigo: str
    gravedad: str
    ambito: str            # "árbitro" | "alineación" | "temporada"
    mensaje: str
    solucion: str = ""
    detalle: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict:
        return {
            "codigo": self.codigo, "gravedad": self.gravedad,
            "ambito": self.ambito, "mensaje": self.mensaje,
            "solucion": self.solucion, "detalle": list(self.detalle),
        }


@dataclass
class Informe:
    """Veredicto del supervisor sobre un partido."""

    veredicto: str
    incidencias: List[Incidencia] = field(default_factory=list)
    comprobaciones: List[str] = field(default_factory=list)

    @property
    def bloqueado(self) -> bool:
        return self.veredicto == BLOQUEADO

    @property
    def graves(self) -> List[Incidencia]:
        return [i for i in self.incidencias if i.gravedad == GRAVE]

    @property
    def leves(self) -> List[Incidencia]:
        return [i for i in self.incidencias if i.gravedad == LEVE]

    def resumen(self) -> str:
        if self.veredicto == APTO:
            return "Datos verificados. El estudio se puede calcular."
        if self.veredicto == ADVERTIDO:
            return (f"{len(self.leves)} aviso(s) sin gravedad. El estudio se "
                    f"puede calcular, pero revisa lo señalado.")
        return (f"{len(self.graves)} incidencia(s) grave(s) impiden un análisis "
                f"fiable. Corrige lo señalado antes de continuar.")

    def to_dict(self) -> Dict:
        return {
            "veredicto": self.veredicto,
            "resumen": self.resumen(),
            "incidencias": [i.to_dict() for i in self.incidencias],
            "comprobaciones": list(self.comprobaciones),
        }


# =============================================================================
# Comprobacion del arbitro
# =============================================================================

_NOMBRES_VACIOS = {
    "", "por detectar", "por confirmar", "no detectado", "no asignado",
    "pendiente", "tbd", "desconocido", "no asignado aún", "no asignado aun",
}


def _revisar_arbitro(arbitro: Optional[Dict], liga: str,
                     incidencias: List[Incidencia],
                     comprobaciones: List[str]) -> None:
    """
    ¿Es este el arbitro designado para ESTE partido?

    Aparecer en la base local no basta y es la confusion que hacia falta
    deshacer: enrich_referee marcaba _is_fallback=False en cuanto reconocia el
    nombre, lo que solo significa "sabemos quien es", nunca "le han designado
    para este encuentro".
    """
    from src.data.referee_database import pertenece_al_censo, es_nombre_plausible

    if not arbitro:
        incidencias.append(Incidencia(
            codigo="ARB_AUSENTE", gravedad=GRAVE, ambito="árbitro",
            mensaje="No hay ningún árbitro asignado al partido.",
            solucion="Pulsa «Buscar Árbitro Auto» o introdúcelo manualmente.",
        ))
        return

    nombre = (arbitro.get("name") or "").strip()

    if nombre.lower() in _NOMBRES_VACIOS:
        incidencias.append(Incidencia(
            codigo="ARB_PENDIENTE", gravedad=GRAVE, ambito="árbitro",
            mensaje=(arbitro.get("motivo")
                     or "La designación arbitral aún no está publicada."),
            solucion=("Consulta el portal oficial de la competición y "
                      "escribe el nombre en el campo manual."),
            detalle=[c.get("url", "") for c in arbitro.get("consultar", []) if c.get("url")],
        ))
        return

    if not es_nombre_plausible(nombre):
        incidencias.append(Incidencia(
            codigo="ARB_NO_ES_NOMBRE", gravedad=GRAVE, ambito="árbitro",
            mensaje=f"«{nombre}» no tiene forma de nombre de persona.",
            solucion="Bórralo e introduce el árbitro manualmente.",
        ))
        return

    estado = arbitro.get("estado")
    manual = "manual" in (arbitro.get("source") or "").lower()
    en_censo = arbitro.get("en_censo")
    if en_censo is None:
        en_censo = pertenece_al_censo(nombre, liga)

    # Un nombre que la competicion no reconoce no se descarta —cada temporada
    # ascienden colegiados nuevos— pero tampoco se da por bueno en silencio.
    if en_censo is False and not manual:
        incidencias.append(Incidencia(
            codigo="ARB_FUERA_CENSO", gravedad=GRAVE, ambito="árbitro",
            mensaje=(f"«{nombre}» no figura entre los colegiados de {liga} que "
                     f"conoce la aplicación."),
            solucion=("Verifícalo en el portal oficial. Si es correcto, "
                      "confírmalo en el campo manual para desbloquearlo."),
        ))
        return

    if manual:
        comprobaciones.append(f"Árbitro «{nombre}» confirmado manualmente.")
        return

    if estado == "VERIFICADO":
        comprobaciones.append(
            f"Árbitro «{nombre}» verificado · {arbitro.get('motivo', '')}".strip())
        return

    if estado == "PROBABLE" or arbitro.get("_is_fallback"):
        incidencias.append(Incidencia(
            codigo="ARB_SIN_CONFIRMAR", gravedad=GRAVE, ambito="árbitro",
            mensaje=(f"«{nombre}» aparece como probable, no confirmado. "
                     + (arbitro.get("motivo") or "")).strip(),
            solucion=("Compruébalo en el enlace de verificación y confírmalo "
                      "manualmente si es correcto."),
            detalle=[arbitro["verification_link"]] if arbitro.get("verification_link") else [],
        ))
        return

    # Sin estado: viene de un camino que no dice como de seguro esta el dato.
    # No se le da el aprobado. Un nombre sin procedencia declarada es justo lo
    # que dejaba pasar arbitros de otros partidos, y "no consta" no puede
    # significar "correcto".
    incidencias.append(Incidencia(
        codigo="ARB_SIN_PROCEDENCIA", gravedad=GRAVE, ambito="árbitro",
        mensaje=(f"«{nombre}» llega sin indicar cómo se ha verificado "
                 f"(fuente: {arbitro.get('source', 'desconocida')})."),
        solucion=("Vuelve a buscarlo para que pase por la verificación, o "
                  "confírmalo manualmente si ya lo has comprobado."),
    ))


# =============================================================================
# Comprobacion de la alineacion
# =============================================================================

def _revisar_once(once: List[str], equipo: str, liga: str, lado: str,
                  incidencias: List[Incidencia],
                  comprobaciones: List[str]) -> None:
    """Contrasta un once con el listado de inscritos vigente del club."""
    from src.data import plantillas

    if not once:
        incidencias.append(Incidencia(
            codigo="ONCE_VACIO", gravedad=GRAVE, ambito="alineación",
            mensaje=f"No hay alineación para {equipo} ({lado}).",
            solucion="Fuerza la búsqueda profunda o introduce el once a mano.",
        ))
        return

    try:
        informe = plantillas.auditar_alineacion(once, equipo, liga)
    except Exception as e:
        logger.error(f"Auditoría de plantilla falló para {equipo}: {e}")
        incidencias.append(Incidencia(
            codigo="ONCE_NO_AUDITABLE", gravedad=GRAVE, ambito="alineación",
            mensaje=(f"No se ha podido contrastar la alineación de {equipo} "
                     f"con el listado de inscritos ({type(e).__name__})."),
            solucion="Reintenta la búsqueda; si persiste, revisa las claves de API.",
        ))
        return

    if not informe["verificada"]:
        incidencias.append(Incidencia(
            codigo="ONCE_SIN_REFERENCIA", gravedad=GRAVE, ambito="alineación",
            mensaje=informe["motivo"],
            solucion=("Sin listado vigente no se puede descartar que haya "
                      "jugadores traspasados. Reintenta más tarde o valida el "
                      "once a mano."),
        ))
        return

    if informe["descartados"]:
        incidencias.append(Incidencia(
            codigo="ONCE_TRASPASADOS", gravedad=GRAVE, ambito="alineación",
            mensaje=(f"{len(informe['descartados'])} jugador(es) del once de "
                     f"{equipo} ya no están en el club."),
            solucion="Se han retirado del análisis. Complétalo con los titulares reales.",
            detalle=list(informe["descartados"]),
        ))

    vigentes = informe["vigentes"]
    if len(vigentes) < MINIMO_TITULARES:
        incidencias.append(Incidencia(
            codigo="ONCE_INCOMPLETO", gravedad=LEVE, ambito="alineación",
            mensaje=(f"Solo {len(vigentes)} titular(es) de {equipo} han podido "
                     f"contrastarse (mínimo recomendado: {MINIMO_TITULARES})."),
            solucion="Añade los que falten en el campo de alineación manual.",
        ))
    else:
        comprobaciones.append(
            f"{equipo}: {len(vigentes)} titulares contrastados contra "
            f"{informe['plantilla']} inscritos.")

    # Demarcaciones. Que no se determinen no invalida el analisis, pero se dice.
    sin_demarcacion = []
    for jugador in vigentes:
        try:
            if plantillas.demarcacion_de(jugador, equipo, liga)["posicion"] is None:
                sin_demarcacion.append(jugador)
        except Exception:
            sin_demarcacion.append(jugador)

    if sin_demarcacion:
        incidencias.append(Incidencia(
            codigo="DEMARCACION_DESCONOCIDA", gravedad=LEVE, ambito="alineación",
            mensaje=(f"{len(sin_demarcacion)} jugador(es) de {equipo} sin "
                     f"demarcación determinada."),
            solucion=("Se muestran como «Sin demarcación» en lugar de "
                      "asignarles una posición por defecto."),
            detalle=sin_demarcacion,
        ))


# =============================================================================
# Comprobacion temporal
# =============================================================================

def _revisar_temporada(fecha, liga: str, incidencias: List[Incidencia],
                       comprobaciones: List[str]) -> None:
    """
    ¿La fecha del partido cae dentro de la temporada en curso?

    Detecta el descuadre que producia analizar un partido de hoy con datos de
    una temporada cerrada.
    """
    from src.data import plantillas

    if fecha is None:
        return

    dia = fecha.date() if isinstance(fecha, datetime) else fecha
    if not isinstance(dia, date):
        return

    try:
        temporada = plantillas.temporada_vigente(liga)
    except Exception:
        temporada = None

    if not temporada or not temporada.get("inicio"):
        return

    try:
        inicio = datetime.fromisoformat(str(temporada["inicio"])[:10]).date()
        fin = datetime.fromisoformat(str(temporada["fin"])[:10]).date()
    except (ValueError, TypeError):
        return

    if inicio <= dia <= fin:
        comprobaciones.append(
            f"Fecha dentro de la temporada vigente ({inicio} a {fin}).")
        return

    incidencias.append(Incidencia(
        codigo="TEMPORADA_INCOHERENTE", gravedad=GRAVE, ambito="temporada",
        mensaje=(f"La fecha del partido ({dia}) queda fuera de la temporada "
                 f"vigente de {liga} ({inicio} a {fin})."),
        solucion=("Corrige la fecha del partido: los datos de plantilla y "
                  "designaciones serían de otra temporada."),
    ))


# =============================================================================
# Entrada publica
# =============================================================================

def supervisar(home: str, away: str, liga: str = "", fecha=None,
               arbitro: Optional[Dict] = None,
               once_local: Optional[List[str]] = None,
               once_visitante: Optional[List[str]] = None,
               revisar_temporada: bool = True) -> Informe:
    """
    Contrasta todo el material del partido y emite un veredicto.

    Es la unica puerta por la que deberia pasar un estudio antes de pintarse.
    No corrige nada por su cuenta: informa de lo que esta mal, de por que lo
    esta y de como arreglarlo, y deja la decision en manos de quien mira.
    """
    incidencias: List[Incidencia] = []
    comprobaciones: List[str] = []

    _revisar_arbitro(arbitro, liga, incidencias, comprobaciones)
    _revisar_once(once_local or [], home, liga, "local", incidencias, comprobaciones)
    _revisar_once(once_visitante or [], away, liga, "visitante", incidencias, comprobaciones)
    if revisar_temporada:
        _revisar_temporada(fecha, liga, incidencias, comprobaciones)

    if any(i.gravedad == GRAVE for i in incidencias):
        veredicto = BLOQUEADO
    elif incidencias:
        veredicto = ADVERTIDO
    else:
        veredicto = APTO

    informe = Informe(veredicto=veredicto, incidencias=incidencias,
                      comprobaciones=comprobaciones)
    logger.info(f"[Supervisor] {home} vs {away}: {veredicto} "
                f"({len(informe.graves)} graves, {len(informe.leves)} leves)")
    return informe
