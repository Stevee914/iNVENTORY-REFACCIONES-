from fastapi import APIRouter, Depends, Query, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import text
from APP.db import get_db
from APP.schemas_clientes import ClienteCreate, ClienteUpdate
from APP.helpers import normalize_text

router = APIRouter(prefix="/clientes", tags=["Clientes"])


@router.get("")
def list_clientes(
    q: str | None = Query(default=None),
    tipo: str | None = Query(default=None),
    only_active: bool = Query(default=True),
    db: Session = Depends(get_db),
):
    where = []
    params = {}

    if q:
        where.append("(c.nombre ILIKE :q OR c.rfc ILIKE :q OR c.telefono ILIKE :q)")
        params["q"] = f"%{normalize_text(q)}%"
    if tipo:
        where.append("c.tipo = :tipo")
        params["tipo"] = tipo.upper()
    if only_active:
        where.append("c.is_active = true")

    where_sql = ("WHERE " + " AND ".join(where)) if where else ""

    rows = db.execute(
        text(f"""
            SELECT c.id, c.nombre, c.rfc, c.direccion, c.telefono, c.correo,
                   c.tipo, c.notas, c.is_active, c.created_at,
                   COUNT(f.id) AS total_facturas,
                   COALESCE(SUM(f.monto), 0) AS total_compras
            FROM clientes c
            LEFT JOIN facturas f ON f.cliente_id = c.id
            {where_sql}
            GROUP BY c.id
            ORDER BY c.nombre
        """),
        params,
    ).mappings().all()
    return {"items": rows, "count": len(rows)}


@router.get("/resumen")
def clientes_resumen(db: Session = Depends(get_db)):
    """Resumen de clientes con saldo pendiente."""
    rows = db.execute(
        text("""
            SELECT * FROM v_clientes_resumen
            ORDER BY total_compras DESC
        """)
    ).mappings().all()
    return {"items": rows, "count": len(rows)}


@router.get("/top")
def clientes_top(
    min_monto: float = Query(default=1000, description="Monto mínimo de compras"),
    db: Session = Depends(get_db),
):
    """Clientes con compras mayores a un monto (default $1,000)."""
    rows = db.execute(
        text("""
            SELECT * FROM v_clientes_resumen
            WHERE total_compras >= :min
            ORDER BY total_compras DESC
        """),
        {"min": min_monto},
    ).mappings().all()
    return {"items": rows, "count": len(rows)}


@router.get("/deudores")
def clientes_deudores(db: Session = Depends(get_db)):
    """Clientes con saldo pendiente > 0."""
    rows = db.execute(
        text("""
            SELECT * FROM v_clientes_resumen
            WHERE saldo_pendiente > 0
            ORDER BY saldo_pendiente DESC
        """)
    ).mappings().all()
    return {"items": rows, "count": len(rows)}


@router.get("/{cliente_id}")
def get_cliente(cliente_id: int, db: Session = Depends(get_db)):
    row = db.execute(
        text("SELECT * FROM v_clientes_resumen WHERE id = :id"),
        {"id": cliente_id},
    ).mappings().first()
    if not row:
        raise HTTPException(status_code=404, detail="Cliente no encontrado")
    return row


@router.post("")
def create_cliente(payload: ClienteCreate, db: Session = Depends(get_db)):
    nombre = normalize_text(payload.nombre).upper()
    if not nombre:
        raise HTTPException(status_code=400, detail="El nombre es obligatorio")

    row = db.execute(
        text("""
            INSERT INTO clientes (nombre, rfc, direccion, telefono, correo, tipo, notas)
            VALUES (:nombre, :rfc, :dir, :tel, :correo, :tipo, :notas)
            RETURNING id, nombre, rfc, direccion, telefono, correo, tipo, notas, is_active, created_at
        """),
        {
            "nombre": nombre,
            "rfc": normalize_text(payload.rfc).upper() or None,
            "dir": normalize_text(payload.direccion) or None,
            "tel": normalize_text(payload.telefono) or None,
            "correo": normalize_text(payload.correo) or None,
            "tipo": normalize_text(payload.tipo).upper() or "MOSTRADOR",
            "notas": normalize_text(payload.notas) or None,
        },
    ).mappings().one()
    db.commit()
    return {"ok": True, "cliente": dict(row)}


@router.patch("/{cliente_id}")
def update_cliente(cliente_id: int, payload: ClienteUpdate, db: Session = Depends(get_db)):
    existing = db.execute(
        text("SELECT id FROM clientes WHERE id = :id"),
        {"id": cliente_id},
    ).mappings().first()
    if not existing:
        raise HTTPException(status_code=404, detail="Cliente no encontrado")

    updates = []
    params = {"id": cliente_id}

    if payload.nombre is not None:
        updates.append("nombre = :nombre")
        params["nombre"] = normalize_text(payload.nombre).upper()
    if payload.rfc is not None:
        updates.append("rfc = :rfc")
        params["rfc"] = normalize_text(payload.rfc).upper() or None
    if payload.direccion is not None:
        updates.append("direccion = :dir")
        params["dir"] = normalize_text(payload.direccion) or None
    if payload.telefono is not None:
        updates.append("telefono = :tel")
        params["tel"] = normalize_text(payload.telefono) or None
    if payload.correo is not None:
        updates.append("correo = :correo")
        params["correo"] = normalize_text(payload.correo) or None
    if payload.tipo is not None:
        updates.append("tipo = :tipo")
        params["tipo"] = normalize_text(payload.tipo).upper()
    if payload.notas is not None:
        updates.append("notas = :notas")
        params["notas"] = normalize_text(payload.notas) or None
    if payload.is_active is not None:
        updates.append("is_active = :active")
        params["active"] = payload.is_active

    if not updates:
        raise HTTPException(status_code=400, detail="No se enviaron campos")

    row = db.execute(
        text(f"""
            UPDATE clientes SET {", ".join(updates)}
            WHERE id = :id
            RETURNING id, nombre, rfc, direccion, telefono, correo, tipo, notas, is_active, created_at
        """),
        params,
    ).mappings().one()
    db.commit()
    return {"ok": True, "cliente": dict(row)}


@router.delete("/{cliente_id}")
def delete_cliente(cliente_id: int, db: Session = Depends(get_db)):
    existing = db.execute(
        text("SELECT id FROM clientes WHERE id = :id"),
        {"id": cliente_id},
    ).mappings().first()
    if not existing:
        raise HTTPException(status_code=404, detail="Cliente no encontrado")

    db.execute(text("DELETE FROM clientes WHERE id = :id"), {"id": cliente_id})
    db.commit()
    return {"ok": True, "deleted": cliente_id}
