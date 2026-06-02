import logging
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from sqlalchemy import text
from pydantic import BaseModel
from datetime import date
from APP.db import get_db
from APP.pos_db import get_pos_db

logger = logging.getLogger("pos_compras")

router = APIRouter(prefix="/import", tags=["POS - Compras"])


class ComprasBody(BaseModel):
    fecha_inicio: date
    fecha_fin: date


_ESTADO_MAP: dict[str, str] = {
    "I": "RECIBIDA",
    "C": "CANCELADA",
    "A": "PENDIENTE",
}

_COND_MAP: dict[str, str] = {
    "C": "CONTADO",
    "R": "CREDITO",
}


def _derive_estatus_pago(totalpagado: float, total: float, tol: float = 0.01) -> str:
    """
    Derive compras.estatus_pago from POS doc.TOTALPAGADO vs doc.TOTAL.
      >= total - tol  → PAGADA   (fully paid; tol absorbs float rounding)
      > 0             → PARCIAL
      else            → PENDIENTE
    """
    if total <= 0:
        return "PAGADA"
    if totalpagado >= total - tol:
        return "PAGADA"
    if totalpagado > 0:
        return "PARCIAL"
    return "PENDIENTE"


def _log_sync(
    pg: Session,
    proceso: str,
    fi,
    ff,
    status: str,
    ok: int,
    err: int,
    notes: str = None,
):
    pg.execute(
        text("""
            INSERT INTO sync_control
                (proceso, fecha_inicio, fecha_fin, status, registros_ok, registros_err, notes)
            VALUES (:p, :fi, :ff, :s, :ok, :err, :n)
        """),
        {"p": proceso, "fi": fi, "ff": ff, "s": status, "ok": ok, "err": err, "n": notes},
    )
    pg.commit()


def _auto_create_product(pg: Session, codigo_pos: str, descripcion: str | None,
                         costo: float | None, costo_iva: float | None) -> int | None:
    """
    Insert a new producto row for a POS article not found in the catalog.
    Returns the new product id, or None if a sku conflict was found (ON CONFLICT DO NOTHING).
    Only called for codes longer than 4 chars (must have a real sku suffix).
    """
    if not codigo_pos or len(codigo_pos) <= 4:
        return None
    codigo_cat = codigo_pos[:4]
    sku = codigo_pos[4:]
    name = ((descripcion or "").strip()[:80]) or codigo_pos
    new_id = pg.execute(
        text("""
            INSERT INTO productos
                (sku, codigo_pos, codigo_cat, name, unit, is_active,
                 price, costo_pos_con_iva, costo_origen, pos_ultimo_sync)
            VALUES
                (:sku, :cp, :cat, :name, 'PZA', true,
                 :price, :costo_iva, 'POS', NOW())
            ON CONFLICT (sku) DO NOTHING
            RETURNING id
        """),
        {
            "sku": sku,
            "cp": codigo_pos,
            "cat": codigo_cat,
            "name": name,
            "price": costo or 0,
            "costo_iva": costo_iva or 0,
        },
    ).scalar()
    if new_id:
        logger.info("producto auto-creado sku=%s codigo_pos=%s", sku, codigo_pos)
    else:
        logger.warning("auto-create omitido: conflicto sku=%s codigo_pos=%s", sku, codigo_pos)
    return new_id


