from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from sqlalchemy import text
from APP.db import get_db

router = APIRouter(prefix="/dashboard", tags=["Dashboard"])


@router.get("/resumen")
def resumen_general(db: Session = Depends(get_db)):
    """Métricas clave del inventario."""

    stats = {}

    # Total productos
    stats["total_productos"] = db.execute(text("SELECT COUNT(*) FROM productos")).scalar()
    stats["productos_activos"] = db.execute(text("SELECT COUNT(*) FROM productos WHERE is_active = true")).scalar()

    # Stock
    row = db.execute(text("""
        SELECT
            COUNT(*) as con_stock,
            SUM(CASE WHEN stock_fisico < 0 THEN 1 ELSE 0 END) as stock_negativo,
            SUM(CASE WHEN stock_fisico < COALESCE(min_stock, 0) AND min_stock > 0 THEN 1 ELSE 0 END) as bajo_minimo,
            SUM(CASE WHEN stock_fisico = 0 AND min_stock > 0 THEN 1 ELSE 0 END) as sin_stock
        FROM v_stock_libros
    """)).mappings().one()
    stats["stock_negativo"] = int(row["stock_negativo"] or 0)
    stats["bajo_minimo"] = int(row["bajo_minimo"] or 0)
    stats["sin_stock_con_minimo"] = int(row["sin_stock"] or 0)

    # Valor total del inventario (stock_fisico * price)
    valor = db.execute(text("""
        SELECT COALESCE(SUM(v.stock_fisico * p.price), 0) as valor_total
        FROM v_stock_libros v
        JOIN productos p ON p.id = v.product_id
        WHERE v.stock_fisico > 0
    """)).scalar()
    stats["valor_inventario_fisico"] = round(float(valor), 2)

    # Movimientos recientes (últimos 30 días)
    movs = db.execute(text("""
        SELECT
            COUNT(*) as total,
            SUM(CASE WHEN movement_type = 'IN' THEN 1 ELSE 0 END) as entradas,
            SUM(CASE WHEN movement_type = 'OUT' THEN 1 ELSE 0 END) as salidas,
            SUM(CASE WHEN movement_type = 'ADJUST' THEN 1 ELSE 0 END) as ajustes
        FROM movimientos_inventario
        WHERE movement_date >= NOW() - INTERVAL '30 days'
          AND reference != 'STOCK_INICIAL'
    """)).mappings().one()
    stats["movimientos_30d"] = {
        "total": int(movs["total"] or 0),
        "entradas": int(movs["entradas"] or 0),
        "salidas": int(movs["salidas"] or 0),
        "ajustes": int(movs["ajustes"] or 0),
    }

    # Categorías y proveedores
    stats["total_categorias"] = db.execute(text("SELECT COUNT(*) FROM categoria")).scalar()
    stats["total_proveedores"] = db.execute(text("SELECT COUNT(*) FROM proveedores")).scalar()

    return stats


@router.get("/productos-criticos")
def productos_criticos(db: Session = Depends(get_db)):
    """Productos con stock bajo mínimo o negativo."""
    rows = db.execute(text("""
        SELECT v.product_id, v.sku, v.name, v.min_stock, v.stock_fisico, v.stock_pos, v.stock_total,
               p.price, p.marca
        FROM v_stock_libros v
        JOIN productos p ON p.id = v.product_id
        WHERE v.stock_fisico < COALESCE(v.min_stock, 0) AND v.min_stock > 0
        ORDER BY (v.stock_fisico - v.min_stock) ASC
        LIMIT 50
    """)).mappings().all()
    return {"items": rows, "count": len(rows)}


@router.get("/diferencias-libros")
def diferencias_libros(db: Session = Depends(get_db)):
    """Productos donde el stock físico y el POS no coinciden."""
    rows = db.execute(text("""
        SELECT product_id, sku, name, min_stock, stock_fisico, stock_pos, diferencia
        FROM v_stock_compare
        WHERE diferencia != 0
        ORDER BY ABS(diferencia) DESC
        LIMIT 50
    """)).mappings().all()
    return {"items": rows, "count": len(rows)}
