from fastapi import APIRouter, Depends, Query, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import text
from APP.db import get_db
from APP.pos_db import get_pos_db
from APP.schemas_clientes import FacturaCreate, FacturaUpdate, PagoCreate
from APP.helpers import normalize_text
from datetime import date, timedelta

router = APIRouter(prefix="/facturas", tags=["Ventas y Cobranza"])

TIPOS_DOCUMENTO = ("FACTURA", "NOTA_VENTA", "CREDITO", "REMISION")
ESTATUS_VALIDOS = ("PAGADA", "CREDITO", "PARCIAL")
CONDICIONES_PAGO = ("CONTADO", "CREDITO_15", "CREDITO_30", "CREDITO_60")


@router.get("")
def list_facturas(
    fecha_inicio: date | None = Query(default=None),
    fecha_fin: date | None = Query(default=None),
    cliente_id: int | None = Query(default=None),
    estatus: str | None = Query(default=None),
    tipo_documento: str | None = Query(default=None),
    solo_pendientes: bool = Query(default=False),
    q: str | None = Query(default=None),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=50, ge=1, le=200),
    db: Session = Depends(get_db),
):
    where = []
    params: dict = {}

    if fecha_inicio:
        where.append("f.fecha >= :fi")
        params["fi"] = fecha_inicio
    if fecha_fin:
        where.append("f.fecha <= :ff")
        params["ff"] = fecha_fin
    if cliente_id:
        where.append("f.cliente_id = :cid")
        params["cid"] = cliente_id
    if estatus:
        where.append("f.estatus = :est")
        params["est"] = estatus.upper()
    if tipo_documento:
        where.append("f.tipo_documento = :tipo")
        params["tipo"] = tipo_documento.upper()
    if q:
        where.append("(f.folio ILIKE :q OR c.nombre ILIKE :q)")
        params["q"] = f"%{normalize_text(q)}%"

    where_sql = ("WHERE " + " AND ".join(where)) if where else ""
    having_sql = "HAVING f.monto - COALESCE(SUM(p.monto), 0) > 0.01" if solo_pendientes else ""

    offset = (page - 1) * page_size
    params["limit"] = page_size
    params["offset"] = offset

    if solo_pendientes:
        total = db.execute(text(f"""
            SELECT COUNT(*) FROM (
                SELECT f.id FROM facturas f
                LEFT JOIN clientes c ON c.id = f.cliente_id
                LEFT JOIN pagos p ON p.factura_id = f.id
                {where_sql} GROUP BY f.id, c.nombre {having_sql}
            ) sub
        """), params).scalar()
    else:
        total = db.execute(text(f"""
            SELECT COUNT(*) FROM facturas f
            LEFT JOIN clientes c ON c.id = f.cliente_id {where_sql}
        """), params).scalar()

    rows = db.execute(text(f"""
        SELECT f.id, f.folio, f.cliente_id, c.nombre AS cliente_nombre, c.rfc AS cliente_rfc,
               f.monto, f.fecha, f.estatus, f.tipo_documento, f.condicion_pago,
               f.fecha_vencimiento, f.metodo_pago, f.notas, f.created_at,
               COALESCE(SUM(p.monto), 0) AS total_pagado,
               f.monto - COALESCE(SUM(p.monto), 0) AS saldo_pendiente
        FROM facturas f
        LEFT JOIN clientes c ON c.id = f.cliente_id
        LEFT JOIN pagos p ON p.factura_id = f.id
        {where_sql}
        GROUP BY f.id, c.nombre, c.rfc
        {having_sql}
        ORDER BY f.fecha DESC, f.folio DESC
        LIMIT :limit OFFSET :offset
    """), params).mappings().all()

    return {"items": rows, "total": int(total or 0), "page": page, "page_size": page_size}


