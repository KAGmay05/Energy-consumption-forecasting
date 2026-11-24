# Resultados de los modelos

Equipo 3 · Noviembre de 2026

Este documento reúne las cifras de todos los modelos de consumo para compararlos en un solo sitio. Las reglas con las que se miden están en [decisiones.md](decisiones.md), y el análisis de cada modelo, en su cuaderno.

**Todas las cifras son de validación (2011-2012).** El test (2012-2013) todavía no se ha ejecutado: se usa una sola vez por modelo ([decisiones.md](decisiones.md), sección 2).

## En breve

- **El umbral es la media de 7 días.** Es la mejor referencia sin sesgo: MASE de 0,81 el día 1 a 0,90 el día 14 y error de la energía diaria del 18,4 al 22,8 %.
- **La mediana de 7 días tiene menos MASE, pero subestima el consumo un 11,8 %.** Superarla en MASE no basta si es a costa del sesgo.
- **Lo más difícil es el invierno, los fines de semana y los días de calor.** En los días de 30 °C o más, la media de 7 días subestima el consumo un 14,9 %.
- **Semanas y meses.** El consumo reciente es la mejor referencia hasta 28 días de antelación en la semana y hasta 14 en el mes. Después lo es el año anterior, con un error del 23,1 % y del 17,8 %.

## Estado

| Modelo | Validación | Test | Cuaderno |
|---|---|---|---|
| Referencias horarias | Hecha | Pendiente, con el primer LightGBM | [baselines.ipynb](../../notebooks/baselines.ipynb) |
| Referencias de semanas y meses | Hecha | Pendiente, con el primer LightGBM | [baselines.ipynb](../../notebooks/baselines.ipynb), sección 4 |
| LightGBM | Pendiente | Pendiente | |
| LSTM | Pendiente | Pendiente | |
| TFT | Pendiente | Pendiente | |
| Chronos-2 | Pendiente | Pendiente | |
| Modelo de semanas y meses | Pendiente | Pendiente | |

## Cómo leer las cifras

- **Día.** Día de horizonte: el 1 es el día del origen y el 14, trece días después.
- **MASE.** Error absoluto medio del hogar dividido por el de copiar la hora de 24 horas antes en el periodo de ajuste. Menos es mejor. Se da la mediana de los 300 hogares.
- **Energía diaria.** Error absoluto medio de la energía de un día, en % de la energía diaria media del hogar. Se da la mediana de los 300 hogares.
- **Sesgo.** De todas las horas juntas, en %. Es positivo si el modelo sobrestima el consumo. Un sesgo negativo da más autonomía de la real.
- **En negrita**, la referencia que fija el umbral.

## 1. Consumo horario, hasta 14 días

### 1.1 Error

| Modelo | MASE día 1 | MASE día 2 | MASE día 7 | MASE día 14 | Energía día 1 | Energía día 2 | Energía día 7 | Energía día 14 |
|---|---|---|---|---|---|---|---|---|
| **Media de 7 días** | **0,81** | **0,82** | **0,87** | **0,90** | **18,4 %** | **19,2 %** | **21,2 %** | **22,8 %** |
| Mediana de 7 días | 0,76 | 0,78 | 0,82 | 0,84 | 19,5 % | 20,5 % | 22,4 % | 24,2 % |
| Persistencia de 24 h | 0,94 | 1,00 | 0,99 | 1,03 | 19,6 % | 22,0 % | 24,0 % | 26,0 % |
| Persistencia de 168 h | 0,99 | 0,99 | 0,99 | 1,03 | 24,0 % | 24,1 % | 24,0 % | 26,0 % |
| Climatología | 0,96 | 0,96 | 0,97 | 0,97 | 26,4 % | 26,4 % | 26,5 % | 26,4 % |

### 1.2 Sesgo

Las dos últimas columnas juntan los 14 días. La franja de 18:00 a 06:00 es la que cubre la batería sin sol.

