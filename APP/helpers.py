import pandas as pd
from fastapi import HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import text


def normalize_quantity(movement_type: str, qty: float) -> float:
    if qty is None:
        raise ValueError("quantity is required")
    mt = movement_type.upper().strip()
    if mt in ("IN", "OUT"):
        if qty <= 0:
            raise ValueError("quantity must be > 0 for IN/OUT")
        return abs(qty) if mt == "IN" else -abs(qty)
    if mt == "ADJUST":
        if qty == 0:
            raise ValueError("quantity cannot be 0 for ADJUST")
        return float(qty)
    raise ValueError(f"Invalid movement_type: {movement_type}")


def normalize_text(value) -> str:
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return ""
    return str(value).strip()


def normalize_code(value) -> str:
    return normalize_text(value).upper().replace(" ", "").replace("-", "")


def normalize_sku(value) -> str:
    return normalize_text(value).upper()


def parse_bool(value, default=True) -> bool:
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return default
    s = str(value).strip().upper()
    if s in ("1", "TRUE", "VERDADERO", "SI", "SÍ", "YES", "Y"):
        return True
    if s in ("0", "FALSE", "FALSO", "NO", "N"):
        return False
    return default


def parse_float(value, default=0.0) -> float:
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return default
    s = str(value).replace("$", "").replace(",", "").strip()
    if s == "" or s.lower() == "nan":
        return default
    return float(s)


def normalize_unit(value: str) -> str:
    unit = normalize_text(value).upper()
    unit_map = {
        "PIEZA": "PZA", "PZA": "PZA", "PAR": "PAR",
        "JUEGO": "JGO", "JGO": "JGO", "KIT": "KIT",
    }
    return unit_map.get(unit, unit or "PZA")


def map_libro(value) -> str:
    libro_in = normalize_text(value).upper() or "FISICO"
    map_values = {
        "FISICO": "FISICO",
        "FISCAL_POS": "FISCAL_POS",
        "POS": "FISCAL_POS",
        "FISCAL": "FISCAL_POS",
    }
    if libro_in not in map_values:
        raise HTTPException(status_code=400, detail="libro debe ser FISICO o FISCAL_POS")
    return map_values[libro_in]


def build_codigo_pos(codigo_cat: str, sku: str) -> str:
    cat = normalize_code(codigo_cat)
    if len(cat) != 4 or not cat.isdigit():
        raise ValueError(f"codigo_cat inválido: {codigo_cat}")
    return cat + normalize_code(sku)


def ensure_category(db: Session, name: str, parent_id: int | None) -> int:
    row = db.execute(
        text("""
            SELECT id FROM categoria
            WHERE name = :name
              AND ((:parent_id IS NULL AND parent_id IS NULL) OR parent_id = :parent_id)
            LIMIT 1
        """),
        {"name": name, "parent_id": parent_id},
    ).mappings().first()
    if row:
        return int(row["id"])
    new_id = db.execute(
        text("""
            INSERT INTO categoria (name, parent_id)
            VALUES (:name, :parent_id)
            RETURNING id
        """),
        {"name": name, "parent_id": parent_id},
    ).scalar()
    return int(new_id)


def derive_evento(movement_type: str, libro: str, proveedor_id: int | None) -> str:
    """Deriva el evento automáticamente basado en tipo, libro y proveedor."""
    mt = movement_type.upper()
    if mt == "ADJUST":
        return "AJUSTE"
    if mt == "IN":
        if proveedor_id is not None:
            return "ENTRADA_FACTURA"
        return "ENTRADA_MOSTRADOR"
    if mt == "OUT":
        if libro == "FISCAL_POS":
            return "VENTA_FACTURADA"
        return "VENTA_MOSTRADOR"
    return "AJUSTE"


def calc_costo_con_iva(costo_sin_iva: float | None, tasa_iva: float) -> float | None:
    if costo_sin_iva is None:
        return None
    return round(costo_sin_iva * (1 + tasa_iva), 4)