@router.get("/resumen-cobranza")
def resumen_cobranza(
    fecha_inicio: date | None = Query(default=None, description="Start date for docs/vendido KPIs"),
    fecha_fin:    date | None = Query(default=None, description="End date for docs/vendido KPIs"),
    db: Session = Depends(get_db),
):
    # All-time: por_cobrar, pendientes, vencidos
    # Date-filtered (when params provided): total_documentos, total_vendido
    date_where = ""
    date_params: dict = {}
    if fecha_inicio:
        date_where += " AND f.fecha >= :fi"
        date_params["fi"] = fecha_inicio
    if fecha_fin:
        date_where += " AND f.fecha <= :ff"
        date_params["ff"] = fecha_fin

    row = db.execute(text(f"""
        SELECT
            (SELECT COUNT(*) FROM facturas f WHERE 1=1 {date_where}) AS total_documentos,
            COALESCE((SELECT SUM(f.monto) FROM facturas f WHERE 1=1 {date_where}), 0) AS total_vendido,
            COALESCE(SUM(f.monto) - SUM(COALESCE(pg.pagado, 0)), 0) AS total_por_cobrar,
            COUNT(*) FILTER (WHERE f.estatus IN ('CREDITO', 'PARCIAL')) AS docs_pendientes,
            COUNT(*) FILTER (WHERE f.fecha_vencimiento IS NOT NULL
                             AND f.fecha_vencimiento < CURRENT_DATE
                             AND f.estatus IN ('CREDITO', 'PARCIAL')) AS docs_vencidos
        FROM facturas f
        LEFT JOIN (SELECT factura_id, SUM(monto) AS pagado FROM pagos GROUP BY factura_id) pg
            ON pg.factura_id = f.id
    """), date_params).mappings().first()
    return dict(row) if row else {}


@router.get("/por-cliente/{cliente_id}")
def facturas_por_cliente(cliente_id: int, db: Session = Depends(get_db)):
    rows = db.execute(text("""
        SELECT f.id, f.folio, f.monto, f.fecha, f.estatus, f.tipo_documento,
               f.condicion_pago, f.metodo_pago, f.notas,
               COALESCE(SUM(p.monto), 0) AS total_pagado,
               f.monto - COALESCE(SUM(p.monto), 0) AS saldo_pendiente
        FROM facturas f
        LEFT JOIN pagos p ON p.factura_id = f.id
        WHERE f.cliente_id = :cid
        GROUP BY f.id
        ORDER BY f.fecha DESC
    """), {"cid": cliente_id}).mappings().all()
    return {"items": rows, "count": len(rows)}


def _auto_pago_si_pagada(db: Session, factura_id: int, monto: float, fecha: date, metodo_pago: str | None):
    pagado = db.execute(
        text("SELECT COALESCE(SUM(monto), 0) FROM pagos WHERE factura_id = :fid"),
        {"fid": factura_id},
    ).scalar()
    saldo = monto - float(pagado)
    if saldo <= 0.01:
        return
    db.execute(text("""
        INSERT INTO pagos (factura_id, monto, fecha, metodo_pago, referencia, notas)
        VALUES (:fid, :monto, :fecha, :mp, 'AUTO', 'Pago automático al marcar como PAGADA')
    """), {"fid": factura_id, "monto": round(saldo, 2), "fecha": fecha, "mp": metodo_pago})


