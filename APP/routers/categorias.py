from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import text
from APP.db import get_db
from APP.schemas import CategoriaCreate, CategoriaUpdate
from APP.helpers import normalize_text

router = APIRouter(prefix="/categorias", tags=["Categorías"])


@router.get("")
def list_categorias(db: Session = Depends(get_db)):
    rows = db.execute(text("""
        SELECT c.id, c.name, c.description, c.parent_id, p.name as parent_name, c.created_at
        FROM categoria c
        LEFT JOIN categoria p ON p.id = c.parent_id
        ORDER BY c.parent_id NULLS FIRST, c.name
    """)).mappings().all()
    return rows


@router.get("/tree")
def categorias_tree(db: Session = Depends(get_db)):
    """Devuelve categorías en formato árbol recursivo con conteo acumulado de productos."""
    rows = db.execute(text("""
        WITH RECURSIVE descendants AS (
            SELECT id AS root_id, id AS desc_id FROM categoria
            UNION ALL
            SELECT d.root_id, c.id
            FROM descendants d
            JOIN categoria c ON c.parent_id = d.desc_id
        ),
        recursive_counts AS (
            SELECT d.root_id, COUNT(p.id) AS total_productos
            FROM descendants d
            LEFT JOIN productos p ON p.categoria_id = d.desc_id
            GROUP BY d.root_id
        )
        SELECT c.id, c.name, c.description, c.parent_id,
               COALESCE(rc.total_productos, 0) AS total_productos
        FROM categoria c
        LEFT JOIN recursive_counts rc ON rc.root_id = c.id
        ORDER BY c.name
    """)).mappings().all()

    by_id = {r["id"]: {**dict(r), "subcategorias": []} for r in rows}

    roots = []
    for node in by_id.values():
        if node["parent_id"] is None:
            roots.append(node)
        else:
            parent = by_id.get(node["parent_id"])
            if parent:
                parent["subcategorias"].append(node)

    return roots


@router.get("/{categoria_id}")
def get_categoria(categoria_id: int, db: Session = Depends(get_db)):
    row = db.execute(
        text("""
            SELECT c.id, c.name, c.description, c.parent_id, p.name as parent_name, c.created_at
            FROM categoria c
            LEFT JOIN categoria p ON p.id = c.parent_id
            WHERE c.id = :id
        """),
        {"id": categoria_id},
    ).mappings().first()
    if not row:
        raise HTTPException(status_code=404, detail="Categoría no encontrada")
    return row


@router.post("")
def create_categoria(payload: CategoriaCreate, db: Session = Depends(get_db)):
    name = normalize_text(payload.name).upper()
    if not name:
        raise HTTPException(status_code=400, detail="name no puede estar vacío")

    if payload.parent_id is not None:
        parent = db.execute(
            text("SELECT id FROM categoria WHERE id = :id"),
            {"id": payload.parent_id},
        ).mappings().first()
        if not parent:
            raise HTTPException(status_code=404, detail=f"Categoría padre no existe: {payload.parent_id}")

    try:
        row = db.execute(
            text("""
                INSERT INTO categoria (name, description, parent_id)
                VALUES (:name, :desc, :parent_id)
                RETURNING id, name, description, parent_id, created_at
            """),
            {"name": name, "desc": payload.description, "parent_id": payload.parent_id},
        ).mappings().one()
        db.commit()
    except Exception as e:
        db.rollback()
        if "categoria_name" in str(e):
            raise HTTPException(status_code=409, detail=f"Categoría ya existe: {name}")
        raise HTTPException(status_code=500, detail=str(e))

    return {"ok": True, "categoria": dict(row)}


@router.patch("/{categoria_id}")
def update_categoria(categoria_id: int, payload: CategoriaUpdate, db: Session = Depends(get_db)):
    existing = db.execute(
        text("SELECT id FROM categoria WHERE id = :id"),
        {"id": categoria_id},
    ).mappings().first()
    if not existing:
        raise HTTPException(status_code=404, detail="Categoría no encontrada")

    updates = []
    params = {"id": categoria_id}

    if payload.name is not None:
        updates.append("name = :name")
        params["name"] = normalize_text(payload.name).upper()
    if payload.description is not None:
        updates.append("description = :desc")
        params["desc"] = payload.description
    if payload.parent_id is not None:
        if payload.parent_id == categoria_id:
            raise HTTPException(status_code=400, detail="Una categoría no puede ser su propio padre")
        updates.append("parent_id = :parent_id")
        params["parent_id"] = payload.parent_id

    if not updates:
        raise HTTPException(status_code=400, detail="No se enviaron campos para actualizar")

    try:
        row = db.execute(
            text(f"""
                UPDATE categoria SET {", ".join(updates)}
                WHERE id = :id
                RETURNING id, name, description, parent_id, created_at
            """),
            params,
        ).mappings().one()
        db.commit()
    except Exception as e:
        db.rollback()
        if "categoria_name" in str(e):
            raise HTTPException(status_code=409, detail=f"Ya existe una categoría con ese nombre en el mismo nivel")
        raise HTTPException(status_code=500, detail=str(e))

    return {"ok": True, "categoria": dict(row)}
