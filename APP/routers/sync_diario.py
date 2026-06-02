"""
POST /sync/diario

Master sync endpoint: runs /import/pos-compras then /sync/pagos-proveedor
with auto-calculated windows based on last successful sync in sync_control.

Windows (auto):
  compras: last POS_COMPRAS success  - 2 days  → today
  pagos:   last POS_PAGOS_PROVEEDOR  - 5 days  → today

Override: ?fecha_inicio=YYYY-MM-DD  (applies to both)
          ?fecha_fin=YYYY-MM-DD     (default: today)

Idempotent — safe to run multiple times per day.
If POS connection fails in compras, pagos step is skipped.
If compras has partial errors, pagos still runs.
"""

import logging
from datetime import date, datetime, timedelta
from typing import Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from sqlalchemy import text

from APP.db import get_db
from APP.pos_db import get_pos_db
from APP.routers.pos_compras import import_pos_compras, ComprasBody
from APP.routers.sync_pagos_proveedor import sync_pagos_proveedor
from APP.routers.pos_sync import sync_proveedores

logger = logging.getLogger("sync_diario")

router = APIRouter(prefix="/sync", tags=["Sync - Diario"])

_POS_CONN_KEYWORDS = ("can't connect", "connection refused", "lost connection",
                      "operationalerror", "mysql", "2003", "2006", "timed out")


# ── Helpers ───────────────────────────────────────────────────────────────────

def _get_last_sync_date(db: Session, proceso: str) -> Optional[date]:
    row = db.execute(text("""
        SELECT fecha_fin FROM sync_control
        WHERE proceso = :p AND status IN ('OK', 'PARCIAL')
        ORDER BY id DESC LIMIT 1
    """), {"p": proceso}).first()
    if row is None:
        return None
    v = row[0]
    if isinstance(v, datetime):   # datetime is subclass of date — extract .date() first
        return v.date()
    if isinstance(v, date):
        return v
    return date.fromisoformat(str(v)[:10])


def _log(db: Session, proceso: str, fi: date, ff: date,
         status: str, ok: int, err: int, notes: str = None) -> None:
    db.execute(text("""
        INSERT INTO sync_control
            (proceso, fecha_inicio, fecha_fin, status, registros_ok, registros_err, notes)
        VALUES (:p, :fi, :ff, :s, :ok, :err, :n)
    """), {"p": proceso, "fi": fi, "ff": ff, "s": status, "ok": ok, "err": err, "n": notes})
    db.commit()


def _is_pos_conn_error(e: Exception) -> bool:
    return any(k in str(e).lower() for k in _POS_CONN_KEYWORDS)


# ── Result mappers ────────────────────────────────────────────────────────────

def _map_compras(result: dict | None, status: str, error: str | None) -> dict:
    if result is None:
        return {
            "status": status,
            "compras_procesadas": 0,
            "movimientos_fisico": 0,
            "movimientos_fiscal_pos": 0,
            "productos_auto_creados": 0,
            "duplicados_saltados": 0,
            "prod_prov_omitidos": 0,
            "warnings": [],
            "errores": [{"motivo": error}] if error else [],
        }
    return {
        "status":                 status,
        "compras_procesadas":     result.get("compras_procesadas", 0),
        "movimientos_fisico":     result.get("movimientos_fisico", 0),
        "movimientos_fiscal_pos": result.get("movimientos_fiscal_pos", 0),
        "productos_auto_creados": result.get("productos_auto_creados", 0),
        "duplicados_saltados":    result.get("duplicados_saltados", 0),
        "prod_prov_omitidos":     result.get("prod_prov_omitidos", 0),
        "warnings":               result.get("advertencias", []),
        "errores":                result.get("errores", []),
    }


def _map_pagos(result, status: str, error: str | None) -> dict:
    if result is None:
        return {
            "status": status,
            "lotes_insertados": 0,
            "lotes_actualizados": 0,
            "detalle_rows_written": 0,
            "conflictos_manual": 0,
            "skipped_no_supplier": 0,
            "total_neto": 0.0,
            "warnings": [],
            "errores": [{"motivo": error}] if error else [],
        }
    lotes   = result.lotes
    created = [l for l in lotes if l.action == "CREATED"]
    updated = [l for l in lotes if l.action == "UPDATED"]
    active  = created + updated

    warnings = []
    for l in lotes:
        if l.conflict_note:
            warnings.append({
                "tipo": "CONFLICT",
                "uid": l.source_uid,
                "detalle": l.conflict_note,
            })
        if l.proveedor_id is None and l.action != "SKIPPED":
            warnings.append({
                "tipo": "SIN_PROVEEDOR",
                "uid": l.source_uid,
                "detalle": f"POS proveedor {l.pos_prov_id} sin match — ejecutar /sync/proveedores",
            })

    return {
        "status":              status,
        "lotes_insertados":    len(created),
        "lotes_actualizados":  len(updated),
        "detalle_rows_written": sum(len(l.detalle) for l in active),
        "conflictos_manual":   result.conflicts,
        "skipped_no_supplier": sum(1 for l in lotes if l.proveedor_id is None and l.action != "SKIPPED"),
        "total_neto":          round(sum(l.total for l in active), 2),
        "warnings":            warnings,
        "errores":             [],
    }


