from fastapi import APIRouter, Depends, Query, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import text
from APP.db import get_db
from APP.helpers import normalize_text
from pydantic import BaseModel, field_validator
from typing import Optional, List
from datetime import date

router = APIRouter(prefix="/compras", tags=["Compras"])

ESTATUS_VALIDOS           = ("PENDIENTE", "RECIBIDA", "PAGADA", "PARCIAL", "CANCELADA")
TIPO_COMPRA_VALIDOS       = ("CON_FACTURA", "SIN_FACTURA")
ESTATUS_RECEPCION_VALIDOS = {"PENDIENTE", "PARCIAL", "RECIBIDA"}
ESTATUS_WORKFLOW_VALIDOS  = {"REVIEW", "READY", "IMPORTED"}

# metodo_pago intentionally stores both payment instruments (EFECTIVO, TRANSFERENCIA…)
# and payment conditions (CONTADO, CREDITO) from the POS.  These are semantically
# different but kept in one field for simplicity.  Separate if needed in a future pass.
METODOS_PAGO = (
    "EFECTIVO", "TRANSFERENCIA", "CHEQUE", "TARJETA",
    "CONTADO", "CREDITO", "OTRO",
)


# ── Schemas ──────────────────────────────────────────────────────────────────

class DetalleItem(BaseModel):
    product_id:   int
    cantidad:     float
    precio_unit:  Optional[float] = None
    supplier_sku: Optional[str]   = None


def _validate_fecha(v: date) -> date:
    today = date.today()
    if v > today:
        raise ValueError("fecha no puede ser futura")
    if v.year < today.year - 1:
        raise ValueError(f"fecha implausible: {v}")
    return v


class CompraCreate(BaseModel):
    proveedor_id:  int
    folio_factura: Optional[str] = None   # supplier's invoice number
    folio_captura: Optional[str] = None   # POS/internal capture reference
    fecha:         date
    subtotal:      float
    iva:           float = 0.0
    total:         float
    estatus:       str = "PENDIENTE"
    metodo_pago:   Optional[str] = None
    notas:         Optional[str] = None
    tipo_compra:       str = "SIN_FACTURA"
    estatus_recepcion: str = "PENDIENTE"
    estatus_workflow:  str | None = None
    uuid_fiscal:       str | None = None
    detalle:           List[DetalleItem] = []

    @field_validator("fecha")
    @classmethod
    def fecha_valida(cls, v: date) -> date:
        return _validate_fecha(v)


class CompraUpdate(BaseModel):
    folio_factura: Optional[str]   = None
    folio_captura: Optional[str]   = None
    fecha:         Optional[date]  = None

    @field_validator("fecha")
    @classmethod
    def fecha_valida(cls, v: date) -> date:
        return _validate_fecha(v)
    subtotal:      Optional[float] = None
    iva:           Optional[float] = None
    total:         Optional[float] = None
    estatus:       Optional[str]   = None
    metodo_pago:       Optional[str]   = None
    notas:             Optional[str]   = None
    tipo_compra:       Optional[str]   = None
    estatus_recepcion: Optional[str]   = None
    estatus_workflow:  Optional[str]   = None


class CompraFromFaltantes(BaseModel):
    proveedor_id: int
    faltante_ids: list[int]
    notas: Optional[str] = None


# ── Helpers ───────────────────────────────────────────────────────────────────

_SELECT = """
    SELECT
        c.id,
        c.folio_factura,
        c.folio_captura,
        c.fecha,
        c.subtotal, c.iva, c.total,
        c.estatus, c.metodo_pago, c.notas,
        c.origen, c.tipo_compra, c.pos_compra_id,
        c.estatus_recepcion, c.estatus_workflow, c.uuid_fiscal,
        c.created_at,
        p.id           AS proveedor_id,
        p.nombre       AS proveedor_nombre,
        p.codigo_corto AS proveedor_codigo
    FROM compras c
    JOIN proveedores p ON p.id = c.proveedor_id
"""


# ── Endpoints ─────────────────────────────────────────────────────────────────

