# Carencias de los datos y cómo se tratan — tarea 1

Diferencias entre lo que necesita el proyecto y lo que ofrecen los conjuntos de datos elegidos. De cada carencia se indica qué falta, cómo se trata y qué magnitud se espera. Las carencias estructurales son propias del problema (los datos nunca van a contener una batería). Las limitaciones están documentadas y se aceptan. Las carencias de preprocesamiento deben resolverse antes de entrenar cualquier modelo.

## Resumen

| # | Carencia | Tipo | Magnitud |
|---|---|---|---|
| G1 | Los datos no incluyen batería | Simulación (tarea 3) | Estructural |
| G2 | Censura por agotamiento de la batería | Simulación (tarea 3) | Estructural |
| G3 | Referencia del potencial FV | Interpretación | Pequeña |
| G4 | Consumo propio del inversor | Simulación (tarea 3) | ~5–10 % de la energía diaria |
| G5 | Ausgrid no codifica el horario de verano | Preprocesamiento | Desfase de 1 h, ~6 meses al año |
| G6 | La columna `0:00` pertenece al día siguiente | Preprocesamiento | Desplazamiento de 30 min si se trata mal |
| G7 | El formato de fecha cambia según el archivo | Preprocesamiento | Error de lectura si se ignora |
| G8 | Clima no tropical (NSW) | Limitación | Cualitativa |
| G9 | No hay pronóstico meteorológico histórico de 2010–2013 | Metodología | Subestima el error del pronóstico |
| G10 | Escenarios para horizontes de semanas y meses | Metodología | Estructural |
| G11 | Coherencia entre demanda y FV en Monte Carlo | Metodología | Subestima P(déficit) |
| G12 | Un solo punto meteorológico para todos los clientes | Supuesto | Pequeña a escala horaria |
| G13 | Tratamiento de la carga controlada (`CL`) | Preprocesamiento | 10–15 % de la demanda si se descarta |
| G14 | 81 días de cliente ausentes en 2012-2013 | Datos | 0,07 % de ese año |

## Lo que *no* es una carencia

Comprobado durante la selección de los datos, **a nivel de celda**: no hay valores ausentes dentro de ninguna fila, ni valores negativos, ni filas `NA` en `Row Quality`, ni valores atípicos preocupantes, ni censura en los datos de demanda (los clientes están conectados a la red, así que la demanda es latente y se observa completa).

Hay una excepción **a nivel de fila**: 81 pares `(cliente, día)` faltan por completo en el archivo de 2012-2013 (véase G14). No son «valores ausentes» dentro de las filas, sino filas enteras que no aparecen. Afecta al 0,07 % de ese año y no requiere imputación.

El conjunto de datos es inusualmente limpio. Las carencias siguientes se refieren a lo que no contiene, no a la calidad de los datos.

---

## G1 — Los datos no incluyen batería

Ausgrid no tiene batería, estado de carga (SOC), potencia de carga y descarga, profundidad de descarga (DoD) ni eficiencia de ida y vuelta (*round-trip*). La batería se simula a partir de un SOC inicial y una capacidad, integrando el balance energético con la demanda **pronosticada** (salida del modelo de demanda, tarea 2) y la FV **pronosticada** (salida de pvlib, tarea 3) como entradas. Los parámetros (eficiencias, *C-rate*, DoD, capacidad) son parámetros de escenario, no se ajustan con los datos, y se varían en el Monte Carlo.

**Importante:** esto es un **paso de modelado (tarea 3), no preparación de datos de la tarea 1.** La tarea 1 entrega datos limpios y verificados; la simulación de la batería necesita los pronósticos de las tareas 2 y 3, que todavía no existen. La carencia se documenta aquí para que el supuesto no se pierda, pero **no se calcula en la tarea 1**.

**Magnitud:** estructural — sin una batería simulada no hay estimación de la autonomía. La sensibilidad a los parámetros de la batería debe darse como un rango.

## G2 — Censura por agotamiento de la batería

En un sistema aislado real, cuando la batería llega a su límite inferior, la carga se desconecta y el consumo registrado cae a cero aunque la demanda continúe. Esto no ocurre en Ausgrid. En los datos de entrenamiento no hay que hacer nada: la demanda es latente y completa, lo que es un punto fuerte del conjunto de datos. En la simulación del sistema aislado (tarea 3), la censura la introduce de forma natural el modelo de batería: cuando `E` llega a `E_min`, la demanda se cuenta como no servida hasta que se recupera la generación.

**Magnitud:** estructural. Debe indicarse en el informe que, en un sistema aislado real, el usuario también puede reducir la demanda cuando la batería está baja, algo que no se puede reproducir con datos de red. Es una limitación conocida y no se corrige.

## G3 — Referencia del potencial FV

La `GG` (generación bruta) de Ausgrid se mide con un contador bruto que registra toda la producción FV con independencia de la carga. Como el sistema está conectado a la red y el excedente se exporta, no hay recorte por batería llena, así que `GG` está muy cerca de la generación potencial. `GG` se usa como referencia para validar pvlib en días despejados. En la simulación del sistema aislado, la entrada FV es la salida de pvlib; el modelo de batería decide cuánta se usa realmente.