| Modelo | Día 1 | Día 14 | De 06:00 a 18:00 | De 18:00 a 06:00 |
|---|---|---|---|---|
| **Media de 7 días** | **0,0 %** | **+0,1 %** | **−0,1 %** | **0,0 %** |
| Mediana de 7 días | −11,8 % | −11,8 % | −15,6 % | −8,5 % |
| Persistencia de 24 h | 0,0 % | 0,0 % | −0,1 % | 0,0 % |
| Persistencia de 168 h | 0,0 % | 0,0 % | −0,1 % | 0,0 % |
| Climatología | +6,3 % | +6,4 % | +6,7 % | +5,8 % |

### 1.3 El umbral, día a día

Un modelo aporta en un día de horizonte si su MASE es menor que el de la media de 7 días y su sesgo y su error de la energía diaria no son peores ([decisiones.md](decisiones.md), sección 3). La última columna es solo la referencia del MAE.

| Día | MASE | Sesgo | Energía diaria | MASE de la mediana de 7 días |
|---|---|---|---|---|
| 1 | 0,814 | +0,01 % | 18,4 % | 0,763 |
| 2 | 0,824 | +0,03 % | 19,2 % | 0,777 |
| 3 | 0,836 | +0,03 % | 19,8 % | 0,786 |
| 4 | 0,844 | +0,02 % | 20,2 % | 0,796 |
| 5 | 0,855 | −0,03 % | 20,6 % | 0,803 |
| 6 | 0,863 | −0,06 % | 21,0 % | 0,807 |
| 7 | 0,872 | −0,09 % | 21,2 % | 0,817 |
| 8 | 0,876 | −0,13 % | 21,6 % | 0,822 |
| 9 | 0,881 | −0,13 % | 21,8 % | 0,827 |
| 10 | 0,884 | −0,13 % | 22,1 % | 0,830 |
| 11 | 0,888 | −0,09 % | 22,3 % | 0,833 |
| 12 | 0,893 | −0,09 % | 22,6 % | 0,839 |
| 13 | 0,897 | −0,06 % | 22,7 % | 0,839 |
| 14 | 0,902 | +0,05 % | 22,8 % | 0,844 |

### 1.4 Por segmento

Con los 14 días juntos. Los segmentos se definen en [decisiones.md](decisiones.md), sección 5. La casa vacía solo aparece en 58 hogares.

**MASE**

| Modelo | Laborable | Sábado | Domingo | Festivo | Verano | Otoño | Invierno | Primavera | Navidad | Calor | Casa vacía |
|---|---|---|---|---|---|---|---|---|---|---|---|
| **Media de 7 días** | **0,83** | **0,90** | **0,93** | **0,84** | **0,72** | **0,77** | **1,14** | **0,81** | **0,76** | **0,82** | **0,86** |
| Mediana de 7 días | 0,77 | 0,86 | 0,90 | 0,81 | 0,67 | 0,72 | 1,08 | 0,75 | 0,73 | 0,79 | 0,68 |
| Persistencia de 24 h | 1,00 | 1,07 | 1,11 | 0,97 | 0,87 | 0,93 | 1,36 | 0,97 | 0,91 | 0,98 | 0,80 |
| Persistencia de 168 h | 0,97 | 1,07 | 1,10 | 1,00 | 0,86 | 0,89 | 1,31 | 0,95 | 0,90 | 0,95 | 0,94 |
| Climatología | 0,94 | 1,02 | 1,02 | 0,96 | 0,85 | 0,89 | 1,23 | 0,85 | 0,92 | 0,94 | 1,45 |

**Sesgo (%)**

