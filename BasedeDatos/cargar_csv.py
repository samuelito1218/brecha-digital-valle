import os
import yaml
import pandas as pd
from sqlalchemy import create_engine, text
from sqlalchemy.exc import SQLAlchemyError


# ============================================================
# CONFIGURACIÓN DE LA BASE DE DATOS
# ============================================================
# Valores por defecto = los de docker-compose.yml. Se pueden cambiar con
# variables de entorno (por ejemplo DB_PORT=5433 si el 5432 está ocupado).

DB_USER = os.getenv("DB_USER", "postgres")
DB_PASSWORD = os.getenv("DB_PASSWORD", "postgres")
DB_HOST = os.getenv("DB_HOST", "localhost")
DB_PORT = os.getenv("DB_PORT", "5432")
DB_NAME = os.getenv("DB_NAME", "brecha_digital")


# ============================================================
# CONEXIÓN A POSTGRESQL
# ============================================================

DATABASE_URL = (
    f"postgresql+psycopg2://"
    f"{DB_USER}:{DB_PASSWORD}@"
    f"{DB_HOST}:{DB_PORT}/{DB_NAME}"
)

engine = create_engine(DATABASE_URL)


# ============================================================
# LEER CONFIG.YAML
# ============================================================

# Trabajar desde la raíz del proyecto (carpeta padre de BasedeDatos/),
# para que las rutas relativas de config.yaml funcionen desde cualquier carpeta.
RAIZ_PROYECTO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
os.chdir(RAIZ_PROYECTO)

with open("./config/config.yaml", "r", encoding="utf-8") as archivo:
    config = yaml.safe_load(archivo)


# Obtener las rutas de la sección gold
rutas_gold = config["gold"]


# ============================================================
# ORDEN DE CARGA
# ============================================================
# Este orden es importante por las llaves foráneas:
# primero la dimensión, luego municipio_anio (el ranking la referencia).

ORDEN = [
    "dim_municipio",
    "municipio_anio",
    "ranking_priorizacion",
    "brecha_urbano_rural",
]

# Tablas que se vacían antes de cargar (incluye brecha_valle, que sale del
# mismo CSV que brecha_urbano_rural).
TABLAS_BD = [
    "brecha_valle",
    "brecha_urbano_rural",
    "ranking_priorizacion",
    "municipio_anio",
    "dim_municipio",
]


# ============================================================
# LEER Y PREPARAR UN CSV
# ============================================================

def leer_archivo(nombre, ruta):

    print("\n----------------------------------------")
    print(f"Archivo : {ruta}")
    print("----------------------------------------")

    # Verificar que exista el archivo
    if not os.path.exists(ruta):
        raise FileNotFoundError(
            f"No se encontró el archivo: {ruta}. Ejecute primero python main.py"
        )

    # Leer CSV. cod_mpio se lee como texto para conservar los 5 dígitos.
    df = pd.read_csv(
        ruta,
        encoding="utf-8-sig",
        dtype={"cod_mpio": str}
    )

    # Limpiar nombres de columnas
    df.columns = (
        df.columns
        .str.strip()
        .str.lower()
    )

    print(f"Registros encontrados: {len(df)}")

    # --------------------------------------------------------
    # Conversión de booleanos
    # --------------------------------------------------------

    for columna in ["muestra_suficiente", "prioritario"]:

        if columna in df.columns:

            df[columna] = (
                df[columna]
                .astype(str)
                .str.strip()
                .str.lower()
                .map({
                    "true": True,
                    "false": False,
                    "1": True,
                    "0": False,
                    "si": True,
                    "sí": True,
                    "no": False
                })
            )

    # --------------------------------------------------------
    # Reemplazar valores vacíos
    # --------------------------------------------------------

    df = df.replace({
        "": None,
        "NA": None,
        "N/A": None,
        "NULL": None,
        "null": None
    })

    return df


# ============================================================
# INSERTAR UN DATAFRAME EN UNA TABLA
# ============================================================

def insertar(df, tabla, conexion):

    print(f"Tabla   : {tabla} ({len(df)} filas)")

    df.to_sql(
        tabla,
        conexion,
        if_exists="append",
        index=False,
        chunksize=500
    )


# ============================================================
# CARGAR TODOS LOS ARCHIVOS
# ============================================================

def cargar_todo():

    # Todo en una sola transacción: si algo falla, PostgreSQL deshace todo
    # y la base no queda a medias.
    with engine.begin() as conexion:

        # Vaciar las tablas antes de cargar. Así el script se puede ejecutar
        # las veces que se quiera y la base queda igual a los CSV de data/gold/.
        conexion.execute(text(
            f"TRUNCATE {', '.join(TABLAS_BD)} RESTART IDENTITY"
        ))
        print("Tablas vaciadas para una carga limpia")

        for nombre in ORDEN:

            df = leer_archivo(nombre, rutas_gold[nombre])

            if nombre == "brecha_urbano_rural":

                # Las filas del total del Valle (nivel = departamento, cod_mpio = 76000)
                # no son de un municipio: van a su propia tabla, brecha_valle.
                valle = df[df["nivel"] == "departamento"].drop(columns=["nivel", "cod_mpio"])
                municipios = df[df["nivel"] == "municipio"]

                insertar(municipios, "brecha_urbano_rural", conexion)
                insertar(valle, "brecha_valle", conexion)

            else:
                insertar(df, nombre, conexion)

        # Verificar cuántas filas quedaron en cada tabla
        print("\n----------------------------------------")
        print("Filas cargadas por tabla:")
        for tabla in reversed(TABLAS_BD):
            total = conexion.execute(text(f"SELECT COUNT(*) FROM {tabla}")).scalar()
            print(f"  {tabla}: {total}")


# ============================================================
# MAIN
# ============================================================

if __name__ == "__main__":

    try:

        cargar_todo()

        print("\n========================================")
        print("✓ CARGA COMPLETADA CORRECTAMENTE")
        print("========================================")

    except SQLAlchemyError as e:

        print("\n========================================")
        print("ERROR DURANTE LA CARGA (no se guardó ningún cambio)")
        print("========================================")
        # Solo el mensaje de PostgreSQL, sin el INSERT completo
        print(getattr(e, "orig", e))
        raise SystemExit(1)

    except Exception as e:

        print("\n========================================")
        print("ERROR DURANTE LA CARGA")
        print("========================================")
        print(e)
        raise SystemExit(1)
