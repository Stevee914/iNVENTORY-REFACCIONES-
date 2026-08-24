-- ============================================================================
-- Migración 009: Cobranza real + contexto POS
-- ----------------------------------------------------------------------------
-- Soporta el modelo nuevo, mínimo y seguro:
--   * POS = contexto FISCAL (factura/pago); NO determina el pago real.
--   * Cobranza manual = estado REAL de libreta.
--   * "POS pagado" NO implica "pagado real".
--
-- Aditiva sobre 007/008. NO renombra `estatus` a `estado_real` (se interpreta
-- `estatus` como estado real). NO remapea estados existentes. Sin FK dura a
-- facturas (el vínculo POS es solo referencia informativa).
--
-- Reversión: ver 009_cobranza_real_pos_context_rollback.sql
-- ============================================================================

BEGIN;

-- 1) Contexto POS (fiscal) en cada cargo — referencia INFORMATIVA, sin FK dura
ALTER TABLE public.cobranza_manual_cargos
    ADD COLUMN IF NOT EXISTS factura_pos_id       INTEGER,
    ADD COLUMN IF NOT EXISTS factura_pos_folio     VARCHAR(50),
    ADD COLUMN IF NOT EXISTS estado_pos_detectado  VARCHAR(20) NOT NULL DEFAULT 'NO_FACTURADO';

ALTER TABLE public.cobranza_manual_cargos DROP CONSTRAINT IF EXISTS chk_cmc_estado_pos;
ALTER TABLE public.cobranza_manual_cargos
    ADD CONSTRAINT chk_cmc_estado_pos
    CHECK (estado_pos_detectado IN ('NO_FACTURADO','FACTURADO_POS','PAGADO_POS'));

-- 2) Estado real: se MANTIENE la columna `estatus` (sin renombrar). Solo se amplía
--    el CHECK para permitir 'REVISAR'. No se tocan los valores existentes.
ALTER TABLE public.cobranza_manual DROP CONSTRAINT IF EXISTS chk_cobranza_manual_estatus;
ALTER TABLE public.cobranza_manual
    ADD CONSTRAINT chk_cobranza_manual_estatus
    CHECK (estatus IN ('PENDIENTE','PARCIAL','PAGADA','CANCELADA','REVISAR'));

COMMIT;