def _upsert_proveedor_link(
    pg: Session,
    proveedor_id: int,
    product_id: int,
    supplier_sku: str | None,
    descripcion: str | None,
    costo: float | None,
) -> bool:
    """
    Maintain producto_proveedor link.
    Returns True if a row was created or updated, False if skipped (no supplier_sku for insert).
    - If a row matching (proveedor_id, supplier_sku) exists: update precio_proveedor (always)
      and descripcion_proveedor only if currently NULL/empty. Never overwrite supplier_sku.
    - If no match by supplier_sku, fall back to (product_id, proveedor_id) soft match.
    - If no existing row and supplier_sku is NULL: skip — cannot insert with NULL sku.
    - If no existing row and supplier_sku present: insert new link.
    """
    precio_valido = costo is not None and costo > 0
    sku_clean = (supplier_sku or "").strip() or None
    desc_clean = (descripcion or "").strip()[:200] or None

    existing = None
    if sku_clean:
        existing = pg.execute(
            text("""
                SELECT id, supplier_sku, precio_proveedor, descripcion_proveedor
                FROM producto_proveedor
                WHERE proveedor_id = :prov AND supplier_sku = :sku
            """),
            {"prov": proveedor_id, "sku": sku_clean},
        ).mappings().first()

    if existing is None:
        existing = pg.execute(
            text("""
                SELECT id, supplier_sku, precio_proveedor, descripcion_proveedor
                FROM producto_proveedor
                WHERE product_id = :pid AND proveedor_id = :prov
                LIMIT 1
            """),
            {"pid": product_id, "prov": proveedor_id},
        ).mappings().first()

    if existing:
        sets, params = [], {"id": existing["id"]}
        if precio_valido:
            sets.append("precio_proveedor = :precio")
            params["precio"] = costo
        # Backfill description only if currently empty
        if desc_clean and not existing["descripcion_proveedor"]:
            sets.append("descripcion_proveedor = :desc")
            params["desc"] = desc_clean
        # Backfill supplier_sku if old row has NULL and we now have the correct value
        if sku_clean and not existing["supplier_sku"]:
            sets.append("supplier_sku = :sku")
            params["sku"] = sku_clean
        if sets:
            pg.execute(
                text(f"UPDATE producto_proveedor SET {', '.join(sets)} WHERE id = :id"),
                params,
            )
        return True
    else:
        # Cannot INSERT with NULL supplier_sku — NOT NULL constraint on producto_proveedor.
        if not sku_clean:
            return False
        cnt = pg.execute(
            text("SELECT COUNT(*) FROM producto_proveedor WHERE product_id = :pid"),
            {"pid": product_id},
        ).scalar() or 0
        pg.execute(
            text("""
                INSERT INTO producto_proveedor
                    (proveedor_id, product_id, supplier_sku, descripcion_proveedor,
                     precio_proveedor, is_primary)
                VALUES
                    (:prov, :pid, :sku, :desc, :precio, :primary)
                ON CONFLICT (proveedor_id, supplier_sku)
                WHERE supplier_sku IS NOT NULL
                DO NOTHING
            """),
            {
                "prov": proveedor_id,
                "pid": product_id,
                "sku": sku_clean,
                "desc": desc_clean,
                "precio": costo if precio_valido else None,
                "primary": cnt == 0,
            },
        )
        return True


