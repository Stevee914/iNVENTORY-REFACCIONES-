"""
Cobranza manual — fuente financiera separada del POS.

REGLAS DURAS (feature "Cobranza manual", Fase 3):
- Este módulo SOLO lee/escribe `cobranza_manual` y `cobranza_manual_pagos`,
  y LEE `clientes` (para nombre / validación). NUNCA toca facturas, pagos,
  inventario, movimientos_inventario, FISICO ni FISCAL_POS.
- NUNCA se suma ni combina con datos financieros del POS.
- NO hay endpoints DELETE. Los pagos son INMUTABLES (sin update ni delete).
- La cancelación es EXCLUSIVAMENTE lógica (endpoint /cancelar).
- total_pagado, saldo_pendiente y estatus SIEMPRE se calculan en el backend.
- folio_factura_referencia y posteriormente_facturada son INFORMATIVOS:
  no enlazan a facturas, no crean pagos, no cambian saldo.
"""
from fastapi import APIRouter, Depends, Query, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import text
from pydantic import BaseModel, Field
from datetime import date
from decimal import Decimal
from typing import Optional

from APP.db import get_db
from APP.helpers import normalize_text

router = APIRouter(prefix="/cobranza-manual", tags=["Ventas y Cobranza"])

METODOS_PAGO = ("EFECTIVO", "TRANSFERENCIA", "CHEQUE", "TARJETA", "OTRO")
ESTATUS_ACTIVOS_PENDIENTES = ("PENDIENTE", "PARCIAL")
TOL = 0.01  # tolerancia de centavos para comparaciones de saldo


# ═══════════════════════════════════════════════════
# SCHEMAS PYDANTIC  (definidos aquí a propósito; NO tocar APP/schemas*.py)
# ═══════════════════════════════════════════════════

class CobranzaCreate(BaseModel):
    cliente_id: int
    fecha_relacion: Optional[date] = None
    numero_notas: int
    importe_total: float
    observaciones: Optional[str] = None
    posteriormente_facturada: Optional[bool] = False
    folio_factura_referencia: Optional[str] = None


class CobranzaUpdate(BaseModel):
    # NOTA (migración 008): importe_total y numero_notas son TOTALES ACUMULADOS
    # DERIVADOS de los cargos. YA NO se editan por PATCH; solo cambian dentro de
    # la transacción que inserta un cargo (POST /{id}/cargos).
    observaciones: Optional[str] = None
    fecha_relacion: Optional[date] = None
    posteriormente_facturada: Optional[bool] = None
    folio_factura_referencia: Optional[str] = None


class CargoManualCreate(BaseModel):
    numero_notas: int
    importe: float
    fecha_cargo: Optional[date] = None
    observaciones: Optional[str] = None


class PagoManualCreate(BaseModel):
    monto: float
    metodo_pago: str
    fecha_pago: Optional[date] = None
    referencia: Optional[str] = None
    observaciones: Optional[str] = None


class CancelacionBody(BaseModel):
    motivo: Optional[str] = None


# ═══════════════════════════════════════════════════
# HELPERS DE CÁLCULO  (estatus/saldo SIEMPRE derivados en backend)
# ═══════════════════════════════════════════════════

def _calc_estatus(importe_total, total_pagado, cancelada_at) -> str:
    """Deriva el estatus canónico según las reglas de la feature."""
    if cancelada_at is not None:
        return "CANCELADA"
    it = float(importe_total or 0)
    tp = float(total_pagado or 0)
    saldo = it - tp
    if tp <= TOL:
        return "PENDIENTE"
    if saldo <= TOL:
        return "PAGADA"
    return "PARCIAL"


def _f(value):
    """Normaliza Decimal/None a float para respuestas JSON limpias."""
    if value is None:
        return 0.0
    if isinstance(value, Decimal):
        return float(value)
    return float(value)


# ═══════════════════════════════════════════════════
# 1. LISTADO PAGINADO + FILTROS
# ═══════════════════════════════════════════════════

