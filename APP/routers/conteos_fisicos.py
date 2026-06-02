from fastapi import APIRouter, Query, HTTPException
from pydantic import BaseModel
from sqlalchemy import text
from typing import Optional
from APP.db import engine

router = APIRouter(prefix="/conteos-fisicos", tags=["conteos_fisicos"])


# ── Schemas ───────────────────────────────────────────────────────────────────

class ConteoCreate(BaseModel):
    nombre: str
    categoria_id: Optional[int] = None
    modo_captura: str = "REEMPLAZAR"
    notas: Optional[str] = None


class ConteoPatch(BaseModel):
    nombre: Optional[str] = None
    modo_captura: Optional[str] = None
    notas: Optional[str] = None


class ScanPayload(BaseModel):
    barcode: str
    product_id: Optional[int] = None
    cantidad: float
    modo: str = "REEMPLAZAR"   # REEMPLAZAR | SUMAR


# ── Helpers ───────────────────────────────────────────────────────────────────

def _get_conteo_or_404(conn, conteo_id: int):
    row = conn.execute(text(
        "SELECT id, nombre, categoria_id, categoria_nombre, estatus, modo_captura, notas, created_at, aplicado_at "
        "FROM conteos_fisicos WHERE id = :id"
    ), {"id": conteo_id}).fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="Conteo no encontrado")
    return row


# ── List sessions ─────────────────────────────────────────────────────────────

@router.get("")
def list_conteos(limit: int = 50):
    with engine.connect() as conn:
        rows = conn.execute(text("""
            SELECT cf.id, cf.nombre, cf.categoria_id, cf.categoria_nombre,
                   cf.estatus, cf.modo_captura, cf.notas, cf.created_at, cf.aplicado_at,
                   COUNT(d.id)                                           AS lineas_count,
                   COALESCE(SUM(CASE
                       WHEN d.cantidad_contada != COALESCE(d.stock_fisico_snapshot, 0) THEN 1
                       ELSE 0 END), 0)                                   AS con_diferencia
            FROM conteos_fisicos cf
            LEFT JOIN conteos_fisicos_detalle d ON d.conteo_id = cf.id
            GROUP BY cf.id
            ORDER BY cf.created_at DESC
            LIMIT :lim
        """), {"lim": limit}).fetchall()
        return [dict(r._mapping) for r in rows]


# ── Create session ────────────────────────────────────────────────────────────

@router.post("", status_code=201)
def create_conteo(body: ConteoCreate):
    with engine.begin() as conn:
        cat_nombre = None
        if body.categoria_id:
            r = conn.execute(text(
                "SELECT name FROM categoria WHERE id = :id"
            ), {"id": body.categoria_id}).fetchone()
            if r:
                cat_nombre = r[0]

        row = conn.execute(text("""
            INSERT INTO conteos_fisicos (nombre, categoria_id, categoria_nombre, modo_captura, notas)
            VALUES (:nombre, :cat_id, :cat_nombre, :modo, :notas)
            RETURNING id, nombre, categoria_id, categoria_nombre, estatus, modo_captura, notas, created_at, aplicado_at
        """), {
            "nombre": body.nombre.strip(),
            "cat_id": body.categoria_id,
            "cat_nombre": cat_nombre,
            "modo": body.modo_captura,
            "notas": body.notas,
        }).fetchone()
        result = dict(row._mapping)
        result["lineas_count"] = 0
        result["con_diferencia"] = 0
        return result


# ── Preload products (fast, called once per session) ──────────────────────────
# NOTE: this route MUST be defined before /{conteo_id} to avoid matching conflicts.

