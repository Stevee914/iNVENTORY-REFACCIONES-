from fastapi import APIRouter, Depends, Query, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import text
from APP.db import get_db
from APP.schemas import ProveedorCreate, ProveedorUpdate
from APP.helpers import normalize_text

router = APIRouter(prefix="/proveedores", tags=["Proveedores"])


@router.get("")
def list_proveedores(db: Session = Depends(get_db)):
    rows = db.execute(text("""
        SELECT id, nombre, codigo_corto, rfc, created_at
        FROM proveedores
        ORDER BY nombre
    """)).mappings().all()
    return rows


@router.get("/search")
def search_proveedores(
    q: str = Query(..., min_length=1),
    limit: int = Query(default=20, ge=1, le=100),
    db: Session = Depends(get_db),
):
    q = normalize_text(q)
    rows = db.execute(
        text("""
            SELECT id, nombre, codigo_corto, rfc
            FROM proveedores
            WHERE nombre ILIKE :q
               OR codigo_corto ILIKE :q
               OR COALESCE(rfc, '') ILIKE :q
            ORDER BY nombre
            LIMIT :limit
        """),
        {"q": f"%{q}%", "limit": limit},
    ).mappings().all()
    return {"items": rows, "count": len(rows)}


@router.get("/{proveedor_id}")
def get_proveedor(proveedor_id: int, db: Session = Depends(get_db)):
    row = db.execute(
        text("SELECT id, nombre, codigo_corto, rfc, created_at FROM proveedores WHERE id = :id"),
        {"id": proveedor_id},
    ).mappings().first()
    if not row:
        raise HTTPException(status_code=404, detail="Proveedor no encontrado")
    return row


@router.post("")
def create_proveedor(payload: ProveedorCreate, db: Session = Depends(get_db)):
    nombre = normalize_text(payload.nombre).upper()
    codigo_corto = normalize_text(payload.codigo_corto).upper()
    rfc = normalize_text(payload.rfc).upper() or None

    if not nombre:
        raise HTTPException(status_code=400, detail="nombre no puede estar vacío")
    if not codigo_corto:
        raise HTTPException(status_code=400, detail="codigo_corto no puede estar vacío")

    try:
        row = db.execute(
            text("""
                INSERT INTO proveedores (nombre, codigo_corto, rfc)
                VALUES (:nombre, :codigo_corto, :rfc)
                RETURNING id, nombre, codigo_corto, rfc, created_at
            """),
            {"nombre": nombre, "codigo_corto": codigo_corto, "rfc": rfc},
        ).mappings().one()
        db.commit()
    except Exception as e:
        db.rollback()
        if "proveedores_codigo_corto_key" in str(e) or "uq_proveedores_codigo_corto" in str(e):
            raise HTTPException(status_code=409, detail=f"codigo_corto ya existe: {codigo_corto}")
        if "uq_proveedores_rfc" in str(e):
            raise HTTPException(status_code=409, detail=f"RFC ya existe: {rfc}")
        raise HTTPException(status_code=500, detail=str(e))

    return {"ok": True, "proveedor": dict(row)}


@router.patch("/{proveedor_id}")
def update_proveedor(proveedor_id: int, payload: ProveedorUpdate, db: Session = Depends(get_db)):
    existing = db.execute(
        text("SELECT id FROM proveedores WHERE id = :id"),
        {"id": proveedor_id},
    ).mappings().first()
    if not existing:
        raise HTTPException(status_code=404, detail="Proveedor no encontrado")

    updates = []
    params = {"id": proveedor_id}

    if payload.nombre is not None:
        updates.append("nombre = :nombre")
        params["nombre"] = normalize_text(payload.nombre).upper()
    if payload.codigo_corto is not None:
        updates.append("codigo_corto = :codigo_corto")
        params["codigo_corto"] = normalize_text(payload.codigo_corto).upper()
    if payload.rfc is not None:
        updates.append("rfc = :rfc")
        params["rfc"] = normalize_text(payload.rfc).upper() or None

    if not updates:
        raise HTTPException(status_code=400, detail="No se enviaron campos para actualizar")

    try:
        row = db.execute(
            text(f"""
                UPDATE proveedores SET {", ".join(updates)}
                WHERE id = :id
                RETURNING id, nombre, codigo_corto, rfc, created_at
            """),
            params,
        ).mappings().one()
        db.commit()
    except Exception as e:
        db.rollback()
        if "codigo_corto" in str(e):
            raise HTTPException(status_code=409, detail="codigo_corto ya existe")
        if "rfc" in str(e):
            raise HTTPException(status_code=409, detail="RFC ya existe")
        raise HTTPException(status_code=500, detail=str(e))

    return {"ok": True, "proveedor": dict(row)}


@router.delete("/{proveedor_id}")
def delete_proveedor(proveedor_id: int, db: Session = Depends(get_db)):
    existing = db.execute(
        text("SELECT id FROM proveedores WHERE id = :id"),
        {"id": proveedor_id},
    ).mappings().first()
    if not existing:
        raise HTTPException(status_code=404, detail="Proveedor no encontrado")

    # Verificar que no tenga movimientos asociados
    has_movs = db.execute(
        text("SELECT 1 FROM movimientos_inventario WHERE proveedor_id = :id LIMIT 1"),
        {"id": proveedor_id},
    ).scalar()
    if has_movs:
        raise HTTPException(status_code=409, detail="No se puede eliminar: tiene movimientos asociados")

    db.execute(text("DELETE FROM producto_proveedor WHERE proveedor_id = :id"), {"id": proveedor_id})
    db.execute(text("DELETE FROM proveedores WHERE id = :id"), {"id": proveedor_id})
    db.commit()
    return {"ok": True, "deleted": proveedor_id}
