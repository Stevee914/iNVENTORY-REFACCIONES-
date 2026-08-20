"""
Conciliación de Cobranza manual vs POS — SOLO LECTURA.

Separado a propósito de cobranza_manual.py:
  - cobranza_manual        = captura / gestión manual (ESCRIBE cobranza_manual*).
  - conciliacion_cobranza  = lectura cruzada POS/manual para EVITAR DUPLICADOS.

Este módulo SOLO ejecuta SELECT. Lee `facturas`/`pagos` (POS) y `cobranza_manual*`
únicamente para DETECTAR solapamientos antes de capturar una nota. NUNCA escribe
(ni POS ni manual) y NUNCA suma/combina montos POS con saldos manuales.

Veredictos: YA_POS · YA_MANUAL · CANDIDATO_MANUAL · REVISAR_MANUAL
"""
from fastapi import APIRouter, Depends, Query, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import text
from datetime import date, timedelta
from typing import Optional

from APP.db import get_db
from APP.helpers import normalize_text

router = APIRouter(tags=["Conciliación Cobranza"])

TOL = 0.01


def _f(v):
    return float(v) if v is not None else None


@router.get("/conciliacion-cobranza")
def conciliacion_cobranza(
    monto: float = Query(..., description="Monto a conciliar (requerido, > 0)"),
    cliente: Optional[str] = Query(default=None, description="Nombre (ILIKE); opcional si va cliente_id"),
    cliente_id: Optional[int] = Query(default=None, description="Id exacto; tiene prioridad sobre 'cliente'"),
    fecha: Optional[date] = Query(default=None, description="Fecha de referencia para el rango/heurística"),
    dias_rango: int = Query(default=7, ge=0, le=90),
    incluir_pagadas: bool = Query(default=True, description="Si false, ignora facturas POS ya pagadas por completo"),
    db: Session = Depends(get_db),
):
    if monto is None or monto <= 0:
        raise HTTPException(status_code=400, detail="monto debe ser mayor a 0")

    params_echo = {
        "cliente": cliente, "cliente_id": cliente_id, "monto": round(monto, 2),
        "fecha": str(fecha) if fecha else None, "dias_rango": dias_rango,
        "incluir_pagadas": incluir_pagadas,
    }

    # ── 1. Resolver cliente ────────────────────────────────────────────────
    if cliente_id is not None:
        cli_rows = db.execute(text(
            "SELECT id, nombre, rfc, pos_cliente_id FROM clientes WHERE id = :id"
        ), {"id": cliente_id}).mappings().all()
    elif cliente and cliente.strip():
        like = f"%{normalize_text(cliente).upper()}%"
        cli_rows = db.execute(text(
            "SELECT id, nombre, rfc, pos_cliente_id FROM clientes "
            "WHERE UPPER(nombre) LIKE :like ORDER BY nombre LIMIT 20"
        ), {"like": like}).mappings().all()
    else:
        raise HTTPException(status_code=400, detail="Se requiere 'cliente' o 'cliente_id'")

    cliente_match = [dict(r) for r in cli_rows]

    def resp(veredicto, razon, recomendacion, **extra):
        return {
            "veredicto": veredicto,
            "razon": razon,
            "parametros": params_echo,
            "cliente_match": cliente_match,
            "facturas_pos_encontradas": extra.get("facturas_pos", []),
            "pagos_pos_encontrados": extra.get("pagos_pos", []),
            "relaciones_manual_encontradas": extra.get("rel_manual", []),
            "cargos_manual_encontrados": extra.get("cargos_manual", []),
            "pagos_manual_encontrados": extra.get("pagos_manual", []),
            "facturas_cercanas": extra.get("facturas_cercanas", []),
            "recomendacion": recomendacion,
        }

    if len(cli_rows) == 0:
        return resp("REVISAR_MANUAL", "No se encontró cliente que coincida.",
                    "Verificar nombre o usar cliente_id exacto antes de capturar.")
    if len(cli_rows) > 1:
        return resp("REVISAR_MANUAL", f"{len(cli_rows)} clientes coinciden con el nombre (ambiguo).",
                    "Especificar cliente_id exacto antes de capturar.")

    cid = cli_rows[0]["id"]

    # Montos objetivo con variantes de IVA (16%)
    m_ex = round(monto, 2)
    m_net = round(monto / 1.16, 2)   # el monto sin IVA
    m_gro = round(monto * 1.16, 2)   # el monto con IVA
    tset = {"exacto": m_ex, "monto/1.16": m_net, "monto*1.16": m_gro}
    p = {"cid": cid, "ex": m_ex, "net": m_net, "gro": m_gro, "tol": TOL}

    def match_type(v):
        v = float(v)
        for label, tv in tset.items():
            if abs(v - tv) < TOL:
                return label
        return None

    # ── 2. POS: facturas por monto (exacto o variante IVA) + su pagado ─────
    fac_rows = db.execute(text("""
        SELECT f.id, f.folio, f.monto, f.subtotal, f.iva, f.fecha, f.estatus,
               f.origen, f.tipo_documento, f.metodo_pago,
               COALESCE((SELECT SUM(pg.monto) FROM pagos pg WHERE pg.factura_id = f.id), 0) AS pagado
        FROM facturas f
        WHERE f.cliente_id = :cid
          AND (ABS(f.monto - :ex) < :tol OR ABS(f.monto - :net) < :tol OR ABS(f.monto - :gro) < :tol)
        ORDER BY f.fecha, f.id
    """), p).mappings().all()

    facturas_pos = []
    for f in fac_rows:
        pagado = float(f["pagado"])
        if not incluir_pagadas and pagado >= float(f["monto"]) - TOL:
            continue  # factura ya pagada por completo: se ignora si incluir_pagadas=false
        facturas_pos.append({
            "id": f["id"], "folio": f["folio"], "fecha": str(f["fecha"]),
            "monto": _f(f["monto"]), "subtotal": _f(f["subtotal"]), "iva": _f(f["iva"]),
            "pagado": round(pagado, 2), "estatus": f["estatus"], "origen": f["origen"],
            "tipo_documento": f["tipo_documento"], "match": match_type(f["monto"]),
        })
    fac_ids = [f["id"] for f in facturas_pos]

    # Pagos POS por monto (variantes) o vinculados a las facturas coincidentes
    pg_rows = db.execute(text("""
        SELECT pg.id, pg.factura_id, pg.monto, pg.fecha, pg.metodo_pago, pg.referencia, f.folio
        FROM pagos pg JOIN facturas f ON f.id = pg.factura_id
        WHERE f.cliente_id = :cid
          AND ( pg.factura_id = ANY(:fids)
                OR ABS(pg.monto - :ex) < :tol OR ABS(pg.monto - :net) < :tol OR ABS(pg.monto - :gro) < :tol )
        ORDER BY pg.fecha, pg.id
    """), {**p, "fids": fac_ids or [0]}).mappings().all()
    pagos_pos = [{
        "id": r["id"], "factura_id": r["factura_id"], "folio": r["folio"],
        "fecha": str(r["fecha"]), "monto": _f(r["monto"]),
        "metodo_pago": r["metodo_pago"], "referencia": r["referencia"],
    } for r in pg_rows]

    # Facturas cercanas por fecha (heurística de facturación combinada)
    facturas_cercanas = []
    if fecha is not None:
        fc_rows = db.execute(text("""
            SELECT id, folio, monto, fecha, estatus, origen, tipo_documento
            FROM facturas
            WHERE cliente_id = :cid AND fecha BETWEEN :fi AND :ff
            ORDER BY fecha, id
        """), {"cid": cid, "fi": fecha - timedelta(days=dias_rango), "ff": fecha + timedelta(days=dias_rango)}).mappings().all()
        facturas_cercanas = [{
            "id": r["id"], "folio": r["folio"], "fecha": str(r["fecha"]),
            "monto": _f(r["monto"]), "estatus": r["estatus"], "origen": r["origen"],
            "tipo_documento": r["tipo_documento"],
        } for r in fc_rows]

    # ── 3. Cobranza manual del cliente ─────────────────────────────────────
    rel_rows = db.execute(text("""
        SELECT cm.id, cm.fecha_relacion, cm.numero_notas, cm.importe_total, cm.estatus,
               COALESCE((SELECT SUM(mp.monto) FROM cobranza_manual_pagos mp WHERE mp.cobranza_manual_id = cm.id), 0) AS pagado
        FROM cobranza_manual cm WHERE cm.cliente_id = :cid ORDER BY cm.id
    """), {"cid": cid}).mappings().all()
    rel_manual = []
    for r in rel_rows:
        saldo = float(r["importe_total"]) - float(r["pagado"])
        rel_manual.append({
            "id": r["id"], "fecha_relacion": str(r["fecha_relacion"]), "numero_notas": r["numero_notas"],
            "importe_total": _f(r["importe_total"]), "pagado": _f(r["pagado"]),
            "saldo": round(saldo, 2), "estatus": r["estatus"],
        })

    cargos_manual, pagos_manual = [], []
    if rel_rows:
        rel_ids = [r["id"] for r in rel_rows]
        cg_rows = db.execute(text("""
            SELECT id, cobranza_manual_id, fecha_cargo, numero_notas, importe, origen
            FROM cobranza_manual_cargos
            WHERE cobranza_manual_id = ANY(:rids)
              AND (ABS(importe - :ex) < :tol OR ABS(importe - :net) < :tol OR ABS(importe - :gro) < :tol)
            ORDER BY fecha_cargo, id
        """), {**p, "rids": rel_ids}).mappings().all()
        cargos_manual = [{
            "id": r["id"], "cobranza_manual_id": r["cobranza_manual_id"], "fecha_cargo": str(r["fecha_cargo"]),
            "numero_notas": r["numero_notas"], "importe": _f(r["importe"]), "origen": r["origen"],
            "match": match_type(r["importe"]),
        } for r in cg_rows]
        pm_rows = db.execute(text("""
            SELECT id, cobranza_manual_id, fecha_pago, monto, metodo_pago, referencia
            FROM cobranza_manual_pagos
            WHERE cobranza_manual_id = ANY(:rids)
              AND (ABS(monto - :ex) < :tol OR ABS(monto - :net) < :tol OR ABS(monto - :gro) < :tol)
            ORDER BY fecha_pago, id
        """), {**p, "rids": rel_ids}).mappings().all()
        pagos_manual = [{
            "id": r["id"], "cobranza_manual_id": r["cobranza_manual_id"], "fecha_pago": str(r["fecha_pago"]),
            "monto": _f(r["monto"]), "metodo_pago": r["metodo_pago"], "referencia": r["referencia"],
        } for r in pm_rows]

    # ── 4. Clasificación ───────────────────────────────────────────────────
    hay_fac = len(facturas_pos) > 0
    hay_pago_pos = len(pagos_pos) > 0
    hay_cargo_manual = len(cargos_manual) > 0
    # Heurística de facturación combinada: factura cercana (no ya coincidente) cuyo
    # monto es >= al buscado → podría incluirlo (ej. nota de $8,750 dentro de factura de $10,740).
    combinada = [f for f in facturas_cercanas if f["id"] not in fac_ids and (f["monto"] or 0) >= m_ex - TOL]

    if hay_fac and hay_cargo_manual:
        return resp("REVISAR_MANUAL",
                    "El monto aparece EN POS (factura) Y en cobranza manual (cargo): posible duplicación existente.",
                    "Revisar y depurar el duplicado; no volver a capturar.",
                    facturas_pos=facturas_pos, pagos_pos=pagos_pos, rel_manual=rel_manual,
                    cargos_manual=cargos_manual, pagos_manual=pagos_manual, facturas_cercanas=facturas_cercanas)
    if hay_fac:
        if hay_pago_pos:
            razon = "Factura POS por el monto CON pago POS por el mismo importe."
            reco = "NO capturar en cobranza manual: ya está facturado y pagado en POS."
        else:
            razon = "Factura POS por el monto SIN pago registrado."
            reco = "NO capturar en cobranza manual: ya está facturado en POS; cobrar por POS."
        return resp("YA_POS", razon, reco,
                    facturas_pos=facturas_pos, pagos_pos=pagos_pos, rel_manual=rel_manual,
                    cargos_manual=cargos_manual, pagos_manual=pagos_manual, facturas_cercanas=facturas_cercanas)
    if hay_cargo_manual:
        return resp("YA_MANUAL",
                    "Ya existe un cargo en cobranza manual por el monto.",
                    "NO duplicar: el cargo ya está en cobranza manual.",
                    rel_manual=rel_manual, cargos_manual=cargos_manual,
                    pagos_manual=pagos_manual, facturas_cercanas=facturas_cercanas)
    if combinada:
        return resp("REVISAR_MANUAL",
                    f"No hay factura exacta, pero {len(combinada)} factura(s) cercana(s) tienen monto >= al buscado y podrían incluirlo (posible facturación combinada).",
                    "Revisar manualmente si el importe ya está incluido en una factura mayor antes de capturar.",
                    rel_manual=rel_manual, facturas_cercanas=facturas_cercanas)
    return resp("CANDIDATO_MANUAL",
                "No hay factura POS ni cargo manual por el monto (ni facturas cercanas que lo incluyan).",
                "Candidato válido para captura manual; confirmar datos reales antes de crear el cargo.",
                rel_manual=rel_manual, facturas_cercanas=facturas_cercanas)
