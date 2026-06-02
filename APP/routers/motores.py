from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from sqlalchemy import text
from APP.db import get_db
from typing import Optional
import re

router = APIRouter(prefix="/motores", tags=["Motores / Servicio Pesado"])

_PROD_COLS = """
    p.id          AS product_id,
    p.sku,
    p.codigo_pos,
    p.marca,
    p.name,
    c.name        AS categoria,
    p.precio_publico,
    COALESCE(sf.qty, 0) AS stock_fisico,
    COALESCE(sp.qty, 0) AS stock_pos,
    pma.notas           AS notas_aplicacion
"""

_STOCK_JOINS = """
    LEFT JOIN categoria c ON c.id = p.categoria_id
    LEFT JOIN (
        SELECT product_id, SUM(quantity) AS qty
        FROM movimientos_inventario WHERE libro = 'FISICO'
        GROUP BY product_id
    ) sf ON sf.product_id = p.id
    LEFT JOIN (
        SELECT product_id, SUM(quantity) AS qty
        FROM movimientos_inventario WHERE libro = 'FISCAL_POS'
        GROUP BY product_id
    ) sp ON sp.product_id = p.id
"""

_MOTOR_COLS = """
    ma.id, ma.marca_motor, ma.familia_motor, ma.cilindrada,
    ma.configuracion, ma.combustible, ma.anio_inicio, ma.anio_fin,
    ma.descripcion_normalizada, ma.notas,
    ma.is_active, ma.fuente, ma.calidad_dato,
    (SELECT COUNT(*) FROM producto_motor_aplicacion x
     WHERE x.motor_aplicacion_id = ma.id) AS total_productos
"""


def _norm(s: str) -> str:
    """Compact normalizer: removes all separators for alias storage/matching."""
    return re.sub(r'[\s.\-/]+', '', str(s).upper().strip())


def _get_motor_or_404(motor_id: int, db: Session):
    row = db.execute(text(f"""
        SELECT {_MOTOR_COLS} FROM motores_aplicaciones ma WHERE ma.id = :id
    """), {"id": motor_id}).mappings().first()
    if not row:
        raise HTTPException(status_code=404, detail="Motor no encontrado")
    return dict(row)


# ─────────────────────────────────────────────────────────────────────────────
# 1. List engine applications
# ─────────────────────────────────────────────────────────────────────────────

@router.get("")
def list_motores(
    q: Optional[str] = None,
    marca_motor: Optional[str] = None,
    familia_motor: Optional[str] = None,
    cilindrada: Optional[str] = None,
    combustible: Optional[str] = None,
    include_inactive: bool = False,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=50, ge=1, le=200),
    db: Session = Depends(get_db),
):
    clauses, params = [], {}

    if not include_inactive:
        clauses.append("ma.is_active = true")

    if q:
        compact = _norm(q.strip())
        clauses.append("""(
            ma.descripcion_normalizada ILIKE :q
            OR ma.marca_motor ILIKE :q
            OR ma.familia_motor ILIKE :q
            OR EXISTS (
                SELECT 1 FROM motores_alias al
                WHERE al.motor_aplicacion_id = ma.id
                  AND (al.alias_normalizado ILIKE :q OR al.alias_normalizado ILIKE :qcompact)
            )
        )""")
        params["q"] = f"%{q.strip().upper()}%"
        params["qcompact"] = f"%{compact}%"

    if marca_motor:
        clauses.append("ma.marca_motor ILIKE :marca")
        params["marca"] = f"%{marca_motor.strip()}%"

    if familia_motor:
        clauses.append("ma.familia_motor ILIKE :familia")
        params["familia"] = f"%{familia_motor.strip()}%"

    if cilindrada:
        clauses.append("ma.cilindrada ILIKE :cil")
        params["cil"] = f"%{cilindrada.strip()}%"

    if combustible:
        clauses.append("ma.combustible ILIKE :comb")
        params["comb"] = f"%{combustible.strip()}%"

    where = ("WHERE " + " AND ".join(clauses)) if clauses else ""

    total = db.execute(
        text(f"SELECT COUNT(*) FROM motores_aplicaciones ma {where}"), params
    ).scalar()

    params["offset"] = (page - 1) * page_size
    params["limit"] = page_size

    rows = db.execute(text(f"""
        SELECT {_MOTOR_COLS}
        FROM motores_aplicaciones ma
        {where}
        ORDER BY ma.marca_motor, ma.familia_motor, ma.cilindrada NULLS LAST
        LIMIT :limit OFFSET :offset
    """), params).mappings().all()

    return {"page": page, "page_size": page_size, "total": total, "items": [dict(r) for r in rows]}