@router.get("/resumen")
def resumen_compras(db: Session = Depends(get_db)):
    row = db.execute(text("""
        SELECT
            COUNT(*)                                                AS total_compras,
            COALESCE(SUM(total), 0)                                 AS monto_total,
            COALESCE(SUM(total) FILTER (WHERE estatus = 'PAGADA'),    0) AS monto_pagado,
            COALESCE(SUM(total) FILTER (WHERE estatus = 'PENDIENTE'), 0) AS monto_pendiente,
            COALESCE(SUM(total) FILTER (WHERE estatus = 'PARCIAL'),   0) AS monto_parcial,
            COUNT(*) FILTER (WHERE estatus = 'PAGADA')              AS compras_pagadas,
            COUNT(*) FILTER (WHERE estatus = 'PENDIENTE')           AS compras_pendientes,
            COUNT(*) FILTER (WHERE estatus = 'PARCIAL')             AS compras_parciales,
            COUNT(*) FILTER (WHERE origen  = 'POS')                 AS compras_pos,
            COUNT(*) FILTER (WHERE origen  = 'MANUAL')              AS compras_manual,
            COUNT(*) FILTER (WHERE tipo_compra = 'CON_FACTURA')     AS compras_con_factura,
            COUNT(*) FILTER (WHERE tipo_compra = 'SIN_FACTURA')     AS compras_sin_factura
        FROM compras
        WHERE estatus != 'CANCELADA'
    """)).mappings().one()
    return dict(row)


@router.get("/audit/duplicados")
def audit_duplicados(
    fecha_inicio: date | None = Query(default=None),
    fecha_fin:    date | None = Query(default=None),
    db: Session = Depends(get_db),
):
    """
    Returns pairs of MANUAL + POS compras that likely represent the same
    real purchase (same supplier, matching folio_factura, total within $1,
    and date within 3 days).  Does not delete or merge anything — audit only.
    """
    fi = fecha_inicio or date(date.today().year, 1, 1)
    ff = fecha_fin    or date.today()

    rows = db.execute(text("""
        SELECT
            m.id            AS manual_id,
            m.folio_factura AS manual_folio,
            m.folio_captura AS manual_captura,
            m.fecha         AS manual_fecha,
            m.total         AS manual_total,
            m.estatus       AS manual_estatus,
            p.id            AS pos_id,
            p.pos_compra_id,
            p.folio_factura AS pos_folio,
            p.fecha         AS pos_fecha,
            p.total         AS pos_total,
            p.estatus       AS pos_estatus,
            pr.nombre       AS proveedor_nombre
        FROM compras m
        JOIN compras p  ON  p.proveedor_id   = m.proveedor_id
                        AND ABS(p.total - m.total) <= 1
                        AND ABS(p.fecha - m.fecha) <= 3
                        AND (
                              (m.folio_factura IS NOT NULL AND p.folio_factura = m.folio_factura)
                           OR (m.folio_factura IS NULL     AND ABS(p.total - m.total) < 0.01)
                        )
        JOIN proveedores pr ON pr.id = m.proveedor_id
        WHERE m.origen = 'MANUAL'
          AND p.origen = 'POS'
          AND m.fecha BETWEEN :fi AND :ff
        ORDER BY m.fecha DESC, pr.nombre
    """), {"fi": fi, "ff": ff}).mappings().all()

    return {
        "fecha_inicio":    str(fi),
        "fecha_fin":       str(ff),
        "total_pares":     len(rows),
        "duplicados": [dict(r) for r in rows],
    }


