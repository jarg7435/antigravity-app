"""
Bootstrap de TLS para La Gema JARG74.

Algunos antivirus de escritorio (Norton, Kaspersky, ESET, Avast) interceptan
el trafico HTTPS y lo re-firman con una CA propia que instalan en el almacen
de certificados del sistema. Python no usa ese almacen: valida contra el
bundle de certifi, que obviamente no contiene esa CA. El resultado es un
SSLCertVerificationError "unable to get local issuer certificate" en todas
las llamadas a APIs y scrapers, aunque el navegador funcione sin problemas.

truststore delega la validacion en el almacen del sistema operativo, con lo
que esas CAs pasan a ser validas. En Streamlit Cloud no hace falta, pero es
inocuo: alli el almacen del sistema es el normal.

IMPORTANTE: activar_tls() debe llamarse ANTES de que cualquier libreria cree
su contexto SSL. En la practica, lo primero del arranque.
"""

import logging

logger = logging.getLogger(__name__)

_activado = False


def activar_tls() -> bool:
    """
    Usa el almacen de certificados del sistema para validar TLS.

    Es idempotente y nunca lanza: si truststore no esta instalado o falla la
    inyeccion, se sigue con el comportamiento por defecto de certifi.

    Returns:
        True si el almacen del sistema quedo activo.
    """
    global _activado
    if _activado:
        return True

    try:
        import truststore
    except ImportError:
        logger.info(
            "truststore no instalado: se validara TLS con el bundle de certifi. "
            "Si un antivirus intercepta HTTPS, las llamadas a APIs fallaran."
        )
        return False

    try:
        truststore.inject_into_ssl()
    except Exception as e:
        logger.warning(f"No se pudo activar el almacen del sistema para TLS: {e}")
        return False

    _activado = True
    logger.info("TLS validado contra el almacen de certificados del sistema")
    return True
