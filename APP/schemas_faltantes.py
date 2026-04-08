from pydantic import BaseModel
from typing import Optional


class FaltanteCreate(BaseModel):
    product_id: int
    cantidad_faltante: float
    comentario: Optional[str] = None


class FaltanteUpdateStatus(BaseModel):
    status: str  # pendiente, comprado, cancelado


class FaltanteUpdate(BaseModel):
    product_id:        Optional[int]   = None
    cantidad_faltante: Optional[float] = None
    comentario:        Optional[str]   = None
    status:            Optional[str]   = None
