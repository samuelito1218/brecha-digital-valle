import datetime
import io
import os
import time

import pandas as pd
import requests
from dotenv import load_dotenv


def registrar_log(config: dict, fuente: str, filas: int, detalle: str = "") -> None:
    # Escribir una línea por fuente en el log del día: fecha, fuente y filas extraídas.
    fecha = datetime.datetime.now().strftime(config["constant"]["date_format"])
    hora = datetime.datetime.now().strftime("%H:%M:%S")
    os.makedirs(config["paths"]["logs_dir"], exist_ok=True)
    ruta_log = os.path.join(config["paths"]["logs_dir"], f"etl_{fecha}.log")
    with open(ruta_log, "a", encoding="utf-8") as archivo:
        archivo.write(f"{fecha} {hora} | {fuente} | filas={filas} | {detalle}\n")


def obtener_encabezados() -> dict:
    # Cargar el token de Socrata desde .env; si no existe se trabaja sin token.
    load_dotenv()
    token = os.getenv("SOCRATA_APP_TOKEN")
    if token:
        print("Usando SOCRATA_APP_TOKEN")
        return {"X-App-Token": token}
    print("Sin SOCRATA_APP_TOKEN: la API puede limitar las peticiones")
    return {}


def hacer_peticion(url: str, parametros: dict, encabezados: dict, timeout: int, reintentos: int) -> requests.Response:
    # Reintentar la petición si falla (red o servidor)
    for intento in range(1, reintentos + 1):
        try:
            respuesta = requests.get(url, params=parametros, headers=encabezados, timeout=timeout)
            respuesta.raise_for_status()
            return respuesta
        except requests.RequestException as error:
            print(f"  Error en intento {intento}/{reintentos}: {error}")
            if intento == reintentos:
                raise
            time.sleep(2 ** intento)


def contar_filas_api(dataset_id: str, filtro: str, config: dict, encabezados: dict) -> int:
    # Preguntar a la API cuántas filas cumplen el filtro, para validar la descarga al final.
    url = f"{config['api']['base_url']}/{dataset_id}.json"
    parametros = {"$select": "count(*) AS total"}
    if filtro:
        parametros["$where"] = filtro
    respuesta = hacer_peticion(url, parametros, encabezados, config["api"]["timeout"], config["api"]["reintentos"])
    return int(respuesta.json()[0]["total"])


def extraer_api(dataset_id: str, filtro: str, columnas: str, config: dict) -> pd.DataFrame:
    print(f"Empezando a extraer el dataset {dataset_id}")
    url = f"{config['api']['base_url']}/{dataset_id}.csv"
    limite = config["api"]["limite_por_pagina"]
    encabezados = obtener_encabezados()

    total_esperado = contar_filas_api(dataset_id, filtro, config, encabezados)
    print(f"Filas esperadas según la API: {total_esperado}")

    # Paginar con $limit y $offset hasta que la API devuelva una página vacía.
    # $order=:id mantiene el mismo orden entre páginas para no repetir ni saltar filas.
    paginas = []
    offset = 0
    while True:
        parametros = {"$limit": limite, "$offset": offset, "$order": ":id"}
        if filtro:
            parametros["$where"] = filtro
        if columnas:
            parametros["$select"] = columnas

        respuesta = hacer_peticion(url, parametros, encabezados, config["api"]["timeout"], config["api"]["reintentos"])
        # Leer todo como texto para no perder ceros a la izquierda en los códigos.
        pagina = pd.read_csv(io.StringIO(respuesta.text), dtype=str)
        if pagina.empty:
            break
        paginas.append(pagina)
        offset += len(pagina)
        print(f"  Página {len(paginas)}: {len(pagina)} filas (acumulado {offset})")

    df = pd.concat(paginas, ignore_index=True)
    print("Shape extraído:", df.shape)

    # Validar que se descargaron todas las filas que reporta la API.
    if len(df) != total_esperado:
        print(f"ADVERTENCIA: se esperaban {total_esperado} filas y se extrajeron {len(df)}")
    else:
        print("Validación OK: filas extraídas = filas esperadas")
    return df


def descargar_archivo(url: str, ruta: str, config: dict) -> None:
    print(f"Empezando a descargar {url}")
    # Descargar el archivo tal cual (sin modificarlo) para guardarlo en Bronze.
    respuesta = hacer_peticion(url, {}, {}, config["api"]["timeout"], config["api"]["reintentos"])
    os.makedirs(os.path.dirname(ruta), exist_ok=True)
    with open(ruta, "wb") as archivo:
        archivo.write(respuesta.content)
    print(f"Archivo guardado en {ruta} ({len(respuesta.content) / 1e6:.1f} MB)")


def guardar_bronze(df: pd.DataFrame, ruta: str) -> None:
    # Guardar los datos crudos sin transformar.
    os.makedirs(os.path.dirname(ruta), exist_ok=True)
    df.to_csv(ruta, index=False, encoding="utf-8")
    print(f"Guardado en Bronze: {ruta}")


def extraer_todo(config: dict) -> None:
    # Extraer las 4 fuentes de la API SODA.
    for nombre, fuente in config["sources"].items():
        if fuente["file_type"] != "api":
            continue
        print(f"\n===== Extracción: {nombre} =====")
        inicio = time.time()
        df = extraer_api(fuente["dataset_id"], fuente["filtro"], fuente["columnas"], config)
        guardar_bronze(df, fuente["path"])
        registrar_log(config, nombre, len(df), f"dataset={fuente['dataset_id']} segundos={time.time() - inicio:.1f}")

    # Descargar los archivos XLSX de población del DANE.
    print("\n===== Extracción: poblacion_dane =====")
    for nombre, archivo in config["sources"]["poblacion_dane"]["archivos"].items():
        descargar_archivo(archivo["url"], archivo["path"], config)
        df = pd.read_excel(archivo["path"], sheet_name=archivo["hoja"], header=archivo["fila_encabezado"], dtype=str)
        print(f"  {nombre}: {df.shape[0]} filas")
        registrar_log(config, f"poblacion_dane_{nombre}", len(df), f"url={archivo['url']}")
