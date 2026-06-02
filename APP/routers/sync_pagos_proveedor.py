"""
POST /sync/pagos-proveedor

Sync payment batches from POS `pag` table into pagos_proveedor_lotes.

Rules:
- Only manages lotes with source_uid LIKE 'POS:PAG:%' (never touches MANUAL lotes)
- source_uid = POS:PAG:{pos_prov_id}:{fecha_pago}:{forma_pago}:{pagref or NOREF}
- Idempotent: ON CONFLICT (source_uid) → only update mutable fields if amounts changed
  (preserves banco_origen, cuenta_origen, estado_conciliacion on update)
- force_replace_pos=True: deletes and re-creates the lote (full replace)
- Flags manual lotes that overlap the same proveedor+fecha window in dry_run output
"""

import logging
from datetime import date
from typing import Optional

from fastapi import APIRouter, Depends, Query, HTTPException
from pydantic import BaseModel
from sqlalchemy import text
from sqlalchemy.orm import Session

from APP.db import get_db
from APP.pos_db import get_pos_db

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/sync", tags=["Sync - Pagos Proveedor"])

_FORMA_MAP = {
    "R": "TRANSFERENCIA",
    "E": "EFECTIVO",
    "N": "NOTA_CREDITO",
    "C": "CHEQUE",
}

# Default banco_origen from POS FORMAPAGO when auto-creating a lote
_FORMAPAGO_BANCO_DEFAULT = {
    "E": "EFECTIVO",
}  # R/N/C/anything else → SIN_DEFINIR


# ── Response schemas ──────────────────────────────────────────────────────────

class LoteDetalleResult(BaseModel):
    folio: Optional[str]
    tipo: str
    monto: float
    compra_id: Optional[int]


class LoteResult(BaseModel):
    source_uid: str
    proveedor_id: Optional[int]
    pos_prov_id: int
    fecha_pago: str
    forma_pago: str
    referencia_pago: Optional[str]
    total: float
    action: str  # CREATED | UPDATED | SKIPPED | CONFLICT
    conflict_note: Optional[str] = None
    detalle: list[LoteDetalleResult]


class SyncPagosResult(BaseModel):
    dry_run: bool
    fecha_inicio: str
    fecha_fin: str
    lotes_candidatos: int
    created: int
    updated: int
    skipped: int
    conflicts: int
    lotes: list[LoteResult]


# ── Helpers ───────────────────────────────────────────────────────────────────

def _source_uid(pos_prov_id: int, fecha_pago: date, forma: str, pagref: str) -> str:
    ref_part = pagref.strip() if pagref and pagref.strip() else "NOREF"
    return f"POS:PAG:{pos_prov_id}:{fecha_pago.isoformat()}:{forma}:{ref_part}"


def _find_compra_id(db: Session, folio: str, proveedor_id: Optional[int]) -> Optional[int]:
    """Match a POS folio to compras.id via folio_factura or folio_captura."""
    if not folio or not proveedor_id:
        return None
    row = db.execute(text("""
        SELECT id FROM compras
        WHERE proveedor_id = :prov
          AND (folio_factura = :folio OR folio_captura = :folio)
        LIMIT 1
    """), {"prov": proveedor_id, "folio": folio.strip()}).fetchone()
    return row[0] if row else None


# ── Main endpoint ──────────────────────────────────────────────────────────────

