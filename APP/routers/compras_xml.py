from fastapi import APIRouter, Depends, UploadFile, File, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import text
from APP.db import get_db
from pydantic import BaseModel
from typing import Optional
import xml.etree.ElementTree as ET

router = APIRouter(prefix="/compras", tags=["compras-xml"])

# CFDI namespaces
CFDI_NS = {
    "cfdi": "http://www.sat.gob.mx/cfd/4",
    "tfd": "http://www.sat.gob.mx/TimbreFiscalDigital",
}

# Service line detection
SERVICE_NO_IDENT = {"SEGURO", "FLETE", "MANIOBRA", "COMISION", "ENVIO", "REEXPEDICION"}
SERVICE_CLAVE_SAT = {"84131500", "78101800", "78111700", "78111800", "78121600"}


def normalize_rfc(rfc: str) -> str:
    """Remove spaces, dashes, uppercase."""
    if not rfc:
        return ""
    return rfc.strip().upper().replace(" ", "").replace("-", "")


def normalize_code(value: str) -> str:
    """Uppercase, strip spaces and dashes."""
    if not value:
        return ""
    return value.strip().upper().replace(" ", "").replace("-", "")


def is_service_line(no_identificacion: str, clave_prod_serv: str) -> bool:
    """Detect non-inventory lines (insurance, freight, etc.)."""
    if normalize_code(no_identificacion) in SERVICE_NO_IDENT:
        return True
    if clave_prod_serv in SERVICE_CLAVE_SAT:
        return True
    return False


def parse_cfdi(xml_bytes: bytes) -> dict:
    """Parse CFDI 4.0 XML and extract header + line items."""
    root = ET.fromstring(xml_bytes)
    ns = CFDI_NS

    emisor = root.find("cfdi:Emisor", ns)
    receptor = root.find("cfdi:Receptor", ns)
    tfd = root.find(".//tfd:TimbreFiscalDigital", ns)
    impuestos_global = root.find("cfdi:Impuestos", ns)

    header = {
        "uuid": tfd.get("UUID") if tfd is not None else None,
        "version": root.get("Version"),
        "serie": root.get("Serie") or "",
        "folio": root.get("Folio") or "",
        "fecha": root.get("Fecha"),
        "forma_pago": root.get("FormaPago"),
        "metodo_pago": root.get("MetodoPago"),
        "moneda": root.get("Moneda"),
        "subtotal": float(root.get("SubTotal", 0)),
        "descuento_total": float(root.get("Descuento", 0)),
        "total": float(root.get("Total", 0)),
        "emisor_rfc": normalize_rfc(emisor.get("Rfc")) if emisor is not None else None,
        "emisor_nombre": emisor.get("Nombre") if emisor is not None else None,
        "receptor_rfc": normalize_rfc(receptor.get("Rfc")) if receptor is not None else None,
        "receptor_nombre": receptor.get("Nombre") if receptor is not None else None,
    }

    # Global taxes
    if impuestos_global is not None:
        header["iva_total"] = float(impuestos_global.get("TotalImpuestosTrasladados", 0))
    else:
        header["iva_total"] = 0.0

    # Line items
    conceptos = []
    for c in root.findall(".//cfdi:Concepto", ns):
        line = {
            "clave_prod_serv": c.get("ClaveProdServ", ""),
            "no_identificacion": c.get("NoIdentificacion", ""),
            "descripcion": c.get("Descripcion", ""),
            "cantidad": float(c.get("Cantidad", 0)),
            "clave_unidad": c.get("ClaveUnidad", ""),
            "unidad": c.get("Unidad", ""),
            "valor_unitario": float(c.get("ValorUnitario", 0)),
            "importe": float(c.get("Importe", 0)),
            "descuento": float(c.get("Descuento", 0)),
        }

        # Line-level tax
        traslado = c.find(".//cfdi:Traslado", ns)
        if traslado is not None:
            line["tax_base"] = float(traslado.get("Base", 0))
            line["tax_tasa"] = float(traslado.get("TasaOCuota", 0))
            line["tax_importe"] = float(traslado.get("Importe", 0))
        else:
            line["tax_base"] = line["importe"] - line["descuento"]
            line["tax_tasa"] = 0
            line["tax_importe"] = 0

        conceptos.append(line)

    header["conceptos"] = conceptos
    return header


def resolve_supplier(db: Session, emisor_rfc: str, emisor_nombre: str) -> dict | None:
    """Find supplier by RFC. Returns {id, nombre, rfc} or None."""
    if not emisor_rfc:
        return None

    row = db.execute(
        text("""
            SELECT id, nombre, rfc
            FROM proveedores
            WHERE UPPER(REPLACE(REPLACE(rfc, ' ', ''), '-', '')) = :rfc
            LIMIT 1
        """),
        {"rfc": emisor_rfc},
    ).mappings().first()

    if row:
        return dict(row)
    return None