@router.get("/dashboard")
def dashboard_compras(
    anio: int | None = Query(default=None),
    mes:  int | None = Query(default=None),
    db: Session = Depends(get_db),
):
    today = date.today()
    if anio is None: anio = today.year
    if mes  is None: mes  = today.month

    row = db.execute(text("""
        SELECT
            COUNT(*)                                                                AS total_compras,
            COALESCE(SUM(total), 0)                                                AS total_monto,
            COALESCE(SUM(CASE WHEN tipo_compra = 'CON_FACTURA' THEN total ELSE 0 END), 0) AS con_factura_monto,
            COUNT(CASE WHEN tipo_compra = 'CON_FACTURA' THEN 1 END)               AS con_factura_count,
            COALESCE(SUM(CASE WHEN tipo_compra = 'SIN_FACTURA' THEN total ELSE 0 END), 0) AS sin_factura_monto,
            COUNT(CASE WHEN tipo_compra = 'SIN_FACTURA' THEN 1 END)               AS sin_factura_count,
            COUNT(CASE WHEN estatus = 'PENDIENTE' THEN 1 END)                     AS compras_pendientes,
            COUNT(CASE WHEN estatus = 'RECIBIDA'  THEN 1 END)                     AS compras_recibidas,
            COUNT(CASE WHEN origen  = 'POS'       THEN 1 END)                     AS compras_pos,
            COUNT(CASE WHEN origen  = 'MANUAL'    THEN 1 END)                     AS compras_manuales,
            ROUND(COALESCE(AVG(total), 0), 2)                                     AS ticket_promedio
        FROM compras
        WHERE EXTRACT(YEAR  FROM fecha) = :anio
          AND EXTRACT(MONTH FROM fecha) = :mes
          AND estatus = 'RECIBIDA'
    """), {"anio": anio, "mes": mes}).mappings().one()

    return {"anio": anio, "mes": mes, "kpis": dict(row)}


@router.get("/dashboard/top-proveedores")
def dashboard_top_proveedores(
    anio:  int | None = Query(default=None),
    mes:   int | None = Query(default=None),
    limit: int        = Query(default=10, ge=1, le=50),
    db: Session = Depends(get_db),
):
    today = date.today()
    if anio is None: anio = today.year
    if mes  is None: mes  = today.month

    rows = db.execute(text("""
        SELECT
            p.id                                                                       AS proveedor_id,
            p.nombre                                                                   AS proveedor_nombre,
            COUNT(c.id)                                                                AS num_compras,
            COALESCE(SUM(c.total), 0)                                                  AS total_monto,
            COALESCE(SUM(CASE WHEN c.tipo_compra = 'CON_FACTURA' THEN c.total ELSE 0 END), 0) AS con_factura,
            COALESCE(SUM(CASE WHEN c.tipo_compra = 'SIN_FACTURA' THEN c.total ELSE 0 END), 0) AS sin_factura,
            ROUND(COALESCE(AVG(c.total), 0), 2)                                       AS ticket_promedio,
            MAX(c.fecha)                                                               AS ultima_compra
        FROM compras c
        JOIN proveedores p ON p.id = c.proveedor_id
        WHERE EXTRACT(YEAR  FROM c.fecha) = :anio
          AND EXTRACT(MONTH FROM c.fecha) = :mes
          AND c.estatus = 'RECIBIDA'
        GROUP BY p.id, p.nombre
        ORDER BY total_monto DESC
        LIMIT :limit
    """), {"anio": anio, "mes": mes, "limit": limit}).mappings().all()

    return {"anio": anio, "mes": mes, "proveedores": [dict(r) for r in rows]}