**Magnitud:** pequeña (recorte del inversor, suciedad, errores de medida). Debe cuantificarse en días despejados.

## G4 — Consumo propio del inversor

Los inversores reales consumen 20–50 W de forma continua mientras están encendidos. Esa energía sale de la batería por la noche y no aparece en los datos de consumo de Ausgrid. Se añade a la demanda simulada un consumo constante del inversor (30 W por defecto). Es un parámetro de escenario que se varía en el Monte Carlo.

**Magnitud:** 0,5–1,5 kWh/día, un 5–15 % del consumo diario típico de Ausgrid. Es relevante para la autonomía diaria; debe incluirse.

## G5 — Ausgrid no codifica el horario de verano

Cada día está codificado como 48 medias horas nominales, sin importar las 46 o 50 que hay en realidad en los cambios de horario. Comprobado: las 48 columnas tienen el mismo número de valores no nulos, y los días de cambio tienen 48 valores no nulos. El UTC se reconstruye a partir de la fecha y las reglas de `Australia/Sydney`. En los dos días de cambio hay una ambigüedad de 30 min; se recomienda eliminar la hora duplicada al terminar el horario de verano, interpolar la hora que falta al empezar y documentar la decisión.

**Magnitud:** si no se trata, hay un desfase sistemático de 1 h con ERA5 / Open-Meteo durante ~6 meses al año. Estropea la posición solar de pvlib, los retardos y la unión de la demanda con el clima. Debe tratarse.

## G6 — La columna `0:00` pertenece al día siguiente

La última columna de media hora (`0:00`) representa el intervalo de 23:30 a 0:00 del día siguiente, no del mismo día. Al pasar de formato ancho a largo hay que asignarle la marca `fecha + 1 día, 00:00 hora local`.

**Magnitud:** si se trata mal, queda un hueco de 30 min y un solapamiento de 30 min en cada cambio de día. Estropea la agregación por horas, los retardos y el remuestreo. Debe tratarse.

## G7 — El formato de fecha cambia según el archivo

`ausgrid_2010_2011.csv` usa `%d-%b-%y`; los otros dos usan `%d/%m/%Y`. Cada archivo debe leerse con su propio formato, o bien usar `errors='coerce'` y comprobar que no queda ningún NaT. No debe suponerse que un mismo formato sirve para todos.

**Magnitud:** si se trata mal, 100 % de NaT en dos de los tres archivos. Debe tratarse.

## G8 — Clima no tropical (NSW)

Ausgrid cubre un clima templado. El encargo del proyecto no depende del clima («capacidad FV + datos meteorológicos → cuánto dura»), pero el contexto del equipo menciona Cuba como lugar de despliegue previsto. El rendimiento del modelo de demanda en condiciones tropicales se desconoce y no se afirma nada sobre él. El marco de simulación FV + batería es transferible; las cifras de autonomía son específicas de NSW.

**Magnitud:** cualitativa — afecta a la validez externa, no a la interna. Se documenta en el informe final. El encargo no exige otro conjunto de datos; si más adelante se pide una validación tropical, la única vía honesta es un conjunto tropical real, no uno sintético derivado de Ausgrid.

## G9 — No hay pronóstico meteorológico histórico de 2010–2013

La Historical Forecast API de Open-Meteo empieza en ~2022; para el periodo de Ausgrid solo está disponible ERA5 (reanálisis). Opciones, por orden de preferencia:

1. **ERA5 como «pronóstico perfecto».** La más simple; el error de autonomía que se obtiene es una **cota inferior** del error real.
2. **ERA5 + perturbación calibrada.** La distribución de la perturbación se ajusta al error típico de un pronóstico operativo a 24–72 h. Más realista.
3. **Dar las dos**, (1) y (2); la diferencia cuantifica qué parte del error de autonomía se debe a la imperfección del pronóstico. Recomendada.

**Magnitud:** la evaluación retrospectiva (*backtest*) con «pronóstico perfecto» subestima el error real.

## G10 — Escenarios para horizontes de semanas y meses

Los pronósticos no tienen capacidad predictiva útil más allá de ~15 días; para horizontes más largos solo se dispone de la climatología. Los escenarios se generan a partir de la climatología (días análogos en bloques de varios días, o cadenas de Markov de tipos de día según el índice de claridad). La respuesta para estos horizontes es un agregado (horas diarias de suministro esperadas, días esperados con algún corte, probabilidad de al menos un agotamiento), no un pronóstico de horas concretas.

**Magnitud:** estructural — la respuesta cambia de naturaleza, no solo de precisión.

## G11 — Coherencia entre demanda y FV en Monte Carlo