| Modelo | Laborable | Sábado | Domingo | Festivo | Verano | Otoño | Invierno | Primavera | Navidad | Calor | Casa vacía |
|---|---|---|---|---|---|---|---|---|---|---|---|
| **Media de 7 días** | **+1,5** | **−1,2** | **−4,7** | **−6,8** | **+0,2** | **−2,7** | **+0,5** | **+1,7** | **−2,2** | **−14,9** | **+101,0** |
| Mediana de 7 días | −10,5 | −12,9 | −16,0 | −17,4 | −12,1 | −14,0 | −10,7 | −10,7 | −13,9 | −25,2 | +71,2 |
| Persistencia de 24 h | +1,5 | −1,2 | −4,7 | −6,0 | 0,0 | −1,8 | +0,5 | +1,0 | −1,6 | −14,7 | +78,4 |
| Persistencia de 168 h | +0,3 | −0,2 | 0,0 | −6,0 | +0,2 | −2,7 | +0,6 | +1,7 | −2,9 | −16,4 | +102,5 |
| Climatología | +6,4 | +7,5 | +3,3 | +9,7 | +16,0 | +5,2 | +3,3 | +1,5 | +17,7 | −8,1 | +279,9 |

## 2. Semanas y meses

Energía de bloques de 7 días (semana) y de 28 días (mes), según los días de antelación entre el origen y el inicio del bloque ([decisiones.md](decisiones.md), sección 8). En negrita, la mejor referencia de cada antelación, que es el umbral.

**Error (% de la energía media de un bloque del hogar, mediana de los hogares)**

| Bloque y modelo | 0 | 7 | 14 | 28 | 56 | 91 | 182 | 273 |
|---|---|---|---|---|---|---|---|---|
| Semana: reciente | **13,5** | **16,4** | **17,9** | **20,7** | 25,0 | 28,0 | 30,6 | 31,8 |
| Semana: año anterior | 23,1 | 23,1 | 23,1 | 23,1 | **23,1** | **23,1** | **23,1** | **23,1** |
| Mes: reciente | **13,7** | **15,8** | **17,5** | 19,6 | 23,0 | 25,8 | 28,5 | 28,5 |
| Mes: año anterior | 17,8 | 17,8 | 17,8 | **17,8** | **17,8** | **17,8** | **17,8** | **17,8** |

**Sesgo (%, todos los bloques juntos)**

| Bloque y modelo | 0 | 7 | 14 | 28 | 56 | 91 | 182 | 273 |
|---|---|---|---|---|---|---|---|---|
| Semana: reciente | −0,2 | −0,1 | −0,1 | +0,1 | +1,0 | +1,5 | +4,9 | +5,1 |
| Semana: año anterior | +6,0 | +6,0 | +6,0 | +6,0 | +6,0 | +6,0 | +6,0 | +6,0 |
| Mes: reciente | +0,2 | +0,5 | +0,9 | +2,1 | +4,0 | +4,5 | +8,2 | +7,9 |
| Mes: año anterior | +6,5 | +6,5 | +6,5 | +6,5 | +6,5 | +6,5 | +6,5 | +6,5 |

## 3. Cómo añadir un modelo

1. Evaluarlo en el pliegue de validación, como explica el [README](../../README.md#cómo-se-evalúan-los-modelos).
2. Añadir una fila a cada tabla con los valores de estas columnas:

| Tabla | De dónde sale |
|---|---|
| 1.1, MASE | `por_dia`, columna `mase_mediana` |
| 1.1, energía diaria | `energia_diaria`, columna `error_energia_mediana` |
| 1.2, días 1 y 14 | `por_dia`, columna `sesgo_total` |
| 1.2, franjas | `noche`, columna `sesgo_total` |
| 1.4, MASE y sesgo | `por_segmento`, columnas `mase_mediana` y `sesgo_total` |
| 2, error y sesgo | `summarize_blocks` de `src/models/energy_baselines.py`: `error_mediana` y `sesgo_total` |

3. Actualizar la tabla de estado con el enlace a su cuaderno. La comparación con el umbral en los 14 días (1.3) va en el cuaderno.

Las tablas completas de las referencias se generan con `python -m src.models.baselines` y se guardan en `data/results/`, que no se sube a git.
