# Inventario de conjuntos de datos candidatos

## Candidato 1 — Ausgrid Solar Home Electricity Data

| Campo | Valor |
|---|---|
| Institución | Ausgrid (distribuidora eléctrica de NSW, Australia) |
| País | Australia (NSW) |
| Periodo | 2010-07-01 a 2013-06-30 (3 años) |
| Resolución | 30 min (48 columnas de media hora por fila) |
| Número de instalaciones | 300 |
| Consumo disponible | sí — `GC` (general) + `CL` (carga controlada, ~46 % de los días de cliente) |
| FV medida por instalación | sí — `GG` (generación medida con contador bruto) |
| Capacidad FV instalada disponible | sí — `Generator Capacity` en kWp (media 1,67, mediana 1,50, rango 1,0–9,99) |
| Ubicación disponible | sí — `Postcode` (100 códigos postales distintos, NSW) |
| Licencia | CC-BY 3.0 Australia (verificada en el README del espejo, originalmente Ausgrid 2014) |
| Acceso | descarga abierta desde el espejo (la página original de Ausgrid ya no está en línea; metadatos en data.gov.au) |
| Formato | CSV (ancho: 5 columnas descriptivas + 48 de media hora + `Row Quality` en 2 de los 3 archivos) |
| Tamaño | ~55 MB comprimido; ~270 mil filas por archivo, ~808 mil filas en total |
| URL oficial | original: ausgrid.com.au (fuera de línea). Metadatos: https://data.gov.au/data/en/dataset/nsw-solar-home-electricty-data. Espejo: https://pierreh.eu/downloads/Ausgrid_solar_home_data.zip |
| Fecha de consulta | 2026-11-10 |
| Notas / discrepancias | véase más abajo |

### Hechos verificados

- 300 clientes, 365/366/365 días por cliente en cada archivo, 48 medias horas por día → 109.500–109.800 filas de GC y de GG por archivo, 49.719–50.735 filas de CL por archivo.
- Cero nulos y cero negativos en las columnas de media hora de los tres archivos.
- `Row Quality`: no existe en 2010-11; existe y vale siempre `BLANK` en 2011-12 y 2012-13. → No hay filas `NA` que imputar.
- Valores de media hora en kWh por 30 min, positivos tanto en consumo como en generación. Rango: de 0,000 a ~7,8 kWh/30 min.
- `Generator Capacity` es coherente entre archivos: media de 1,67 kWp.

### Discrepancias con el PDF oficial

- La cabecera del CSV está en la **línea 2 (índice 1)**, precedida por una línea de título. Hay que usar `skiprows=1`.
- Los nombres de las columnas del CSV no coinciden con los del PDF:
  - PDF: `Customer | Postcode | Generator Capacity | Consumption | Date`
  - CSV: `Customer | Generator Capacity | Postcode | Consumption Category | date`
- El formato de fecha cambia **entre archivos**:
  - 2010-2011: `%d-%b-%y` (p. ej. `1-Jul-10`)
  - 2011-2012: `%d/%m/%Y` (p. ej. `1/07/2011`)
  - 2012-2013: `%d/%m/%Y`
- La columna `0:00` corresponde al intervalo de **23:30 a 0:00 del día siguiente** (peculiaridad de Ausgrid). Al pasar de formato ancho a largo hay que asignarle la marca `fecha + 1 día, 00:00`.
- **El horario de verano no está codificado**: las 48 columnas de media hora tienen el mismo número de valores no nulos (270.304), y los días de cambio de horario (2 de octubre de 2011 y 1 de abril de 2012) tienen 48 valores no nulos, no 46/50. El conjunto trata todos los días como de 24 horas nominales.

### Implicaciones para el proyecto

- **Demanda latente**: clientes conectados a la red → no hay censura por agotamiento de la batería. Es una ventaja para modelar la demanda; la censura se introduce al simular el sistema aislado.
- **Potencial FV**: `GG`, medida con contador bruto, recoge la generación total sin recorte por batería llena → se aproxima bien al potencial FV.
- **Clima**: una sola zona climática (NSW, templada). No valida el contexto tropical que se menciona en el proyecto. Es una limitación documentada.
- **No hay pronóstico histórico de 2010–2013** en Open-Meteo (empieza en ~2022). La evaluación retrospectiva (*backtesting*) de la cadena completa usará ERA5 como «pronóstico perfecto» o con una perturbación calibrada. Véase `gaps.md`.
- **Hace falta reconstruir el horario de verano** antes de unir con el clima, que está en UTC, y de ejecutar pvlib. Véase `gaps.md`.

### Comprobación de una muestra (cliente 1, código postal 2076, 3,78 kWp)

- 1 de julio de 2010: perfil de GC típico de un hogar en invierno (pico por la tarde), GG nula hasta ~13:00, pico de ~1,18 kWh/30 min hacia el mediodía. Coherente con un sistema de 3,78 kWp orientado al norte en el invierno de Sídney.
