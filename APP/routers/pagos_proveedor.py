import logging
import re
from collections import defaultdict
from datetime import date
from typing import Optional, Literal

from fastapi import APIRouter, Depends, Query, HTTPException
from pydantic import BaseModel, field_validator
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from APP.db import get_db
from APP.pos_db import get_pos_db

logger = logging.getLogger(__name__)

router          = APIRouter(prefix="/compras/pagos-lotes", tags=["Pagos Proveedor"])
router_reportes = APIRouter(prefix="/compras/reportes",    tags=["Pagos Proveedor"])


# ── Schemas ───────────────────────────────────────────────────────────────────

class PagoLoteCreate(BaseModel):
    proveedor_id:    int
    fecha_pago:      date
    banco_origen:    Optional[str] = None
    cuenta_origen:   Optional[str] = None
    forma_pago:      Optional[str] = None
    origen:          str = "MANUAL"
    source_uid:      Optional[str] = None
    referencia_pago: Optional[str] = None
    notas:           Optional[str] = None


class PagoLoteUpdate(BaseModel):
    fecha_pago:           Optional[date] = None
    banco_origen:         Optional[str]  = None
    cuenta_origen:        Optional[str]  = None
    forma_pago:           Optional[str]  = None
    referencia_pago:      Optional[str]  = None
    referencia_bancaria:  Optional[str]  = None
    estado_conciliacion:  Optional[str]  = None
    notas:                Optional[str]  = None
    notas_credito:        Optional[str]  = None


class PagoLoteDetalleCreate(BaseModel):
    line_no:         int  = 1
    compra_id:       Optional[int]  = None
    tipo:            Literal["FACTURA", "NOTA_CREDITO"]
    folio:           Optional[str]  = None
    fecha_documento: Optional[date] = None
    monto:           float
    notas:           Optional[str]  = None

    @field_validator("monto")
    @classmethod
    def monto_positivo(cls, v):
        if v <= 0:
            raise ValueError("monto must be > 0")
        return round(v, 2)


# ── Helpers ───────────────────────────────────────────────────────────────────

_LOTE_TOTALS_SQL = """
    SELECT
        l.id,
        l.proveedor_id,
        p.nombre                                                                  AS proveedor_nombre,
        l.fecha_pago,
        l.banco_origen,
        l.cuenta_origen,
        l.forma_pago,
        l.source_uid,
        l.referencia_pago,
        l.origen,
        l.notas,
        l.notas_credito,
        l.estado_conciliacion,
        l.referencia_bancaria,
        l.created_at,
        l.updated_at,
        COALESCE(COUNT(d.id), 0)                                                  AS lineas,
        COALESCE(SUM(CASE WHEN d.tipo = 'FACTURA'      THEN d.monto ELSE 0 END), 0) AS total_facturas,
        COALESCE(SUM(CASE WHEN d.tipo = 'NOTA_CREDITO' THEN d.monto ELSE 0 END), 0) AS total_notas_credito,
        COALESCE(SUM(CASE WHEN d.tipo = 'FACTURA'      THEN  d.monto
                          WHEN d.tipo = 'NOTA_CREDITO' THEN -d.monto
                          ELSE 0 END), 0)                                         AS total_neto
    FROM pagos_proveedor_lotes l
    JOIN proveedores p ON p.id = l.proveedor_id
    LEFT JOIN pagos_proveedor_lote_detalle d ON d.lote_id = l.id
"""


def _require_lote(db: Session, lote_id: int) -> dict:
    row = db.execute(
        text(_LOTE_TOTALS_SQL + " WHERE l.id = :id GROUP BY l.id, p.nombre"),
        {"id": lote_id},
    ).mappings().first()
    if not row:
        raise HTTPException(status_code=404, detail=f"Lote no existe: {lote_id}")
    return dict(row)