Muestrear la demanda y la FV de forma independiente rompe su correlación: mezcla FV de cielo despejado con demanda de día nublado y distorsiona las probabilidades de déficit. Dos mecanismos: (i) los miembros del ensemble de Open-Meteo para horizontes ≤ 15 días, cada uno con una trayectoria coherente de temperatura, irradiancia, nubosidad y viento que alimenta tanto al modelo de demanda como a pvlib; (ii) bootstrap por bloques de los residuos de la demanda, en bloques de 24 h y no hora a hora, para conservar la autocorrelación. Si los residuos se muestrean hora a hora, se compensan dentro de cada noche y se subestima la dispersión de la autonomía.

**Magnitud:** si no se trata, se subestima la probabilidad de un déficit prolongado. El bootstrap por bloques es el tratamiento mínimo aceptable.

## G12 — Un solo punto meteorológico para todos los clientes

Los 300 clientes comparten un mismo punto de la malla de ERA5 (centro de Sídney, *Sydney CBD*). Los códigos postales abarcan ~150 km, que a la resolución de ERA5 son unas pocas celdas. Se acepta como supuesto: a resolución horaria, la variación entre lugares cercanos de NSW es pequeña comparada con la variación de un día a otro en un mismo lugar. Usar el clima de cada código postal multiplicaría los datos por ~100 sin una mejora clara. Se revisará si hace falta simular por código postal.

**Magnitud:** pequeña, mucho menor que el error debido a la falta del pronóstico operativo (G9) o de los parámetros de la batería (G1).

## G13 — Tratamiento de la carga controlada (`CL`)

Ausgrid tiene tres categorías: `GC` (consumo general), `CL` (carga controlada, calentamiento de agua en horario valle, ~46 % de los días de cliente) y `GG` (generación bruta). `CL` es demanda real medida con un contador aparte y con un patrón temporal propio. Dos opciones:

1. **Incluir `CL` en la demanda total** (`GC + CL`). Recomendada: el consumo total es lo que debe cubrir un sistema aislado.
2. **Modelar `GC` y `CL` por separado.** Más preciso, pero duplica el trabajo de modelado. Se retomará en la tarea 2 si el EDA muestra un patrón de `CL` muy diferenciado y predecible.

**Magnitud:** si se descarta `CL`, la demanda se subestima un 10–15 % en los días afectados, y ese error se propaga directamente a la autonomía.

## G14 — 81 días de cliente ausentes en 2012-2013

El archivo de 2012-2013 contiene 109.419 filas de `GC` y 109.419 filas de `GG`, frente a las 109.500 esperadas (= 300 clientes × 365 días). Los archivos de 2010-2011 y 2011-2012 tienen exactamente las filas esperadas (109.500 y 109.800 respectivamente; el segundo tiene más porque 2012 es bisiesto). Esto significa que **81 pares `(cliente, día)` faltan por completo** en el archivo de 2012-2013: no hay fila de `GC` ni fila de `GG` y, por tanto, tampoco fila de `CL` para esos pares.

No son «valores ausentes» dentro de una fila (de esos no hay ninguno en todo el conjunto); son filas enteras que no aparecen en el archivo.

**Cómo se trata.** Esos pares se **descartan**, no se imputan. 81 de 109.500 es el 0,07 % del año; imputarlos sería inventar datos sin justificación y sesgaría cualquier métrica calculada sobre los días de cliente afectados. Al pasar de formato ancho a largo, esos pares simplemente no generan filas; el modelo debe tolerar los huecos que quedan en la serie temporal de cada cliente (por ejemplo, al calcular los retardos, saltarse las marcas de tiempo ausentes en lugar de propagar valores).

**Magnitud:** 0,07 % de un año en un archivo. Sin efecto apreciable en el entrenamiento del modelo ni en la estimación de la autonomía. Debe documentarse para que quien transforme los datos no confunda la ausencia con un error de lectura.

**Interacción con otras carencias:** G14 no interactúa con G5 (horario de verano) ni con G6 (`0:00`); es una ausencia independiente, a nivel de fila. Aparece al final porque se descubrió después de la verificación principal.

---

## Notas transversales

- **G5 (reconstrucción del horario de verano)** es, con diferencia, la fuente más probable de errores sutiles. Debe probarse en los dos días de cambio antes de que ningún modelo use los datos transformados; se recomienda un test de regresión que compruebe el número esperado de medias horas por año.
- **G6 (nueva marca de `0:00`)** y **G5 (horario de verano)** interactúan: la nueva marca debe asignarse antes de la conversión a UTC; si no, el límite del día queda desplazado 30 min dos veces al año.
- **G13 (inclusión de `CL`)** debe decidirse antes del EDA; si no, la referencia (*baseline*) se calcula sobre la serie de demanda equivocada.
- **G14 (81 días de cliente ausentes)** debe tratarse al pasar de formato ancho a largo, no al imputar. No deben rellenarse.
- **G1–G4 son pasos de modelado de la tarea 3**, no preparación de datos de la tarea 1. La tarea 1 termina con datos limpios y verificados; la simulación de la batería empieza cuando existen los pronósticos de demanda y de FV.
- La serie de demanda es latente y completa a nivel de celda; **no hace falta imputar** en ningún momento. G14 es una ausencia de filas enteras, no un valor ausente.
