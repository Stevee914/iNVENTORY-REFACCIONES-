from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from sqlalchemy import text
from pydantic import BaseModel
from datetime import date
from APP.db import get_db
from APP.pos_db import get_pos_db

router = APIRouter(prefix="/import", tags=["POS - Ventas"])


class VentasBody(BaseModel):
    fecha_inicio: date
    fecha_fin: date


def _auto_create_product(pg: Session, codigo_pos: str, descripcion: str | None,
                         costo: float | None) -> int | None:
    """
    Insert a minimal producto row for a POS article not found in the catalog.
    Returns the new product id, or None if a sku conflict exists (ON CONFLICT DO NOTHING).
    Only called for codes longer than 4 chars with no leading underscore.
    cost comes from des.DESCOSTO (POS cost at time of sale) — used as price if > 0.
    """
    if not codigo_pos or len(codigo_pos) <= 4:
        return None
    codigo_cat = codigo_pos[:4]
    sku = codigo_pos[4:]
    name = ((descripcion or "").strip()[:80]) or codigo_pos
    costo_valido = costo is not None and costo > 0
    costo_iva = round(costo * 1.16, 4) if costo_valido else None
    new_id = pg.execute(
        text("""
            INSERT INTO productos
                (sku, codigo_pos, codigo_cat, name, unit, is_active,
                 price, costo_pos_con_iva, costo_origen, pos_ultimo_sync)
            VALUES
                (:sku, :cp, :cat, :name, 'PZA', true,
                 :price, :costo_iva, :origen, NOW())
            ON CONFLICT (sku) DO NOTHING
            RETURNING id
        """),
        {
            "sku": sku,
            "cp": codigo_pos,
            "cat": codigo_cat,
            "name": name,
            "price": costo if costo_valido else None,
            "costo_iva": costo_iva,
            "origen": "POS" if costo_valido else None,
        },
    ).scalar()
    return new_id


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


