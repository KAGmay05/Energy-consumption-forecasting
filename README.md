# Energy-consumption-forecasting

Machine learning project for predicting energy carrier consumption and estimating energy autonomy duration using photovoltaic capacity and meteorological data.

## Cómo preparar los datos

Los datos no se suben al repositorio. Hay que descargarlos y ejecutar los scripts de preprocesamiento, que generan el conjunto final en `data/processed/`.

### 1. Instalar las dependencias

```
pip install -r requirements.txt
```

Para abrir los notebooks también hace falta Jupyter (`pip install jupyter`).

### 2. Descargar los datos originales

**Ausgrid (consumo y generación fotovoltaica).** Descargar el archivo compartido del equipo:
https://drive.google.com/file/d/1uF5bdWaEl-Q6VyxT9G-PVJkpbHZQEEcx/view?usp=sharing

También se puede obtener del espejo original, https://pierreh.eu/downloads/Ausgrid_solar_home_data.zip, renombrando los CSV como se indica en `docs/data/MANIFEST.md`. Los tres archivos van en `data/raw/`:

```
data/raw/ausgrid_2010_2011.csv
data/raw/ausgrid_2011_2012.csv
data/raw/ausgrid_2012_2013.csv
```

**ERA5 (clima de Sídney).** Descargar el archivo compartido del equipo:
https://drive.google.com/file/d/1Qde4yv6pQ_0q-lKonvf8FKOLE9zpr0bd/view?usp=sharing

y colocarlo en `data/weather/era5_sydney_2010_2013.parquet`. Este archivo es una versión congelada: no conviene volver a generarlo con `scripts/00_download_weather.py`, porque Open-Meteo puede devolver valores algo distintos y la huella dejaría de coincidir.

Los scripts comprueban la huella SHA-256 de cada archivo con la registrada en `docs/data/MANIFEST.md` y se detienen si no coincide.

### 3. Ejecutar el preprocesamiento

Desde la raíz del proyecto y en este orden:

```
python -m src.preprocessing.weather
python -m src.preprocessing.ausgrid
python -m src.preprocessing.merge
```

**`weather.py`** valida ERA5, pasa el viento a m/s y lo recorta al período de Ausgrid.
- Lee: `data/weather/era5_sydney_2010_2013.parquet`
- Genera: `data/processed/era5_processed.parquet`

**`ausgrid.py`** une los tres años, convierte las fechas, resuelve el horario de verano, pasa a horas UTC, calcula el consumo total y añade las marcas de calidad.
- Lee: `data/raw/ausgrid_2010_2011.csv`, `ausgrid_2011_2012.csv` y `ausgrid_2012_2013.csv`
- Genera: `data/processed/ausgrid_processed.parquet`

**`merge.py`** une Ausgrid con ERA5 por hora UTC.
- Lee: los dos archivos anteriores
- Genera: `data/processed/ausgrid_era5_joined.parquet`

El proceso completo tarda alrededor de un minuto. **El archivo que se usa para los modelos es `ausgrid_era5_joined.parquet`**: una fila por hogar y hora, con el consumo, la generación, las marcas de calidad y el clima. Los otros dos son pasos intermedios.

### 4. Documentación de los datos

| Notebook | Contenido |
|---|---|
| `notebooks/weather_exploration.ipynb` | Revisión de ERA5 y justificación de los cambios de `weather.py` |
| `notebooks/ausgrid_exploration.ipynb` | Revisión de Ausgrid y justificación de los cambios de `ausgrid.py` |
| `notebooks/final_dataset.ipynb` | Descripción del conjunto final: filas, columnas, marcas de calidad y notas de uso |
| `notebooks/forecasting_eda.ipynb` | Análisis exploratorio para el pronóstico de la demanda (solo 2010-2011 y 2011-2012; 2012-2013 se reserva para el test): calendario, distribución del consumo, diferencias entre hogares, estacionalidades, dependencia temporal y relación con el clima |

`docs/data/` contiene el origen de cada archivo (`MANIFEST.md`) y las limitaciones conocidas de los datos (`gaps.md`).