def match_line(db: Session, proveedor_id: int, no_identificacion: str) -> dict:
    """
    Product matching pipeline for one XML line item.
    Returns: {status_match, matched_by, product_id, candidates}
    """
    code = normalize_code(no_identificacion)
    if not code:
        return {"status_match": "UNRESOLVED", "matched_by": None, "product_id": None, "candidates": []}

    # Paso 1: Match exacto by producto_proveedor (supplier_sku)
    rows = db.execute(
        text("""
            SELECT pp.product_id, p.sku, p.name
            FROM producto_proveedor pp
            JOIN productos p ON p.id = pp.product_id
            WHERE pp.proveedor_id = :prov_id
              AND UPPER(REPLACE(REPLACE(pp.supplier_sku, '-', ''), ' ', '')) = :code
        """),
        {"prov_id": proveedor_id, "code": code},
    ).mappings().all()

    if len(rows) == 1:
        return {
            "status_match": "MATCHED",
            "matched_by": "AUTO_PP",
            "product_id": rows[0]["product_id"],
            "candidates": [dict(r) for r in rows],
        }
    if len(rows) > 1:
        return {
            "status_match": "SUGGESTED_MATCH",
            "matched_by": "AUTO_PP",
            "product_id": None,
            "candidates": [dict(r) for r in rows],
        }

    # Paso 2: Fallback - match by SKU or codigo_pos in productos
    rows2 = db.execute(
        text("""
            SELECT id AS product_id, sku, name
            FROM productos
            WHERE UPPER(REPLACE(REPLACE(sku, '-', ''), ' ', '')) = :code
               OR UPPER(REPLACE(REPLACE(codigo_pos, '-', ''), ' ', '')) LIKE '%' || :code
            LIMIT 5
        """),
        {"code": code},
    ).mappings().all()

    if len(rows2) == 1:
        return {
            "status_match": "SUGGESTED_MATCH",
            "matched_by": "AUTO_SKU",
            "product_id": None,
            "candidates": [dict(r) for r in rows2],
        }
    if len(rows2) > 1:
        return {
            "status_match": "SUGGESTED_MATCH",
            "matched_by": "AUTO_SKU",
            "product_id": None,
            "candidates": [dict(r) for r in rows2],
        }

    # Paso 3: No match
    return {"status_match": "UNRESOLVED", "matched_by": None, "product_id": None, "candidates": []}


def recalculate_compra_totals(db: Session, compra_id: int):
    """Recalculate compra subtotal/iva/total based on non-excluded, non-service lines and financial discount."""

    lineas = db.execute(
        text("""
            SELECT precio_unit, cantidad, iva, descuento
            FROM compras_detalle
            WHERE compra_id = :cid
              AND status_match != 'EXCLUDED'
              AND es_servicio = FALSE
        """),
        {"cid": compra_id},
    ).mappings().all()

    servicios = db.execute(
        text("""
            SELECT precio_unit, cantidad, iva
            FROM compras_detalle
            WHERE compra_id = :cid
              AND status_match != 'EXCLUDED'
              AND es_servicio = TRUE
        """),
        {"cid": compra_id},
    ).mappings().all()

    subtotal_productos = sum(float(l["precio_unit"] or 0) * float(l["cantidad"] or 0) for l in lineas)
    iva_productos = sum(float(l["iva"] or 0) for l in lineas)

    subtotal_servicios = sum(float(s["precio_unit"] or 0) * float(s["cantidad"] or 0) for s in servicios)
    iva_servicios = sum(float(s["iva"] or 0) for s in servicios)

    subtotal_before_discount = subtotal_productos + subtotal_servicios
    iva_before_discount = iva_productos + iva_servicios

    compra = db.execute(
        text("SELECT descuento_financiero FROM compras WHERE id = :id"),
        {"id": compra_id},
    ).mappings().first()

    descuento_pct = float(compra["descuento_financiero"] or 0) / 100.0

    subtotal_final = round(subtotal_before_discount * (1 - descuento_pct), 2)
    iva_final = round(iva_before_discount * (1 - descuento_pct), 2)
    total_final = round(subtotal_final + iva_final, 2)

    db.execute(
        text("""
            UPDATE compras
            SET subtotal = :subtotal, iva = :iva, total = :total
            WHERE id = :id
        """),
        {"subtotal": subtotal_final, "iva": iva_final, "total": total_final, "id": compra_id},
    )


