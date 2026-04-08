from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from sqlalchemy import text
from APP.db import get_db
from APP.helpers import normalize_text

router = APIRouter(prefix="/reportes", tags=["Reportes"])

# ──────────────────────────────────────────────────────────────
# Shared CTE fragments
# ──────────────────────────────────────────────────────────────

_LAST_MOV_CTE = """
last_mov AS (
    SELECT product_id, MAX(movement_date) AS ultimo_mov
    FROM movimientos_inventario
    GROUP BY product_id
),"""

_PRIMARY_PROV_CTE = """
primary_prov AS (
    SELECT DISTINCT ON (product_id)
        product_id, proveedor_id
    FROM producto_proveedor
    ORDER BY product_id, is_primary DESC NULLS LAST, id ASC
),"""

_BASE_JOINS = """
LEFT JOIN v_stock_libros      v   ON v.product_id   = p.id
LEFT JOIN categoria           c   ON c.id           = p.categoria_id
LEFT JOIN categoria           cp  ON cp.id          = c.parent_id
LEFT JOIN last_mov            lm  ON lm.product_id  = p.id
LEFT JOIN primary_prov        pp  ON pp.product_id  = p.id
LEFT JOIN proveedores         pr  ON pr.id          = pp.proveedor_id"""

_CAT_LABEL = "CASE WHEN cp.name IS NOT NULL THEN cp.name || ' › ' || c.name ELSE c.name END"


def _apply_common_filters(where, params, q, categoria_id, marca, proveedor_id):
    if q:
        where.append(
            "(p.sku ILIKE :q OR p.name ILIKE :q OR COALESCE(p.marca,'') ILIKE :q)"
        )
        params["q"] = f"%{normalize_text(q)}%"
    if categoria_id is not None:
        where.append("p.categoria_id = :categoria_id")
        params["categoria_id"] = categoria_id
    if marca:
        where.append("UPPER(COALESCE(p.marca,'')) = UPPER(:marca)")
        params["marca"] = marca
    if proveedor_id is not None:
        where.append(
            "EXISTS (SELECT 1 FROM producto_proveedor pp2"
            " WHERE pp2.product_id = p.id AND pp2.proveedor_id = :proveedor_id)"
        )
        params["proveedor_id"] = proveedor_id


# ──────────────────────────────────────────────────────────────
# 1. Operational Inventory Alerts
# ──────────────────────────────────────────────────────────────

