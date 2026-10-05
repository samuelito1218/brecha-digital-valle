-- ============================================================
-- DIMENSIÓN MUNICIPIO
-- ============================================================

CREATE TABLE IF NOT EXISTS dim_municipio (
    cod_mpio INTEGER PRIMARY KEY,
    municipio VARCHAR(150) NOT NULL
);


-- ============================================================
-- BRECHA URBANO-RURAL
-- ============================================================

CREATE TABLE IF NOT EXISTS brecha_urbano_rural (
    id BIGSERIAL PRIMARY KEY,

    nivel VARCHAR(50),
    cod_mpio INTEGER,
    anio INTEGER,
    zona VARCHAR(50),

    n_estudiantes INTEGER,
    muestra_suficiente BOOLEAN,

    pct_con_internet NUMERIC(10,4),
    pct_con_computador NUMERIC(10,4),
    pct_internet_si_tiene_pc NUMERIC(10,4),
    pct_internet_si_no_tiene_pc NUMERIC(10,4),

    punt_global_prom NUMERIC(10,4),

    CONSTRAINT fk_brecha_municipio
        FOREIGN KEY (cod_mpio)
        REFERENCES dim_municipio(cod_mpio),

    CONSTRAINT uq_brecha_municipio_anio_zona
        UNIQUE (cod_mpio, anio, zona)
);
-- ============================================================
-- MUNICIPIO - AÑO
-- ============================================================

CREATE TABLE IF NOT EXISTS municipio_anio (
    id BIGSERIAL PRIMARY KEY,

    cod_mpio INTEGER NOT NULL,
    municipio VARCHAR(150),
    anio INTEGER,

    poblacion_total BIGINT,
    pct_poblacion_rural NUMERIC(10,4),

    trimestre_fijo VARCHAR(50),

    accesos_fijos_total BIGINT,
    accesos_fijos_residenciales BIGINT,

    accesos_por_100_hab NUMERIC(10,4),
    accesos_residenciales_por_100_hab NUMERIC(10,4),

    operadores_movil INTEGER,
    operadores_4g INTEGER,

    pct_centros_poblados_4g NUMERIC(10,4),

    cobertura_neta NUMERIC(10,4),
    cobertura_bruta NUMERIC(10,4),

    desercion NUMERIC(10,4),

    sedes_conectadas_a_internet INTEGER,

    saber11_anio_completo INTEGER,
    n_estudiantes_saber11 INTEGER,

    pct_estudiantes_con_internet NUMERIC(10,4),
    pct_estudiantes_con_computador NUMERIC(10,4),

    punt_global_prom NUMERIC(10,4),

    CONSTRAINT fk_municipio_anio_municipio
        FOREIGN KEY (cod_mpio)
        REFERENCES dim_municipio(cod_mpio),

    CONSTRAINT uq_municipio_anio
        UNIQUE (cod_mpio, anio)
);
-- ============================================================
-- RANKING DE PRIORIZACIÓN
-- ============================================================

CREATE TABLE IF NOT EXISTS ranking_priorizacion (
    id BIGSERIAL PRIMARY KEY,

    cod_mpio INTEGER NOT NULL,
    municipio VARCHAR(150),
    anio INTEGER,

    accesos_residenciales_por_100_hab NUMERIC(10,4),
    operadores_4g INTEGER,
    pct_estudiantes_con_internet NUMERIC(10,4),
    punt_global_prom NUMERIC(10,4),
    cobertura_neta NUMERIC(10,4),
    desercion NUMERIC(10,4),

    accesos_residenciales_por_100_hab_norm NUMERIC(10,6),
    operadores_4g_norm NUMERIC(10,6),
    pct_estudiantes_con_internet_norm NUMERIC(10,6),
    punt_global_prom_norm NUMERIC(10,6),
    cobertura_neta_norm NUMERIC(10,6),
    desercion_norm NUMERIC(10,6),

    variables_con_dato INTEGER,

    indice NUMERIC(12,6),

    posicion INTEGER,

    nivel VARCHAR(50),

    prioritario BOOLEAN,

    CONSTRAINT fk_ranking_municipio
        FOREIGN KEY (cod_mpio)
        REFERENCES dim_municipio(cod_mpio),

    CONSTRAINT uq_ranking_municipio_anio
        UNIQUE (cod_mpio, anio)
);
-- ============================================================
-- ÍNDICES
-- ============================================================

CREATE INDEX IF NOT EXISTS idx_brecha_cod_mpio
    ON brecha_urbano_rural(cod_mpio);

CREATE INDEX IF NOT EXISTS idx_brecha_anio
    ON brecha_urbano_rural(anio);

CREATE INDEX IF NOT EXISTS idx_municipio_anio_cod_mpio
    ON municipio_anio(cod_mpio);

CREATE INDEX IF NOT EXISTS idx_municipio_anio_anio
    ON municipio_anio(anio);

CREATE INDEX IF NOT EXISTS idx_ranking_cod_mpio
    ON ranking_priorizacion(cod_mpio);

CREATE INDEX IF NOT EXISTS idx_ranking_anio
    ON ranking_priorizacion(anio);

CREATE INDEX IF NOT EXISTS idx_ranking_posicion
    ON ranking_priorizacion(posicion);