@router.post("/upload-xml")
async def upload_xml(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
):
    """
    Upload a CFDI 4.0 XML invoice.
    Creates a compra in REVIEW status with detail lines.
    Runs automatic product matching pipeline.
    """
    # Validate file type
    if not file.filename or not file.filename.lower().endswith(".xml"):
        raise HTTPException(status_code=400, detail="Solo se aceptan archivos XML (.xml)")

    xml_bytes = await file.read()

    # Parse XML
    try:
        parsed = parse_cfdi(xml_bytes)
    except ET.ParseError as e:
        raise HTTPException(status_code=400, detail=f"Error parseando XML: {str(e)}")
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Error procesando XML: {str(e)}")

    # Validate UUID exists
    uuid = parsed.get("uuid")
    if not uuid:
        raise HTTPException(status_code=400, detail="El XML no contiene UUID (TimbreFiscalDigital)")

    # Check duplicate UUID
    existing = db.execute(
        text("SELECT id FROM compras WHERE uuid_fiscal = :uuid"),
        {"uuid": uuid},
    ).scalar()
    if existing:
        raise HTTPException(
            status_code=409,
            detail=f"Esta factura ya fue importada (UUID: {uuid}, compra_id: {existing})"
        )

    # Resolve supplier by RFC
    supplier = resolve_supplier(db, parsed["emisor_rfc"], parsed["emisor_nombre"])
    supplier_resolved = supplier is not None
    proveedor_id = supplier["id"] if supplier else None

    # Build folio_factura from serie + folio
    serie = parsed.get("serie", "")
    folio = parsed.get("folio", "")
    folio_factura = f"{serie}-{folio}" if serie else folio

    # Determine metodo_pago for estatus default
    metodo_pago_xml = parsed.get("metodo_pago", "")
    # PPD = credit, PUE = paid
    estatus_pago = "PAGADA" if metodo_pago_xml == "PUE" else "PENDIENTE"

    # Create compra header
    try:
        compra_id = db.execute(
            text("""
                INSERT INTO compras
                    (proveedor_id, folio_factura, fecha, subtotal, iva, total,
                     estatus, metodo_pago, notas, origen,
                     estatus_recepcion, estatus_workflow, uuid_fiscal,
                     subtotal_original, iva_original, total_original,
                     created_at, updated_at)
                VALUES
                    (:proveedor_id, :folio_factura, CURRENT_DATE, :subtotal, :iva, :total,
                     :estatus, :metodo_pago, :notas, 'XML',
                     'PENDIENTE', 'REVIEW', :uuid_fiscal,
                     :subtotal_original, :iva_original, :total_original,
                     NOW(), NOW())
                RETURNING id
            """),
            {
                "proveedor_id": proveedor_id,
                "folio_factura": folio_factura,
                "subtotal": parsed["subtotal"] - parsed["descuento_total"],
                "iva": parsed["iva_total"],
                "total": parsed["total"],
                "estatus": estatus_pago,
                "metodo_pago": metodo_pago_xml,
                "notas": f"Importado desde XML. Emisor: {parsed.get('emisor_nombre', '')}",
                "uuid_fiscal": uuid,
                "subtotal_original": parsed["subtotal"] - parsed["descuento_total"],
                "iva_original": parsed["iva_total"],
                "total_original": parsed["total"],
            },
        ).scalar()
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Error creando compra: {str(e)}")

    # Process line items
    line_results = []
    counts = {"MATCHED": 0, "SUGGESTED_MATCH": 0, "UNRESOLVED": 0, "SERVICE": 0}

    for i, concepto in enumerate(parsed["conceptos"]):
        no_ident = concepto["no_identificacion"]
        clave_sat = concepto["clave_prod_serv"]

        # Check if service line
        if is_service_line(no_ident, clave_sat):
            status_match = "SERVICE"
            matched_by = "SERVICE_AUTO"
            product_id = None
            candidates = []
        elif not supplier_resolved:
            # Cannot match without supplier
            status_match = "UNRESOLVED"
            matched_by = None
            product_id = None
            candidates = []
        else:
            # Run matching pipeline
            match = match_line(db, proveedor_id, no_ident)
            status_match = match["status_match"]
            matched_by = match["matched_by"]
            product_id = match["product_id"]
            candidates = match["candidates"]

        # Calculate unit cost after discount (for precio_unit)
        qty = concepto["cantidad"] or 1
        precio_unit = round((concepto["importe"] - concepto["descuento"]) / qty, 4)

        # Insert detail line
        try:
            db.execute(
                text("""
                    INSERT INTO compras_detalle
                        (compra_id, product_id, cantidad, precio_unit, supplier_sku,
                         descripcion_xml, codigo_proveedor, clave_prod_serv,
                         descuento, iva, status_match, matched_by, es_servicio)
                    VALUES
                        (:compra_id, :product_id, :cantidad, :precio_unit, :supplier_sku,
                         :descripcion_xml, :codigo_proveedor, :clave_prod_serv,
                         :descuento, :iva, :status_match, :matched_by, :es_servicio)
                """),
                {
                    "compra_id": compra_id,
                    "product_id": product_id,
                    "cantidad": concepto["cantidad"],
                    "precio_unit": precio_unit,
                    "supplier_sku": no_ident,
                    "descripcion_xml": concepto["descripcion"],
                    "codigo_proveedor": no_ident,
                    "clave_prod_serv": clave_sat,
                    "descuento": concepto["descuento"],
                    "iva": concepto["tax_importe"],
                    "status_match": status_match,
                    "matched_by": matched_by,
                    "es_servicio": status_match == "SERVICE",
                },
            )
        except Exception as e:
            db.rollback()
            raise HTTPException(status_code=500, detail=f"Error insertando linea {i+1}: {str(e)}")

        counts[status_match] = counts.get(status_match, 0) + 1
        line_results.append({
            "linea": i + 1,
            "codigo_proveedor": no_ident,
            "descripcion_xml": concepto["descripcion"],
            "cantidad": concepto["cantidad"],
            "precio_unit": precio_unit,
            "status_match": status_match,
            "matched_by": matched_by,
            "product_id": product_id,
            "candidates": candidates,
        })

    # If ALL product lines are MATCHED, auto-advance workflow to READY
    pending = counts.get("SUGGESTED_MATCH", 0) + counts.get("UNRESOLVED", 0)
    workflow_status = "READY" if pending == 0 else "REVIEW"

    if workflow_status == "READY":
        db.execute(
            text("UPDATE compras SET estatus_workflow = 'READY' WHERE id = :id"),
            {"id": compra_id},
        )

    db.commit()

    return {
        "ok": True,
        "compra_id": compra_id,
        "uuid": uuid,
        "folio_factura": folio_factura,
        "proveedor": {
            "resolved": supplier_resolved,
            "id": proveedor_id,
            "nombre": supplier["nombre"] if supplier else None,
            "rfc_xml": parsed["emisor_rfc"],
            "nombre_xml": parsed["emisor_nombre"],
        },
        "totales": {
            "subtotal": parsed["subtotal"],
            "descuento": parsed["descuento_total"],
            "iva": parsed["iva_total"],
            "total": parsed["total"],
        },
        "lineas": {
            "total": len(parsed["conceptos"]),
            "matched": counts.get("MATCHED", 0),
            "suggested": counts.get("SUGGESTED_MATCH", 0),
            "unresolved": counts.get("UNRESOLVED", 0),
            "service": counts.get("SERVICE", 0),
        },
        "estatus_workflow": workflow_status,
        "detalle": line_results,
    }


