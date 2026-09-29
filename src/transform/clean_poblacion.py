import pandas as pd

from src.transform.validaciones import resumen_nulos, validar_municipios


def leer_poblacion_dane(archivo: dict) -> pd.DataFrame:
    print(f"Leyendo {archivo['path']}")
    # El XLSX del DANE trae varias filas de título antes del encabezado real.
    df = pd.read_excel(archivo["path"], sheet_name=archivo["hoja"], header=archivo["fila_encabezado"], dtype=str)
    print("Shape leído:", df.shape)
    print("Columnas:", df.columns.tolist())
    return df


def limpiar_poblacion(df_retro: pd.DataFrame, df_proy: pd.DataFrame, config: dict) -> pd.DataFrame:
    print("Empezando a limpiar la población del DANE")

    # Los dos archivos nombran distinto la columna de población ("Población" y "TOTAL").
    # Se renombran al mismo esquema para poder unirlos en una sola serie.
    renombrar = {"DP": "cod_depto", "MPIO": "cod_mpio", "DPMP": "municipio", "AÑO": "anio",
                 "ÁREA GEOGRÁFICA": "area", "Población": "poblacion", "TOTAL": "poblacion"}
    df_retro = df_retro.rename(columns=renombrar)
    df_proy = df_proy.rename(columns=renombrar)
    df_retro["serie"] = "retroproyeccion"
    df_proy["serie"] = "proyeccion"

    # Unir retroproyección (2005-2017) y proyección (2018-2042), ambas con base en el Censo 2018.
    columnas = ["cod_depto", "cod_mpio", "municipio", "anio", "area", "poblacion", "serie"]
    df = pd.concat([df_retro[columnas], df_proy[columnas]], ignore_index=True)
    print("Shape unido:", df.shape)

    # Eliminar filas vacías (el XLSX tiene filas en blanco y notas al pie).
    antes = len(df)
    df = df.dropna(subset=["cod_mpio", "anio", "poblacion"])
    print(f"Filas vacías o de notas eliminadas: {antes - len(df)}")

    # Filtrar solo el Valle del Cauca (código 76).
    df = df[df["cod_depto"].str.strip() == config["constant"]["cod_departamento"]].copy()
    print("Filas del Valle:", len(df))

    # Normalizar tipos: código de 5 dígitos como texto, año y población enteros.
    df["cod_mpio"] = df["cod_mpio"].str.strip().str.zfill(5)
    df["anio"] = pd.to_numeric(df["anio"], errors="coerce").astype("Int64")
    df["poblacion"] = pd.to_numeric(df["poblacion"], errors="coerce").round().astype("Int64")

    # Normalizar el área a 3 categorías: total, cabecera y rural (centros poblados + rural disperso).
    df["area"] = df["area"].str.strip().str.lower()
    print(df["area"].value_counts())
    df["area"] = df["area"].map({"total": "total", "cabecera municipal": "cabecera",
                                 "centros poblados y rural disperso": "rural"})
    df["municipio"] = df["municipio"].str.strip().str.lower()

    # Eliminar duplicados por la llave (cod_mpio, anio, area).
    antes = len(df)
    df = df.drop_duplicates(subset=["cod_mpio", "anio", "area"])
    print(f"Duplicados eliminados: {antes - len(df)}")

    # Validar que total = cabecera + rural en todas las filas.
    pivote = df.pivot_table(index=["cod_mpio", "anio"], columns="area", values="poblacion", aggfunc="sum")
    diferencias = (pivote["total"] - pivote["cabecera"] - pivote["rural"]).abs()
    print("Filas donde total != cabecera + rural:", (diferencias > 1).sum())

    df = df.drop(columns=["cod_depto"])
    resumen_nulos(df, "Población DANE")
    print("Años:", df["anio"].min(), "-", df["anio"].max())
    validar_municipios(df, "Población DANE", config)
    print("Shape final:", df.shape)
    return df.sort_values(["cod_mpio", "anio", "area"]).reset_index(drop=True)