@router.get("/dashboard/proveedor/{proveedor_id}")
def dashboard_proveedor_detalle(
    proveedor_id: int,
    anio: int | None = Query(default=None),
    mes:  int | None = Query(default=None),
    db: Session = Depends(get_db),
):
    today = date.today()
    if anio is None: anio = today.year
    if mes  is None: mes  = today.month

    prov = db.execute(
        text("SELECT id, nombre FROM proveedores WHERE id = :id"),
        {"id": proveedor_id},
    ).mappings().first()
    if not prov:
        raise HTTPException(status_code=404, detail="Proveedor no encontrado")

    stats = db.execute(text("""
        SELECT
            COUNT(c.id)                                                                AS num_compras,
            COALESCE(SUM(c.total), 0)                                                  AS total_monto,
            COALESCE(SUM(CASE WHEN c.tipo_compra = 'CON_FACTURA' THEN c.total ELSE 0 END), 0) AS con_factura,
            COALESCE(SUM(CASE WHEN c.tipo_compra = 'SIN_FACTURA' THEN c.total ELSE 0 END), 0) AS sin_factura,
            ROUND(COALESCE(AVG(c.total), 0), 2)                                       AS ticket_promedio,
            MAX(c.fecha)                                                               AS ultima_compra
        FROM compras c
        WHERE c.proveedor_id = :pid
          AND EXTRACT(YEAR  FROM c.fecha) = :anio
          AND EXTRACT(MONTH FROM c.fecha) = :mes
    """), {"pid": proveedor_id, "anio": anio, "mes": mes}).mappings().one()

    productos = db.execute(text("""
        SELECT
            cd.product_id,
            pr.sku,
            pr.name                              AS product_name,
            SUM(cd.cantidad)                     AS cantidad_total,
            COALESCE(SUM(cd.cantidad * cd.precio_unit), 0) AS monto_total
        FROM compras_detalle cd
        JOIN compras  c  ON c.id  = cd.compra_id
        JOIN productos pr ON pr.id = cd.product_id
        WHERE c.proveedor_id = :pid
          AND EXTRACT(YEAR  FROM c.fecha) = :anio
          AND EXTRACT(MONTH FROM c.fecha) = :mes
        GROUP BY cd.product_id, pr.sku, pr.name
        ORDER BY monto_total DESC
        LIMIT 10
    """), {"pid": proveedor_id, "anio": anio, "mes": mes}).mappings().all()

    recientes = db.execute(text("""
        SELECT
            c.id             AS compra_id,
            c.fecha,
            c.folio_factura,
            c.tipo_compra,
            c.total,
            c.estatus
        FROM compras c
        WHERE c.proveedor_id = :pid
          AND EXTRACT(YEAR  FROM c.fecha) = :anio
          AND EXTRACT(MONTH FROM c.fecha) = :mes
        ORDER BY c.fecha DESC, c.id DESC
        LIMIT 5
    """), {"pid": proveedor_id, "anio": anio, "mes": mes}).mappings().all()

    return {
        "proveedor_id":      proveedor_id,
        "proveedor_nombre":  prov["nombre"],
        "anio":              anio,
        "mes":               mes,
        "stats":             dict(stats),
        "top_productos":     [dict(r) for r in productos],
        "compras_recientes": [dict(r) for r in recientes],
    }


@router.get("")
def list_compras(
    fecha_inicio: date | None = Query(default=None),
    fecha_fin:    date | None = Query(default=None),
    proveedor_id: int | None  = Query(default=None),
    estatus:      str | None  = Query(default=None),
    origen:       str | None  = Query(default=None),
    tipo_compra:  str | None  = Query(default=None),
    q:            str | None  = Query(default=None),
    page:         int         = Query(default=1, ge=1),
    page_size:    int         = Query(default=50, ge=1, le=200),
    db: Session = Depends(get_db),
):
    where  = []
    params: dict = {}

    if fecha_inicio:
        where.append("c.fecha >= :fi");       params["fi"]  = fecha_inicio
    if fecha_fin:
        where.append("c.fecha <= :ff");       params["ff"]  = fecha_fin
    if proveedor_id:
        where.append("c.proveedor_id = :pid"); params["pid"] = proveedor_id
    if estatus:
        where.append("c.estatus = :est");     params["est"] = estatus.upper()
    if origen:
        where.append("c.origen = :origen");   params["origen"] = origen.upper()
    if tipo_compra:
        where.append("c.tipo_compra = :tipo_compra"); params["tipo_compra"] = tipo_compra.upper()
    if q:
        where.append(
            "(c.folio_factura ILIKE :q OR c.folio_captura ILIKE :q OR p.nombre ILIKE :q)"
        )
        params["q"] = f"%{normalize_text(q)}%"

    where_sql = ("WHERE " + " AND ".join(where)) if where else ""
    offset = (page - 1) * page_size
    params["limit"]  = page_size
    params["offset"] = offset

    total = db.execute(text(f"""
        SELECT COUNT(*)
        FROM compras c
        JOIN proveedores p ON p.id = c.proveedor_id
        {where_sql}
    """), params).scalar()

    rows = db.execute(text(f"""
        {_SELECT}
        {where_sql}
        ORDER BY c.fecha DESC, c.id DESC
        LIMIT :limit OFFSET :offset
    """), params).mappings().all()

    return {
        "page":      page,
        "page_size": page_size,
        "total":     int(total or 0),
        "items":     [dict(r) for r in rows],
    }


