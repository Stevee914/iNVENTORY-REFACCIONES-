from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from sqlalchemy import text
from APP.db import get_db
from APP.pos_db import get_pos_db
from APP.helpers import normalize_code
from datetime import date, datetime, timedelta

router = APIRouter(prefix="/sync", tags=["POS Sync"])


# ── Etapa 2: Client sync ──────────────────────────────────────────────────────

@router.post("/clientes")
def sync_clientes(
    pg: Session = Depends(get_db),
    pos: Session = Depends(get_pos_db),
):
    """
    Pull clients from MariaDB (FerrumOP) and create/update them in PostgreSQL.

    Match priority:
      1. pos_cliente_id  → already linked, update nombre/rfc/is_active
      2. RFC             → link by tax ID, assign pos_cliente_id
      3. no match        → create new PostgreSQL client
    """

    # ── Pass 1: sync clients from cli ────────────────────────────────────────
    pos_rows = pos.execute(text(
        "SELECT CLIENTEID, NOMBRE, ACTIVO FROM cli"
    )).mappings().all()

    stats = {"created": 0, "updated": 0, "rfc_updated": 0, "skipped": 0, "errors": []}

    for row in pos_rows:
        pos_id    = int(row["CLIENTEID"])
        nombre    = (row["NOMBRE"] or "").strip().upper()
        is_active = (row["ACTIVO"] == "S")

        if not nombre:
            stats["skipped"] += 1
            continue

        try:
            # Match by pos_cliente_id
            existing = pg.execute(
                text("SELECT id FROM clientes WHERE pos_cliente_id = :pid"),
                {"pid": pos_id},
            ).mappings().first()

            if existing:
                pg.execute(text("""
                    UPDATE clientes
                       SET nombre     = :nombre,
                           is_active  = :active,
                           updated_at = NOW()
                     WHERE pos_cliente_id = :pid
                """), {"nombre": nombre, "active": is_active, "pid": pos_id})
                stats["updated"] += 1
                continue

            # No match → create (RFC will be filled in pass 2)
            pg.execute(text("""
                INSERT INTO clientes
                    (pos_cliente_id, nombre, tipo, is_active)
                VALUES
                    (:pid, :nombre, 'MOSTRADOR', :active)
            """), {"pid": pos_id, "nombre": nombre, "active": is_active})
            stats["created"] += 1

        except Exception as e:
            pg.rollback()
            stats["errors"].append({"pos_cliente_id": pos_id, "error": str(e)})
            continue

    pg.commit()

    # ── Pass 2: backfill RFC from cfd ─────────────────────────────────────────
    rfc_rows = pos.execute(text("""
        SELECT DISTINCT d.CLIENTEID, c.RFC
        FROM cfd c
        INNER JOIN doc d ON d.DOCID = c.DOCID
        WHERE c.RFC IS NOT NULL AND c.RFC != ''
    """)).mappings().all()

    # Build a map: pos_cliente_id -> RFC (last one wins if multiple, all should match)
    rfc_map: dict[int, str] = {}
    for row in rfc_rows:
        rfc_map[int(row["CLIENTEID"])] = row["RFC"].strip().upper()

    for pos_id, rfc in rfc_map.items():
        if not rfc:
            continue
        try:
            pg.execute(text("""
                UPDATE clientes
                   SET rfc        = :rfc,
                       updated_at = NOW()
                 WHERE pos_cliente_id = :pid
                   AND (rfc IS NULL OR rfc = '')
            """), {"rfc": rfc, "pid": pos_id})
            stats["rfc_updated"] += 1
        except Exception as e:
            pg.rollback()
            stats["errors"].append({"pos_cliente_id": pos_id, "rfc_error": str(e)})
            continue

    pg.commit()

    return {
        "ok": True,
        "total_pos": len(pos_rows),
        "created": stats["created"],
        "updated": stats["updated"],
        "rfc_updated": stats["rfc_updated"],
        "skipped": stats["skipped"],
        "errors":  stats["errors"],
    }


# ── Etapa 3: Invoiced document sync ──────────────────────────────────────────

CONDICION_MAP = {
    "CO": "CONTADO",
    "CR": "CREDITO_30",
    "15": "CREDITO_15",
    "30": "CREDITO_30",
    "60": "CREDITO_60",
}


def _map_condicion(v: str) -> str:
    return CONDICION_MAP.get((v or "").strip().upper(), "CONTADO")


def _derive_estatus(cond: str, total: float, total_pagado: float) -> str:
    """
    cond = doc.COND char(1): 'C' = contado, anything else = credito.
    Falls back to payment amounts if cond is ambiguous.
    """
    if (cond or "").strip().upper() == "C":
        return "PAGADA"
    if total_pagado >= total - 0.01:
        return "PAGADA"
    if total_pagado > 0.01:
        return "PARCIAL"
    return "CREDITO"


