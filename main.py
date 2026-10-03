import argparse
import datetime
import os
import time

import pandas as pd
import yaml

from src.extract.extract_api import extraer_todo, registrar_log
from src.transform.clean_conectividad import limpiar_cobertura_movil, limpiar_internet_fijo
from src.transform.clean_educacion import limpiar_men, limpiar_saber11
from src.transform.clean_poblacion import leer_poblacion_dane, limpiar_poblacion
from src.transform.gold_data import construir_gold


def leer_bronze(ruta: str) -> pd.DataFrame:
    # leer todo como texto para no perder ceros a la izquierda.
    return pd.read_csv(ruta, dtype=str, keep_default_na=False, na_values=[""])


def guardar(df: pd.DataFrame, ruta: str) -> None:
    os.makedirs(os.path.dirname(ruta), exist_ok=True)
    df.to_csv(ruta, index=False, encoding="utf-8")
    print(f"Guardado: {ruta} {df.shape}")


def etapa_limpieza(config: dict) -> dict:
    fuentes = config["sources"]
    silver = {}

    print("\n===== Silver: internet fijo =====")
    silver["internet_fijo"] = limpiar_internet_fijo(leer_bronze(fuentes["internet_fijo"]["path"]), config)

    print("\n===== Silver: cobertura móvil =====")
    silver["cobertura_movil"] = limpiar_cobertura_movil(leer_bronze(fuentes["cobertura_movil"]["path"]), config)

    print("\n===== Silver: MEN =====")
    silver["men_educacion"] = limpiar_men(leer_bronze(fuentes["men_educacion"]["path"]), config)

    print("\n===== Silver: Saber 11 =====")
    silver["saber11"] = limpiar_saber11(leer_bronze(fuentes["saber11"]["path"]), config)

    print("\n===== Silver: población DANE =====")
    archivos = fuentes["poblacion_dane"]["archivos"]
    silver["poblacion"] = limpiar_poblacion(leer_poblacion_dane(archivos["retroproyeccion"]),
                                            leer_poblacion_dane(archivos["proyeccion"]), config)

    # Guardar un archivo limpio por fuente.
    for nombre, clave in [("internet_fijo", "internet_fijo"), ("cobertura_movil", "cobertura_movil"),
                          ("men_educacion", "men_educacion"), ("saber11", "saber11"), ("poblacion", "poblacion_dane")]:
        guardar(silver[nombre], fuentes[clave]["silver"])
        registrar_log(config, f"silver_{nombre}", len(silver[nombre]))
    return silver


def etapa_gold(config: dict, silver: dict) -> None:
    tablas = construir_gold(silver, config)
    for nombre, df in tablas.items():
        guardar(df, config["gold"][nombre])
        registrar_log(config, f"gold_{nombre}", len(df))


def main() -> None:
    parser = argparse.ArgumentParser(description="Pipeline ETL brecha digital Valle del Cauca")
    parser.add_argument("--sin-extraccion", action="store_true", help="Usar los archivos que ya están en data/bronze")
    parser.add_argument("--cargar-duckdb", action="store_true", help="Cargar las tablas Gold en DuckDB")
    args = parser.parse_args()

    
    os.chdir(os.path.dirname(os.path.abspath(__file__)))

    with open("config/config.yaml", "r", encoding="utf-8") as file:
        config = yaml.safe_load(file)
    execution_date = datetime.datetime.now().strftime(config["constant"]["date_format"])
    inicio = time.time()
    print(f"Ejecución del pipeline {config['project']['name']} - {execution_date}")

    print("\n########## 1. EXTRACCIÓN (Bronze) ##########")
    if args.sin_extraccion:
        print("Extracción omitida: se usan los archivos de data/bronze")
    else:
        extraer_todo(config)

    print("\n########## 2. TRANSFORMACIÓN (Silver) ##########")
    silver = etapa_limpieza(config)

    print("\n########## 3. TABLAS DE NEGOCIO (Gold) ##########")
    etapa_gold(config, silver)

    if args.cargar_duckdb:
        print("\n########## 4. CARGA EN DUCKDB (opcional) ##########")
        from src.load.load_database import cargar_duckdb
        cargar_duckdb(config)

    duracion = time.time() - inicio
    registrar_log(config, "pipeline", 0, f"fin OK en {duracion:.1f} s")
    print(f"\nPipeline terminado en {duracion:.1f} segundos")


if __name__ == "__main__":
    main()