@router.get("/{compra_id}/detalle")
def get_compra_detalle(compra_id: int, db: Session = Depends(get_db)):
    if not db.execute(text("SELECT 1 FROM compras WHERE id = :id"), {"id": compra_id}).scalar():
        raise HTTPException(status_code=404, detail="Compra no encontrada")
    rows = db.execute(text("""
        SELECT
            cd.id,
            cd.compra_id,
            cd.product_id,
            p.sku,
            p.name        AS product_name,
            p.marca,
            p.unit,
            cd.cantidad,
            cd.precio_unit,
            cd.supplier_sku,
            cd.created_at
        FROM compras_detalle cd
        JOIN productos p ON p.id = cd.product_id
        WHERE cd.compra_id = :cid
        ORDER BY cd.id
    """), {"cid": compra_id}).mappings().all()
    return {"items": [dict(r) for r in rows], "count": len(rows)}


@router.put("/{compra_id}/detalle")
def replace_compra_detalle(compra_id: int, items: List[DetalleItem], db: Session = Depends(get_db)):
    """Replace all line items for a compra (full overwrite, not patch)."""
    if not db.execute(text("SELECT 1 FROM compras WHERE id = :id"), {"id": compra_id}).scalar():
        raise HTTPException(status_code=404, detail="Compra no encontrada")

    for item in items:
        if item.cantidad <= 0:
            raise HTTPException(status_code=400, detail=f"cantidad debe ser > 0 (product_id={item.product_id})")
        if not db.execute(text("SELECT 1 FROM productos WHERE id = :id"), {"id": item.product_id}).scalar():
            raise HTTPException(status_code=404, detail=f"Producto no encontrado: {item.product_id}")

    try:
        db.execute(text("DELETE FROM compras_detalle WHERE compra_id = :cid"), {"cid": compra_id})
        for item in items:
            db.execute(text("""
                INSERT INTO compras_detalle (compra_id, product_id, cantidad, precio_unit, supplier_sku)
                VALUES (:cid, :pid, :qty, :precio, :sku)
            """), {
                "cid":    compra_id,
                "pid":    item.product_id,
                "qty":    item.cantidad,
                "precio": item.precio_unit,
                "sku":    item.supplier_sku,
            })
            if item.precio_unit and item.precio_unit > 0:
                db.execute(text("""
                    UPDATE productos SET
                        costo_real_sin_iva    = :costo,
                        costo_real_updated_at = NOW(),
                        precio_sugerido = CASE
                            WHEN porcentaje_margen_objetivo IS NOT NULL
                            THEN ROUND(:costo * (1 + porcentaje_margen_objetivo / 100), 2)
                            ELSE precio_sugerido
                        END
                    WHERE id = :pid
                """), {"costo": item.precio_unit, "pid": item.product_id})
        db.execute(text("UPDATE compras SET updated_at = NOW() WHERE id = :id"), {"id": compra_id})
        db.commit()
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))

    return {"ok": True, "count": len(items)}


@router.get("/{compra_id}")
def get_compra(compra_id: int, db: Session = Depends(get_db)):
    row = db.execute(
        text(f"{_SELECT} WHERE c.id = :id"),
        {"id": compra_id},
    ).mappings().first()
    if not row:
        raise HTTPException(status_code=404, detail="Compra no encontrada")
    return dict(row)


