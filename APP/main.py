from fastapi import FastAPI
from APP.routers import products, movements, stock, imports, proveedores, categorias, producto_proveedor, dashboard, faltantes
from APP.db import get_db
from sqlalchemy.orm import Session
from sqlalchemy import text
from fastapi import Depends
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI(title="Inventario Refacciones", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://127.0.0.1:3000",
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "http://192.168.1.68:3000",
        "http://192.168.1.68:5173",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- Registrar routers ---
app.include_router(products.router)
app.include_router(movements.router)
app.include_router(stock.router)
app.include_router(imports.router)
app.include_router(proveedores.router)
app.include_router(categorias.router)
app.include_router(producto_proveedor.router)
app.include_router(dashboard.router)
app.include_router(faltantes.router)


# --- Health checks ---

@app.get("/health", tags=["Sistema"])
def health():
    return {"status": "ok"}


@app.get("/db-check", tags=["Sistema"])
def db_check(db: Session = Depends(get_db)):
    result = db.execute(text("SELECT 1")).scalar()
    return {"database": "connected", "test_query": result}
