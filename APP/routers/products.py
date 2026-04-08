import math
from decimal import Decimal
from datetime import datetime, date
from fastapi import APIRouter, Depends, Query, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import text
from APP.db import get_db
from APP.schemas import ProductCreate, ProductUpdate
from APP.helpers import (
    normalize_sku, normalize_text, normalize_code, normalize_unit,
    parse_float, build_codigo_pos,
)

def _sanitize(row: dict) -> dict:
    """Normalize a DB row dict to plain JSON-safe Python types."""
    out = {}
    for k, v in row.items():
        if isinstance(v, float) and not math.isfinite(v):
            out[k] = None
        elif isinstance(v, Decimal):
            f = float(v)
            out[k] = None if not math.isfinite(f) else f
        elif isinstance(v, (datetime, date)):
            out[k] = v.isoformat()
        else:
            out[k] = v
    return out

router = APIRouter(prefix="/products", tags=["Productos"])


@router.get("")
def list_products(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=50, ge=1, le=50000),
    is_active: bool | None = Query(default=None),
    categoria_id: int | None = Query(default=None),
    parent_categoria_id: int | None = Query(default=None),
    marca: str | None = Query(default=None),
    q: str | None = Query(default=None),
    sort: str | None = Query(default=None),
    db: Session = Depends(get_db),
):
    where = []
    params: dict = {}
    if is_active is not None:
        where.append("p.is_active = :is_active")
        params["is_active"] = is_active
    if categoria_id is not None:
        where.append("p.categoria_id = :categoria_id")
        params["categoria_id"] = categoria_id
    if parent_categoria_id is not None:
        where.append("""p.categoria_id IN (
            SELECT id FROM categoria
            WHERE id = :parent_categoria_id
               OR parent_id = :parent_categoria_id
               OR parent_id IN (SELECT id FROM categoria WHERE parent_id = :parent_categoria_id)
        )""")
        params["parent_categoria_id"] = parent_categoria_id
    if marca:
        where.append("UPPER(p.marca) = :marca")
        params["marca"] = marca.upper()
    if q:
        where.append("(p.sku ILIKE :q OR p.name ILIKE :q OR COALESCE(p.marca, '') ILIKE :q OR COALESCE(p.codigo_pos, '') ILIKE :q)")
        params["q"] = f"%{normalize_text(q)}%"

    where_sql = ("WHERE " + " AND ".join(where)) if where else ""
    order_sql = {
        "precio": "ORDER BY COALESCE(p.precio_publico, 0) DESC",
        "nombre": "ORDER BY p.name",
        "stock": "ORDER BY COALESCE(s.stock_fisico, 0) DESC",
    }.get(sort or "", "ORDER BY p.id")

    offset = (page - 1) * page_size
    params["limit"] = page_size
    params["offset"] = offset

    total = db.execute(text(f"""
        SELECT COUNT(*) FROM productos p
        LEFT JOIN v_stock_libros s ON s.sku = p.sku
        {where_sql}
    """), params).scalar()
    rows = db.execute(text(f"""
        SELECT p.id, p.sku, p.codigo_pos, p.codigo_cat, p.marca, p.name, p.categoria_id,
               p.unit, p.min_stock, p.price, p.costo_pos_con_iva, p.precio_publico,
               p.is_active, p.created_at,
               p.aplicacion, p.ubicacion, p.descripcion_larga, p.medida,
               p.anio_inicio, p.anio_fin, p.dim_largo, p.dim_ancho, p.dim_alto, p.equivalencia, p.imagen_url,
               COALESCE(s.stock_fisico, 0) AS stock_fisico,
               COALESCE(s.stock_pos, 0) AS stock_pos
        FROM productos p
        LEFT JOIN v_stock_libros s ON s.sku = p.sku
        {where_sql}
        {order_sql}
        LIMIT :limit OFFSET :offset
    """), params).mappings().all()
    return {"page": page, "page_size": page_size, "total": int(total or 0), "items": [_sanitize(dict(r)) for r in rows]}


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
                   unit, min_stock, price, costo_pos_con_iva, precio_publico, is_active
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


@router.get("/marcas")
def list_marcas(
    categoria_id: int | None = Query(default=None),
    parent_categoria_id: int | None = Query(default=None),
    db: Session = Depends(get_db),
):
    """Distinct brand values for filter dropdowns, optionally scoped to a category."""
    where = ["marca IS NOT NULL AND marca != ''"]
    params: dict = {}
    if categoria_id is not None:
        where.append("categoria_id = :categoria_id")
        params["categoria_id"] = categoria_id
    if parent_categoria_id is not None:
        where.append("""categoria_id IN (
            SELECT id FROM categoria
            WHERE id = :parent_categoria_id
               OR parent_id = :parent_categoria_id
               OR parent_id IN (SELECT id FROM categoria WHERE parent_id = :parent_categoria_id)
        )""")
        params["parent_categoria_id"] = parent_categoria_id
    where_sql = "WHERE " + " AND ".join(where)
    rows = db.execute(text(f"""
        SELECT DISTINCT marca FROM productos
        {where_sql}
        ORDER BY marca
    """), params).scalars().all()
    return rows


