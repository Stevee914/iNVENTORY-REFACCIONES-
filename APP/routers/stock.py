from fastapi import APIRouter, Depends, Query, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import text
from APP.db import get_db
from APP.helpers import normalize_text, normalize_sku

router = APIRouter(prefix="/stock", tags=["Stock"])


@router.get("")
def list_stock(
    db: Session = Depends(get_db),
    q: str | None = Query(default=None, description="Buscar por SKU, nombre, marca o codigo_pos"),
    only_negative: bool = Query(default=False, description="Solo productos con stock físico < 0"),
    below_min_stock: bool = Query(default=False, description="Solo productos con stock físico < min_stock"),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=50, ge=1, le=10000),
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
            SELECT product_id, sku, name, min_stock, stock_fisico, stock_pos, stock_total
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


@router.get("/{sku}")
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
