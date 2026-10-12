-- Modelo estrella del registro mercantil de la Cámara de Comercio de Pasto.
-- Hechos: una fila por empresa/establecimiento. Dimensiones: municipio, sector (CIIU) y tiempo.

PRAGMA foreign_keys = ON;

-- Dimensión municipio (código DIVIPOLA de 5 dígitos)
CREATE TABLE dim_municipio (
    mun_codigo   TEXT PRIMARY KEY,
    mun_nombre   TEXT NOT NULL
);

-- Dimensión sector: jerarquía CIIU Rev. 4 A.C. (clase > grupo > división > sección > macro sector)
CREATE TABLE dim_sector (
    ciiu_codigo      TEXT PRIMARY KEY,                  -- clase, 4 dígitos ('0000' = sin clasificar)
    clase_nombre     TEXT NOT NULL,
    grupo_codigo     TEXT NOT NULL,
    grupo_nombre     TEXT NOT NULL,
    division_codigo  TEXT NOT NULL,
    division_nombre  TEXT NOT NULL,
    seccion_letra    TEXT NOT NULL,                     -- A..U ('-' = sin clasificar)
    seccion_nombre   TEXT NOT NULL,
    macro_sector     TEXT NOT NULL,                     -- Primario / Secundario / Terciario / SIN CLASIFICAR
    en_catalogo      INTEGER NOT NULL CHECK (en_catalogo IN (0, 1))   -- 0 = código del registro ausente del catálogo 2020
);

-- Dimensión tiempo (año de matrícula)
CREATE TABLE dim_tiempo (
    anio          INTEGER PRIMARY KEY,
    decada        TEXT NOT NULL,
    anio_parcial  INTEGER NOT NULL CHECK (anio_parcial IN (0, 1))     -- 1 = año con matrículas incompletas por el corte
);

-- Hechos
CREATE TABLE fact_empresa (
    id_empresa           INTEGER PRIMARY KEY,
    mun_codigo           TEXT    NOT NULL REFERENCES dim_municipio (mun_codigo),
    ciiu_codigo          TEXT    NOT NULL REFERENCES dim_sector (ciiu_codigo),
    anio_matricula       INTEGER REFERENCES dim_tiempo (anio),
    est_datos            TEXT    NOT NULL,              -- dimensión degenerada: código sin diccionario oficial
    fec_matricula        TEXT,                          -- ISO AAAA-MM-DD
    fec_renovacion       TEXT,
    ult_ano_ren          INTEGER,
    antiguedad_anios     REAL,
    n_actividades        INTEGER NOT NULL,
    ciiu_estado          TEXT    NOT NULL CHECK (ciiu_estado IN ('ok', 'codigo_no_encontrado', 'sin_ciiu')),
    barrio_codigo        TEXT,                          -- solo Pasto trae barrio
    barrio_nombre        TEXT,
    actividad            TEXT,
    vlr_establecimiento  REAL,                          -- valor original
    vlr_no_reportado     INTEGER NOT NULL CHECK (vlr_no_reportado IN (0, 1)),
    vlr_winsorizado      REAL,                          -- valor recortado a P1-P99 (usar este para promedios)
    vlr_outlier          INTEGER NOT NULL CHECK (vlr_outlier IN (0, 1))
);

CREATE INDEX idx_fact_municipio ON fact_empresa (mun_codigo);
CREATE INDEX idx_fact_sector    ON fact_empresa (ciiu_codigo);
CREATE INDEX idx_fact_anio      ON fact_empresa (anio_matricula);

-- Vista de consumo: hechos con sus dimensiones ya unidas (la usa el dashboard)
CREATE VIEW v_empresas AS
SELECT f.*,
       m.mun_nombre,
       s.clase_nombre, s.grupo_nombre, s.division_nombre, s.seccion_letra, s.seccion_nombre, s.macro_sector,
       t.decada, t.anio_parcial
FROM fact_empresa f
JOIN dim_municipio m ON m.mun_codigo  = f.mun_codigo
JOIN dim_sector    s ON s.ciiu_codigo = f.ciiu_codigo
LEFT JOIN dim_tiempo t ON t.anio      = f.anio_matricula;