@router.get("/{sku}")
def get_product_by_sku(sku: str, db: Session = Depends(get_db)):
    sku = normalize_sku(sku)
    row = db.execute(
        text("""
            SELECT id, sku, codigo_pos, codigo_cat, marca, name, categoria_id,
                   unit, min_stock, price, costo_pos_con_iva, precio_publico, is_active, created_at,
                   aplicacion, ubicacion, descripcion_larga, medida,
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

    costo_pos_con_iva = round(payload.price * 1.16, 4) if payload.price else None

    row = db.execute(
        text("""
            INSERT INTO productos
                (sku, name, codigo_pos, codigo_cat, marca, price, costo_pos_con_iva, precio_publico,
                 categoria_id, unit, min_stock, is_active, aplicacion, ubicacion, descripcion_larga, medida,
                 anio_inicio, anio_fin, dim_largo, dim_ancho, dim_alto, equivalencia, imagen_url)
            VALUES
                (:sku, :name, :codigo_pos, :codigo_cat, :marca, :price, :costo_pos_con_iva, :precio_publico,
                 :categoria_id, :unit, :min_stock, :is_active, :aplicacion, :ubicacion, :descripcion_larga, :medida,
                 :anio_inicio, :anio_fin, :dim_largo, :dim_ancho, :dim_alto, :equivalencia, :imagen_url)
            ON CONFLICT (sku) DO UPDATE
            SET
                name = EXCLUDED.name,
                codigo_pos = EXCLUDED.codigo_pos,
                codigo_cat = EXCLUDED.codigo_cat,
                marca = EXCLUDED.marca,
                price = EXCLUDED.price,
                costo_pos_con_iva = EXCLUDED.costo_pos_con_iva,
                precio_publico = EXCLUDED.precio_publico,
                categoria_id = EXCLUDED.categoria_id,
                unit = EXCLUDED.unit,
                min_stock = EXCLUDED.min_stock,
                is_active = EXCLUDED.is_active,
                aplicacion = EXCLUDED.aplicacion,
                ubicacion = EXCLUDED.ubicacion,
                descripcion_larga = EXCLUDED.descripcion_larga,
                medida = EXCLUDED.medida,
                anio_inicio = EXCLUDED.anio_inicio,
                anio_fin = EXCLUDED.anio_fin,
                dim_largo = EXCLUDED.dim_largo,
                dim_ancho = EXCLUDED.dim_ancho,
                dim_alto = EXCLUDED.dim_alto,
                equivalencia = EXCLUDED.equivalencia,
                imagen_url = EXCLUDED.imagen_url
            RETURNING
                id, sku, name, codigo_pos, codigo_cat, marca, price, costo_pos_con_iva, precio_publico,
                categoria_id, unit, min_stock, is_active, created_at,
                (xmax = 0) AS inserted_flag
        """),
        {
            "sku": sku, "name": name, "codigo_pos": codigo_pos,
            "codigo_cat": codigo_cat, "marca": marca, "price": payload.price,
            "costo_pos_con_iva": costo_pos_con_iva,
            "precio_publico": payload.precio_publico or None,
            "categoria_id": payload.categoria_id, "unit": unit,
            "min_stock": payload.min_stock, "is_active": payload.is_active,
            "aplicacion": payload.aplicacion, "ubicacion": payload.ubicacion,
            "descripcion_larga": payload.descripcion_larga,
            "medida": payload.medida,
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
        "precio_publico": ("precio_publico", lambda v: v if v and v > 0 else None),
        "marca": ("marca", lambda v: normalize_text(v).upper()),
        "aplicacion": ("aplicacion", lambda v: v),
        "ubicacion": ("ubicacion", lambda v: v),
        "descripcion_larga": ("descripcion_larga", lambda v: v),
        "medida": ("medida", lambda v: v),
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

    # Auto-calculate costo_pos_con_iva when price is manually updated
    if payload.price is not None:
        updates.append("costo_pos_con_iva = :costo_pos_con_iva")
        params["costo_pos_con_iva"] = round(payload.price * 1.16, 4)

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


@router.get("/{sku}/margen")
def get_product_margen(sku: str, db: Session = Depends(get_db)):
    sku = normalize_sku(sku)
    row = db.execute(
        text("""
            SELECT
                vm.producto_id, vm.sku, vm.name, vm.marca,
                vm.costo_pos_con_iva, vm.costo_real_sin_iva,
                vm.costo_base, vm.fuente_costo,
                vm.precio_final, vm.porcentaje_margen_objetivo,
                vm.precio_sugerido, vm.costo_real_updated_at,
                vm.utilidad, vm.margen_porcentaje, vm.markup_porcentaje
            FROM v_producto_margen vm
            WHERE UPPER(vm.sku) = :sku
            LIMIT 1
        """),
        {"sku": sku},
    ).mappings().first()
    if not row:
        raise HTTPException(status_code=404, detail=f"SKU no encontrado: {sku}")
    return dict(row)