# ─────────────────────────────────────────────────────────────────────────────
# 2. Search (must be before /{motor_id})
# ─────────────────────────────────────────────────────────────────────────────

@router.get("/search")
def search_motores(
    q: str = Query(..., min_length=1),
    db: Session = Depends(get_db),
):
    """
    Flexible search against descripcion_normalizada, marca+familia, and aliases.
    Matches compact forms: ISB67 → ISB 6.7, N14 → N-14, OM366 → OM 366.
    """
    term = q.strip().upper()
    compact = _norm(term)

    rows = db.execute(text(f"""
        SELECT DISTINCT {_MOTOR_COLS}
        FROM motores_aplicaciones ma
        LEFT JOIN motores_alias al ON al.motor_aplicacion_id = ma.id
        WHERE ma.is_active = true
          AND (
            ma.descripcion_normalizada ILIKE :pct
            OR (ma.marca_motor || ' ' || ma.familia_motor) ILIKE :pct
            OR (ma.marca_motor || ' ' || ma.familia_motor || ' ' || COALESCE(ma.cilindrada,'')) ILIKE :pct
            OR al.alias_normalizado ILIKE :pct
            OR al.alias_normalizado ILIKE :compact_pct
          )
        ORDER BY ma.marca_motor, ma.familia_motor, ma.cilindrada NULLS LAST
        LIMIT 20
    """), {"pct": f"%{term}%", "compact_pct": f"%{compact}%"}).mappings().all()

    return [dict(r) for r in rows]


# ─────────────────────────────────────────────────────────────────────────────
# 3. Distinct brand list (must be before /{motor_id})
# ─────────────────────────────────────────────────────────────────────────────

@router.get("/marcas")
def list_marcas_motor(db: Session = Depends(get_db)):
    rows = db.execute(text(
        "SELECT DISTINCT marca_motor FROM motores_aplicaciones WHERE is_active = true ORDER BY marca_motor"
    )).scalars().all()
    return rows


# ─────────────────────────────────────────────────────────────────────────────
# 3b. Families for a brand (guided flow step 2)
# ─────────────────────────────────────────────────────────────────────────────

@router.get("/familias")
def list_familias_motor(
    marca_motor: str = Query(...),
    db: Session = Depends(get_db),
):
    rows = db.execute(text("""
        SELECT familia_motor, COUNT(*) AS count
        FROM motores_aplicaciones
        WHERE is_active = true AND UPPER(marca_motor) = UPPER(:marca)
        GROUP BY familia_motor
        ORDER BY familia_motor
    """), {"marca": marca_motor}).mappings().all()
    return [dict(r) for r in rows]


# ─────────────────────────────────────────────────────────────────────────────
# 3c. Variants for a brand+family (guided flow step 3)
# ─────────────────────────────────────────────────────────────────────────────

@router.get("/variantes")
def list_variantes_motor(
    marca_motor: str = Query(...),
    familia_motor: str = Query(...),
    db: Session = Depends(get_db),
):
    rows = db.execute(text(f"""
        SELECT {_MOTOR_COLS}
        FROM motores_aplicaciones ma
        WHERE ma.is_active = true
          AND UPPER(ma.marca_motor) = UPPER(:marca)
          AND UPPER(ma.familia_motor) = UPPER(:familia)
        ORDER BY ma.cilindrada NULLS LAST
    """), {"marca": marca_motor, "familia": familia_motor}).mappings().all()
    return [dict(r) for r in rows]


# ─────────────────────────────────────────────────────────────────────────────
# 4. Reverse lookup: engines for a product (must be before /{motor_id})
# ─────────────────────────────────────────────────────────────────────────────

