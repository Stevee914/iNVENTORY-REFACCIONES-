from fastapi import APIRouter, Depends, UploadFile, File, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import text
from APP.db import get_db
from APP.dbf_reader import read_dbf
from APP.helpers import (
    normalize_sku, normalize_text, normalize_code, normalize_quantity,
    parse_bool, parse_float, build_codigo_pos, ensure_category,
)
import pandas as pd
from io import BytesIO
from datetime import datetime

router = APIRouter(prefix="/import", tags=["Importaciones"])


# =========================
# Validaciones de archivo
# =========================

def _validate_excel(file: UploadFile):
    if not file.filename.lower().endswith((".xlsx", ".xls")):
        raise HTTPException(status_code=400, detail="Solo se aceptan archivos Excel (.xlsx/.xls)")


def _validate_pos_file(file: UploadFile):
    """Valida que el archivo sea .xlsx, .xls o .dbf"""
    if not file.filename.lower().endswith((".xlsx", ".xls", ".dbf")):
        raise HTTPException(
            status_code=400,
            detail="Solo se aceptan archivos .xlsx, .xls o .dbf"
        )


# =========================
# Helper: leer archivo POS (Excel o DBF) → DataFrame normalizado
# =========================

def _read_pos_file(content: bytes, filename: str) -> pd.DataFrame:
    """
    Lee un archivo POS en formato .xlsx/.xls o .dbf y devuelve un
    DataFrame con columnas normalizadas: CODIGO_POS, NAME, STOCK, PRICE.

    Para Excel espera columnas: CÓDIGO, STOCK (y opcionalmente DESCRIPCION, PRECIO).
    Para DBF   espera columnas: CLAVE, ALMACTUAL, DESCRIPCIO, PRECIO1A.
    """
    lower = filename.lower()

    if lower.endswith(".dbf"):
        rows = read_dbf(content)
        if not rows:
            raise HTTPException(status_code=400, detail="El archivo DBF está vacío")

        normalized = []
        for r in rows:
            normalized.append({str(k).strip().upper(): v for k, v in r.items()})

        available = set(normalized[0].keys())
        required_dbf = {"CLAVE", "ALMACTUAL"}
        missing = required_dbf - available
        if missing:
            raise HTTPException(
                status_code=400,
                detail=f"Faltan columnas requeridas en DBF: {sorted(list(missing))}. "
                       f"Columnas encontradas: {sorted(list(available))}"
            )

        mapped = []
        for r in normalized:
            mapped.append({
                "CODIGO_POS": normalize_code(r.get("CLAVE")),
                "NAME": normalize_text(r.get("DESCRIPCIO", "")),
                "STOCK": parse_float(r.get("ALMACTUAL"), 0.0),
                "PRICE": parse_float(r.get("PRECIO1A"), 0.0),
            })
        return pd.DataFrame(mapped)

    elif lower.endswith((".xlsx", ".xls")):
        df = pd.read_excel(BytesIO(content))
        df.columns = [str(c).strip().upper() for c in df.columns]

        required_xls = {"CÓDIGO", "STOCK"}
        missing = required_xls - set(df.columns)
        if missing:
            raise HTTPException(
                status_code=400,
                detail=f"Faltan columnas requeridas: {sorted(list(missing))}"
            )

        result = pd.DataFrame()
        result["CODIGO_POS"] = df["CÓDIGO"].apply(normalize_code)
        result["NAME"] = df.get("DESCRIPCION", pd.Series([""] * len(df))).apply(normalize_text)
        result["STOCK"] = df["STOCK"].apply(lambda v: parse_float(v, 0.0))
        result["PRICE"] = df.get("PRECIO", pd.Series([0.0] * len(df))).apply(lambda v: parse_float(v, 0.0))
        return result

    else:
        raise HTTPException(
            status_code=400,
            detail="Formato no soportado. Se aceptan archivos .xlsx, .xls o .dbf"
        )


# =========================
# Catálogo (solo Excel, sin cambios)
# =========================