@router.post("/pagos-proveedor", response_model=SyncPagosResult)
def sync_pagos_proveedor(
    fecha_inicio: date = Query(..., description="YYYY-MM-DD"),
    fecha_fin:    date = Query(..., description="YYYY-MM-DD"),
    dry_run:      bool = Query(True,  description="True = preview only, no writes"),
    force_replace_pos: bool = Query(False, description="Delete+recreate existing POS lotes if totals changed"),
    skip_on_conflict: bool = Query(True, description="Skip lotes that have a manual conflict; default True"),
    rebuild_existing: bool = Query(False, description="Rebuild detalle of existing POS lotes when total differs; False = report warning only"),
    db:     Session = Depends(get_db),
    pos_db: Session = Depends(get_pos_db),
):
    if fecha_fin < fecha_inicio:
        raise HTTPException(400, "fecha_fin must be >= fecha_inicio")

    # ── 1. Pull POS pag rows in window ────────────────────────────────────────
    # pag.DOCID → doc.DOCID; supplier = doc.CLIENTEID where doc.TIPO='E'
    # doc.ANTERIOR = supplier invoice folio (QUA..., etc.)
    pos_rows = pos_db.execute(text("""
        SELECT
            d.CLIENTEID                            AS pos_prov_id,
            DATE(p.FECHAAPLICADA)                  AS fecha_pago,
            p.FORMAPAGO                            AS forma,
            COALESCE(p.PAGREF, '')                 AS pagref,
            CONCAT(TRIM(d.SERIE), CAST(d.NUMERO AS CHAR)) AS folio,
            TRIM(d.ANTERIOR)                       AS folio_proveedor,
            p.PAGADO                               AS monto,
            p.TIPODOC                              AS tipodoc
        FROM pag p
        JOIN doc d ON d.DOCID = p.DOCID
        WHERE p.APLICADO = 'S'
          AND d.TIPO = 'E'
          AND DATE(p.FECHAAPLICADA) BETWEEN :fi AND :ff
        ORDER BY d.CLIENTEID, DATE(p.FECHAAPLICADA), p.FORMAPAGO, p.PAGREF, folio
    """), {"fi": fecha_inicio, "ff": fecha_fin}).mappings().all()

    if not pos_rows:
        return SyncPagosResult(
            dry_run=dry_run,
            fecha_inicio=str(fecha_inicio),
            fecha_fin=str(fecha_fin),
            lotes_candidatos=0,
            created=0, updated=0, skipped=0, conflicts=0,
            lotes=[],
        )

    # ── 2. Group POS rows → candidate lotes ───────────────────────────────────
    # Key: (pos_prov_id, fecha_pago, forma, pagref)
    from collections import defaultdict
    groups: dict[tuple, list] = defaultdict(list)
    for r in pos_rows:
        key = (r["pos_prov_id"], r["fecha_pago"], r["forma"], r["pagref"])
        groups[key].append(r)

    # ── 3. Load proveedor mapping (pos_proveedor_id → internal id) ────────────
    pos_prov_ids = list({k[0] for k in groups})
    ph = ", ".join(f":p{i}" for i in range(len(pos_prov_ids)))
    prov_rows = db.execute(text(f"""
        SELECT id, pos_proveedor_id FROM proveedores
        WHERE pos_proveedor_id IN ({ph})
    """), {f"p{i}": pos_prov_ids[i] for i in range(len(pos_prov_ids))}).mappings().all()
    prov_map: dict[int, int] = {r["pos_proveedor_id"]: r["id"] for r in prov_rows}

    # ── 4. Load existing POS lotes for this window (source_uid LIKE 'POS:PAG:%') ─
    existing_rows = db.execute(text("""
        SELECT id, source_uid, proveedor_id, fecha_pago, forma_pago
        FROM pagos_proveedor_lotes
        WHERE source_uid LIKE 'POS:PAG:%'
          AND fecha_pago BETWEEN :fi AND :ff
    """), {"fi": fecha_inicio, "ff": fecha_fin}).mappings().all()
    existing_by_uid: dict[str, dict] = {r["source_uid"]: dict(r) for r in existing_rows}

    # ── 5. Load manual lotes in window (for conflict detection) ───────────────
    manual_rows = db.execute(text("""
        SELECT id, source_uid, proveedor_id, fecha_pago
        FROM pagos_proveedor_lotes
        WHERE (source_uid IS NULL OR source_uid NOT LIKE 'POS:PAG:%')
          AND fecha_pago BETWEEN :fi AND :ff
    """), {"fi": fecha_inicio, "ff": fecha_fin}).mappings().all()
    # Index by (proveedor_id, fecha_pago_str)
    manual_index: dict[tuple, list] = defaultdict(list)
    for m in manual_rows:
        manual_index[(m["proveedor_id"], str(m["fecha_pago"]))].append(m)

    # ── 6. Process each candidate lote ───────────────────────────────────────
    results: list[LoteResult] = []
    counts = {"created": 0, "updated": 0, "skipped": 0, "conflicts": 0}

    for (pos_prov_id, fecha_pago_raw, forma, pagref), lineas in groups.items():
        fecha_pago_date = fecha_pago_raw if isinstance(fecha_pago_raw, date) else fecha_pago_raw
        proveedor_id = prov_map.get(pos_prov_id)
        forma_str = _FORMA_MAP.get(forma, forma or "DESCONOCIDO")
        uid = _source_uid(pos_prov_id, fecha_pago_date, forma, pagref)
        total = round(sum(float(l["monto"] or 0) for l in lineas), 2)

        # Build detalle lines — use supplier invoice folio (doc.ANTERIOR) as folio
        detalle_items: list[LoteDetalleResult] = []
        folio_proveedores: list[str] = []
        for l in lineas:
            pagado = float(l["monto"] or 0)
            if pagado == 0:
                continue
            # Prefer supplier invoice folio (doc.ANTERIOR) for matching; fall back to POS NUMERO
            folio_sup = (l.get("folio_proveedor") or "").strip()
            folio_pos = (l["folio"] or "").strip()
            folio = folio_sup or folio_pos or None
            # Credit note: negative PAGADO, FORMAPAGO='N', or TIPODOC='NC'
            is_nc = (pagado < 0
                     or (l.get("forma") or "").upper() == "N"
                     or (l["tipodoc"] or "").upper() == "NC")
            tipo  = "NOTA_CREDITO" if is_nc else "FACTURA"
            monto = round(abs(pagado), 2)
            compra_id = _find_compra_id(db, folio, proveedor_id) if not dry_run else None
            if folio and not is_nc:
                folio_proveedores.append(folio)
            detalle_items.append(LoteDetalleResult(
                folio=folio,
                tipo=tipo,
                monto=monto,
                compra_id=compra_id,
            ))
        # lote referencia = unique supplier folios joined
        referencia = ", ".join(dict.fromkeys(folio_proveedores)) or (pagref.strip() if pagref else None)

        # Detect manual conflict
        conflict_note: Optional[str] = None
        if proveedor_id:
            manual_conflicts = manual_index.get((proveedor_id, str(fecha_pago_date)), [])
            if manual_conflicts:
                ids_str = ", ".join(str(m["id"]) for m in manual_conflicts)
                conflict_note = f"Manual lote(s) id={ids_str} exist for same proveedor+fecha"
                counts["conflicts"] += 1

        existing = existing_by_uid.get(uid)

        # Skip new lotes that conflict with existing manual records
        if conflict_note and skip_on_conflict and not existing:
            action = "SKIPPED"
            counts["skipped"] += 1
            results.append(LoteResult(
                source_uid=uid,
                proveedor_id=proveedor_id,
                pos_prov_id=pos_prov_id,
                fecha_pago=str(fecha_pago_date),
                forma_pago=forma_str,
                referencia_pago=referencia,
                total=total,
                action=action,
                conflict_note=conflict_note,
                detalle=detalle_items,
            ))
            continue

        if existing:
            # Determine if update needed (total changed significantly)
            existing_total = db.execute(text("""
                SELECT COALESCE(SUM(CASE WHEN tipo='FACTURA' THEN monto ELSE -monto END), 0)
                FROM pagos_proveedor_lote_detalle WHERE lote_id = :lid
            """), {"lid": existing["id"]}).scalar() or 0
            diff = abs(float(existing_total) - total)

            needs_rebuild = diff >= 0.01 or force_replace_pos
            can_rebuild   = rebuild_existing or force_replace_pos

            if not needs_rebuild:
                action = "SKIPPED"
                counts["skipped"] += 1
            elif not can_rebuild:
                # Difference detected but rebuild not authorized — report warning, do not touch
                action = "SKIPPED"
                counts["skipped"] += 1
                warn = f"diff={diff:.2f}; rebuild omitido (rebuild_existing=False)"
                conflict_note = f"{conflict_note}; {warn}" if conflict_note else warn
            else:
                action = "UPDATED"
                counts["updated"] += 1
                if not dry_run:
                    db.execute(text("DELETE FROM pagos_proveedor_lote_detalle WHERE lote_id = :lid"),
                               {"lid": existing["id"]})
                    _insert_detalle(db, existing["id"], detalle_items, proveedor_id)
                    db.commit()
        else:
            action = "CREATED"
            counts["created"] += 1
            if not dry_run:
                banco_default = _FORMAPAGO_BANCO_DEFAULT.get(forma, "SIN_DEFINIR")
                lote_id = _insert_lote(db, uid, proveedor_id, pos_prov_id,
                                       fecha_pago_date, forma_str, referencia,
                                       banco_default)
                _insert_detalle(db, lote_id, detalle_items, proveedor_id)
                db.commit()

        results.append(LoteResult(
            source_uid=uid,
            proveedor_id=proveedor_id,
            pos_prov_id=pos_prov_id,
            fecha_pago=str(fecha_pago_date),
            forma_pago=forma_str,
            referencia_pago=referencia,
            total=total,
            action=action,
            conflict_note=conflict_note,
            detalle=detalle_items,
        ))

    result = SyncPagosResult(
        dry_run=dry_run,
        fecha_inicio=str(fecha_inicio),
        fecha_fin=str(fecha_fin),
        lotes_candidatos=len(groups),
        created=counts["created"],
        updated=counts["updated"],
        skipped=counts["skipped"],
        conflicts=counts["conflicts"],
        lotes=results,
    )

    # Log to sync_control when this is a real run (not dry_run).
    # Allows sync_diario to calculate the correct pagos window next time.
    if not dry_run:
        try:
            db.execute(text("""
                INSERT INTO sync_control
                    (proceso, fecha_inicio, fecha_fin, status, registros_ok, registros_err, notes)
                VALUES ('POS_PAGOS_PROVEEDOR', :fi, :ff, 'OK', :ok, :err, :notes)
            """), {
                "fi":    fecha_inicio,
                "ff":    fecha_fin,
                "ok":    counts["created"] + counts["updated"],
                "err":   counts["conflicts"],
                "notes": f"candidatos:{len(groups)} skipped:{counts['skipped']}",
            })
            db.commit()
        except Exception:
            logger.warning("sync_pagos_proveedor: failed to write sync_control entry", exc_info=True)

    return result


