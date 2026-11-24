# Decisiones de modelado

Equipo 3 · Noviembre de 2026

Este documento fija cómo se evalúan los modelos de consumo y responde a las preguntas abiertas que deja el análisis exploratorio, `notebooks/forecasting_eda.ipynb`. Cuando se cita una sección sin más, es de ese cuaderno. Las limitaciones de los datos (G1 a G14) están en `docs/data/gaps.md`.

Unas decisiones se toman ya porque las necesitan los modelos de referencia. Otras solo afectan a LightGBM y quedan con una propuesta inicial que se confirmará al entrenarlo. La tabla de la sección 9 indica cuál es cada una.

## 1. Planteamiento del pronóstico

- **Origen.** Se pronostica una vez al día, a las 00:00 hora local. El origen *t0* es la marca `timestamp_utc` de la hora que termina a esa medianoche: las 14:00 UTC en horario estándar y las 13:00 UTC en horario de verano.
- **Información disponible.** Desde *t0* solo se usa el consumo de las horas que terminan en *t0* o antes. El clima de las horas pronosticadas se toma de ERA5, el tiempo que realmente hizo. Equivale a un pronóstico meteorológico perfecto, así que el error medido es una cota inferior del real (G9).
- **Horizonte.** Los 14 días locales que empiezan en el origen, del día *d0* al *d0 + 13*. Catorce días es el alcance del ensemble de Open-Meteo, del que saldrán los escenarios de la simulación. El horizonte tiene 336 horas, salvo cuando incluye un cambio de horario: 335 si empieza el horario de verano y 337 si termina.
- **Paso *h*.** Horas reales desde el origen: *h* = 1 es la hora de 00:00 a 01:00 del día *d0*.
- **Día de horizonte *k*.** Fecha local de la hora pronosticada menos *d0*, más 1. Va de 1 a 14, y es la unidad en que se dará la respuesta final (horas de suministro por día).

El modelo horario cubre estos 14 días. Las preguntas a semanas y meses se responden con la energía de periodos de 7 y 28 días, con un modelo aparte y su propio umbral (sección 8). Las referencias apoyan el corte en los 14 días: a esa distancia, el consumo de la última semana todavía da menos error que la climatología (`notebooks/baselines.ipynb`, sección 1).

## 2. Pliegues

| Pliegue | Periodo de ajuste | Orígenes | Número de orígenes | Uso |
|---|---|---|---|---|
| Validación | 2010-07-01 a 2011-06-30 | 2011-07-01 a 2012-06-17 | 353 | Elegir variables e hiperparámetros y comparar modelos durante el desarrollo |
| Test | 2010-07-01 a 2012-06-30 | 2012-07-01 a 2013-06-17 | 352 | Medición final |

- El último origen de cada pliegue es el último cuyos 14 días caen dentro del año. Ningún horizonte cruza de un año al siguiente.
- Todo lo que se ajusta, como la escala del MASE, la climatología de referencia o un modelo entrenado, se calcula solo con el periodo de ajuste del pliegue. En validación ese periodo es un año y en test son dos, así que en test la climatología y los modelos entrenados disponen de más datos.
- Las variables y los hiperparámetros se eligen **solo** con el pliegue de validación.
- El test se ejecuta **una sola vez por modelo**, cuando su configuración ya está fijada con validación. Las referencias se ejecutan en test a la vez que el primer LightGBM.
- Los modelos entrenados se entrenan una vez por pliegue con todo su periodo de ajuste. Si conviene reentrenarlos durante el año, por ejemplo cada mes con ventana creciente, se decidirá con LightGBM.
- En los cambios de horario, el retardo de 24 horas cae una hora antes o después en el reloj. Afecta a pocos orígenes de cada pliegue, los que tienen un cambio de horario en su horizonte o en la semana anterior, y se acepta porque el efecto es despreciable (introducción de la sección 4).

## 3. Métricas

Las métricas se calculan **para cada hogar** y se resumen después entre los 300 hogares. Los niveles de consumo varían casi 6 veces de un hogar a otro (sección 2.1): un error en kWh con todos los hogares juntos estaría dominado por los que más consumen.