@router.get("")
def list_cobranza(
    cliente_id: int | None = Query(default=None),
    q: str | None = Query(default=None),
    estatus: str | None = Query(default=None),
    fecha_inicio: date | None = Query(default=None),
    fecha_fin: date | None = Query(default=None),
    solo_pendientes: bool = Query(default=False),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=50, ge=1, le=200),
    db: Session = Depends(get_db),
):
    where = []
    params: dict = {}

    if cliente_id:
        where.append("cm.cliente_id = :cid")
        params["cid"] = cliente_id
    if estatus:
        where.append("cm.estatus = :est")
        params["est"] = estatus.upper()
    if fecha_inicio:
        where.append("cm.fecha_relacion >= :fi")
        params["fi"] = fecha_inicio
    if fecha_fin:
        where.append("cm.fecha_relacion <= :ff")
        params["ff"] = fecha_fin
    if q:
        where.append("(c.nombre ILIKE :q OR cm.observaciones ILIKE :q OR cm.folio_factura_referencia ILIKE :q)")
        params["q"] = f"%{normalize_text(q)}%"
    if solo_pendientes:
        where.append("cm.estatus IN ('PENDIENTE', 'PARCIAL')")

    where_sql = ("WHERE " + " AND ".join(where)) if where else ""

    total = db.execute(text(f"""
        SELECT COUNT(*)
        FROM cobranza_manual cm
        LEFT JOIN clientes c ON c.id = cm.cliente_id
        {where_sql}
    """), params).scalar()

    offset = (page - 1) * page_size
    params["limit"] = page_size
    params["offset"] = offset

    rows = db.execute(text(f"""
        SELECT cm.id, cm.cliente_id, c.nombre AS cliente_nombre,
               cm.fecha_relacion, cm.numero_notas, cm.importe_total,
               cm.estatus, cm.posteriormente_facturada, cm.folio_factura_referencia,
               cm.observaciones, cm.cancelada_at, cm.created_at, cm.updated_at,
               COALESCE(pg.total_pagado, 0) AS total_pagado,
               cm.importe_total - COALESCE(pg.total_pagado, 0) AS saldo_pendiente
        FROM cobranza_manual cm
        LEFT JOIN clientes c ON c.id = cm.cliente_id
        LEFT JOIN (
            SELECT cobranza_manual_id, SUM(monto) AS total_pagado
            FROM cobranza_manual_pagos GROUP BY cobranza_manual_id
        ) pg ON pg.cobranza_manual_id = cm.id
        {where_sql}
        ORDER BY cm.fecha_relacion DESC, cm.id DESC
        LIMIT :limit OFFSET :offset
    """), params).mappings().all()

    items = [_row_to_item(r) for r in rows]
    return {"items": items, "total": int(total or 0), "page": page, "page_size": page_size}


def _row_to_item(r) -> dict:
    """Normaliza una fila del listado al contrato de item (numéricos como float)."""
    return {
        "id": r["id"],
        "cliente_id": r["cliente_id"],
        "cliente_nombre": r["cliente_nombre"],
        "fecha_relacion": r["fecha_relacion"],
        "numero_notas": r["numero_notas"],
        "importe_total": _f(r["importe_total"]),
        "total_pagado": _f(r["total_pagado"]),
        "saldo_pendiente": _f(r["saldo_pendiente"]),
        "estatus": r["estatus"],
        "posteriormente_facturada": r["posteriormente_facturada"],
        "folio_factura_referencia": r["folio_factura_referencia"],
        "observaciones": r["observaciones"],
        "cancelada_at": r["cancelada_at"],
        "created_at": r["created_at"],
        "updated_at": r["updated_at"],
    }


# ═══════════════════════════════════════════════════
# 2. RESUMEN / KPIs  (SOLO tablas manuales — antes de /{id})
# ═══════════════════════════════════════════════════

@router.get("/resumen")
def resumen_cobranza_manual(
    fecha_inicio: date | None = Query(default=None, description="Filtra cobrado_periodo por fecha_pago >="),
    fecha_fin: date | None = Query(default=None, description="Filtra cobrado_periodo por fecha_pago <="),
    db: Session = Depends(get_db),
):
    # saldo_manual_pendiente: importe_total - pagos, SOLO relaciones no canceladas.
    saldo_row = db.execute(text("""
        SELECT COALESCE(SUM(cm.importe_total - COALESCE(pg.total_pagado, 0)), 0) AS saldo_manual_pendiente,
               COUNT(*) FILTER (WHERE cm.estatus IN ('PENDIENTE', 'PARCIAL')) AS relaciones_pendientes,
               COUNT(DISTINCT cm.cliente_id) FILTER (WHERE cm.estatus IN ('PENDIENTE', 'PARCIAL'))
                   AS clientes_con_cobranza_pendiente
        FROM cobranza_manual cm
        LEFT JOIN (
            SELECT cobranza_manual_id, SUM(monto) AS total_pagado
            FROM cobranza_manual_pagos GROUP BY cobranza_manual_id
        ) pg ON pg.cobranza_manual_id = cm.id
        WHERE cm.estatus <> 'CANCELADA'
    """)).mappings().first()

    # cobrado_periodo: suma de pagos manuales en el rango (sobre fecha_pago).
    pago_where = []
    pago_params: dict = {}
    if fecha_inicio:
        pago_where.append("fecha_pago >= :fi")
        pago_params["fi"] = fecha_inicio
    if fecha_fin:
        pago_where.append("fecha_pago <= :ff")
        pago_params["ff"] = fecha_fin
    pago_where_sql = ("WHERE " + " AND ".join(pago_where)) if pago_where else ""

    cobrado = db.execute(text(f"""
        SELECT COALESCE(SUM(monto), 0) AS cobrado_periodo
        FROM cobranza_manual_pagos
        {pago_where_sql}
    """), pago_params).scalar()

    return {
        "saldo_manual_pendiente": _f(saldo_row["saldo_manual_pendiente"]),
        "cobrado_periodo": _f(cobrado),
        "relaciones_pendientes": int(saldo_row["relaciones_pendientes"] or 0),
        "clientes_con_cobranza_pendiente": int(saldo_row["clientes_con_cobranza_pendiente"] or 0),
        "fecha_inicio": str(fecha_inicio) if fecha_inicio else None,
        "fecha_fin": str(fecha_fin) if fecha_fin else None,
    }