def _sync_one_day(fecha: date, pg: Session, pos: Session) -> dict:
    """Sync a single day from POS → PostgreSQL. Returns per-day stats dict."""

    # Pre-count excluded rows for observability
    skipped_cancelled = pos.execute(text("""
        SELECT COUNT(*) FROM cfd c
        INNER JOIN doc d ON d.DOCID = c.DOCID
        WHERE c.FECHA = :fecha AND c.ESTADO = 'A'
    """), {"fecha": fecha}).scalar() or 0

    skipped_complement = pos.execute(text("""
        SELECT COUNT(*) FROM cfd c
        INNER JOIN doc d ON d.DOCID = c.DOCID
        WHERE c.FECHA = :fecha AND c.ESTADO = 'S'
          AND (c.TIPDOC != 'F' OR c.TOTAL <= 0)
    """), {"fecha": fecha}).scalar() or 0

    # Pull valid invoices from MariaDB for the requested date
    pos_rows = pos.execute(text("""
        SELECT
            d.DOCID          AS pos_documento_id,
            c.CFDID          AS pos_cfd_id,
            d.CLIENTEID      AS pos_cliente_id,
            c.RFC            AS rfc,
            c.SERIE          AS serie,
            c.FOLIO          AS folio,
            c.FECHA          AS fecha,
            c.TOTAL          AS total,
            c.IMPUESTO       AS impuesto,
            d.COND           AS cond,
            d.CONDICIONPAGO  AS condicionpago,
            d.TOTALPAGADO    AS totalpagado,
            c.UUID           AS uuid
        FROM cfd c
        INNER JOIN doc d ON d.DOCID = c.DOCID
        WHERE c.FECHA = :fecha
          AND c.ESTADO = 'S'
          AND c.TIPDOC = 'F'
          AND c.TOTAL > 0
    """), {"fecha": fecha}).mappings().all()

    stats = {
        "total_pos_raw":      len(pos_rows) + int(skipped_cancelled) + int(skipped_complement),
        "total_pos_eligible": len(pos_rows),
        "inserted":           0,
        "updated":            0,
        "skipped_no_client":  0,
        "skipped_cancelled":  int(skipped_cancelled),
        "skipped_complement": int(skipped_complement),
        "errors":             [],
    }

    for row in pos_rows:
        pos_doc_id  = int(row["pos_documento_id"])
        pos_cfd_id  = int(row["pos_cfd_id"])
        pos_cli_id  = int(row["pos_cliente_id"])
        serie       = (row["serie"] or "").strip().upper()
        folio_raw   = (row["folio"] or "").strip().upper()
        folio_pg    = (serie + folio_raw) if serie else folio_raw
        fecha_doc   = row["fecha"]
        total       = float(row["total"] or 0)
        impuesto    = float(row["impuesto"] or 0)
        subtotal    = round(total - impuesto, 2)
        totalpagado = float(row["totalpagado"] or 0)
        condicion   = _map_condicion(row["condicionpago"])
        estatus     = _derive_estatus(row["cond"], total, totalpagado)
        uuid_val    = (row["uuid"] or "").strip() or None

        if not folio_pg:
            folio_pg = str(pos_doc_id)

        try:
            cliente = pg.execute(
                text("SELECT id FROM clientes WHERE pos_cliente_id = :pid"),
                {"pid": pos_cli_id},
            ).mappings().first()

            if not cliente:
                stats["skipped_no_client"] += 1
                stats["errors"].append({
                    "pos_documento_id": pos_doc_id,
                    "reason": f"no local client for pos_cliente_id={pos_cli_id}",
                })
                continue

            cliente_id = cliente["id"]

            already_exists = pg.execute(
                text("SELECT 1 FROM facturas WHERE pos_documento_id = :pid"),
                {"pid": pos_doc_id},
            ).first() is not None

            pg.execute(text("""
                INSERT INTO facturas (
                    folio, serie, fecha, cliente_id,
                    monto, subtotal, iva,
                    estatus, tipo_documento, condicion_pago,
                    uuid, origen, pos_documento_id, pos_cfd_id
                ) VALUES (
                    :folio, :serie, :fecha, :cliente_id,
                    :monto, :subtotal, :iva,
                    :estatus, 'FACTURA', :condicion,
                    :uuid, 'POS', :pos_doc_id, :pos_cfd_id
                )
                ON CONFLICT (pos_documento_id) DO UPDATE SET
                    folio          = EXCLUDED.folio,
                    serie          = EXCLUDED.serie,
                    fecha          = EXCLUDED.fecha,
                    monto          = EXCLUDED.monto,
                    subtotal       = EXCLUDED.subtotal,
                    iva            = EXCLUDED.iva,
                    estatus        = EXCLUDED.estatus,
                    condicion_pago = EXCLUDED.condicion_pago,
                    uuid           = EXCLUDED.uuid,
                    pos_cfd_id     = EXCLUDED.pos_cfd_id,
                    updated_at     = NOW()
            """), {
                "folio":      folio_pg,
                "serie":      serie or None,
                "fecha":      fecha_doc,
                "cliente_id": cliente_id,
                "monto":      total,
                "subtotal":   subtotal,
                "iva":        impuesto,
                "estatus":    estatus,
                "condicion":  condicion,
                "uuid":       uuid_val,
                "pos_doc_id": pos_doc_id,
                "pos_cfd_id": pos_cfd_id,
            })

            if already_exists:
                stats["updated"] += 1
            else:
                stats["inserted"] += 1

            if totalpagado > 0.01:
                factura_id_pg = pg.execute(
                    text("SELECT id FROM facturas WHERE pos_documento_id = :pid"),
                    {"pid": pos_doc_id},
                ).scalar()
                if factura_id_pg:
                    # Upsert on pos_cfd_id — atomic, safe for re-sync.
                    # Each invoice CFDI (pos_cfd_id) produces exactly one TOTALPAGADO-based
                    # payment row. ON CONFLICT updates the amount if already present instead
                    # of inserting a duplicate.
                    pg.execute(text("""
                        INSERT INTO pagos
                            (factura_id, monto, fecha, referencia, notas, pos_cfd_id)
                        VALUES
                            (:fid, :monto, :fecha, 'POS-SYNC', 'Pago registrado desde POS', :cfd_id)
                        ON CONFLICT (pos_cfd_id) WHERE pos_cfd_id IS NOT NULL
                        DO UPDATE SET
                            monto = EXCLUDED.monto,
                            fecha = EXCLUDED.fecha
                    """), {
                        "fid":    factura_id_pg,
                        "monto":  totalpagado,
                        "fecha":  fecha_doc,
                        "cfd_id": pos_cfd_id,
                    })

        except Exception as e:
            pg.rollback()
            stats["errors"].append({"pos_documento_id": pos_doc_id, "error": str(e)})
            continue

    pg.commit()
    return stats


