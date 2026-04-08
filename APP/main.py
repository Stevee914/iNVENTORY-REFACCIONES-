from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from APP.db import get_db
from sqlalchemy.orm import Session
from sqlalchemy import text
from fastapi import Depends

app = FastAPI(title="Inventario Refacciones", version="0.1.0")

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- Routers ---
from APP.routers import (
    products,
    movements,
    stock,
    imports,
    proveedores,
    producto_proveedor,
    categorias,
    dashboard,
    clientes,
    facturas,
    faltantes,
    compras,
    pos_sync,
    vehiculos,
    reportes,
)

app.include_router(products.router)
app.include_router(movements.router)
app.include_router(stock.router)
app.include_router(imports.router)
app.include_router(proveedores.router)
app.include_router(producto_proveedor.router)
app.include_router(categorias.router)
app.include_router(dashboard.router)
app.include_router(clientes.router)
app.include_router(facturas.router)
app.include_router(faltantes.router)
app.include_router(compras.router)
app.include_router(pos_sync.router)
app.include_router(vehiculos.router)
app.include_router(reportes.router)


# --- Base endpoints ---

@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/db-check")
def db_check(db: Session = Depends(get_db)):
    result = db.execute(text("SELECT 1")).scalar()
    return {"database": "connected", "test_query": result}