# ═══════════════════════════════════════════════════
# 3. POR CLIENTE  (antes de /{id})
# ═══════════════════════════════════════════════════

@router.get("/por-cliente/{cliente_id}")
def cobranza_por_cliente(cliente_id: int, db: Session = Depends(get_db)):
    rows = db.execute(text("""
        SELECT cm.id, cm.cliente_id, c.nombre AS cliente_nombre,
               cm.fecha_relacion, cm.numero_notas, cm.importe_total,
               cm.estatus, cm.posteriormente_facturada, cm.folio_factura_referencia,
               cm.observaciones, cm.cancelada_at, cm.created_at, cm.updated_at,
               COALESCE(pg.total_pagado, 0) AS total_pagado,
               cm.importe_total - COALESCE(pg.total_pagado, 0) AS saldo_pendiente
        FROM cobranza_manual cm
        LEFT JOIN clientes c ON c.id = cm.cliente_id
        LEFT JOIN (
            SELECT cobranza_manual_id, SUM(monto) AS total_pagado
            FROM cobranza_manual_pagos GROUP BY cobranza_manual_id
        ) pg ON pg.cobranza_manual_id = cm.id
        WHERE cm.cliente_id = :cid
        ORDER BY cm.fecha_relacion DESC, cm.id DESC
    """), {"cid": cliente_id}).mappings().all()

    items = [_row_to_item(r) for r in rows]
    return {"items": items, "count": len(items)}


# ═══════════════════════════════════════════════════
# 3b. ESTADO DE CUENTA CONSOLIDADO POR CLIENTE  (antes de /{id})
# ═══════════════════════════════════════════════════

