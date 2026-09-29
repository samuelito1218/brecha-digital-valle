# Brecha digital en el Valle del Cauca – Proyecto ETL (Entrega 2)

Universidad Autónoma de Occidente · Curso GyAD · Prof. Juan Manuel Núñez

**Integrantes:** Samuel Arredondo Delgado, Cristian Andrés M. Giraldo, Luis Carlos Lozano Giraldo y Emmanuel Medina Gutiérrez.

## 1. De qué trata el proyecto

Los datos que sirven para medir la brecha digital del Valle del Cauca existen, pero están repartidos entre varias entidades (MinTIC, MEN, ICFES, DANE). Cada una publica con su propia granularidad (estudiante, proveedor, centro poblado, municipio), su propia periodicidad (trimestral, anual, semestral) y su propio formato. Así no es posible comparar los municipios entre sí.

**Objetivo:** construir un pipeline ETL con arquitectura Medallón (Bronze → Silver → Gold) que descargue esas fuentes, las limpie y las integre en tablas por **municipio y año**. Con esas tablas se responden cinco preguntas sobre conectividad y educación, y se arma un índice que indica qué municipios deberían priorizarse.

- **Para quién:** la Gobernación del Valle del Cauca (dependencias de TIC y Planeación), que decide dónde invertir en conectividad. También pueden usarlo MinTIC y las alcaldías.
- **Alcance:** los 42 municipios del Valle (código de departamento DANE `76`), años 2017 a 2022.
- **Llave de integración:** `cod_mpio`, el código DIVIPOLA de 5 dígitos, que siempre se maneja como texto (por ejemplo, `76001` = Cali), junto con `anio`.

| # | Pregunta | Datos que la responden | Tabla Gold |
|---|---|---|---|
| P1 | ¿Cuál es la diferencia en acceso a internet entre zonas urbanas y rurales, y cómo ha evolucionado? | Saber 11 | `brecha_urbano_rural` |
| P2 | ¿Qué municipios tienen los menores niveles de conectividad? | Internet fijo + cobertura móvil + población DANE | `municipio_anio` |
| P3 | ¿Hay relación entre tener computador y tener internet en los hogares rurales? | Saber 11 | `brecha_urbano_rural` |
| P4 | ¿Qué relación hay entre la conectividad de un municipio y sus indicadores educativos? | Tabla integrada | `municipio_anio` |
| P5 | ¿Qué municipios combinan baja conectividad y rezago educativo, y deberían priorizarse? | Índice compuesto | `ranking_priorizacion` |

**Qué produce el proyecto:**

- 4 tablas finales en `data/gold/`.
- Un notebook de análisis (`notebooks/eda.ipynb`) organizado por pregunta.
- 21 gráficas en `reports/figures/`.

## 2. Datos utilizados

Todas las fuentes son públicas. Las cuatro de datos.gov.co se descargan por su API (SODA). La de población se descarga como archivo Excel desde la página del DANE.

