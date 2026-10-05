import os
import yaml
import pandas as pd
from sqlalchemy import create_engine
from sqlalchemy.exc import SQLAlchemyError


# ============================================================
# CONFIGURACIÓN DE LA BASE DE DATOS
# ============================================================

DB_USER = "postgres"
DB_PASSWORD = "postgres"
DB_HOST = "localhost"
DB_PORT = "5432"
DB_NAME = "brecha_digital"


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

with open("./config/config.yaml", "r", encoding="utf-8") as archivo:
    config = yaml.safe_load(archivo)


# Obtener las rutas de la sección gold
rutas_gold = config["gold"]


# ============================================================
# RELACIÓN CSV -> TABLA
# ============================================================

TABLAS = {
    "dim_municipio": "dim_municipio",
    "brecha_urbano_rural": "brecha_urbano_rural",
    "municipio_anio": "municipio_anio",
    "ranking_priorizacion": "ranking_priorizacion"
}


# ============================================================
# CARGAR ARCHIVO
# ============================================================

def cargar_archivo(nombre, ruta):

    tabla = TABLAS[nombre]

    print("\n----------------------------------------")
    print(f"Archivo : {ruta}")
    print(f"Tabla   : {tabla}")
    print("----------------------------------------")

    # Verificar que exista el archivo
    if not os.path.exists(ruta):
        raise FileNotFoundError(
            f"No se encontró el archivo: {ruta}"
        )

    # Leer CSV
    df = pd.read_csv(
        ruta,
        encoding="utf-8-sig"
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

    if "muestra_suficiente" in df.columns:

        df["muestra_suficiente"] = (
            df["muestra_suficiente"]
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

    if "prioritario" in df.columns:

        df["prioritario"] = (
            df["prioritario"]
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

    # --------------------------------------------------------
    # Insertar en PostgreSQL
    # --------------------------------------------------------


    try:
        df.to_sql(
        tabla,
        engine,
        if_exists="append",
        index=False,
        chunksize=500
    )
    except SQLAlchemyError as e:
        print("\nERROR EN LA TABLA:", tabla)
        print(str(e.orig))   # solo el mensaje de PostgreSQL, sin el INSERT gigante
        raise SystemExit(1)


# ============================================================
# CARGAR TODOS LOS ARCHIVOS
# ============================================================

def cargar_todo():

    # Este orden es importante por las llaves foráneas
    orden = [
        "dim_municipio",
        "brecha_urbano_rural",
        "municipio_anio",
        "ranking_priorizacion"
    ]

    for nombre in orden:

        ruta = rutas_gold[nombre]

        cargar_archivo(
            nombre,
            ruta
        )


# ============================================================
# MAIN
# ============================================================

if __name__ == "__main__":

    try:

        cargar_todo()

        print("\n========================================")
        print("✓ CARGA COMPLETADA CORRECTAMENTE")
        print("========================================")

    except Exception as e:

        print("\n========================================")
        print("ERROR DURANTE LA CARGA")
        print("========================================")
        print(e)