@router.post("")
def create_factura(payload: FacturaCreate, db: Session = Depends(get_db)):
    folio = normalize_text(payload.folio).upper()
    if not folio:
        raise HTTPException(status_code=400, detail="El folio es obligatorio")

    cliente = db.execute(
        text("SELECT id, nombre FROM clientes WHERE id = :id"),
        {"id": payload.cliente_id},
    ).mappings().first()
    if not cliente:
        raise HTTPException(status_code=404, detail=f"Cliente no encontrado: {payload.cliente_id}")
    if payload.monto <= 0:
        raise HTTPException(status_code=400, detail="El monto debe ser mayor a 0")

    fecha = payload.fecha or date.today()
    estatus = normalize_text(payload.estatus).upper() or "PAGADA"
    if estatus not in ESTATUS_VALIDOS:
        raise HTTPException(status_code=400, detail=f"Estatus debe ser: {', '.join(ESTATUS_VALIDOS)}")

    tipo_doc = normalize_text(payload.tipo_documento).upper() or "FACTURA"
    if tipo_doc not in TIPOS_DOCUMENTO:
        raise HTTPException(status_code=400, detail=f"tipo_documento debe ser: {', '.join(TIPOS_DOCUMENTO)}")

    condicion = normalize_text(payload.condicion_pago).upper() or "CONTADO"
    metodo_pago = normalize_text(payload.metodo_pago).upper() or None

    fecha_venc = payload.fecha_vencimiento
    if not fecha_venc and condicion.startswith("CREDITO_"):
        try:
            dias = int(condicion.split("_")[1])
            fecha_venc = fecha + timedelta(days=dias)
        except Exception:
            pass

    try:
        row = db.execute(text("""
            INSERT INTO facturas (folio, cliente_id, monto, fecha, estatus, tipo_documento,
                                  condicion_pago, fecha_vencimiento, metodo_pago, notas)
            VALUES (:folio, :cid, :monto, :fecha, :estatus, :tipo, :condicion, :fv, :mp, :notas)
            RETURNING id, folio, cliente_id, monto, fecha, estatus, tipo_documento,
                      condicion_pago, fecha_vencimiento, metodo_pago, notas, created_at
        """), {
            "folio": folio, "cid": payload.cliente_id, "monto": payload.monto,
            "fecha": fecha, "estatus": estatus, "tipo": tipo_doc,
            "condicion": condicion, "fv": fecha_venc,
            "mp": metodo_pago, "notas": normalize_text(payload.notas) or None,
        }).mappings().one()

        if estatus == "PAGADA":
            _auto_pago_si_pagada(db, row["id"], payload.monto, fecha, metodo_pago)
        db.commit()
    except Exception as e:
        db.rollback()
        if "uq_folio" in str(e):
            raise HTTPException(status_code=409, detail=f"El folio {folio} ya existe")
        raise HTTPException(status_code=500, detail=str(e))

    return {"ok": True, "factura": dict(row)}


@router.patch("/{factura_id}")
def update_factura(factura_id: int, payload: FacturaUpdate, db: Session = Depends(get_db)):
    existing = db.execute(
        text("SELECT id, monto, fecha, estatus, metodo_pago, origen FROM facturas WHERE id = :id"),
        {"id": factura_id},
    ).mappings().first()
    if not existing:
        raise HTTPException(status_code=404, detail="Documento no encontrado")

    updates = []
    params = {"id": factura_id}

    if payload.folio is not None:
        folio_norm = normalize_text(payload.folio).upper()
        conflict = db.execute(
            text("SELECT id FROM facturas WHERE folio = :folio AND origen = :origen AND id != :id"),
            {"folio": folio_norm, "origen": existing["origen"], "id": factura_id},
        ).first()
        if conflict:
            raise HTTPException(status_code=409, detail=f"El folio {folio_norm} ya existe")
        updates.append("folio = :folio"); params["folio"] = folio_norm
    if payload.fecha is not None:
        updates.append("fecha = :fecha"); params["fecha"] = payload.fecha
    if payload.monto is not None:
        updates.append("monto = :monto"); params["monto"] = payload.monto
    if payload.estatus is not None:
        est = normalize_text(payload.estatus).upper()
        if est not in ESTATUS_VALIDOS:
            raise HTTPException(status_code=400, detail=f"Estatus debe ser: {', '.join(ESTATUS_VALIDOS)}")
        updates.append("estatus = :estatus"); params["estatus"] = est
    if payload.tipo_documento is not None:
        td = normalize_text(payload.tipo_documento).upper()
        if td not in TIPOS_DOCUMENTO:
            raise HTTPException(status_code=400, detail=f"tipo_documento debe ser: {', '.join(TIPOS_DOCUMENTO)}")
        updates.append("tipo_documento = :tipo_documento"); params["tipo_documento"] = td
    if payload.condicion_pago is not None:
        updates.append("condicion_pago = :condicion_pago")
        params["condicion_pago"] = normalize_text(payload.condicion_pago).upper()
    if payload.fecha_vencimiento is not None:
        updates.append("fecha_vencimiento = :fecha_vencimiento")
        params["fecha_vencimiento"] = payload.fecha_vencimiento
    if payload.metodo_pago is not None:
        updates.append("metodo_pago = :mp")
        params["mp"] = normalize_text(payload.metodo_pago).upper() or None
    if payload.notas is not None:
        updates.append("notas = :notas")
        params["notas"] = normalize_text(payload.notas) or None

    if not updates:
        raise HTTPException(status_code=400, detail="No se enviaron campos")

    row = db.execute(text(f"""
        UPDATE facturas SET {", ".join(updates)} WHERE id = :id
        RETURNING id, folio, cliente_id, monto, fecha, estatus, tipo_documento,
                  condicion_pago, fecha_vencimiento, metodo_pago, notas
    """), params).mappings().one()

    nuevo_estatus = params.get("estatus", existing["estatus"])
    if nuevo_estatus == "PAGADA":
        monto_factura = params.get("monto", float(existing["monto"]))
        metodo = params.get("mp", existing["metodo_pago"])
        _auto_pago_si_pagada(db, factura_id, monto_factura, existing["fecha"], metodo)

    db.commit()
    return {"ok": True, "factura": dict(row)}