@router.get("/inventario")
def reporte_inventario(
    q: str | None = Query(default=None),
    categoria_id: int | None = Query(default=None),
    marca: str | None = Query(default=None),
    proveedor_id: int | None = Query(default=None),
    bajo_minimo: bool | None = Query(default=None),
    stock_cero: bool | None = Query(default=None),
    stock_negativo: bool | None = Query(default=None),
    sin_movimiento_30d: bool | None = Query(default=None),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=50, ge=1, le=1000),
    db: Session = Depends(get_db),
):
    # ── Global KPIs (no user filters) ──────────────────────────
    kpis = db.execute(text(f"""
        WITH {_LAST_MOV_CTE.rstrip(',')}
        SELECT
            COUNT(*)   FILTER (WHERE p.is_active)                                                      AS total_activos,
            SUM(COALESCE(v.stock_fisico, 0)) FILTER (WHERE p.is_active)                               AS stock_fisico_total,
            SUM(COALESCE(v.stock_pos,   0)) FILTER (WHERE p.is_active)                               AS stock_pos_total,
            COUNT(*)   FILTER (WHERE p.is_active
                                 AND COALESCE(v.stock_fisico, 0) < COALESCE(p.min_stock, 0)
                                 AND COALESCE(p.min_stock, 0) > 0)                                    AS bajo_minimo,
            COUNT(*)   FILTER (WHERE p.is_active AND COALESCE(v.stock_fisico, 0) = 0)                AS stock_cero,
            COUNT(*)   FILTER (WHERE p.is_active
                                 AND (lm.ultimo_mov IS NULL
                                      OR lm.ultimo_mov < NOW() - INTERVAL '30 days'))                AS sin_movimiento_30d
        FROM productos p
        LEFT JOIN v_stock_libros v  ON v.product_id = p.id
        LEFT JOIN last_mov      lm ON lm.product_id = p.id
    """)).mappings().one()

    # ── Filtered query ──────────────────────────────────────────
    where = ["p.is_active = true"]
    params: dict = {}
    _apply_common_filters(where, params, q, categoria_id, marca, proveedor_id)
    if bajo_minimo:
        where.append(
            "COALESCE(v.stock_fisico,0) < COALESCE(p.min_stock,0)"
            " AND COALESCE(p.min_stock,0) > 0"
        )
    if stock_cero:
        where.append("COALESCE(v.stock_fisico,0) = 0")
    if stock_negativo:
        where.append("COALESCE(v.stock_fisico,0) < 0")
    if sin_movimiento_30d:
        where.append(
            "(lm.ultimo_mov IS NULL OR lm.ultimo_mov < NOW() - INTERVAL '30 days')"
        )

    where_sql = "WHERE " + " AND ".join(where)
    offset = (page - 1) * page_size
    params["limit"] = page_size
    params["offset"] = offset

    total = db.execute(text(f"""
        WITH {_LAST_MOV_CTE} {_PRIMARY_PROV_CTE.rstrip(',')}
        SELECT COUNT(*) FROM productos p {_BASE_JOINS} {where_sql}
    """), params).scalar()

    rows = db.execute(text(f"""
        WITH {_LAST_MOV_CTE} {_PRIMARY_PROV_CTE.rstrip(',')}
        SELECT
            p.id   AS producto_id,
            p.sku,
            p.name,
            p.marca,
            {_CAT_LABEL}                                     AS categoria,
            COALESCE(v.stock_fisico, 0)                      AS stock_fisico,
            COALESCE(v.stock_pos,   0)                       AS stock_pos,
            COALESCE(p.min_stock,   0)                       AS min_stock,
            GREATEST(0, COALESCE(p.min_stock,0) - COALESCE(v.stock_fisico,0)) AS deficit,
            lm.ultimo_mov,
            pr.nombre                                        AS proveedor
        FROM productos p {_BASE_JOINS}
        {where_sql}
        ORDER BY deficit DESC, p.sku
        LIMIT :limit OFFSET :offset
    """), params).mappings().all()

    return {
        "kpis": {
            "total_activos":      int(kpis["total_activos"] or 0),
            "stock_fisico_total": float(kpis["stock_fisico_total"] or 0),
            "stock_pos_total":    float(kpis["stock_pos_total"] or 0),
            "bajo_minimo":        int(kpis["bajo_minimo"] or 0),
            "stock_cero":         int(kpis["stock_cero"] or 0),
            "sin_movimiento_30d": int(kpis["sin_movimiento_30d"] or 0),
        },
        "total": int(total or 0),
        "page": page,
        "page_size": page_size,
        "items": [dict(r) for r in rows],
    }


# ──────────────────────────────────────────────────────────────
# 2. Rotation / Forecast
# ──────────────────────────────────────────────────────────────

_HIGH_ROTATION_THRESHOLD = 1.0   # > 1 unit/day ≈ 30+/month


