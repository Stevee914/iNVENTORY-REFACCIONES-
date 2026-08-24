-- ============================================================================
-- Reversión de la Migración 010: Tipo de movimiento en cobranza real
-- ----------------------------------------------------------------------------
-- ABORTA si ya se capturaron movimientos NOTA_CREDITO o AJUSTE (perderlos sería
-- pérdida de datos reales). Solo si todo sigue siendo CARGO, restaura el CHECK
-- anterior de numero_notas y elimina la columna tipo_movimiento.
--
-- Idempotente: si la columna/tabla ya no existen, no falla.
-- ============================================================================

BEGIN;

DO $$
BEGIN
    -- Guard: solo revierte si NO hay créditos/ajustes capturados
    IF EXISTS (SELECT 1 FROM information_schema.columns
               WHERE table_schema = 'public'
                 AND table_name  = 'cobranza_manual_cargos'
                 AND column_name = 'tipo_movimiento') THEN
        IF EXISTS (SELECT 1 FROM public.cobranza_manual_cargos
                   WHERE tipo_movimiento <> 'CARGO') THEN
            RAISE EXCEPTION
              'Reversión 010 abortada: existen movimientos NOTA_CREDITO/AJUSTE (sin equivalente previo).';
        END IF;
    END IF;
END $$;

-- Restaurar el CHECK anterior de numero_notas (> 0 para todas las filas)
ALTER TABLE public.cobranza_manual_cargos DROP CONSTRAINT IF EXISTS chk_cmc_numero_notas;
ALTER TABLE public.cobranza_manual_cargos
    ADD CONSTRAINT chk_cmc_numero_notas CHECK (numero_notas > 0);

-- Eliminar el CHECK de tipo y la columna
ALTER TABLE public.cobranza_manual_cargos DROP CONSTRAINT IF EXISTS chk_cmc_tipo_mov;
ALTER TABLE public.cobranza_manual_cargos DROP COLUMN IF EXISTS tipo_movimiento;

COMMIT;