@router.delete("/{factura_id}")
def delete_factura(factura_id: int, db: Session = Depends(get_db)):
    existing = db.execute(
        text("SELECT id FROM facturas WHERE id = :id"), {"id": factura_id},
    ).mappings().first()
    if not existing:
        raise HTTPException(status_code=404, detail="Documento no encontrado")
    db.execute(text("DELETE FROM pagos WHERE factura_id = :id"), {"id": factura_id})
    db.execute(text("DELETE FROM facturas WHERE id = :id"), {"id": factura_id})
    db.commit()
    return {"ok": True, "deleted": factura_id}


# ═══════════════════════════════════════════════════
# REPORTES  (must be before /{factura_id} to avoid int-parse 422)
# ═══════════════════════════════════════════════════

@router.get("/reporte/diario")
def reporte_diario(
    fecha: date = Query(default=None),
    tipo_documento: str | None = Query(default=None),
    db: Session = Depends(get_db),
):
    dia = fecha or date.today()
    where = ["f.fecha = :dia"]
    params: dict = {"dia": dia}
    if tipo_documento:
        where.append("f.tipo_documento = :tipo")
        params["tipo"] = tipo_documento.upper()

    facturas = db.execute(text(f"""
        SELECT f.folio, c.nombre AS cliente, f.monto, f.estatus, f.tipo_documento, f.metodo_pago
        FROM facturas f LEFT JOIN clientes c ON c.id = f.cliente_id
        WHERE {" AND ".join(where)} ORDER BY f.folio
    """), params).mappings().all()

    total = sum(float(f["monto"]) for f in facturas)
    folios = [f["folio"] for f in facturas]
    return {
        "fecha": str(dia), "total_facturas": len(facturas),
        "rango_folios": f"{folios[0]} - {folios[-1]}" if folios else "—",
        "total_dia": round(total, 2), "facturas": facturas,
    }


@router.get("/reporte/mensual")
def reporte_mensual(
    anio: int = Query(default=None), mes: int = Query(default=None, ge=1, le=12),
    tipo_documento: str | None = Query(default=None),
    db: Session = Depends(get_db),
):
    hoy = date.today()
    anio = anio or hoy.year
    mes = mes or hoy.month
    where = ["EXTRACT(YEAR FROM f.fecha) = :anio", "EXTRACT(MONTH FROM f.fecha) = :mes"]
    params: dict = {"anio": anio, "mes": mes}
    if tipo_documento:
        where.append("f.tipo_documento = :tipo")
        params["tipo"] = tipo_documento.upper()

    rows = db.execute(text(f"""
        SELECT f.fecha, MIN(f.folio) AS folio_inicio, MAX(f.folio) AS folio_fin,
               COUNT(*) AS num_facturas, SUM(f.monto) AS total_dia
        FROM facturas f WHERE {" AND ".join(where)}
        GROUP BY f.fecha ORDER BY f.fecha
    """), params).mappings().all()

    gran_total = sum(float(r["total_dia"]) for r in rows)
    total_facturas = sum(int(r["num_facturas"]) for r in rows)
    return {
        "anio": anio, "mes": mes, "dias": rows,
        "total_dias_con_ventas": len(rows), "total_facturas": total_facturas,
        "gran_total": round(gran_total, 2),
    }