def _folios_resumen(detalle: list) -> str:
    folios = [d["folio"] for d in detalle if d.get("tipo") == "FACTURA" and d.get("folio")]
    if not folios:
        return ""
    if len(folios) <= 5:
        return ", ".join(folios)
    return ", ".join(folios[:5]) + f" +{len(folios) - 5} más"


def _normalize_pagref(s: str) -> str:
    """Normalize PAGREF to a safe source_uid segment."""
    cleaned = s.strip().upper() if s else ""
    return re.sub(r"[^A-Za-z0-9]", "_", cleaned) if cleaned else "NONE"


# ── POST /compras/pagos-lotes ─────────────────────────────────────────────────

@router.post("", status_code=201)
def create_lote(payload: PagoLoteCreate, db: Session = Depends(get_db)):
    prov = db.execute(
        text("SELECT id FROM proveedores WHERE id = :id"),
        {"id": payload.proveedor_id},
    ).first()
    if not prov:
        raise HTTPException(status_code=404, detail=f"Proveedor no existe: {payload.proveedor_id}")

    try:
        row_id = db.execute(
            text("""
                INSERT INTO pagos_proveedor_lotes
                    (proveedor_id, fecha_pago, banco_origen, cuenta_origen, forma_pago,
                     origen, source_uid, referencia_pago, notas, created_at, updated_at)
                VALUES
                    (:proveedor_id, :fecha_pago, :banco_origen, :cuenta_origen, :forma_pago,
                     :origen, :source_uid, :referencia_pago, :notas, NOW(), NOW())
                RETURNING id
            """),
            {
                "proveedor_id":    payload.proveedor_id,
                "fecha_pago":      payload.fecha_pago,
                "banco_origen":    payload.banco_origen,
                "cuenta_origen":   payload.cuenta_origen,
                "forma_pago":      payload.forma_pago,
                "origen":          payload.origen,
                "source_uid":      payload.source_uid,
                "referencia_pago": payload.referencia_pago,
                "notas":           payload.notas,
            },
        ).scalar()
        db.commit()
    except IntegrityError as e:
        db.rollback()
        logger.error("IntegrityError create_lote: %s", e)
        raise HTTPException(status_code=409, detail="source_uid duplicado o restricción de integridad")

    return {"ok": True, "lote": _require_lote(db, row_id)}


# ── GET /compras/pagos-lotes ──────────────────────────────────────────────────

@router.get("")
def list_lotes(
    proveedor_id: Optional[int]  = Query(default=None),
    fecha_inicio: Optional[date] = Query(default=None),
    fecha_fin:    Optional[date] = Query(default=None),
    page:  int = Query(default=1,   ge=1),
    limit: int = Query(default=50,  ge=1, le=200),
    db: Session = Depends(get_db),
):
    filters: list[str] = []
    params: dict = {"offset": (page - 1) * limit, "limit": limit}

    if proveedor_id is not None:
        filters.append("l.proveedor_id = :proveedor_id")
        params["proveedor_id"] = proveedor_id
    if fecha_inicio is not None:
        filters.append("l.fecha_pago >= :fecha_inicio")
        params["fecha_inicio"] = fecha_inicio
    if fecha_fin is not None:
        filters.append("l.fecha_pago <= :fecha_fin")
        params["fecha_fin"] = fecha_fin

    where = ("WHERE " + " AND ".join(filters)) if filters else ""

    count_row = db.execute(
        text(f"SELECT COUNT(*) FROM pagos_proveedor_lotes l {where}"), params
    ).scalar()

    rows = db.execute(
        text(
            _LOTE_TOTALS_SQL
            + f" {where} GROUP BY l.id, p.nombre"
            + " ORDER BY l.fecha_pago DESC, l.id DESC"
            + " OFFSET :offset LIMIT :limit"
        ),
        params,
    ).mappings().all()

    return {"total": count_row, "page": page, "limit": limit, "items": [dict(r) for r in rows]}


# ── GET /compras/pagos-lotes/{lote_id} ───────────────────────────────────────