@router.get("/preload-products")
def preload_products(categoria_id: int = Query(...)):
    with engine.connect() as conn:
        rows = conn.execute(text("""
            WITH RECURSIVE cat_tree AS (
                SELECT id FROM categoria WHERE id = :cat_id
                UNION ALL
                SELECT c.id FROM categoria c
                JOIN cat_tree ct ON c.parent_id = ct.id
            )
            SELECT
                p.id            AS product_id,
                p.sku,
                p.codigo_pos,
                p.name,
                p.marca,
                p.categoria_id,
                cat.name        AS categoria,
                p.imagen_url,
                p.ubicacion,
                p.aplicacion,
                COALESCE(vs.stock_fisico, 0) AS stock_fisico,
                COALESCE(vs.stock_pos,   0) AS stock_pos
            FROM productos p
            LEFT JOIN categoria cat ON cat.id = p.categoria_id
            LEFT JOIN v_stock_libros vs ON vs.product_id = p.id
            WHERE p.is_active = true
              AND p.catalog_visible = true
              AND p.categoria_id IN (SELECT id FROM cat_tree)
            ORDER BY p.sku
        """), {"cat_id": categoria_id}).fetchall()
        return [dict(r._mapping) for r in rows]


# ── Fallback barcode lookup ───────────────────────────────────────────────────

@router.get("/lookup")
def lookup_barcode(barcode: str = Query(...)):
    cleaned = barcode.strip().upper().replace("-", "")
    with engine.connect() as conn:
        row = conn.execute(text("""
            SELECT
                p.id AS product_id, p.sku, p.codigo_pos, p.name, p.marca,
                p.categoria_id, c.name AS categoria,
                p.imagen_url, p.ubicacion, p.aplicacion,
                COALESCE(vs.stock_fisico, 0) AS stock_fisico,
                COALESCE(vs.stock_pos,   0) AS stock_pos
            FROM productos p
            LEFT JOIN categoria c ON c.id = p.categoria_id
            LEFT JOIN v_stock_libros vs ON vs.product_id = p.id
            WHERE p.is_active = true
              AND (
                UPPER(REPLACE(p.sku,                          '-', '')) = :bc
                OR UPPER(REPLACE(COALESCE(p.codigo_pos, ''), '-', '')) = :bc
              )
            LIMIT 1
        """), {"bc": cleaned}).fetchone()
        if not row:
            raise HTTPException(status_code=404, detail=f"No encontrado: {barcode}")
        return dict(row._mapping)


# ── Get session ───────────────────────────────────────────────────────────────

@router.get("/{conteo_id}")
def get_conteo(conteo_id: int):
    with engine.connect() as conn:
        cf = _get_conteo_or_404(conn, conteo_id)
        stats = conn.execute(text("""
            SELECT COUNT(*),
                   COALESCE(SUM(CASE
                       WHEN cantidad_contada != COALESCE(stock_fisico_snapshot, 0) THEN 1
                       ELSE 0 END), 0)
            FROM conteos_fisicos_detalle WHERE conteo_id = :id
        """), {"id": conteo_id}).fetchone()
        result = dict(cf._mapping)
        result["lineas_count"] = stats[0]
        result["con_diferencia"] = stats[1]
        return result


# ── Patch session ─────────────────────────────────────────────────────────────

@router.patch("/{conteo_id}")
def patch_conteo(conteo_id: int, body: ConteoPatch):
    with engine.begin() as conn:
        _get_conteo_or_404(conn, conteo_id)
        updates = {}
        if body.nombre is not None:
            updates["nombre"] = body.nombre.strip()
        if body.modo_captura is not None:
            updates["modo_captura"] = body.modo_captura
        if body.notas is not None:
            updates["notas"] = body.notas
        if not updates:
            return {"ok": True}
        set_clause = ", ".join(f"{k} = :{k}" for k in updates)
        updates["id"] = conteo_id
        conn.execute(text(f"UPDATE conteos_fisicos SET {set_clause} WHERE id = :id"), updates)
        return {"ok": True}


# ── Save scan ─────────────────────────────────────────────────────────────────

