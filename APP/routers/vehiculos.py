from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from sqlalchemy import text
from APP.db import get_db

router = APIRouter(prefix="/vehiculos", tags=["Vehículos"])


# ─────────────────────────────────────────────────────────────────────────────
# 1. Marcas
# ─────────────────────────────────────────────────────────────────────────────

@router.get("/marcas")
def list_marcas(db: Session = Depends(get_db)):
    """All makes, ordered alphabetically. Used to populate the first dropdown."""
    rows = db.execute(text("""
        SELECT id, nombre, slug, primer_anio, ultimo_anio
        FROM vehiculos_marcas
        ORDER BY nombre
    """)).mappings().all()
    return [dict(r) for r in rows]


# ─────────────────────────────────────────────────────────────────────────────
# 2. Models by make
# ─────────────────────────────────────────────────────────────────────────────

@router.get("/modelos")
def list_modelos(
    marca_id: int = Query(..., description="vehiculos_marcas.id"),
    db: Session = Depends(get_db),
):
    """Models for a given make, ordered alphabetically."""
    rows = db.execute(text("""
        SELECT id, nombre, vehicle_type
        FROM vehiculos_modelos
        WHERE marca_id = :mid
        ORDER BY nombre
    """), {"mid": marca_id}).mappings().all()
    return [dict(r) for r in rows]


# ─────────────────────────────────────────────────────────────────────────────
# 3. Years by model
# ─────────────────────────────────────────────────────────────────────────────

@router.get("/anios")
def list_anios(
    modelo_id: int = Query(..., description="vehiculos_modelos.id"),
    db: Session = Depends(get_db),
):
    """Distinct years available for a model, newest first."""
    rows = db.execute(text("""
        SELECT DISTINCT anio
        FROM vehiculos_aplicaciones
        WHERE modelo_id = :mid
        ORDER BY anio DESC
    """), {"mid": modelo_id}).scalars().all()
    return rows


# ─────────────────────────────────────────────────────────────────────────────
# 4. Applications / styles
# ─────────────────────────────────────────────────────────────────────────────

@router.get("/aplicaciones")
def list_aplicaciones(
    modelo_id: int = Query(...),
    anio: int = Query(...),
    db: Session = Depends(get_db),
):
    """
    Motor options for a specific model + year combination.
    Returns motor (free text), traccion, and carroceria as display labels.
    """
    rows = db.execute(text("""
        SELECT id, motor, traccion, carroceria
        FROM vehiculos_aplicaciones
        WHERE modelo_id = :mid AND anio = :anio
        ORDER BY motor
    """), {"mid": modelo_id, "anio": anio}).mappings().all()
    return [dict(r) for r in rows]


# ─────────────────────────────────────────────────────────────────────────────
# 5a. Compatible products by model + year  (used by the simplified search UI)
# ─────────────────────────────────────────────────────────────────────────────

@router.get("/productos")
def productos_por_modelo_anio(
    modelo_id: int = Query(...),
    anio: int = Query(...),
    motor: str | None = Query(default=None),
    db: Session = Depends(get_db),
):
    """
    Products linked to any application for a given model + year, with optional
    motor filter. Always returns the full list of available motors for that
    model+year so the frontend can populate the dropdown in a single call.

    Response shape:
        { motores: string[], items: ProductoAplicacion[] }
    """
    # Always fetch available motors for this model+year
    motores = db.execute(text("""
        SELECT DISTINCT motor
        FROM vehiculos_aplicaciones
        WHERE modelo_id = :mid AND anio = :anio
        ORDER BY motor
    """), {"mid": modelo_id, "anio": anio}).scalars().all()

    # Build product query — motor filter is optional
    params: dict = {"mid": modelo_id, "anio": anio}
    motor_clause = ""
    if motor:
        motor_clause = "AND a.motor = :motor"
        params["motor"] = motor

    rows = db.execute(text(f"""
        SELECT DISTINCT ON (p.id)
            p.id,
            p.sku,
            p.codigo_pos,
            p.marca,
            p.name,
            p.unit,
            COALESCE(p.precio_publico, p.price) AS price,
            p.min_stock,
            p.is_active,
            p.imagen_url,
            pa.notas AS notas_aplicacion,
            COALESCE(s.qty, 0) AS stock
        FROM vehiculos_aplicaciones a
        JOIN producto_aplicacion pa ON pa.aplicacion_id = a.id
        JOIN productos p            ON p.id = pa.producto_id
        LEFT JOIN (
            SELECT product_id, SUM(quantity) AS qty
            FROM movimientos_inventario
            GROUP BY product_id
        ) s ON s.product_id = p.id
        WHERE a.modelo_id = :mid AND a.anio = :anio {motor_clause}
        ORDER BY p.id, p.marca, p.name
    """), params).mappings().all()

    return {"motores": list(motores), "items": [dict(r) for r in rows]}