@router.get("/{lote_id}")
def get_lote(lote_id: int, db: Session = Depends(get_db)):
    lote = _require_lote(db, lote_id)
    detalle = db.execute(
        text("""
            SELECT id, lote_id, line_no, compra_id, tipo, folio, fecha_documento, monto, notas, created_at
            FROM pagos_proveedor_lote_detalle
            WHERE lote_id = :lid
            ORDER BY
                (CASE tipo WHEN 'FACTURA' THEN 0 ELSE 1 END),
                fecha_documento ASC NULLS LAST,
                folio           ASC NULLS LAST,
                line_no         ASC
        """),
        {"lid": lote_id},
    ).mappings().all()
    detalle_list = [dict(d) for d in detalle]
    lote["detalle"]        = detalle_list
    lote["folios_resumen"] = _folios_resumen(detalle_list)
    return lote


# ── PATCH /compras/pagos-lotes/{lote_id} ─────────────────────────────────────

@router.patch("/{lote_id}")
def update_lote(lote_id: int, payload: PagoLoteUpdate, db: Session = Depends(get_db)):
    _require_lote(db, lote_id)

    sets: list[str] = []
    params: dict = {"id": lote_id}
    for field in ("fecha_pago", "banco_origen", "cuenta_origen", "forma_pago",
                  "referencia_pago", "referencia_bancaria", "estado_conciliacion", "notas",
                  "notas_credito"):
        val = getattr(payload, field)
        if val is not None:
            sets.append(f"{field} = :{field}")
            params[field] = val

    if not sets:
        raise HTTPException(status_code=422, detail="No fields to update")

    sets.append("updated_at = NOW()")
    db.execute(
        text(f"UPDATE pagos_proveedor_lotes SET {', '.join(sets)} WHERE id = :id"), params
    )
    db.commit()
    return {"ok": True, "lote": _require_lote(db, lote_id)}


# ── DELETE /compras/pagos-lotes/{lote_id} ────────────────────────────────────

@router.delete("/{lote_id}")
def delete_lote(lote_id: int, db: Session = Depends(get_db)):
    _require_lote(db, lote_id)
    db.execute(text("DELETE FROM pagos_proveedor_lotes WHERE id = :id"), {"id": lote_id})
    db.commit()
    return {"ok": True, "deleted_lote_id": lote_id}


# ── POST /compras/pagos-lotes/{lote_id}/detalle ───────────────────────────────

@router.post("/{lote_id}/detalle", status_code=201)
def add_detalle(lote_id: int, payload: PagoLoteDetalleCreate, db: Session = Depends(get_db)):
    lote = _require_lote(db, lote_id)

    if payload.compra_id is not None:
        compra_prov = db.execute(
            text("SELECT proveedor_id FROM compras WHERE id = :id"), {"id": payload.compra_id}
        ).scalar()
        if compra_prov is None:
            raise HTTPException(status_code=404, detail=f"Compra no existe: {payload.compra_id}")
        if compra_prov != lote["proveedor_id"]:
            raise HTTPException(
                status_code=422,
                detail=f"Compra {payload.compra_id} pertenece a proveedor {compra_prov}, "
                       f"no a {lote['proveedor_id']}",
            )

    try:
        row = db.execute(
            text("""
                INSERT INTO pagos_proveedor_lote_detalle
                    (lote_id, line_no, compra_id, tipo, folio, fecha_documento, monto, notas, created_at)
                VALUES
                    (:lote_id, :line_no, :compra_id, :tipo, :folio, :fecha_documento, :monto, :notas, NOW())
                RETURNING id, lote_id, line_no, compra_id, tipo, folio, fecha_documento, monto, notas, created_at
            """),
            {
                "lote_id":         lote_id,
                "line_no":         payload.line_no,
                "compra_id":       payload.compra_id,
                "tipo":            payload.tipo,
                "folio":           payload.folio,
                "fecha_documento": payload.fecha_documento,
                "monto":           payload.monto,
                "notas":           payload.notas,
            },
        ).mappings().one()
        db.commit()
    except IntegrityError as e:
        db.rollback()
        logger.error("IntegrityError add_detalle lote=%s: %s", lote_id, e)
        raise HTTPException(status_code=409, detail=f"line_no {payload.line_no} ya existe en este lote")

    return {"ok": True, "detalle": dict(row)}


