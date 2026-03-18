from fastapi import APIRouter, Depends, Query, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import text
from APP.db import get_db
from APP.schemas import ProductCreate, ProductUpdate
from APP.helpers import (
    normalize_sku, normalize_text, normalize_code, normalize_unit,
    parse_float, build_codigo_pos,
)

router = APIRouter(prefix="/products", tags=["Productos"])


@router.get("")
def list_products(db: Session = Depends(get_db)):
    rows = db.execute(text("""
        SELECT id, sku, codigo_pos, codigo_cat, marca, name, categoria_id,
               unit, min_stock, price, is_active, created_at,
               aplicacion, ubicacion, descripcion_larga,
               anio_inicio, anio_fin, dim_largo, dim_ancho, dim_alto, equivalencia, imagen_url
        FROM productos
        ORDER BY id
    """)).mappings().all()
    return rows


@router.get("/search")
def search_products(
    q: str = Query(..., min_length=1),
    limit: int = Query(default=20, ge=1, le=100),
    db: Session = Depends(get_db),
):
    q = normalize_text(q)
    rows = db.execute(
        text("""
            SELECT id, sku, codigo_pos, codigo_cat, marca, name, categoria_id,
                   unit, min_stock, price, is_active
            FROM productos
            WHERE sku ILIKE :q
               OR codigo_pos ILIKE :q
               OR name ILIKE :q
               OR COALESCE(marca, '') ILIKE :q
            ORDER BY sku
            LIMIT :limit
        """),
        {"q": f"%{q}%", "limit": limit},
    ).mappings().all()
    return {"items": rows, "count": len(rows)}


@router.get("/count")
def products_count(db: Session = Depends(get_db)):
    n = db.execute(text("SELECT COUNT(*) FROM productos")).scalar()
    return {"count": int(n)}


@router.get("/{sku}")
def get_product_by_sku(sku: str, db: Session = Depends(get_db)):
    sku = normalize_sku(sku)
    row = db.execute(
        text("""
            SELECT id, sku, codigo_pos, codigo_cat, marca, name, categoria_id,
                   unit, min_stock, price, is_active, created_at,
                   aplicacion, ubicacion, descripcion_larga,
                   anio_inicio, anio_fin, dim_largo, dim_ancho, dim_alto, equivalencia, imagen_url
            FROM productos
            WHERE UPPER(sku) = :sku
            LIMIT 1
        """),
        {"sku": sku},
    ).mappings().first()
    if not row:
        raise HTTPException(status_code=404, detail=f"SKU no encontrado: {sku}")
    return dict(row)

@router.post("")
def create_product(payload: ProductCreate, db: Session = Depends(get_db)):
    sku = normalize_sku(payload.sku)
    name = normalize_text(payload.name)
    if not sku:
        raise HTTPException(status_code=400, detail="SKU no puede estar vacío")
    if not name:
        raise HTTPException(status_code=400, detail="name no puede estar vacío")

    codigo_cat = normalize_code(payload.codigo_cat) or None
    codigo_pos = normalize_code(payload.codigo_pos) or None
    marca = normalize_text(payload.marca).upper() or None
    unit = normalize_unit(payload.unit)

    if not codigo_pos and codigo_cat:
        codigo_pos = build_codigo_pos(codigo_cat, sku)

    row = db.execute(
        text("""
            INSERT INTO productos
                (sku, name, codigo_pos, codigo_cat, marca, price, categoria_id,
                 unit, min_stock, is_active, aplicacion, ubicacion, descripcion_larga,
                 anio_inicio, anio_fin, dim_largo, dim_ancho, dim_alto, equivalencia, imagen_url)
            VALUES
                (:sku, :name, :codigo_pos, :codigo_cat, :marca, :price, :categoria_id,
                 :unit, :min_stock, :is_active, :aplicacion, :ubicacion, :descripcion_larga,
                 :anio_inicio, :anio_fin, :dim_largo, :dim_ancho, :dim_alto, :equivalencia, :imagen_url)
            ON CONFLICT (sku) DO UPDATE
            SET
                name = EXCLUDED.name,
                codigo_pos = EXCLUDED.codigo_pos,
                codigo_cat = EXCLUDED.codigo_cat,
                marca = EXCLUDED.marca,
                price = EXCLUDED.price,
                categoria_id = EXCLUDED.categoria_id,
                unit = EXCLUDED.unit,
                min_stock = EXCLUDED.min_stock,
                is_active = EXCLUDED.is_active,
                aplicacion = EXCLUDED.aplicacion,
                ubicacion = EXCLUDED.ubicacion,
                descripcion_larga = EXCLUDED.descripcion_larga,
                anio_inicio = EXCLUDED.anio_inicio,
                anio_fin = EXCLUDED.anio_fin,
                dim_largo = EXCLUDED.dim_largo,
                dim_ancho = EXCLUDED.dim_ancho,
                dim_alto = EXCLUDED.dim_alto,
                equivalencia = EXCLUDED.equivalencia,
                imagen_url = EXCLUDED.imagen_url
            RETURNING
                id, sku, name, codigo_pos, codigo_cat, marca, price,
                categoria_id, unit, min_stock, is_active, created_at,
                (xmax = 0) AS inserted_flag
        """),
        {
            "sku": sku, "name": name, "codigo_pos": codigo_pos,
            "codigo_cat": codigo_cat, "marca": marca, "price": payload.price,
            "categoria_id": payload.categoria_id, "unit": unit,
            "min_stock": payload.min_stock, "is_active": payload.is_active,
            "aplicacion": payload.aplicacion, "ubicacion": payload.ubicacion,
            "descripcion_larga": payload.descripcion_larga,
            "anio_inicio": payload.anio_inicio, "anio_fin": payload.anio_fin,
            "dim_largo": payload.dim_largo, "dim_ancho": payload.dim_ancho,
            "dim_alto": payload.dim_alto, "equivalencia": payload.equivalencia,
            "imagen_url": payload.imagen_url,
        },
    ).mappings().one()
    db.commit()
    action = "inserted" if row["inserted_flag"] else "updated"
    return {"ok": True, "action": action, "product": dict(row)}