@router.get("/estado-cuenta/{cliente_id}")
def estado_cuenta_cliente(cliente_id: int, db: Session = Depends(get_db)):
    """Estado de cuenta CONSOLIDADO de un cliente: todos sus movimientos manuales
    (cargos + abonos) de TODAS sus relaciones, con saldo corriente acumulado.

    SOLO tablas manuales + clientes. NUNCA facturas/pagos POS/inventario.
    Decisión documentada: las relaciones CANCELADA se EXCLUYEN por completo
    (no aportan al saldo ni aparecen en los movimientos)."""
    cliente = db.execute(
        text("SELECT id, nombre FROM clientes WHERE id = :id"),
        {"id": cliente_id},
    ).mappings().first()
    if not cliente:
        raise HTTPException(status_code=404, detail=f"Cliente no encontrado: {cliente_id}")

    # Cargos (signo +) y abonos (signo -) de todas las relaciones NO canceladas.
    # Se unifican en un solo flujo cronológico. El orden usa la fecha del
    # movimiento y desempata por created_at, tipo (CARGO antes que ABONO en el
    # mismo instante) e id, de forma estable.
    movimientos = db.execute(text("""
        SELECT * FROM (
            SELECT
                'CARGO' AS tipo,
                cmc.cobranza_manual_id AS relacion_id,
                cmc.fecha_cargo        AS fecha,
                cmc.numero_notas       AS numero_notas,
                cmc.importe            AS importe,
                NULL::varchar          AS metodo_pago,
                NULL::varchar          AS referencia,
                cmc.observaciones      AS observaciones,
                cmc.created_at         AS created_at,
                cmc.id                 AS mov_id
            FROM cobranza_manual_cargos cmc
            JOIN cobranza_manual cm ON cm.id = cmc.cobranza_manual_id
            WHERE cm.cliente_id = :cid AND cm.estatus <> 'CANCELADA'

            UNION ALL

            SELECT
                'ABONO' AS tipo,
                cmp.cobranza_manual_id AS relacion_id,
                cmp.fecha_pago         AS fecha,
                NULL::integer          AS numero_notas,
                cmp.monto              AS importe,
                cmp.metodo_pago        AS metodo_pago,
                cmp.referencia         AS referencia,
                cmp.observaciones      AS observaciones,
                cmp.created_at         AS created_at,
                cmp.id                 AS mov_id
            FROM cobranza_manual_pagos cmp
            JOIN cobranza_manual cm ON cm.id = cmp.cobranza_manual_id
            WHERE cm.cliente_id = :cid AND cm.estatus <> 'CANCELADA'
        ) mov
        ORDER BY fecha ASC, created_at ASC,
                 CASE WHEN tipo = 'CARGO' THEN 0 ELSE 1 END, mov_id ASC
    """), {"cid": cliente_id}).mappings().all()

    total_cargado = 0.0
    total_abonado = 0.0
    saldo_corriente = 0.0
    items = []
    for m in movimientos:
        imp = _f(m["importe"])
        if m["tipo"] == "CARGO":
            saldo_corriente += imp
            total_cargado += imp
            importe_con_signo = imp
        else:
            saldo_corriente -= imp
            total_abonado += imp
            importe_con_signo = -imp
        items.append({
            "tipo": m["tipo"],
            "relacion_id": m["relacion_id"],
            "fecha": m["fecha"],
            "numero_notas": m["numero_notas"],
            "importe": imp,
            "importe_con_signo": round(importe_con_signo, 2),
            "metodo_pago": m["metodo_pago"],
            "referencia": m["referencia"],
            "observaciones": m["observaciones"],
            "saldo_corriente": round(saldo_corriente, 2),
        })

    return {
        "cliente_id": cliente["id"],
        "cliente_nombre": cliente["nombre"],
        "total_cargado": round(total_cargado, 2),
        "total_abonado": round(total_abonado, 2),
        "saldo": round(total_cargado - total_abonado, 2),
        "movimientos": items,
    }


# ═══════════════════════════════════════════════════
# 4. DETALLE + PAGOS  (después de rutas específicas)
# ═══════════════════════════════════════════════════

@router.get("/{id}")
def get_cobranza_detalle(id: int, db: Session = Depends(get_db)):
    row = db.execute(text("""
        SELECT cm.id, cm.cliente_id, c.nombre AS cliente_nombre,
               cm.fecha_relacion, cm.numero_notas, cm.importe_total,
               cm.estatus, cm.posteriormente_facturada, cm.folio_factura_referencia,
               cm.observaciones, cm.cancelada_at, cm.created_at, cm.updated_at,
               COALESCE(pg.total_pagado, 0) AS total_pagado,
               cm.importe_total - COALESCE(pg.total_pagado, 0) AS saldo_pendiente
        FROM cobranza_manual cm
        LEFT JOIN clientes c ON c.id = cm.cliente_id
        LEFT JOIN (
            SELECT cobranza_manual_id, SUM(monto) AS total_pagado
            FROM cobranza_manual_pagos GROUP BY cobranza_manual_id
        ) pg ON pg.cobranza_manual_id = cm.id
        WHERE cm.id = :id
    """), {"id": id}).mappings().first()
    if not row:
        raise HTTPException(status_code=404, detail="Relación de cobranza no encontrada")

    pagos = db.execute(text("""
        SELECT id, fecha_pago, monto, metodo_pago, referencia, observaciones, created_at
        FROM cobranza_manual_pagos
        WHERE cobranza_manual_id = :id
        ORDER BY fecha_pago DESC, id DESC
    """), {"id": id}).mappings().all()

    item = _row_to_item(row)
    item["pagos"] = [{
        "id": p["id"],
        "fecha_pago": p["fecha_pago"],
        "monto": _f(p["monto"]),
        "metodo_pago": p["metodo_pago"],
        "referencia": p["referencia"],
        "observaciones": p["observaciones"],
        "created_at": p["created_at"],
    } for p in pagos]
    return item


# ═══════════════════════════════════════════════════
# 5. CREAR RELACIÓN
# ═══════════════════════════════════════════════════