| Métrica | Definición en cada hogar | Para qué |
|---|---|---|
| MASE | MAE del modelo dividido por la escala del hogar. La escala es el MAE de la persistencia de 24 horas (copiar la hora de 24 horas antes) en todas las horas del periodo de ajuste | Métrica principal. Hace comparables los hogares |
| MAE | Error absoluto medio en kWh | Lectura física del error |
| Sesgo | (Σ predicción − Σ real) / Σ real, en %. Positivo si el modelo sobrestima | Un sesgo negativo da más autonomía de la real |
| Error de la energía diaria | Para cada origen y día *k*, la energía pronosticada del día menos la real, dividida por la energía diaria media del hogar en el periodo de ajuste. Se dan el error absoluto medio y el sesgo | La batería suma horas: lo que importa es la energía acumulada |
| Sesgo nocturno | El sesgo en las horas de 18:00 a 06:00 hora local | Son las horas que cubre la batería sin sol |

- **Resumen entre hogares.** El resumen principal es la **mediana** de los 300 hogares, que no se deja arrastrar por los pocos con periodos atípicos (sección 2.5). Se informa también la media, que sí recoge los hogares con más error.
- **Escala del MASE.** Se usa la persistencia de 24 horas y no la de 168: tiene menos error (0,508 del consumo medio frente a 0,545, sección 4.2), así que es una escala más exigente.
- **Desglose.** Cada métrica se calcula para cada paso *h*, para cada día de horizonte *k* y para cada segmento de la sección 5. El sesgo se da además por hora local.
- **Sin MAPE.** En el 10 % de los hogares más del 13 % de las horas está por debajo de 0,1 kWh, y en dos, más de la mitad (sección 1.2). Ahí el error porcentual se dispara.

### El umbral de las referencias

El umbral se da para cada día de horizonte *k* con dos referencias del pliegue de validación. Las cifras completas están en `notebooks/baselines.ipynb` (sección 5) y en `data/results/umbral_validacion_horario.parquet`.

- **Umbral principal: la media de 7 días**, la mejor referencia sin sesgo. Un modelo aporta en el día *k* si su MASE es menor que el de la media de 7 días y su sesgo y su error de energía diaria no son peores.
- **Referencia del MAE: la mediana de 7 días.** Tiene menos MASE, pero subestima el consumo un 11,8 %, porque predice la mediana (pregunta 3). Superarla en MASE no basta si es a costa del sesgo.

| Día de horizonte | 1 | 2 | 7 | 14 |
|---|---|---|---|---|
| MASE de la media de 7 días | 0,81 | 0,82 | 0,87 | 0,90 |
| Error de la energía diaria de la media de 7 días | 18,4 % | 19,2 % | 21,2 % | 22,8 % |
| MASE de la mediana de 7 días | 0,76 | 0,78 | 0,82 | 0,84 |

El sesgo de la media de 7 días es prácticamente nulo: menos de un 0,2 % en todos los días. Son cifras de validación. Las de test se calcularán una sola vez, con el primer LightGBM.

## 4. Qué horas se evalúan

- **Hueco del hogar 2.** Le faltan los días del 12 de octubre al 31 de diciembre de 2012 (G14). Un par hogar-origen se evalúa solo si los 28 días anteriores al origen y los 14 del horizonte están completos. Veintiocho días es la historia más larga que se prevé usar (la normalización de la pregunta 5), así que todos los modelos se evalúan sobre las mismas horas. Quedan fuera 122 orígenes del hogar 2 en test, del 29 de septiembre de 2012 al 28 de enero de 2013. En validación no se excluye nada.
- **`CL` estimado.** Hay 570 días completos (13.680 horas) de 10 hogares, entre el 26 de enero y el 31 de marzo de 2013, en los que el `CL` se copió del año anterior. Esas horas no se usan como valor real al medir el error, ni sus días en el error de energía diaria. Sí se pueden usar como historia para pronosticar, como indica `notebooks/final_dataset.ipynb`.
- **Casas vacías.** Se evalúan como cualquier otro día: un sistema real también tendrá periodos de casa vacía. Se informan además como segmento (sección 5).

## 5. Segmentos

Cada hora se asigna a un segmento según el día local en que cae.

| Segmento | Definición | Por qué |
|---|---|---|
| Tipo de día | Laborable, sábado, domingo o festivo | Los fines de semana y los festivos tienen otra forma y más error (secciones 3.1 y 4.2) |
| Estación | Verano (diciembre a febrero), otoño, invierno y primavera | El perfil cambia mucho con la estación (sección 3.3) |
| Navidad | Del 23 de diciembre al 6 de enero | Los laborables se parecen a un fin de semana (sección 3.2) |
| Calor | Días con máxima de ERA5 de 30 °C o más | Son los días de más consumo y los menos representados: 38 en los dos años de entrenamiento (sección 5.1). El test incluye 44,8 °C, por encima del máximo de entrenamiento |
| Casa vacía | Días marcados con el criterio de la sección 6 | Comportamiento que el modelo no puede anticipar (sección 2.5) |