@router.get("/por-producto/{product_id}")
def motores_por_producto(product_id: int, db: Session = Depends(get_db)):
    rows = db.execute(text(f"""
        SELECT {_MOTOR_COLS},
               pma.notas AS notas_aplicacion
        FROM producto_motor_aplicacion pma
        JOIN motores_aplicaciones ma ON ma.id = pma.motor_aplicacion_id
        WHERE pma.product_id = :pid
        ORDER BY ma.marca_motor, ma.familia_motor
    """), {"pid": product_id}).mappings().all()
    return [dict(r) for r in rows]


# ─────────────────────────────────────────────────────────────────────────────
# 5. Create engine application
# ─────────────────────────────────────────────────────────────────────────────

@router.post("", status_code=201)
def create_motor(payload: dict, db: Session = Depends(get_db)):
    marca = str(payload.get("marca_motor", "")).strip().upper()
    familia = str(payload.get("familia_motor", "")).strip().upper()
    desc = str(payload.get("descripcion_normalizada", "")).strip().upper()

    if not marca or not familia:
        raise HTTPException(status_code=422, detail="marca_motor y familia_motor son obligatorios")
    if not desc:
        raise HTTPException(status_code=422, detail="descripcion_normalizada es obligatoria")

    cil    = str(payload["cilindrada"]).strip().upper()    if payload.get("cilindrada")    else None
    config = str(payload["configuracion"]).strip().upper() if payload.get("configuracion") else None
    comb   = str(payload["combustible"]).strip().upper()   if payload.get("combustible")   else None
    notas  = payload.get("notas")
    fuente       = str(payload["fuente"]).strip()       if payload.get("fuente")       else None
    calidad_dato = str(payload["calidad_dato"]).strip() if payload.get("calidad_dato") else None

    try:
        motor_id = db.execute(text("""
            INSERT INTO motores_aplicaciones
                (marca_motor, familia_motor, cilindrada, configuracion, combustible,
                 anio_inicio, anio_fin, descripcion_normalizada, notas, fuente, calidad_dato)
            VALUES (:marca, :familia, :cil, :config, :comb, :ai, :af, :desc, :notas, :fuente, :calidad)
            RETURNING id
        """), {
            "marca": marca, "familia": familia, "cil": cil, "config": config,
            "comb": comb, "ai": payload.get("anio_inicio"), "af": payload.get("anio_fin"),
            "desc": desc, "notas": notas, "fuente": fuente, "calidad": calidad_dato,
        }).scalar()
    except Exception as e:
        db.rollback()
        if "unique" in str(e).lower() or "uq_motor" in str(e).lower():
            raise HTTPException(status_code=409, detail="Ya existe una aplicación de motor con esa combinación")
        raise HTTPException(status_code=500, detail=str(e))

    _upsert_aliases(motor_id, payload.get("aliases", []), db)
    db.commit()
    return _get_motor_or_404(motor_id, db)


# ─────────────────────────────────────────────────────────────────────────────
# 6. Get single engine application
# ─────────────────────────────────────────────────────────────────────────────

@router.get("/{motor_id}")
def get_motor(motor_id: int, db: Session = Depends(get_db)):
    result = _get_motor_or_404(motor_id, db)
    aliases = db.execute(text("""
        SELECT id, alias, alias_normalizado FROM motores_alias
        WHERE motor_aplicacion_id = :id ORDER BY alias
    """), {"id": motor_id}).mappings().all()
    result["aliases"] = [dict(a) for a in aliases]
    return result


# ─────────────────────────────────────────────────────────────────────────────
# 7. Update engine application
# ─────────────────────────────────────────────────────────────────────────────

@router.patch("/{motor_id}")
def update_motor(motor_id: int, payload: dict, db: Session = Depends(get_db)):
    _get_motor_or_404(motor_id, db)

    updatable = (
        "marca_motor", "familia_motor", "cilindrada", "configuracion",
        "combustible", "anio_inicio", "anio_fin", "descripcion_normalizada",
        "notas", "is_active", "fuente", "calidad_dato",
    )
    fields = {}
    for col in updatable:
        if col in payload:
            val = payload[col]
            if isinstance(val, str):
                val = val.strip().upper() if col not in ("fuente", "calidad_dato", "notas") else val.strip() or None
            fields[col] = val

    if fields:
        sets = ", ".join(f"{k} = :{k}" for k in fields)
        fields["id"] = motor_id
        db.execute(text(f"UPDATE motores_aplicaciones SET {sets}, updated_at = NOW() WHERE id = :id"), fields)

    if "aliases" in payload:
        db.execute(text("DELETE FROM motores_alias WHERE motor_aplicacion_id = :id"), {"id": motor_id})
        _upsert_aliases(motor_id, payload["aliases"], db)

    db.commit()
    return get_motor(motor_id, db)


