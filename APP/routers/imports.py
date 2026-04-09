from fastapi import APIRouter, Depends, UploadFile, File, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import text
from APP.db import get_db
from APP.helpers import (
    normalize_sku, normalize_text, normalize_code,
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

    # ── Column aliases ────────────────────────────────────────────────────────
    if "NOMBRE_LIMPIO" in df.columns and "NAME" not in df.columns:
        df.rename(columns={"NOMBRE_LIMPIO": "NAME"}, inplace=True)

    # ── Required column validation ────────────────────────────────────────────
    missing: set[str] = set()
    if "SKU" not in df.columns:
        missing.add("SKU")
    if "NAME" not in df.columns:
        missing.add("NAME o NOMBRE_LIMPIO")
    if "CODIGO CA" not in df.columns and "CODIGO_POS" not in df.columns:
        missing.add("CODIGO CA o CODIGO_POS")
    if missing:
        raise HTTPException(status_code=400, detail=f"Faltan columnas requeridas: {sorted(list(missing))}")

    has_cat         = "CATEGORY" in df.columns
    has_sub         = "SUB CATEGORY" in df.columns
    has_codigo_pos  = "CODIGO_POS" in df.columns
    has_medida      = "MEDIDA" in df.columns
    has_specs       = "MODELO_SPECS" in df.columns

    inserted = 0
    updated  = 0
    errors: list[dict] = []
    cat_cache: dict[tuple[str, int | None], int] = {}

    try:
        for idx, r in df.iterrows():
            try:
                sku  = normalize_sku(r.get("SKU"))
                name = normalize_text(r.get("NAME"))
                if not sku:
                    raise ValueError("SKU vacío")
                if not name:
                    raise ValueError("NAME vacío")

                marca     = normalize_text(r.get("MARCA")).upper() or None if normalize_text(r.get("MARCA")) else None
                unit      = normalize_text(r.get("UNIT")) or "PZA"
                min_stock = parse_float(r.get("MIN STOCK"), 0.0)  if "MIN STOCK"  in df.columns else 0.0
                is_active = parse_bool(r.get("IS ACTIVE"), True)  if "IS ACTIVE"  in df.columns else True
                price     = parse_float(r.get("PRICE"), 0.0)      if "PRICE"      in df.columns else 0.0
                medida    = normalize_text(r.get("MEDIDA"))        or None         if has_medida  else None
                desc_larga = normalize_text(r.get("MODELO_SPECS")) or None         if has_specs   else None

                # ── codigo_pos / codigo_cat resolution ────────────────────────
                raw_cpos = normalize_code(r.get("CODIGO_POS")) if has_codigo_pos else None

                if raw_cpos:
                    codigo_pos = raw_cpos
                    # Extract codigo_cat from first 4 digits if possible
                    if len(codigo_pos) >= 4 and codigo_pos[:4].isdigit():
                        codigo_cat = codigo_pos[:4]
                    else:
                        raw_cc = r.get("CODIGO CA")
                        if raw_cc is not None and not (isinstance(raw_cc, float) and pd.isna(raw_cc)):
                            cc = str(raw_cc).strip().replace(" ", "").replace("-", "")
                            try:
                                cc = str(int(float(cc))).zfill(4)
                            except Exception:
                                cc = cc.upper()
                            codigo_cat = cc if len(cc) == 4 and cc.isdigit() else None
                        else:
                            codigo_cat = None
                else:
                    # Original flow: CODIGO CA required
                    raw_cc = r.get("CODIGO CA")
                    if raw_cc is None or (isinstance(raw_cc, float) and pd.isna(raw_cc)):
                        raise ValueError("Se requiere CODIGO CA o CODIGO_POS")
                    codigo_cat = str(raw_cc).strip().replace(" ", "").replace("-", "")
                    try:
                        codigo_cat = str(int(float(codigo_cat))).zfill(4)
                    except Exception:
                        codigo_cat = codigo_cat.upper()
                    if len(codigo_cat) != 4 or not codigo_cat.isdigit():
                        raise ValueError(f"CODIGO CA inválido (debe ser 4 dígitos): '{codigo_cat}'")
                    codigo_pos = build_codigo_pos(codigo_cat, sku)

                # ── Category resolution (unchanged) ───────────────────────────
                parent_name = (normalize_text(r.get("CATEGORY")).upper() if has_cat else "GENERAL") or "GENERAL"
                child_name  = (normalize_text(r.get("SUB CATEGORY")).upper() if has_sub else "GENERAL") or "GENERAL"

                parent_key = (parent_name, None)
                if parent_key not in cat_cache:
                    cat_cache[parent_key] = ensure_category(db, parent_name, None)
                parent_id = cat_cache[parent_key]

                child_key = (child_name, parent_id)
                if child_key not in cat_cache:
                    cat_cache[child_key] = ensure_category(db, child_name, parent_id)
                subcat_id = cat_cache[child_key]

                aplicacion   = normalize_text(r.get("APLICACION"))  or None if "APLICACION"  in df.columns else None
                equivalencia = normalize_text(r.get("EQUIVALENCIA")) or None if "EQUIVALENCIA" in df.columns else None
                ubicacion    = normalize_text(r.get("UBICACION"))    or None if "UBICACION"    in df.columns else None
                imagen_url   = normalize_text(r.get("IMAGEN_URL"))   or None if "IMAGEN_URL"   in df.columns else None

                res = db.execute(
                    text("""
                        INSERT INTO productos
                            (sku, name, categoria_id, unit, min_stock, is_active, price,
                             codigo_cat, codigo_pos, marca,
                             aplicacion, equivalencia, ubicacion, imagen_url,
                             medida, descripcion_larga)
                        VALUES
                            (:sku, :name, :categoria_id, :unit, :min_stock, :is_active, :price,
                             :codigo_cat, :codigo_pos, :marca,
                             :aplicacion, :equivalencia, :ubicacion, :imagen_url,
                             :medida, :descripcion_larga)
                        ON CONFLICT (sku) DO UPDATE SET
                            name              = EXCLUDED.name,
                            categoria_id      = EXCLUDED.categoria_id,
                            unit              = EXCLUDED.unit,
                            min_stock         = EXCLUDED.min_stock,
                            is_active         = EXCLUDED.is_active,
                            price             = EXCLUDED.price,
                            codigo_cat        = EXCLUDED.codigo_cat,
                            codigo_pos        = EXCLUDED.codigo_pos,
                            marca             = EXCLUDED.marca,
                            aplicacion        = COALESCE(EXCLUDED.aplicacion,    productos.aplicacion),
                            equivalencia      = COALESCE(EXCLUDED.equivalencia,  productos.equivalencia),
                            ubicacion         = COALESCE(EXCLUDED.ubicacion,     productos.ubicacion),
                            imagen_url        = COALESCE(EXCLUDED.imagen_url,    productos.imagen_url),
                            medida            = COALESCE(EXCLUDED.medida,        productos.medida),
                            descripcion_larga = COALESCE(EXCLUDED.descripcion_larga, productos.descripcion_larga)
                        RETURNING (xmax = 0) AS inserted_flag
                    """),
                    {
                        "sku": sku, "name": name, "categoria_id": subcat_id,
                        "unit": unit, "min_stock": min_stock, "is_active": is_active,
                        "price": price, "codigo_cat": codigo_cat, "codigo_pos": codigo_pos,
                        "marca": marca, "aplicacion": aplicacion, "equivalencia": equivalencia,
                        "ubicacion": ubicacion, "imagen_url": imagen_url,
                        "medida": medida, "descripcion_larga": desc_larga,
                    },
                ).mappings().one()

                if res["inserted_flag"]:
                    inserted += 1
                else:
                    updated += 1

            except Exception as e:
                errors.append({"row": int(idx) + 2, "sku": str(r.get("SKU", "")), "error": str(e)})

        db.commit()
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Error importando catálogo: {str(e)}")

    return {
        "ok": True,
        "products_inserted": inserted,
        "products_updated":  updated,
        "errors_count":      len(errors),
        "errors_sample":     errors[:30],
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


@router.post("/pos-sync")
async def import_pos_sync(file: UploadFile = File(...), db: Session = Depends(get_db)):
    """
    Sincronización unificada de stock POS desde archivo Excel del POS.

    Columnas requeridas: CLAVE, DESCRIPCIO, ALMACTUAL, PRECIO1A

    - Producto existente (match por codigo_pos): genera un movimiento ADJUST en FISCAL_POS
      para igualar stock al valor de ALMACTUAL. Sin cambio → skip.
    - Producto nuevo: crea el producto derivando sku/codigo_cat de CLAVE,
      y crea movimiento inicial si ALMACTUAL != 0.
    - Idempotente por diseño: misma carga dos veces → delta = 0 → sin movimientos duplicados.
    - Optimizado para volúmenes grandes: usa bulk queries en lugar de N+1.
    """
    _validate_excel(file)
    reference = "POS_SYNC_" + datetime.now().strftime("%Y%m%d_%H%M%S")
    content = await file.read()

    try:
        df = pd.read_excel(BytesIO(content))
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Error leyendo archivo Excel: {str(e)}")

    df.columns = [str(c).strip().upper() for c in df.columns]

    required = {"CLAVE", "DESCRIPCIO", "ALMACTUAL"}
    missing = required - set(df.columns)
    if missing:
        raise HTTPException(
            status_code=400,
            detail=f"Faltan columnas requeridas: {sorted(list(missing))}. "
                   f"Columnas encontradas: {sorted(list(df.columns))}",
        )

    # COSTO_CON_ = POS cost with VAT → costo_pos_con_iva (preferred)
    # PRECIO1A   = public sale price  → ignored here (managed manually)
    _costo_col = "COSTO_CON_" if "COSTO_CON_" in df.columns else None

    # ── Paso 1: parsear y validar todas las filas del archivo ───────
    rows_parsed: list[dict] = []
    errors: list[dict] = []

    for idx, row in df.iterrows():
        try:
            codigo_pos = normalize_code(row.get("CLAVE"))
            if not codigo_pos:
                continue
            if len(codigo_pos) < 5:
                raise ValueError(
                    f"CLAVE muy corta (mín. 5 chars para extraer codigo_cat+sku): '{codigo_pos}'"
                )
            costo_con_iva = parse_float(row.get(_costo_col), 0.0) if _costo_col else 0.0
            rows_parsed.append({
                "idx": int(idx) + 2,
                "codigo_pos": codigo_pos,
                "almactual": parse_float(row.get("ALMACTUAL"), 0.0),
                "nombre": normalize_text(row.get("DESCRIPCIO")) or codigo_pos,
                "costo_con_iva": costo_con_iva,          # COSTO_CON_ = cost with VAT
                "costo_sin_iva": round(costo_con_iva / 1.16, 4) if costo_con_iva > 0 else 0.0,
            })
        except Exception as e:
            errors.append({"row": int(idx) + 2, "clave": str(row.get("CLAVE", "")), "error": str(e)})

    total_rows_read = len(df)
    total_valid_rows = len(rows_parsed)

    if not rows_parsed:
        db.commit()
        return {
            "ok": True, "reference": reference,
            "total_rows_read": total_rows_read, "total_valid_rows": 0,
            "existing_updated": 0, "existing_no_change": 0,
            "new_products_created": 0, "skipped_zero_stock_new": 0,
            "errors_count": len(errors), "errors_sample": errors[:20],
            "new_codigos_pos": [],
        }

    all_codigos = [r["codigo_pos"] for r in rows_parsed]

    # ── Paso 2: una sola query para traer todos los productos existentes ─
    existing_rows = db.execute(
        text("""
            SELECT p.id, p.sku, p.codigo_pos, COALESCE(v.stock_pos, 0) AS stock_pos
            FROM productos p
            LEFT JOIN v_stock_libros v ON v.sku = p.sku
            WHERE p.codigo_pos = ANY(:codigos)
        """),
        {"codigos": all_codigos},
    ).mappings().all()

    # codigo_pos → {id, sku, stock_pos}
    existing_map: dict[str, dict] = {r["codigo_pos"]: dict(r) for r in existing_rows}

    # ── Paso 2b: pre-cargar skus derivados que ya existen en DB ────────
    # Esto permite detectar conflictos de sku ANTES de intentar el INSERT,
    # sin usar ON CONFLICT DO UPDATE como fallback de match.
    candidate_skus = []
    for r in rows_parsed:
        cp = r["codigo_pos"]
        if cp not in existing_map and len(cp) >= 5:
            candidate_skus.append(cp[4:])  # sku derivado = CLAVE[4:]

    sku_conflicts: set[str] = set()
    if candidate_skus:
        conflict_rows = db.execute(
            text("SELECT sku FROM productos WHERE sku = ANY(:skus)"),
            {"skus": candidate_skus},
        ).mappings().all()
        sku_conflicts = {r["sku"] for r in conflict_rows}

    # ── Paso 3: procesar cada fila en memoria ───────────────────────
    existing_updated = 0
    existing_no_change = 0
    new_products_created = 0
    skipped_zero_stock_new = 0
    new_codigos_pos: list[str] = []
    sku_conflict_rows: list[dict] = []

    movements_to_insert: list[dict] = []
    costo_pos_updates:   list[dict] = []   # existing products whose cost needs updating

    for r in rows_parsed:
        codigo_pos = r["codigo_pos"]
        almactual = r["almactual"]

        try:
            if codigo_pos in existing_map:
                # ── Producto existente: ajustar stock + actualizar costo POS ──
                prod = existing_map[codigo_pos]
                sys_stock = float(prod["stock_pos"])
                diff = almactual - sys_stock

                if abs(diff) >= 1e-9:
                    movements_to_insert.append({
                        "pid": prod["id"],
                        "libro": "FISCAL_POS",
                        "mt": "ADJUST",
                        "evento": "AJUSTE",
                        "qty": diff,
                        "ref": reference,
                        "notes": f"Sync POS: pos={almactual} sys={sys_stock}",
                    })
                    existing_updated += 1
                else:
                    existing_no_change += 1

                # Always update cost for existing products (PRECIO1A may change)
                if r["costo_con_iva"] > 0:
                    costo_pos_updates.append({"pid": prod["id"], "costo": r["costo_con_iva"]})

            else:
                # ── Producto nuevo ──────────────────────────────────
                codigo_cat = codigo_pos[:4]
                sku = codigo_pos[4:]

                if not codigo_cat.isdigit():
                    raise ValueError(
                        f"Los primeros 4 caracteres de CLAVE deben ser dígitos "
                        f"(codigo_cat): '{codigo_cat}' en '{codigo_pos}'"
                    )

                # Si el sku derivado ya existe en otro producto → conflicto, no tocar
                if sku in sku_conflicts:
                    sku_conflict_rows.append({
                        "row": r["idx"],
                        "clave": codigo_pos,
                        "sku_derivado": sku,
                        "error": (
                            f"El SKU derivado '{sku}' ya existe en el catálogo con un "
                            f"codigo_pos diferente. Revisar manualmente."
                        ),
                    })
                    continue

                try:
                    with db.begin_nested():
                        new_product = db.execute(
                            text("""
                                INSERT INTO productos
                                    (sku, name, codigo_pos, codigo_cat, unit, min_stock, is_active,
                                     price, costo_pos_con_iva)
                                VALUES
                                    (:sku, :name, :codigo_pos, :codigo_cat, 'PZA', 0, TRUE,
                                     :price, :costo_pos)
                                RETURNING id, sku
                            """),
                            {
                                "sku": sku, "name": r["nombre"],
                                "codigo_pos": codigo_pos, "codigo_cat": codigo_cat,
                                "price":      r["costo_sin_iva"] if r["costo_sin_iva"] > 0 else None,
                                "costo_pos":  r["costo_con_iva"] if r["costo_con_iva"] > 0 else None,
                            },
                        ).mappings().one()
                except Exception as insert_err:
                    errors.append({"row": r["idx"], "clave": codigo_pos, "error": str(insert_err)})
                    continue

                new_products_created += 1
                new_codigos_pos.append(codigo_pos)

                if abs(almactual) < 1e-9:
                    skipped_zero_stock_new += 1
                    continue

                movements_to_insert.append({
                    "pid": new_product["id"],
                    "libro": "FISCAL_POS",
                    "mt": "ADJUST",
                    "evento": "AJUSTE",
                    "qty": almactual,
                    "ref": reference,
                    "notes": "Stock inicial desde sincronización POS",
                })

        except Exception as e:
            errors.append({"row": r["idx"], "clave": codigo_pos, "error": str(e)})

    # ── Paso 4a: actualizar costo_pos_con_iva en bulk (productos existentes) ──
    if costo_pos_updates:
        db.execute(
            text("""
                UPDATE productos p
                SET
                    costo_pos_con_iva = u.costo::numeric,
                    precio_sugerido = CASE
                        WHEN p.porcentaje_margen_objetivo IS NOT NULL
                        THEN ROUND(
                            COALESCE(p.costo_real_sin_iva, u.costo::numeric / 1.16)
                            * (1 + p.porcentaje_margen_objetivo / 100),
                            2
                        )
                        ELSE p.precio_sugerido
                    END
                FROM unnest(
                    CAST(:pids   AS int[]),
                    CAST(:costos AS float[])
                ) AS u(pid, costo)
                WHERE p.id = u.pid
            """),
            {
                "pids":   [m["pid"]   for m in costo_pos_updates],
                "costos": [m["costo"] for m in costo_pos_updates],
            },
        )

    # ── Paso 4b: insertar todos los movimientos en bulk ──────────────
    if movements_to_insert:
        db.execute(
            text("""
                INSERT INTO movimientos_inventario
                    (product_id, libro, movement_type, evento, quantity,
                     reference, notes, movement_date, created_at)
                SELECT
                    m.pid,
                    CAST(m.libro AS inv_libro),
                    m.mt,
                    CAST(m.evento AS inv_evento),
                    m.qty,
                    m.ref, m.notes, NOW(), NOW()
                FROM unnest(
                    CAST(:pids AS int[]),
                    CAST(:libros AS text[]),
                    CAST(:mts AS text[]),
                    CAST(:eventos AS text[]),
                    CAST(:qtys AS float[]),
                    CAST(:refs AS text[]),
                    CAST(:notes_arr AS text[])
                ) AS m(pid, libro, mt, evento, qty, ref, notes)
            """),
            {
                "pids":      [m["pid"]    for m in movements_to_insert],
                "libros":    [m["libro"]  for m in movements_to_insert],
                "mts":       [m["mt"]     for m in movements_to_insert],
                "eventos":   [m["evento"] for m in movements_to_insert],
                "qtys":      [m["qty"]    for m in movements_to_insert],
                "refs":      [m["ref"]    for m in movements_to_insert],
                "notes_arr": [m["notes"]  for m in movements_to_insert],
            },
        )

    db.commit()
    return {
        "ok": True,
        "reference": reference,
        "total_rows_read": total_rows_read,
        "total_valid_rows": total_valid_rows,
        "existing_updated": existing_updated,
        "existing_no_change": existing_no_change,
        "new_products_created": new_products_created,
        "skipped_zero_stock_new": skipped_zero_stock_new,
        "sku_conflicts_count": len(sku_conflict_rows),
        "sku_conflicts": sku_conflict_rows,
        "errors_count": len(errors),
        "errors_sample": errors[:20],
        "new_codigos_pos": new_codigos_pos[:50],
    }


