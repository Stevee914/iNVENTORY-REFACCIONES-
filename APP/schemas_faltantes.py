from pydantic import BaseModel
from typing import Optional


class FaltanteCreate(BaseModel):
    product_id: int
    cantidad_faltante: float
    comentario: Optional[str] = None


class FaltanteUpdateStatus(BaseModel):
    status: str  # pendiente, comprado, cancelado
