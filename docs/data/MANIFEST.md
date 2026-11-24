# Manifiesto de los datos — tarea 1

Todos los conjuntos de datos usados en la tarea 1. Hay dos fuentes: Ausgrid (descargado a mano de un espejo estático) y Open-Meteo ERA5 (descargado con un script). La huella SHA-256 de cada archivo se verifica antes de colocarlo en `data/raw/` o `data/weather/`.

## Dónde están los datos

- CSV de Ausgrid: `data/raw/` (excluida de git con `.gitignore`). Copia compartida: `https://drive.google.com/file/d/1uF5bdWaEl-Q6VyxT9G-PVJkpbHZQEEcx/view?usp=sharing`.
- Parquet de Open-Meteo: `data/weather/` (excluida de git con `.gitignore`). Copia compartida: `https://drive.google.com/file/d/1Qde4yv6pQ_0q-lKonvf8FKOLE9zpr0bd/view?usp=sharing`.

## Nota sobre la reproducibilidad

- **Ausgrid** se descarga **a mano** de un zip del espejo. No hay script de descarga. El zip es un archivo estático; la huella SHA-256 es la garantía de reproducibilidad.
- **Open-Meteo ERA5** se descarga con `scripts/00_download_weather.py`. El archivo parquet está **congelado**; volver a ejecutar el script puede devolver valores algo distintos si Open-Meteo actualiza su servicio de ERA5. El archivo congelado (su SHA-256 está más abajo) es la referencia válida para este proyecto.

---

## Ausgrid — Solar Home Electricity Data

Fuente: https://pierreh.eu/downloads/Ausgrid_solar_home_data.zip

El zip contiene los tres CSV, un PDF con las notas originales de Ausgrid y el README del espejo. En este proyecto solo se usan los tres CSV.

| Nombre canónico | Nombre original en el zip | SHA-256 | Filas | Verificado el |
|---|---|---|---|---|
| `ausgrid_2010_2011.csv` | `Solar home 2010-2011.csv` | `2FC1F615E22FBD8EC350CDB19F7465D3A038453FC2FFD19473EF1BD38FD28289` | 269.735 | 2026-11-10 |
| `ausgrid_2011_2012.csv` | `Solar home 2011-2012.csv` | `A7D6ABD1369311A5566E00D249141FD8AEC28E9FABA0BC928788607D961FC8C8` | 270.304 | 2026-11-10 |
| `ausgrid_2012_2013.csv` | `Solar home 2012-2013.csv` | `E4BE46B3C9991C65735A9545319A2F1C33BE8E639C75A17A88E0323A8E5098BE` | 268.557 | 2026-11-10 |

### Esquema (los tres archivos)

- **Disposición:** formato ancho. Cada fila es una combinación `(cliente, día, categoría de consumo)`.
- **La primera línea de cada archivo es un título**, no la cabecera. La cabecera real está en la **línea 2 (índice 1)**. Se lee con `skiprows=1`, o detectando automáticamente la primera línea que empieza por `Customer`.
- **Columnas descriptivas (5):** `Customer` (1..300), `Generator Capacity` (kWp), `Postcode`, `Consumption Category` (`GC` / `CL` / `GG`), `date`.
- **48 columnas de media hora:** `0:30` … `23:30`, `0:00`. kWh por intervalo de 30 minutos, positivos tanto en consumo como en generación.
- **`Row Quality`:** solo aparece en 2011-2012 y 2012-2013, siempre vacía. No existe en 2010-2011.

### Formatos de fecha (distintos según el archivo)

| Archivo | Formato | Ejemplo |
|---|---|---|
| `ausgrid_2010_2011.csv` | `%d-%b-%y` | `1-Jul-10` |
| `ausgrid_2011_2012.csv` | `%d/%m/%Y` | `1/07/2011` |
| `ausgrid_2012_2013.csv` | `%d/%m/%Y` | `1/07/2012` |

### Unidades y convenciones

