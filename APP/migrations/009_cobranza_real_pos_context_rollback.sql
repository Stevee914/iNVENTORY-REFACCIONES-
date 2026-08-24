-- ============================================================================
-- Reversión de la Migración 009: Cobranza real + contexto POS
-- ----------------------------------------------------------------------------
-- ABORTA si ya se capturó información real de contexto POS o estados REVISAR
-- (perderlos sería pérdida de datos reales). Solo si todo está en su valor por
-- defecto, restaura el CHECK de `estatus` y elimina las columnas nuevas.
--
-- Idempotente: si las columnas/tablas ya no existen, no falla.
-- ============================================================================

BEGIN;

DO $$
BEGIN
    -- Guard 1: ningún cargo con contexto POS capturado
    IF to_regclass('public.cobranza_manual_cargos') IS NOT NULL THEN
        IF EXISTS (SELECT 1 FROM public.cobranza_manual_cargos
                   WHERE factura_pos_id IS NOT NULL
                      OR factura_pos_folio IS NOT NULL
                      OR estado_pos_detectado <> 'NO_FACTURADO') THEN
            RAISE EXCEPTION
              'Reversión 009 abortada: hay cargos con contexto POS (factura_pos_id/factura_pos_folio o estado_pos_detectado <> NO_FACTURADO).';
        END IF;
    END IF;
    -- Guard 2: ninguna relación en estado REVISAR
    IF to_regclass('public.cobranza_manual') IS NOT NULL THEN
        IF EXISTS (SELECT 1 FROM public.cobranza_manual WHERE estatus = 'REVISAR') THEN
            RAISE EXCEPTION
              'Reversión 009 abortada: hay relaciones con estatus = REVISAR (sin equivalente previo).';
        END IF;
    END IF;
END $$;

-- Restaurar el CHECK de estatus SIN 'REVISAR'
ALTER TABLE public.cobranza_manual DROP CONSTRAINT IF EXISTS chk_cobranza_manual_estatus;
ALTER TABLE public.cobranza_manual
    ADD CONSTRAINT chk_cobranza_manual_estatus
    CHECK (estatus IN ('PENDIENTE','PARCIAL','PAGADA','CANCELADA'));

-- Eliminar las columnas de contexto POS
ALTER TABLE public.cobranza_manual_cargos DROP CONSTRAINT IF EXISTS chk_cmc_estado_pos;
ALTER TABLE public.cobranza_manual_cargos
    DROP COLUMN IF EXISTS estado_pos_detectado,
    DROP COLUMN IF EXISTS factura_pos_folio,
    DROP COLUMN IF EXISTS factura_pos_id;

COMMIT;