# ---------------------------------------------------------------------------
# Pydantic models for review/resolution endpoints
# ---------------------------------------------------------------------------

class ConfirmarMatchBody(BaseModel):
    product_id: int


class CrearProductoFromXmlBody(BaseModel):
    sku: str
    name: str
    marca: Optional[str] = None
    categoria_id: Optional[int] = None
    unit: str = "PZA"
    min_stock: float = 0
    price: float = 0
    precio_publico: Optional[float] = None
    codigo_cat: Optional[str] = None


# ---------------------------------------------------------------------------
# GET /compras/{compra_id}/revision
# ---------------------------------------------------------------------------

@router.get("/{compra_id}/revision")
def get_compra_revision(compra_id: int, db: Session = Depends(get_db)):
    """Get full review view of an XML purchase with match candidates."""

    compra = db.execute(
        text("""
            SELECT c.id, c.proveedor_id, c.folio_factura, c.fecha,
                   c.subtotal, c.iva, c.total, c.estatus, c.metodo_pago,
                   c.estatus_recepcion, c.estatus_workflow, c.uuid_fiscal,
                   c.origen, c.notas,
                   c.descuento_financiero, c.subtotal_original, c.iva_original, c.total_original,
                   p.nombre AS proveedor_nombre, p.rfc AS proveedor_rfc
            FROM compras c
            LEFT JOIN proveedores p ON p.id = c.proveedor_id
            WHERE c.id = :id
        """),
        {"id": compra_id},
    ).mappings().first()

    if not compra:
        raise HTTPException(status_code=404, detail="Compra no encontrada")

    lineas = db.execute(
        text("""
            SELECT cd.id, cd.product_id, cd.cantidad, cd.precio_unit,
                   cd.supplier_sku, cd.descripcion_xml, cd.codigo_proveedor,
                   cd.clave_prod_serv, cd.descuento, cd.iva,
                   cd.status_match, cd.matched_by, cd.es_servicio,
                   pr.sku AS product_sku, pr.name AS product_name
            FROM compras_detalle cd
            LEFT JOIN productos pr ON pr.id = cd.product_id
            WHERE cd.compra_id = :compra_id
            ORDER BY cd.id
        """),
        {"compra_id": compra_id},
    ).mappings().all()

    lineas_out = []
    for l in lineas:
        line_dict = dict(l)
        line_dict["candidates"] = []

        if l["status_match"] == "SUGGESTED_MATCH" and l["product_id"] is None:
            code = normalize_code(l["codigo_proveedor"] or "")
            if code and compra["proveedor_id"]:
                cands = db.execute(
                    text("""
                        SELECT pp.product_id, p.sku, p.name
                        FROM producto_proveedor pp
                        JOIN productos p ON p.id = pp.product_id
                        WHERE pp.proveedor_id = :prov_id
                          AND UPPER(REPLACE(REPLACE(pp.supplier_sku, '-', ''), ' ', '')) = :code
                    """),
                    {"prov_id": compra["proveedor_id"], "code": code},
                ).mappings().all()

                if not cands:
                    cands = db.execute(
                        text("""
                            SELECT id AS product_id, sku, name
                            FROM productos
                            WHERE UPPER(REPLACE(REPLACE(sku, '-', ''), ' ', '')) = :code
                               OR UPPER(REPLACE(REPLACE(codigo_pos, '-', ''), ' ', '')) LIKE '%' || :code
                            LIMIT 5
                        """),
                        {"code": code},
                    ).mappings().all()

                line_dict["candidates"] = [dict(c) for c in cands]

        lineas_out.append(line_dict)

    counts = {"MATCHED": 0, "SUGGESTED_MATCH": 0, "UNRESOLVED": 0, "SERVICE": 0}
    for l in lineas:
        s = l["status_match"] or "UNRESOLVED"
        counts[s] = counts.get(s, 0) + 1

    return {
        "compra": dict(compra),
        "lineas": lineas_out,
        "counts": counts,
        "puede_importar": (counts.get("SUGGESTED_MATCH", 0) + counts.get("UNRESOLVED", 0)) == 0,
    }