@router.post("/pos-compras")
def import_pos_compras(
    body: ComprasBody,
    pg: Session = Depends(get_db),
    pos: Session = Depends(get_pos_db),
):
    """
    Sync periódico de compras del POS.

    Por cada compra en el rango:
    - Resuelve proveedor por pos_proveedor_id. Si no se resuelve, omite la compra completa.
    - Hace upsert del encabezado en compras (dedup por pos_compra_id).
    - Hace upsert de líneas en compras_detalle (solo después de resolver producto).
    - Inserta ENTRADA_FACTURA en FISCAL_POS por cada línea (idempotente por source_uid).
    - Inserta ENTRADA_FACTURA en FISICO por cada línea (idempotente por source_uid + ':FISICO').
      Doble entrada intencional: compras POS facturadas y recibidas afectan ambos libros.
    - Auto-crea productos faltantes con datos mínimos del POS.
    - Mantiene enlace producto_proveedor solo cuando supplier_sku existe (NOT NULL constraint).
      Si supplier_sku es NULL, omite el link y lo reporta en advertencias.
    - Actualiza productos.pos_ultimo_sync para productos que aparecen.
    - Usa SAVEPOINT por compra para aislar errores sin perder otras compras.
    - Registra resultado en sync_control.

    Omite artículos con código que empieza por '_' (técnicos de CONTPAQi, e.g. _ARTIMP).
    """
    compras_ok: int = 0
    movs_ok: int = 0
    movs_fisico_ok: int = 0
    prods_created: int = 0
    duplicados: int = 0
    prod_prov_omitidos: int = 0
    errores: list[dict] = []
    advertencias: list[dict] = []

    # ── Caches para reducir queries N+1 ─────────────────────────────────────────
    prod_cache: dict[str, int | None] = {}
    prov_cache: dict[int, int | None] = {}

    def _get_product(codigo_pos: str) -> int | None:
        if codigo_pos not in prod_cache:
            # L2: exact codigo_pos match
            row = pg.execute(
                text("SELECT id FROM productos WHERE codigo_pos = :cp"),
                {"cp": codigo_pos},
            ).mappings().first()
            if not row and len(codigo_pos) > 4:
                base = codigo_pos[4:]
                # L3: exact sku match (handles category-prefix changes in POS)
                row = pg.execute(
                    text("SELECT id FROM productos WHERE sku = :s"),
                    {"s": base},
                ).mappings().first()
                if not row:
                    # L4: normalized sku match (handles hyphens in stored sku, e.g. '1162-HG' vs '1162HG')
                    row = pg.execute(
                        text("SELECT id FROM productos WHERE REPLACE(sku, '-', '') = :s"),
                        {"s": base},
                    ).mappings().first()
            prod_cache[codigo_pos] = int(row["id"]) if row else None
        return prod_cache[codigo_pos]

    def _get_proveedor(pos_prov_id: int) -> int | None:
        if pos_prov_id not in prov_cache:
            row = pg.execute(
                text("SELECT id FROM proveedores WHERE pos_proveedor_id = :pid"),
                {"pid": pos_prov_id},
            ).mappings().first()
            prov_cache[pos_prov_id] = int(row["id"]) if row else None
        return prov_cache[pos_prov_id]

    # ── Pull purchase headers ────────────────────────────────────────────────────
    headers = pos.execute(
        text("""
            SELECT
                d.DOCID                             AS pos_compra_id,
                d.CLIENTEID                         AS pos_proveedor_id,
                TRIM(CONCAT(d.SERIE, d.NUMERO))     AS folio_captura,
                d.ANTERIOR                          AS folio_factura,
                d.FECHA                             AS fecha,
                NULLIF(d.FECCAP, '0000-00-00')      AS fecha_documento,
                ROUND(d.TOTAL - d.IMPUESTO, 2)      AS subtotal,
                d.IMPUESTO                          AS iva,
                d.TOTAL                             AS total,
                d.TOTALPAGADO                       AS totalpagado,
                d.ESTADO                            AS estado,
                d.COND                              AS cond,
                d.NOTA                              AS notas,
                MAX(CASE WHEN p.APLICADO = 'S'
                         THEN p.FECHAAPLICADA END)  AS fecha_pago_pos,
                MAX(CASE WHEN p.APLICADO = 'S'
                         THEN p.FECHAPAG END)       AS fecha_pago_procesada_pos,
                MAX(CASE WHEN p.APLICADO = 'N'
                         THEN p.FECHAAPLICADA END)  AS fecha_pago_programada_pos,
                MAX(CASE WHEN p.APLICADO = 'S'
                         THEN 1 ELSE 0 END) > 0     AS pago_aplicado_pos
            FROM doc d
            LEFT JOIN pag p ON p.DOCID = d.DOCID
            WHERE d.TIPO = 'E'
              AND d.FECHA BETWEEN :fi AND :ff
            GROUP BY d.DOCID, d.CLIENTEID, d.SERIE, d.NUMERO, d.ANTERIOR,
                     d.FECHA, d.FECCAP, d.TOTAL, d.IMPUESTO, d.TOTALPAGADO,
                     d.ESTADO, d.COND, d.NOTA
            ORDER BY d.FECHA, d.DOCID
        """),
        {"fi": body.fecha_inicio, "ff": body.fecha_fin},
    ).mappings().all()

    for header in headers:
        pos_compra_id = int(header["pos_compra_id"])
        pos_prov_id   = int(header["pos_proveedor_id"])
        folio_factura = (header["folio_factura"] or "").strip().upper() or None
        folio_captura = (header["folio_captura"] or "").strip() or None
        ref_display   = folio_factura or folio_captura or str(pos_compra_id)
        tipo_compra   = "CON_FACTURA" if folio_factura else "SIN_FACTURA"
        fecha         = header["fecha"]
        subtotal      = float(header["subtotal"] or 0)
        iva           = float(header["iva"] or 0)
        total         = float(header["total"] or 0)
        estatus       = _ESTADO_MAP.get((header["estado"] or "").strip().upper(), "RECIBIDA")
        metodo_pago   = _COND_MAP.get((header["cond"] or "").strip().upper())
        notas         = (header["notas"] or "").strip() or None
        totalpagado   = float(header["totalpagado"] or 0)
        estatus_pago  = _derive_estatus_pago(totalpagado, total)

        fecha_documento          = header["fecha_documento"] or None
        fecha_pago_pos           = header["fecha_pago_pos"] or None
        fecha_pago_procesada_pos = header["fecha_pago_procesada_pos"] or None
        fecha_pago_programada_pos = header["fecha_pago_programada_pos"] or None
        pago_aplicado_pos        = bool(header["pago_aplicado_pos"]) if header["pago_aplicado_pos"] is not None else None

        try:
            pg.execute(text("SAVEPOINT sp_compra"))

            # ── Resolver proveedor — obligatorio por chk_proveedor_en_entradas ──
            proveedor_id = _get_proveedor(pos_prov_id)
            if proveedor_id is None:
                errores.append({
                    "folio": ref_display,
                    "codigo_pos": None,
                    "source_uid": f"POS:COMPRA:{pos_compra_id}:*",
                    "motivo": f"proveedor POS {pos_prov_id} no encontrado — ejecute /sync/proveedores",
                })
                pg.execute(text("ROLLBACK TO SAVEPOINT sp_compra"))
                pg.execute(text("RELEASE SAVEPOINT sp_compra"))
                continue

            # ── Upsert encabezado compra ─────────────────────────────────────
            # uq_compras_pos_compra_id es un índice parcial WHERE pos_compra_id IS NOT NULL
            compra_id = pg.execute(
                text("""
                    INSERT INTO compras
                        (proveedor_id, folio_factura, folio_captura, fecha,
                         subtotal, iva, total, estatus, metodo_pago,
                         notas, origen, tipo_compra,
                         estatus_recepcion, estatus_pago, pos_compra_id,
                         fecha_documento, fecha_pago_pos, fecha_pago_procesada_pos,
                         fecha_pago_programada_pos, pago_aplicado_pos)
                    VALUES
                        (:prov, :ff, :fc, :fecha,
                         :sub, :iva, :total, :est, :mp,
                         :notas, 'POS', :tipo,
                         'RECIBIDA', :estatus_pago, :pos_id,
                         :fecha_doc, :fecha_pago, :fecha_pago_proc,
                         :fecha_pago_prog, :pago_aplicado)
                    ON CONFLICT (pos_compra_id) WHERE pos_compra_id IS NOT NULL
                    DO UPDATE SET
                        estatus                   = EXCLUDED.estatus,
                        total                     = EXCLUDED.total,
                        iva                       = EXCLUDED.iva,
                        subtotal                  = EXCLUDED.subtotal,
                        estatus_pago              = EXCLUDED.estatus_pago,
                        fecha_documento           = EXCLUDED.fecha_documento,
                        fecha_pago_pos            = EXCLUDED.fecha_pago_pos,
                        fecha_pago_procesada_pos  = EXCLUDED.fecha_pago_procesada_pos,
                        fecha_pago_programada_pos = EXCLUDED.fecha_pago_programada_pos,
                        pago_aplicado_pos         = EXCLUDED.pago_aplicado_pos
                    RETURNING id
                """),
                {
                    "prov": proveedor_id,
                    "ff": folio_factura,
                    "fc": folio_captura,
                    "fecha": fecha,
                    "sub": subtotal,
                    "iva": iva,
                    "total": total,
                    "est": estatus,
                    "mp": metodo_pago,
                    "notas": notas,
                    "tipo": tipo_compra,
                    "estatus_pago": estatus_pago,
                    "pos_id": pos_compra_id,
                    "fecha_doc": fecha_documento,
                    "fecha_pago": fecha_pago_pos,
                    "fecha_pago_proc": fecha_pago_procesada_pos,
                    "fecha_pago_prog": fecha_pago_programada_pos,
                    "pago_aplicado": pago_aplicado_pos,
                },
            ).scalar()
            compras_ok += 1

            # ── Pull lines for this purchase ──────────────────────────────────
            lines = pos.execute(
                text("""
                    SELECT
                        des.DESID                              AS desid,
                        des.DESFECHA                          AS fecha_linea,
                        inv.CLAVE                             AS codigo_pos,
                        COALESCE(ppa.CLAVE, inv.CLVPROV)      AS supplier_sku,
                        inv.DESCRIPCIO                        AS descripcion,
                        des.DESCANTIDAD                       AS cantidad,
                        des.DESCOSTO                          AS costo_unit,
                        des.DESIVA                            AS iva_linea
                    FROM des
                    JOIN inv ON inv.ARTICULOID = des.DESARTID
                    LEFT JOIN ppa ON ppa.ARTICULOID = des.DESARTID
                                 AND ppa.PROVEEDORID = :prov_pos_id
                    WHERE des.DESDOCID = :docid
                      AND des.DESCANTIDAD != 0
                    ORDER BY des.DESID
                """),
                {"docid": pos_compra_id, "prov_pos_id": pos_prov_id},
            ).mappings().all()

            for line in lines:
                desid        = int(line["desid"])
                codigo_pos   = (line["codigo_pos"] or "").strip().upper()
                cantidad_raw = float(line["cantidad"] or 0)
                source_uid   = f"POS:COMPRA:{pos_compra_id}:{desid}"

                if not codigo_pos or cantidad_raw == 0:
                    continue

                # Skip CONTPAQi technical articles (e.g. _ARTIMP = IVA import charge)
                if codigo_pos.startswith("_"):
                    continue

                # Negative qty in POS = devolution to supplier
                accion   = "DEVOLUCION" if cantidad_raw < 0 else "ENTRADA"
                cantidad = abs(cantidad_raw)

                costo        = float(line["costo_unit"] or 0) or None
                costo_iva    = round(costo * 1.16, 4) if costo else None
                supplier_sku = (line["supplier_sku"] or "").strip() or None
                descripcion  = (line["descripcion"] or "").strip() or None
                iva_linea    = float(line["iva_linea"] or 0) or None

                # ── Check for duplicate — skip only when both libro rows exist ──
                already_fiscal = pg.execute(
                    text("SELECT id FROM movimientos_inventario WHERE source_uid = :uid"),
                    {"uid": source_uid},
                ).first()
                already_fisico = pg.execute(
                    text("SELECT id FROM movimientos_inventario WHERE source_uid = :uid"),
                    {"uid": source_uid + ":FISICO"},
                ).first()

                if already_fiscal and already_fisico:
                    duplicados += 1
                    continue

                # ── Resolve product (create if missing) ──────────────────────
                product_id = _get_product(codigo_pos)
                if product_id is None:
                    new_id = _auto_create_product(pg, codigo_pos, descripcion, costo, costo_iva)
                    if new_id:
                        prod_cache[codigo_pos] = new_id
                        product_id = new_id
                        prods_created += 1

                if product_id is None:
                    errores.append({
                        "folio": ref_display,
                        "codigo_pos": codigo_pos,
                        "source_uid": source_uid,
                        "motivo": "producto no encontrado ni creado (codigo_pos <= 4 chars o conflicto sku)",
                    })
                    continue

                # ── Insert compras_detalle (after product is resolved) ────────
                pg.execute(
                    text("""
                        INSERT INTO compras_detalle
                            (compra_id, product_id, cantidad, precio_unit,
                             supplier_sku, descripcion_xml, codigo_proveedor,
                             iva, es_servicio, accion)
                        VALUES
                            (:cid, :pid, :qty, :precio,
                             :sku, :desc, :clave,
                             :iva_l, false, :accion)
                    """),
                    {
                        "cid": compra_id,
                        "pid": product_id,
                        "qty": cantidad,
                        "precio": costo,
                        "sku": supplier_sku,
                        "desc": descripcion,
                        "clave": codigo_pos,
                        "iva_l": iva_linea,
                        "accion": accion,
                    },
                )

                # ── Insert movements — DEVOLUCION uses OUT on both books ──────
                movement_type = "OUT" if accion == "DEVOLUCION" else "IN"
                mov_params = {
                    "pid": product_id,
                    "mt": movement_type,
                    "qty": cantidad,
                    "costo": costo,
                    "costo_iva": costo_iva,
                    "prov": proveedor_id,
                    "fecha": line["fecha_linea"] or fecha,
                    "ref": ref_display,
                }

                r_fiscal = pg.execute(
                    text("""
                        INSERT INTO movimientos_inventario
                            (product_id, libro, movement_type, quantity, evento,
                             costo_unit_sin_iva, tasa_iva, costo_unit_con_iva,
                             proveedor_id, movement_date, reference, source_uid)
                        VALUES
                            (:pid, 'FISCAL_POS', :mt, :qty, 'ENTRADA_FACTURA',
                             :costo, 0.16, :costo_iva,
                             :prov, :fecha, :ref, :uid)
                        ON CONFLICT (source_uid) DO NOTHING
                    """),
                    {**mov_params, "uid": source_uid},
                )
                if r_fiscal.rowcount:
                    movs_ok += 1

                r_fisico = pg.execute(
                    text("""
                        INSERT INTO movimientos_inventario
                            (product_id, libro, movement_type, quantity, evento,
                             costo_unit_sin_iva, tasa_iva, costo_unit_con_iva,
                             proveedor_id, movement_date, reference, source_uid)
                        VALUES
                            (:pid, 'FISICO', :mt, :qty, 'ENTRADA_FACTURA',
                             :costo, 0.16, :costo_iva,
                             :prov, :fecha, :ref, :uid)
                        ON CONFLICT (source_uid) DO NOTHING
                    """),
                    {**mov_params, "uid": source_uid + ":FISICO"},
                )
                if r_fisico.rowcount:
                    movs_fisico_ok += 1

                # ── Maintain supplier link ────────────────────────────────────
                linked = _upsert_proveedor_link(
                    pg, proveedor_id, product_id, supplier_sku, descripcion, costo
                )
                if not linked:
                    prod_prov_omitidos += 1
                    advertencias.append({
                        "folio": ref_display,
                        "codigo_pos": codigo_pos,
                        "source_uid": source_uid,
                        "motivo": "producto_proveedor omitido: supplier_sku vacío",
                    })

                # ── Update product cost and sync timestamp ────────────────────
                # Recency gate: update cost only when doc date is strictly newer
                # than the stored cost date, or same date with POS-origin cost
                # (MANUAL on same day wins — handled by excluding same-date POS).
                compra_fecha = line["fecha_linea"] or fecha
                if costo:
                    pg.execute(
                        text("""
                            UPDATE productos SET
                                price              = :costo,
                                costo_pos_con_iva  = :costo_iva,
                                costo_origen       = 'POS',
                                costo_fuente_fecha = :compra_fecha,
                                pos_ultimo_sync    = NOW()
                            WHERE id = :pid
                              AND (costo_fuente_fecha IS NULL
                                   OR :compra_fecha > costo_fuente_fecha
                                   OR (:compra_fecha = costo_fuente_fecha AND costo_origen = 'POS'))
                        """),
                        {"costo": costo, "costo_iva": costo_iva, "pid": product_id,
                         "compra_fecha": compra_fecha},
                    )
                else:
                    pg.execute(
                        text("UPDATE productos SET pos_ultimo_sync = NOW() WHERE id = :pid"),
                        {"pid": product_id},
                    )

            pg.execute(text("RELEASE SAVEPOINT sp_compra"))

        except Exception as e:
            logger.exception(
                "Error procesando compra pos_id=%s folio=%s", pos_compra_id, ref_display
            )
            try:
                pg.execute(text("ROLLBACK TO SAVEPOINT sp_compra"))
                pg.execute(text("RELEASE SAVEPOINT sp_compra"))
            except Exception:
                pass
            errores.append({
                "folio": ref_display,
                "codigo_pos": None,
                "source_uid": f"POS:COMPRA:{pos_compra_id}:*",
                "motivo": str(e),
            })
            continue

    pg.commit()

    total_err = len(errores)
    status    = "OK" if total_err == 0 else ("PARCIAL" if (compras_ok + movs_ok) > 0 else "ERROR")
    _log_sync(
        pg,
        "POS_COMPRAS",
        body.fecha_inicio,
        body.fecha_fin,
        status,
        compras_ok + movs_ok,
        total_err,
        notes=f"{prods_created} productos auto-creados" if prods_created else None,
    )

    return {
        "ok": status in ("OK", "PARCIAL"),
        "status": status,
        "compras_procesadas": compras_ok,
        "movimientos_fiscal_pos": movs_ok,
        "movimientos_fisico": movs_fisico_ok,
        "productos_auto_creados": prods_created,
        "duplicados_saltados": duplicados,
        "prod_prov_omitidos": prod_prov_omitidos,
        "errores": errores,
        "advertencias": advertencias,
    }