@router.post("/facturas")
def sync_facturas(
    fecha_inicio: date = Query(default=None, description="Start date (inclusive). Defaults to today."),
    fecha_fin:    date = Query(default=None, description="End date (inclusive). Defaults to today."),
    # backwards-compat: single ?fecha=YYYY-MM-DD still works
    fecha:        date = Query(default=None, description="Single day shorthand (sets both start and end)."),
    pg: Session = Depends(get_db),
    pos: Session = Depends(get_pos_db),
):
    """
    Pull invoiced documents from FerrumOP POS and upsert them into PostgreSQL.

    - fecha_inicio + fecha_fin  → sync every day in the range (inclusive)
    - fecha_inicio only         → sync from that date up to today
    - fecha only                → backwards-compat single-day sync
    - no params                 → sync today only

    origen = 'POS', tipo_documento = 'FACTURA'.
    Dedup key: pos_documento_id (unique constraint uq_pos_documento_id).
    """
    today = date.today()

    # Resolve date range
    if fecha is not None and fecha_inicio is None:
        # backwards-compat single-day call
        fi = ff = fecha
    else:
        fi = fecha_inicio or today
        ff = fecha_fin    or today

    if fi > ff:
        fi, ff = ff, fi  # silently swap if caller passed them backwards

    # Accumulate stats across all days
    agg = {
        "total_pos_raw":      0,
        "total_pos_eligible": 0,
        "inserted":           0,
        "updated":            0,
        "skipped_no_client":  0,
        "skipped_cancelled":  0,
        "skipped_complement": 0,
        "errors":             [],
    }
    dias_procesados = 0
    current = fi
    while current <= ff:
        day_stats = _sync_one_day(current, pg, pos)
        for key in ("total_pos_raw", "total_pos_eligible", "inserted", "updated",
                    "skipped_no_client", "skipped_cancelled", "skipped_complement"):
            agg[key] += day_stats[key]
        agg["errors"].extend(day_stats["errors"])
        dias_procesados += 1
        current += timedelta(days=1)

    return {
        "ok":                  True,
        "fecha_inicio":        str(fi),
        "fecha_fin":           str(ff),
        "dias_procesados":     dias_procesados,
        "total_pos_raw":       agg["total_pos_raw"],
        "total_pos_eligible":  agg["total_pos_eligible"],
        "inserted":            agg["inserted"],
        "updated":             agg["updated"],
        "skipped_no_client":   agg["skipped_no_client"],
        "skipped_cancelled":   agg["skipped_cancelled"],
        "skipped_complement":  agg["skipped_complement"],
        "errors":              agg["errors"],
    }


# ── Etapa 4: Purchase sync ───────────────────────────────────────────────────

# doc.ESTADO → compras.estatus
_ESTADO_MAP = {
    "I": "RECIBIDA",   # Ingresada / active purchase
    "C": "CANCELADA",
}

# doc.COND → compras.metodo_pago
# Note: COND is a payment condition (CONTADO/CREDITO), not a payment instrument.
# Stored in metodo_pago for simplicity; distinguish properly in a future pass.
_COND_MAP = {
    "C": "CONTADO",
    "R": "CREDITO",
}