def _insert_lote(
    db: Session,
    source_uid: str,
    proveedor_id: Optional[int],
    pos_prov_id: int,
    fecha_pago: date,
    forma_pago: str,
    referencia_pago: str,
    banco_origen: str = "SIN_DEFINIR",
) -> int:
    row = db.execute(text("""
        INSERT INTO pagos_proveedor_lotes
            (proveedor_id, fecha_pago, source_uid, referencia_pago,
             forma_pago, banco_origen, origen, estado_conciliacion)
        VALUES
            (:prov, :fecha, :uid, :ref,
             :forma, :banco, 'POS', 'PENDIENTE')
        ON CONFLICT (source_uid) DO NOTHING
        RETURNING id
    """), {
        "prov": proveedor_id,
        "fecha": fecha_pago,
        "uid": source_uid,
        "ref": referencia_pago.strip() if referencia_pago else None,
        "forma": forma_pago,
        "banco": banco_origen,
    }).fetchone()
    if row:
        return row[0]
    # Already exists (race) — fetch id
    existing = db.execute(text(
        "SELECT id FROM pagos_proveedor_lotes WHERE source_uid = :uid"
    ), {"uid": source_uid}).fetchone()
    return existing[0]


def _insert_detalle(
    db: Session,
    lote_id: int,
    items: list[LoteDetalleResult],
    proveedor_id: Optional[int],
) -> None:
    for i, item in enumerate(items, start=1):
        compra_id = item.compra_id
        if compra_id is None and item.folio and proveedor_id:
            compra_id = _find_compra_id(db, item.folio, proveedor_id)
        db.execute(text("""
            INSERT INTO pagos_proveedor_lote_detalle
                (lote_id, line_no, compra_id, tipo, folio, monto)
            VALUES
                (:lid, :lno, :cid, :tipo, :folio, :monto)
            ON CONFLICT (lote_id, line_no) DO NOTHING
        """), {
            "lid": lote_id,
            "lno": i,
            "cid": compra_id,
            "tipo": item.tipo,
            "folio": item.folio,
            "monto": item.monto,
        })
