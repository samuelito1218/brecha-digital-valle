import pandas as pd


def unir_con_control(izquierda: pd.DataFrame, derecha: pd.DataFrame, nombre: str) -> pd.DataFrame:
    # Unir por (cod_mpio, anio) validando que la relación sea 1 a 1,
    # e imprimir filas antes y después para comprobar que no se pierden ni se duplican municipios.
    filas_antes = len(izquierda)
    df = pd.merge(izquierda, derecha, on=["cod_mpio", "anio"], how="left", validate="one_to_one")
    print(f"  merge con {nombre}: {filas_antes} -> {len(df)} filas, "
          f"{df['cod_mpio'].nunique()} municipios")
    return df


def anios_completos_saber11(saber: pd.DataFrame) -> list:
    # Un año está completo si tiene el periodo de calendario B o el periodo anual (semestre 2 o 4).
    # Los años que solo tienen calendario A (2018, 2020, 2021) cubren 10-15 municipios y están sesgados.
    anios = sorted(saber.loc[saber["semestre"] != 1, "anio"].unique().tolist())
    print("Años completos de Saber 11:", anios)
    return anios


def construir_dim_municipio(poblacion: pd.DataFrame) -> pd.DataFrame:
    print("Construyendo dim_municipio")
    # Tomar el nombre oficial del DANE para cada código DIVIPOLA.
    dim = poblacion[["cod_mpio", "municipio"]].drop_duplicates(subset=["cod_mpio"])
    dim = dim.sort_values("cod_mpio").reset_index(drop=True)
    print("Shape:", dim.shape)
    return dim


def agregar_internet_fijo(fijo: pd.DataFrame, config: dict) -> pd.DataFrame:
    print("Agregando internet fijo a municipio-año")
    # Los accesos son un corte (stock), no se pueden sumar entre trimestres.
    # Se toma el trimestre 4; si un año no lo tiene, el último disponible.
    ultimo = fijo.groupby("anio")["trimestre"].max().rename("trimestre_usado").reset_index()
    for _, fila in ultimo.iterrows():
        if fila["trimestre_usado"] != 4:
            print(f"  Aviso: {fila['anio']} no tiene T4, se usa T{fila['trimestre_usado']}")
    fijo = fijo.merge(ultimo, on="anio")
    fijo = fijo[fijo["trimestre"] == fijo["trimestre_usado"]]

    # Sumar accesos totales y residenciales por municipio y año.
    fijo["accesos_residenciales"] = fijo["accesos"] * fijo["es_residencial"]
    df = fijo.groupby(["cod_mpio", "anio"]).agg(
        accesos_fijos_total=("accesos", "sum"),
        accesos_fijos_residenciales=("accesos_residenciales", "sum"),
        trimestre_fijo=("trimestre_usado", "first"),
    ).reset_index()
    print("Shape:", df.shape)
    return df


def agregar_cobertura_movil(movil: pd.DataFrame) -> pd.DataFrame:
    print("Agregando cobertura móvil a municipio-año")
    # Igual que en internet fijo: se usa el último trimestre de cada año.
    ultimo = movil.groupby("anio")["trimestre"].transform("max")
    movil = movil[movil["trimestre"] == ultimo]

    # Número de operadores que ofrecen 4G en alguna parte del municipio.
    con_4g = movil[movil["tiene_4g"] == 1]
    operadores = con_4g.groupby(["cod_mpio", "anio"])["proveedor"].nunique().rename("operadores_4g")
    total_operadores = movil.groupby(["cod_mpio", "anio"])["proveedor"].nunique().rename("operadores_movil")

    # % de centros poblados (fuera de la cabecera) con 4G de al menos un operador.
    rural = movil[(movil["cabecera_municipal"] == 0) & movil["cod_centro_poblado"].notna()]
    por_centro = rural.groupby(["cod_mpio", "anio", "cod_centro_poblado"])["tiene_4g"].max().reset_index()
    pct_centros = (por_centro.groupby(["cod_mpio", "anio"])["tiene_4g"].mean() * 100).rename("pct_centros_poblados_4g")

    df = pd.concat([total_operadores, operadores, pct_centros], axis=1).reset_index()
    # Si un municipio aparece en la fuente pero ningún operador tiene 4G, son 0 operadores (no es nulo).
    df["operadores_4g"] = df["operadores_4g"].fillna(0).astype(int)
    print("Shape:", df.shape)
    return df