@router.get("/reporte/clientes-mayores")
def reporte_clientes_mayores(
    anio: int | None = Query(default=None), mes: int | None = Query(default=None, ge=1, le=12),
    min_monto: float = Query(default=1000), db: Session = Depends(get_db),
):
    hoy = date.today()
    anio = anio or hoy.year
    mes = mes or hoy.month
    rows = db.execute(text("""
        SELECT c.id, c.nombre, c.rfc, COUNT(f.id) AS num_facturas, SUM(f.monto) AS total_compras
        FROM facturas f JOIN clientes c ON c.id = f.cliente_id
        WHERE EXTRACT(YEAR FROM f.fecha) = :anio AND EXTRACT(MONTH FROM f.fecha) = :mes
        GROUP BY c.id, c.nombre, c.rfc HAVING SUM(f.monto) >= :min
        ORDER BY total_compras DESC
    """), {"anio": anio, "mes": mes, "min": min_monto}).mappings().all()
    return {"anio": anio, "mes": mes, "min_monto": min_monto, "clientes": rows, "total_clientes": len(rows)}


# ═══════════════════════════════════════════════════
# CONTROL CFDI  (must be before /{factura_id})
# ═══════════════════════════════════════════════════

@router.get("/control/cancelados")
def control_cancelados(
    fecha_inicio: date | None = Query(default=None),
    fecha_fin:    date | None = Query(default=None),
    db:  Session = Depends(get_db),
    pos: Session = Depends(get_pos_db),
):
    """
    Live report of cancelled CFDIs from POS (ESTADO='A').
    Queries FerrumOP directly — not from the local facturas table.
    For each cancelled CFDI, attempts to find a likely replacement CFDI
    (same client, same amount ±1 peso, within 7 days, ESTADO='S').
    """
    fi = fecha_inicio or date(date.today().year, date.today().month, 1)
    ff = fecha_fin    or date.today()

    # Pull ALL cancelled CFDIs in the date range.
    # LEFT JOIN doc so CFDIs not linked to a doc record are still included.
    cancelled_rows = pos.execute(text("""
        SELECT
            c.CFDID     AS cfdid,
            c.FOLIO     AS folio,
            c.SERIE     AS serie,
            c.FECHA     AS fecha,
            c.TOTAL     AS total,
            c.UUID      AS uuid,
            c.ESTADO    AS estado,
            d.CLIENTEID AS pos_cliente_id,
            cl.NOMBRE   AS cliente_nombre
        FROM cfd c
        LEFT  JOIN doc d  ON d.DOCID  = c.DOCID
        LEFT  JOIN cli cl ON cl.CLIENTEID = d.CLIENTEID
        WHERE c.ESTADO = 'A'
          AND c.TIPDOC = 'F'
          AND c.FECHA BETWEEN :fi AND :ff
        ORDER BY c.FECHA DESC, c.FOLIO DESC
    """), {"fi": fi, "ff": ff}).mappings().all()

    result = []
    total_monto_cancelado = 0.0

    for row in cancelled_rows:
        monto = float(row["total"] or 0)
        total_monto_cancelado += monto

        # Look for a likely replacement: same client, ±1 peso, within 7 days before or after.
        # SAT CFDI workflow: replacement is usually issued BEFORE the cancellation, so we
        # search ±7 days. Only attempt if we have a client to search against.
        rep = None
        if row["pos_cliente_id"] is not None:
            rep = pos.execute(text("""
                SELECT c2.FOLIO AS folio, c2.FECHA AS fecha, c2.TOTAL AS total, c2.UUID AS uuid
                FROM cfd c2
                INNER JOIN doc d2 ON d2.DOCID = c2.DOCID
                WHERE d2.CLIENTEID = :cli
                  AND c2.ESTADO    = 'S'
                  AND c2.TIPDOC    = 'F'
                  AND ABS(c2.TOTAL - :total) <= 1
                  AND c2.FECHA BETWEEN DATE_SUB(:fecha, INTERVAL 7 DAY)
                                   AND DATE_ADD(:fecha, INTERVAL 7 DAY)
                  AND c2.CFDID != :cfdid
                ORDER BY ABS(DATEDIFF(c2.FECHA, :fecha)), c2.CFDID
                LIMIT 1
            """), {
                "cli":   row["pos_cliente_id"],
                "total": monto,
                "fecha": row["fecha"],
                "cfdid": row["cfdid"],
            }).mappings().first()

        # Also check whether the cancelled folio exists in local facturas (stale row)
        stale = db.execute(
            text("SELECT id FROM facturas WHERE pos_cfd_id = :cfdid"),
            {"cfdid": row["cfdid"]},
        ).scalar()

        result.append({
            "folio":           (row["serie"] or "").strip() + str(row["folio"] or ""),
            "serie":           (row["serie"] or "").strip() or None,
            "fecha":           str(row["fecha"]),
            "monto":           monto,
            "uuid":            row["uuid"],
            "cliente":         row["cliente_nombre"],
            "pos_cfd_id":      row["cfdid"],
            "en_sistema":      stale is not None,   # True = stale row still in facturas
            "reemplazo": {
                "folio": str(rep["folio"] or ""),
                "fecha": str(rep["fecha"]),
                "monto": float(rep["total"] or 0),
                "uuid":  rep["uuid"],
            } if rep else None,
        })

    return {
        "fecha_inicio":          str(fi),
        "fecha_fin":             str(ff),
        "total_cancelados":      len(result),
        "total_monto_cancelado": round(total_monto_cancelado, 2),
        "cancelados":            result,
    }


