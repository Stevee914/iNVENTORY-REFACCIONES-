-- ============================================================================
-- Migración 011: vínculo abono -> factura/cargo
-- ----------------------------------------------------------------------------
-- Agrega cobranza_manual_pagos.cargo_id (nullable): "este abono pagó esta
-- factura (cargo)". Nullable para pagos generales (clientes que pagan todo el
-- día junto). FK ON DELETE RESTRICT (no se puede borrar un cargo con abono ligado).
--
-- Aditiva. NO toca POS/facturas/inventario. Retrocompatible (columna opcional).
-- Reversión: ver 011_pago_cargo_id_rollback.sql
-- ============================================================================

BEGIN;

ALTER TABLE public.cobranza_manual_pagos
    ADD COLUMN IF NOT EXISTS cargo_id INTEGER;

ALTER TABLE public.cobranza_manual_pagos DROP CONSTRAINT IF EXISTS fk_cmp_cargo;
ALTER TABLE public.cobranza_manual_pagos
    ADD CONSTRAINT fk_cmp_cargo FOREIGN KEY (cargo_id)
    REFERENCES public.cobranza_manual_cargos(id) ON DELETE RESTRICT;

CREATE INDEX IF NOT EXISTS idx_cmp_cargo ON public.cobranza_manual_pagos(cargo_id);

COMMIT;