@router.post("")
def create_cobranza(payload: CobranzaCreate, db: Session = Depends(get_db)):
    if payload.numero_notas is None or payload.numero_notas <= 0:
        raise HTTPException(status_code=400, detail="numero_notas debe ser mayor a 0")
    if payload.importe_total is None or payload.importe_total <= 0:
        raise HTTPException(status_code=400, detail="importe_total debe ser mayor a 0")

    cliente = db.execute(
        text("SELECT id, nombre FROM clientes WHERE id = :id"),
        {"id": payload.cliente_id},
    ).mappings().first()
    if not cliente:
        raise HTTPException(status_code=404, detail=f"Cliente no encontrado: {payload.cliente_id}")

    fecha = payload.fecha_relacion or date.today()

    try:
        row = db.execute(text("""
            INSERT INTO cobranza_manual
                (cliente_id, fecha_relacion, numero_notas, importe_total, estatus,
                 observaciones, posteriormente_facturada, folio_factura_referencia)
            VALUES
                (:cid, :fecha, :notas, :importe, 'PENDIENTE',
                 :obs, :postfact, :folio)
            RETURNING id, cliente_id, fecha_relacion, numero_notas, importe_total, estatus,
                      observaciones, posteriormente_facturada, folio_factura_referencia,
                      cancelada_at, created_at, updated_at
        """), {
            "cid": payload.cliente_id,
            "fecha": fecha,
            "notas": payload.numero_notas,
            "importe": payload.importe_total,
            "obs": normalize_text(payload.observaciones) or None,
            "postfact": bool(payload.posteriormente_facturada),
            "folio": normalize_text(payload.folio_factura_referencia) or None,
        }).mappings().one()

        # Migración 008: el importe_total/numero_notas de la relación son TOTALES
        # ACUMULADOS DERIVADOS de los cargos. Al crear la relación, se registra su
        # PRIMER cargo (origen 'MANUAL') en la MISMA transacción, de modo que el
        # total de la relación quede = ese cargo (coherente).
        db.execute(text("""
            INSERT INTO cobranza_manual_cargos
                (cobranza_manual_id, fecha_cargo, numero_notas, importe, origen, observaciones)
            VALUES
                (:cmid, :fecha, :notas, :importe, 'MANUAL', :obs)
        """), {
            "cmid": row["id"],
            "fecha": fecha,
            "notas": payload.numero_notas,
            "importe": payload.importe_total,
            "obs": "Cargo inicial",
        })

        db.commit()
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))

    result = dict(row)
    result["cliente_nombre"] = cliente["nombre"]
    result["importe_total"] = _f(result["importe_total"])
    result["total_pagado"] = 0.0
    result["saldo_pendiente"] = _f(row["importe_total"])
    return {"ok": True, "cobranza": result}


# ═══════════════════════════════════════════════════
# 6. EDICIÓN ADMINISTRATIVA (PATCH)  — no cambia estatus directo, no cancela
# ═══════════════════════════════════════════════════

@router.patch("/{id}")
def update_cobranza(id: int, payload: CobranzaUpdate, db: Session = Depends(get_db)):
    try:
        # Lectura + bloqueo dentro de la MISMA transacción (evita carrera con abonos).
        existing = db.execute(text("""
            SELECT id, importe_total, estatus, cancelada_at
            FROM cobranza_manual WHERE id = :id
            FOR UPDATE
        """), {"id": id}).mappings().first()
        if not existing:
            db.rollback()
            raise HTTPException(status_code=404, detail="Relación de cobranza no encontrada")
        if existing["estatus"] == "CANCELADA" or existing["cancelada_at"] is not None:
            db.rollback()
            raise HTTPException(status_code=400, detail="No se puede editar una relación CANCELADA")

        # Migración 008: importe_total y numero_notas son ACUMULADOS DERIVADOS de
        # los cargos; YA NO se editan por PATCH (usar POST /{id}/cargos). Aquí solo
        # se editan campos administrativos/informativos.
        updates = []
        params: dict = {"id": id}

        if payload.observaciones is not None:
            updates.append("observaciones = :obs")
            params["obs"] = normalize_text(payload.observaciones) or None
        if payload.fecha_relacion is not None:
            updates.append("fecha_relacion = :fecha")
            params["fecha"] = payload.fecha_relacion
        if payload.posteriormente_facturada is not None:
            updates.append("posteriormente_facturada = :postfact")
            params["postfact"] = bool(payload.posteriormente_facturada)
        if payload.folio_factura_referencia is not None:
            updates.append("folio_factura_referencia = :folio")
            params["folio"] = normalize_text(payload.folio_factura_referencia) or None

        if not updates:
            db.rollback()
            raise HTTPException(status_code=400, detail="No se enviaron campos para actualizar")

        updates.append("updated_at = now()")

        db.execute(text(f"""
            UPDATE cobranza_manual SET {", ".join(updates)}
            WHERE id = :id
        """), params)
        db.commit()
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))

    return {"ok": True, "cobranza": _reload_item(db, id)}