# ═══════════════════════════════════════════════════
# DASHBOARD  (must be before /{factura_id})
# ═══════════════════════════════════════════════════

@router.get("/dashboard")
def ventas_dashboard(
    anio:      int | None   = Query(default=None),
    mes:       int | None   = Query(default=None, ge=1, le=12),
    min_monto: float        = Query(default=5000),
    db: Session = Depends(get_db),
):
    hoy = date.today()
    anio = anio or hoy.year
    mes  = mes  or hoy.month

    row = db.execute(text("""
        SELECT
            COUNT(*)
                FILTER (WHERE EXTRACT(YEAR  FROM fecha) = :anio
                          AND EXTRACT(MONTH FROM fecha) = :mes)            AS total_documentos,
            COALESCE(SUM(monto)
                FILTER (WHERE EXTRACT(YEAR  FROM fecha) = :anio
                          AND EXTRACT(MONTH FROM fecha) = :mes), 0)        AS total_vendido,
            COUNT(DISTINCT cliente_id)
                FILTER (WHERE EXTRACT(YEAR  FROM fecha) = :anio
                          AND EXTRACT(MONTH FROM fecha) = :mes)            AS clientes_con_compra,
            COALESCE(SUM(
                CASE WHEN estatus IN ('CREDITO','PARCIAL')
                     THEN f.monto - COALESCE(pg.pagado, 0) ELSE 0 END
            ), 0)                                                          AS total_por_cobrar,
            COUNT(*) FILTER (WHERE estatus IN ('CREDITO','PARCIAL'))       AS docs_pendientes,
            COUNT(*) FILTER (WHERE fecha_vencimiento IS NOT NULL
                              AND fecha_vencimiento < CURRENT_DATE
                              AND estatus IN ('CREDITO','PARCIAL'))        AS docs_vencidos
        FROM facturas f
        LEFT JOIN (
            SELECT factura_id, SUM(monto) AS pagado FROM pagos GROUP BY factura_id
        ) pg ON pg.factura_id = f.id
    """), {"anio": anio, "mes": mes}).mappings().one()

    clientes_arriba = db.execute(text("""
        SELECT COUNT(*) FROM (
            SELECT cliente_id FROM facturas
            WHERE EXTRACT(YEAR  FROM fecha) = :anio
              AND EXTRACT(MONTH FROM fecha) = :mes
            GROUP BY cliente_id
            HAVING SUM(monto) >= :min
        ) sub
    """), {"anio": anio, "mes": mes, "min": min_monto}).scalar()

    return {
        "anio": anio, "mes": mes, "min_monto": min_monto,
        "kpis": {**dict(row), "clientes_arriba": int(clientes_arriba or 0)},
    }