# ─────────────────────────────────────────────────────────────────────────────
# 8. Delete engine application
# ─────────────────────────────────────────────────────────────────────────────

@router.delete("/{motor_id}")
def delete_motor(motor_id: int, db: Session = Depends(get_db)):
    _get_motor_or_404(motor_id, db)
    linked = db.execute(text(
        "SELECT COUNT(*) FROM producto_motor_aplicacion WHERE motor_aplicacion_id = :id"
    ), {"id": motor_id}).scalar()
    if linked:
        raise HTTPException(status_code=409, detail=f"No se puede eliminar: {linked} producto(s) vinculado(s)")
    db.execute(text("DELETE FROM motores_aplicaciones WHERE id = :id"), {"id": motor_id})
    db.commit()
    return {"ok": True}


# ─────────────────────────────────────────────────────────────────────────────
# 9. Products for engine
# ─────────────────────────────────────────────────────────────────────────────

@router.get("/{motor_id}/productos")
def productos_por_motor(motor_id: int, db: Session = Depends(get_db)):
    _get_motor_or_404(motor_id, db)
    rows = db.execute(text(f"""
        SELECT {_PROD_COLS}
        FROM producto_motor_aplicacion pma
        JOIN productos p ON p.id = pma.product_id
        {_STOCK_JOINS}
        WHERE pma.motor_aplicacion_id = :mid
          AND p.catalog_visible = true
        ORDER BY p.marca NULLS LAST, p.name
    """), {"mid": motor_id}).mappings().all()
    return [dict(r) for r in rows]


# ─────────────────────────────────────────────────────────────────────────────
# 10. Link product to engine
# ─────────────────────────────────────────────────────────────────────────────

@router.post("/{motor_id}/productos/{product_id}", status_code=201)
def link_producto_motor(
    motor_id: int,
    product_id: int,
    notas: Optional[str] = None,
    db: Session = Depends(get_db),
):
    _get_motor_or_404(motor_id, db)
    if not db.execute(text("SELECT 1 FROM productos WHERE id = :id"), {"id": product_id}).scalar():
        raise HTTPException(status_code=404, detail="Producto no encontrado")
    db.execute(text("""
        INSERT INTO producto_motor_aplicacion (product_id, motor_aplicacion_id, notas)
        VALUES (:pid, :mid, :notas)
        ON CONFLICT (product_id, motor_aplicacion_id) DO NOTHING
    """), {"pid": product_id, "mid": motor_id, "notas": notas})
    db.commit()
    return {"ok": True}


# ─────────────────────────────────────────────────────────────────────────────
# 11. Unlink product from engine
# ─────────────────────────────────────────────────────────────────────────────

@router.delete("/{motor_id}/productos/{product_id}")
def unlink_producto_motor(motor_id: int, product_id: int, db: Session = Depends(get_db)):
    db.execute(text("""
        DELETE FROM producto_motor_aplicacion
        WHERE motor_aplicacion_id = :mid AND product_id = :pid
    """), {"mid": motor_id, "pid": product_id})
    db.commit()
    return {"ok": True}


# ─── helpers ─────────────────────────────────────────────────────────────────

def _upsert_aliases(motor_id: int, aliases: list, db: Session):
    for a in aliases:
        a_text = str(a).strip()
        if not a_text:
            continue
        db.execute(text("""
            INSERT INTO motores_alias (motor_aplicacion_id, alias, alias_normalizado)
            VALUES (:mid, :alias, :norm)
            ON CONFLICT (alias_normalizado) DO NOTHING
        """), {"mid": motor_id, "alias": a_text.upper(), "norm": _norm(a_text)})