@router.get("/forecast")
def reporte_forecast(
    q: str | None = Query(default=None),
    categoria_id: int | None = Query(default=None),
    marca: str | None = Query(default=None),
    proveedor_id: int | None = Query(default=None),
    horizon: int = Query(default=30, ge=1, le=365),
    status: str | None = Query(default=None),   # reorden | cobertura_baja | sin_rotacion
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=50, ge=1, le=1000),
    db: Session = Depends(get_db),
):
    consumo_cte = """
consumo_90d AS (
    SELECT
        product_id,
        COUNT(*)                  AS num_out,
        SUM(ABS(quantity)) / 90.0 AS consumo_diario,
        MAX(movement_date)        AS ultimo_mov_out
    FROM movimientos_inventario
    WHERE libro::text = 'FISICO'
      AND movement_type = 'OUT'
      AND movement_date >= NOW() - INTERVAL '90 days'
    GROUP BY product_id
),"""

    # ── Global KPIs ─────────────────────────────────────────────
    kpis = db.execute(text(f"""
        WITH {consumo_cte}
        sin_rot_60d AS (
            SELECT product_id
            FROM movimientos_inventario
            WHERE libro::text = 'FISICO'
              AND movement_type = 'OUT'
              AND movement_date >= NOW() - INTERVAL '60 days'
            GROUP BY product_id
        )
        SELECT
            COUNT(*)  FILTER (WHERE c90.num_out >= 3)                             AS productos_analizados,
            AVG(c90.consumo_diario) FILTER (WHERE c90.num_out >= 3)              AS rotacion_promedio,
            COUNT(*)  FILTER (WHERE c90.consumo_diario > :threshold)              AS alta_rotacion,
            COUNT(p.id) FILTER (WHERE p.is_active
                                  AND sr.product_id IS NULL
                                  AND COALESCE(v.stock_fisico,0) > 0)             AS sin_rotacion_60d
        FROM productos p
        LEFT JOIN v_stock_libros v  ON v.product_id = p.id
        LEFT JOIN consumo_90d   c90 ON c90.product_id = p.id
        LEFT JOIN sin_rot_60d   sr  ON sr.product_id  = p.id
        WHERE p.is_active = true
    """), {"threshold": _HIGH_ROTATION_THRESHOLD}).mappings().one()

    # ── Filtered data query ─────────────────────────────────────
    where = ["p.is_active = true"]
    params: dict = {"horizon": horizon, "threshold": _HIGH_ROTATION_THRESHOLD}
    _apply_common_filters(where, params, q, categoria_id, marca, proveedor_id)

    # status filter mapped to WHERE clauses
    if status == "reorden":
        where.append(
            "GREATEST(0, COALESCE(c90.consumo_diario,0)*:horizon"
            " - COALESCE(v.stock_fisico,0) + COALESCE(p.min_stock,0)) > 0"
        )
    elif status == "cobertura_baja":
        where.append(
            "c90.consumo_diario > 0"
            " AND COALESCE(v.stock_fisico,0) / NULLIF(c90.consumo_diario,0) < 15"
        )
    elif status == "sin_rotacion":
        where.append("COALESCE(c90.consumo_diario,0) = 0")

    where_sql = "WHERE " + " AND ".join(where)
    offset = (page - 1) * page_size
    params["limit"] = page_size
    params["offset"] = offset

    base_from = f"""
        FROM productos p
        LEFT JOIN v_stock_libros v   ON v.product_id  = p.id
        LEFT JOIN categoria      c   ON c.id           = p.categoria_id
        LEFT JOIN categoria      cp  ON cp.id          = c.parent_id
        LEFT JOIN consumo_90d    c90 ON c90.product_id = p.id
        LEFT JOIN primary_prov   pp  ON pp.product_id  = p.id
        LEFT JOIN proveedores    pr  ON pr.id           = pp.proveedor_id
    """

    total = db.execute(text(f"""
        WITH {consumo_cte} {_PRIMARY_PROV_CTE.rstrip(',')}
        SELECT COUNT(*) {base_from} {where_sql}
    """), params).scalar()

    rows = db.execute(text(f"""
        WITH {consumo_cte} {_PRIMARY_PROV_CTE.rstrip(',')}
        SELECT
            p.id                                                             AS producto_id,
            p.sku,
            p.name,
            p.marca,
            {_CAT_LABEL}                                                     AS categoria,
            COALESCE(v.stock_fisico, 0)                                      AS stock_fisico,
            ROUND(COALESCE(c90.consumo_diario, 0)::numeric, 3)              AS consumo_promedio_diario,
            CASE
                WHEN COALESCE(c90.consumo_diario,0) = 0 THEN NULL
                ELSE GREATEST(0, ROUND((COALESCE(v.stock_fisico,0)
                             / NULLIF(c90.consumo_diario,0))::numeric, 1))
            END                                                              AS cobertura_dias,
            ROUND((COALESCE(c90.consumo_diario,0) * :horizon)::numeric, 1)  AS demanda_proyectada,
            GREATEST(0, ROUND((
                COALESCE(c90.consumo_diario,0) * :horizon
                - COALESCE(v.stock_fisico,0)
                + COALESCE(p.min_stock,0)
            )::numeric, 0))                                                  AS sugerido_comprar,
            COALESCE(c90.num_out, 0)                                         AS num_out_90d,
            c90.ultimo_mov_out,
            pr.nombre                                                        AS proveedor
        {base_from}
        {where_sql}
        ORDER BY
            CASE WHEN COALESCE(c90.consumo_diario,0) = 0 THEN 1 ELSE 0 END,
            cobertura_dias ASC NULLS LAST,
            p.sku
        LIMIT :limit OFFSET :offset
    """), params).mappings().all()

    return {
        "kpis": {
            "productos_analizados": int(kpis["productos_analizados"] or 0),
            "rotacion_promedio":    round(float(kpis["rotacion_promedio"] or 0), 3),
            "alta_rotacion":        int(kpis["alta_rotacion"] or 0),
            "sin_rotacion_60d":     int(kpis["sin_rotacion_60d"] or 0),
        },
        "total": int(total or 0),
        "page": page,
        "page_size": page_size,
        "items": [dict(r) for r in rows],
    }


# ──────────────────────────────────────────────────────────────
# 3. Margin Analysis
# ──────────────────────────────────────────────────────────────