@router.get("/dashboard/top-clientes")
def ventas_dashboard_top_clientes(
    anio:      int | None = Query(default=None),
    mes:       int | None = Query(default=None, ge=1, le=12),
    min_monto: float      = Query(default=5000),
    limit:     int        = Query(default=10, ge=1, le=50),
    db: Session = Depends(get_db),
):
    hoy = date.today()
    anio = anio or hoy.year
    mes  = mes  or hoy.month

    rows = db.execute(text("""
        SELECT
            c.id                                                          AS cliente_id,
            c.nombre                                                      AS cliente_nombre,
            c.tipo,
            COUNT(f.id)                                                   AS num_docs,
            COALESCE(SUM(f.monto), 0)                                     AS total_mes,
            COALESCE(SUM(
                CASE WHEN f.estatus IN ('CREDITO','PARCIAL')
                     THEN f.monto - COALESCE(pg.pagado, 0) ELSE 0 END
            ), 0)                                                         AS saldo_pendiente_mes,
            MAX(f.fecha)                                                  AS ultima_compra
        FROM facturas f
        JOIN clientes c ON c.id = f.cliente_id
        LEFT JOIN (
            SELECT factura_id, SUM(monto) AS pagado FROM pagos GROUP BY factura_id
        ) pg ON pg.factura_id = f.id
        WHERE EXTRACT(YEAR  FROM f.fecha) = :anio
          AND EXTRACT(MONTH FROM f.fecha) = :mes
        GROUP BY c.id, c.nombre, c.tipo
        HAVING SUM(f.monto) >= :min
        ORDER BY total_mes DESC
        LIMIT :limit
    """), {"anio": anio, "mes": mes, "min": min_monto, "limit": limit}).mappings().all()

    return {"anio": anio, "mes": mes, "min_monto": min_monto, "clientes": [dict(r) for r in rows]}


@router.get("/dashboard/cliente/{cliente_id}")
def ventas_dashboard_cliente_detalle(
    cliente_id: int,
    anio:       int | None = Query(default=None),
    mes:        int | None = Query(default=None, ge=1, le=12),
    db: Session = Depends(get_db),
):
    hoy = date.today()
    anio = anio or hoy.year
    mes  = mes  or hoy.month

    cliente = db.execute(
        text("SELECT id, nombre, tipo FROM clientes WHERE id = :id"),
        {"id": cliente_id},
    ).mappings().first()
    if not cliente:
        raise HTTPException(status_code=404, detail="Cliente no encontrado")

    stats_mes = db.execute(text("""
        SELECT
            COUNT(f.id)               AS num_docs,
            COALESCE(SUM(f.monto), 0) AS total_mes,
            MAX(f.fecha)              AS ultima_compra
        FROM facturas f
        WHERE f.cliente_id = :cid
          AND EXTRACT(YEAR  FROM f.fecha) = :anio
          AND EXTRACT(MONTH FROM f.fecha) = :mes
    """), {"cid": cliente_id, "anio": anio, "mes": mes}).mappings().one()

    saldo_row = db.execute(text("""
        SELECT
            COALESCE(SUM(f.monto), 0)                                     AS total_historico,
            COALESCE(SUM(
                CASE WHEN f.estatus IN ('CREDITO','PARCIAL')
                     THEN f.monto - COALESCE(pg.pagado, 0) ELSE 0 END
            ), 0)                                                         AS saldo_pendiente_total
        FROM facturas f
        LEFT JOIN (
            SELECT factura_id, SUM(monto) AS pagado FROM pagos GROUP BY factura_id
        ) pg ON pg.factura_id = f.id
        WHERE f.cliente_id = :cid
    """), {"cid": cliente_id}).mappings().one()

    docs = db.execute(text("""
        SELECT
            f.id, f.folio, f.fecha, f.monto, f.estatus, f.tipo_documento,
            f.monto - COALESCE(pg.pagado, 0) AS saldo_pendiente
        FROM facturas f
        LEFT JOIN (
            SELECT factura_id, SUM(monto) AS pagado FROM pagos GROUP BY factura_id
        ) pg ON pg.factura_id = f.id
        WHERE f.cliente_id = :cid
          AND EXTRACT(YEAR  FROM f.fecha) = :anio
          AND EXTRACT(MONTH FROM f.fecha) = :mes
        ORDER BY f.fecha DESC, f.id DESC
        LIMIT 5
    """), {"cid": cliente_id, "anio": anio, "mes": mes}).mappings().all()

    return {
        "cliente_id":     cliente_id,
        "cliente_nombre": cliente["nombre"],
        "tipo":           cliente["tipo"],
        "anio":           anio,
        "mes":            mes,
        "stats": {
            **dict(stats_mes),
            "saldo_pendiente_total": saldo_row["saldo_pendiente_total"],
            "total_historico":       saldo_row["total_historico"],
        },
        "documentos_recientes": [dict(r) for r in docs],
    }