@router.get("/debug/pos-purchases")
def debug_pos_purchases(
    fecha_inicio: date = Query(...),
    fecha_fin: date = Query(...),
    pg: Session = Depends(get_db),
    pos: Session = Depends(get_pos_db),
):
    """
    Read-only preview of what /pos-compras would import for a date range.
    No writes. Shows per-line resolution status including seria_auto_creado.
    """
    headers = pos.execute(
        text("""
            SELECT
                d.DOCID                             AS pos_compra_id,
                d.CLIENTEID                         AS pos_proveedor_id,
                TRIM(CONCAT(d.SERIE, d.NUMERO))     AS folio_captura,
                d.ANTERIOR                          AS folio_factura,
                d.FECHA                             AS fecha,
                d.TOTAL                             AS total,
                d.TOTALPAGADO                       AS totalpagado,
                d.ESTADO                            AS estado
            FROM doc d
            WHERE d.TIPO = 'E'
              AND d.FECHA BETWEEN :fi AND :ff
            ORDER BY d.FECHA, d.DOCID
        """),
        {"fi": fecha_inicio, "ff": fecha_fin},
    ).mappings().all()

    result = []
    for header in headers:
        pos_compra_id = int(header["pos_compra_id"])
        pos_prov_id   = int(header["pos_proveedor_id"])
        folio_factura = (header["folio_factura"] or "").strip().upper() or None
        folio_captura = (header["folio_captura"] or "").strip() or None
        ref_display   = folio_factura or folio_captura or str(pos_compra_id)

        prov_row = pg.execute(
            text("SELECT id, nombre FROM proveedores WHERE pos_proveedor_id = :pid"),
            {"pid": pos_prov_id},
        ).mappings().first()

        compra_row = pg.execute(
            text("SELECT id FROM compras WHERE pos_compra_id = :cid"),
            {"cid": pos_compra_id},
        ).first()

        lines = pos.execute(
            text("""
                SELECT
                    des.DESID       AS desid,
                    inv.CLAVE       AS codigo_pos,
                    inv.CLVPROV     AS supplier_sku,
                    inv.DESCRIPCIO  AS descripcion,
                    des.DESCANTIDAD AS cantidad,
                    des.DESCOSTO    AS costo_unit
                FROM des
                JOIN inv ON inv.ARTICULOID = des.DESARTID
                WHERE des.DESDOCID = :docid
                  AND des.DESCANTIDAD != 0
                ORDER BY des.DESID
            """),
            {"docid": pos_compra_id},
        ).mappings().all()

        lineas = []
        for line in lines:
            desid      = int(line["desid"])
            codigo_pos = (line["codigo_pos"] or "").strip().upper()
            source_uid = f"POS:COMPRA:{pos_compra_id}:{desid}"

            es_tecnico = codigo_pos.startswith("_") if codigo_pos else False

            prod_row = None
            if codigo_pos and not es_tecnico:
                prod_row = pg.execute(
                    text("SELECT id FROM productos WHERE codigo_pos = :cp"),
                    {"cp": codigo_pos},
                ).first()

            ya_existe_mov = bool(
                pg.execute(
                    text("SELECT 1 FROM movimientos_inventario WHERE source_uid = :uid"),
                    {"uid": source_uid},
                ).first()
            )

            # seria_auto_creado: would this line trigger auto-create?
            seria_auto_creado = (
                not es_tecnico
                and prod_row is None
                and bool(codigo_pos)
                and len(codigo_pos) > 4
                and not ya_existe_mov
            )

            lineas.append({
                "desid": desid,
                "codigo_pos": codigo_pos,
                "supplier_sku": (line["supplier_sku"] or "").strip() or None,
                "descripcion": (line["descripcion"] or "").strip() or None,
                "cantidad": float(line["cantidad"] or 0),
                "costo_unit": float(line["costo_unit"] or 0) or None,
                "es_tecnico": es_tecnico,
                "producto_encontrado": prod_row is not None,
                "seria_auto_creado": seria_auto_creado,
                "movimiento_ya_existe": ya_existe_mov,
                "source_uid": source_uid,
            })

        result.append({
            "pos_compra_id": pos_compra_id,
            "folio": ref_display,
            "fecha": str(header["fecha"]),
            "total": float(header["total"] or 0),
            "totalpagado": float(header["totalpagado"] or 0),
            "estatus_pago_derivado": _derive_estatus_pago(
                float(header["totalpagado"] or 0), float(header["total"] or 0)
            ),
            "estado": (header["estado"] or "").strip(),
            "proveedor_encontrado": prov_row is not None,
            "proveedor_nombre": prov_row["nombre"] if prov_row else None,
            "compra_ya_importada": compra_row is not None,
            "lineas": lineas,
        })

    return {"compras": result, "count": len(result)}