@router.post("")
def create_compra(payload: CompraCreate, db: Session = Depends(get_db)):
    estatus = payload.estatus.upper()
    if estatus not in ESTATUS_VALIDOS:
        raise HTTPException(status_code=400, detail=f"Estatus inválido. Válidos: {ESTATUS_VALIDOS}")

    estatus_recepcion = payload.estatus_recepcion.upper()
    if estatus_recepcion not in ESTATUS_RECEPCION_VALIDOS:
        raise HTTPException(status_code=400, detail=f"estatus_recepcion inválido: {estatus_recepcion}. Válidos: {ESTATUS_RECEPCION_VALIDOS}")

    if payload.estatus_workflow is not None:
        estatus_workflow = payload.estatus_workflow.upper()
        if estatus_workflow not in ESTATUS_WORKFLOW_VALIDOS:
            raise HTTPException(status_code=400, detail=f"estatus_workflow inválido: {estatus_workflow}. Válidos: {ESTATUS_WORKFLOW_VALIDOS}")
    else:
        estatus_workflow = None

    tipo = payload.tipo_compra.upper()
    if tipo not in TIPO_COMPRA_VALIDOS:
        raise HTTPException(status_code=400, detail=f"tipo_compra inválido. Válidos: {TIPO_COMPRA_VALIDOS}")

    metodo = payload.metodo_pago.upper() if payload.metodo_pago else None

    if not db.execute(text("SELECT 1 FROM proveedores WHERE id = :id"), {"id": payload.proveedor_id}).scalar():
        raise HTTPException(status_code=404, detail="Proveedor no encontrado")

    if payload.folio_factura:
        dup = db.execute(text("""
            SELECT id FROM compras
            WHERE proveedor_id = :pid AND folio_factura = :folio AND fecha = :fecha
        """), {
            "pid":   payload.proveedor_id,
            "folio": normalize_text(payload.folio_factura).upper(),
            "fecha": payload.fecha,
        }).scalar()
        if dup:
            raise HTTPException(status_code=409,
                detail=f"Compra duplicada: folio {payload.folio_factura} ya registrado para este proveedor y fecha")

    # Validate detalle product_ids exist before inserting anything
    for item in payload.detalle:
        if item.cantidad <= 0:
            raise HTTPException(status_code=400, detail=f"cantidad debe ser > 0 (product_id={item.product_id})")
        if not db.execute(text("SELECT 1 FROM productos WHERE id = :id"), {"id": item.product_id}).scalar():
            raise HTTPException(status_code=404, detail=f"Producto no encontrado: {item.product_id}")

    try:
        new_id = db.execute(text("""
            INSERT INTO compras
                (proveedor_id, folio_factura, folio_captura,
                 fecha, subtotal, iva, total,
                 estatus, metodo_pago, notas,
                 origen, tipo_compra,
                 estatus_recepcion, estatus_workflow, uuid_fiscal)
            VALUES
                (:proveedor_id, :folio_factura, :folio_captura,
                 :fecha, :subtotal, :iva, :total,
                 :estatus, :metodo_pago, :notas,
                 'MANUAL', :tipo_compra,
                 :estatus_recepcion, :estatus_workflow, :uuid_fiscal)
            RETURNING id
        """), {
            "proveedor_id":      payload.proveedor_id,
            "folio_factura":     normalize_text(payload.folio_factura).upper() if payload.folio_factura else None,
            "folio_captura":     normalize_text(payload.folio_captura).upper() if payload.folio_captura else None,
            "fecha":             payload.fecha,
            "subtotal":          payload.subtotal,
            "iva":               payload.iva,
            "total":             payload.total,
            "estatus":           estatus,
            "metodo_pago":       metodo,
            "notas":             payload.notas,
            "tipo_compra":       tipo,
            "estatus_recepcion": estatus_recepcion,
            "estatus_workflow":  estatus_workflow,
            "uuid_fiscal":       payload.uuid_fiscal,
        }).scalar()

        for item in payload.detalle:
            db.execute(text("""
                INSERT INTO compras_detalle (compra_id, product_id, cantidad, precio_unit, supplier_sku)
                VALUES (:cid, :pid, :qty, :precio, :sku)
            """), {
                "cid":    new_id,
                "pid":    item.product_id,
                "qty":    item.cantidad,
                "precio": item.precio_unit,
                "sku":    item.supplier_sku,
            })
            # precio_unit in compras_detalle is sin IVA — use directly as costo_real
            if item.precio_unit and item.precio_unit > 0:
                db.execute(text("""
                    UPDATE productos SET
                        costo_real_sin_iva    = :costo,
                        costo_real_updated_at = NOW(),
                        precio_sugerido = CASE
                            WHEN porcentaje_margen_objetivo IS NOT NULL
                            THEN ROUND(:costo * (1 + porcentaje_margen_objetivo / 100), 2)
                            ELSE precio_sugerido
                        END
                    WHERE id = :pid
                """), {"costo": item.precio_unit, "pid": item.product_id})

        db.commit()
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))

    return {"ok": True, "id": new_id}