@router.get("/margenes")
def reporte_margenes(
    q: str | None = Query(default=None),
    categoria_id: int | None = Query(default=None),
    marca: str | None = Query(default=None),
    proveedor_id: int | None = Query(default=None),
    sin_costo: bool | None = Query(default=None),
    sin_precio_publico: bool | None = Query(default=None),
    margen_bajo: float | None = Query(default=None),
    margen_negativo: bool | None = Query(default=None),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=50, ge=1, le=1000),
    db: Session = Depends(get_db),
):
    where = []
    params: dict = {}

    if q:
        where.append(
            "(vm.sku ILIKE :q OR vm.name ILIKE :q OR COALESCE(vm.marca,'') ILIKE :q)"
        )
        params["q"] = f"%{normalize_text(q)}%"
    if categoria_id is not None:
        where.append("p.categoria_id = :categoria_id")
        params["categoria_id"] = categoria_id
    if marca:
        where.append("UPPER(COALESCE(vm.marca,'')) = UPPER(:marca)")
        params["marca"] = marca
    if proveedor_id is not None:
        where.append(
            "EXISTS (SELECT 1 FROM producto_proveedor pp2"
            " WHERE pp2.product_id = vm.producto_id AND pp2.proveedor_id = :proveedor_id)"
        )
        params["proveedor_id"] = proveedor_id
    if sin_costo:
        where.append("vm.costo_base IS NULL")
    if sin_precio_publico:
        where.append("p.precio_publico IS NULL")
    if margen_negativo:
        where.append("vm.margen_porcentaje < 0")
    elif margen_bajo is not None:
        where.append(
            "(vm.margen_porcentaje IS NULL OR vm.margen_porcentaje < :margen_bajo)"
        )
        params["margen_bajo"] = margen_bajo

    base_from = """
        FROM v_producto_margen vm
        JOIN productos p ON p.id = vm.producto_id
        LEFT JOIN categoria  c  ON c.id  = p.categoria_id
        LEFT JOIN categoria  cp ON cp.id = c.parent_id
        LEFT JOIN (
            SELECT DISTINCT ON (product_id) product_id, proveedor_id
            FROM producto_proveedor
            ORDER BY product_id, is_primary DESC NULLS LAST, id ASC
        ) pp ON pp.product_id = vm.producto_id
        LEFT JOIN proveedores pr ON pr.id = pp.proveedor_id
    """
    where_sql = ("WHERE " + " AND ".join(where)) if where else ""

    # ── Full-dataset totals (same WHERE, no pagination) ─────────
    totals_row = db.execute(text(f"""
        SELECT
            COUNT(*)                                                         AS total,
            COUNT(*) FILTER (WHERE vm.costo_base IS NULL)                   AS sin_costo,
            COUNT(*) FILTER (WHERE p.precio_publico IS NULL)                AS sin_precio_publico,
            AVG(vm.margen_porcentaje) FILTER (WHERE vm.margen_porcentaje IS NOT NULL) AS margen_promedio,
            COUNT(*) FILTER (WHERE vm.margen_porcentaje IS NOT NULL
                              AND vm.margen_porcentaje < 15)                AS en_riesgo
        {base_from} {where_sql}
    """), params).mappings().one()

    offset = (page - 1) * page_size
    params["limit"] = page_size
    params["offset"] = offset

    rows = db.execute(text(f"""
        SELECT
            vm.producto_id, vm.sku, vm.name, vm.marca,
            {_CAT_LABEL}                                    AS categoria,
            vm.costo_pos_con_iva, vm.costo_real_sin_iva,
            vm.costo_base, vm.fuente_costo,
            p.precio_publico,
            vm.precio_final,
            vm.porcentaje_margen_objetivo, vm.precio_sugerido,
            vm.costo_real_updated_at,
            vm.utilidad, vm.margen_porcentaje, vm.markup_porcentaje,
            pr.nombre AS proveedor
        {base_from} {where_sql}
        ORDER BY vm.margen_porcentaje ASC NULLS FIRST
        LIMIT :limit OFFSET :offset
    """), params).mappings().all()

    mp = totals_row["margen_promedio"]
    return {
        "totals": {
            "total":               int(totals_row["total"] or 0),
            "sin_costo":           int(totals_row["sin_costo"] or 0),
            "sin_precio_publico":  int(totals_row["sin_precio_publico"] or 0),
            "margen_promedio":     round(float(mp), 2) if mp is not None else None,
            "en_riesgo":           int(totals_row["en_riesgo"] or 0),
        },
        "total":     int(totals_row["total"] or 0),
        "page":      page,
        "page_size": page_size,
        "items": [dict(r) for r in rows],
    }