@router.post("/compras")
def sync_compras(
    fecha: date = Query(default=None, description="Sync purchases for a single day (YYYY-MM-DD). Omit to sync all."),
    desde: date = Query(default=None, description="Sync purchases from this date onwards."),
    pg:  Session = Depends(get_db),
    pos: Session = Depends(get_pos_db),
):
    """
    Pull purchase headers (doc.TIPO='E') from FerrumOP POS and upsert into
    PostgreSQL compras.

    origen = 'POS'.  Dedup key: pos_compra_id (= doc.DOCID, unique constraint).
    Never touches rows where origen = 'MANUAL'.

    Date filtering:
      ?fecha=YYYY-MM-DD  → single day
      ?desde=YYYY-MM-DD  → that date and forward
      (no params)        → full history (use carefully on first run)
    """
    # ── 1. Build date filter ──────────────────────────────────────────────────
    date_clause = ""
    date_params: dict = {}
    if fecha:
        date_clause = "AND d.FECHA = :fecha"
        date_params["fecha"] = fecha
    elif desde:
        date_clause = "AND d.FECHA >= :desde"
        date_params["desde"] = desde

    # ── 2. Pull purchase headers from MariaDB ─────────────────────────────────
    pos_rows = pos.execute(text(f"""
        SELECT
            d.DOCID                                 AS pos_compra_id,
            d.NUMERO                                AS folio_captura,
            d.ANTERIOR                              AS folio_factura,
            d.FECHA                                 AS fecha,
            d.CLIENTEID                             AS pos_proveedor_id,
            ROUND(d.TOTAL - d.IMPUESTO, 2)          AS subtotal,
            d.IMPUESTO                              AS iva,
            d.TOTAL                                 AS total,
            d.ESTADO                                AS estado,
            d.COND                                  AS cond,
            d.NOTA                                  AS notas
        FROM doc d
        WHERE d.TIPO = 'E'
        {date_clause}
        ORDER BY d.FECHA, d.DOCID
    """), date_params).mappings().all()

    stats = {
        "inserted":            0,
        "updated":             0,
        "skipped_no_supplier": 0,
        "possible_duplicates": [],
        "errors":              [],
    }

    for row in pos_rows:
        pos_doc_id     = int(row["pos_compra_id"])
        folio_factura  = (row["folio_factura"] or "").strip().upper() or None
        folio_captura  = str(int(row["folio_captura"])) if row["folio_captura"] else None
        tipo_compra    = "CON_FACTURA" if folio_factura else "SIN_FACTURA"
        fecha_doc      = row["fecha"]
        pos_prov_id    = int(row["pos_proveedor_id"])
        subtotal       = float(row["subtotal"] or 0)
        iva            = float(row["iva"] or 0)
        total          = float(row["total"] or 0)
        estatus        = _ESTADO_MAP.get((row["estado"] or "").strip().upper(), "RECIBIDA")
        metodo_pago    = _COND_MAP.get((row["cond"] or "").strip().upper())
        notas          = (row["notas"] or "").strip() or None

        try:
            # ── 3. Resolve PostgreSQL supplier ───────────────────────────────
            proveedor = pg.execute(
                text("SELECT id FROM proveedores WHERE pos_proveedor_id = :pid"),
                {"pid": pos_prov_id},
            ).mappings().first()

            if not proveedor:
                stats["skipped_no_supplier"] += 1
                stats["errors"].append({
                    "pos_compra_id": pos_doc_id,
                    "reason": f"no local supplier for pos_proveedor_id={pos_prov_id}",
                })
                continue

            proveedor_id = proveedor["id"]

            # ── 4. Check existence ────────────────────────────────────────────
            already = pg.execute(
                text("SELECT id FROM compras WHERE pos_compra_id = :pid"),
                {"pid": pos_doc_id},
            ).mappings().first()

            if already:
                # Update POS-owned fields only
                pg.execute(text("""
                    UPDATE compras
                       SET folio_factura = :folio_factura,
                           folio_captura = :folio_captura,
                           fecha         = :fecha,
                           subtotal      = :subtotal,
                           iva           = :iva,
                           total         = :total,
                           estatus       = :estatus,
                           metodo_pago   = :metodo_pago,
                           notas         = :notas,
                           tipo_compra   = :tipo_compra,
                           updated_at    = NOW()
                     WHERE pos_compra_id = :pid
                """), {
                    "folio_factura": folio_factura,
                    "folio_captura": folio_captura,
                    "fecha":         fecha_doc,
                    "subtotal":      subtotal,
                    "iva":           iva,
                    "total":         total,
                    "estatus":       estatus,
                    "metodo_pago":   metodo_pago,
                    "notas":         notas,
                    "tipo_compra":   tipo_compra,
                    "pid":           pos_doc_id,
                })
                stats["updated"] += 1
                continue

            # ── 5. Check for possible manual duplicate before inserting ───────
            # Criteria: same supplier + date + total (within 0.10) + same folio_factura
            # If found, flag and skip — do not auto-merge.
            dup = pg.execute(text("""
                SELECT id FROM compras
                WHERE origen = 'MANUAL'
                  AND proveedor_id = :pid
                  AND fecha        = :fecha
                  AND ABS(total - :total) < 0.10
                  AND (folio_factura = :folio OR folio_factura IS NULL)
                LIMIT 1
            """), {
                "pid":   proveedor_id,
                "fecha": fecha_doc,
                "total": total,
                "folio": folio_factura,
            }).mappings().first()

            if dup:
                stats["possible_duplicates"].append({
                    "pos_compra_id":   pos_doc_id,
                    "manual_compra_id": dup["id"],
                    "folio_factura":   folio_factura,
                    "fecha":           str(fecha_doc),
                    "total":           total,
                })
                continue

            # ── 6. Insert new POS purchase ────────────────────────────────────
            pg.execute(text("""
                INSERT INTO compras
                    (proveedor_id, folio_factura, folio_captura,
                     fecha, subtotal, iva, total,
                     estatus, metodo_pago, notas,
                     origen, tipo_compra, pos_compra_id)
                VALUES
                    (:proveedor_id, :folio_factura, :folio_captura,
                     :fecha, :subtotal, :iva, :total,
                     :estatus, :metodo_pago, :notas,
                     'POS', :tipo_compra, :pos_compra_id)
            """), {
                "proveedor_id":  proveedor_id,
                "folio_factura": folio_factura,
                "folio_captura": folio_captura,
                "fecha":         fecha_doc,
                "subtotal":      subtotal,
                "iva":           iva,
                "total":         total,
                "estatus":       estatus,
                "metodo_pago":   metodo_pago,
                "notas":         notas,
                "tipo_compra":   tipo_compra,
                "pos_compra_id": pos_doc_id,
            })
            stats["inserted"] += 1

        except Exception as e:
            pg.rollback()
            stats["errors"].append({"pos_compra_id": pos_doc_id, "error": str(e)})
            continue

    pg.commit()

    fechas = [r["fecha"] for r in pos_rows if r["fecha"]]
    return {
        "ok":                  True,
        "fecha_filter":        str(fecha) if fecha else None,
        "desde_filter":        str(desde) if desde else None,
        "total_pos":           len(pos_rows),
        "fecha_min":           str(min(fechas)) if fechas else None,
        "fecha_max":           str(max(fechas)) if fechas else None,
        "folio_min":           min((int(r["folio_captura"]) for r in pos_rows if r["folio_captura"]), default=None),
        "folio_max":           max((int(r["folio_captura"]) for r in pos_rows if r["folio_captura"]), default=None),
        "inserted":            stats["inserted"],
        "updated":             stats["updated"],
        "skipped_no_supplier": stats["skipped_no_supplier"],
        "possible_duplicates": stats["possible_duplicates"],
        "errors":              stats["errors"],
    }