# ── DELETE /compras/pagos-lotes/detalle/{detalle_id} ─────────────────────────

@router.delete("/detalle/{detalle_id}")
def delete_detalle(detalle_id: int, db: Session = Depends(get_db)):
    row = db.execute(
        text("SELECT id FROM pagos_proveedor_lote_detalle WHERE id = :id"), {"id": detalle_id}
    ).scalar()
    if not row:
        raise HTTPException(status_code=404, detail=f"Detalle no existe: {detalle_id}")
    db.execute(text("DELETE FROM pagos_proveedor_lote_detalle WHERE id = :id"), {"id": detalle_id})
    db.commit()
    return {"ok": True, "deleted_detalle_id": detalle_id}


# ── POST /compras/pagos-lotes/sync/pos ───────────────────────────────────────

@router.post("/sync/pos")
def sync_pagos_from_pos(
    fecha_inicio: date = Query(...),
    fecha_fin:    date = Query(...),
    dry_run: bool = Query(
        default=True,
        description="True = preview only (no writes). Set False to commit.",
    ),
    db:  Session = Depends(get_db),
    pos: Session = Depends(get_pos_db),
):
    """
    Build pagos_proveedor_lotes from POS pag table for a date range (by FECHAAPLICADA).

    Groups: proveedor + fecha_pago + forma_pago + pagref  → one lote per group.
    Detail: one row per pag entry; PAGADO>0 = FACTURA, PAGADO<0 = NOTA_CREDITO.
    source_uid: POS:PAG:{pos_prov_id}:{fecha_pago}:{forma_pago}:{normalized_pagref}
    Idempotent — skips lotes whose source_uid already exists.
    """
    pos_rows = pos.execute(text("""
        SELECT
            d.CLIENTEID                    AS pos_prov_id,
            DATE(p.FECHAAPLICADA)          AS fecha_pago,
            p.FORMAPAGO                    AS forma_pago,
            COALESCE(TRIM(p.PAGREF), '')   AS pagref,
            p.PAGOID                       AS pagoid,
            d.DOCID                        AS docid,
            COALESCE(TRIM(d.ANTERIOR), '') AS anterior,
            COALESCE(TRIM(d.NUMERO),   '') AS numero,
            d.FECHA                        AS fecha_doc,
            p.PAGADO                       AS pagado,
            p.FECHAPAG                     AS fechapag
        FROM pag p
        JOIN doc d ON d.DOCID = p.DOCID
        WHERE d.TIPO = 'E'
          AND DATE(p.FECHAAPLICADA) BETWEEN :fi AND :ff
        ORDER BY d.CLIENTEID, DATE(p.FECHAAPLICADA), p.FORMAPAGO,
                 COALESCE(TRIM(p.PAGREF),''), p.PAGOID
    """), {"fi": fecha_inicio, "ff": fecha_fin}).mappings().all()

    if not pos_rows:
        return {
            "ok": True, "dry_run": dry_run,
            "lotes_found": 0, "lotes_created": 0, "lotes_skipped": 0, "detail_rows": 0,
            "preview": [],
        }

    # Build lookups from PostgreSQL
    prov_map: dict[int, int] = {
        int(r["pos_proveedor_id"]): int(r["id"])
        for r in db.execute(
            text("SELECT id, pos_proveedor_id FROM proveedores WHERE pos_proveedor_id IS NOT NULL")
        ).mappings()
    }
    compra_map: dict[int, int] = {
        int(r["pos_compra_id"]): int(r["id"])
        for r in db.execute(
            text("SELECT id, pos_compra_id FROM compras WHERE pos_compra_id IS NOT NULL")
        ).mappings()
    }

    # Group pag rows into lotes
    groups: dict[tuple, list] = defaultdict(list)
    for row in pos_rows:
        key = (
            int(row["pos_prov_id"]),
            str(row["fecha_pago"]),
            str(row["forma_pago"] or ""),
            str(row["pagref"] or ""),
        )
        groups[key].append(dict(row))

    lotes_found   = len(groups)
    lotes_created = 0
    lotes_skipped = 0
    detail_rows   = 0
    preview: list[dict] = []

    for (pos_prov_id, fecha_pago_str, forma_pago, pagref), pag_rows in groups.items():
        proveedor_id = prov_map.get(pos_prov_id)
        if proveedor_id is None:
            lotes_skipped += 1
            preview.append({"source_uid": f"POS:PAG:{pos_prov_id}:...", "status": "SKIP_NO_PROVEEDOR"})
            continue

        norm_ref   = _normalize_pagref(pagref)
        source_uid = f"POS:PAG:{pos_prov_id}:{fecha_pago_str}:{forma_pago}:{norm_ref}"

        entry: dict = {
            "source_uid":    source_uid,
            "proveedor_id":  proveedor_id,
            "fecha_pago":    fecha_pago_str,
            "forma_pago":    forma_pago,
            "pagref":        pagref,
            "rows":          len(pag_rows),
            "status":        None,
        }

        exists = db.execute(
            text("SELECT id FROM pagos_proveedor_lotes WHERE source_uid = :uid"),
            {"uid": source_uid},
        ).scalar()

        if dry_run:
            entry["status"] = "EXISTS" if exists else "WOULD_CREATE"
            if not exists:
                lotes_created += 1
            else:
                lotes_skipped += 1
            detail_rows += len(pag_rows)
            preview.append(entry)
            continue

        if exists:
            entry["status"] = "SKIPPED_EXISTS"
            lotes_skipped  += 1
            preview.append(entry)
            continue

        try:
            db.execute(text("SAVEPOINT sp_lote"))

            lote_id = db.execute(text("""
                INSERT INTO pagos_proveedor_lotes
                    (proveedor_id, fecha_pago, forma_pago, origen, source_uid, created_at, updated_at)
                VALUES (:prov, :fecha, :fp, 'POS', :uid, NOW(), NOW())
                RETURNING id
            """), {
                "prov":  proveedor_id,
                "fecha": fecha_pago_str,
                "fp":    forma_pago or None,
                "uid":   source_uid,
            }).scalar()

            for line_no, pag in enumerate(pag_rows, start=1):
                pagado = float(pag["pagado"] or 0)
                if pagado == 0:
                    continue
                tipo   = "FACTURA" if pagado > 0 else "NOTA_CREDITO"
                monto  = round(abs(pagado), 2)
                folio  = pag["anterior"] or pag["numero"] or str(pag["docid"])
                compra_id = compra_map.get(int(pag["docid"]))
                det_notas = (
                    f"POS docid={pag['docid']} num={pag['numero']} "
                    f"ant={pag['anterior']} fp={pag['forma_pago']} "
                    f"ref={pag['pagref']} fechapag={pag['fechapag']}"
                )
                db.execute(text("""
                    INSERT INTO pagos_proveedor_lote_detalle
                        (lote_id, line_no, compra_id, tipo, folio, fecha_documento, monto, notas, created_at)
                    VALUES (:lid, :ln, :cid, :tipo, :folio, :fd, :monto, :notas, NOW())
                """), {
                    "lid":   lote_id,
                    "ln":    line_no,
                    "cid":   compra_id,
                    "tipo":  tipo,
                    "folio": folio,
                    "fd":    pag["fecha_doc"],
                    "monto": monto,
                    "notas": det_notas,
                })
                detail_rows += 1

            db.execute(text("RELEASE SAVEPOINT sp_lote"))
            lotes_created  += 1
            entry["status"] = "CREATED"

        except Exception as e:
            db.execute(text("ROLLBACK TO SAVEPOINT sp_lote"))
            logger.error("sync_pagos_from_pos error %s: %s", source_uid, e)
            lotes_skipped  += 1
            entry["status"] = f"ERROR: {e}"

        preview.append(entry)

    if not dry_run:
        db.commit()

    return {
        "ok":          True,
        "dry_run":     dry_run,
        "fecha_inicio": str(fecha_inicio),
        "fecha_fin":    str(fecha_fin),
        "lotes_found":   lotes_found,
        "lotes_created": lotes_created,
        "lotes_skipped": lotes_skipped,
        "detail_rows":   detail_rows,
        "preview":       preview,
    }


