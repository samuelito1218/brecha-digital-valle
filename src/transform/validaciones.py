import pandas as pd


def resumen_nulos(df: pd.DataFrame, nombre: str) -> None:
    # Mostrar cuántos nulos quedan por columna.
    nulos = df.isnull().sum()
    print(f"Nulos por columna en {nombre}:")
    print(nulos[nulos > 0] if nulos.sum() > 0 else "  sin nulos")


def validar_municipios(df: pd.DataFrame, nombre: str, config: dict) -> None:
    # Validar que aparezcan los 42 municipios del Valle y que el código tenga 5 dígitos.
    total = config["constant"]["total_municipios"]
    codigos = set(df["cod_mpio"].dropna().unique())
    mal_formados = [c for c in codigos if len(c) != 5 or not c.startswith(config["constant"]["cod_departamento"])]
    print(f"Municipios presentes en {nombre}: {len(codigos)} de {total}")
    if mal_formados:
        print(f"ADVERTENCIA: códigos mal formados o de otro departamento: {mal_formados}")
    if len(codigos) < total:
        print(f"ADVERTENCIA: faltan {total - len(codigos)} municipios en {nombre}")