def agregar_saber11(saber: pd.DataFrame, anios_completos: list) -> pd.DataFrame:
    print("Agregando Saber 11 a municipio-año")
    # Solo años completos: en los demás las métricas quedan nulas en la tabla integrada.
    saber = saber[saber["anio"].isin(anios_completos)]
    df = saber.groupby(["cod_mpio", "anio"]).agg(
        n_estudiantes_saber11=("estu_consecutivo", "count"),
        pct_estudiantes_con_internet=("tiene_internet", "mean"),
        pct_estudiantes_con_computador=("tiene_computador", "mean"),
        punt_global_prom=("punt_global", "mean"),
    ).reset_index()
    # Pasar proporciones a porcentaje (normalización de unidades).
    df["pct_estudiantes_con_internet"] = df["pct_estudiantes_con_internet"].astype(float) * 100
    df["pct_estudiantes_con_computador"] = df["pct_estudiantes_con_computador"].astype(float) * 100
    print("Shape:", df.shape)
    return df


def construir_brecha_urbano_rural(saber: pd.DataFrame, anios_completos: list, config: dict) -> pd.DataFrame:
    print("Construyendo brecha_urbano_rural")
    # Usar solo años completos y estudiantes con zona conocida.
    saber = saber[saber["anio"].isin(anios_completos) & saber["zona"].notna()].copy()
    saber["internet_con_pc"] = saber["tiene_internet"].where(saber["tiene_computador"] == 1)
    saber["internet_sin_pc"] = saber["tiene_internet"].where(saber["tiene_computador"] == 0)

    agregaciones = dict(
        n_estudiantes=("estu_consecutivo", "count"),
        pct_con_internet=("tiene_internet", "mean"),
        pct_con_computador=("tiene_computador", "mean"),
        pct_internet_si_tiene_pc=("internet_con_pc", "mean"),
        pct_internet_si_no_tiene_pc=("internet_sin_pc", "mean"),
        punt_global_prom=("punt_global", "mean"),
    )

    # Nivel municipal: municipio, año y zona.
    municipal = saber.groupby(["cod_mpio", "anio", "zona"]).agg(**agregaciones).reset_index()
    municipal["nivel"] = "municipio"

    # Nivel departamental: agregado del Valle por año y zona (código 76000, marcado con nivel).
    departamental = saber.groupby(["anio", "zona"]).agg(**agregaciones).reset_index()
    departamental["cod_mpio"] = "76000"
    departamental["nivel"] = "departamento"

    df = pd.concat([municipal, departamental], ignore_index=True)
    for columna in ["pct_con_internet", "pct_con_computador", "pct_internet_si_tiene_pc", "pct_internet_si_no_tiene_pc"]:
        df[columna] = (df[columna].astype(float) * 100).round(2)
    df["punt_global_prom"] = df["punt_global_prom"].round(2)

    # Marcar las celdas con pocos estudiantes: sus porcentajes son poco confiables.
    df["muestra_suficiente"] = (df["n_estudiantes"] >= config["constant"]["min_estudiantes_zona"]).astype(int)
    print("Celdas con muestra insuficiente:", (df["muestra_suficiente"] == 0).sum())

    df = df[["nivel", "cod_mpio", "anio", "zona", "n_estudiantes", "muestra_suficiente", "pct_con_internet",
             "pct_con_computador", "pct_internet_si_tiene_pc", "pct_internet_si_no_tiene_pc", "punt_global_prom"]]
    print("Shape:", df.shape)
    return df.sort_values(["nivel", "cod_mpio", "anio", "zona"]).reset_index(drop=True)


def construir_municipio_anio(dim: pd.DataFrame, silver: dict, anios_completos: list, config: dict) -> pd.DataFrame:
    print("Construyendo municipio_anio")
    anio_inicio = config["constant"]["anio_inicio"]
    anio_fin = config["constant"]["anio_fin"]

    # Base: todas las combinaciones municipio x año (42 x 6), para que ningún municipio desaparezca.
    anios = pd.DataFrame({"anio": list(range(anio_inicio, anio_fin + 1))})
    df = dim.merge(anios, how="cross")
    df["anio"] = df["anio"].astype("Int64")
    print(f"  base: {len(df)} filas ({df['cod_mpio'].nunique()} municipios x {len(anios)} años)")

    # Población total y % rural (DANE).
    poblacion = silver["poblacion"].pivot_table(index=["cod_mpio", "anio"], columns="area",
                                                values="poblacion", aggfunc="sum").reset_index()
    poblacion["pct_poblacion_rural"] = (poblacion["rural"] / poblacion["total"] * 100).round(2)
    poblacion = poblacion.rename(columns={"total": "poblacion_total"})[["cod_mpio", "anio", "poblacion_total", "pct_poblacion_rural"]]
    df = unir_con_control(df, poblacion, "población DANE")

    df = unir_con_control(df, agregar_internet_fijo(silver["internet_fijo"], config), "internet fijo")
    df = unir_con_control(df, agregar_cobertura_movil(silver["cobertura_movil"]), "cobertura móvil")

    men = silver["men_educacion"][["cod_mpio", "anio", "cobertura_neta", "cobertura_bruta", "desercion",
                                   "sedes_conectadas_a_internet"]]
    df = unir_con_control(df, men, "MEN")
    df = unir_con_control(df, agregar_saber11(silver["saber11"], anios_completos), "Saber 11")
    df["saber11_anio_completo"] = df["anio"].isin(anios_completos).astype(int)

    # KPIs nuevos: accesos por cada 100 habitantes (total y solo residenciales).
    df["accesos_por_100_hab"] = (df["accesos_fijos_total"] / df["poblacion_total"] * 100).round(2)
    df["accesos_residenciales_por_100_hab"] = (df["accesos_fijos_residenciales"] / df["poblacion_total"] * 100).round(2)

    columnas = [
        "cod_mpio", "municipio", "anio", "poblacion_total", "pct_poblacion_rural",
        "trimestre_fijo", "accesos_fijos_total", "accesos_fijos_residenciales",
        "accesos_por_100_hab", "accesos_residenciales_por_100_hab",
        "operadores_movil", "operadores_4g", "pct_centros_poblados_4g",
        "cobertura_neta", "cobertura_bruta", "desercion", "sedes_conectadas_a_internet",
        "saber11_anio_completo", "n_estudiantes_saber11", "pct_estudiantes_con_internet",
        "pct_estudiantes_con_computador", "punt_global_prom",
    ]
    df = df[columnas].round(2)
    print("Nulos por columna en municipio_anio:")
    print(df.isnull().sum()[df.isnull().sum() > 0])
    print("Shape:", df.shape)
    return df