## 6. Calendario y marcas

Estas reglas se implementarán en un solo módulo, que usarán el entrenamiento, la evaluación y el año de test.

- **Hora local.** Hora local en que **empieza** cada intervalo: `timestamp_utc` menos una hora, pasado a `Australia/Sydney` (sección 0.2).
- **Hora estándar.** La misma hora de inicio en UTC+10 todo el año, sin horario de verano. En casi la mitad de los hogares con carga controlada, el temporizador del `CL` sigue esta hora y no la local (sección 4.5, pregunta 4).
- **Festivos.** Los de Nueva Gales del Sur según la librería `holidays`, con dos cambios:
  - se añade el 28 de diciembre de 2010, festivo por proclamación que la librería no incluye (sección 0.3);
  - se quita el *Bank Holiday* del 2 de agosto de 2010, que se consume como un laborable (sección 3.2). La librería no lo incluye en los años siguientes.

  Para el año de test, la librería da 11 festivos entre julio de 2012 y junio de 2013, incluido el traslado de *Australia Day* al lunes 28 de enero de 2013. Navidad no cae en fin de semana, como en 2010, así que no hace falta añadir ningún día.
- **Día de la semana.** Se usan los siete días y no dos tipos de día, para que sábado y domingo queden separados (sección 3.1).
- **Navidad.** Una marca del 23 de diciembre al 6 de enero (sección 3.2).
- **Vacaciones escolares.** No se añaden. No se han podido comprobar las fechas de 2010 a 2013 (sección 3.2), y su efecto puede recogerlo el consumo de los días anteriores.
- **Casa vacía.** Para cada hogar y día local, la *hora típica* es la mediana de sus horas de `GC`, y la *habitual* del hogar es la mediana de la hora típica en 2010-2012. Un día se marca si su hora típica es menor que el 30 % de la habitual y forma parte de una racha de al menos 3 días seguidos así. En los dos años de entrenamiento marca 2.680 días de 85 hogares (sección 2.5). Las dos medianas solo usan los años de entrenamiento, también para marcar el año de test. La marca se calcula después de conocer el consumo, así que sirve para evaluar y, como mucho, para probar a quitar esos días del entrenamiento. **Nunca es una variable de entrada.**

## 7. Modelos de referencia

Las referencias no se entrenan: cada pronóstico sale del consumo anterior al origen o de la climatología del periodo de ajuste. *y*(*t*) es el consumo de la hora que termina en *t*, y los retardos se cuentan en horas reales.

| Referencia | Pronóstico para la hora *t0* + *h* | Papel |
|---|---|---|
| Persistencia de 24 h | *y*(*t0* + *h* − 24·⌈*h*/24⌉): la misma hora del último día observado | Persistencia estacional del Plan |
| Persistencia de 168 h | *y*(*t0* + *h* − 168·⌈*h*/168⌉): la misma hora y el mismo día de la última semana observada | Complementaria. Los lunes acierta más que la de 24 horas (sección 4.2) |
| Media de 7 días | Media de la misma hora en los 7 días anteriores al origen | Media estacional del Plan. Acierta más que las dos persistencias en 292 hogares (sección 4.2) |
| Mediana de 7 días | La misma, con la mediana | Mide cuánto sesgo introduce predecir la mediana (pregunta 3) |
| Climatología del hogar | Media del hogar en el periodo de ajuste para la misma estación, tipo de día y hora local. El tipo de día es laborable o no laborable: sábado, domingo, festivo o laborable de Navidad | Hacia ella converge cualquier modelo en los horizontes largos |

Todas predicen `demand_kwh`. Como son lineales, predecir `GC` y `CL` por separado y sumarlos daría el mismo resultado. Las referencias para semanas y meses están en la sección 8.

Como comprobación, en el día 1 la persistencia de 24 horas debería dar un error relativo cercano a 0,50 del consumo medio, y la media de 7 días, cercano a 0,44. Son las cifras de la sección 4.2 con los dos años juntos, así que en validación pueden variar algo.

## 8. Semanas y meses

A partir de unas dos semanas, el pronóstico deja de referirse a horas concretas y pasa a describir la energía de un periodo (estado del arte, sección 3.6). Para semanas y meses se pronostica la energía de un **bloque** de días seguidos:

