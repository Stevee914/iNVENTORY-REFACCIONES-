-- ============================================================================
-- Migración 008: Cobranza Manual — historial de CARGOS (estado de cuenta)
-- ----------------------------------------------------------------------------
-- Crea cobranza_manual_cargos: cada cargo (grupo de notas) de una relación,
-- para armar un estado de cuenta (cargos + abonos) por cliente/relación.
--
-- CONTRATO TRAS ESTA MIGRACIÓN:
--   * cobranza_manual.importe_total y cobranza_manual.numero_notas pasan a ser
--     TOTALES ACUMULADOS DERIVADOS de los cargos:
--       importe_total = SUM(cobranza_manual_cargos.importe)
--       numero_notas  = SUM(cobranza_manual_cargos.numero_notas)
--   * El backend NO permitirá editarlos directamente por PATCH; solo se
--     actualizan dentro de la MISMA transacción que inserta un cargo.
--
-- REGLA DE DESPLIEGUE (obligatoria): esta migración NO puede quedar activa
--   mientras siga corriendo el backend anterior (permite crear relaciones sin
--   cargos y editar directamente importe_total/numero_notas). Debe aplicarse en
--   la ventana controlada junto con el arranque del backend compatible con cargos.
--
-- Seguridad:
--   * Crea 1 tabla + 2 índices + 1 índice único parcial. Idempotente.
--   * NO modifica ni borra cobranza_manual ni cobranza_manual_pagos.
--   * El backfill solo INSERTA cargos 'INICIAL_MIGRADO' (1 por relación),
--     preservando el importe/notas/fecha actuales de cada relación.
--   * Sin relación con facturas, pagos, inventario, FISICO ni FISCAL_POS.
--
-- Reversión: ver 008_cobranza_manual_cargos_rollback.sql
-- ============================================================================

BEGIN;

CREATE TABLE IF NOT EXISTS public.cobranza_manual_cargos (
    id                   SERIAL PRIMARY KEY,
    cobranza_manual_id   INTEGER NOT NULL REFERENCES public.cobranza_manual(id) ON DELETE RESTRICT,
    fecha_cargo          DATE NOT NULL DEFAULT CURRENT_DATE,
    numero_notas         INTEGER NOT NULL,
    importe              NUMERIC(14,2) NOT NULL,
    origen               VARCHAR(20) NOT NULL DEFAULT 'MANUAL',
    observaciones        TEXT,
    created_at           TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT chk_cmc_numero_notas CHECK (numero_notas > 0),
    CONSTRAINT chk_cmc_importe      CHECK (importe > 0),
    CONSTRAINT chk_cmc_origen       CHECK (origen IN ('INICIAL_MIGRADO','MANUAL'))
);

CREATE INDEX IF NOT EXISTS idx_cmc_cobranza ON public.cobranza_manual_cargos(cobranza_manual_id);
CREATE INDEX IF NOT EXISTS idx_cmc_fecha    ON public.cobranza_manual_cargos(fecha_cargo);

-- Solo UN cargo INICIAL_MIGRADO por relación; los MANUAL no tienen límite.
CREATE UNIQUE INDEX IF NOT EXISTS uq_cmc_inicial_por_relacion
    ON public.cobranza_manual_cargos(cobranza_manual_id)
    WHERE origen = 'INICIAL_MIGRADO';

-- Backfill idempotente RESPECTO AL INICIAL_MIGRADO (no respecto a cargos MANUAL):
-- convierte cada relación en su cargo inicial preservando importe/notas/fecha.
INSERT INTO public.cobranza_manual_cargos
    (cobranza_manual_id, fecha_cargo, numero_notas, importe, origen, observaciones)
SELECT cm.id, cm.fecha_relacion, cm.numero_notas, cm.importe_total, 'INICIAL_MIGRADO',
       'Cargo inicial (migrado de la relación)'
FROM public.cobranza_manual cm
WHERE NOT EXISTS (
    SELECT 1 FROM public.cobranza_manual_cargos x
    WHERE x.cobranza_manual_id = cm.id AND x.origen = 'INICIAL_MIGRADO'
);

COMMIT;