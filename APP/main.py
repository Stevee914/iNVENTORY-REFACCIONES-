from fastapi import FastAPI, Depends, UploadFile, File, Query, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import text
from APP.db import get_db
import pandas as pd
from io import BytesIO
from datetime import datetime
from typing import Optional
from pydantic import BaseModel

app = FastAPI(title="Inventario Refacciones Prueba", version="0.0.2")


class ProductUpdate(BaseModel):
    name: Optional[str] = None
    categoria_id: Optional[int] = None
    unit: Optional[str] = None
    min_stock: Optional[float] = None
    is_active: Optional[bool] = None
    price: Optional[float] = None
    codigo_cat: Optional[str] = None
    codigo_pos: Optional[str] = None
    marca: Optional[str] = None


# =========================
# Helpers
# =========================

def normalize_quantity(movement_type: str, qty: float) -> float:
    if qty is None:
        raise ValueError("quantity is required")

    mt = movement_type.upper().strip()

    if mt in ("IN", "OUT"):
        if qty <= 0:
            raise ValueError("quantity must be > 0 for IN/OUT")
        return abs(qty) if mt == "IN" else -abs(qty)

    if mt == "ADJUST":
        if qty == 0:
            raise ValueError("quantity cannot be 0 for ADJUST")
        return float(qty)

    raise ValueError(f"Invalid movement_type: {movement_type}")


def normalize_text(value) -> str:
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return ""
    return str(value).strip()


def normalize_code(value) -> str:
    return normalize_text(value).upper().replace(" ", "").replace("-", "")


def normalize_sku(value) -> str:
    return normalize_text(value).upper()


def parse_bool(value, default=True) -> bool:
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return default
    s = str(value).strip().upper()
    if s in ("1", "TRUE", "VERDADERO", "SI", "SÍ", "YES", "Y"):
        return True
    if s in ("0", "FALSE", "FALSO", "NO", "N"):
        return False
    return default


def parse_float(value, default=0.0) -> float:
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return default
    s = str(value).replace("$", "").replace(",", "").strip()
    if s == "" or s.lower() == "nan":
        return default
    return float(s)


def map_libro(value) -> str:
    libro_in = normalize_text(value).upper() or "FISICO"
    map_libro_values = {
        "FISICO": "FISICO",
        "FISCAL_POS": "FISCAL_POS",
        "POS": "FISCAL_POS",
        "FISCAL": "FISCAL_POS",
    }
    if libro_in not in map_libro_values:
        raise HTTPException(status_code=400, detail="libro debe ser FISICO o FISCAL_POS (alias: POS)")
    return map_libro_values[libro_in]


def build_codigo_pos(codigo_cat: str, sku: str) -> str:
    cat = normalize_code(codigo_cat)
    if len(cat) != 4 or not cat.isdigit():
        raise ValueError(f"codigo_cat inválido: {codigo_cat}")
    return cat + normalize_code(sku)


def ensure_category(db: Session, name: str, parent_id: int | None) -> int:
    row = db.execute(
        text(
            """
            SELECT id
            FROM categoria
            WHERE name = :name
              AND ((:parent_id IS NULL AND parent_id IS NULL) OR parent_id = :parent_id)
            LIMIT 1
            """
        ),
        {"name": name, "parent_id": parent_id},
    ).mappings().first()

    if row:
        return int(row["id"])

    new_id = db.execute(
        text(
            """
            INSERT INTO categoria (name, parent_id)
            VALUES (:name, :parent_id)
            RETURNING id
            """
        ),
        {"name": name, "parent_id": parent_id},
    ).scalar()

    return int(new_id)


# =========================
# Base endpoints
# =========================

@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/db-check")
def db_check(db: Session = Depends(get_db)):
    result = db.execute(text("SELECT 1")).scalar()
    return {"database": "connected", "test_query": result}


# =========================
# Products
# =========================

@app.get("/products")
def list_products(db: Session = Depends(get_db)):
    rows = db.execute(text("""
        SELECT id, sku, codigo_pos, codigo_cat, marca, name, categoria_id, unit, min_stock, price, is_active, created_at
        FROM productos
        ORDER BY id
    """)).mappings().all()
    return rows


