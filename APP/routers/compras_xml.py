from fastapi import APIRouter, Depends, UploadFile, File, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import text
from APP.db import get_db
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
                     created_at, updated_at)
                VALUES
                    (:proveedor_id, :folio_factura, :fecha, :subtotal, :iva, :total,
                     :estatus, :metodo_pago, :notas, 'XML',
                     'PENDIENTE', 'REVIEW', :uuid_fiscal,
                     NOW(), NOW())
                RETURNING id
            """),
            {
                "proveedor_id": proveedor_id,
                "folio_factura": folio_factura,
                "fecha": parsed["fecha"][:10] if parsed["fecha"] else None,
                "subtotal": parsed["subtotal"] - parsed["descuento_total"],
                "iva": parsed["iva_total"],
                "total": parsed["total"],
                "estatus": estatus_pago,
                "metodo_pago": metodo_pago_xml,
                "notas": f"Importado desde XML. Emisor: {parsed.get('emisor_nombre', '')}",
                "uuid_fiscal": uuid,
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
