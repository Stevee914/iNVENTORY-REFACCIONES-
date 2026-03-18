from fastapi import APIRouter, Depends, UploadFile, File, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import text
from APP.db import get_db
from APP.helpers import (
    normalize_sku, normalize_text, normalize_code, normalize_quantity,
    parse_bool, parse_float, build_codigo_pos, ensure_category,
)
import pandas as pd
from io import BytesIO
from datetime import datetime

router = APIRouter(prefix="/import", tags=["Importaciones"])


def _validate_excel(file: UploadFile):
    if not file.filename.lower().endswith((".xlsx", ".xls")):
        raise HTTPException(status_code=400, detail="Solo se aceptan archivos Excel (.xlsx/.xls)")


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


@router.post("/pos-stock-initial")
async def import_pos_stock_initial(file: UploadFile = File(...), db: Session = Depends(get_db)):
    _validate_excel(file)
    reference = "POS_STOCK_INITIAL_" + datetime.now().strftime("%Y%m%d_%H%M%S")
    content = await file.read()
    df = pd.read_excel(BytesIO(content))
    df.columns = [str(c).strip().upper() for c in df.columns]

    required = {"CÓDIGO", "STOCK"}
    missing = required - set(df.columns)
    if missing:
        raise HTTPException(status_code=400, detail=f"Faltan columnas requeridas: {sorted(list(missing))}")

    created = 0
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
                text("SELECT id, sku FROM productos WHERE codigo_pos = :cp"),
                {"cp": codigo_pos},
            ).mappings().first()
            if not product:
                not_found.append({"row": int(idx) + 2, "codigo_pos": codigo_pos, "error": "codigo_pos no existe"})
                continue

            movement_type = "IN" if stock > 0 else "OUT"
            evento = "ENTRADA_FACTURA" if stock > 0 else "VENTA_FACTURADA"
            quantity = normalize_quantity(movement_type, abs(stock))

            # POS initial no requiere proveedor en ENTRADA, pero el constraint sí lo pide para ENTRADA_FACTURA
            # Usamos ENTRADA_MOSTRADOR para evitar el constraint
            if evento == "ENTRADA_FACTURA":
                evento = "ENTRADA_MOSTRADOR"

            db.execute(
                text("""
                    INSERT INTO movimientos_inventario
                        (product_id, libro, movement_type, evento, quantity, reference, notes, movement_date, created_at)
                    VALUES
                        (:pid, 'FISCAL_POS', :mt, :evento, :qty, :ref,
                         'Carga inicial automática desde POS', NOW(), NOW())
                """),
                {
                    "pid": product["id"], "mt": movement_type, "evento": evento,
                    "qty": quantity, "ref": reference,
                },
            )
            created += 1

        except Exception as e:
            errors.append({"row": int(idx) + 2, "error": str(e)})

    db.commit()
    return {
        "ok": True,
        "reference": reference,
        "movements_created": created,
        "skipped_zero": skipped_zero,
        "not_found_count": len(not_found),
        "not_found_sample": not_found[:20],
        "errors_count": len(errors),
        "errors_sample": errors[:20],
        "warning": "Endpoint para carga inicial POS. No ejecutar múltiples veces sin limpiar previo.",
    }


@router.post("/pos-stock-sync")
async def import_pos_stock_sync(file: UploadFile = File(...), db: Session = Depends(get_db)):
    _validate_excel(file)
    reference = "POS_STOCK_SYNC_" + datetime.now().strftime("%Y%m%d_%H%M%S")
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
                text("SELECT id, sku FROM productos WHERE codigo_pos = :cp"),
                {"cp": codigo_pos},
            ).mappings().first()
            if not product:
                not_found.append({"row": int(idx) + 2, "codigo_pos": codigo_pos, "error": "codigo_pos no existe"})
                continue

            sys_row = db.execute(
                text("SELECT COALESCE(stock_pos, 0) AS stock_pos FROM v_stock_libros WHERE sku = :sku"),
                {"sku": product["sku"]},
            ).mappings().first()

            sys_stock = float(sys_row["stock_pos"]) if sys_row else 0.0
            diff = pos_stock - sys_stock
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
                    "pid": product["id"], "mt": movement_type, "evento": evento,
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
        "reference": reference,
        "products_adjusted": adjusted,
        "skipped_no_change": skipped,
        "not_found_count": len(not_found),
        "not_found_sample": not_found[:20],
        "errors_count": len(errors),
        "errors_sample": errors[:20],
    }