# ---------------------------------------------------------------------------
# PATCH /compras/{compra_id}/lineas/{linea_id}/confirmar
# ---------------------------------------------------------------------------

@router.patch("/{compra_id}/lineas/{linea_id}/confirmar")
def confirmar_match(
    compra_id: int,
    linea_id: int,
    body: ConfirmarMatchBody,
    db: Session = Depends(get_db),
):
    """Confirm product match for an XML line. Creates producto_proveedor if needed."""

    compra = db.execute(
        text("SELECT id, proveedor_id, estatus_workflow FROM compras WHERE id = :id"),
        {"id": compra_id},
    ).mappings().first()

    if not compra:
        raise HTTPException(status_code=404, detail="Compra no encontrada")
    if compra["estatus_workflow"] not in ("REVIEW", "READY"):
        raise HTTPException(status_code=400, detail="La compra no esta en estado de revision")

    linea = db.execute(
        text("""
            SELECT id, status_match, codigo_proveedor, descripcion_xml, precio_unit
            FROM compras_detalle
            WHERE id = :lid AND compra_id = :cid
        """),
        {"lid": linea_id, "cid": compra_id},
    ).mappings().first()

    if not linea:
        raise HTTPException(status_code=404, detail="Linea no encontrada en esta compra")
    if linea["status_match"] == "MATCHED":
        raise HTTPException(status_code=400, detail="Esta linea ya esta resuelta")
    if linea["status_match"] == "SERVICE":
        raise HTTPException(status_code=400, detail="Las lineas de servicio no requieren match")

    product = db.execute(
        text("SELECT id, sku, name FROM productos WHERE id = :id"),
        {"id": body.product_id},
    ).mappings().first()

    if not product:
        raise HTTPException(status_code=404, detail=f"Producto no encontrado: id={body.product_id}")

    db.execute(
        text("""
            UPDATE compras_detalle
            SET product_id = :product_id,
                status_match = 'MATCHED',
                matched_by = 'MANUAL_LINK'
            WHERE id = :lid
        """),
        {"product_id": body.product_id, "lid": linea_id},
    )

    if compra["proveedor_id"] and linea["codigo_proveedor"]:
        existing_pp = db.execute(
            text("""
                SELECT id FROM producto_proveedor
                WHERE product_id = :pid AND proveedor_id = :prov_id
            """),
            {"pid": body.product_id, "prov_id": compra["proveedor_id"]},
        ).scalar()

        if existing_pp:
            db.execute(
                text("""
                    UPDATE producto_proveedor
                    SET supplier_sku = :sku,
                        descripcion_proveedor = :desc,
                        precio_proveedor = :precio
                    WHERE id = :id
                """),
                {
                    "id": existing_pp,
                    "sku": linea["codigo_proveedor"],
                    "desc": linea["descripcion_xml"],
                    "precio": linea["precio_unit"],
                },
            )
        else:
            db.execute(
                text("""
                    INSERT INTO producto_proveedor
                        (product_id, proveedor_id, supplier_sku, descripcion_proveedor, precio_proveedor, is_primary, created_at)
                    VALUES
                        (:pid, :prov_id, :sku, :desc, :precio, FALSE, NOW())
                """),
                {
                    "pid": body.product_id,
                    "prov_id": compra["proveedor_id"],
                    "sku": linea["codigo_proveedor"],
                    "desc": linea["descripcion_xml"],
                    "precio": linea["precio_unit"],
                },
            )

    pending = db.execute(
        text("""
            SELECT COUNT(*) FROM compras_detalle
            WHERE compra_id = :cid
              AND status_match IN ('SUGGESTED_MATCH', 'UNRESOLVED')
        """),
        {"cid": compra_id},
    ).scalar()

    new_workflow = "READY" if pending == 0 else "REVIEW"
    db.execute(
        text("UPDATE compras SET estatus_workflow = :ws WHERE id = :id"),
        {"ws": new_workflow, "id": compra_id},
    )

    db.commit()

    return {
        "ok": True,
        "linea_id": linea_id,
        "product_id": body.product_id,
        "product_sku": product["sku"],
        "product_name": product["name"],
        "status_match": "MATCHED",
        "matched_by": "MANUAL_LINK",
        "estatus_workflow": new_workflow,
        "lineas_pendientes": pending,
    }


