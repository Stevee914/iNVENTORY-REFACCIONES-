from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import text
from pydantic import BaseModel
from datetime import date
from APP.db import get_db
from APP.pos_db import get_pos_db

router = APIRouter(prefix="/import", tags=["POS - Fiscal"])


class FiscalInicialBody(BaseModel):
    fecha_inicio: date
    fecha_fin: date
    confirmar: bool = False


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


@router.post("/pos-fiscal-inicial")
def pos_fiscal_inicial(
    body: FiscalInicialBody,
    pg: Session = Depends(get_db),
    pos: Session = Depends(get_pos_db),
):
    """
    Carga inicial única del historial FISCAL_POS desde el POS.

    Procesa compras (doc.TIPO='E') y ventas (doc.TIPO='F') en el rango de fechas dado.
    Solo puede ejecutarse una vez con éxito; rechaza con HTTP 409 si ya existe
    un registro OK en sync_control para 'POS_FISCAL_INICIAL'.

    Restricciones:
    - Requiere confirmar=true en el body.
    - No toca el libro FISICO.
    - Idempotente: usa ON CONFLICT (source_uid) DO NOTHING.
    - Compras sin proveedor resuelto: se registran como error y se omiten.
    - stock negativo en FISCAL_POS es válido, no se bloquea.
    """
    if not body.confirmar:
        raise HTTPException(
            status_code=400,
            detail="Envíe confirmar=true para ejecutar la carga inicial.",
        )

    existing = pg.execute(
        text("""
            SELECT id FROM sync_control
            WHERE proceso = 'POS_FISCAL_INICIAL' AND status = 'OK'
            LIMIT 1
        """)
    ).first()
    if existing:
        raise HTTPException(
            status_code=409,
            detail=(
                "La carga inicial FISCAL_POS ya fue ejecutada exitosamente. "
                "Use POST /import/pos-compras y POST /import/pos-ventas para syncs periódicos."
            ),
        )

    in_ok: int = 0
    out_ok: int = 0
    err_compras: list[dict] = []
    err_ventas: list[dict] = []

    # ── Producto lookup cache (codigo_pos → product_id | None) ──────────────────
    prod_cache: dict[str, int | None] = {}
    # ── Proveedor lookup cache (pos_proveedor_id → proveedor_id | None) ─────────
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

    # ── 1. Compras (TIPO = 'E') ──────────────────────────────────────────────────
    compra_rows = pos.execute(
        text("""
            SELECT
                d.DOCID                             AS docid,
                d.CLIENTEID                         AS pos_proveedor_id,
                TRIM(CONCAT(d.SERIE, d.NUMERO))     AS folio,
                d.ANTERIOR                          AS folio_factura,
                d.FECHA                             AS fecha_doc,
                des.DESID                           AS desid,
                des.DESFECHA                        AS fecha_linea,
                inv.CLAVE                           AS codigo_pos,
                des.DESCANTIDAD                     AS cantidad,
                des.DESCOSTO                        AS costo_unit
            FROM doc d
            JOIN des ON des.DESDOCID = d.DOCID
            JOIN inv ON inv.ARTICULOID = des.DESARTID
            WHERE d.TIPO = 'E'
              AND d.FECHA BETWEEN :fi AND :ff
              AND des.DESCANTIDAD != 0
            ORDER BY d.DOCID, des.DESID
        """),
        {"fi": body.fecha_inicio, "ff": body.fecha_fin},
    ).mappings().all()

    for row in compra_rows:
        docid       = int(row["docid"])
        desid       = int(row["desid"])
        codigo_pos  = (row["codigo_pos"] or "").strip().upper()
        cantidad    = float(row["cantidad"] or 0)
        folio       = (row["folio"] or "").strip()
        source_uid  = f"POS:COMPRA:{docid}:{desid}"

        if not codigo_pos or cantidad == 0:
            continue

        # Resolve supplier — required by chk_proveedor_en_entradas
        proveedor_id = _get_proveedor(int(row["pos_proveedor_id"]))
        if proveedor_id is None:
            err_compras.append({
                "folio": folio,
                "codigo_pos": codigo_pos,
                "source_uid": source_uid,
                "motivo": f"proveedor POS {row['pos_proveedor_id']} no encontrado — "
                           "ejecute /sync/proveedores primero",
            })
            continue

        # Resolve product
        product_id = _get_product(codigo_pos)
        if product_id is None:
            err_compras.append({
                "folio": folio,
                "codigo_pos": codigo_pos,
                "source_uid": source_uid,
                "motivo": "producto no encontrado por codigo_pos",
            })
            continue

        costo      = float(row["costo_unit"] or 0) or None
        costo_iva  = round(costo * 1.16, 4) if costo else None
        # Positive qty = stock IN; negative = return (stock OUT)
        signed_qty = cantidad
        movement_type = "IN" if signed_qty > 0 else "OUT"
        fecha_mov  = row["fecha_linea"] or row["fecha_doc"]

        pg.execute(
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
            {
                "pid": product_id,
                "mt": movement_type,
                "qty": signed_qty,
                "costo": costo,
                "costo_iva": costo_iva,
                "prov": proveedor_id,
                "fecha": fecha_mov,
                "ref": folio,
                "uid": source_uid,
            },
        )
        in_ok += 1

    # ── 2. Ventas (TIPO = 'F') ───────────────────────────────────────────────────
    venta_rows = pos.execute(
        text("""
            SELECT
                d.DOCID                             AS docid,
                TRIM(CONCAT(d.SERIE, d.NUMERO))     AS folio,
                d.FECHA                             AS fecha_doc,
                des.DESID                           AS desid,
                des.DESFECHA                        AS fecha_linea,
                inv.CLAVE                           AS codigo_pos,
                des.DESCANTIDAD                     AS cantidad,
                des.DESVENTA                        AS precio_venta
            FROM doc d
            JOIN des ON des.DESDOCID = d.DOCID
            JOIN inv ON inv.ARTICULOID = des.DESARTID
            WHERE d.TIPO = 'F'
              AND d.FECHA BETWEEN :fi AND :ff
              AND des.DESCANTIDAD != 0
            ORDER BY d.DOCID, des.DESID
        """),
        {"fi": body.fecha_inicio, "ff": body.fecha_fin},
    ).mappings().all()

    for row in venta_rows:
        docid      = int(row["docid"])
        desid      = int(row["desid"])
        codigo_pos = (row["codigo_pos"] or "").strip().upper()
        cantidad   = float(row["cantidad"] or 0)
        folio      = (row["folio"] or "").strip()
        source_uid = f"POS:VENTA:{docid}:{desid}"

        if not codigo_pos or cantidad == 0:
            continue

        product_id = _get_product(codigo_pos)
        if product_id is None:
            err_ventas.append({
                "folio": folio,
                "codigo_pos": codigo_pos,
                "source_uid": source_uid,
                "motivo": "producto no encontrado por codigo_pos",
            })
            continue

        # Sales flip sign: positive sale = stock OUT (negative movement)
        signed_qty    = -cantidad
        movement_type = "OUT" if signed_qty < 0 else "IN"
        fecha_mov     = row["fecha_linea"] or row["fecha_doc"]
        precio        = float(row["precio_venta"] or 0) or None

        pg.execute(
            text("""
                INSERT INTO movimientos_inventario
                    (product_id, libro, movement_type, quantity, evento,
                     precio_venta_unit, movement_date, reference, source_uid)
                VALUES
                    (:pid, 'FISCAL_POS', :mt, :qty, 'VENTA_FACTURADA',
                     :precio, :fecha, :ref, :uid)
                ON CONFLICT (source_uid) DO NOTHING
            """),
            {
                "pid": product_id,
                "mt": movement_type,
                "qty": signed_qty,
                "precio": precio,
                "fecha": fecha_mov,
                "ref": folio,
                "uid": source_uid,
            },
        )
        out_ok += 1

    pg.commit()

    # ── 3. Registrar en sync_control ─────────────────────────────────────────────
    total_ok  = in_ok + out_ok
    total_err = len(err_compras) + len(err_ventas)
    status    = "OK" if total_err == 0 else ("PARCIAL" if total_ok > 0 else "ERROR")

    _log_sync(
        pg,
        "POS_FISCAL_INICIAL",
        body.fecha_inicio,
        body.fecha_fin,
        status,
        total_ok,
        total_err,
        f"{len(err_compras)} err_compra, {len(err_ventas)} err_venta",
    )

    return {
        "ok": status in ("OK", "PARCIAL"),
        "status": status,
        "in_insertados": in_ok,
        "out_insertados": out_ok,
        "errores_compra": len(err_compras),
        "errores_venta": len(err_ventas),
        "lista_errores": err_compras + err_ventas,
    }