- **Bloques.** La semana tiene 7 días y el mes, 28. Con cuatro semanas, cada bloque tiene los mismos días de la semana, y se puede comparar con el año anterior tomado 364 días antes.
- **Antelación.** Días entre el origen y el inicio del bloque: 0, 7, 14, 28, 56, 91, 182 y 273. Cada bloque del año evaluado se pronostica con todas las antelaciones, así que todas se miden sobre los mismos bloques.
- **Error.** En % de la energía media de un bloque del hogar en el periodo de ajuste, resumido con la mediana entre hogares, junto con el sesgo. Los bloques con algún día de `CL` estimado no se evalúan, aunque esos días sí sirven como historia.

Hay dos referencias (`src/models/energy_baselines.py`):

| Referencia | Pronóstico |
|---|---|
| Reciente | La energía diaria media de los 7 días anteriores al origen, por la longitud del bloque |
| Año anterior | La energía del mismo bloque 364 días antes. No depende de la antelación |

El umbral de cada antelación es el error de la mejor de las dos en validación (`data/results/umbral_validacion_bloques.parquet`):

| Antelación (días) | 0 | 14 | 28 | 56 o más |
|---|---|---|---|---|
| Semana | 13,5 % (reciente) | 17,9 % (reciente) | 20,7 % (reciente) | 23,1 % (año anterior) |
| Mes | 13,7 % (reciente) | 17,5 % (reciente) | 17,8 % (año anterior) | 17,8 % (año anterior) |

El año anterior tiene un sesgo de +6 %, porque en 2011-2012 se consumió algo menos que en 2010-2011. El modelo de periodos corresponde al paso 5 del Plan. A estos plazos la respuesta no son horas concretas, sino la energía esperada y su distribución, que la simulación convierte en horas de suministro por día y en probabilidad de agotamiento (G10).

## 9. Respuestas a las preguntas abiertas

| # | Pregunta | Decisión | Estado |
|---|---|---|---|
| 1 | Métricas | MASE por hogar, escalado con la persistencia de 24 horas, más MAE, sesgo y error de la energía diaria. Mediana entre hogares. Sin MAPE (sección 3) | Decidida |
| 2 | Transformación `log1p` | Primero sin transformar. `log1p` se prueba como variante, vigilando el sesgo, porque al deshacerla el modelo tiende a predecir la mediana | Propuesta para LightGBM |
| 3 | Función de pérdida | El sesgo y el error de energía diaria son obligatorios. La mediana de 7 días confirma el riesgo: tiene menos MASE que la media de 7 días, pero subestima el consumo un 11,8 %. Para LightGBM se empieza con L2, que predice la media, y se compara con Tweedie y L1 | Decidida para las referencias; propuesta para LightGBM |
| 4 | Carga controlada | Se predice `demand_kwh`. LightGBM recibirá la hora estándar además de la local. Predecir `GC` y `CL` por separado queda como experimento si aparece sesgo en las horas del `CL` | Decidida para las referencias; propuesta para LightGBM |
| 5 | Diferencias entre hogares | Las referencias son por hogar. Para LightGBM, un modelo global para los 300 hogares, con el objetivo dividido por la media del hogar en los 28 días anteriores al origen | Propuesta para LightGBM |
| 6 | Periodos atípicos | Se marcan las casas vacías con el criterio de la sección 6 y se evalúan como segmento. No se quitan de la métrica principal. El hogar 146 se queda | Decidida |
| 7 | Calendario | Sin *Bank Holiday*, con marca de Navidad, con los siete días de la semana y sin vacaciones escolares (sección 6) | Decidida |
| 8 | Referencias | Persistencia estacional: la de 24 horas. Media estacional: la media de 7 días. Además, la persistencia de 168 horas, la mediana de 7 días y la climatología (sección 7) | Decidida |
| 9 | Retardos y horizontes | Origen diario a las 00:00 y modelo horario hasta 14 días (sección 1). Las semanas y los meses se responden con la energía de bloques de 7 y 28 días (sección 8). Los retardos de LightGBM se eligen al entrenarlo. Con el origen a medianoche, las últimas horas antes del origen solo sirven para el principio del horizonte, y la información está sobre todo en la misma hora de los días anteriores (sección 4.1) | Decidida; los retardos, con LightGBM |
| 10 | Variables meteorológicas | Temperatura de la hora, media y máxima del día, y grados por debajo de 17 °C y por encima de 23 °C (sección 5.1). La humedad, que no aporta en Sídney (sección 5.5), queda fuera de la primera versión y se prueba como variante | Propuesta para LightGBM |
| 11 | Días de calor | Se evalúan como segmento aparte (sección 5). Cómo tratar en LightGBM las temperaturas por encima de las de entrenamiento se decide al entrenarlo | Segmento decidido; tratamiento, con LightGBM |