@router.post("/{conteo_id}/scan")
def save_scan(conteo_id: int, body: ScanPayload):
    with engine.begin() as conn:
        cf = _get_conteo_or_404(conn, conteo_id)
        if cf.estatus == "APLICADO":
            raise HTTPException(status_code=400, detail="Conteo ya fue aplicado")

        # Resolve product
        if body.product_id is not None:
            prod = conn.execute(text(
                "SELECT id, sku FROM productos WHERE id = :id AND is_active = true"
            ), {"id": body.product_id}).fetchone()
            if not prod:
                raise HTTPException(status_code=404, detail="Producto no encontrado")
            product_id = prod[0]
        else:
            cleaned = body.barcode.strip().upper().replace("-", "")
            prod = conn.execute(text("""
                SELECT id, sku FROM productos
                WHERE is_active = true AND (
                    UPPER(REPLACE(sku, '-', '')) = :bc
                    OR UPPER(REPLACE(COALESCE(codigo_pos, ''), '-', '')) = :bc
                )
                LIMIT 1
            """), {"bc": cleaned}).fetchone()
            if not prod:
                raise HTTPException(status_code=404, detail=f"Producto no encontrado: {body.barcode}")
            product_id = prod[0]

        # Existing line?
        existing = conn.execute(text("""
            SELECT id, stock_fisico_snapshot, stock_pos_snapshot, cantidad_contada, veces_escaneado
            FROM conteos_fisicos_detalle
            WHERE conteo_id = :cid AND product_id = :pid
        """), {"cid": conteo_id, "pid": product_id}).fetchone()

        if existing:
            nueva_qty = (
                existing.cantidad_contada + body.cantidad
                if body.modo == "SUMAR"
                else body.cantidad
            )
            conn.execute(text("""
                UPDATE conteos_fisicos_detalle
                SET cantidad_contada = :qty,
                    veces_escaneado  = veces_escaneado + 1,
                    updated_at       = NOW()
                WHERE id = :id
            """), {"qty": nueva_qty, "id": existing.id})
        else:
            # First scan — capture stock snapshot
            snap = conn.execute(text(
                "SELECT COALESCE(stock_fisico,0), COALESCE(stock_pos,0) "
                "FROM v_stock_libros WHERE product_id = :pid"
            ), {"pid": product_id}).fetchone()
            sf = snap[0] if snap else 0
            sp = snap[1] if snap else 0

            conn.execute(text("""
                INSERT INTO conteos_fisicos_detalle
                    (conteo_id, product_id, sku, stock_fisico_snapshot, stock_pos_snapshot,
                     cantidad_contada, veces_escaneado)
                VALUES
                    (:cid, :pid,
                     (SELECT sku FROM productos WHERE id = :pid),
                     :sf, :sp, :qty, 1)
            """), {"cid": conteo_id, "pid": product_id, "sf": sf, "sp": sp, "qty": body.cantidad})

        # Return updated line
        row = conn.execute(text("""
            SELECT d.id, d.conteo_id, d.product_id, d.sku,
                   p.name, p.marca, p.codigo_pos, p.imagen_url,
                   d.stock_fisico_snapshot, d.stock_pos_snapshot,
                   d.cantidad_contada, d.veces_escaneado, d.notas, d.updated_at,
                   (d.cantidad_contada - COALESCE(d.stock_fisico_snapshot, 0)) AS diferencia
            FROM conteos_fisicos_detalle d
            JOIN productos p ON p.id = d.product_id
            WHERE d.conteo_id = :cid AND d.product_id = :pid
        """), {"cid": conteo_id, "pid": product_id}).fetchone()
        return dict(row._mapping)


# ── Review detail ─────────────────────────────────────────────────────────────

