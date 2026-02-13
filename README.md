# LAGEMA JARG74 V6.0 - Sistema de Análisis Predictivo de Fútbol

## Identidad del Sistema
LAGEMA JARG74 es un sistema de inteligencia analítica deportiva especializado en predicción de partidos de fútbol con una precisión objetivo >80%. El sistema combina análisis multifuente, validación visual en tiempo real (**Blindaje V5.0**) y aprendizaje continuo supervisado.

## Competiciones Objetivo
- Premier League
- La Liga EA Sports
- Serie A
- Bundesliga
- Ligue 1
- Competiciones UEFA

## Metodología
1.  **Recopilación Multifuente**: Datos de Opta, Transfermarkt, y prensa local.
2.  **Cálculo BPA (Balance de Presión Avanzada)**: Algoritmo ponderado basado en 5 nodos críticos (Finalizador, Creador, Defensivo, Portero, Táctico).
3.  **Blindaje V5.0**: Validación visual cruzada minutos antes del partido para confirmar alineaciones.
4.  **Predicciones**: 
    - **P1**: Resultado directo (1X2).
    - **P2**: Rango de goles y BTTS.
    - **OPE3**: Mercados estadísticos (Córners, Tarjetas, Remates).

## Estructura del Proyecto
- `src/`: Lógica central del sistema (Modelos, BPA, Scrapers).
- `app/`: Interfaz de usuario basada en Streamlit.
- `data/`: Almacenamiento de datos locales (SQLite).

## Instalación
```bash
pip install -r requirements.txt
streamlit run app/main.py
```