@router.post("/pos-ventas")
def import_pos_ventas(
    body: VentasBody,
    pg: Session = Depends(get_db),
    pos: Session = Depends(get_pos_db),
):
    """
    Sync periódico de ventas/facturas del POS.

    Por cada venta en el rango:
    - Resuelve o crea el cliente (por pos_cliente_id, luego RFC).
      Nunca sobreescribe campos que ya tienen valor en el sistema.
    - Hace upsert del encabezado en facturas (dedup por pos_documento_id).
    - Hace upsert de líneas en facturas_detalle (dedup por factura_id + pos_line_id).
      Guarda codigo_pos_snapshot y descripcion_snap tal como estaban en el momento del sync.
    - Inserta movimiento OUT en FISCAL_POS por cada línea con producto encontrado
      (idempotente por source_uid).
    - Auto-crea productos faltantes con datos mínimos del POS (codigo_pos, nombre, costo).
    - Si facturas_detalle ya existe con product_id=NULL, lo actualiza al id resuelto.
    - Actualiza productos.pos_ultimo_sync para productos que aparecen.
    - Registra resultado en sync_control.

    Líneas cuyo codigo_pos es inválido (vacío, <= 4 chars, empieza con _): se guardan
    en facturas_detalle con product_id=NULL y se reportan en lineas_sin_producto.
    No toca el libro FISICO.
    """
    facturas_ok: int = 0
    clientes_nuevos: int = 0
    movs_ok: int = 0
    duplicados: int = 0
    prods_created: int = 0
    lineas_anteriores_init: int = 0
    lineas_sin_producto: list[dict] = []
    errores: list[dict] = []

    # ── Caches ──────────────────────────────────────────────────────────────────
    prod_cache: dict[str, int | None] = {}
    cli_cache: dict[int, int | None] = {}
    # Cache de fecha mínima del primer movimiento FISCAL_POS por producto.
    # Ventas con fecha anterior a ese mínimo ya estaban en el stock inicial — no importar.
    init_date_cache: dict[int, object] = {}

    def _get_fiscal_init_date(product_id: int):
        if product_id not in init_date_cache:
            r = pg.execute(
                text("""
                    SELECT MIN(movement_date)::date
                    FROM movimientos_inventario
                    WHERE product_id = :pid AND libro = 'FISCAL_POS'
                """),
                {"pid": product_id},
            ).scalar()
            init_date_cache[product_id] = r  # date or None
        return init_date_cache[product_id]

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

    def _resolve_cliente(pos_cli_id: int) -> int | None:
        """
        Busca o crea el cliente en PostgreSQL.
        Match: pos_cliente_id → RFC → crear nuevo.
        Nunca sobreescribe campos que ya tienen valor.
        """
        if pos_cli_id in cli_cache:
            return cli_cache[pos_cli_id]

        # 1. Match by pos_cliente_id (already linked)
        existing = pg.execute(
            text("SELECT id FROM clientes WHERE pos_cliente_id = :pid"),
            {"pid": pos_cli_id},
        ).mappings().first()
        if existing:
            cli_cache[pos_cli_id] = int(existing["id"])
            return cli_cache[pos_cli_id]

        # Fetch client data from POS
        pos_cli = pos.execute(
            text("""
                SELECT
                    c.NOMBRE    AS nombre,
                    c.ACTIVO    AS activo,
                    dom.RFC     AS rfc
                FROM cli c
                LEFT JOIN dom ON dom.CLIENTEID = c.CLIENTEID
                WHERE c.CLIENTEID = :cid
                LIMIT 1
            """),
            {"cid": pos_cli_id},
        ).mappings().first()

        if not pos_cli:
            cli_cache[pos_cli_id] = None
            return None

        nombre  = (pos_cli["nombre"] or "").strip().upper()
        rfc_raw = (pos_cli["rfc"] or "").strip().upper().replace(" ", "")
        rfc     = rfc_raw or None
        activo  = pos_cli["activo"] == "S"

        if not nombre:
            cli_cache[pos_cli_id] = None
            return None

        # 2. Match by RFC
        if rfc:
            by_rfc = pg.execute(
                text("SELECT id FROM clientes WHERE rfc = :rfc LIMIT 1"),
                {"rfc": rfc},
            ).mappings().first()
            if by_rfc:
                pg.execute(
                    text("""
                        UPDATE clientes
                           SET pos_cliente_id = :pid,
                               updated_at     = NOW()
                         WHERE id = :id
                           AND pos_cliente_id IS NULL
                    """),
                    {"pid": pos_cli_id, "id": by_rfc["id"]},
                )
                cli_cache[pos_cli_id] = int(by_rfc["id"])
                return cli_cache[pos_cli_id]

        # 3. Create new client
        nonlocal clientes_nuevos
        new_id = pg.execute(
            text("""
                INSERT INTO clientes (nombre, rfc, is_active, pos_cliente_id)
                VALUES (:nombre, :rfc, :active, :pid)
                ON CONFLICT (pos_cliente_id) DO UPDATE
                    SET nombre = EXCLUDED.nombre
                RETURNING id
            """),
            {"nombre": nombre, "rfc": rfc, "active": activo, "pid": pos_cli_id},
        ).scalar()
        clientes_nuevos += 1
        cli_cache[pos_cli_id] = int(new_id)
        return cli_cache[pos_cli_id]

    # ── Pull sale headers ────────────────────────────────────────────────────────
    headers = pos.execute(
        text("""
            SELECT
                d.DOCID                             AS pos_doc_id,
                d.CLIENTEID                         AS pos_cli_id,
                TRIM(d.SERIE)                       AS serie,
                CAST(d.NUMERO AS CHAR)              AS folio,
                d.FECHA                             AS fecha,
                ROUND(d.TOTAL - d.IMPUESTO, 2)      AS subtotal,
                d.IMPUESTO                          AS iva,
                d.TOTAL                             AS total,
                d.COND                              AS cond,
                d.DOCCFDID                          AS pos_cfd_id,
                cfd.UUID                            AS uuid
            FROM doc d
            LEFT JOIN cfd ON cfd.CFDID = d.DOCCFDID AND d.DOCCFDID != 0
            WHERE d.TIPO = 'F'
              AND d.FECHA BETWEEN :fi AND :ff
            ORDER BY d.FECHA, d.DOCID
        """),
        {"fi": body.fecha_inicio, "ff": body.fecha_fin},
    ).mappings().all()

    for header in headers:
        pos_doc_id     = int(header["pos_doc_id"])
        pos_cli_id     = int(header["pos_cli_id"])
        serie          = (header["serie"] or "").strip() or None
        folio          = (header["folio"] or "").strip()
        folio_display  = f"{serie or ''}{folio}"
        fecha          = header["fecha"]
        subtotal       = float(header["subtotal"] or 0)
        iva            = float(header["iva"] or 0)
        total          = float(header["total"] or 0)
        pos_cfd_id     = int(header["pos_cfd_id"]) if header["pos_cfd_id"] else None
        uuid           = (header["uuid"] or "").strip() or None
        cond           = (header["cond"] or "").strip().upper()
        condicion_pago = "CONTADO" if cond == "C" else ("CREDITO" if cond == "R" else None)

        try:
            pg.execute(text("SAVEPOINT sp_venta"))

            # ── Resolver / crear cliente ──────────────────────────────────────
            cliente_id = _resolve_cliente(pos_cli_id)

            # ── Upsert encabezado factura ─────────────────────────────────────
            # uq_pos_documento_id: UNIQUE(pos_documento_id)
            factura_id = pg.execute(
                text("""
                    INSERT INTO facturas
                        (folio, serie, cliente_id, monto, subtotal, iva, fecha,
                         estatus, metodo_pago, condicion_pago,
                         origen, tipo_documento,
                         pos_documento_id, pos_cfd_id, uuid)
                    VALUES
                        (:folio, :serie, :cli, :monto, :sub, :iva, :fecha,
                         'EMITIDA', 'CONTADO', :cond,
                         'POS', 'VENTA',
                         :pos_id, :cfd_id, :uuid)
                    ON CONFLICT (pos_documento_id) WHERE pos_documento_id IS NOT NULL
                    DO UPDATE SET
                        estatus    = EXCLUDED.estatus,
                        updated_at = NOW()
                    RETURNING id
                """),
                {
                    "folio": folio,
                    "serie": serie,
                    "cli": cliente_id,
                    "monto": total,
                    "sub": subtotal,
                    "iva": iva,
                    "fecha": fecha,
                    "cond": condicion_pago,
                    "pos_id": pos_doc_id,
                    "cfd_id": pos_cfd_id,
                    "uuid": uuid,
                },
            ).scalar()
            facturas_ok += 1

            # ── Pull lines for this sale ──────────────────────────────────────
            lines = pos.execute(
                text("""
                    SELECT
                        des.DESID           AS desid,
                        des.DESFECHA        AS fecha_linea,
                        inv.CLAVE           AS codigo_pos,
                        inv.DESCRIPCIO      AS descripcion,
                        des.DESCANTIDAD     AS cantidad,
                        des.DESVENTA        AS precio_venta,
                        des.DESCOSTO        AS costo_venta
                    FROM des
                    JOIN inv ON inv.ARTICULOID = des.DESARTID
                    WHERE des.DESDOCID = :docid
                      AND des.DESCANTIDAD != 0
                    ORDER BY des.DESID
                """),
                {"docid": pos_doc_id},
            ).mappings().all()

            for line in lines:
                desid       = int(line["desid"])
                codigo_pos  = (line["codigo_pos"] or "").strip().upper()
                cantidad    = float(line["cantidad"] or 0)
                source_uid  = f"POS:VENTA:{pos_doc_id}:{desid}"
                descripcion = (line["descripcion"] or "").strip() or None

                if not codigo_pos or cantidad == 0:
                    continue

                # Skip CONTPAQi technical articles (e.g. _ARTIMP)
                if codigo_pos.startswith("_"):
                    continue

                costo_venta = float(line["costo_venta"] or 0) or None
                precio      = float(line["precio_venta"] or 0) or None
                sub_linea   = round(precio * abs(cantidad), 2) if precio else None

                # ── Resolve product (auto-create if missing and code is valid) ─
                product_id = _get_product(codigo_pos)
                if product_id is None:
                    new_id = _auto_create_product(pg, codigo_pos, descripcion, costo_venta)
                    if new_id:
                        prod_cache[codigo_pos] = new_id
                        product_id = new_id
                        prods_created += 1

                # ── Upsert facturas_detalle — dedup por (factura_id, pos_line_id) ─
                pg.execute(
                    text("""
                        INSERT INTO facturas_detalle
                            (factura_id, product_id, codigo_pos_snapshot,
                             descripcion_snap, cantidad, precio_unitario,
                             subtotal, pos_line_id)
                        VALUES
                            (:fid, :pid, :cp, :desc, :qty, :precio, :sub, :plid)
                        ON CONFLICT (factura_id, pos_line_id) DO NOTHING
                    """),
                    {
                        "fid": factura_id,
                        "pid": product_id,
                        "cp": codigo_pos,
                        "desc": descripcion,
                        "qty": cantidad,
                        "precio": precio,
                        "sub": sub_linea,
                        "plid": str(desid),
                    },
                )

                # ── Backfill product_id if detail row already exists with NULL ─
                if product_id is not None:
                    pg.execute(
                        text("""
                            UPDATE facturas_detalle
                               SET product_id = :pid
                             WHERE factura_id = :fid
                               AND pos_line_id = :plid
                               AND product_id IS NULL
                        """),
                        {"pid": product_id, "fid": factura_id, "plid": str(desid)},
                    )

                if product_id is None:
                    lineas_sin_producto.append({
                        "folio": folio_display,
                        "codigo_pos": codigo_pos,
                        "source_uid": source_uid,
                        "motivo": "producto no encontrado ni creado (codigo_pos <= 4 chars o conflicto sku)",
                    })
                    continue

                # Skip movements that predate this product's FISCAL_POS baseline
                # (those sales were already captured in the stock-pos initial load)
                fecha_linea_val = line["fecha_linea"] or fecha
                fecha_linea_d = fecha_linea_val.date() if hasattr(fecha_linea_val, "date") else fecha_linea_val
                init_date = _get_fiscal_init_date(product_id)
                if init_date and fecha_linea_d < init_date:
                    lineas_anteriores_init += 1
                    continue

                # Verificar si ya existe (idempotencia explícita antes del INSERT)
                already = pg.execute(
                    text("SELECT id FROM movimientos_inventario WHERE source_uid = :uid"),
                    {"uid": source_uid},
                ).first()

                if already:
                    duplicados += 1
                    continue

                # Sales flip sign: positive sale = stock OUT
                signed_qty    = -cantidad
                movement_type = "OUT" if signed_qty < 0 else "IN"

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
                        "fecha": line["fecha_linea"] or fecha,
                        "ref": folio_display,
                        "uid": source_uid,
                    },
                )
                movs_ok += 1

                pg.execute(
                    text("UPDATE productos SET pos_ultimo_sync = NOW() WHERE id = :pid"),
                    {"pid": product_id},
                )

            pg.execute(text("RELEASE SAVEPOINT sp_venta"))

        except Exception as e:
            try:
                pg.execute(text("ROLLBACK TO SAVEPOINT sp_venta"))
                pg.execute(text("RELEASE SAVEPOINT sp_venta"))
            except Exception:
                pass
            errores.append({
                "folio": folio_display,
                "codigo_pos": None,
                "source_uid": f"POS:VENTA:{pos_doc_id}:*",
                "motivo": str(e),
            })
            continue

    pg.commit()

    total_err = len(errores)
    status    = "OK" if total_err == 0 else ("PARCIAL" if (facturas_ok + movs_ok) > 0 else "ERROR")
    notes_parts = []
    if prods_created:
        notes_parts.append(f"{prods_created} productos auto-creados")
    if lineas_sin_producto:
        notes_parts.append(f"{len(lineas_sin_producto)} lineas sin producto")
    _log_sync(
        pg,
        "POS_VENTAS",
        body.fecha_inicio,
        body.fecha_fin,
        status,
        facturas_ok + movs_ok,
        total_err,
        "; ".join(notes_parts) or None,
    )

    return {
        "ok": status in ("OK", "PARCIAL"),
        "status": status,
        "facturas_procesadas": facturas_ok,
        "clientes_nuevos": clientes_nuevos,
        "movimientos_out": movs_ok,
        "productos_auto_creados": prods_created,
        "duplicados_saltados": duplicados,
        "lineas_anteriores_init_saltadas": lineas_anteriores_init,
        "lineas_sin_producto": lineas_sin_producto,
        "errores": errores,
    }