@router.get("/{conteo_id}/detalle")
def get_detalle(conteo_id: int, solo_diferencias: bool = False):
    with engine.connect() as conn:
        _get_conteo_or_404(conn, conteo_id)
        base = """
            SELECT d.id, d.product_id, d.sku,
                   p.name, p.marca, p.codigo_pos, p.categoria_id,
                   c.name AS categoria,
                   d.stock_fisico_snapshot, d.stock_pos_snapshot,
                   d.cantidad_contada, d.veces_escaneado, d.notas, d.updated_at,
                   (d.cantidad_contada - COALESCE(d.stock_fisico_snapshot, 0)) AS diferencia
            FROM conteos_fisicos_detalle d
            JOIN productos p ON p.id = d.product_id
            LEFT JOIN categoria c ON c.id = p.categoria_id
            WHERE d.conteo_id = :cid
        """
        if solo_diferencias:
            base += " AND d.cantidad_contada != COALESCE(d.stock_fisico_snapshot, 0)"
        base += " ORDER BY ABS(d.cantidad_contada - COALESCE(d.stock_fisico_snapshot,0)) DESC, d.updated_at DESC"
        rows = conn.execute(text(base), {"cid": conteo_id}).fetchall()
        return [dict(r._mapping) for r in rows]


# ── Apply adjustments ─────────────────────────────────────────────────────────

@router.post("/{conteo_id}/aplicar")
def aplicar_conteo(conteo_id: int):
    with engine.begin() as conn:
        cf = _get_conteo_or_404(conn, conteo_id)
        if cf.estatus == "APLICADO":
            raise HTTPException(status_code=400, detail="Conteo ya fue aplicado")

        rows = conn.execute(text("""
            SELECT product_id, cantidad_contada, stock_fisico_snapshot
            FROM conteos_fisicos_detalle
            WHERE conteo_id = :cid
              AND cantidad_contada != COALESCE(stock_fisico_snapshot, 0)
        """), {"cid": conteo_id}).fetchall()

        ajustes = 0
        for row in rows:
            diferencia = float(row.cantidad_contada) - float(row.stock_fisico_snapshot or 0)
            conn.execute(text("""
                INSERT INTO movimientos_inventario
                    (product_id, libro, movement_type, quantity, evento, notes, movement_date)
                VALUES
                    (:pid, 'FISICO', 'ADJUST', :qty, 'AJUSTE',
                     :notes, NOW())
            """), {
                "pid": row.product_id,
                "qty": diferencia,
                "notes": f"Conteo físico #{conteo_id}",
            })
            ajustes += 1

        conn.execute(text(
            "UPDATE conteos_fisicos SET estatus = 'APLICADO', aplicado_at = NOW() WHERE id = :id"
        ), {"id": conteo_id})

        return {"ok": True, "ajustes_creados": ajustes}


# ── Faltantes preview ─────────────────────────────────────────────────────────

@router.get("/{conteo_id}/faltantes-preview")
def faltantes_preview(conteo_id: int):
    with engine.connect() as conn:
        _get_conteo_or_404(conn, conteo_id)

        rows = conn.execute(text("""
            SELECT
                d.id                        AS detalle_id,
                d.product_id,
                d.sku,
                p.name                      AS product_name,
                c.name                      AS categoria,
                d.cantidad_contada,
                COALESCE(d.stock_fisico_snapshot, 0) AS stock_sistema_snapshot,
                COALESCE(p.min_stock, 0)    AS min_stock,
                GREATEST(COALESCE(p.min_stock, 0) - d.cantidad_contada, 0) AS cantidad_faltante,
                pp.proveedor_id,
                pr.nombre                   AS proveedor_nombre,
                CASE WHEN f.id IS NOT NULL THEN true ELSE false END AS already_has_pending,
                f.id                        AS existing_faltante_id
            FROM conteos_fisicos_detalle d
            JOIN productos p ON p.id = d.product_id AND p.is_active = true
            LEFT JOIN categoria c ON c.id = p.categoria_id
            LEFT JOIN producto_proveedor pp ON pp.product_id = p.id AND pp.is_primary = true
            LEFT JOIN proveedores pr ON pr.id = pp.proveedor_id
            LEFT JOIN faltantes f
                ON f.product_id = d.product_id
               AND f.status = 'pendiente'
               AND f.id = (
                   SELECT id FROM faltantes
                   WHERE product_id = d.product_id AND status = 'pendiente'
                   ORDER BY id DESC LIMIT 1
               )
            WHERE d.conteo_id = :cid
              AND COALESCE(p.min_stock, 0) > 0
              AND GREATEST(COALESCE(p.min_stock, 0) - d.cantidad_contada, 0) > 0
            ORDER BY cantidad_faltante DESC
        """), {"cid": conteo_id}).fetchall()

        return [dict(r._mapping) for r in rows]


