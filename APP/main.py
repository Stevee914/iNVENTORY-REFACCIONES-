from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
import os
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
    cobranza_manual,
    conciliacion_cobranza,
    faltantes,
    compras,
    compras_xml,
    pos_sync,
    pos_fiscal_inicial,
    pos_compras,
    pos_ventas,
    vehiculos,
    motores,
    reportes,
    pagos_proveedor,
    sync_pagos_proveedor,
    sync_diario,
    conteos_fisicos,
    etiquetas,
    config,
)

app.include_router(config.router)
app.include_router(conteos_fisicos.router)
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
app.include_router(cobranza_manual.router)
app.include_router(conciliacion_cobranza.router)
app.include_router(faltantes.router)
app.include_router(pagos_proveedor.router_reportes)
app.include_router(pagos_proveedor.router)
app.include_router(compras_xml.router)
app.include_router(compras.router)
app.include_router(pos_sync.router)
app.include_router(pos_fiscal_inicial.router)
app.include_router(pos_compras.router)
app.include_router(pos_ventas.router)
app.include_router(sync_pagos_proveedor.router)
app.include_router(sync_diario.router)
app.include_router(vehiculos.router)
app.include_router(motores.router)
app.include_router(reportes.router)
app.include_router(etiquetas.router)

# --- Static media ---
_MEDIA_DIR = r"C:\Refacciones\media"
os.makedirs(os.path.join(_MEDIA_DIR, "productos"), exist_ok=True)
app.mount("/media", StaticFiles(directory=_MEDIA_DIR), name="media")

# --- Base endpoints ---

@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/db-check")
def db_check(db: Session = Depends(get_db)):
    result = db.execute(text("SELECT 1")).scalar()
    return {"database": "connected", "test_query": result}