@router.post("/catalog")
async def import_catalog(file: UploadFile = File(...), db: Session = Depends(get_db)):
    _validate_excel(file)
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

                codigo_cat = str(raw_codigo_cat).strip().replace(" ", "").replace("-", "")
                try:
                    codigo_cat = str(int(float(codigo_cat))).zfill(4)
                except Exception:
                    codigo_cat = codigo_cat.upper()

                if len(codigo_cat) != 4 or not codigo_cat.isdigit():
                    raise ValueError(f"CODIGO CA inválido (debe ser 4 dígitos): {codigo_cat}")

                codigo_pos = build_codigo_pos(codigo_cat, sku)

                parent_name = (normalize_text(r.get("CATEGORY")).upper() if has_cat else "GENERAL") or "GENERAL"
                child_name = (normalize_text(r.get("SUB CATEGORY")).upper() if has_sub else "GENERAL") or "GENERAL"

                parent_key = (parent_name, None)
                if parent_key not in cat_cache:
                    cat_cache[parent_key] = ensure_category(db, parent_name, None)
                parent_id = cat_cache[parent_key]

                child_key = (child_name, parent_id)
                if child_key not in cat_cache:
                    cat_cache[child_key] = ensure_category(db, child_name, parent_id)
                subcat_id = cat_cache[child_key]

                aplicacion = normalize_text(r.get("APLICACION")) or None if "APLICACION" in df.columns else None
                equivalencia = normalize_text(r.get("EQUIVALENCIA")) or None if "EQUIVALENCIA" in df.columns else None
                ubicacion = normalize_text(r.get("UBICACION")) or None if "UBICACION" in df.columns else None
                imagen_url = normalize_text(r.get("IMAGEN_URL")) or None if "IMAGEN_URL" in df.columns else None

                res = db.execute(
                    text("""
                        INSERT INTO productos
                            (sku, name, categoria_id, unit, min_stock, is_active, price, codigo_cat, codigo_pos, marca,
                             aplicacion, equivalencia, ubicacion, imagen_url)
                        VALUES
                            (:sku, :name, :categoria_id, :unit, :min_stock, :is_active, :price, :codigo_cat, :codigo_pos, :marca,
                             :aplicacion, :equivalencia, :ubicacion, :imagen_url)
                        ON CONFLICT (sku) DO UPDATE SET
                            name = EXCLUDED.name, categoria_id = EXCLUDED.categoria_id,
                            unit = EXCLUDED.unit, min_stock = EXCLUDED.min_stock,
                            is_active = EXCLUDED.is_active, price = EXCLUDED.price,
                            codigo_cat = EXCLUDED.codigo_cat, codigo_pos = EXCLUDED.codigo_pos,
                            marca = EXCLUDED.marca,
                            aplicacion = COALESCE(EXCLUDED.aplicacion, productos.aplicacion),
                            equivalencia = COALESCE(EXCLUDED.equivalencia, productos.equivalencia),
                            ubicacion = COALESCE(EXCLUDED.ubicacion, productos.ubicacion),
                            imagen_url = COALESCE(EXCLUDED.imagen_url, productos.imagen_url)
                        RETURNING (xmax = 0) AS inserted_flag
                    """),
                    {
                        "sku": sku, "name": name, "categoria_id": subcat_id,
                        "unit": unit, "min_stock": min_stock, "is_active": is_active,
                        "price": price, "codigo_cat": codigo_cat, "codigo_pos": codigo_pos,
                        "marca": marca, "aplicacion": aplicacion, "equivalencia": equivalencia,
                        "ubicacion": ubicacion, "imagen_url": imagen_url,
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
        raise HTTPException(status_code=500, detail=f"Error importando catálogo: {str(e)}")

    return {
        "ok": True,
        "products_inserted": inserted,
        "products_updated": updated,
        "errors_count": len(errors),
        "errors_sample": errors[:30],
    }


# =========================
# Stock inicial físico (solo Excel, sin cambios)
# =========================

@router.post("/stock-initial")
async def import_stock_initial(file: UploadFile = File(...), db: Session = Depends(get_db)):
    _validate_excel(file)
    content = await file.read()
    df = pd.read_excel(BytesIO(content), dtype=str)
    df.columns = [str(c).strip().upper() for c in df.columns]

    required = {"SKU", "QUANTITY"}
    missing = required - set(df.columns)
    if missing:
        raise HTTPException(status_code=400, detail=f"Faltan columnas requeridas: {sorted(list(missing))}")

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

                prod = db.execute(
                    text("SELECT id FROM productos WHERE UPPER(sku) = :sku LIMIT 1"),
                    {"sku": sku},
                ).mappings().first()
                if not prod:
                    raise ValueError(f"SKU no existe: {sku}")

                existing = db.execute(
                    text("""
                        SELECT 1 FROM movimientos_inventario
                        WHERE product_id = :pid AND libro = 'FISICO' AND reference = 'STOCK_INICIAL'
                        LIMIT 1
                    """),
                    {"pid": prod["id"]},
                ).scalar()
                if existing:
                    skipped_existing += 1
                    continue

                db.execute(
                    text("""
                        INSERT INTO movimientos_inventario
                            (product_id, libro, movement_type, evento, quantity, reference, notes, movement_date, created_at)
                        VALUES
                            (:pid, 'FISICO', 'ADJUST', 'AJUSTE', :qty, 'STOCK_INICIAL',
                             'Carga inicial de inventario físico', NOW(), NOW())
                    """),
                    {"pid": prod["id"], "qty": qty},
                )
                inserted += 1

            except Exception as e:
                errors.append({"row": int(idx) + 2, "error": str(e)})

        db.commit()
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Error importando stock inicial: {str(e)}")

    return {
        "ok": True,
        "movements_inserted": inserted,
        "rows_skipped_zero": skipped_zero,
        "rows_skipped_existing": skipped_existing,
        "errors_count": len(errors),
        "errors_sample": errors[:30],
    }


# =========================
# POS Stock Initial (Excel + DBF)
# =========================

@router.post("/pos-stock-initial")
async def import_pos_stock_initial(file: UploadFile = File(...), db: Session = Depends(get_db)):
    """
    Carga inicial de stock desde POS.
    Acepta .xlsx, .xls o .dbf.

    DBF: columnas CLAVE, ALMACTUAL, DESCRIPCIO, PRECIO1A
    Excel: columnas CÓDIGO, STOCK (y opcionalmente DESCRIPCION, PRECIO)

    - Si codigo_pos ya existe → solo crea movimiento (no toca catálogo maestro)
    - Si codigo_pos NO existe → crea producto nuevo con datos mínimos
    - Idempotente: no duplica si ya existe movimiento POS_STOCK_INITIAL para ese producto
    """
    _validate_pos_file(file)
    reference = "POS_STOCK_INITIAL_" + datetime.now().strftime("%Y%m%d_%H%M%S")
    fname = file.filename or ""
    content = await file.read()

    try:
        df = _read_pos_file(content, fname)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Error leyendo archivo: {str(e)}")

    created_movements = 0
    skipped_zero = 0
    skipped_existing = 0
    products_created = 0
    errors = []

    for idx, row in df.iterrows():
        try:
            codigo_pos = row["CODIGO_POS"]
            stock = row["STOCK"]
            name = row["NAME"]
            price = row["PRICE"]

            if not codigo_pos:
                continue

            if abs(stock) < 1e-9:
                skipped_zero += 1
                continue

            # Buscar producto por codigo_pos
            product = db.execute(
                text("SELECT id, sku FROM productos WHERE codigo_pos = :cp"),
                {"cp": codigo_pos},
            ).mappings().first()

            # Si no existe → crear producto nuevo con datos mínimos
            if not product:
                gen_sku = f"POS-{codigo_pos}"
                product = db.execute(
                    text("""
                        INSERT INTO productos
                            (sku, name, codigo_pos, unit, min_stock, is_active, price)
                        VALUES
                            (:sku, :name, :codigo_pos, 'PZA', 0, TRUE, :price)
                        ON CONFLICT (sku) DO UPDATE
                        SET codigo_pos = EXCLUDED.codigo_pos
                        RETURNING id, sku
                    """),
                    {
                        "sku": gen_sku,
                        "name": name or gen_sku,
                        "codigo_pos": codigo_pos,
                        "price": price,
                    },
                ).mappings().one()
                db.flush()
                products_created += 1

            product_id = product["id"]

            # Idempotencia: no duplicar
            existing = db.execute(
                text("""
                    SELECT 1 FROM movimientos_inventario
                    WHERE product_id = :pid AND libro = 'FISCAL_POS'
                      AND reference LIKE 'POS_STOCK_INITIAL_%'
                    LIMIT 1
                """),
                {"pid": product_id},
            ).scalar()

            if existing:
                skipped_existing += 1
                continue

            movement_type = "IN" if stock > 0 else "OUT"
            evento = "ENTRADA_MOSTRADOR" if stock > 0 else "VENTA_FACTURADA"
            quantity = normalize_quantity(movement_type, abs(stock))

            db.execute(
                text("""
                    INSERT INTO movimientos_inventario
                        (product_id, libro, movement_type, evento, quantity, reference, notes, movement_date, created_at)
                    VALUES
                        (:pid, 'FISCAL_POS', :mt, :evento, :qty, :ref,
                         'Carga inicial automática desde POS', NOW(), NOW())
                """),
                {
                    "pid": product_id, "mt": movement_type, "evento": evento,
                    "qty": quantity, "ref": reference,
                },
            )
            created_movements += 1

            # Actualizar precio si viene del POS
            if price and price > 0:
                db.execute(
                    text("UPDATE productos SET price = :price WHERE id = :id"),
                    {"price": price, "id": product_id},
                )

        except Exception as e:
            errors.append({"row": int(idx) + 2, "error": str(e)})

    db.commit()
    return {
        "ok": True,
        "file_format": "dbf" if fname.lower().endswith(".dbf") else "excel",
        "reference": reference,
        "movements_created": created_movements,
        "products_created_from_pos": products_created,
        "skipped_zero": skipped_zero,
        "skipped_already_loaded": skipped_existing,
        "errors_count": len(errors),
        "errors_sample": errors[:20],
        "warning": "Endpoint para carga inicial POS. No ejecutar múltiples veces sin limpiar previo.",
    }


# =========================
# POS Stock Sync (Excel + DBF)
# =========================

@router.post("/pos-stock-sync")
async def import_pos_stock_sync(file: UploadFile = File(...), db: Session = Depends(get_db)):
    """
    Sincronización delta de stock POS.
    Acepta .xlsx, .xls o .dbf.

    DBF: columnas CLAVE, ALMACTUAL, DESCRIPCIO, PRECIO1A
    Excel: columnas CÓDIGO, STOCK (y opcionalmente DESCRIPCION, PRECIO)

    - Compara stock del archivo vs stock_pos actual en el sistema
    - Si codigo_pos NO existe → crea producto nuevo con datos mínimos
    - NO modifica name, sku, categoría, unidad, marca del catálogo maestro
    - Actualiza price si viene del archivo
    - Idempotente por diseño (delta = 0 → skip)
    """
    _validate_pos_file(file)
    reference = "POS_STOCK_SYNC_" + datetime.now().strftime("%Y%m%d_%H%M%S")
    fname = file.filename or ""
    content = await file.read()

    try:
        df = _read_pos_file(content, fname)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Error leyendo archivo: {str(e)}")

    adjusted = 0
    skipped = 0
    products_created = 0
    price_updated = 0
    errors = []

    for idx, row in df.iterrows():
        try:
            codigo_pos = row["CODIGO_POS"]
            pos_stock = row["STOCK"]
            name = row["NAME"]
            price = row["PRICE"]

            if not codigo_pos:
                continue

            # Buscar producto por codigo_pos
            product = db.execute(
                text("SELECT id, sku FROM productos WHERE codigo_pos = :cp"),
                {"cp": codigo_pos},
            ).mappings().first()

            # Si no existe → crear producto nuevo con datos mínimos
            if not product:
                gen_sku = f"POS-{codigo_pos}"
                product = db.execute(
                    text("""
                        INSERT INTO productos
                            (sku, name, codigo_pos, unit, min_stock, is_active, price)
                        VALUES
                            (:sku, :name, :codigo_pos, 'PZA', 0, TRUE, :price)
                        ON CONFLICT (sku) DO UPDATE
                        SET codigo_pos = EXCLUDED.codigo_pos
                        RETURNING id, sku
                    """),
                    {
                        "sku": gen_sku,
                        "name": name or gen_sku,
                        "codigo_pos": codigo_pos,
                        "price": price,
                    },
                ).mappings().one()
                db.flush()
                products_created += 1
                sys_stock = 0.0
            else:
                sys_row = db.execute(
                    text("SELECT COALESCE(stock_pos, 0) AS stock_pos FROM v_stock_libros WHERE sku = :sku"),
                    {"sku": product["sku"]},
                ).mappings().first()
                sys_stock = float(sys_row["stock_pos"]) if sys_row else 0.0

            product_id = product["id"]
            diff = pos_stock - sys_stock

            # Actualizar precio si viene valor positivo del POS
            if price and price > 0:
                db.execute(
                    text("UPDATE productos SET price = :price WHERE id = :id"),
                    {"price": price, "id": product_id},
                )
                price_updated += 1

            if abs(diff) < 1e-9:
                skipped += 1
                continue

            movement_type = "IN" if diff > 0 else "OUT"
            evento = "ENTRADA_MOSTRADOR" if diff > 0 else "VENTA_FACTURADA"
            quantity = normalize_quantity(movement_type, abs(diff))

            db.execute(
                text("""
                    INSERT INTO movimientos_inventario
                        (product_id, libro, movement_type, evento, quantity, reference, notes, movement_date, created_at)
                    VALUES
                        (:pid, 'FISCAL_POS', :mt, :evento, :qty, :ref,
                         :notes, NOW(), NOW())
                """),
                {
                    "pid": product_id, "mt": movement_type, "evento": evento,
                    "qty": quantity, "ref": reference,
                    "notes": f"Sync POS delta: pos={pos_stock} sys={sys_stock}",
                },
            )
            adjusted += 1

        except Exception as e:
            errors.append({"row": int(idx) + 2, "error": str(e)})

    db.commit()
    return {
        "ok": True,
        "file_format": "dbf" if fname.lower().endswith(".dbf") else "excel",
        "reference": reference,
        "products_adjusted": adjusted,
        "products_created_from_pos": products_created,
        "prices_updated": price_updated,
        "skipped_no_change": skipped,
        "errors_count": len(errors),
        "errors_sample": errors[:20],
    }