# ── Etapa 5: Supplier sync ───────────────────────────────────────────────────

@router.post("/proveedores")
def sync_proveedores(
    pg: Session = Depends(get_db),
    pos: Session = Depends(get_pos_db),
):
    """
    Pull suppliers from MariaDB cli (TIPO IN ('D','P')) and upsert into
    PostgreSQL proveedores.

    Match priority:
      1. pos_proveedor_id → already linked, update nombre/rfc
      2. RFC (normalized)  → link by tax ID, assign pos_proveedor_id
      3. no match          → create new supplier (codigo_corto = POS{CLIENTEID})
    """
    pos_rows = pos.execute(text("""
        SELECT
            c.CLIENTEID  AS pos_id,
            c.NOMBRE     AS nombre,
            c.ACTIVO     AS activo,
            d.RFC        AS rfc
        FROM cli c
        LEFT JOIN dom d ON d.CLIENTEID = c.CLIENTEID
        WHERE c.TIPO IN ('D', 'P')
    """)).mappings().all()

    stats = {"created": 0, "updated": 0, "skipped": 0, "errors": []}

    for row in pos_rows:
        pos_id   = int(row["pos_id"])
        nombre   = (row["nombre"] or "").strip().upper()
        rfc_raw  = (row["rfc"] or "").strip().upper()
        rfc      = rfc_raw.replace(" ", "") or None   # normalize: remove spaces

        if not nombre:
            stats["skipped"] += 1
            continue

        try:
            # ── 1. Match by pos_proveedor_id (already linked) ─────────────
            existing = pg.execute(
                text("SELECT id FROM proveedores WHERE pos_proveedor_id = :pid"),
                {"pid": pos_id},
            ).mappings().first()

            if existing:
                pg.execute(text("""
                    UPDATE proveedores
                       SET nombre     = :nombre,
                           rfc        = COALESCE(:rfc, rfc),
                           updated_at = NOW()
                     WHERE pos_proveedor_id = :pid
                """), {"nombre": nombre, "rfc": rfc, "pid": pos_id})
                stats["updated"] += 1
                continue

            # ── 2. Match by RFC ───────────────────────────────────────────
            if rfc:
                by_rfc = pg.execute(
                    text("SELECT id FROM proveedores WHERE rfc = :rfc"),
                    {"rfc": rfc},
                ).mappings().first()

                if by_rfc:
                    pg.execute(text("""
                        UPDATE proveedores
                           SET pos_proveedor_id = :pid,
                               nombre           = :nombre,
                               updated_at       = NOW()
                         WHERE id = :id
                    """), {"pid": pos_id, "nombre": nombre, "id": by_rfc["id"]})
                    stats["updated"] += 1
                    continue

            # ── 3. No match → create new supplier ────────────────────────
            codigo_corto = f"POS{pos_id}"
            pg.execute(text("""
                INSERT INTO proveedores
                    (nombre, codigo_corto, rfc, pos_proveedor_id)
                VALUES
                    (:nombre, :codigo_corto, :rfc, :pid)
            """), {
                "nombre":       nombre,
                "codigo_corto": codigo_corto,
                "rfc":          rfc,
                "pid":          pos_id,
            })
            stats["created"] += 1

        except Exception as e:
            pg.rollback()
            stats["errors"].append({"pos_proveedor_id": pos_id, "error": str(e)})
            continue

    pg.commit()

    return {
        "ok":        True,
        "total_pos": len(pos_rows),
        "created":   stats["created"],
        "updated":   stats["updated"],
        "skipped":   stats["skipped"],
        "errors":    stats["errors"],
    }


# ── Etapa 6: Product sync from POS ───────────────────────────────────────────

