# 📄 Manual Técnico: LAGEMA JARG74 (V6.0)

Este documento detalla la arquitectura, algoritmos y procesos operativos del ecosistema Antigravity para apuestas deportivas profesionales.

## 1. Motores de Inteligencia

### 🛡️ BPA Engine (Blindaje de Puntos Críticos)
- **Función**: Evalúa factores tácticos y contextuales (lesiones, rotaciones, clima, árbitro).
- **Impacto**: Genera un "bias" o ajuste que se suma a la probabilidad estadística pura.

### 📈 Poisson Engine (Distribución de Goles)
- **Función**: Calcula probabilidades de marcadores exactos (`0-0`, `1-0`, etc.) usando la media de goles esperados (Lambdas).
- **Mercados**: Más de 2.5, Ambos marcan, Marcador exacto.

### 🤖 ML Engine (Ensemble XGBoost/RF)
- **Función**: Clasificador binario/multiclase basado en datos históricos (XGBoost y Random Forest).
- **Meta**: 55%+ de precisión en mercados de 1X2.

## 2. Motor Financiero (Profitability)

### 💎 ValueEngine
- **Algoritmo**: Compara la Probabilidad IA contra la cuota del mercado (`EV = (Prob * Cuota) - 1`).
- **Kelly Criterion**: Utiliza `Fractional Kelly (1/4)` para calcular el stake sugerido, protegiendo contra rachas de varianza.

### 💰 BankrollManager
- **Persistencia**: Datos guardados en `data/bankroll.json`.
- **Métricas**: ROI (Return on Investment), Equity Curve (Plotly).

## 3. Guía de Operación

1.  **Configuración**: Seleccionar la liga y equipos (o entrar datos manuales).
2.  **Validación 1H**: Confirmar alineaciones reales. Si hay cambios críticos, el BPA lo reflejará inmediatamente.
3.  **Ejecución**: Si el sistema muestra una **Alerta de Valor** de más del 5%, la apuesta se considera rentable a largo plazo.
4.  **Post-Partido**: Introducir el resultado real en la "Zona de Aprendizaje" para recalibrar los pesos de los equipos.

---
*Desarrollado para: LAGEMA JARG74 - Equipo Antigravity*