| Fuente | Entidad | Dataset | Para qué la usamos | Granularidad original | Años disponibles (Valle) |
|---|---|---|---|---|---|
| [Internet Fijo: accesos por tecnología y segmento](https://www.datos.gov.co/d/n48w-gutb) | MinTIC | `n48w-gutb` | Número de accesos (conexiones) de internet fijo por municipio, separados en residenciales y corporativos (P2, P4, P5) | Municipio × trimestre × proveedor × segmento × tecnología | 2017-T1 a 2023-T3 |
| [Cobertura móvil por tecnología](https://www.datos.gov.co/d/9mey-c8s8) | MinTIC | `9mey-c8s8` | Qué operadores ofrecen 4G en cada municipio (P2, P5) | Centro poblado × trimestre × proveedor | 2015 a 2023-T3 |
| [Estadísticas en educación por municipio](https://www.datos.gov.co/d/nudc-7mev) | MEN | `nudc-7mev` | Cobertura neta y bruta, y deserción escolar (P4, P5) | Municipio × año | 2011 a 2024 |
| [Resultados únicos Saber 11](https://www.datos.gov.co/d/kgxf-xxbe) | ICFES | `kgxf-xxbe` | Por estudiante: si tiene internet y computador en el hogar, zona del colegio y puntaje global (P1, P3, P4, P5) | Estudiante × periodo | 2010 a 2022 (puntaje global desde el periodo 20142) |
| [Proyecciones de población municipal por área](https://www.dane.gov.co/index.php/estadisticas-por-tema/demografia-y-poblacion/proyecciones-de-poblacion) | DANE | 2 archivos XLSX (ver 2.1) | Población total, urbana y rural de cada municipio, para calcular tasas por habitante (P2, P4, P5) | Municipio × año × área | 2005 a 2042 |

**Ventana de análisis: 2017–2022.** Son los años que comparten todas las fuentes. Internet fijo empieza en 2017, y 2022 es el último año con cuarto trimestre de MinTIC y con resultados de Saber 11 publicados.

Los conteos de filas de este README corresponden a la extracción del 29 de septiembre de 2026. Si las entidades actualizan los datasets, los números pueden cambiar un poco.

### 2.1 Población del DANE: qué se toma, para qué y cómo se calcula

El dataset de internet fijo de MinTIC dice **cuántos accesos** hay en cada municipio, pero no trae la población. Un número absoluto no sirve para comparar: en 2022 Cali tenía 547.318 accesos y El Cairo 101, pero Cali también tiene unas 320 veces más habitantes. Para comparar municipios de distinto tamaño necesitábamos una tasa **por habitante**, y para eso usamos las proyecciones oficiales de población del DANE.

**Qué se descarga.** Dos archivos, ambos con base en el Censo Nacional de Población y Vivienda 2018:

| Archivo | Periodo | Hoja usada | Enlace |
|---|---|---|---|
| `DCD-area-proypoblacion-Mun-2005-2017_VP.xlsx` (retroproyección) | 2005–2017 | `NuevaMpal` | [descargar](https://www.dane.gov.co/files/censo2018/proyecciones-de-poblacion/Municipal/DCD-area-proypoblacion-Mun-2005-2017_VP.xlsx) |
| `PPED-AreaMun-2018-2042_VP.xlsx` (proyección) | 2018–2042 | `PobMunicipalxÁrea` | [descargar](https://www.dane.gov.co/files/censo2018/proyecciones-de-poblacion/Municipal/PPED-AreaMun-2018-2042_VP.xlsx) |

Hacen falta los dos porque la ventana empieza en 2017, que está en la retroproyección, y 2018–2022 están en la proyección. De cada archivo se usan las columnas:

- `DP` (departamento) y `MPIO` (código del municipio);
- `DPMP` (nombre del municipio) y `AÑO`;
- `ÁREA GEOGRÁFICA`, con tres valores: *Cabecera Municipal*, *Centros Poblados y Rural Disperso* y *Total*;
- la población, que en un archivo se llama `Población` y en el otro `TOTAL`.

**Cómo se procesa:**

1. **Bronze:** los dos XLSX se guardan tal como se descargan (`data/bronze/poblacion_dane_*_raw.xlsx`), con los datos de todo el país.
2. **Silver** (`src/transform/clean_poblacion.py`):
   - Se leen saltando las filas de título que trae el Excel. El encabezado está en la fila 12 de un archivo y en la 8 del otro; eso se define en `config.yaml`.
   - Se renombran las columnas al mismo esquema y se unen las dos series en una sola tabla.
   - Se eliminan las filas vacías y las notas al pie, y se filtra el Valle (`DP = 76`).
   - El área se simplifica a `total`, `cabecera` y `rural` (centros poblados y rural disperso).
   - Se comprueba que en todas las filas `total = cabecera + rural`; no hubo diferencias.
   - Resultado: `data/silver/poblacion.csv`, con 4.788 filas (42 municipios × 38 años × 3 áreas).
3. **Gold** (`src/transform/gold_data.py`): la población se une a la tabla `municipio_anio` por `cod_mpio` y `anio`, y con ella se calculan tres columnas:

```
accesos_por_100_hab               = accesos_fijos_total         / poblacion_total × 100
accesos_residenciales_por_100_hab = accesos_fijos_residenciales / poblacion_total × 100
pct_poblacion_rural               = poblacion (área rural)      / poblacion_total × 100
```

`poblacion_total` es la población del área *Total* del DANE para ese municipio y ese año. Los accesos son los del cuarto trimestre del mismo año (ver sección 5.3).

Ejemplo con Cali en 2022: 547.318 accesos / 2.283.342 habitantes × 100 = **23,97 accesos por cada 100 habitantes**. En El Cairo: 101 / 7.054 × 100 = **1,43**.

Además, los nombres oficiales de los municipios de `dim_municipio.csv` salen de este mismo archivo del DANE.

**Qué hay que tener en cuenta:** son proyecciones, es decir, estimaciones del DANE y no conteos. La tasa es "por habitante", no "por hogar". Como MinTIC no publica en este dataset un indicador oficial de penetración, no pudimos contrastar nuestra tasa contra uno oficial.

## 3. Cómo ejecutarlo desde cero

### 3.1 Requisitos

- **Python 3.11 o superior.** Lo probamos con Python 3.14 en Windows 11.
- **Conexión a internet:** la primera ejecución descarga unos 85 MB.
- Unos 150 MB libres para los datos generados, sin contar el entorno virtual.

### 3.2 Pasos

Todos los comandos se ejecutan desde la carpeta raíz del proyecto (la que contiene `main.py`).

**1. Crear y activar el entorno virtual**

```bash
python -m venv venv
venv\Scripts\activate          # Windows (en Linux/Mac: source venv/bin/activate)
```

En PowerShell, si aparece un error de "ejecución de scripts deshabilitada", ejecute una vez `Set-ExecutionPolicy -Scope CurrentUser RemoteSigned` y vuelva a activar.

**2. Instalar las dependencias**

```bash
pip install -r requirements.txt
```

**3. (Opcional) Configurar el token de datos.gov.co**

Sin token el pipeline funciona igual, pero la API puede limitar las peticiones. Para usar uno:

1. Cree una cuenta en datos.gov.co.
2. En *Developer Settings*, cree un **App Token**. Use el valor de la columna *App Token*, no el *Secret Token*.
3. Cree un archivo `.env` en la raíz con esta línea:

```
SOCRATA_APP_TOKEN=su_app_token
```

**4. Ejecutar el pipeline**

```bash
python main.py
```

Tarda entre 3 y 5 minutos (con token suele ser más rápido); la mayor parte del tiempo se va en descargar Saber 11. Primero hace la extracción, después la limpieza y al final construye las tablas Gold. En consola se imprime cada paso:

- las páginas que se descargan;
- la validación de filas (`Validación OK: filas extraídas = filas esperadas`);
- los duplicados y nulos eliminados;
- la verificación de los 42 municipios;
- las filas antes y después de cada unión;
- al final, `Pipeline terminado en ... segundos`.

**5. Correr las pruebas unitarias (opcional)**

```bash
pytest
```

Deben pasar las 5 pruebas. No descargan nada: usan datos de ejemplo.

**6. Abrir el notebook de análisis**

Requiere haber ejecutado antes el paso 4, porque lee los archivos de `data/silver/` y `data/gold/`.

```bash
jupyter notebook notebooks/eda.ipynb
```

En el menú, elija *Kernel → Restart & Run All*. Además de mostrar las gráficas, el notebook las guarda como PNG en `reports/figures/`. También se puede abrir en VS Code seleccionando como kernel el Python del `venv`.

### 3.3 Otras opciones de `main.py`

| Comando | Qué hace |
|---|---|
| `python main.py --sin-extraccion` | No descarga nada: rehace Silver y Gold con los archivos que ya estén en `data/bronze/`. Requiere haber corrido antes `python main.py` una vez. |
| `python main.py --cargar-duckdb` | Además de todo lo anterior, carga las tablas Gold en `data/gold/brecha_digital.duckdb` y muestra una consulta de ejemplo (los 5 municipios más prioritarios). Es opcional. |

### 3.4 Problemas comunes

| Síntoma | Causa | Qué hacer |
|---|---|---|
| Error `500`, `503` o `Read timed out` durante la extracción | datos.gov.co a veces responde con errores intermitentes | El código ya reintenta cada petición 3 veces. Si aun así falla, espere unos minutos y vuelva a ejecutar, o suba `reintentos` en `config/config.yaml`. |
| Error `403 Invalid app_token specified` | El valor de `.env` no es un App Token válido | Revise que sea el *App Token* y no el *Secret Token*, o deje la línea vacía (`SOCRATA_APP_TOKEN=`). |
| `FileNotFoundError` al usar `--sin-extraccion` o al abrir el notebook | Todavía no existen los datos | Ejecute primero `python main.py`. |

## 4. Estructura del proyecto

```
Proyecto_ETL/
├── config/config.yaml              ← rutas, IDs de los datasets, filtros, URLs del DANE y constantes
├── data/
│   ├── bronze/                     ← datos crudos
│   ├── silver/                     ← un CSV limpio por fuente
│   └── gold/                       ← tablas finales para el análisis
├── logs/                           ← un archivo etl_AAAA-MM-DD.log por día de ejecución
├── notebooks/eda.ipynb             ← análisis exploratorio y gráficas, organizado por P1–P5
├── reports/figures/                ← gráficas del notebook en PNG
├── src/
│   ├── extract/extract_api.py          ← descarga de la API y del DANE (Bronze)
│   ├── transform/clean_conectividad.py ← limpieza de internet fijo y cobertura móvil
│   ├── transform/clean_educacion.py    ← limpieza de MEN y Saber 11
│   ├── transform/clean_poblacion.py    ← limpieza y unión de la población del DANE
│   ├── transform/validaciones.py       ← revisión de nulos y de los 42 municipios
│   ├── transform/gold_data.py          ← construcción de las tablas Gold y del índice
│   └── load/load_database.py           ← (opcional) carga de Gold en DuckDB
├── tests/test_transform.py         ← pruebas unitarias
├── main.py                         ← ejecuta todo en orden: extracción → limpieza → Gold
├── requirements.txt                ← dependencias con las versiones probadas
└── .env                            ← token de datos.gov.co (opcional; no se sube al repositorio)
```

Las carpetas de `data/` vienen vacías en el repositorio: todos los datos se generan al ejecutar `python main.py`.

Ningún archivo de código tiene rutas absolutas: todas las rutas salen de `config/config.yaml` y son relativas a la raíz del proyecto.

## 5. Proceso completo (arquitectura Medallón)

| Etapa | Entra | Qué se hace | Sale | Código |
|---|---|---|---|---|
| Bronze | API de datos.gov.co y archivos del DANE | Descarga sin modificar valores | 4 CSV + 2 XLSX en `data/bronze/` | `src/extract/extract_api.py` |
| Silver | Archivos de Bronze | Limpieza, conversión de tipos y deduplicación; una función por fuente | 5 CSV en `data/silver/` | `src/transform/clean_*.py` |
| Gold | Archivos de Silver | Agregación a municipio-año, unión de fuentes, cálculo de indicadores e índice | 4 CSV en `data/gold/` | `src/transform/gold_data.py` |
| Análisis | Archivos de Silver y Gold | Exploración de datos y gráficas por pregunta | Notebook y 21 PNG en `reports/figures/` | `notebooks/eda.ipynb` |

### 5.1 Bronze: extracción

La idea de Bronze es guardar lo que entrega cada fuente **sin cambiar ningún valor**. Todo se lee como texto (`dtype=str`) para no perder, por ejemplo, el cero inicial de un código. Lo único que se aplica al descargar es el filtro del departamento (`$where`, código 76) y, en Saber 11, la selección de columnas (`$select`). Sin el filtro del departamento, Saber 11 tiene 7.109.704 filas en todo el país.

Técnicas usadas en la extracción:

- **Paginación** de 50.000 filas por petición (`$limit` y `$offset`), ordenando por `:id` para que las páginas no se repitan ni se salten filas. Saber 11 se descarga en 13 páginas.
- **Validación:** antes de descargar se consulta cuántas filas tiene el dataset (`count(*)`), y al final se compara con las descargadas.
- **Token opcional** en el encabezado `X-App-Token`, leído desde `.env` con `python-dotenv`.
- **Reintentos** automáticos, esperando 2 y luego 4 segundos entre intentos.
- **Registro:** cada fuente deja una línea en `logs/etl_AAAA-MM-DD.log` con la fecha, la fuente, las filas y el tiempo de descarga. Las etapas Silver y Gold también registran sus filas.

| Archivo en `data/bronze/` | Filas | Contenido |
|---|---|---|
| `internet_fijo_raw.csv` | 256.229 | Todas las columnas del dataset, solo Valle |
| `cobertura_movil_raw.csv` | 26.822 | Todas las columnas del dataset, solo Valle |
| `men_educacion_raw.csv` | 588 | 42 municipios × 14 años (2011–2024) |
| `saber11_raw.csv` | 642.592 | 10 columnas seleccionadas, solo colegios del Valle |
| `poblacion_dane_2005_2017_raw.xlsx` | 43.758 | Todo el país |
| `poblacion_dane_2018_2042_raw.xlsx` | 84.234 | Todo el país |

### 5.2 Silver: limpieza

Cada fuente tiene su propia función de limpieza, porque sus columnas y sus problemas son distintos. Todas quedan en su granularidad original (por ejemplo, Saber 11 sigue siendo una fila por estudiante), pero con las mismas reglas:

- Nombres de columnas en `snake_case`, en español y sin tildes.
- `cod_mpio` como texto de 5 dígitos y `anio` como número entero.
- Se verifica que estén los 42 municipios; están completos en las cinco fuentes.

| Archivo en `data/silver/` | Filas | Una fila es… | Llave usada para duplicados |
|---|---|---|---|
| `internet_fijo.csv` | 247.113 | un proveedor × segmento × tecnología × velocidad en un municipio y trimestre | fila completa (el dataset no tiene un identificador) |
| `cobertura_movil.csv` | 26.822 | un proveedor en un centro poblado y trimestre | `anio, trimestre, cod_mpio, centro poblado, proveedor` |
| `men_educacion.csv` | 588 | un municipio en un año | `anio, cod_mpio` |
| `saber11.csv` | 295.188 | un estudiante (periodos desde 20142) | `estu_consecutivo` |
| `poblacion.csv` | 4.788 | un municipio, año y área | `cod_mpio, anio, area` |

**Transformaciones aplicadas**, agrupadas según las operaciones vistas en clase:

| Operación | Fuente | Qué hicimos y por qué |
|---|---|---|
| Eliminación de duplicados | Saber 11 | La API devuelve 139.037 filas repetidas; en los periodos 20194 y 20224 cada estudiante aparece dos veces. Se deja una fila por `estu_consecutivo`. |
| | Internet fijo | Hay 9.116 filas idénticas, todas de 2022 y 2023, cuando MinTIC cambió el formato de reporte. Como no hay un identificador, no se puede saber si son repeticiones o registros distintos. Las eliminamos porque equivalen al 0,32 % de los accesos (en el T4 de 2022, de 918.562 a 915.664) y la serie queda continua con 2021. Se eliminan antes de quitar columnas. Por eso, en `internet_fijo.csv` quedan 6.855 filas que parecen repetidas: en Bronze solo se diferenciaban en `velocidad_subida`, que se elimina en Silver. Son planes distintos del mismo proveedor, así que se conservan (la sección 1.3 del notebook lo demuestra). |
| | MEN, móvil, población | Se revisó la llave natural y no había duplicados. |
| Manejo de valores faltantes | Todas | No imputamos ningún valor: si a un municipio le falta un dato, queda vacío, porque rellenarlo con la media sería inventar conectividad o resultados. Solo se eliminan filas sin llave o sin su dato principal (sin municipio, sin cantidad de accesos o sin puntaje). En Saber 11, las respuestas vacías sobre internet o computador quedan vacías y no cuentan en los porcentajes. |
| Corrección de errores tipográficos | Nombres de columnas | `cobertuta_4g` se corrige a `cobertura_4g`. La API reemplaza tildes y eñes por `_` (`a_o`, `deserci_n`, `c_digo_municipio`), y se corrigen a `anio`, `desercion`, `cod_mpio`. |
| Normalización de formatos | Todas | Códigos con `zfill(5)`. Texto sin espacios sobrantes y en minúscula. Los dos archivos del DANE tienen las columnas en distinto orden y con distinto nombre, y se llevan a un mismo esquema. |
| Conversión de tipos | Todas | Texto a número entero o decimal. En internet fijo, las velocidades vienen con coma decimal (`"15,00"`) y se pasan a punto. En Saber 11, `periodo` (formato AAAAS, p. ej. `20224`) se separa en `anio` y `semestre`. |
| Conversión de categóricas | Móvil, Saber 11, internet fijo | `S`/`N` y `Si`/`No` pasan a 1/0. `OFICIAL`/`NO OFICIAL` pasa a `colegio_oficial` (1/0). `Estrato 3` pasa a 3, y `Sin Estrato` a 0. `segmento` se convierte en `es_residencial` (1/0; ver 5.3). En la población, el área pasa a `total`/`cabecera`/`rural`. |
| Corrección de un cambio de formato | Móvil | Hasta 2020 el 4G se reportaba en la columna `cobertura_lte` y desde 2021 en `cobertuta_4g`; nunca en ambas a la vez. Se unifican en `tiene_4g` (1 si cualquiera de las dos es 1). Sin esto, parecería que no hubo 4G antes de 2021. |
| Valores que no son códigos reales | Móvil | `cod_centro_poblado = "0"` significa "sin centro poblado", así que se convierte en vacío. |
| Outliers | Saber 11 | Se valida que `punt_global` esté entre 0 y 500. No hubo valores por fuera. |
| | MEN | Una cobertura bruta mayor que 100 % es válida, porque incluye estudiantes en extraedad. Una cobertura neta de hasta 111 % se debe a que el MEN divide por población proyectada. En ambos casos se conservan. |
| Filtrado | Saber 11 | Solo periodos desde 20142, porque antes el puntaje global no existe (el examen tenía otra escala). |
| Eliminación de columnas irrelevantes | Todas | Departamento (siempre es 76), velocidad de subida, columnas de ETC y desagregados por nivel del MEN (usamos los totales municipales). |

### 5.3 Gold: integración y cálculos

Para unir las fuentes, primero cada una se lleva al nivel **municipio-año**. Luego se parte de una tabla con las 252 combinaciones posibles (42 municipios × 6 años) y se le van uniendo las fuentes por `cod_mpio` y `anio`. Así ningún municipio desaparece aunque le falte un dato. Cada unión usa `validate="one_to_one"`, y en consola se imprimen las filas antes y después para comprobar que no se pierden ni se duplican registros.

**Tablas que quedan en `data/gold/`:**

| Archivo | Filas | Una fila es… | Para |
|---|---|---|---|
| `dim_municipio.csv` | 42 | un municipio: `cod_mpio` y nombre oficial (DANE) | referencia |
| `brecha_urbano_rural.csv` | 509 | un municipio (o el total del Valle), año y zona (urbano/rural) | P1, P3 |
| `municipio_anio.csv` | 252 | un municipio en un año, 2017–2022 | P2, P4 |
| `ranking_priorizacion.csv` | 42 | un municipio en 2022, con su índice y posición | P5 |

**Columnas de `municipio_anio.csv` y cómo se obtiene cada una:**

| Columna | Fuente | Cálculo |
|---|---|---|
| `cod_mpio`, `municipio`, `anio` | DANE | Nombre oficial del DANE. |
| `poblacion_total`, `pct_poblacion_rural` | DANE | Ver sección 2.1. |
| `trimestre_fijo` | MinTIC fijo | Trimestre usado. Siempre es 4: los accesos son una "foto" al corte de cada trimestre y no se pueden sumar entre trimestres, así que se usa el último del año. |
| `accesos_fijos_total` | MinTIC fijo | Suma de los accesos del municipio en el T4 de ese año (todos los proveedores, segmentos y tecnologías). |
| `accesos_fijos_residenciales` | MinTIC fijo | La misma suma, solo con los accesos de hogares (ver nota abajo). |
| `accesos_por_100_hab`, `accesos_residenciales_por_100_hab` | MinTIC fijo + DANE | Accesos / población total × 100 (sección 2.1). |
| `operadores_movil` | MinTIC móvil | Número de operadores distintos que reportan cobertura en el municipio en el último trimestre del año. |
| `operadores_4g` | MinTIC móvil | Número de operadores distintos con 4G en al menos un lugar del municipio. |
| `pct_centros_poblados_4g` | MinTIC móvil | De los centros poblados fuera de la cabecera, el % que tiene 4G de al menos un operador. Queda vacío si el municipio no reporta centros poblados fuera de la cabecera. |
| `cobertura_neta`, `cobertura_bruta`, `desercion`, `sedes_conectadas_a_internet` | MEN | Se toman tal cual del MEN (en %). `sedes_conectadas_a_internet` solo tiene datos hasta 2017. |
| `saber11_anio_completo` | Saber 11 | 1 si ese año tiene la aplicación completa del examen (ver nota abajo); 0 si no. |
| `n_estudiantes_saber11` | Saber 11 | Número de estudiantes de colegios del municipio que presentaron el examen ese año. |
| `pct_estudiantes_con_internet`, `pct_estudiantes_con_computador` | Saber 11 | Estudiantes que respondieron "Sí" / estudiantes que respondieron la pregunta × 100. |
| `punt_global_prom` | Saber 11 | Promedio del puntaje global (escala 0–500) de los estudiantes del municipio. |

Notas sobre estos cálculos:

- **Accesos residenciales.** El dataset de MinTIC clasifica cada acceso por segmento. Contamos como residencial todo lo que no es `corporativo` ni `uso propio interno del operador`, es decir, los estratos 1 a 6 y también el segmento *sin estratificar*. Lo incluimos porque en municipios rurales algunos operadores reportan así todos sus hogares: en Obando, en 2022, son 874 de 940 accesos. Excluirlo haría ver a los municipios rurales con menos conectividad de la que tienen. Calculamos las dos tasas (total y residencial), pero en el índice usamos la residencial, porque la total se infla en municipios con muchas empresas.
- **Años completos de Saber 11.** El examen se aplica en calendario A (pocos colegios, sobre todo privados) y calendario B (la mayoría). Consideramos completo un año si incluye la aplicación de calendario B o la anual (semestre 2 o 4 en el periodo). En 2018, 2020 y 2021 solo está publicado el calendario A, con 12 a 14 municipios. Usar esos años daría una muestra sesgada, así que sus columnas de Saber 11 quedan **vacías**.

**Columnas de `brecha_urbano_rural.csv`:** se calculan igual que las de Saber 11 de arriba, pero separando por la zona del colegio (`urbano` o `rural`). Solo se incluyen los años completos: 2014, 2015, 2016, 2017, 2019 y 2022. Aquí usamos desde 2014 porque esta tabla depende solo de Saber 11, y así la evolución de P1 tiene más puntos.

- `n_estudiantes`, `pct_con_internet`, `pct_con_computador`, `punt_global_prom`: como en `municipio_anio`.
- `pct_internet_si_tiene_pc` y `pct_internet_si_no_tiene_pc`: el % con internet solo entre quienes tienen computador, y solo entre quienes no tienen (usado en P3).
- `muestra_suficiente`: 1 si la celda tiene al menos 30 estudiantes (valor definido en `config.yaml`). Con menos, el porcentaje no es confiable y el notebook no lo grafica.
- `nivel`: `municipio` o `departamento`. Las filas `departamento` son el total del Valle; se identifican con `cod_mpio = 76000` para que todas las filas tengan un código de 5 dígitos, y no corresponden a ningún municipio real.

### 5.4 Índice de priorización (`ranking_priorizacion.csv`)

El índice resume en un solo número qué tan buena es la situación de cada municipio en conectividad y educación durante 2022, el último año con datos de todas las fuentes. Pasos:

1. **Variables.** Se parte de siete candidatas.
   - Donde más es mejor: `accesos_residenciales_por_100_hab`, `operadores_4g`, `pct_estudiantes_con_internet`, `punt_global_prom`, `cobertura_neta` y `sedes_conectadas_a_internet`.
   - Donde más es peor: `desercion`.

   Se descarta cualquier variable con más de 20 % de datos vacíos en 2022. Por eso sale `sedes_conectadas_a_internet`, que está 100 % vacía. Quedan 6 variables: 3 de conectividad y 3 de educación.
2. **Normalización min-max.** Cada variable se lleva a una escala de 0 a 1 comparando los 42 municipios:
   `x_norm = (x − mínimo) / (máximo − mínimo)`.
   En la deserción se usa `1 − x_norm`, para que en todas las variables 1 signifique "mejor situación".
3. **Índice.** Es el promedio simple de las variables normalizadas, con pesos iguales. Los pesos iguales son un supuesto nuestro, no una calibración. Si a un municipio le faltara una variable, se promediarían las que tiene; la columna `variables_con_dato` lo indica. En 2022 todos tienen las 6.
4. **Posición y nivel.** `posicion` = 1 para el índice más bajo, es decir, el municipio más prioritario. Los municipios se dividen en tres grupos iguales (terciles) según el índice: `bajo`, `medio` y `alto`. Los 14 del nivel `bajo` quedan marcados como `prioritario = 1`.
5. **Sensibilidad.** En 2022 `operadores_4g` casi no varía (todos los municipios tienen 3 o 4), pero con min-max un operador de diferencia pesa lo mismo que toda la escala. En el notebook recalculamos el índice sin esa variable: 13 de los 14 prioritarios se mantienen (sale El Dovio y entra Ulloa).

## 6. Qué archivos quedan después de ejecutar

| Dónde | Archivos | Lo genera |
|---|---|---|
| `data/bronze/` | `internet_fijo_raw.csv`, `cobertura_movil_raw.csv`, `men_educacion_raw.csv`, `saber11_raw.csv`, `poblacion_dane_2005_2017_raw.xlsx`, `poblacion_dane_2018_2042_raw.xlsx` | `python main.py` |
| `data/silver/` | `internet_fijo.csv`, `cobertura_movil.csv`, `men_educacion.csv`, `saber11.csv`, `poblacion.csv` | `python main.py` |
| `data/gold/` | `dim_municipio.csv`, `brecha_urbano_rural.csv`, `municipio_anio.csv`, `ranking_priorizacion.csv` | `python main.py` |
| `data/gold/` | `brecha_digital.duckdb` | `python main.py --cargar-duckdb` (opcional) |
| `logs/` | `etl_AAAA-MM-DD.log` | `python main.py` |
| `reports/figures/` | 21 gráficas PNG numeradas por sección (por ejemplo, `08_p1_evolucion_urbano_rural.png`, `18_p5_ranking_indice.png`) | ejecutar el notebook completo |

## 7. Limitaciones

- **Internet fijo:**
  - Cuenta accesos (suscripciones), no personas conectadas ni calidad del servicio.
  - Desde 2022 cambia el formato de reporte (se duplican las filas y aparecen filas idénticas).
  - Tiene reportes anómalos. Por ejemplo, en Ulloa en 2017 un solo proveedor reportó 2.242 accesos corporativos y 1.121 de estrato 6 en un municipio de 5.433 habitantes (68,1 accesos por cada 100). Lo dejamos documentado, pero no lo borramos porque no hay forma de corregirlo; no afecta al ranking, que es de 2022.
- **Cobertura móvil:**
  - Es la cobertura que declaran los operadores; no mide uso, velocidad ni calidad.
  - En 2022 cambió la forma de reporte: se pasó de 573 centros poblados en 2021 a 236. Por eso `pct_centros_poblados_4g` no es comparable entre años.
- **MEN:**
  - Desde 2018 las tasas usan proyecciones de población del Censo 2018, lo que puede generar un salto en la serie frente a años anteriores.
  - `sedes_conectadas_a_internet` está vacía desde 2018.
- **Saber 11:**
  - Representa los hogares de estudiantes de grado 11, no a todos los hogares.
  - La zona es la del colegio, no la de la vivienda.
  - Faltan 2018, 2020 y 2021, y 2014 solo tiene calendario B.
  - En 10 municipios hay menos de 30 estudiantes en alguna zona, por lo que su brecha municipal no se reporta.
- **Población DANE:** son proyecciones, no conteos, y la tasa de accesos por habitante no se pudo comparar con un indicador oficial de MinTIC.
- **Análisis:**
  - Las relaciones de P3 y P4 son correlaciones, no efectos causales: la ruralidad y el nivel socioeconómico influyen a la vez en la conectividad y en los resultados educativos.
  - El índice depende de los supuestos de la sección 5.4.

## 8. Resultados principales

El detalle, con las gráficas y su interpretación, está en `notebooks/eda.ipynb`.

- **P1.** La brecha urbano-rural en acceso a internet (estudiantes de grado 11) bajó de 32,3 puntos porcentuales en 2014 a 14,2 en 2022. En 2022, las brechas municipales más grandes están en Yotoco (50,7 pp, con pocos estudiantes rurales), Buenaventura (37,7 pp) y Trujillo (25,8 pp).
- **P2.** Los municipios con menos accesos fijos residenciales por cada 100 habitantes en 2022 son El Águila (0,86), Riofrío (1,05) y El Cairo (1,22). En el otro extremo están Jamundí (24,6) y Cali (21,7); Jamundí tiene 28,7 veces más que El Águila. En cambio, el 4G llega a los 42 municipios, con 3 o 4 operadores cada uno.
- **P3.** En colegios rurales, el 90,6 % de los estudiantes con computador tiene internet, frente al 54,8 % de los que no tienen. El internet creció mucho, pero la tenencia de computador en lo rural se ha mantenido entre 43 % y 51 % desde 2014 (44,6 % en 2022), así que la brecha rural hoy es sobre todo de dispositivos.
- **P4.** Los municipios con más accesos residenciales por habitante tienen mejores puntajes en Saber 11 (r = 0,57), pero la relación con la deserción es débil (r = −0,22).
- **P5.** Los 14 municipios prioritarios en 2022 son Bolívar, El Águila, Argelia, Alcalá, La Victoria, El Cairo, El Dovio, Obando, Trujillo, Buenaventura, Riofrío, Caicedonia, Ansermanuevo y Toro.
