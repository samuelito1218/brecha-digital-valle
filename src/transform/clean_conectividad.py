import pandas as pd

from src.transform.validaciones import resumen_nulos, validar_municipios


def limpiar_internet_fijo(df: pd.DataFrame, config: dict) -> pd.DataFrame:
    print("Empezando a limpiar los datos de internet fijo")
    print("Shape inicial:", df.shape)

    # Eliminar filas idénticas en todas las columnas (antes de quitar columnas,
    # para no confundir filas que solo difieren en una columna eliminada).
    # Solo aparecen desde 2022 (cuando cambió el formato de reporte) y pesan ~0,3% de los accesos.
    antes = len(df)
    df = df.drop_duplicates()
    print(f"Filas duplicadas eliminadas: {antes - len(df)}")

    # Renombrar a snake_case en español.
    df = df.rename(columns={"anno": "anio", "cod_municipio": "cod_mpio", "no_de_accesos": "accesos"})

    # Eliminar columnas irrelevantes: el departamento siempre es Valle (76)
    # y la velocidad de subida no se usa en el análisis.
    df = df.drop(columns=["cod_departamento", "departamento", "velocidad_subida"])

    # Normalizar tipos: código DIVIPOLA como texto de 5 dígitos, año y trimestre enteros.
    df["cod_mpio"] = df["cod_mpio"].str.strip().str.zfill(5)
    df["anio"] = pd.to_numeric(df["anio"], errors="coerce").astype("Int64")
    df["trimestre"] = pd.to_numeric(df["trimestre"], errors="coerce").astype("Int64")

    # Convertir la coma decimal a punto ("15,00" -> 15.0) y el texto a número.
    df["velocidad_bajada_mbps"] = pd.to_numeric(df["velocidad_bajada"].str.replace(",", ".", regex=False), errors="coerce")
    df["accesos"] = pd.to_numeric(df["accesos"], errors="coerce").astype("Int64")
    df = df.drop(columns=["velocidad_bajada"])

    # Estandarizar texto.
    for columna in ["proveedor", "municipio", "segmento", "tecnologia"]:
        df[columna] = df[columna].str.strip().str.lower()
    print(df["segmento"].value_counts())

    # Nueva columna categórica 1/0: el acceso es residencial (estratos 1-6 o "sin estratificar")
    # o no (corporativo o uso propio del operador).
    # "sin estratificar" se cuenta como residencial: en municipios rurales algunos operadores reportan
    # así todos sus hogares (p. ej. Obando 2022: 874 de 940 accesos). Excluirlo subestimaría lo rural.
    df["es_residencial"] = (df["segmento"].str.startswith("residencial") | (df["segmento"] == "sin estratificar")).astype(int)

    # Nulos y valores negativos: un acceso sin cantidad no se puede imputar, se elimina.
    antes = len(df)
    df = df.dropna(subset=["anio", "trimestre", "cod_mpio", "accesos"])
    df = df[df["accesos"] >= 0]
    print(f"Filas eliminadas por nulos o accesos negativos: {antes - len(df)}")

    resumen_nulos(df, "Internet fijo")
    print("Trimestres por año:")
    print(df.groupby("anio")["trimestre"].max())
    validar_municipios(df, "Internet fijo", config)
    print("Shape final:", df.shape)
    print(df.dtypes)
    return df.reset_index(drop=True)


def limpiar_cobertura_movil(df: pd.DataFrame, config: dict) -> pd.DataFrame:
    print("Empezando a limpiar los datos de cobertura móvil")
    print("Shape inicial:", df.shape)

    # Renombrar a snake_case y corregir el error tipográfico "cobertuta_4g".
    df = df.rename(columns={
        "a_o": "anio",
        "cod_municipio": "cod_mpio",
        "cobertuta_4g": "cobertura_4g",
        "cobertura_hspa_hspa_dc": "cobertura_hspa",
    })

    # Eliminar columnas irrelevantes (departamento constante).
    df = df.drop(columns=["cod_departamento", "departamento"])

    # Normalizar tipos.
    df["cod_mpio"] = df["cod_mpio"].str.strip().str.zfill(5)
    df["anio"] = pd.to_numeric(df["anio"], errors="coerce").astype("Int64")
    df["trimestre"] = pd.to_numeric(df["trimestre"], errors="coerce").astype("Int64")

    # Estandarizar texto.
    for columna in ["proveedor", "municipio", "centro_poblado"]:
        df[columna] = df[columna].str.strip().str.lower().str.replace(r"\s+", " ", regex=True)

    # El código de centro poblado "0" significa "sin centro poblado": es un valor faltante, no un código real.
    df["cod_centro_poblado"] = df["cod_centro_poblado"].str.strip()
    print("Filas con cod_centro_poblado = 0:", (df["cod_centro_poblado"] == "0").sum())
    df.loc[df["cod_centro_poblado"] == "0", "cod_centro_poblado"] = pd.NA

    # Convertir las categóricas "S"/"N" a 1/0.
    indicadores = ["cabecera_municipal", "cobertura_2g", "cobertura_3g", "cobertura_hspa",
                   "cobertura_4g", "cobertura_lte", "cobertura_5g"]
    for columna in indicadores:
        df[columna] = df[columna].str.strip().str.upper().map({"S": 1, "N": 0}).astype("Int64")

    # Corregir el cambio de formato: hasta 2020 el 4G se reportaba en cobertura_lte
    # y desde 2021 en cobertura_4g (nunca ambas). Se unifican en una sola columna.
    print(pd.crosstab(df["anio"], [df["cobertura_4g"], df["cobertura_lte"]]))
    df["tiene_4g"] = df[["cobertura_4g", "cobertura_lte"]].max(axis=1).astype("Int64")
    df = df.drop(columns=["cobertura_4g", "cobertura_lte"])

    # Eliminar duplicados por la llave natural (anio, trimestre, municipio, centro poblado, proveedor).
    antes = len(df)
    df = df.drop_duplicates(subset=["anio", "trimestre", "cod_mpio", "cod_centro_poblado", "centro_poblado", "proveedor"])
    print(f"Duplicados eliminados: {antes - len(df)}")

    resumen_nulos(df, "Cobertura móvil")
    print("Centros poblados distintos por año (cambia la forma de reporte en 2022):")
    print(df.groupby("anio")["cod_centro_poblado"].nunique())
    validar_municipios(df, "Cobertura móvil", config)
    print("Shape final:", df.shape)
    print(df.dtypes)
    return df.reset_index(drop=True)
