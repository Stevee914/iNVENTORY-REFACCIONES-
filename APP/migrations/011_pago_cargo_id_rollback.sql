-- ============================================================================
-- Reversión de la Migración 011: vínculo abono -> factura/cargo
-- ----------------------------------------------------------------------------
-- ABORTA si algún abono ya tiene cargo_id (perder ese vínculo sería pérdida de
-- información real). Solo si todos son NULL, elimina índice, FK y columna.
-- Idempotente.
-- ============================================================================

BEGIN;

DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM information_schema.columns
               WHERE table_schema='public' AND table_name='cobranza_manual_pagos'
                 AND column_name='cargo_id') THEN
        IF EXISTS (SELECT 1 FROM public.cobranza_manual_pagos WHERE cargo_id IS NOT NULL) THEN
            RAISE EXCEPTION 'Reversión 011 abortada: hay abonos con cargo_id (vínculo a factura).';
        END IF;
    END IF;
END $$;

DROP INDEX IF EXISTS public.idx_cmp_cargo;
ALTER TABLE public.cobranza_manual_pagos DROP CONSTRAINT IF EXISTS fk_cmp_cargo;
ALTER TABLE public.cobranza_manual_pagos DROP COLUMN IF EXISTS cargo_id;

COMMIT;