@router.patch("/{sku}")
def update_product(sku: str, payload: ProductUpdate, db: Session = Depends(get_db)):
    sku = normalize_sku(sku)

    existing = db.execute(
        text("SELECT id FROM productos WHERE UPPER(sku) = :sku LIMIT 1"),
        {"sku": sku},
    ).mappings().first()
    if not existing:
        raise HTTPException(status_code=404, detail=f"SKU no existe: {sku}")

    updates = []
    params = {"sku": sku}

    field_map = {
        "name": ("name", lambda v: normalize_text(v)),
        "categoria_id": ("categoria_id", lambda v: v),
        "unit": ("unit", lambda v: normalize_unit(v)),
        "min_stock": ("min_stock", lambda v: v),
        "is_active": ("is_active", lambda v: bool(v)),
        "price": ("price", lambda v: v),
        "marca": ("marca", lambda v: normalize_text(v).upper()),
        "aplicacion": ("aplicacion", lambda v: v),
        "ubicacion": ("ubicacion", lambda v: v),
        "descripcion_larga": ("descripcion_larga", lambda v: v),
        "anio_inicio": ("anio_inicio", lambda v: v),
        "anio_fin": ("anio_fin", lambda v: v),
        "dim_largo": ("dim_largo", lambda v: v),
        "dim_ancho": ("dim_ancho", lambda v: v),
        "dim_alto": ("dim_alto", lambda v: v),
        "equivalencia": ("equivalencia", lambda v: v),
        "imagen_url": ("imagen_url", lambda v: v),
    }

    for field, (col, transform) in field_map.items():
        value = getattr(payload, field)
        if value is not None:
            updates.append(f"{col} = :{col}")
            params[col] = transform(value)

    if payload.codigo_cat is not None:
        codigo_cat = normalize_code(payload.codigo_cat)
        try:
            codigo_cat = str(int(float(codigo_cat))).zfill(4)
        except Exception:
            raise HTTPException(status_code=400, detail=f"codigo_cat inválido: {payload.codigo_cat}")
        if len(codigo_cat) != 4 or not codigo_cat.isdigit():
            raise HTTPException(status_code=400, detail=f"codigo_cat inválido: {payload.codigo_cat}")
        updates.append("codigo_cat = :codigo_cat")
        params["codigo_cat"] = codigo_cat

    if payload.codigo_pos is not None:
        updates.append("codigo_pos = :codigo_pos")
        params["codigo_pos"] = normalize_code(payload.codigo_pos)

    if not updates:
        raise HTTPException(status_code=400, detail="No se enviaron campos para actualizar")

    if payload.codigo_cat is not None and payload.codigo_pos is None:
        codigo_pos = build_codigo_pos(params["codigo_cat"], sku)
        if "codigo_pos = :codigo_pos" not in updates:
            updates.append("codigo_pos = :codigo_pos")
        params["codigo_pos"] = codigo_pos

    row = db.execute(
        text(f"""
            UPDATE productos
            SET {", ".join(updates)}
            WHERE UPPER(sku) = :sku
            RETURNING id, sku, codigo_pos, codigo_cat, marca, name,
                      categoria_id, unit, min_stock, price, is_active, created_at
        """),
        params,
    ).mappings().one()
    db.commit()
    return {"ok": True, "product": dict(row)}
