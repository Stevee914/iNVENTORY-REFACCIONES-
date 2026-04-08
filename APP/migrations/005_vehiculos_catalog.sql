-- Migration 005: Vehicle catalog tables
-- Hierarchy: marca → modelo → aplicacion (modelo + año + estilo)
-- producto_aplicacion links products to specific vehicle applications

-- ─────────────────────────────────────────────────────────────────────────────
-- 1. Makes (marcas)
-- ─────────────────────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS vehiculos_marcas (
    id         INTEGER      PRIMARY KEY,          -- from NHTSA / open-vehicle-db make_id
    nombre     VARCHAR(100) NOT NULL,
    slug       VARCHAR(100) NOT NULL UNIQUE,      -- lowercase, underscored (e.g. "gmc", "alfa_romeo")
    primer_anio SMALLINT,
    ultimo_anio SMALLINT
);

-- ─────────────────────────────────────────────────────────────────────────────
-- 2. Models (modelos)
-- ─────────────────────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS vehiculos_modelos (
    id           INTEGER      PRIMARY KEY,        -- from open-vehicle-db model_id
    marca_id     INTEGER      NOT NULL REFERENCES vehiculos_marcas(id) ON DELETE CASCADE,
    nombre       VARCHAR(150) NOT NULL,
    vehicle_type VARCHAR(50),                     -- "car", "truck", "van", "suv", etc.
    UNIQUE (marca_id, nombre)
);

CREATE INDEX IF NOT EXISTS idx_vmodelos_marca ON vehiculos_modelos (marca_id);

-- ─────────────────────────────────────────────────────────────────────────────
-- 3. Applications (modelo + año + estilo)
--    Each row = one specific trim/configuration in a specific year.
--    Motor fields are parsed from the raw style string by the import script.
-- ─────────────────────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS vehiculos_aplicaciones (
    id            SERIAL       PRIMARY KEY,
    modelo_id     INTEGER      NOT NULL REFERENCES vehiculos_modelos(id) ON DELETE CASCADE,
    anio          SMALLINT     NOT NULL CHECK (anio BETWEEN 1900 AND 2100),
    estilo        VARCHAR(250) NOT NULL,          -- raw style string from dataset
    -- parsed motor fields (NULL when not parseable from style string)
    litros        NUMERIC(4,1),                   -- e.g. 2.4
    cilindros     SMALLINT,                       -- e.g. 4, 6, 8
    config_motor  VARCHAR(10),                    -- V, I, H, W, R (inline/boxer/rotary)
    traccion      VARCHAR(5),                     -- FWD, RWD, AWD, 4WD
    carroceria    VARCHAR(30),                    -- SEDAN, SUV, PICKUP, COUPE, etc.
    UNIQUE (modelo_id, anio, estilo)
);

CREATE INDEX IF NOT EXISTS idx_vapl_modelo ON vehiculos_aplicaciones (modelo_id);
CREATE INDEX IF NOT EXISTS idx_vapl_anio   ON vehiculos_aplicaciones (anio);
-- Composite: covers common filter combo (marca implied through modelo)
CREATE INDEX IF NOT EXISTS idx_vapl_modelo_anio ON vehiculos_aplicaciones (modelo_id, anio);

-- ─────────────────────────────────────────────────────────────────────────────
-- 4. Product ↔ Application junction
-- ─────────────────────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS producto_aplicacion (
    producto_id    INTEGER NOT NULL REFERENCES productos(id)              ON DELETE CASCADE,
    aplicacion_id  INTEGER NOT NULL REFERENCES vehiculos_aplicaciones(id) ON DELETE CASCADE,
    notas          VARCHAR(250),
    PRIMARY KEY (producto_id, aplicacion_id)
);

CREATE INDEX IF NOT EXISTS idx_prod_apl_apl ON producto_aplicacion (aplicacion_id);
