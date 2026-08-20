-- ============================================================================
-- Migración 007: Cobranza Manual
-- ----------------------------------------------------------------------------
-- Crea DOS tablas nuevas e independientes para gestionar "relaciones de notas"
-- capturadas a mano por el personal y sus abonos:
--     - cobranza_manual         (la relación / encabezado)
--     - cobranza_manual_pagos   (los abonos de cada relación)
--
-- Fuente financiera SEPARADA del POS. Sus importes, pagos y saldos NUNCA se
-- suman ni se enlazan automáticamente con facturas/pagos del POS.
--
-- Seguridad:
--   * Solo CREATE TABLE / CREATE INDEX nuevos (idempotentes con IF NOT EXISTS).
--   * NO modifica ni elimina datos existentes.
--   * NO toca facturas, pagos, inventario, movimientos, FISICO ni FISCAL_POS.
--   * folio_factura_referencia es informativo (VARCHAR libre, SIN FK a facturas).
--   * Saldos y estados se calculan/validan en el backend, no en la DB.
--
-- Reversión: ver 007_cobranza_manual_rollback.sql
-- ============================================================================

BEGIN;

CREATE TABLE IF NOT EXISTS public.cobranza_manual (
    id                        SERIAL PRIMARY KEY,
    cliente_id                INTEGER NOT NULL REFERENCES public.clientes(id) ON DELETE RESTRICT,
    fecha_relacion            DATE NOT NULL DEFAULT CURRENT_DATE,
    numero_notas              INTEGER NOT NULL,
    importe_total             NUMERIC(14,2) NOT NULL,
    estatus                   VARCHAR(20) NOT NULL DEFAULT 'PENDIENTE',
    observaciones             TEXT,
    posteriormente_facturada  BOOLEAN NOT NULL DEFAULT FALSE,
    folio_factura_referencia  VARCHAR(50),
    created_at                TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at                TIMESTAMPTZ NOT NULL DEFAULT now(),
    cancelada_at              TIMESTAMPTZ,
    CONSTRAINT chk_cobranza_manual_numero_notas  CHECK (numero_notas > 0),
    CONSTRAINT chk_cobranza_manual_importe_total CHECK (importe_total > 0),
    CONSTRAINT chk_cobranza_manual_estatus       CHECK (estatus IN ('PENDIENTE','PARCIAL','PAGADA','CANCELADA'))
);

CREATE TABLE IF NOT EXISTS public.cobranza_manual_pagos (
    id                   SERIAL PRIMARY KEY,
    cobranza_manual_id   INTEGER NOT NULL REFERENCES public.cobranza_manual(id) ON DELETE RESTRICT,
    fecha_pago           DATE NOT NULL DEFAULT CURRENT_DATE,
    monto                NUMERIC(14,2) NOT NULL,
    metodo_pago          VARCHAR(20) NOT NULL,
    referencia           VARCHAR(100),
    observaciones        TEXT,
    created_at           TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT chk_cobranza_manual_pagos_monto  CHECK (monto > 0),
    CONSTRAINT chk_cobranza_manual_pagos_metodo CHECK (metodo_pago IN ('EFECTIVO','TRANSFERENCIA','CHEQUE','TARJETA','OTRO'))
);

CREATE INDEX IF NOT EXISTS idx_cobranza_manual_cliente   ON public.cobranza_manual(cliente_id);
CREATE INDEX IF NOT EXISTS idx_cobranza_manual_fecha     ON public.cobranza_manual(fecha_relacion);
CREATE INDEX IF NOT EXISTS idx_cobranza_manual_estatus   ON public.cobranza_manual(estatus);
CREATE INDEX IF NOT EXISTS idx_cobranza_manual_cancelada ON public.cobranza_manual(cancelada_at);
CREATE INDEX IF NOT EXISTS idx_cobranza_manual_pagos_cm  ON public.cobranza_manual_pagos(cobranza_manual_id);

COMMIT;
