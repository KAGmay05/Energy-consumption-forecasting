# Energy-consumption-forecasting

Proyecto de aprendizaje automático para predecir el consumo de portadores energéticos y estimar cuánto dura la autonomía energética a partir de la capacidad fotovoltaica y los datos meteorológicos.

**Estado (noviembre de 2026).** Los datos están preparados y los modelos de referencia, evaluados en validación. Lo siguiente es LightGBM (paso 2 del [Plan](Plan.md#5-orden-de-implementación)). Las cifras están en [resultados.md](docs/modelado/resultados.md).

- [Mapa del proyecto](#mapa-del-proyecto)
- [Cómo preparar los datos](#cómo-preparar-los-datos)
- [Cómo se evalúan los modelos](#cómo-se-evalúan-los-modelos)

## Mapa del proyecto

### Si es tu primera vez

1. Leer el [Plan](Plan.md): qué se va a hacer y en qué orden.
2. [Preparar los datos](#cómo-preparar-los-datos).
3. Ver con qué datos se trabaja, en [final_dataset.ipynb](notebooks/final_dataset.ipynb).
4. Leer las reglas comunes de los modelos, en [decisiones.md](docs/modelado/decisiones.md).
5. Mirar qué hay que superar, en [resultados.md](docs/modelado/resultados.md).

### Dónde está cada cosa

| Si buscas... | Está en |
|---|---|
| Qué modelos se harán y en qué orden | [Plan.md](Plan.md) |
| Por qué se eligieron esos métodos, según la literatura | [estado_del_arte.md](estado_del_arte.md) |
| De dónde sale cada archivo de datos, su huella, sus columnas y su licencia | [docs/data/MANIFEST.md](docs/data/MANIFEST.md) |
| La ficha de Ausgrid y lo que se verificó al elegirlo | [docs/data/inventory.md](docs/data/inventory.md) |
| Qué les falta a los datos y cómo se trata (G1 a G14) | [docs/data/gaps.md](docs/data/gaps.md) |
| Cómo se miden los modelos y qué se ha decidido sobre ellos | [docs/modelado/decisiones.md](docs/modelado/decisiones.md) |
| Qué error tiene cada modelo y cuál hay que superar | [docs/modelado/resultados.md](docs/modelado/resultados.md) |

### Los cuadernos, en orden de lectura

| | Cuaderno | Contenido |
|---|---|---|
| Datos | [weather_exploration.ipynb](notebooks/weather_exploration.ipynb) | Revisión de ERA5 y justificación de los cambios de `weather.py` |
| Datos | [ausgrid_exploration.ipynb](notebooks/ausgrid_exploration.ipynb) | Revisión de Ausgrid y justificación de los cambios de `ausgrid.py` |
| Datos | [final_dataset.ipynb](notebooks/final_dataset.ipynb) | Descripción del conjunto final: filas, columnas, marcas de calidad y notas de uso |
| Modelado | [forecasting_eda.ipynb](notebooks/forecasting_eda.ipynb) | Análisis exploratorio para el pronóstico de la demanda (solo 2010-2011 y 2011-2012; 2012-2013 se reserva para el test): calendario, distribución del consumo, diferencias entre hogares, estacionalidades, dependencia temporal y relación con el clima. Sus preguntas abiertas se responden en [decisiones.md](docs/modelado/decisiones.md), sección 9 |
| Modelado | [baselines.ipynb](notebooks/baselines.ipynb) | Modelos de referencia y umbral de medición |

### Las carpetas

```
docs/data/           Documentación de los datos
docs/modelado/       Decisiones y resultados de los modelos
notebooks/           Análisis
src/preprocessing/   Preparación de los datos
src/features/        Calendario y marcas
src/evaluation/      Pliegues, métricas y segmentos
src/models/          Modelos
tests/               Pruebas del código
scripts/             Descarga de ERA5 (00_download_weather.py) y una prueba inicial
                     con Ausgrid que no forma parte del proceso (scratch_ausgrid_sample.py)
data/                Datos y resultados. No se suben a git
```

### Dónde va lo nuevo

| Qué | Dónde |
|---|---|
| Un modelo de consumo | Código en `src/models/`, pruebas en `tests/`, cuaderno `notebooks/modelo_<nombre>.ipynb` y sus cifras en [resultados.md](docs/modelado/resultados.md#3-cómo-añadir-un-modelo) |
| Variables que usan varios modelos | `src/features/` |
| Una decisión que afecta a varios modelos | [decisiones.md](docs/modelado/decisiones.md). Si solo afecta a uno, en su cuaderno |
| La generación FV | `src/generation/`, `notebooks/generacion_<nombre>.ipynb` y `docs/modelado/generacion.md` |
| La batería y Monte Carlo | `src/simulation/`, `notebooks/simulacion_<nombre>.ipynb` y `docs/modelado/simulacion.md` |
| Un archivo de datos | [MANIFEST.md](docs/data/MANIFEST.md) |
| Una carencia de los datos | [gaps.md](docs/data/gaps.md), con el número siguiente (G15, G16...) |

Las carpetas y los documentos que aún no existen se crean al empezar esa parte.

## Cómo preparar los datos

Los datos no se suben al repositorio. Hay que descargarlos y ejecutar los scripts de preprocesamiento, que generan el conjunto final en `data/processed/`.

### 1. Instalar las dependencias

```
pip install -r requirements.txt
```

Para abrir los notebooks también hace falta Jupyter (`pip install jupyter`).

### 2. Descargar los datos originales

**Ausgrid (consumo y generación fotovoltaica).** Descargar `ausgrid.zip`, el archivo compartido del equipo, y extraer los tres CSV:
https://drive.google.com/file/d/1uF5bdWaEl-Q6VyxT9G-PVJkpbHZQEEcx/view?usp=sharing

También se puede obtener del espejo original, https://pierreh.eu/downloads/Ausgrid_solar_home_data.zip, renombrando los CSV como se indica en [MANIFEST.md](docs/data/MANIFEST.md). Los tres archivos van en `data/raw/`:

```
data/raw/ausgrid_2010_2011.csv
data/raw/ausgrid_2011_2012.csv
data/raw/ausgrid_2012_2013.csv
```

**ERA5 (clima de Sídney).** Descargar `weather_task1.zip`, el archivo compartido del equipo:
https://drive.google.com/file/d/1Qde4yv6pQ_0q-lKonvf8FKOLE9zpr0bd/view?usp=sharing

y extraer el parquet en `data/weather/era5_sydney_2010_2013.parquet`. Este archivo es una versión congelada: no conviene volver a generarlo con `scripts/00_download_weather.py`, porque Open-Meteo puede devolver valores algo distintos y la huella dejaría de coincidir.

Los scripts comprueban la huella SHA-256 de cada archivo con la registrada en [MANIFEST.md](docs/data/MANIFEST.md) y se detienen si no coincide.

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

## Cómo se evalúan los modelos

Las reglas de evaluación están en [decisiones.md](docs/modelado/decisiones.md): origen diario a las 00:00 hora local, horizonte de 14 días, pliegues de validación (2011-2012) y test (2012-2013), métricas y segmentos. El código que las aplica:

| Módulo | Contenido |
|---|---|
| `src/features/calendar.py` | Hora local y estándar, festivos de NSW, Navidad, tipo de día y estación |
| `src/features/vacancy.py` | Marca de casa vacía, solo para evaluar |
| `src/evaluation/panel.py` | Matrices hogar × hora a partir de `ausgrid_era5_joined.parquet` |
| `src/evaluation/splits.py` | Pliegues, orígenes, horizonte y horas que se evalúan |
| `src/evaluation/segments.py` | Segmentos: tipo de día, estación, Navidad, calor y casa vacía |
| `src/evaluation/metrics.py` | MASE, MAE, sesgo y error de la energía diaria |
| `src/evaluation/runner.py` | Prepara la evaluación de un pliegue y guarda las tablas |
| `src/models/baselines.py` | Los cinco modelos de referencia horarios |
| `src/models/energy_baselines.py` | Referencias para semanas y meses: energía de bloques de 7 y 28 días |

Las referencias se evalúan en el pliegue de validación con:

```
python -m src.models.baselines
```

Tarda unos minutos y guarda las tablas en `data/results/referencias_validacion_*.parquet`. El cuaderno [baselines.ipynb](notebooks/baselines.ipynb) las lee y fija el **umbral de medición**: el error que tiene que mejorar cada modelo, por día de horizonte hasta 14 días y, para semanas y meses, según la antelación. Las cifras están en [resultados.md](docs/modelado/resultados.md). El test se usa una sola vez por modelo, así que solo se evalúa si se pide de forma explícita: `--fold test --confirmo-test`.

Cualquier otro modelo se evalúa entregando sus pronósticos como una matriz `y_pred` de forma (hogares, orígenes, 337), alineada con el `ForecastGrid` del pliegue:

```python
from src.evaluation.runner import evaluate_forecast, prepare
from src.evaluation.splits import VALIDATION

context = prepare(VALIDATION)  # panel, grid, valores reales, máscara, escalas y segmentos
tables = evaluate_forecast(context, y_pred)
```

`tables` es un diccionario de tablas: por paso, por día de horizonte, por hora, día y noche, energía diaria y por segmento.

Los tests no necesitan los datos. Se ejecutan desde la raíz del proyecto:

```
python -m pytest
```