- Los valores son **kWh por cada 30 minutos**, no kW. Multiplicados por 2 dan los kW medios.
- Columna `0:00` = intervalo de **23:30 a 0:00 del día siguiente**. Al pasar de formato ancho a largo se le asigna la marca `D + 1 día, 00:00`.
- Zona horaria: hora local de NSW (EST/EDT). **El horario de verano no está codificado**: cada día tiene 48 medias horas nominales, incluidos el 2 de octubre de 2011 y el 1 de abril de 2012. El UTC se reconstruye a partir de la fecha y las reglas de `Australia/Sydney`. Véase `gaps.md`.
- Sin nulos, sin negativos, sin filas `NA`.

### Licencia

CC-BY 3.0 Australia. Publicado originalmente por Ausgrid en 2014; metadatos en https://data.gov.au/data/en/dataset/nsw-solar-home-electricty-data.

### Cómo reproducirlo (Ausgrid)

1. Descargar https://pierreh.eu/downloads/Ausgrid_solar_home_data.zip
2. Extraer y renombrar:
   - `Solar home 2010-2011.csv` → `ausgrid_2010_2011.csv`
   - `Solar home 2011-2012.csv` → `ausgrid_2011_2012.csv`
   - `Solar home 2012-2013.csv` → `ausgrid_2012_2013.csv`
3. Verificar la SHA-256: `Get-FileHash <archivo> -Algorithm SHA256` (Windows) o `sha256sum <archivo>` (Linux/macOS).
4. Colocar los archivos en `data/raw/`.

---

## Clima — Open-Meteo ERA5

| Nombre canónico | SHA-256 | Filas | Periodo |
|---|---|---|---|
| `era5_sydney_2010_2013.parquet` | `63e45ef341654d177c3670d109d54d344e971859fd46b799b1b7bb0133ae0f58` | 26.304 | 2010-07-01 → 2013-06-30 (horario, UTC) |

### Parámetros

| Parámetro | Valor |
|---|---|
| Endpoint | `https://archive-api.open-meteo.com/v1/archive` |
| Latitud | `-33.8688` (centro de Sídney, *Sydney CBD*) |
| Longitud | `151.2093` |
| Inicio / fin | `2010-07-01` / `2013-06-30` |
| Zona horaria | `UTC` |
| Modelo | `era5` (explícito) |
| Variables | `temperature_2m`, `relative_humidity_2m`, `precipitation`, `cloud_cover`, `shortwave_radiation`, `direct_normal_irradiance`, `diffuse_radiation`, `wind_speed_10m`, `surface_pressure` |

### Supuestos

- **Un solo punto meteorológico.** Los 300 clientes de Ausgrid comparten el punto de la malla del centro de Sídney (*Sydney CBD*). Los códigos postales de Ausgrid abarcan ~150 km; a resolución horaria, la variación del clima dentro de la región es pequeña comparada con la variabilidad de un día a otro. Se revisará si hacen falta simulaciones por código postal.
- **Solo ERA5.** La Historical Forecast API no está disponible para 2010–2013 (empieza en ~2022). Las API Forecast y Ensemble no se descargan en la tarea 1; se usarán en la tarea 4 (Monte Carlo). Véase `gaps.md`.
- **Todas las marcas de tiempo en UTC.** No deben convertirse a hora local. La reconstrucción del horario de verano se hace del lado de Ausgrid, y la unión con Ausgrid debe hacerse en UTC.

### Cómo reproducirlo (clima)

1. Descargar `weather_task1.zip` de `https://drive.google.com/file/d/1Qde4yv6pQ_0q-lKonvf8FKOLE9zpr0bd/view?usp=sharing` y extraer `era5_sydney_2010_2013.parquet` en `data/weather/`.
2. Verificar la SHA-256 con `Get-FileHash` o `sha256sum`.
3. O volver a ejecutar `python scripts/00_download_weather.py`. Descargará datos nuevos de Open-Meteo, que **pueden diferir ligeramente** de la versión congelada. El archivo congelado es la fuente de verdad.