# ---------------------------------------------------------------------------
# POST /compras/{compra_id}/lineas/{linea_id}/crear-producto
# ---------------------------------------------------------------------------

@router.post("/{compra_id}/lineas/{linea_id}/crear-producto")
def crear_producto_from_xml(
    compra_id: int,
    linea_id: int,
    body: CrearProductoFromXmlBody,
    db: Session = Depends(get_db),
):
    """Create a new product from an unresolved XML line and link it."""

    compra = db.execute(
        text("SELECT id, proveedor_id, estatus_workflow FROM compras WHERE id = :id"),
        {"id": compra_id},
    ).mappings().first()

    if not compra:
        raise HTTPException(status_code=404, detail="Compra no encontrada")
    if compra["estatus_workflow"] not in ("REVIEW", "READY"):
        raise HTTPException(status_code=400, detail="La compra no esta en estado de revision")

    linea = db.execute(
        text("""
            SELECT id, status_match, codigo_proveedor, descripcion_xml, precio_unit
            FROM compras_detalle
            WHERE id = :lid AND compra_id = :cid
        """),
        {"lid": linea_id, "cid": compra_id},
    ).mappings().first()

    if not linea:
        raise HTTPException(status_code=404, detail="Linea no encontrada en esta compra")
    if linea["status_match"] in ("MATCHED", "SERVICE"):
        raise HTTPException(status_code=400, detail="Esta linea ya esta resuelta")

    sku = body.sku.strip().upper()
    if not sku:
        raise HTTPException(status_code=400, detail="SKU es obligatorio")

    sku_exists = db.execute(
        text("SELECT id FROM productos WHERE UPPER(sku) = :sku"),
        {"sku": sku},
    ).scalar()
    if sku_exists:
        raise HTTPException(status_code=409, detail=f"SKU ya existe: {sku}. Use confirmar-match en su lugar.")

    name = body.name.strip()
    if not name:
        raise HTTPException(status_code=400, detail="Nombre es obligatorio")

    unit = body.unit.strip().upper()
    if unit in ("PIEZA", "PZA"):
        unit = "PZA"
    elif unit in ("JUEGO", "JGO"):
        unit = "JGO"

    codigo_cat = None
    codigo_pos = None
    if body.codigo_cat:
        codigo_cat = body.codigo_cat.strip().replace(" ", "").replace("-", "")
        try:
            codigo_cat = str(int(float(codigo_cat))).zfill(4)
        except Exception:
            pass
        if codigo_cat and len(codigo_cat) == 4 and codigo_cat.isdigit():
            codigo_pos = codigo_cat + sku.replace("-", "").replace(" ", "")
        else:
            codigo_cat = None

    try:
        new_product = db.execute(
            text("""
                INSERT INTO productos
                    (sku, name, marca, categoria_id, unit, min_stock, price, is_active,
                     codigo_cat, codigo_pos, precio_publico)
                VALUES
                    (:sku, :name, :marca, :cat_id, :unit, :min_stock, :price, TRUE,
                     :codigo_cat, :codigo_pos, :precio_publico)
                RETURNING id, sku, name
            """),
            {
                "sku": sku,
                "name": name,
                "marca": body.marca.strip().upper() if body.marca else None,
                "cat_id": body.categoria_id,
                "unit": unit,
                "min_stock": body.min_stock,
                "price": body.price if body.price else (float(linea["precio_unit"]) if linea["precio_unit"] else 0),
                "codigo_cat": codigo_cat,
                "codigo_pos": codigo_pos,
                "precio_publico": body.precio_publico,
            },
        ).mappings().one()
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Error creando producto: {str(e)}")

    product_id = new_product["id"]

    db.execute(
        text("""
            UPDATE compras_detalle
            SET product_id = :product_id,
                status_match = 'MATCHED',
                matched_by = 'MANUAL_CREATE'
            WHERE id = :lid
        """),
        {"product_id": product_id, "lid": linea_id},
    )

    if compra["proveedor_id"] and linea["codigo_proveedor"]:
        db.execute(
            text("""
                INSERT INTO producto_proveedor
                    (product_id, proveedor_id, supplier_sku, descripcion_proveedor, precio_proveedor, is_primary, created_at)
                VALUES
                    (:pid, :prov_id, :sku, :desc, :precio, TRUE, NOW())
            """),
            {
                "pid": product_id,
                "prov_id": compra["proveedor_id"],
                "sku": linea["codigo_proveedor"],
                "desc": linea["descripcion_xml"],
                "precio": linea["precio_unit"],
            },
        )

    pending = db.execute(
        text("""
            SELECT COUNT(*) FROM compras_detalle
            WHERE compra_id = :cid
              AND status_match IN ('SUGGESTED_MATCH', 'UNRESOLVED')
        """),
        {"cid": compra_id},
    ).scalar()

    new_workflow = "READY" if pending == 0 else "REVIEW"
    db.execute(
        text("UPDATE compras SET estatus_workflow = :ws WHERE id = :id"),
        {"ws": new_workflow, "id": compra_id},
    )

    db.commit()

    return {
        "ok": True,
        "linea_id": linea_id,
        "product_created": {
            "id": new_product["id"],
            "sku": new_product["sku"],
            "name": new_product["name"],
        },
        "status_match": "MATCHED",
        "matched_by": "MANUAL_CREATE",
        "estatus_workflow": new_workflow,
        "lineas_pendientes": pending,
    }


