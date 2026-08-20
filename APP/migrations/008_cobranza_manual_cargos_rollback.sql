-- ============================================================================
-- Reversión de la Migración 008: Cobranza Manual — cargos
-- ----------------------------------------------------------------------------
-- ABORTA si existe algún cargo 'MANUAL' (retirarlos sería pérdida de historial
-- financiero real). Si solo hay cargos 'INICIAL_MIGRADO', los retira junto con
-- la tabla: los totales originales siguen en cobranza_manual
-- (importe_total / numero_notas), por lo que NO se pierde ningún saldo.
--
-- Idempotente: si la tabla ya no existe, to_regclass() devuelve NULL y no falla.
-- ============================================================================

BEGIN;

DO $$
BEGIN
    IF to_regclass('public.cobranza_manual_cargos') IS NOT NULL THEN
        IF EXISTS (SELECT 1 FROM public.cobranza_manual_cargos WHERE origen = 'MANUAL') THEN
            RAISE EXCEPTION
              'Reversión abortada: existen cargos MANUAL. Respaldar/consolidar antes de revertir (se perderia historial de cargos reales).';
        END IF;
    END IF;
END $$;

DROP TABLE IF EXISTS public.cobranza_manual_cargos;

COMMIT;