# ═══════════════════════════════════════════════════
# DETALLE Y PAGOS  (must be after specific routes)
# ═══════════════════════════════════════════════════

@router.get("/{factura_id}")
def get_factura_detalle(factura_id: int, db: Session = Depends(get_db)):
    doc = db.execute(text("""
        SELECT f.id, f.folio, f.cliente_id, c.nombre AS cliente_nombre, c.rfc AS cliente_rfc,
               c.telefono AS cliente_telefono, c.direccion AS cliente_direccion,
               f.monto, f.fecha, f.estatus, f.tipo_documento, f.condicion_pago,
               f.fecha_vencimiento, f.metodo_pago, f.notas, f.created_at,
               COALESCE(SUM(p.monto), 0) AS total_pagado,
               f.monto - COALESCE(SUM(p.monto), 0) AS saldo_pendiente
        FROM facturas f
        LEFT JOIN clientes c ON c.id = f.cliente_id
        LEFT JOIN pagos p ON p.factura_id = f.id
        WHERE f.id = :id
        GROUP BY f.id, c.nombre, c.rfc, c.telefono, c.direccion
    """), {"id": factura_id}).mappings().first()
    if not doc:
        raise HTTPException(status_code=404, detail="Documento no encontrado")

    pagos = db.execute(text("""
        SELECT id, monto, fecha, metodo_pago, referencia, notas, created_at
        FROM pagos WHERE factura_id = :fid ORDER BY fecha DESC
    """), {"fid": factura_id}).mappings().all()

    return {"documento": dict(doc), "pagos": [dict(p) for p in pagos]}


@router.get("/{factura_id}/pagos")
def list_pagos(factura_id: int, db: Session = Depends(get_db)):
    rows = db.execute(text("""
        SELECT id, factura_id, monto, fecha, metodo_pago, referencia, notas, created_at
        FROM pagos WHERE factura_id = :fid ORDER BY fecha DESC
    """), {"fid": factura_id}).mappings().all()
    return {"items": rows, "count": len(rows)}


@router.post("/{factura_id}/pagos")
def create_pago(factura_id: int, payload: PagoCreate, db: Session = Depends(get_db)):
    factura = db.execute(
        text("SELECT id, monto, estatus FROM facturas WHERE id = :id"),
        {"id": factura_id},
    ).mappings().first()
    if not factura:
        raise HTTPException(status_code=404, detail="Documento no encontrado")
    if payload.monto <= 0:
        raise HTTPException(status_code=400, detail="El monto del pago debe ser mayor a 0")

    pagado = db.execute(
        text("SELECT COALESCE(SUM(monto), 0) FROM pagos WHERE factura_id = :fid"),
        {"fid": factura_id},
    ).scalar()
    saldo = float(factura["monto"]) - float(pagado)
    if payload.monto > saldo + 0.01:
        raise HTTPException(status_code=400, detail=f"El pago excede el saldo pendiente (${saldo:.2f})")

    row = db.execute(text("""
        INSERT INTO pagos (factura_id, monto, fecha, metodo_pago, referencia, notas)
        VALUES (:fid, :monto, :fecha, :mp, :ref, :notas)
        RETURNING id, factura_id, monto, fecha, metodo_pago, referencia, notas, created_at
    """), {
        "fid": factura_id, "monto": payload.monto,
        "fecha": payload.fecha or date.today(),
        "mp": normalize_text(payload.metodo_pago).upper() or None,
        "ref": normalize_text(payload.referencia) or None,
        "notas": normalize_text(payload.notas) or None,
    }).mappings().one()

    nuevo_pagado = float(pagado) + payload.monto
    if nuevo_pagado >= float(factura["monto"]) - 0.01:
        nuevo_estatus = "PAGADA"
    elif nuevo_pagado > 0:
        nuevo_estatus = "PARCIAL"
    else:
        nuevo_estatus = factura["estatus"]

    db.execute(text("UPDATE facturas SET estatus = :est WHERE id = :id"),
               {"est": nuevo_estatus, "id": factura_id})
    db.commit()
    return {"ok": True, "pago": dict(row), "nuevo_estatus": nuevo_estatus}