def construir_ranking(municipio_anio: pd.DataFrame, config: dict) -> pd.DataFrame:
    anio = config["constant"]["anio_ranking"]
    print(f"Construyendo ranking_priorizacion para {anio}")
    df = municipio_anio[municipio_anio["anio"] == anio].copy()

    # Variables candidatas y su sentido: +1 = más es mejor, -1 = más es peor.
    # Se usa el acceso residencial (no el total) porque no se infla con accesos corporativos.
    variables = {
        "accesos_residenciales_por_100_hab": 1,
        "operadores_4g": 1,
        "pct_estudiantes_con_internet": 1,
        "punt_global_prom": 1,
        "cobertura_neta": 1,
        "desercion": -1,
        "sedes_conectadas_a_internet": 1,
    }

    # Excluir variables con demasiados nulos en el año elegido.
    usadas = []
    for variable in variables:
        pct_nulos = df[variable].isnull().mean() * 100
        if pct_nulos > config["constant"]["max_pct_nulos_indice"]:
            print(f"  Excluida {variable}: {pct_nulos:.0f}% nulos")
        else:
            usadas.append(variable)
            print(f"  Usada {variable}: {pct_nulos:.0f}% nulos")

    # Normalización min-max (0-1); en las variables donde más es peor se invierte (1 - x),
    # para que 1 siempre signifique mejor situación.
    for variable in usadas:
        minimo, maximo = df[variable].min(), df[variable].max()
        normalizada = (df[variable] - minimo) / (maximo - minimo)
        if variables[variable] == -1:
            normalizada = 1 - normalizada
        df[f"{variable}_norm"] = normalizada.round(4)

    # Índice = promedio simple (pesos iguales). Si a un municipio le falta una variable,
    # se promedian las que sí tiene (no se imputa).
    columnas_norm = [f"{v}_norm" for v in usadas]
    df["variables_con_dato"] = df[columnas_norm].notna().sum(axis=1)
    df["indice"] = df[columnas_norm].mean(axis=1).round(4)

    # Posición 1 = índice más bajo = municipio más prioritario.
    df["posicion"] = df["indice"].rank(method="min").astype(int)
    # Niveles por terciles del índice.
    df["nivel"] = pd.qcut(df["indice"], 3, labels=["bajo", "medio", "alto"]).astype(str)
    df["prioritario"] = (df["nivel"] == "bajo").astype(int)
    print(df["nivel"].value_counts())

    df = df[["cod_mpio", "municipio", "anio"] + usadas + columnas_norm +
            ["variables_con_dato", "indice", "posicion", "nivel", "prioritario"]]
    print("Shape:", df.shape)
    return df.sort_values("posicion").reset_index(drop=True)


def construir_gold(silver: dict, config: dict) -> dict:
    print("Empezando a construir las tablas Gold")
    anios_completos = anios_completos_saber11(silver["saber11"])
    dim = construir_dim_municipio(silver["poblacion"])
    brecha = construir_brecha_urbano_rural(silver["saber11"], anios_completos, config)
    municipio_anio = construir_municipio_anio(dim, silver, anios_completos, config)
    ranking = construir_ranking(municipio_anio, config)
    return {
        "dim_municipio": dim,
        "brecha_urbano_rural": brecha,
        "municipio_anio": municipio_anio,
        "ranking_priorizacion": ranking,
    }
