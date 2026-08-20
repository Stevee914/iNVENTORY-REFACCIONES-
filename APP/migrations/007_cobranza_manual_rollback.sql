-- ============================================================================
-- Reversión de la Migración 007: Cobranza Manual
-- ----------------------------------------------------------------------------
-- Elimina ÚNICAMENTE las dos tablas nuevas creadas por 007_cobranza_manual.sql.
--
-- Protección de datos:
--   * Antes de borrar, verifica CADA tabla por separado con to_regclass():
--     si la tabla existe Y contiene filas, ABORTA (rollback total) para no
--     perder registros financieros. Respaldar antes de forzar el borrado.
--   * Idempotente: si las tablas ya no existen, to_regclass() devuelve NULL y
--     el conteo se omite, por lo que correr este script dos veces no falla.
--   * Orden de DROP: primero la tabla hija (pagos), luego la padre.
-- ============================================================================

BEGIN;

DO $$
DECLARE
    v_pagos_count       BIGINT := 0;
    v_relaciones_count  BIGINT := 0;
BEGIN
    -- Comprobar existencia de cada tabla por separado ANTES de contar sus filas
    IF to_regclass('public.cobranza_manual_pagos') IS NOT NULL THEN
        SELECT count(*) INTO v_pagos_count FROM public.cobranza_manual_pagos;
    END IF;

    IF to_regclass('public.cobranza_manual') IS NOT NULL THEN
        SELECT count(*) INTO v_relaciones_count FROM public.cobranza_manual;
    END IF;

    IF v_pagos_count > 0 OR v_relaciones_count > 0 THEN
        RAISE EXCEPTION
            'Reversión abortada: cobranza_manual tiene % relaciones y % pagos. Respaldar antes de continuar.',
            v_relaciones_count, v_pagos_count;
    END IF;
END $$;

DROP TABLE IF EXISTS public.cobranza_manual_pagos;
DROP TABLE IF EXISTS public.cobranza_manual;

COMMIT;
