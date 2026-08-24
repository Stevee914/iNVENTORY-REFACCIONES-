-- ============================================================================
-- Migración 010: Tipo de movimiento en el ledger de cobranza real
-- ----------------------------------------------------------------------------
-- Convierte cobranza_manual_cargos en un libro de movimientos con signo por tipo:
--   * CARGO        (+)  nota/venta a cobrar (facturada o no)
--   * NOTA_CREDITO (-)  crédito fiscal; baja el saldo, no es efectivo
--   * AJUSTE       (-)  ajuste a favor del cliente; baja el saldo, no es efectivo
--
-- `importe` sigue siendo MAGNITUD positiva (CHECK importe>0 intacto); el signo lo
-- da el tipo. saldo_real = ΣCARGO - Σ(NOTA_CREDITO+AJUSTE) - Σpagos.
-- La regla "una NOTA_CREDITO/AJUSTE no puede exceder el saldo pendiente"
-- (no saldo_real < 0) es validación de BACKEND, no se impone aquí.
--
-- Aditiva sobre 007/008/009. Retrocompatible: el backend actual la ignora hasta
-- implementar el modelo nuevo. NO renombra ni remapea nada.
--
-- Reversión: ver 010_cobranza_tipo_movimiento_rollback.sql
-- ============================================================================

BEGIN;

-- 1) Nueva columna de tipo de movimiento (default CARGO -> retrocompatible)
ALTER TABLE public.cobranza_manual_cargos
    ADD COLUMN IF NOT EXISTS tipo_movimiento VARCHAR(16) NOT NULL DEFAULT 'CARGO';

-- 2) CHECK de dominio del tipo
ALTER TABLE public.cobranza_manual_cargos DROP CONSTRAINT IF EXISTS chk_cmc_tipo_mov;
ALTER TABLE public.cobranza_manual_cargos
    ADD CONSTRAINT chk_cmc_tipo_mov
    CHECK (tipo_movimiento IN ('CARGO','NOTA_CREDITO','AJUSTE'));

-- 3) numero_notas: obligatorio (>0) SOLO para CARGO; 0 permitido en crédito/ajuste
ALTER TABLE public.cobranza_manual_cargos DROP CONSTRAINT IF EXISTS chk_cmc_numero_notas;
ALTER TABLE public.cobranza_manual_cargos
    ADD CONSTRAINT chk_cmc_numero_notas
    CHECK ( (tipo_movimiento = 'CARGO'  AND numero_notas > 0)
         OR (tipo_movimiento <> 'CARGO' AND numero_notas >= 0) );

COMMIT;
