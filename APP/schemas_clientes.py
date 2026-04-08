from pydantic import BaseModel
from typing import Optional
from datetime import date


# ─── Clientes ───────────────────────────────────────

class ClienteCreate(BaseModel):
    nombre: str
    rfc: Optional[str] = None
    direccion: Optional[str] = None
    telefono: Optional[str] = None
    correo: Optional[str] = None
    tipo: str = "MOSTRADOR"  # MOSTRADOR, CREDITO, TALLER
    notas: Optional[str] = None

class ClienteUpdate(BaseModel):
    nombre: Optional[str] = None
    rfc: Optional[str] = None
    direccion: Optional[str] = None
    telefono: Optional[str] = None
    correo: Optional[str] = None
    tipo: Optional[str] = None
    notas: Optional[str] = None
    is_active: Optional[bool] = None


# ─── Documentos (antes Facturas) ──────────────────────

class FacturaCreate(BaseModel):
    folio: str
    cliente_id: int
    monto: float
    fecha: Optional[date] = None
    estatus: str = "PAGADA"             # PAGADA, CREDITO, PARCIAL
    tipo_documento: str = "FACTURA"     # FACTURA, NOTA_VENTA, CREDITO, REMISION
    condicion_pago: str = "CONTADO"     # CONTADO, CREDITO_15, CREDITO_30
    fecha_vencimiento: Optional[date] = None
    metodo_pago: Optional[str] = None
    notas: Optional[str] = None

class FacturaUpdate(BaseModel):
    folio: Optional[str] = None
    fecha: Optional[date] = None
    monto: Optional[float] = None
    estatus: Optional[str] = None
    tipo_documento: Optional[str] = None
    condicion_pago: Optional[str] = None
    fecha_vencimiento: Optional[date] = None
    metodo_pago: Optional[str] = None
    notas: Optional[str] = None


# ─── Pagos ──────────────────────────────────────────

class PagoCreate(BaseModel):
    monto: float
    fecha: Optional[date] = None
    metodo_pago: Optional[str] = None
    referencia: Optional[str] = None
    notas: Optional[str] = None
