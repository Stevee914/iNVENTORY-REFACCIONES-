import logging
from fastapi import APIRouter, Depends, Query, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError
from APP.db import get_db
from APP.schemas import MovementCreate
from APP.helpers import normalize_sku, normalize_text, normalize_quantity, derive_evento, calc_costo_con_iva

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/movements", tags=["Movimientos"])


@router.post("")
def create_movement(payload: MovementCreate, db: Session = Depends(get_db)):
    sku = normalize_sku(payload.sku)
    movement_type = payload.movement_type.value
    libro = payload.libro.value
    reference = normalize_text(payload.reference) or None
    notes = normalize_text(payload.notes) or None

    try:
        quantity = normalize_quantity(movement_type, payload.quantity)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    # Derivar evento automáticamente si no se envió
    if payload.evento:
        evento = payload.evento.value
    else:
        evento = derive_evento(movement_type, libro, payload.proveedor_id)

    # Validar: ENTRADA_FACTURA requiere proveedor
    if evento == "ENTRADA_FACTURA" and payload.proveedor_id is None:
        raise HTTPException(
            status_code=400,
            detail="ENTRADA_FACTURA requiere proveedor_id"
        )

    # Validar proveedor existe si se envió
    if payload.proveedor_id is not None:
        prov = db.execute(
            text("SELECT id FROM proveedores WHERE id = :id"),
            {"id": payload.proveedor_id},
        ).mappings().first()
        if not prov:
            raise HTTPException(status_code=404, detail=f"Proveedor no existe: {payload.proveedor_id}")

    # Buscar producto
    product = db.execute(
        text("SELECT id FROM productos WHERE UPPER(sku) = :sku"),
        {"sku": sku},
    ).mappings().first()
    if not product:
        raise HTTPException(status_code=404, detail=f"SKU no existe: {sku}")

    # Calcular costo con IVA
    costo_con_iva = calc_costo_con_iva(payload.costo_unit_sin_iva, payload.tasa_iva)

    try:
        row = db.execute(
            text("""
                INSERT INTO movimientos_inventario
                    (product_id, libro, movement_type, evento, quantity,
                     reference, notes, proveedor_id,
                     costo_unit_sin_iva, tasa_iva, costo_unit_con_iva, precio_venta_unit,
                     movement_date, created_at)
                VALUES
                    (:product_id, :libro, :movement_type, :evento, :quantity,
                     :reference, :notes, :proveedor_id,
                     :costo_sin_iva, :tasa_iva, :costo_con_iva, :precio_venta,
                     NOW(), NOW())
                RETURNING id, product_id, libro, movement_type, evento, quantity,
                          movement_date, reference, notes, proveedor_id,
                          costo_unit_sin_iva, tasa_iva, costo_unit_con_iva, precio_venta_unit
            """),
            {
                "product_id": product["id"],
                "libro": libro,
                "movement_type": movement_type,
                "evento": evento,
                "quantity": quantity,
                "reference": reference,
                "notes": notes,
                "proveedor_id": payload.proveedor_id,
                "costo_sin_iva": payload.costo_unit_sin_iva,
                "tasa_iva": payload.tasa_iva,
                "costo_con_iva": costo_con_iva,
                "precio_venta": payload.precio_venta_unit,
            },
        ).mappings().one()
        db.commit()
    except IntegrityError as e:
        db.rollback()
        logger.error("IntegrityError en movimiento sku=%s evento=%s: %s", sku, evento, e)
        raise HTTPException(status_code=400, detail="Movimiento rechazado: datos inconsistentes (proveedor requerido o restricción de integridad)")
    except Exception as e:
        db.rollback()
        logger.error("Error inesperado en movimiento sku=%s: %s", sku, e)
        raise HTTPException(status_code=500, detail="Error interno al registrar el movimiento")

    return {"ok": True, "movement": dict(row)}


@router.get("/kardex/{sku}")
def kardex_by_sku(
    sku: str,
    limit: int = Query(default=100, ge=1, le=500),
    db: Session = Depends(get_db),
):
    sku = normalize_sku(sku)
    rows = db.execute(
        text("""
            SELECT
                mi.id, p.sku, mi.libro, mi.movement_type, mi.evento,
                mi.quantity, mi.reference, mi.notes, mi.proveedor_id,
                mi.costo_unit_sin_iva, mi.tasa_iva, mi.costo_unit_con_iva,
                mi.precio_venta_unit, mi.movement_date, mi.created_at
            FROM movimientos_inventario mi
            JOIN productos p ON p.id = mi.product_id
            WHERE p.sku = :sku
            ORDER BY mi.movement_date DESC, mi.id DESC
            LIMIT :limit
        """),
        {"sku": sku, "limit": limit},
    ).mappings().all()
    return {"sku": sku, "items": rows, "count": len(rows)}
