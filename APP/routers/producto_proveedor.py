from fastapi import APIRouter, Depends, Query, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import text
from APP.db import get_db
from APP.schemas import ProductoProveedorCreate, ProductoProveedorUpdate
from APP.helpers import normalize_text

router = APIRouter(prefix="/producto-proveedor", tags=["Producto-Proveedor"])


@router.get("")
def list_mappings(
    proveedor_id: int | None = Query(default=None),
    product_id: int | None = Query(default=None),
    db: Session = Depends(get_db),
):
    where = []
    params = {}
    if proveedor_id is not None:
        where.append("pp.proveedor_id = :prov_id")
        params["prov_id"] = proveedor_id
    if product_id is not None:
        where.append("pp.product_id = :prod_id")
        params["prod_id"] = product_id

    where_sql = ("WHERE " + " AND ".join(where)) if where else ""

    rows = db.execute(
        text(f"""
            SELECT pp.id, pp.proveedor_id, pv.nombre as proveedor_nombre,
                   pp.product_id, p.sku, p.name as product_name,
                   pp.supplier_sku, pp.descripcion_proveedor, pp.is_primary, pp.created_at
            FROM producto_proveedor pp
            JOIN proveedores pv ON pv.id = pp.proveedor_id
            JOIN productos p ON p.id = pp.product_id
            {where_sql}
            ORDER BY pv.nombre, p.sku
        """),
        params,
    ).mappings().all()
    return {"items": rows, "count": len(rows)}


@router.post("")
def create_mapping(payload: ProductoProveedorCreate, db: Session = Depends(get_db)):
    # Validar proveedor
    prov = db.execute(
        text("SELECT id FROM proveedores WHERE id = :id"),
        {"id": payload.proveedor_id},
    ).mappings().first()
    if not prov:
        raise HTTPException(status_code=404, detail=f"Proveedor no existe: {payload.proveedor_id}")

    # Validar producto
    prod = db.execute(
        text("SELECT id FROM productos WHERE id = :id"),
        {"id": payload.product_id},
    ).mappings().first()
    if not prod:
        raise HTTPException(status_code=404, detail=f"Producto no existe: {payload.product_id}")

    supplier_sku = normalize_text(payload.supplier_sku).upper()
    if not supplier_sku:
        raise HTTPException(status_code=400, detail="supplier_sku no puede estar vacío")

    try:
        row = db.execute(
            text("""
                INSERT INTO producto_proveedor
                    (proveedor_id, product_id, supplier_sku, descripcion_proveedor, is_primary)
                VALUES
                    (:prov_id, :prod_id, :sup_sku, :desc, :is_primary)
                RETURNING id, proveedor_id, product_id, supplier_sku, descripcion_proveedor, is_primary, created_at
            """),
            {
                "prov_id": payload.proveedor_id,
                "prod_id": payload.product_id,
                "sup_sku": supplier_sku,
                "desc": payload.descripcion_proveedor,
                "is_primary": payload.is_primary,
            },
        ).mappings().one()
        db.commit()
    except Exception as e:
        db.rollback()
        if "proveedor_id_supplier_sku" in str(e):
            raise HTTPException(status_code=409, detail=f"El código {supplier_sku} ya existe para este proveedor")
        raise HTTPException(status_code=500, detail=str(e))

    return {"ok": True, "mapping": dict(row)}


@router.patch("/{mapping_id}")
def update_mapping(mapping_id: int, payload: ProductoProveedorUpdate, db: Session = Depends(get_db)):
    existing = db.execute(
        text("SELECT id FROM producto_proveedor WHERE id = :id"),
        {"id": mapping_id},
    ).mappings().first()
    if not existing:
        raise HTTPException(status_code=404, detail="Mapeo no encontrado")

    updates = []
    params = {"id": mapping_id}

    if payload.supplier_sku is not None:
        updates.append("supplier_sku = :sup_sku")
        params["sup_sku"] = normalize_text(payload.supplier_sku).upper()
    if payload.descripcion_proveedor is not None:
        updates.append("descripcion_proveedor = :desc")
        params["desc"] = payload.descripcion_proveedor
    if payload.is_primary is not None:
        updates.append("is_primary = :is_primary")
        params["is_primary"] = payload.is_primary

    if not updates:
        raise HTTPException(status_code=400, detail="No se enviaron campos")

    row = db.execute(
        text(f"""
            UPDATE producto_proveedor SET {", ".join(updates)}
            WHERE id = :id
            RETURNING id, proveedor_id, product_id, supplier_sku, descripcion_proveedor, is_primary
        """),
        params,
    ).mappings().one()
    db.commit()
    return {"ok": True, "mapping": dict(row)}


@router.delete("/{mapping_id}")
def delete_mapping(mapping_id: int, db: Session = Depends(get_db)):
    existing = db.execute(
        text("SELECT id FROM producto_proveedor WHERE id = :id"),
        {"id": mapping_id},
    ).mappings().first()
    if not existing:
        raise HTTPException(status_code=404, detail="Mapeo no encontrado")

    db.execute(text("DELETE FROM producto_proveedor WHERE id = :id"), {"id": mapping_id})
    db.commit()
    return {"ok": True, "deleted": mapping_id}