def _reload_item(db: Session, id: int) -> dict:
    """Relee una relación con cliente_nombre y saldos calculados."""
    row = db.execute(text("""
        SELECT cm.id, cm.cliente_id, c.nombre AS cliente_nombre,
               cm.fecha_relacion, cm.numero_notas, cm.importe_total,
               cm.estatus, cm.posteriormente_facturada, cm.folio_factura_referencia,
               cm.observaciones, cm.cancelada_at, cm.created_at, cm.updated_at,
               COALESCE(pg.total_pagado, 0) AS total_pagado,
               cm.importe_total - COALESCE(pg.total_pagado, 0) AS saldo_pendiente
        FROM cobranza_manual cm
        LEFT JOIN clientes c ON c.id = cm.cliente_id
        LEFT JOIN (
            SELECT cobranza_manual_id, SUM(monto) AS total_pagado
            FROM cobranza_manual_pagos GROUP BY cobranza_manual_id
        ) pg ON pg.cobranza_manual_id = cm.id
        WHERE cm.id = :id
    """), {"id": id}).mappings().first()
    return _row_to_item(row)


# ═══════════════════════════════════════════════════
# 7. REGISTRAR ABONO  (transacción con lock)
# ═══════════════════════════════════════════════════

@router.post("/{id}/pagos")
def create_pago_manual(id: int, payload: PagoManualCreate, db: Session = Depends(get_db)):
    # Validaciones de entrada (fuera de la transacción crítica).
    if payload.monto is None or payload.monto <= 0:
        raise HTTPException(status_code=400, detail="El monto del abono debe ser mayor a 0")
    metodo = normalize_text(payload.metodo_pago).upper()
    if metodo not in METODOS_PAGO:
        raise HTTPException(status_code=400, detail=f"metodo_pago debe ser: {', '.join(METODOS_PAGO)}")

    try:
        # (a) Bloquear la relación FOR UPDATE.
        rel = db.execute(text("""
            SELECT id, importe_total, estatus, cancelada_at
            FROM cobranza_manual WHERE id = :id
            FOR UPDATE
        """), {"id": id}).mappings().first()
        if not rel:
            db.rollback()
            raise HTTPException(status_code=404, detail="Relación de cobranza no encontrada")

        # (d) Rechazar si está CANCELADA o PAGADA.
        if rel["estatus"] == "CANCELADA" or rel["cancelada_at"] is not None:
            db.rollback()
            raise HTTPException(status_code=409, detail="No se pueden registrar abonos en una relación CANCELADA")
        if rel["estatus"] == "PAGADA":
            db.rollback()
            raise HTTPException(status_code=409, detail="La relación ya está PAGADA; no admite más abonos")

        # (c) Validar que el monto no supere el saldo pendiente (tolerancia 0.01).
        total_pagado = db.execute(
            text("SELECT COALESCE(SUM(monto), 0) FROM cobranza_manual_pagos WHERE cobranza_manual_id = :id"),
            {"id": id},
        ).scalar()
        saldo = float(rel["importe_total"]) - float(total_pagado)
        if payload.monto > saldo + TOL:
            db.rollback()
            raise HTTPException(status_code=400, detail=f"El abono excede el saldo pendiente (${saldo:.2f})")

        # (e) Insertar el pago.
        pago = db.execute(text("""
            INSERT INTO cobranza_manual_pagos
                (cobranza_manual_id, fecha_pago, monto, metodo_pago, referencia, observaciones)
            VALUES
                (:id, :fecha, :monto, :metodo, :ref, :obs)
            RETURNING id, cobranza_manual_id, fecha_pago, monto, metodo_pago,
                      referencia, observaciones, created_at
        """), {
            "id": id,
            "fecha": payload.fecha_pago or date.today(),
            "monto": payload.monto,
            "metodo": metodo,
            "ref": normalize_text(payload.referencia) or None,
            "obs": normalize_text(payload.observaciones) or None,
        }).mappings().one()

        # (f) Recalcular estatus + updated_at.
        nuevo_total = float(total_pagado) + float(payload.monto)
        nuevo_estatus = _calc_estatus(rel["importe_total"], nuevo_total, None)
        db.execute(text("""
            UPDATE cobranza_manual SET estatus = :est, updated_at = now() WHERE id = :id
        """), {"est": nuevo_estatus, "id": id})

        # (g) Commit.
        db.commit()
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))

    pago_dict = {
        "id": pago["id"],
        "cobranza_manual_id": pago["cobranza_manual_id"],
        "fecha_pago": pago["fecha_pago"],
        "monto": _f(pago["monto"]),
        "metodo_pago": pago["metodo_pago"],
        "referencia": pago["referencia"],
        "observaciones": pago["observaciones"],
        "created_at": pago["created_at"],
    }
    return {"ok": True, "pago": pago_dict, "nuevo_estatus": nuevo_estatus, "cobranza": _reload_item(db, id)}


