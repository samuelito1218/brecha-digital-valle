import pandas as pd

from src.transform.clean_conectividad import limpiar_cobertura_movil, limpiar_internet_fijo
from src.transform.clean_educacion import limpiar_men, limpiar_saber11
from src.transform.gold_data import agregar_internet_fijo, construir_ranking

# Configuración mínima para las pruebas (no se descarga nada).
CONFIG = {"constant": {"cod_departamento": "76", "total_municipios": 42, "periodo_minimo_saber11": 20142,
                       "anio_ranking": 2022, "max_pct_nulos_indice": 20}}


def test_internet_fijo_coma_decimal_duplicados_y_residencial():
    df = pd.DataFrame({
        "anno": ["2022"] * 4, "trimestre": ["4"] * 4, "proveedor": ["A", "A", "B", "C"],
        "cod_departamento": ["76"] * 4, "departamento": ["VALLE"] * 4,
        "cod_municipio": ["76001"] * 4, "municipio": ["CALI "] * 4,
        "segmento": ["RESIDENCIAL - ESTRATO 1", "RESIDENCIAL - ESTRATO 1", "CORPORATIVO", "SIN ESTRATIFICAR"],
        "tecnologia": ["XDSL"] * 4, "velocidad_bajada": ["15,50", "15,50", "100,00", "10,00"],
        "velocidad_subida": ["1,00", "1,00", "1,00", "1,00"], "no_de_accesos": ["10", "10", "5", "7"],
    })
    limpio = limpiar_internet_fijo(df, CONFIG)
    # La fila 2 es idéntica a la 1 y se elimina.
    assert len(limpio) == 3
    assert limpio["velocidad_bajada_mbps"].iloc[0] == 15.5
    # "sin estratificar" cuenta como residencial; corporativo no.
    assert limpio["es_residencial"].tolist() == [1, 0, 1]
    agregado = agregar_internet_fijo(limpio, CONFIG)
    assert agregado.loc[0, "accesos_fijos_total"] == 22
    assert agregado.loc[0, "accesos_fijos_residenciales"] == 17


def test_cobertura_movil_unifica_lte_y_4g():
    df = pd.DataFrame({
        "a_o": ["2020", "2022"], "trimestre": ["4", "4"], "proveedor": ["A", "A"],
        "cod_departamento": ["76", "76"], "departamento": ["VALLE", "VALLE"],
        "cod_municipio": ["76001", "76001"], "municipio": ["CALI", "CALI"],
        "cabecera_municipal": ["S", "N"], "cod_centro_poblado": ["76001000", "0"],
        "centro_poblado": ["CALI", "SIN CENTRO POBLADO"],
        "cobertura_2g": ["S", "S"], "cobertura_3g": ["S", "S"], "cobertura_hspa_hspa_dc": ["S", "N"],
        "cobertuta_4g": ["N", "S"], "cobertura_lte": ["S", "N"], "cobertura_5g": ["N", "N"],
    })
    limpio = limpiar_cobertura_movil(df, CONFIG)
    assert limpio["tiene_4g"].tolist() == [1, 1]
    # El código "0" es un valor faltante.
    assert limpio["cod_centro_poblado"].isna().tolist() == [False, True]


def test_men_codigo_y_nombres():
    columnas = ["a_o", "c_digo_municipio", "municipio", "poblaci_n_5_16", "tasa_matriculaci_n_5_16", "cobertura_neta",
                "cobertura_bruta", "cobertura_neta_media", "tama_o_promedio_de_grupo", "sedes_conectadas_a_internet",
                "deserci_n", "aprobaci_n", "reprobaci_n", "repitencia"]
    df = pd.DataFrame([["2022", "76001", "Cali", "1", "1", "80.5", "105", "1", None, None, "5", "1", "1", "1"]] * 2,
                      columns=columnas)
    limpio = limpiar_men(df, CONFIG)
    assert len(limpio) == 1
    assert limpio.loc[0, "cod_mpio"] == "76001"
    # Cobertura bruta > 100 es válida y no se modifica.
    assert limpio.loc[0, "cobertura_bruta"] == 105


def test_saber11_periodo_duplicados_y_si_no():
    df = pd.DataFrame({
        "periodo": ["20224", "20224", "20132"], "estu_consecutivo": ["A", "A", "B"],
        "cole_cod_mcpio_ubicacion": ["76001", "76001", "76001"], "cole_mcpio_ubicacion": ["CALI"] * 3,
        "cole_area_ubicacion": ["RURAL", "RURAL", "URBANO"], "cole_naturaleza": ["OFICIAL"] * 3,
        "fami_estratovivienda": ["Estrato 2", "Estrato 2", "Sin Estrato"],
        "fami_tienecomputador": ["Si", "Si", "No"], "fami_tieneinternet": ["No", "No", "Si"],
        "punt_global": ["250", "250", "300"],
    })
    limpio = limpiar_saber11(df, CONFIG)
    # Se elimina el duplicado y el periodo 20132 (anterior a 20142).
    assert len(limpio) == 1
    fila = limpio.iloc[0]
    assert (fila["anio"], fila["semestre"], fila["estrato"]) == (2022, 4, 2)
    assert (fila["tiene_computador"], fila["tiene_internet"]) == (1, 0)


def test_ranking_invierte_desercion_y_excluye_nulos():
    df = pd.DataFrame({
        "cod_mpio": ["76001", "76002", "76003"], "municipio": ["a", "b", "c"], "anio": [2022] * 3,
        "accesos_residenciales_por_100_hab": [10, 5, 0], "operadores_4g": [4, 4, 3],
        "pct_estudiantes_con_internet": [90, 60, 30], "punt_global_prom": [260, 240, 220],
        "cobertura_neta": [90, 80, 70], "desercion": [2, 5, 8], "sedes_conectadas_a_internet": [None, None, None],
    })
    ranking = construir_ranking(df, CONFIG)
    assert "sedes_conectadas_a_internet_norm" not in ranking.columns
    # Menor deserción = valor normalizado 1 (mejor situación).
    assert ranking.set_index("municipio").loc["a", "desercion_norm"] == 1
    assert ranking.loc[0, "municipio"] == "c"
    assert ranking.loc[0, "posicion"] == 1