# ---------------------------------------------------------------------------
# POST /compras/{compra_id}/importar
# ---------------------------------------------------------------------------

@router.post("/{compra_id}/importar")
def importar_compra_xml(compra_id: int, db: Session = Depends(get_db)):
    """Import resolved XML purchase - generates inventory movements."""

    compra = db.execute(
        text("SELECT id, proveedor_id, estatus_workflow, uuid_fiscal, descuento_financiero FROM compras WHERE id = :id"),
        {"id": compra_id},
    ).mappings().first()

    if not compra:
        raise HTTPException(status_code=404, detail="Compra no encontrada")
    if compra["estatus_workflow"] != "READY":
        raise HTTPException(
            status_code=400,
            detail=f"La compra debe estar en READY para importar (actual: {compra['estatus_workflow']})",
        )

    lineas = db.execute(
        text("""
            SELECT cd.id, cd.product_id, cd.cantidad, cd.precio_unit,
                   cd.codigo_proveedor, cd.descripcion_xml
            FROM compras_detalle cd
            WHERE cd.compra_id = :cid
              AND cd.status_match = 'MATCHED'
              AND cd.status_match != 'EXCLUDED'
              AND cd.es_servicio = FALSE
        """),
        {"cid": compra_id},
    ).mappings().all()

    if not lineas:
        raise HTTPException(status_code=400, detail="No hay lineas resueltas para importar")

    reference = f"COMPRA_XML_{compra['uuid_fiscal'] or compra_id}"
    movements_created = 0

    descuento_pct = float(compra["descuento_financiero"] or 0) / 100.0

    for l in lineas:
        if not l["product_id"]:
            continue

        db.execute(
            text("""
                INSERT INTO movimientos_inventario
                    (product_id, libro, movement_type, quantity, reference, notes, movement_date, created_at)
                VALUES
                    (:product_id, 'FISICO', 'IN', :quantity, :reference, :notes, NOW(), NOW())
            """),
            {
                "product_id": l["product_id"],
                "quantity": abs(float(l["cantidad"])),
                "reference": reference,
                "notes": f"XML import: {l['codigo_proveedor']} - {l['descripcion_xml'] or ''}",
            },
        )
        movements_created += 1

        if compra["proveedor_id"] and l["precio_unit"]:
            precio_real = float(l["precio_unit"]) * (1 - descuento_pct)
            db.execute(
                text("""
                    UPDATE producto_proveedor
                    SET precio_proveedor = :precio
                    WHERE product_id = :pid AND proveedor_id = :prov_id
                """),
                {
                    "precio": precio_real,
                    "pid": l["product_id"],
                    "prov_id": compra["proveedor_id"],
                },
            )
            db.execute(
                text("UPDATE productos SET price = :precio WHERE id = :product_id"),
                {"precio": precio_real, "product_id": l["product_id"]},
            )

    db.execute(
        text("""
            UPDATE compras
            SET estatus_workflow = 'IMPORTED',
                estatus_recepcion = 'RECIBIDA'
            WHERE id = :id
        """),
        {"id": compra_id},
    )

    db.commit()

    return {
        "ok": True,
        "compra_id": compra_id,
        "movements_created": movements_created,
        "reference": reference,
        "estatus_workflow": "IMPORTED",
        "estatus_recepcion": "RECIBIDA",
    }