@router.post("/productos")
def sync_productos(
    only_new: bool = Query(
        default=False,
        description="If true, only create new products; skip updates to existing ones.",
    ),
    pg: Session = Depends(get_db),
    pos: Session = Depends(get_pos_db),
):
    """
    Pull products from MariaDB inv and upsert into PostgreSQL productos.

    inv.CLAVE        → productos.codigo_pos        (NOT sku — critical business rule)
    inv.COSTO        → productos.price             (POS cost sin IVA)
    inv.COSTO * 1.16 → productos.costo_pos_con_iva (calculated cost con IVA)

    Match priority:
      1. pos_articulo_id → already linked, update costo_pos_con_iva
      2. codigo_pos      → link by CLAVE, assign pos_articulo_id + update costo_pos_con_iva
      3. no match        → create new product (requires len(CLAVE) >= 5)

    Uses per-row SAVEPOINTs so a single failure never rolls back other rows.
    Commits every 500 rows to bound memory usage.
    """
    pos_rows = pos.execute(text("""
        SELECT ARTICULOID, CLAVE, DESCRIPCIO, COSTO
        FROM inv
        WHERE CLAVE != '' AND LEFT(CLAVE, 1) != '_'
    """)).mappings().all()

    stats: dict = {
        "existing_updated": 0,
        "new_created":      0,
        "skipped":          0,
        "errors":           [],
        "new_codigos_pos":  [],
    }

    BATCH = 500

    for i, row in enumerate(pos_rows):
        art_id     = int(row["ARTICULOID"])
        clave_raw      = (row["CLAVE"] or "").strip()
        codigo_pos     = normalize_code(clave_raw)
        descripcio     = (row["DESCRIPCIO"] or "").strip()
        costo_sin_iva  = float(row["COSTO"] or 0)          # inv.COSTO = sin IVA → price
        costo_con_iva  = round(costo_sin_iva * 1.16, 6)    # calculated → costo_pos_con_iva

        if not codigo_pos:
            stats["skipped"] += 1
            continue

        try:
            pg.execute(text("SAVEPOINT sp_prod"))

            # ── 1. Match by pos_articulo_id (already linked) ──────────────
            existing = pg.execute(
                text("SELECT id FROM productos WHERE pos_articulo_id = :aid"),
                {"aid": art_id},
            ).mappings().first()

            if existing:
                if not only_new:
                    pg.execute(text("""
                        UPDATE productos
                           SET price             = CASE WHEN COALESCE(price, 0) = 0 THEN :costo_sin ELSE price END,
                               costo_pos_con_iva = :costo_con,
                               updated_at        = NOW()
                         WHERE pos_articulo_id = :aid
                    """), {"costo_sin": costo_sin_iva, "costo_con": costo_con_iva, "aid": art_id})
                    stats["existing_updated"] += 1
                else:
                    stats["skipped"] += 1
                pg.execute(text("RELEASE SAVEPOINT sp_prod"))
                continue

            # ── 2. Match by codigo_pos ────────────────────────────────────
            by_cpos = pg.execute(
                text("SELECT id FROM productos WHERE codigo_pos = :cpos"),
                {"cpos": codigo_pos},
            ).mappings().first()

            if by_cpos:
                if not only_new:
                    pg.execute(text("""
                        UPDATE productos
                           SET pos_articulo_id   = :aid,
                               price             = CASE WHEN COALESCE(price, 0) = 0 THEN :costo_sin ELSE price END,
                               costo_pos_con_iva = :costo_con,
                               updated_at        = NOW()
                         WHERE id = :id
                    """), {"aid": art_id, "costo_sin": costo_sin_iva, "costo_con": costo_con_iva, "id": by_cpos["id"]})
                    stats["existing_updated"] += 1
                else:
                    stats["skipped"] += 1
                pg.execute(text("RELEASE SAVEPOINT sp_prod"))
                continue

            # ── 3. No match → create new product ─────────────────────────
            # Spec: CLAVE must be >= 5 chars (4 for codigo_cat + 1 for sku)
            if len(codigo_pos) < 5:
                stats["skipped"] += 1
                pg.execute(text("RELEASE SAVEPOINT sp_prod"))
                continue

            codigo_cat = codigo_pos[:4]
            sku        = codigo_pos[4:]
            name       = descripcio or codigo_pos

            pg.execute(text("""
                INSERT INTO productos
                    (sku, name, codigo_pos, codigo_cat,
                     price, costo_pos_con_iva, unit, is_active, min_stock, pos_articulo_id)
                VALUES
                    (:sku, :name, :codigo_pos, :codigo_cat,
                     :costo_sin, :costo_con, 'PZA', true, 0, :aid)
            """), {
                "sku":        sku,
                "name":       name,
                "codigo_pos": codigo_pos,
                "codigo_cat": codigo_cat,
                "costo_sin":  costo_sin_iva,
                "costo_con":  costo_con_iva,
                "aid":        art_id,
            })
            stats["new_created"] += 1
            stats["new_codigos_pos"].append(codigo_pos)
            pg.execute(text("RELEASE SAVEPOINT sp_prod"))

        except Exception as e:
            pg.execute(text("ROLLBACK TO SAVEPOINT sp_prod"))
            stats["errors"].append({
                "articuloid": art_id,
                "clave":      clave_raw,
                "error":      str(e),
            })

        # Commit every BATCH rows to bound transaction size
        if (i + 1) % BATCH == 0:
            pg.commit()

    pg.commit()

    return {
        "ok":               True,
        "total_pos":        len(pos_rows),
        "existing_updated": stats["existing_updated"],
        "new_created":      stats["new_created"],
        "skipped":          stats["skipped"],
        "errors":           stats["errors"],
        "new_codigos_pos":  stats["new_codigos_pos"],
    }


