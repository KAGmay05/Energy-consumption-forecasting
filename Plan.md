# Planes futuros del proyecto

Equipo 3 · Noviembre de 2026

Este documento recoge los modelos que se van a implementar. Su justificación está en el [estado del arte](estado_del_arte.md).

El sistema consta de tres componentes: un pronóstico de consumo, un pronóstico de generación fotovoltaica (FV) y una simulación de la batería que combina ambos para estimar cuántas horas del día habrá suministro.

## 1. Predicción del consumo

| Modelo | Papel |
|---|---|
| Persistencia estacional y media estacional | Referencias mínimas con las que se compara todo lo demás |
| LightGBM | Modelo principal. Usa retardos del consumo, variables de calendario y temperatura y humedad pronosticadas |
| LSTM | Red recurrente, la familia más usada en los trabajos de referencia |
| TFT (Temporal Fusion Transformer) | Admite el pronóstico meteorológico como entrada futura y produce cuantiles |
| Chronos-2 | Modelo fundacional, usado sin entrenamiento específico y con covariables meteorológicas |

Para los horizontes de semanas y meses se usará un modelo de energía diaria o semanal basado en el calendario y la estacionalidad, porque los modelos horarios pierden su ventaja a partir de unos días.

## 2. Predicción de la generación fotovoltaica

Modelo físico con pvlib, que calcula la generación a partir de la capacidad instalada y de la irradiancia y la temperatura de Open-Meteo. No necesita histórico de generación.

## 3. Estimación de la duración

- **Simulación del balance energético de la batería.** A partir de los pronósticos de consumo y de generación, se simula hora a hora el estado de carga y se obtienen las horas diarias con y sin suministro.
- **Simulación de Monte Carlo.** La simulación se repite sobre muchos escenarios para dar el resultado como intervalo (P10, P50 y P90) y como probabilidad de agotamiento. Hasta unos 15 días, los escenarios proceden del ensemble meteorológico de Open-Meteo; para semanas y meses, de la climatología histórica (ERA5).

## 4. Incertidumbre y evaluación

- **Incertidumbre del consumo.** Regresión cuantílica con LightGBM, calibrada con predicción conformal (CQR).
- **Evaluación.** Validación temporal con origen móvil. Los modelos de consumo se comparan con MAE, MASE y sesgo, y la cadena completa, por el error en horas de suministro en cada horizonte.

## 5. Orden de implementación

1. Datos: buscar los datos de consumo y descargar los meteorológicos.
2. Referencias y LightGBM.
3. pvlib y simulación de la batería, para tener la cadena completa.
4. Cuantiles y Monte Carlo.
5. Horizontes de semanas y meses.
6. LSTM, TFT y Chronos-2, y comparación final.