@router.patch("/{compra_id}/lineas/{linea_id}/excluir")
def excluir_linea(compra_id: int, linea_id: int, db: Session = Depends(get_db)):
    row = db.execute(
        text("SELECT status_match, matched_by FROM compras_detalle WHERE id = :id AND compra_id = :cid"),
        {"id": linea_id, "cid": compra_id},
    ).mappings().first()
    if not row:
        raise HTTPException(status_code=404, detail="Linea no encontrada")
    if row["status_match"] == "EXCLUDED":
        raise HTTPException(status_code=400, detail="Linea ya excluida")

    # Store previous status in matched_by so we can restore it later
    prev_status = row["status_match"]
    db.execute(
        text("""
            UPDATE compras_detalle
            SET status_match = 'EXCLUDED', matched_by = :prev
            WHERE id = :id
        """),
        {"prev": f"PREV:{prev_status}", "id": linea_id},
    )

    # Recalculate workflow: only SUGGESTED_MATCH and UNRESOLVED block READY
    pending = db.execute(
        text("""
            SELECT COUNT(*) FROM compras_detalle
            WHERE compra_id = :cid
              AND status_match IN ('SUGGESTED_MATCH', 'UNRESOLVED')
        """),
        {"cid": compra_id},
    ).scalar()
    new_workflow = "READY" if pending == 0 else "REVIEW"
    db.execute(
        text("UPDATE compras SET estatus_workflow = :wf WHERE id = :cid"),
        {"wf": new_workflow, "cid": compra_id},
    )

    recalculate_compra_totals(db, compra_id)

    db.commit()
    return {"ok": True, "linea_id": linea_id, "status_match": "EXCLUDED", "estatus_workflow": new_workflow}


@router.patch("/{compra_id}/lineas/{linea_id}/incluir")
def incluir_linea(compra_id: int, linea_id: int, db: Session = Depends(get_db)):
    row = db.execute(
        text("SELECT status_match, matched_by FROM compras_detalle WHERE id = :id AND compra_id = :cid"),
        {"id": linea_id, "cid": compra_id},
    ).mappings().first()
    if not row:
        raise HTTPException(status_code=404, detail="Linea no encontrada")
    if row["status_match"] != "EXCLUDED":
        raise HTTPException(status_code=400, detail="Linea no está excluida")

    # Restore previous status (stored as "PREV:STATUS" in matched_by)
    matched_by_val = row["matched_by"] or ""
    if matched_by_val.startswith("PREV:"):
        restored_status = matched_by_val[5:]
    else:
        restored_status = "UNRESOLVED"

    db.execute(
        text("""
            UPDATE compras_detalle
            SET status_match = :st, matched_by = NULL
            WHERE id = :id
        """),
        {"st": restored_status, "id": linea_id},
    )

    # Recalculate workflow
    pending = db.execute(
        text("""
            SELECT COUNT(*) FROM compras_detalle
            WHERE compra_id = :cid
              AND status_match IN ('SUGGESTED_MATCH', 'UNRESOLVED')
        """),
        {"cid": compra_id},
    ).scalar()
    new_workflow = "READY" if pending == 0 else "REVIEW"
    db.execute(
        text("UPDATE compras SET estatus_workflow = :wf WHERE id = :cid"),
        {"wf": new_workflow, "cid": compra_id},
    )

    recalculate_compra_totals(db, compra_id)

    db.commit()
    return {"ok": True, "linea_id": linea_id, "status_match": restored_status, "estatus_workflow": new_workflow}


class DescuentoFinancieroBody(BaseModel):
    porcentaje: float


@router.patch("/{compra_id}/descuento-financiero")
def set_descuento_financiero(compra_id: int, body: DescuentoFinancieroBody, db: Session = Depends(get_db)):
    compra = db.execute(
        text("SELECT id, estatus_workflow FROM compras WHERE id = :id"),
        {"id": compra_id},
    ).mappings().first()
    if not compra:
        raise HTTPException(status_code=404, detail="Compra no encontrada")
    if compra["estatus_workflow"] not in ("REVIEW", "READY", None):
        raise HTTPException(status_code=400, detail="La compra ya fue importada")
    if body.porcentaje < 0 or body.porcentaje > 100:
        raise HTTPException(status_code=400, detail="Porcentaje debe ser entre 0 y 100")

    db.execute(
        text("UPDATE compras SET descuento_financiero = :pct WHERE id = :id"),
        {"pct": body.porcentaje, "id": compra_id},
    )

    recalculate_compra_totals(db, compra_id)

    updated = db.execute(
        text("""
            SELECT subtotal, iva, total,
                   subtotal_original, iva_original, total_original,
                   descuento_financiero
            FROM compras WHERE id = :id
        """),
        {"id": compra_id},
    ).mappings().first()

    db.commit()

    return {
        "ok": True,
        "descuento_financiero": float(updated["descuento_financiero"]),
        "original": {
            "subtotal": float(updated["subtotal_original"] or 0),
            "iva": float(updated["iva_original"] or 0),
            "total": float(updated["total_original"] or 0),
        },
        "actual": {
            "subtotal": float(updated["subtotal"]),
            "iva": float(updated["iva"]),
            "total": float(updated["total"]),
        },
    }