# ── Etapa 6b: Stock sync from POS MariaDB ────────────────────────────────────

@router.post("/stock-pos")
def sync_stock_pos(
    pg: Session = Depends(get_db),
    pos: Session = Depends(get_pos_db),
):
    """
    Read current stock (EXISTENCIA) from MariaDB alm, match products by
    codigo_pos (inv.CLAVE), compare against v_stock_libros.stock_pos in
    PostgreSQL, and generate ADJUST movements in libro FISCAL_POS for any
    product whose stock differs.

    Replaces the manual Excel upload for POS stock synchronisation.
    Idempotent: running twice when nothing changed → 0 movements created.
    """
    reference = "POS_STOCK_SYNC_" + datetime.now().strftime("%Y%m%d_%H%M%S")

    # ── 1. Pull stock totals from MariaDB (sum across all warehouses) ─────────
    pos_rows = pos.execute(text("""
        SELECT
            i.ARTICULOID           AS articuloid,
            i.CLAVE                AS clave,
            SUM(a.EXISTENCIA)      AS existencia
        FROM inv i
        INNER JOIN alm a ON a.ARTICULOID = i.ARTICULOID
        WHERE i.CLAVE != '' AND LEFT(i.CLAVE, 1) != '_'
        GROUP BY i.ARTICULOID, i.CLAVE
    """)).mappings().all()

    # ── 2. Normalize CLAVE → codigo_pos and build lookup ──────────────────────
    pos_stock: dict[str, float] = {}   # codigo_pos → existencia
    for row in pos_rows:
        cp = normalize_code(row["clave"])
        if cp:
            pos_stock[cp] = float(row["existencia"] or 0)

    if not pos_stock:
        return {
            "ok": True, "reference": reference,
            "total_products": 0, "adjusted": 0,
            "no_change": 0, "skipped_not_found": 0, "errors": [],
        }

    # ── 3. Bulk fetch matching PG products + current stock_pos ────────────────
    all_codigos = list(pos_stock.keys())
    pg_rows = pg.execute(
        text("""
            SELECT p.id, p.sku, p.codigo_pos,
                   COALESCE(v.stock_pos, 0) AS stock_pos
            FROM productos p
            LEFT JOIN v_stock_libros v ON v.sku = p.sku
            WHERE p.codigo_pos = ANY(:codigos)
        """),
        {"codigos": all_codigos},
    ).mappings().all()

    # codigo_pos → {id, sku, stock_pos}
    pg_map: dict[str, dict] = {r["codigo_pos"]: dict(r) for r in pg_rows}

    # ── 4. Compute deltas ─────────────────────────────────────────────────────
    movements: list[dict] = []
    adjusted        = 0
    no_change       = 0
    skipped         = 0
    errors: list[dict] = []

    for codigo_pos, pos_qty in pos_stock.items():
        if codigo_pos not in pg_map:
            skipped += 1
            continue

        prod    = pg_map[codigo_pos]
        sys_qty = float(prod["stock_pos"])
        delta   = pos_qty - sys_qty

        if abs(delta) < 1e-9:
            no_change += 1
            continue

        try:
            movements.append({
                "pid":   prod["id"],
                "libro": "FISCAL_POS",
                "mt":    "ADJUST",
                "evento": "AJUSTE",
                "qty":   delta,
                "ref":   reference,
                "notes": f"Sync POS: pos={pos_qty} sys={sys_qty}",
            })
            adjusted += 1
        except Exception as e:
            errors.append({"codigo_pos": codigo_pos, "error": str(e)})

    # ── 5. Bulk insert all movements in one query ──────────────────────────────
    if movements:
        pg.execute(
            text("""
                INSERT INTO movimientos_inventario
                    (product_id, libro, movement_type, evento, quantity,
                     reference, notes, movement_date, created_at)
                SELECT
                    m.pid,
                    CAST(m.libro  AS inv_libro),
                    m.mt,
                    CAST(m.evento AS inv_evento),
                    m.qty,
                    m.ref, m.notes, NOW(), NOW()
                FROM unnest(
                    CAST(:pids      AS int[]),
                    CAST(:libros    AS text[]),
                    CAST(:mts       AS text[]),
                    CAST(:eventos   AS text[]),
                    CAST(:qtys      AS float[]),
                    CAST(:refs      AS text[]),
                    CAST(:notes_arr AS text[])
                ) AS m(pid, libro, mt, evento, qty, ref, notes)
            """),
            {
                "pids":      [m["pid"]   for m in movements],
                "libros":    [m["libro"] for m in movements],
                "mts":       [m["mt"]    for m in movements],
                "eventos":   [m["evento"] for m in movements],
                "qtys":      [m["qty"]   for m in movements],
                "refs":      [m["ref"]   for m in movements],
                "notes_arr": [m["notes"] for m in movements],
            },
        )

    pg.commit()

    return {
        "ok":                True,
        "reference":         reference,
        "total_products":    len(pos_stock),
        "adjusted":          adjusted,
        "no_change":         no_change,
        "skipped_not_found": skipped,
        "errors":            errors,
    }


# ── Health check for POS connection ──────────────────────────────────────────

@router.get("/pos-check")
def pos_check(pos: Session = Depends(get_pos_db)):
    """Verify the MariaDB POS connection is reachable."""
    result = pos.execute(text("SELECT 1")).scalar()
    count  = pos.execute(text("SELECT COUNT(*) FROM cli")).scalar()
    return {"pos_db": "connected", "cli_rows": count}


