from pydantic import BaseModel, Field, field_validator
from typing import Optional
from datetime import datetime, date
from enum import Enum


# --- Enums ---

class MovementType(str, Enum):
    IN = "IN"
    OUT = "OUT"
    ADJUST = "ADJUST"

class Libro(str, Enum):
    FISICO = "FISICO"
    FISCAL_POS = "FISCAL_POS"

class Evento(str, Enum):
    ENTRADA_FACTURA = "ENTRADA_FACTURA"
    ENTRADA_MOSTRADOR = "ENTRADA_MOSTRADOR"
    VENTA_FACTURADA = "VENTA_FACTURADA"
    VENTA_MOSTRADOR = "VENTA_MOSTRADOR"
    AJUSTE = "AJUSTE"


# --- Productos ---

class ProductCreate(BaseModel):
    sku: str
    name: str
    codigo_cat: Optional[str] = None
    codigo_pos: Optional[str] = None
    marca: Optional[str] = None
    categoria_id: Optional[int] = None
    unit: str = "PZA"
    min_stock: float = 0.0
    price: float = 0.0
    precio_publico: Optional[float] = None
    is_active: bool = True
    aplicacion: Optional[str] = None
    ubicacion: Optional[str] = None
    descripcion_larga: Optional[str] = None
    medida: Optional[str] = None
    anio_inicio: Optional[int] = None
    anio_fin: Optional[int] = None
    dim_largo: Optional[float] = None
    dim_ancho: Optional[float] = None
    dim_alto: Optional[float] = None
    equivalencia: Optional[str] = None
    imagen_url: Optional[str] = None

class ProductUpdate(BaseModel):
    name: Optional[str] = None
    categoria_id: Optional[int] = None
    unit: Optional[str] = None
    min_stock: Optional[float] = None
    is_active: Optional[bool] = None
    price: Optional[float] = None
    precio_publico: Optional[float] = None
    codigo_cat: Optional[str] = None
    codigo_pos: Optional[str] = None
    marca: Optional[str] = None
    aplicacion: Optional[str] = None
    ubicacion: Optional[str] = None
    descripcion_larga: Optional[str] = None
    medida: Optional[str] = None
    anio_inicio: Optional[int] = None
    anio_fin: Optional[int] = None
    dim_largo: Optional[float] = None
    dim_ancho: Optional[float] = None
    dim_alto: Optional[float] = None
    equivalencia: Optional[str] = None
    imagen_url: Optional[str] = None


# --- Movimientos ---

class MovementCreate(BaseModel):
    sku: str
    movement_type: MovementType
    quantity: float
    libro: Libro = Libro.FISICO
    evento: Optional[Evento] = None
    reference: Optional[str] = None
    notes: Optional[str] = None
    proveedor_id: Optional[int] = None
    costo_unit_sin_iva: Optional[float] = None
    tasa_iva: float = 0.16
    precio_venta_unit: Optional[float] = None


# --- Proveedores ---

class ProveedorCreate(BaseModel):
    nombre: str
    codigo_corto: str
    rfc: Optional[str] = None

class ProveedorUpdate(BaseModel):
    nombre: Optional[str] = None
    codigo_corto: Optional[str] = None
    rfc: Optional[str] = None


# --- Producto-Proveedor ---

class ProductoProveedorCreate(BaseModel):
    proveedor_id: int
    product_id: int
    supplier_sku: str
    descripcion_proveedor: Optional[str] = None
    is_primary: bool = False
    precio_proveedor: Optional[float] = None

class ProductoProveedorUpdate(BaseModel):
    supplier_sku: Optional[str] = None
    descripcion_proveedor: Optional[str] = None
    is_primary: Optional[bool] = None
    precio_proveedor: Optional[float] = None

# --- Categorias ---

class CategoriaCreate(BaseModel):
    name: str
    description: Optional[str] = None
    parent_id: Optional[int] = None

class CategoriaUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    parent_id: Optional[int] = None
