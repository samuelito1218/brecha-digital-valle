import pandas as pd

from src.transform.validaciones import resumen_nulos, validar_municipios


def limpiar_men(df: pd.DataFrame, config: dict) -> pd.DataFrame:
    print("Empezando a limpiar los datos del MEN")
    print("Shape inicial:", df.shape)

    # Corregir nombres de columnas: la API reemplaza tildes y ñ por "_" (a_o, deserci_n...).
    df = df.rename(columns={
        "a_o": "anio",
        "c_digo_municipio": "cod_mpio",
        "poblaci_n_5_16": "poblacion_5_16",
        "tasa_matriculaci_n_5_16": "tasa_matriculacion_5_16",
        "tama_o_promedio_de_grupo": "tamano_promedio_grupo",
        "deserci_n": "desercion",
        "aprobaci_n": "aprobacion",
        "reprobaci_n": "reprobacion",
    })

    # Eliminar columnas irrelevantes: departamento (siempre Valle), ETC y los desagregados
    # por nivel (transición, primaria...), porque el análisis usa los totales municipales.
    columnas = [
        "anio", "cod_mpio", "municipio", "poblacion_5_16", "tasa_matriculacion_5_16",
        "cobertura_neta", "cobertura_bruta", "cobertura_neta_media", "tamano_promedio_grupo",
        "sedes_conectadas_a_internet", "desercion", "aprobacion", "reprobacion", "repitencia",
    ]
    df = df[columnas].copy()

    # Normalizar el código DIVIPOLA a texto de 5 dígitos y el año a entero.
    df["cod_mpio"] = df["cod_mpio"].str.strip().str.zfill(5)
    df["anio"] = pd.to_numeric(df["anio"], errors="coerce").astype("Int64")

    # Estandarizar texto.
    df["municipio"] = df["municipio"].str.strip().str.lower()

    # Convertir los indicadores de texto a numérico (por si alguno trae coma decimal).
    for columna in columnas[3:]:
        df[columna] = pd.to_numeric(df[columna].str.replace(",", ".", regex=False), errors="coerce")

    # Eliminar duplicados según la llave natural (anio, cod_mpio).
    antes = len(df)
    df = df.drop_duplicates(subset=["anio", "cod_mpio"], keep="last").reset_index(drop=True)
    print(f"Duplicados eliminados por (anio, cod_mpio): {antes - len(df)}")

    # Nulos: NO se imputan. Un municipio sin dato queda nulo para no inventar valores.
    # sedes_conectadas_a_internet viene vacía desde 2018 en la fuente (se documenta en el README).
    resumen_nulos(df, "MEN")
    print("Años con sedes_conectadas_a_internet:",
          sorted(df.loc[df["sedes_conectadas_a_internet"].notna(), "anio"].unique().tolist()))

    # Outliers: la cobertura bruta > 100% es válida (incluye estudiantes en extraedad), no se elimina.
    print("Filas con cobertura_bruta > 100:", (df["cobertura_bruta"] > 100).sum(), "(válidas, no son outliers)")

    validar_municipios(df, "MEN", config)
    print("Shape final:", df.shape)
    print(df.dtypes)
    return df


def limpiar_saber11(df: pd.DataFrame, config: dict) -> pd.DataFrame:
    print("Empezando a limpiar los datos de Saber 11")
    print("Shape inicial:", df.shape)

    # Renombrar a snake_case en español.
    df = df.rename(columns={
        "cole_cod_mcpio_ubicacion": "cod_mpio",
        "cole_mcpio_ubicacion": "municipio",
        "cole_area_ubicacion": "zona",
        "cole_naturaleza": "naturaleza",
        "fami_estratovivienda": "estrato",
        "fami_tienecomputador": "tiene_computador",
        "fami_tieneinternet": "tiene_internet",
    })

    # Eliminar duplicados por la llave natural estu_consecutivo.
    # La API devuelve varias veces a los mismos estudiantes (sobre todo en 20194 y 20224).
    antes = len(df)
    duplicados_exactos = df.duplicated().sum()
    df = df.drop_duplicates(subset=["estu_consecutivo"], keep="first")
    print(f"Duplicados eliminados por estu_consecutivo: {antes - len(df)} "
          f"(de ellos {duplicados_exactos} eran filas idénticas)")

    # Separar periodo (AAAAS) en anio y semestre, y filtrar desde 20142,
    # porque antes el puntaje global tenía otra escala y no es comparable.
    df["periodo"] = pd.to_numeric(df["periodo"], errors="coerce").astype("Int64")
    antes = len(df)
    df = df[df["periodo"] >= config["constant"]["periodo_minimo_saber11"]].copy()
    print(f"Filas eliminadas por periodo < {config['constant']['periodo_minimo_saber11']}: {antes - len(df)}")
    df["anio"] = (df["periodo"] // 10).astype("Int64")
    df["semestre"] = (df["periodo"] % 10).astype("Int64")

    # Normalizar el código DIVIPOLA a texto de 5 dígitos.
    df["cod_mpio"] = df["cod_mpio"].str.strip().str.zfill(5)

    # Estandarizar texto.
    for columna in ["municipio", "zona", "naturaleza", "estrato", "tiene_computador", "tiene_internet"]:
        df[columna] = df[columna].str.strip().str.lower()
    print(df["zona"].value_counts(dropna=False))

    # Convertir categóricas "si"/"no" a 1/0. Los vacíos quedan nulos (no se sabe la respuesta).
    for columna in ["tiene_computador", "tiene_internet"]:
        df[columna] = df[columna].map({"si": 1, "no": 0}).astype("Int64")
        print(df[columna].value_counts(dropna=False))

    # Convertir naturaleza del colegio a 1 = oficial, 0 = no oficial.
    df["colegio_oficial"] = df["naturaleza"].map({"oficial": 1, "no oficial": 0}).astype("Int64")

    # Convertir estrato a número: "estrato 3" -> 3; "sin estrato" -> 0 (categoría propia, no es nulo).
    print(df["estrato"].value_counts(dropna=False))
    df["estrato"] = df["estrato"].replace({"sin estrato": "0"}).str.extract(r"(\d)", expand=False)
    df["estrato"] = pd.to_numeric(df["estrato"], errors="coerce").astype("Int64")

    # Convertir el puntaje global a número y validar el rango 0-500 (outliers imposibles -> nulo).
    df["punt_global"] = pd.to_numeric(df["punt_global"], errors="coerce")
    fuera_rango = ((df["punt_global"] < 0) | (df["punt_global"] > 500)).sum()
    df.loc[(df["punt_global"] < 0) | (df["punt_global"] > 500), "punt_global"] = pd.NA
    print("Puntajes fuera del rango 0-500:", fuera_rango)

    # Eliminar filas sin municipio o sin puntaje: no se pueden agregar ni imputar.
    antes = len(df)
    df = df.dropna(subset=["cod_mpio", "punt_global"])
    print(f"Filas eliminadas sin municipio o sin puntaje: {antes - len(df)}")

    # Eliminar columnas irrelevantes (naturaleza ya quedó en colegio_oficial).
    df = df[[
        "estu_consecutivo", "periodo", "anio", "semestre", "cod_mpio", "municipio", "zona",
        "colegio_oficial", "estrato", "tiene_computador", "tiene_internet", "punt_global",
    ]]

    resumen_nulos(df, "Saber 11")
    print("Estudiantes por periodo:")
    print(df["periodo"].value_counts().sort_index())
    validar_municipios(df, "Saber 11", config)
    print("Shape final:", df.shape)
    print(df.dtypes)
    return df
