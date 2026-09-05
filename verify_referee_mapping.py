# -*- coding: utf-8 -*-
"""
Verifica el enrutado de competiciones a su fuente de designaciones arbitrales.

Antes comprobaba que cada liga devolviera SU clase de scraper
(LaLigaRefereeScraper, PremierLeagueRefereeScraper...). Ya no hay una clase por
liga: las cinco hacian exactamente lo mismo —raspar la portada de la federacion
con una expresion regular que cruzaba toda la pagina— y mantener cinco copias
de esa logica fue lo que propago el mismo fallo a las cinco competiciones.

Ahora hay un unico BuscadorDesignaciones que recibe la liga y delega en
src/data/investigador_web.py. Lo que hay que verificar, por tanto, ya no es la
clase sino que cada nombre de competicion —con todas las variantes que usa la
interfaz— se enrute a la liga correcta.
"""

import os
import sys

sys.path.append(os.path.abspath(os.path.join(os.getcwd())))

from src.data.referee_source_mapper import (
    RefereeSourceMapper, BuscadorDesignaciones,
    LaLigaRefereeScraper, PremierLeagueRefereeScraper,
    InternationalRefereePoolScraper,
)


def test_mapping():
    casos = [
        ("La Liga", "La Liga"),
        ("La Liga EA Sports", "La Liga"),
        ("La Liga (España)", "La Liga"),
        ("Primera Division", "La Liga"),
        ("Premier League", "Premier League"),
        ("Premier League (Inglaterra)", "Premier League"),
        ("Serie A (Italia)", "Serie A"),
        ("Bundesliga (Alemania)", "Bundesliga"),
        ("Ligue 1 (Francia)", "Ligue 1"),
        ("Champions League", "UEFA"),
        ("Europa League", "UEFA"),
        # Sin correspondencia: se conserva el nombre y el investigador se
        # limitara a las fuentes generales, sin censo con el que contrastar.
        ("EPL", "EPL"),
        ("Liga Mixta (Combinada)", "Liga Mixta (Combinada)"),
    ]

    print("--- Enrutado de competiciones a fuente de designaciones ---")
    todo_ok = True
    for nombre_liga, liga_esperada in casos:
        buscador = RefereeSourceMapper.get_scraper(nombre_liga)
        ok = isinstance(buscador, BuscadorDesignaciones) and buscador.league == liga_esperada
        print(f"[{'PASS' if ok else 'FAIL'}] '{nombre_liga}' -> "
              f"{buscador.league!r} (esperado: {liga_esperada!r})")
        todo_ok = todo_ok and ok

    # Los alias historicos deben seguir existiendo y apuntar a su liga: otros
    # modulos podrian importarlos por nombre.
    print("\n--- Alias historicos ---")
    for clase, liga_esperada in (
        (LaLigaRefereeScraper, "La Liga"),
        (PremierLeagueRefereeScraper, "Premier League"),
        (InternationalRefereePoolScraper, "UEFA"),
    ):
        instancia = clase()
        ok = isinstance(instancia, BuscadorDesignaciones) and instancia.league == liga_esperada
        print(f"[{'PASS' if ok else 'FAIL'}] {clase.__name__}() -> {instancia.league!r}")
        todo_ok = todo_ok and ok

    # Sin designacion publicada NUNCA se devuelve un nombre.
    print("\n--- Ausencia de designacion ---")
    vacio = BuscadorDesignaciones("La Liga")._sin_designacion()
    ok = vacio["name"] == "" and vacio["_is_fallback"] and vacio["estado"] == "PENDIENTE"
    print(f"[{'PASS' if ok else 'FAIL'}] Sin designacion -> name={vacio['name']!r}, "
          f"estado={vacio['estado']!r}")
    todo_ok = todo_ok and ok

    if todo_ok:
        print("\nTODAS LAS COMPROBACIONES DE ENRUTADO HAN PASADO")
    else:
        print("\nHAY COMPROBACIONES DE ENRUTADO QUE FALLAN")
        sys.exit(1)


if __name__ == "__main__":
    test_mapping()