# ── Endpoint ──────────────────────────────────────────────────────────────────

@router.post("/diario")
def sync_diario(
    fecha_inicio: Optional[date] = Query(None, description="Override inicio (aplica a ambos syncs)"),
    fecha_fin:    Optional[date] = Query(None, description="Override fin (default: hoy)"),
    db:     Session = Depends(get_db),
    pos_db: Session = Depends(get_pos_db),
):
    today = date.today()
    ff    = fecha_fin or today

    # ── Auto-calculate windows ────────────────────────────────────────────────
    if fecha_inicio:
        fi_compras = fecha_inicio
        fi_pagos   = fecha_inicio
    else:
        last_compras = _get_last_sync_date(db, "POS_COMPRAS")
        fi_compras   = (last_compras - timedelta(days=2)) if last_compras else (today - timedelta(days=7))

        last_pagos = _get_last_sync_date(db, "POS_PAGOS_PROVEEDOR")
        fi_pagos   = (last_pagos - timedelta(days=5)) if last_pagos else (today - timedelta(days=7))

    # Safety clamp: fi_* must never exceed ff
    if fi_compras > ff:
        fi_compras = ff - timedelta(days=7)
    if fi_pagos > ff:
        fi_pagos = ff - timedelta(days=7)

    logger.info("sync_diario start fi_compras=%s fi_pagos=%s ff=%s", fi_compras, fi_pagos, ff)

    # ── Step 0: Sync proveedores (must run before compras to avoid missing supplier errors) ──
    proveedores_stats = {"created": 0, "updated": 0, "skipped": 0, "errors": []}
    try:
        result_prov = sync_proveedores(pg=db, pos=pos_db)
        proveedores_stats = {
            "created": result_prov.get("created", 0),
            "updated": result_prov.get("updated", 0),
            "errors":  result_prov.get("errors", []),
        }
    except Exception as e:
        logger.warning("sync_diario: sync_proveedores failed (non-fatal): %s", e)

    # ── Step 1: Sync compras ──────────────────────────────────────────────────
    compras_result  = None
    compras_status  = "ERROR"
    compras_error   = None
    pos_conn_failed = False

    try:
        body           = ComprasBody(fecha_inicio=fi_compras, fecha_fin=ff)
        compras_result = import_pos_compras(body, pg=db, pos=pos_db)
        compras_status = compras_result.get("status", "OK")
    except Exception as e:
        logger.exception("sync_diario: import_pos_compras failed")
        compras_status  = "ERROR"
        compras_error   = str(e)
        pos_conn_failed = _is_pos_conn_error(e)
        try:
            db.rollback()
        except Exception:
            pass

    # ── Step 2: Sync pagos ────────────────────────────────────────────────────
    pagos_result_raw = None
    pagos_status     = "ERROR"
    pagos_error      = None

    if pos_conn_failed:
        pagos_status = "SKIPPED"
        pagos_error  = "Omitido: error de conexión POS en paso de compras"
    else:
        try:
            pagos_result_raw = sync_pagos_proveedor(
                fecha_inicio=fi_pagos,
                fecha_fin=ff,
                dry_run=False,
                force_replace_pos=False,
                skip_on_conflict=True,
                rebuild_existing=False,
                db=db,
                pos_db=pos_db,
            )
            pagos_status = "OK"
        except Exception as e:
            logger.exception("sync_diario: sync_pagos_proveedor failed")
            pagos_status = "ERROR"
            pagos_error  = str(e)
            try:
                db.rollback()
            except Exception:
                pass

    # ── Map results ───────────────────────────────────────────────────────────
    compras_out = _map_compras(compras_result, compras_status, compras_error)
    pagos_out   = _map_pagos(pagos_result_raw, pagos_status, pagos_error)

    # ── Log POS_PAGOS_PROVEEDOR ───────────────────────────────────────────────
    _log(db, "POS_PAGOS_PROVEEDOR", fi_pagos, ff, pagos_status,
         pagos_out["lotes_insertados"] + pagos_out["lotes_actualizados"],
         len(pagos_out["errores"]))

    # ── Overall status ────────────────────────────────────────────────────────
    s = {compras_status, pagos_status}
    if s <= {"OK"}:
        overall = "OK"
    elif s <= {"ERROR", "SKIPPED"} and "OK" not in s and "PARCIAL" not in s:
        overall = "ERROR"
    else:
        overall = "PARCIAL"

    # ── Log SYNC_DIARIO ───────────────────────────────────────────────────────
    _log(db, "SYNC_DIARIO", min(fi_compras, fi_pagos), ff, overall,
         compras_out["compras_procesadas"],
         len(compras_out["errores"]) + len(pagos_out["errores"]),
         notes=f"compras:{compras_status} pagos:{pagos_status}")

    logger.info("sync_diario done overall=%s", overall)

    return {
        "ok":                   overall in ("OK", "PARCIAL"),
        "status":               overall,
        "fecha_inicio_compras": str(fi_compras),
        "fecha_inicio_pagos":   str(fi_pagos),
        "fecha_fin":            str(ff),
        "proveedores":          proveedores_stats,
        "compras":              compras_out,
        "pagos":                pagos_out,
    }
