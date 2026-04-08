from fastapi import APIRouter, Depends, Query, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import text
from APP.db import get_db
from APP.schemas_faltantes import FaltanteCreate, FaltanteUpdate

router = APIRouter(prefix="/faltantes", tags=["Faltantes"])

VALID_STATUS = ("pendiente", "comprado", "cancelado")


@router.post("")
def create_faltante(payload: FaltanteCreate, db: Session = Depends(get_db)):
    if payload.cantidad_faltante <= 0:
        raise HTTPException(status_code=400, detail="cantidad_faltante debe ser mayor a 0")

    prod = db.execute(
        text("SELECT id, sku, name FROM productos WHERE id = :id"),
        {"id": payload.product_id},
    ).mappings().first()
    if not prod:
        raise HTTPException(status_code=404, detail=f"Producto no existe: {payload.product_id}")

    row = db.execute(
        text("""
            INSERT INTO faltantes (product_id, cantidad_faltante, comentario)
            VALUES (:pid, :qty, :com)
            RETURNING id, product_id, cantidad_faltante, comentario, fecha_detectado, status
        """),
        {
            "pid": payload.product_id,
            "qty": payload.cantidad_faltante,
            "com": payload.comentario or None,
        },
    ).mappings().one()
    db.commit()
    return {"ok": True, "faltante": dict(row)}


@router.get("")
def list_faltantes(
    status: str | None = Query(default=None, description="Filtrar por status"),
    proveedor_id: int | None = Query(default=None, description="Filtrar por proveedor sugerido"),
    db: Session = Depends(get_db),
):
    where = []
    params = {}

    if status:
        if status not in VALID_STATUS:
            raise HTTPException(status_code=400, detail=f"status debe ser: {', '.join(VALID_STATUS)}")
        where.append("f.status = :status")
        params["status"] = status

    if proveedor_id is not None:
        where.append("pp.proveedor_id = :prov_id")
        params["prov_id"] = proveedor_id

    where_sql = ("WHERE " + " AND ".join(where)) if where else ""

    rows = db.execute(
        text(f"""
            SELECT f.id, f.product_id, p.sku, p.name as product_name, p.marca,
                   f.cantidad_faltante, f.comentario, f.fecha_detectado, f.status,
                   pv.id as proveedor_id, pv.nombre as proveedor_nombre
            FROM faltantes f
            JOIN productos p ON p.id = f.product_id
            LEFT JOIN producto_proveedor pp ON pp.product_id = p.id AND pp.is_primary = true
            LEFT JOIN proveedores pv ON pv.id = pp.proveedor_id
            {where_sql}
            ORDER BY f.fecha_detectado DESC
        """),
        params,
    ).mappings().all()
    return {"items": rows, "count": len(rows)}


@router.patch("/{faltante_id}")
def update_faltante(faltante_id: int, payload: FaltanteUpdate, db: Session = Depends(get_db)):
    existing = db.execute(
        text("SELECT id FROM faltantes WHERE id = :id"),
        {"id": faltante_id},
    ).mappings().first()
    if not existing:
        raise HTTPException(status_code=404, detail="Faltante no encontrado")

    updates: list[str] = []
    params: dict = {"id": faltante_id}

    if payload.status is not None:
        if payload.status not in VALID_STATUS:
            raise HTTPException(status_code=400, detail=f"status debe ser: {', '.join(VALID_STATUS)}")
        updates.append("status = :status")
        params["status"] = payload.status

    if payload.product_id is not None:
        if not db.execute(text("SELECT 1 FROM productos WHERE id = :pid"), {"pid": payload.product_id}).scalar():
            raise HTTPException(status_code=404, detail=f"Producto no existe: {payload.product_id}")
        updates.append("product_id = :product_id")
        params["product_id"] = payload.product_id

    if payload.cantidad_faltante is not None:
        if payload.cantidad_faltante <= 0:
            raise HTTPException(status_code=400, detail="cantidad_faltante debe ser mayor a 0")
        updates.append("cantidad_faltante = :cantidad_faltante")
        params["cantidad_faltante"] = payload.cantidad_faltante

    if payload.comentario is not None:
        updates.append("comentario = :comentario")
        params["comentario"] = payload.comentario or None

    if not updates:
        raise HTTPException(status_code=400, detail="No se enviaron campos para actualizar")

    row = db.execute(
        text(f"""
            UPDATE faltantes SET {', '.join(updates)}
            WHERE id = :id
            RETURNING id, product_id, cantidad_faltante, comentario, fecha_detectado, status
        """),
        params,
    ).mappings().one()
    db.commit()
    return {"ok": True, "faltante": dict(row)}


@router.delete("/{faltante_id}")
def delete_faltante(faltante_id: int, db: Session = Depends(get_db)):
    existing = db.execute(
        text("SELECT id FROM faltantes WHERE id = :id"),
        {"id": faltante_id},
    ).mappings().first()
    if not existing:
        raise HTTPException(status_code=404, detail="Faltante no encontrado")

    db.execute(text("DELETE FROM faltantes WHERE id = :id"), {"id": faltante_id})
    db.commit()
    return {"ok": True, "deleted": faltante_id}


@router.get("/por-proveedor")
def faltantes_por_proveedor(db: Session = Depends(get_db)):
    """Agrupa faltantes pendientes por proveedor sugerido."""
    rows = db.execute(
        text("""
            SELECT f.id, f.product_id, p.sku, p.name as product_name, p.marca, p.unit,
                   f.cantidad_faltante, f.comentario, f.fecha_detectado,
                   pv.id as proveedor_id, COALESCE(pv.nombre, 'Sin proveedor') as proveedor_nombre,
                   pp.supplier_sku, pp.precio_proveedor
            FROM faltantes f
            JOIN productos p ON p.id = f.product_id
            LEFT JOIN producto_proveedor pp ON pp.product_id = p.id AND pp.is_primary = true
            LEFT JOIN proveedores pv ON pv.id = pp.proveedor_id
            WHERE f.status = 'pendiente'
            ORDER BY pv.nombre NULLS LAST, p.sku
        """),
    ).mappings().all()

    grupos = {}
    for r in rows:
        key = r["proveedor_nombre"]
        if key not in grupos:
            grupos[key] = {
                "proveedor_id": r["proveedor_id"],
                "proveedor_nombre": key,
                "productos": [],
                "total_items": 0,
            }
        grupos[key]["productos"].append({
            "faltante_id": r["id"],
            "product_id": r["product_id"],
            "sku": r["sku"],
            "product_name": r["product_name"],
            "marca": r["marca"],
            "unit": r["unit"],
            "cantidad_faltante": r["cantidad_faltante"],
            "comentario": r["comentario"],
            "fecha_detectado": r["fecha_detectado"],
            "supplier_sku": r["supplier_sku"],
            "precio_proveedor": float(r["precio_proveedor"]) if r["precio_proveedor"] else None,
        })
        grupos[key]["total_items"] += 1

    return {"grupos": list(grupos.values()), "total_proveedores": len(grupos)}