# ── Generar faltantes ─────────────────────────────────────────────────────────

class GenerarFaltantesPayload(BaseModel):
    mode: str = "SKIP_EXISTING"   # SKIP_EXISTING only in v1


@router.post("/{conteo_id}/generar-faltantes")
def generar_faltantes(conteo_id: int, body: GenerarFaltantesPayload):
    with engine.begin() as conn:
        cf = _get_conteo_or_404(conn, conteo_id)

        rows = conn.execute(text("""
            SELECT
                d.id                        AS detalle_id,
                d.product_id,
                d.sku,
                p.name                      AS product_name,
                d.cantidad_contada,
                COALESCE(p.min_stock, 0)    AS min_stock,
                GREATEST(COALESCE(p.min_stock, 0) - d.cantidad_contada, 0) AS cantidad_faltante,
                pp.proveedor_id
            FROM conteos_fisicos_detalle d
            JOIN productos p ON p.id = d.product_id AND p.is_active = true
            LEFT JOIN producto_proveedor pp ON pp.product_id = p.id AND pp.is_primary = true
            WHERE d.conteo_id = :cid
              AND COALESCE(p.min_stock, 0) > 0
              AND GREATEST(COALESCE(p.min_stock, 0) - d.cantidad_contada, 0) > 0
        """), {"cid": conteo_id}).fetchall()

        creados = 0
        omitidos_existente = 0
        omitidos_duplicado = 0

        for row in rows:
            # Skip if product already has a pending faltante
            pending = conn.execute(text(
                "SELECT id FROM faltantes WHERE product_id = :pid AND status = 'pendiente' LIMIT 1"
            ), {"pid": row.product_id}).fetchone()

            if pending:
                omitidos_existente += 1
                continue

            comentario = (
                f"Generado desde conteo físico: {cf.nombre} | "
                f"contado={float(row.cantidad_contada):.0f} | "
                f"min={float(row.min_stock):.0f}"
            )

            try:
                conn.execute(text("""
                    INSERT INTO faltantes
                        (product_id, cantidad_faltante, comentario, status,
                         origen, origen_id, origen_detalle_id)
                    VALUES
                        (:pid, :qty, :com, 'pendiente',
                         'CONTEO_FISICO', :conteo_id, :detalle_id)
                    ON CONFLICT (origen_detalle_id) WHERE origen_detalle_id IS NOT NULL
                    DO NOTHING
                """), {
                    "pid":        row.product_id,
                    "qty":        float(row.cantidad_faltante),
                    "com":        comentario,
                    "conteo_id":  conteo_id,
                    "detalle_id": row.detalle_id,
                })
                # Check if actually inserted
                affected = conn.execute(text(
                    "SELECT id FROM faltantes WHERE origen_detalle_id = :did"
                ), {"did": row.detalle_id}).fetchone()
                if affected:
                    creados += 1
                else:
                    omitidos_duplicado += 1
            except Exception:
                omitidos_duplicado += 1

        return {
            "ok": True,
            "creados": creados,
            "omitidos_existente": omitidos_existente,
            "omitidos_duplicado": omitidos_duplicado,
        }