@app.get("/products/search")
def search_products(
    q: str = Query(..., min_length=1),
    limit: int = Query(default=20, ge=1, le=100),
    db: Session = Depends(get_db),
):
    q = normalize_text(q)
    rows = db.execute(
        text("""
            SELECT id, sku, codigo_pos, codigo_cat, marca, name, categoria_id, unit, min_stock, price, is_active
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


@app.post("/products")
def create_product(payload: dict, db: Session = Depends(get_db)):
    required = ["sku", "name"]
    for k in required:
        if k not in payload or not normalize_text(payload[k]):
            raise HTTPException(status_code=400, detail=f"Falta campo obligatorio: {k}")

    sku = normalize_sku(payload["sku"])
    name = normalize_text(payload["name"])
    codigo_cat = normalize_code(payload.get("codigo_cat")) or None
    marca = normalize_text(payload.get("marca")) or None
    categoria_id = payload.get("categoria_id", None)
    unit = str(payload.get("unit", "PZA")).strip().upper()

    if unit in ("PIEZA", "PZA"):
        unit = "PZA"
    elif unit == "PAR":
        unit = "PAR"
    elif unit == "JUEGO":
        unit = "JGO"
    elif unit == "KIT":
        unit = "KIT"

    min_stock = parse_float(payload.get("min_stock"), 0.0)
    price = parse_float(payload.get("price"), 0.0)

    is_active = payload.get("is_active", True)
    if isinstance(is_active, str):
        is_active = is_active.strip().upper() in ("1", "TRUE", "VERDADERO", "SI", "SÍ", "YES", "Y")
    else:
        is_active = bool(is_active)


    codigo_pos = normalize_code(payload.get("codigo_pos")) or None
    if not codigo_pos and codigo_cat:
        codigo_pos = build_codigo_pos(codigo_cat, sku)

    row = db.execute(
        text("""
            INSERT INTO productos
                (sku, name, codigo_pos, codigo_cat, marca, price, categoria_id, unit, min_stock, is_active)
            VALUES
                (:sku, :name, :codigo_pos, :codigo_cat, :marca, :price, :categoria_id, :unit, :min_stock, :is_active)
            ON CONFLICT (sku) DO UPDATE
            SET
                name        = EXCLUDED.name,
                codigo_pos  = EXCLUDED.codigo_pos,
                codigo_cat  = EXCLUDED.codigo_cat,
                marca       = EXCLUDED.marca,
                price       = EXCLUDED.price,
                categoria_id= EXCLUDED.categoria_id,
                unit        = EXCLUDED.unit,
                min_stock   = EXCLUDED.min_stock,
                is_active   = EXCLUDED.is_active
            RETURNING
                id, sku, name, codigo_pos, codigo_cat, marca, price,
                categoria_id, unit, min_stock, is_active, created_at,
                (xmax = 0) AS inserted_flag
        """),
        {
            "sku": sku,
            "name": name,
            "codigo_pos": codigo_pos,
            "codigo_cat": codigo_cat,
            "marca": marca,
            "price": price,
            "categoria_id": categoria_id,
            "unit": unit,
            "min_stock": min_stock,
            "is_active": is_active,
        },
    ).mappings().one()
    db.commit()
    action = "inserted" if row["inserted_flag"] else "updated"

    return {
        "ok": True,
        "action": action,
        "product": {
            "id": row["id"],
            "sku": row["sku"],
            "name": row["name"],
            "codigo_pos": row["codigo_pos"],
            "codigo_cat": row["codigo_cat"],
            "marca": row["marca"],
            "price": row["price"],
            "categoria_id": row["categoria_id"],
            "unit": row["unit"],
            "min_stock": row["min_stock"],
            "is_active": row["is_active"],
            "created_at": row["created_at"],
        }
    }
@app.post("/movements")
def create_movement(payload: dict, db: Session = Depends(get_db)):
    required = ["sku", "movement_type", "quantity"]
    for k in required:
        if k not in payload:
            raise HTTPException(status_code=400, detail=f"Falta campo obligatorio: {k}")

    sku = normalize_sku(payload["sku"])
    movement_type = normalize_text(payload["movement_type"]).upper()
    reference = normalize_text(payload.get("reference")) or None
    notes = normalize_text(payload.get("notes")) or None
    libro = map_libro(payload.get("libro", "FISICO"))

    if movement_type not in ("IN", "OUT", "ADJUST"):
        raise HTTPException(status_code=400, detail="movement_type debe ser IN, OUT o ADJUST")

    try:
        quantity = float(payload["quantity"])
    except Exception:
        raise HTTPException(status_code=400, detail="quantity debe ser numérico")

    try:
        quantity = normalize_quantity(movement_type, quantity)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    product = db.execute(
        text("SELECT id FROM productos WHERE UPPER(sku) = :sku"),
        {"sku": sku},
    ).mappings().first()

    if not product:
        raise HTTPException(status_code=404, detail=f"SKU no existe: {sku}")

    try:
        row = db.execute(
            text("""
                INSERT INTO movimientos_inventario
                    (product_id, libro, movement_type, quantity, reference, notes, movement_date, created_at)
                VALUES
                    (:product_id, :libro, :movement_type, :quantity, :reference, :notes, NOW(), NOW())
                RETURNING id, product_id, libro, movement_type, quantity, movement_date, reference, notes
            """),
            {
                "product_id": product["id"],
                "libro": libro,
                "movement_type": movement_type,
                "quantity": quantity,
                "reference": reference,
                "notes": notes,
            },
        ).mappings().one()
        db.commit()
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Error insertando movimiento: {str(e)}")

    return {"ok": True, "movement": row}


@app.get("/kardex/{sku}")
def kardex_by_sku(
    sku: str,
    limit: int = Query(default=100, ge=1, le=500),
    db: Session = Depends(get_db),
):
    sku = normalize_sku(sku)
    rows = db.execute(
        text("""
            SELECT
                mi.id,
                p.sku,
                mi.libro,
                mi.movement_type,
                mi.quantity,
                mi.reference,
                mi.notes,
                mi.movement_date,
                mi.created_at
            FROM movimientos_inventario mi
            JOIN productos p ON p.id = mi.product_id
            WHERE p.sku = :sku
            ORDER BY mi.movement_date DESC, mi.id DESC
            LIMIT :limit
        """),
        {"sku": sku, "limit": limit},
    ).mappings().all()
    return {"sku": sku, "items": rows, "count": len(rows)}


# =========================
# Stock
# =========================

@app.get("/stock")
def list_stock(
    db: Session = Depends(get_db),
    q: str | None = Query(default=None, description="Buscar por SKU o nombre"),
    only_negative: bool = Query(default=False, description="Solo productos con stock físico < 0"),
    below_min_stock: bool = Query(default=False, description="Solo productos con stock físico < min_stock"),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=50, ge=1, le=200),
):
    where = []
    params: dict = {}

    if q:
        where.append("(sku ILIKE :q OR name ILIKE :q OR COALESCE(marca, '') ILIKE :q OR COALESCE(codigo_pos, '') ILIKE :q)")
        params["q"] = f"%{normalize_text(q)}%"

    if only_negative:
        where.append("stock_fisico < 0")

    if below_min_stock:
        where.append("stock_fisico < COALESCE(min_stock, 0)")

    where_sql = ("WHERE " + " AND ".join(where)) if where else ""

    offset = (page - 1) * page_size
    params["limit"] = page_size
    params["offset"] = offset

    total = db.execute(
        text(f"SELECT COUNT(*) FROM v_stock_libros {where_sql}"),
        params,
    ).scalar()

    items = db.execute(
        text(f"""
            SELECT
                product_id,
                sku,
                name,
                min_stock,
                stock_fisico,
                stock_pos,
                stock_total
            FROM v_stock_libros
            {where_sql}
            ORDER BY sku
            LIMIT :limit OFFSET :offset
        """),
        params,
    ).mappings().all()

    return {
        "page": page,
        "page_size": page_size,
        "total": int(total or 0),
        "items": items,
    }


@app.get("/stock/{sku}")
def stock_by_sku(sku: str, db: Session = Depends(get_db)):
    row = db.execute(
        text("""
            SELECT product_id, sku, name, min_stock, stock_fisico, stock_pos, stock_total
            FROM v_stock_libros
            WHERE sku = :sku
        """),
        {"sku": normalize_sku(sku)},
    ).mappings().first()

    if not row:
        raise HTTPException(status_code=404, detail="SKU no encontrado")

    return row


# =========================
# Imports
# =========================

@app.post("/import/catalog")
async def import_catalog(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
):
    if not file.filename.lower().endswith((".xlsx", ".xls")):
        raise HTTPException(status_code=400, detail="Solo se aceptan archivos Excel (.xlsx/.xls)")

    content = await file.read()
    df = pd.read_excel(BytesIO(content))
    df.columns = [str(c).strip().upper() for c in df.columns]

    required = {"SKU", "NAME", "CODIGO CA"}
    missing = required - set(df.columns)
    if missing:
        raise HTTPException(status_code=400, detail=f"Faltan columnas requeridas: {sorted(list(missing))}")

    has_cat = "CATEGORY" in df.columns
    has_sub = "SUB CATEGORY" in df.columns

    inserted = 0
    updated = 0
    errors = []
    cat_cache: dict[tuple[str, int | None], int] = {}

    try:
        for idx, r in df.iterrows():
            try:
                sku = normalize_sku(r.get("SKU"))
                name = normalize_text(r.get("NAME"))
                raw_codigo_cat = normalize_code(r.get("CODIGO CA"))
                marca = normalize_text(r.get("MARCA")) or None
                unit = normalize_text(r.get("UNIT")) or "pieza"
                min_stock = parse_float(r.get("MIN STOCK"), 0.0) if "MIN STOCK" in df.columns else 0.0
                is_active = parse_bool(r.get("IS ACTIVE"), True) if "IS ACTIVE" in df.columns else True
                price = parse_float(r.get("PRICE"), 0.0) if "PRICE" in df.columns else 0.0

                if not sku:
                    raise ValueError("SKU vacío")
                if not name:
                    raise ValueError("NAME vacío")
                raw_codigo_cat = r.get("CODIGO CA")

                if raw_codigo_cat is None or (isinstance(raw_codigo_cat, float) and pd.isna(raw_codigo_cat)):
                    raise ValueError("CODIGO CA vacío")

                # Primero limpiamos
                codigo_cat = str(raw_codigo_cat).strip().replace(" ", "").replace("-", "")

                # Si viene como 4.0 por Excel/pandas, lo convertimos a 4
                try:
                    codigo_cat_num = int(float(codigo_cat))
                    codigo_cat = str(codigo_cat_num).zfill(4)
                except Exception:
                    # si no se puede convertir, intentamos usarlo directo
                    codigo_cat = codigo_cat.upper()

                if len(codigo_cat) != 4 or not codigo_cat.isdigit():
                    raise ValueError(f"CODIGO CA inválido (debe ser 4 dígitos): {codigo_cat}")
                codigo_pos = build_codigo_pos(codigo_cat, sku)

                parent_name = normalize_text(r.get("CATEGORY")).upper() if has_cat else "GENERAL"
                child_name = normalize_text(r.get("SUB CATEGORY")).upper() if has_sub else "GENERAL"
                parent_name = parent_name or "GENERAL"
                child_name = child_name or "GENERAL"

                parent_key = (parent_name, None)
                if parent_key in cat_cache:
                    parent_id = cat_cache[parent_key]
                else:
                    parent_id = ensure_category(db, parent_name, None)
                    cat_cache[parent_key] = parent_id

                child_key = (child_name, parent_id)
                if child_key in cat_cache:
                    subcat_id = cat_cache[child_key]
                else:
                    subcat_id = ensure_category(db, child_name, parent_id)
                    cat_cache[child_key] = subcat_id

                res = db.execute(
                    text("""
                        INSERT INTO productos
                            (sku, name, categoria_id, unit, min_stock, is_active, price, codigo_cat, codigo_pos, marca)
                        VALUES
                            (:sku, :name, :categoria_id, :unit, :min_stock, :is_active, :price, :codigo_cat, :codigo_pos, :marca)
                        ON CONFLICT (sku) DO UPDATE
                        SET
                            name        = EXCLUDED.name,
                            categoria_id= EXCLUDED.categoria_id,
                            unit        = EXCLUDED.unit,
                            min_stock   = EXCLUDED.min_stock,
                            is_active   = EXCLUDED.is_active,
                            price       = EXCLUDED.price,
                            codigo_cat  = EXCLUDED.codigo_cat,
                            codigo_pos  = EXCLUDED.codigo_pos,
                            marca       = EXCLUDED.marca
                        RETURNING (xmax = 0) AS inserted_flag;
                    """),
                    {
                        "sku": sku,
                        "name": name,
                        "categoria_id": subcat_id,
                        "unit": unit,
                        "min_stock": min_stock,
                        "is_active": is_active,
                        "price": price,
                        "codigo_cat": codigo_cat,
                        "codigo_pos": codigo_pos,
                        "marca": marca,
                    },
                ).mappings().one()

                if res["inserted_flag"]:
                    inserted += 1
                else:
                    updated += 1

            except Exception as e:
                errors.append({"row": int(idx) + 2, "error": str(e)})

        db.commit()
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Error general importando catálogo: {str(e)}")

    return {
        "ok": True,
        "products_inserted": inserted,
        "products_updated": updated,
        "errors_count": len(errors),
        "errors_sample": errors[:30],
    }


@app.post("/import/stock-initial")
async def import_stock_initial(
    file: UploadFile = File(...),
    db: Session = Depends(get_db)
):
    if not file.filename.lower().endswith((".xlsx", ".xls")):
        raise HTTPException(
            status_code=400,
            detail="Solo se aceptan archivos Excel (.xlsx/.xls)"
        )

    content = await file.read()
    df = pd.read_excel(BytesIO(content), dtype=str)
    df.columns = [str(c).strip().upper() for c in df.columns]

    required = {"SKU", "QUANTITY"}
    missing = required - set(df.columns)
    if missing:
        raise HTTPException(
            status_code=400,
            detail=f"Faltan columnas requeridas: {sorted(list(missing))}"
        )

    inserted = 0
    skipped_zero = 0
    skipped_existing = 0
    errors = []

    try:
        for idx, r in df.iterrows():
            try:
                sku = str(r.get("SKU", "")).strip().upper()
                raw_qty = r.get("QUANTITY", None)

                if not sku:
                    raise ValueError("SKU vacío")

                if raw_qty is None or str(raw_qty).strip() == "":
                    skipped_zero += 1
                    continue

                qty = float(str(raw_qty).replace(",", "").strip())

                if qty == 0:
                    skipped_zero += 1
                    continue

                # Buscar producto
                prod = db.execute(
                    text("""
                        SELECT id
                        FROM productos
                        WHERE UPPER(sku) = :sku
                        LIMIT 1
                    """),
                    {"sku": sku}
                ).mappings().first()

                if not prod:
                    raise ValueError(f"SKU no existe en productos: {sku}")

                product_id = prod["id"]

                # Protección: si ya existe STOCK_INICIAL para ese SKU en FISICO, no duplicar
                existing = db.execute(
                    text("""
                        SELECT 1
                        FROM movimientos_inventario
                        WHERE product_id = :product_id
                          AND libro = 'FISICO'
                          AND reference = 'STOCK_INICIAL'
                        LIMIT 1
                    """),
                    {"product_id": product_id}
                ).scalar()

                if existing:
                    skipped_existing += 1
                    continue

                # Insertar movimiento inicial
                db.execute(
                    text("""
                        INSERT INTO movimientos_inventario
                            (product_id, libro, movement_type, quantity, reference, notes, movement_date, created_at)
                        VALUES
                            (:product_id, :libro, :movement_type, :quantity, :reference, :notes, NOW(), NOW())
                    """),
                    {
                        "product_id": product_id,
                        "libro": "FISICO",
                        "movement_type": "ADJUST",
                        "quantity": qty,
                        "reference": "STOCK_INICIAL",
                        "notes": "Carga inicial de inventario físico"
                    }
                )

                inserted += 1

            except Exception as e:
                errors.append({
                    "row": int(idx) + 2,
                    "error": str(e)
                })

        db.commit()

    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=500,
            detail=f"Error general importando stock inicial: {str(e)}"
        )

    return {
        "ok": True,
        "movements_inserted": inserted,
        "rows_skipped_zero": skipped_zero,
        "rows_skipped_existing": skipped_existing,
        "errors_count": len(errors),
        "errors_sample": errors[:30]
    }


@app.get("/products/count")
def products_count(db: Session = Depends(get_db)):
    n = db.execute(text("SELECT COUNT(*) FROM productos")).scalar()
    return {"count": int(n)}


@app.post("/import/pos-stock-initial")
async def import_pos_stock_initial(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
):
    reference = "POS_STOCK_INITIAL_" + datetime.now().strftime("%Y%m%d_%H%M%S")

    if not file.filename.lower().endswith((".xlsx", ".xls")):
        raise HTTPException(status_code=400, detail="Solo se aceptan archivos Excel (.xlsx/.xls)")

    content = await file.read()
    df = pd.read_excel(BytesIO(content))
    df.columns = [str(c).strip().upper() for c in df.columns]

    required = {"CÓDIGO", "STOCK"}
    missing = required - set(df.columns)
    if missing:
        raise HTTPException(status_code=400, detail=f"Faltan columnas requeridas: {sorted(list(missing))}")

    created_movements = 0
    skipped_zero = 0
    not_found = []
    errors = []

    for idx, row in df.iterrows():
        try:
            codigo_pos = normalize_code(row.get("CÓDIGO"))
            stock = parse_float(row.get("STOCK"), 0.0)

            if not codigo_pos:
                raise ValueError("CÓDIGO vacío")

            if abs(stock) < 1e-9:
                skipped_zero += 1
                continue

            product = db.execute(
                text("SELECT id, sku FROM productos WHERE codigo_pos = :codigo_pos"),
                {"codigo_pos": codigo_pos},
            ).mappings().first()

            if not product:
                not_found.append({"row": int(idx) + 2, "codigo_pos": codigo_pos, "error": "codigo_pos no existe en productos"})
                continue

            movement_type = "IN" if stock > 0 else "OUT"
            quantity = normalize_quantity(movement_type, abs(stock))

            db.execute(
                text("""
                    INSERT INTO movimientos_inventario
                        (product_id, libro, movement_type, quantity, reference, notes, movement_date, created_at)
                    VALUES
                        (:product_id, 'FISCAL_POS', :movement_type, :quantity, :reference, :notes, NOW(), NOW())
                """),
                {
                    "product_id": product["id"],
                    "movement_type": movement_type,
                    "quantity": quantity,
                    "reference": reference,
                    "notes": "Carga inicial automática desde POS (snapshot)",
                },
            )
            created_movements += 1

        except Exception as e:
            errors.append({"row": int(idx) + 2, "error": str(e)})

    db.commit()

    return {
        "ok": True,
        "reference_generated": reference,
        "movements_created": created_movements,
        "skipped_zero_stock": skipped_zero,
        "not_found_count": len(not_found),
        "not_found_sample": not_found[:20],
        "errors_count": len(errors),
        "errors_sample": errors[:20],
        "warning": "Este endpoint es para carga inicial POS (libro FISCAL_POS). No debe ejecutarse múltiples veces sin limpiar el snapshot previo.",
    }


@app.post("/import/pos-stock-sync")
async def import_pos_stock_sync(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
):
    reference = "POS_STOCK_SYNC_" + datetime.now().strftime("%Y%m%d_%H%M%S")

    if not file.filename.lower().endswith((".xlsx", ".xls")):
        raise HTTPException(status_code=400, detail="Solo se aceptan archivos Excel (.xlsx/.xls)")

    content = await file.read()
    df = pd.read_excel(BytesIO(content))
    df.columns = [str(c).strip().upper() for c in df.columns]

    required = {"CÓDIGO", "STOCK"}
    missing = required - set(df.columns)
    if missing:
        raise HTTPException(status_code=400, detail=f"Faltan columnas requeridas: {sorted(list(missing))}")

    adjusted = 0
    skipped = 0
    not_found = []
    errors = []

    for idx, row in df.iterrows():
        try:
            codigo_pos = normalize_code(row.get("CÓDIGO"))
            pos_stock = parse_float(row.get("STOCK"), 0.0)

            if not codigo_pos:
                raise ValueError("CÓDIGO vacío")

            product = db.execute(
                text("SELECT id, sku FROM productos WHERE codigo_pos = :codigo_pos"),
                {"codigo_pos": codigo_pos},
            ).mappings().first()

            if not product:
                not_found.append({"row": int(idx) + 2, "codigo_pos": codigo_pos, "error": "codigo_pos no existe en productos"})
                continue

            sys_row = db.execute(
                text("""
                    SELECT COALESCE(stock_pos, 0) AS stock_pos
                    FROM v_stock_libros
                    WHERE sku = :sku
                """),
                {"sku": product["sku"]},
            ).mappings().first()

            sys_stock_pos = float(sys_row["stock_pos"]) if sys_row else 0.0
            diff = pos_stock - sys_stock_pos

            if abs(diff) < 1e-9:
                skipped += 1
                continue

            movement_type = "IN" if diff > 0 else "OUT"
            quantity = normalize_quantity(movement_type, abs(diff))

            db.execute(
                text("""
                    INSERT INTO movimientos_inventario
                        (product_id, libro, movement_type, quantity, reference, notes, movement_date, created_at)
                    VALUES
                        (:product_id, 'FISCAL_POS', :movement_type, :quantity, :reference, :notes, NOW(), NOW())
                """),
                {
                    "product_id": product["id"],
                    "movement_type": movement_type,
                    "quantity": quantity,
                    "reference": reference,
                    "notes": f"Sync POS delta: pos={pos_stock} sys_pos={sys_stock_pos}",
                },
            )
            adjusted += 1

        except Exception as e:
            errors.append({"row": int(idx) + 2, "error": str(e)})

    db.commit()

    return {
        "ok": True,
        "reference_generated": reference,
        "products_adjusted": adjusted,
        "skipped_no_change": skipped,
        "not_found_count": len(not_found),
        "not_found_sample": not_found[:20],
        "errors_count": len(errors),
        "errors_sample": errors[:20],
    }


@app.patch("/products/{sku}")
def update_product(
    sku: str,
    payload: ProductUpdate,
    db: Session = Depends(get_db)
):
    sku = str(sku).strip().upper()

    # verificar que exista
    existing = db.execute(
        text("""
            SELECT id
            FROM productos
            WHERE UPPER(sku) = :sku
            LIMIT 1
        """),
        {"sku": sku}
    ).mappings().first()

    if not existing:
        raise HTTPException(status_code=404, detail=f"SKU no existe: {sku}")

    updates = []
    params = {"sku": sku}

    if payload.name is not None:
        updates.append("name = :name")
        params["name"] = str(payload.name).strip()

    if payload.categoria_id is not None:
        updates.append("categoria_id = :categoria_id")
        params["categoria_id"] = payload.categoria_id

    if payload.unit is not None:
        unit = str(payload.unit).strip().upper()
        if unit in ("PIEZA", "PZA"):
            unit = "PZA"
        elif unit == "PAR":
            unit = "PAR"
        elif unit in ("JUEGO", "JGO"):
            unit = "JGO"
        elif unit == "KIT":
            unit = "KIT"
        updates.append("unit = :unit")
        params["unit"] = unit

    if payload.min_stock is not None:
        updates.append("min_stock = :min_stock")
        params["min_stock"] = payload.min_stock

    if payload.is_active is not None:
        is_active = payload.is_active
        if isinstance(is_active, str):
            is_active = is_active.strip().upper() in (
                "1", "TRUE", "VERDADERO", "SI", "SÍ", "YES", "Y"
            )
        else:
            is_active = bool(is_active)

        updates.append("is_active = :is_active")
        params["is_active"] = is_active

    if payload.price is not None:
        updates.append("price = :price")
        params["price"] = payload.price

    if payload.codigo_cat is not None:
        codigo_cat = str(payload.codigo_cat).strip().replace(" ", "").replace("-", "")
        try:
            codigo_cat = str(int(float(codigo_cat))).zfill(4)
        except Exception:
            raise HTTPException(status_code=400, detail=f"CODIGO CAT inválido: {payload.codigo_cat}")

        if len(codigo_cat) != 4 or not codigo_cat.isdigit():
            raise HTTPException(status_code=400, detail=f"CODIGO CAT inválido: {payload.codigo_cat}")

        updates.append("codigo_cat = :codigo_cat")
        params["codigo_cat"] = codigo_cat

    if payload.codigo_pos is not None:
        codigo_pos = str(payload.codigo_pos).strip().upper().replace(" ", "").replace("-", "")
        updates.append("codigo_pos = :codigo_pos")
        params["codigo_pos"] = codigo_pos

    if payload.marca is not None:
        updates.append("marca = :marca")
        params["marca"] = str(payload.marca).strip().upper()

    # si no mandaron nada
    if not updates:
        raise HTTPException(status_code=400, detail="No se enviaron campos para actualizar")

    # si cambió codigo_cat pero no codigo_pos, recalcular codigo_pos
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
            RETURNING
                id, sku, codigo_pos, codigo_cat, marca, name,
                categoria_id, unit, min_stock, price, is_active, created_at
        """),
        params
    ).mappings().one()

    db.commit()

    return {"ok": True, "product": row}