@router.post("/desde-faltantes")
def crear_compra_desde_faltantes(payload: CompraFromFaltantes, db: Session = Depends(get_db)):
    """Create a compra header + detail lines from selected faltante IDs."""
    # 1. Validate proveedor
    prov = db.execute(
        text("SELECT id, nombre FROM proveedores WHERE id = :id"),
        {"id": payload.proveedor_id},
    ).mappings().first()
    if not prov:
        raise HTTPException(status_code=404, detail="Proveedor no encontrado")

    # 2. Validate list not empty
    if not payload.faltante_ids:
        raise HTTPException(status_code=400, detail="Debe seleccionar al menos un faltante")

    # 3. Validate each faltante
    valid_items: list[dict] = []
    errores: list[dict] = []

    for fid in payload.faltante_ids:
        faltante = db.execute(
            text("SELECT id, product_id, cantidad_faltante, status FROM faltantes WHERE id = :id"),
            {"id": fid},
        ).mappings().first()

        if not faltante:
            errores.append({"faltante_id": fid, "error": "Faltante no encontrado"})
            continue

        if faltante["status"] != "pendiente":
            errores.append({"faltante_id": fid, "error": f"Faltante no está pendiente (status={faltante['status']})"})
            continue

        pp = db.execute(
            text("""
                SELECT proveedor_id, precio_proveedor, supplier_sku
                FROM producto_proveedor
                WHERE product_id = :pid AND is_primary = true
                LIMIT 1
            """),
            {"pid": faltante["product_id"]},
        ).mappings().first()

        if not pp or pp["proveedor_id"] != payload.proveedor_id:
            errores.append({"faltante_id": fid, "error": "Faltante no pertenece al proveedor indicado"})
            continue

        valid_items.append({
            "faltante_id": fid,
            "product_id":  faltante["product_id"],
            "cantidad":    faltante["cantidad_faltante"],
            "precio_unit": float(pp["precio_proveedor"]) if pp["precio_proveedor"] else None,
            "supplier_sku": pp["supplier_sku"],
        })

    if not valid_items:
        raise HTTPException(status_code=400, detail={
            "message": "Todos los faltantes fallaron la validación",
            "errores": errores,
        })

    # 4. Create compra header + detail in one transaction
    try:
        compra = db.execute(text("""
            INSERT INTO compras
                (proveedor_id, estatus, origen, tipo_compra, notas, fecha, subtotal, iva, total,
                 estatus_recepcion, estatus_workflow, created_at, updated_at)
            VALUES
                (:proveedor_id, 'PENDIENTE', 'MANUAL', 'SIN_FACTURA', :notas, CURRENT_DATE, 0, 0, 0,
                 'PENDIENTE', NULL, NOW(), NOW())
            RETURNING id, fecha, estatus
        """), {
            "proveedor_id": payload.proveedor_id,
            "notas":        payload.notas,
        }).mappings().one()

        compra_id = compra["id"]

        for item in valid_items:
            db.execute(text("""
                INSERT INTO compras_detalle
                    (compra_id, product_id, cantidad, precio_unit, supplier_sku, faltante_id, created_at)
                VALUES
                    (:compra_id, :product_id, :cantidad, :precio_unit, :supplier_sku, :faltante_id, NOW())
            """), {
                "compra_id":   compra_id,
                "product_id":  item["product_id"],
                "cantidad":    item["cantidad"],
                "precio_unit": item["precio_unit"],
                "supplier_sku": item["supplier_sku"],
                "faltante_id": item["faltante_id"],
            })

        db.commit()
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))

    return {
        "ok":                True,
        "compra_id":         compra_id,
        "fecha":             str(compra["fecha"]),
        "estatus":           compra["estatus"],
        "proveedor_nombre":  prov["nombre"],
        "lineas_creadas":    len(valid_items),
        "errores_validacion": errores,
    }