# ─────────────────────────────────────────────────────────────────────────────
# 5b. Compatible products by application
# ─────────────────────────────────────────────────────────────────────────────

@router.get("/aplicaciones/{aplicacion_id}/productos")
def productos_por_aplicacion(
    aplicacion_id: int,
    db: Session = Depends(get_db),
):
    """
    Products linked to a specific application (trim + year).
    Returns enough product fields to display a result list with
    price and current stock.
    """
    # Verify the application exists
    exists = db.execute(
        text("SELECT 1 FROM vehiculos_aplicaciones WHERE id = :id"),
        {"id": aplicacion_id},
    ).scalar()
    if not exists:
        raise HTTPException(status_code=404, detail="Aplicación no encontrada")

    rows = db.execute(text("""
        SELECT
            p.id,
            p.sku,
            p.codigo_pos,
            p.marca,
            p.name,
            p.unit,
            COALESCE(p.precio_publico, p.price) AS price,
            p.min_stock,
            p.is_active,
            p.imagen_url,
            pa.notas AS notas_aplicacion,
            COALESCE(s.qty, 0) AS stock
        FROM producto_aplicacion pa
        JOIN productos p ON p.id = pa.producto_id
        LEFT JOIN (
            SELECT product_id, SUM(quantity) AS qty
            FROM movimientos_inventario
            GROUP BY product_id
        ) s ON s.product_id = p.id
        WHERE pa.aplicacion_id = :aid
        ORDER BY p.marca, p.name
    """), {"aid": aplicacion_id}).mappings().all()

    return [dict(r) for r in rows]


# ─────────────────────────────────────────────────────────────────────────────
# 6. Reverse lookup: which vehicles fit a given product?
# ─────────────────────────────────────────────────────────────────────────────

@router.get("/productos/{producto_id}/aplicaciones")
def aplicaciones_por_producto(
    producto_id: int,
    db: Session = Depends(get_db),
):
    """
    All vehicle applications that a product is linked to.
    Returns the full make → model → year → style hierarchy.
    """
    rows = db.execute(text("""
        SELECT
            mk.id  AS marca_id,
            mk.nombre AS marca,
            m.id   AS modelo_id,
            m.nombre AS modelo,
            a.anio,
            a.id   AS aplicacion_id,
            a.motor,
            a.traccion,
            a.carroceria,
            pa.notas AS notas_aplicacion
        FROM producto_aplicacion pa
        JOIN vehiculos_aplicaciones a  ON a.id  = pa.aplicacion_id
        JOIN vehiculos_modelos m       ON m.id  = a.modelo_id
        JOIN vehiculos_marcas mk       ON mk.id = m.marca_id
        WHERE pa.producto_id = :pid
        ORDER BY mk.nombre, m.nombre, a.anio DESC, a.motor
    """), {"pid": producto_id}).mappings().all()

    return [dict(r) for r in rows]


# ─────────────────────────────────────────────────────────────────────────────
# 7. Link / unlink a product to an application
# ─────────────────────────────────────────────────────────────────────────────

@router.post("/aplicaciones/{aplicacion_id}/productos/{producto_id}")
def link_producto(
    aplicacion_id: int,
    producto_id: int,
    notas: str | None = None,
    db: Session = Depends(get_db),
):
    """Add a product ↔ application link (idempotent)."""
    db.execute(text("""
        INSERT INTO producto_aplicacion (producto_id, aplicacion_id, notas)
        VALUES (:pid, :aid, :notas)
        ON CONFLICT DO NOTHING
    """), {"pid": producto_id, "aid": aplicacion_id, "notas": notas})
    db.commit()
    return {"ok": True}


@router.delete("/aplicaciones/{aplicacion_id}/productos/{producto_id}")
def unlink_producto(
    aplicacion_id: int,
    producto_id: int,
    db: Session = Depends(get_db),
):
    """Remove a product ↔ application link."""
    db.execute(text("""
        DELETE FROM producto_aplicacion
        WHERE aplicacion_id = :aid AND producto_id = :pid
    """), {"pid": producto_id, "aid": aplicacion_id})
    db.commit()
    return {"ok": True}