# ═══════════════════════════════════════════════════
# 8. LISTAR PAGOS DE LA RELACIÓN
# ═══════════════════════════════════════════════════

@router.get("/{id}/pagos")
def list_pagos_manual(id: int, db: Session = Depends(get_db)):
    exists = db.execute(text("SELECT id FROM cobranza_manual WHERE id = :id"), {"id": id}).first()
    if not exists:
        raise HTTPException(status_code=404, detail="Relación de cobranza no encontrada")
    rows = db.execute(text("""
        SELECT id, cobranza_manual_id, fecha_pago, monto, metodo_pago,
               referencia, observaciones, created_at
        FROM cobranza_manual_pagos
        WHERE cobranza_manual_id = :id
        ORDER BY fecha_pago DESC, id DESC
    """), {"id": id}).mappings().all()
    items = [{
        "id": r["id"],
        "cobranza_manual_id": r["cobranza_manual_id"],
        "fecha_pago": r["fecha_pago"],
        "monto": _f(r["monto"]),
        "metodo_pago": r["metodo_pago"],
        "referencia": r["referencia"],
        "observaciones": r["observaciones"],
        "created_at": r["created_at"],
    } for r in rows]
    return {"items": items, "count": len(items)}


# ═══════════════════════════════════════════════════
# 8b. CARGOS (historial que compone el importe/notas acumulados)
# ═══════════════════════════════════════════════════

@router.post("/{id}/cargos")
def create_cargo_manual(id: int, payload: CargoManualCreate, db: Session = Depends(get_db)):
    """Agrega un cargo a la relación (suma a la cuenta). Los acumulados
    importe_total/numero_notas de la relación se incrementan en la MISMA
    transacción. Un cargo puede REABRIR una relación PAGADA (vuelve a
    PARCIAL/PENDIENTE). No se permite en relaciones CANCELADA."""
    # Validaciones de entrada (fuera de la transacción crítica).
    if payload.numero_notas is None or payload.numero_notas <= 0:
        raise HTTPException(status_code=400, detail="numero_notas debe ser mayor a 0")
    if payload.importe is None or payload.importe <= 0:
        raise HTTPException(status_code=400, detail="importe debe ser mayor a 0")

    try:
        # (a) Bloquear la relación FOR UPDATE.
        rel = db.execute(text("""
            SELECT id, importe_total, numero_notas, estatus, cancelada_at
            FROM cobranza_manual WHERE id = :id
            FOR UPDATE
        """), {"id": id}).mappings().first()
        if not rel:
            db.rollback()
            raise HTTPException(status_code=404, detail="Relación de cobranza no encontrada")

        # (b) Rechazar si está CANCELADA.
        if rel["estatus"] == "CANCELADA" or rel["cancelada_at"] is not None:
            db.rollback()
            raise HTTPException(status_code=409, detail="No se pueden agregar cargos a una relación CANCELADA")

        fecha = payload.fecha_cargo or date.today()

        # (c) Insertar el cargo (origen MANUAL).
        cargo = db.execute(text("""
            INSERT INTO cobranza_manual_cargos
                (cobranza_manual_id, fecha_cargo, numero_notas, importe, origen, observaciones)
            VALUES
                (:cmid, :fecha, :notas, :importe, 'MANUAL', :obs)
            RETURNING id, cobranza_manual_id, fecha_cargo, numero_notas, importe,
                      origen, observaciones, created_at
        """), {
            "cmid": id,
            "fecha": fecha,
            "notas": payload.numero_notas,
            "importe": payload.importe,
            "obs": normalize_text(payload.observaciones) or None,
        }).mappings().one()

        # (d) Incrementar los acumulados de la relación.
        nuevo_importe_total = float(rel["importe_total"]) + float(payload.importe)
        nuevo_numero_notas = int(rel["numero_notas"]) + int(payload.numero_notas)

        # (e) Recalcular estatus con el total pagado actual (puede reabrir una PAGADA).
        total_pagado = db.execute(
            text("SELECT COALESCE(SUM(monto), 0) FROM cobranza_manual_pagos WHERE cobranza_manual_id = :id"),
            {"id": id},
        ).scalar()
        nuevo_estatus = _calc_estatus(nuevo_importe_total, float(total_pagado), None)

        db.execute(text("""
            UPDATE cobranza_manual
            SET importe_total = :importe, numero_notas = :notas,
                estatus = :est, updated_at = now()
            WHERE id = :id
        """), {
            "importe": nuevo_importe_total,
            "notas": nuevo_numero_notas,
            "est": nuevo_estatus,
            "id": id,
        })

        db.commit()
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))

    cargo_dict = {
        "id": cargo["id"],
        "cobranza_manual_id": cargo["cobranza_manual_id"],
        "fecha_cargo": cargo["fecha_cargo"],
        "numero_notas": cargo["numero_notas"],
        "importe": _f(cargo["importe"]),
        "origen": cargo["origen"],
        "observaciones": cargo["observaciones"],
        "created_at": cargo["created_at"],
    }
    return {"ok": True, "cargo": cargo_dict, "cobranza": _reload_item(db, id)}


