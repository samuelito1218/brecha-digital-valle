import os

import pandas as pd


def cargar_duckdb(config: dict) -> None:
    print("Empezando a cargar las tablas Gold en DuckDB")
    try:
        import duckdb
    except ImportError:
        print("duckdb no está instalado (pip install duckdb). Se omite la carga.")
        return

    ruta_db = config["paths"]["duckdb"]
    os.makedirs(os.path.dirname(ruta_db), exist_ok=True)
    conexion = duckdb.connect(ruta_db)

    for nombre, ruta in config["gold"].items():
        # Leer con pandas forzando cod_mpio como texto, para no perder los ceros a la izquierda.
        df = pd.read_csv(ruta, dtype={"cod_mpio": str})
        conexion.register("df_temporal", df)
        conexion.execute(f"CREATE OR REPLACE TABLE {nombre} AS SELECT * FROM df_temporal")
        conexion.unregister("df_temporal")
        filas = conexion.execute(f"SELECT COUNT(*) FROM {nombre}").fetchone()[0]
        print(f"  Tabla {nombre}: {filas} filas")

    # Consulta de ejemplo: los 5 municipios más prioritarios y su conectividad.
    print("Consulta de ejemplo: top 5 municipios prioritarios")
    consulta = """
        SELECT r.posicion, r.municipio, r.indice, m.accesos_residenciales_por_100_hab, m.punt_global_prom
        FROM ranking_priorizacion r
        JOIN municipio_anio m ON r.cod_mpio = m.cod_mpio AND r.anio = m.anio
        ORDER BY r.posicion
        LIMIT 5
    """
    print(conexion.execute(consulta).df())
    conexion.close()
    print(f"Base de datos guardada en {ruta_db}")