# ── Etapa 7: Product-supplier relationship sync ───────────────────────────────

BATCH_PP = 500

@router.post("/producto-proveedores")
def sync_producto_proveedores(
    pg:  Session = Depends(get_db),
    pos: Session = Depends(get_pos_db),
):
    """
    Pull product-supplier relationships from MariaDB ppa and upsert them into
    PostgreSQL producto_proveedor.

    Fields mapped from ppa:
      ARTICULOID  → product_id   (via productos.pos_articulo_id)
      PROVEEDORID → proveedor_id (via proveedores.pos_proveedor_id)
      CLAVE       → supplier_sku
      COSTO       → precio_proveedor
      PREFERENCIA → is_primary  (PREFERENCIA = 1 → True, else False)

    Upsert key: (proveedor_id, supplier_sku)  — matches existing UNIQUE constraint.

    Skips:
      - Rows with empty CLAVE (supplier_sku is NOT NULL in the table)
      - Rows whose ARTICULOID has no matching producto in PostgreSQL
      - Rows whose PROVEEDORID has no matching proveedor in PostgreSQL
    """

    # ── 1. Fetch all ppa rows from MariaDB ────────────────────────────────────
    pos_rows = pos.execute(text("""
        SELECT ARTICULOID, PROVEEDORID, CLAVE, COSTO, PREFERENCIA
        FROM   ppa
        ORDER  BY PROVEEDORID, ARTICULOID
    """)).mappings().all()

    # ── 2. Build lookup dicts from PostgreSQL ─────────────────────────────────
    prod_map = {
        int(r["pos_articulo_id"]): int(r["id"])
        for r in pg.execute(text(
            "SELECT id, pos_articulo_id FROM productos WHERE pos_articulo_id IS NOT NULL"
        )).mappings().all()
    }

    prov_map = {
        int(r["pos_proveedor_id"]): int(r["id"])
        for r in pg.execute(text(
            "SELECT id, pos_proveedor_id FROM proveedores WHERE pos_proveedor_id IS NOT NULL"
        )).mappings().all()
    }

    stats = {
        "total_pos":               len(pos_rows),
        "created":                 0,
        "updated":                 0,
        "skipped_empty_clave":     0,
        "skipped_missing_product": 0,
        "skipped_missing_supplier":0,
        "errors":                  [],
    }

    batch = 0

    for row in pos_rows:
        art_id  = int(row["ARTICULOID"])
        prov_id = int(row["PROVEEDORID"])
        clave   = (row["CLAVE"] or "").strip()
        costo   = float(row["COSTO"]) if row["COSTO"] else None
        is_prim = (int(row["PREFERENCIA"]) == 1)

        # Skip rows with no supplier_sku — can't upsert without it
        if not clave:
            stats["skipped_empty_clave"] += 1
            continue

        pg_product_id   = prod_map.get(art_id)
        pg_proveedor_id = prov_map.get(prov_id)

        if pg_proveedor_id is None:
            stats["skipped_missing_supplier"] += 1
            continue

        if pg_product_id is None:
            stats["skipped_missing_product"] += 1
            continue

        try:
            pg.execute(text("SAVEPOINT sp_pp"))
            result = pg.execute(text("""
                INSERT INTO producto_proveedor
                    (proveedor_id, product_id, supplier_sku,
                     precio_proveedor, is_primary, created_at, updated_at)
                VALUES
                    (:prov, :prod, :sku,
                     :precio, :is_prim, NOW(), NOW())
                ON CONFLICT (proveedor_id, supplier_sku)
                DO UPDATE SET
                    product_id       = EXCLUDED.product_id,
                    precio_proveedor = EXCLUDED.precio_proveedor,
                    is_primary       = EXCLUDED.is_primary,
                    updated_at       = NOW()
                RETURNING (xmax = 0) AS was_inserted
            """), {
                "prov":    pg_proveedor_id,
                "prod":    pg_product_id,
                "sku":     clave,
                "precio":  costo,
                "is_prim": is_prim,
            })
            row_result = result.mappings().one()
            if row_result["was_inserted"]:
                stats["created"] += 1
            else:
                stats["updated"] += 1
            pg.execute(text("RELEASE SAVEPOINT sp_pp"))

        except Exception as e:
            pg.execute(text("ROLLBACK TO SAVEPOINT sp_pp"))
            stats["errors"].append({
                "articuloid":  art_id,
                "proveedorid": prov_id,
                "sku":         clave,
                "error":       str(e),
            })
            continue

        batch += 1
        if batch % BATCH_PP == 0:
            pg.commit()

    pg.commit()

    skipped_total = (
        stats["skipped_empty_clave"]
        + stats["skipped_missing_product"]
        + stats["skipped_missing_supplier"]
    )

    return {
        "ok":                       True,
        "total_pos":                stats["total_pos"],
        "created":                  stats["created"],
        "updated":                  stats["updated"],
        "skipped":                  skipped_total,
        "skipped_empty_clave":      stats["skipped_empty_clave"],
        "skipped_missing_product":  stats["skipped_missing_product"],
        "skipped_missing_supplier": stats["skipped_missing_supplier"],
        "error_count":              len(stats["errors"]),
        "errors":                   stats["errors"][:50],
    }