@router.get("/{id}/cargos")
def list_cargos_manual(id: int, db: Session = Depends(get_db)):
    exists = db.execute(text("SELECT id FROM cobranza_manual WHERE id = :id"), {"id": id}).first()
    if not exists:
        raise HTTPException(status_code=404, detail="Relación de cobranza no encontrada")
    rows = db.execute(text("""
        SELECT id, cobranza_manual_id, fecha_cargo, numero_notas, importe,
               origen, observaciones, created_at
        FROM cobranza_manual_cargos
        WHERE cobranza_manual_id = :id
        ORDER BY fecha_cargo ASC, id ASC
    """), {"id": id}).mappings().all()
    items = [{
        "id": r["id"],
        "cobranza_manual_id": r["cobranza_manual_id"],
        "fecha_cargo": r["fecha_cargo"],
        "numero_notas": r["numero_notas"],
        "importe": _f(r["importe"]),
        "origen": r["origen"],
        "observaciones": r["observaciones"],
        "created_at": r["created_at"],
    } for r in rows]
    return {"items": items, "count": len(items)}


# ═══════════════════════════════════════════════════
# 9. CANCELACIÓN LÓGICA
# ═══════════════════════════════════════════════════

@router.post("/{id}/cancelar")
def cancelar_cobranza(id: int, payload: CancelacionBody | None = None, db: Session = Depends(get_db)):
    # Motivo OBLIGATORIO y no vacío (antes de tocar la transacción).
    motivo = normalize_text(payload.motivo) if (payload and payload.motivo) else ""
    if not motivo:
        raise HTTPException(status_code=400, detail="El motivo de cancelación es obligatorio")

    try:
        # Bloquear la relación y evaluar abonos dentro de la MISMA transacción.
        existing = db.execute(text("""
            SELECT id, estatus, observaciones, cancelada_at
            FROM cobranza_manual WHERE id = :id
            FOR UPDATE
        """), {"id": id}).mappings().first()
        if not existing:
            db.rollback()
            raise HTTPException(status_code=404, detail="Relación de cobranza no encontrada")
        if existing["estatus"] == "CANCELADA" or existing["cancelada_at"] is not None:
            db.rollback()
            raise HTTPException(status_code=400, detail="La relación ya está CANCELADA")

        # Los pagos son INMUTABLES: una relación con abonos NO puede cancelarse.
        # Una devolución/reversión será un flujo financiero independiente (futuro).
        total_pagado = db.execute(
            text("SELECT COALESCE(SUM(monto), 0) FROM cobranza_manual_pagos WHERE cobranza_manual_id = :id"),
            {"id": id},
        ).scalar()
        if float(total_pagado) > TOL:
            db.rollback()
            raise HTTPException(
                status_code=409,
                detail=(f"No se puede cancelar: la relación tiene abonos por ${float(total_pagado):.2f}. "
                        "Los pagos son inmutables; una devolución/reversión se maneja como flujo aparte."),
            )

        marca = f"[CANCELADA {date.today().isoformat()}] {motivo}"
        nuevas_obs = f"{existing['observaciones']}\n{marca}" if existing["observaciones"] else marca

        db.execute(text("""
            UPDATE cobranza_manual
            SET estatus = 'CANCELADA', cancelada_at = now(), updated_at = now(),
                observaciones = :obs
            WHERE id = :id
        """), {"obs": nuevas_obs, "id": id})
        db.commit()
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))

    return {"ok": True, "cobranza": _reload_item(db, id)}