# ── GET /compras/reportes/pagos-proveedor ─────────────────────────────────────

@router_reportes.get("/pagos-proveedor")
def reporte_pagos_proveedor(
    fecha_inicio:      date = Query(...),
    fecha_fin:         date = Query(...),
    proveedor_id:      Optional[int]  = Query(default=None),
    incluir_excluidos: bool = Query(default=False, description="Incluir lotes con estado_conciliacion='EXCLUIR' en los totales"),
    db: Session = Depends(get_db),
):
    params: dict = {"fi": fecha_inicio, "ff": fecha_fin, "prov": proveedor_id}
    prov_filter    = "AND l.proveedor_id = :prov" if proveedor_id is not None else ""
    excluir_filter = "" if incluir_excluidos else "AND l.estado_conciliacion != 'EXCLUIR'"

    # ── Header totals (active lotes only) ────────────────────────────────────
    header = db.execute(text(f"""
        SELECT
            COUNT(DISTINCT l.id) AS total_lotes,
            ROUND(COALESCE(SUM(CASE WHEN d.tipo='FACTURA'      THEN d.monto ELSE 0 END),0)::numeric,2) AS total_facturas,
            ROUND(COALESCE(SUM(CASE WHEN d.tipo='NOTA_CREDITO' THEN d.monto ELSE 0 END),0)::numeric,2) AS total_notas_credito,
            ROUND(COALESCE(SUM(CASE WHEN d.tipo='FACTURA'      THEN  d.monto
                                    WHEN d.tipo='NOTA_CREDITO' THEN -d.monto
                                    ELSE 0 END),0)::numeric,2) AS total_neto_pagado
        FROM pagos_proveedor_lotes l
        JOIN pagos_proveedor_lote_detalle d ON d.lote_id = l.id
        WHERE l.fecha_pago BETWEEN :fi AND :ff {prov_filter} {excluir_filter}
    """), params).mappings().first()

    # ── Count of excluded lotes in window (always computed) ──────────────────
    excluidos_count = db.execute(text(f"""
        SELECT COUNT(DISTINCT l.id)
        FROM pagos_proveedor_lotes l
        WHERE l.fecha_pago BETWEEN :fi AND :ff {prov_filter}
          AND l.estado_conciliacion = 'EXCLUIR'
    """), params).scalar() or 0

    # ── By supplier ───────────────────────────────────────────────────────────
    por_proveedor = db.execute(text(f"""
        SELECT
            p.id     AS proveedor_id,
            p.nombre AS proveedor,
            COUNT(DISTINCT l.id) AS lotes,
            ROUND(COALESCE(SUM(CASE WHEN d.tipo='FACTURA'      THEN d.monto ELSE 0 END),0)::numeric,2) AS total_facturas,
            ROUND(COALESCE(SUM(CASE WHEN d.tipo='NOTA_CREDITO' THEN d.monto ELSE 0 END),0)::numeric,2) AS total_notas_credito,
            ROUND(COALESCE(SUM(CASE WHEN d.tipo='FACTURA'      THEN  d.monto
                                    WHEN d.tipo='NOTA_CREDITO' THEN -d.monto
                                    ELSE 0 END),0)::numeric,2) AS total_neto
        FROM pagos_proveedor_lotes l
        JOIN pagos_proveedor_lote_detalle d ON d.lote_id = l.id
        JOIN proveedores p ON p.id = l.proveedor_id
        WHERE l.fecha_pago BETWEEN :fi AND :ff {prov_filter} {excluir_filter}
        GROUP BY p.id, p.nombre
        ORDER BY total_neto DESC
    """), params).mappings().all()

    # ── Per lote with full detalle via json_agg ───────────────────────────────
    por_lote_rows = db.execute(text(f"""
        SELECT
            l.id                  AS lote_id,
            l.proveedor_id,
            p.nombre              AS proveedor,
            l.fecha_pago,
            l.banco_origen,
            l.cuenta_origen,
            l.forma_pago,
            l.referencia_pago,
            l.origen,
            l.source_uid,
            l.estado_conciliacion,
            l.referencia_bancaria,
            l.notas,
            ROUND(COALESCE(SUM(CASE WHEN d.tipo='FACTURA'      THEN d.monto ELSE 0 END),0)::numeric,2) AS total_facturas,
            ROUND(COALESCE(SUM(CASE WHEN d.tipo='NOTA_CREDITO' THEN d.monto ELSE 0 END),0)::numeric,2) AS total_notas_credito,
            ROUND(COALESCE(SUM(CASE WHEN d.tipo='FACTURA'      THEN  d.monto
                                    WHEN d.tipo='NOTA_CREDITO' THEN -d.monto
                                    ELSE 0 END),0)::numeric,2) AS total_neto,
            COUNT(CASE WHEN d.tipo='FACTURA'      THEN 1 END)::int AS facturas_count,
            COUNT(CASE WHEN d.tipo='NOTA_CREDITO' THEN 1 END)::int AS notas_credito_count,
            COALESCE(
                json_agg(
                    json_build_object(
                        'line_no',         d.line_no,
                        'tipo',            d.tipo,
                        'compra_id',       d.compra_id,
                        'folio',           d.folio,
                        'fecha_documento', d.fecha_documento,
                        'monto',           d.monto,
                        'notas',           d.notas
                    ) ORDER BY
                        (CASE d.tipo WHEN 'FACTURA' THEN 0 ELSE 1 END),
                        d.fecha_documento ASC NULLS LAST,
                        d.folio           ASC NULLS LAST,
                        d.line_no         ASC
                ) FILTER (WHERE d.id IS NOT NULL),
                '[]'::json
            ) AS detalle
        FROM pagos_proveedor_lotes l
        JOIN proveedores p ON p.id = l.proveedor_id
        LEFT JOIN pagos_proveedor_lote_detalle d ON d.lote_id = l.id
        WHERE l.fecha_pago BETWEEN :fi AND :ff {prov_filter} {excluir_filter}
        GROUP BY l.id, l.proveedor_id, p.nombre, l.fecha_pago,
                 l.banco_origen, l.cuenta_origen, l.forma_pago,
                 l.referencia_pago, l.origen, l.source_uid,
                 l.estado_conciliacion, l.referencia_bancaria, l.notas
        ORDER BY l.fecha_pago ASC, p.nombre ASC, l.id ASC
    """), params).mappings().all()

    por_lote: list[dict] = []
    for row in por_lote_rows:
        r       = dict(row)
        detalle = r.get("detalle") or []
        r["folios_resumen"] = _folios_resumen(detalle)
        por_lote.append(r)

    return {
        "fecha_inicio":     fecha_inicio,
        "fecha_fin":        fecha_fin,
        "incluir_excluidos": incluir_excluidos,
        "excluidos_count":  int(excluidos_count),
        **dict(header),
        "por_proveedor": [dict(r) for r in por_proveedor],
        "por_lote":      por_lote,
    }