@router.patch("/{compra_id}")
def update_compra(compra_id: int, payload: CompraUpdate, db: Session = Depends(get_db)):
    existing = db.execute(
        text("SELECT id FROM compras WHERE id = :id"), {"id": compra_id}
    ).scalar()
    if not existing:
        raise HTTPException(status_code=404, detail="Compra no encontrada")

    updates: list[str] = []
    params: dict = {"id": compra_id}

    if payload.folio_factura is not None:
        updates.append("folio_factura = :folio_factura")
        params["folio_factura"] = normalize_text(payload.folio_factura).upper() or None
    if payload.folio_captura is not None:
        updates.append("folio_captura = :folio_captura")
        params["folio_captura"] = normalize_text(payload.folio_captura).upper() or None
    if payload.fecha is not None:
        updates.append("fecha = :fecha");        params["fecha"]    = payload.fecha
    if payload.subtotal is not None:
        updates.append("subtotal = :subtotal");  params["subtotal"] = payload.subtotal
    if payload.iva is not None:
        updates.append("iva = :iva");            params["iva"]      = payload.iva
    if payload.total is not None:
        updates.append("total = :total");        params["total"]    = payload.total
    if payload.estatus is not None:
        est = payload.estatus.upper()
        if est not in ESTATUS_VALIDOS:
            raise HTTPException(status_code=400, detail=f"Estatus inválido. Válidos: {ESTATUS_VALIDOS}")
        updates.append("estatus = :estatus");    params["estatus"]    = est
    if payload.metodo_pago is not None:
        updates.append("metodo_pago = :metodo_pago")
        params["metodo_pago"] = payload.metodo_pago.upper()
    if payload.notas is not None:
        updates.append("notas = :notas");        params["notas"] = payload.notas
    if payload.tipo_compra is not None:
        tipo = payload.tipo_compra.upper()
        if tipo not in TIPO_COMPRA_VALIDOS:
            raise HTTPException(status_code=400, detail=f"tipo_compra inválido. Válidos: {TIPO_COMPRA_VALIDOS}")
        updates.append("tipo_compra = :tipo_compra"); params["tipo_compra"] = tipo
    if payload.estatus_recepcion is not None:
        er = payload.estatus_recepcion.upper()
        if er not in ESTATUS_RECEPCION_VALIDOS:
            raise HTTPException(status_code=400, detail=f"estatus_recepcion inválido: {er}. Válidos: {ESTATUS_RECEPCION_VALIDOS}")
        updates.append("estatus_recepcion = :estatus_recepcion"); params["estatus_recepcion"] = er
    if payload.estatus_workflow is not None:
        ew = payload.estatus_workflow.upper()
        if ew not in ESTATUS_WORKFLOW_VALIDOS:
            raise HTTPException(status_code=400, detail=f"estatus_workflow inválido: {ew}. Válidos: {ESTATUS_WORKFLOW_VALIDOS}")
        updates.append("estatus_workflow = :estatus_workflow"); params["estatus_workflow"] = ew

    if not updates:
        raise HTTPException(status_code=400, detail="No se enviaron campos para actualizar")

    updates.append("updated_at = NOW()")
    db.execute(text(f"UPDATE compras SET {', '.join(updates)} WHERE id = :id"), params)
    db.commit()
    return {"ok": True}


@router.delete("/{compra_id}")
def delete_compra(compra_id: int, db: Session = Depends(get_db)):
    if not db.execute(text("SELECT 1 FROM compras WHERE id = :id"), {"id": compra_id}).scalar():
        raise HTTPException(status_code=404, detail="Compra no encontrada")
    db.execute(text("DELETE FROM compras WHERE id = :id"), {"id": compra_id})
    db.commit()
    return {"ok": True}
