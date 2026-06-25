"""
AI Catalog Agent — chat endpoint con tool use via Claude API.

Tools disponibles:
  - buscar_productos       : busca productos por texto, marca, categoria
  - productos_sin_categoria: lista productos sin categoria con ventas
  - productos_sin_precio   : lista productos con precio_publico nulo o cero
  - productos_sin_movimiento: productos sin ventas en N dias
  - resumen_catalogo       : KPIs generales del catalogo
  - actualizar_producto    : actualiza campos de un producto (requiere confirmacion del usuario)
  - pendientes_catalogo    : genera lista de tareas de limpieza pendientes
"""

import json
import logging
from typing import Optional
from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session
from sqlalchemy import text

from APP.db import get_db
from APP.services.llm import generate_chat_response, LLMProviderError

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/ai", tags=["AI Agent"])

# ── Tool definitions ───────────────────────────────────────────────────────────
TOOLS = [
    {
        "name": "buscar_productos",
        "description": "Busca productos en el catálogo por texto libre, marca o categoría.",
        "input_schema": {
            "type": "object",
            "properties": {
                "q":          {"type": "string",  "description": "Texto de búsqueda (nombre, SKU)"},
                "marca":      {"type": "string",  "description": "Filtrar por marca"},
                "categoria":  {"type": "string",  "description": "Filtrar por nombre de categoría"},
                "sin_precio": {"type": "boolean", "description": "Solo productos sin precio público"},
                "sin_cat":    {"type": "boolean", "description": "Solo productos sin categoría"},
                "limit":      {"type": "integer", "description": "Máximo de resultados (default 20)"},
            },
        },
    },
    {
        "name": "productos_sin_movimiento",
        "description": "Lista productos que no han tenido ventas en los últimos N días.",
        "input_schema": {
            "type": "object",
            "properties": {
                "dias":      {"type": "integer", "description": "Días sin movimiento (ej. 180)"},
                "categoria": {"type": "string",  "description": "Filtrar por categoría (opcional)"},
                "limit":     {"type": "integer", "description": "Máximo de resultados (default 30)"},
            },
            "required": ["dias"],
        },
    },
    {
        "name": "resumen_catalogo",
        "description": "Retorna KPIs generales del catálogo: total productos, sin categoría, sin precio, sin movimiento, etc.",
        "input_schema": {"type": "object", "properties": {}},
    },
    {
        "name": "pendientes_catalogo",
        "description": "Genera lista de tareas de limpieza priorizadas: productos con datos incompletos, sin movimiento, posibles duplicados.",
        "input_schema": {"type": "object", "properties": {}},
    },
    {
        "name": "actualizar_producto",
        "description": "Actualiza campos de un producto. SOLO usar después de que el usuario confirme explícitamente.",
        "input_schema": {
            "type": "object",
            "properties": {
                "sku":            {"type": "string", "description": "SKU del producto"},
                "nombre":         {"type": "string", "description": "Nuevo nombre"},
                "marca":          {"type": "string", "description": "Nueva marca"},
                "categoria_id":   {"type": "integer","description": "ID de categoría"},
                "precio_publico": {"type": "number", "description": "Nuevo precio público"},
                "is_active":      {"type": "boolean","description": "Activar/desactivar producto"},
            },
            "required": ["sku"],
        },
    },
]

# ── Tool handlers ──────────────────────────────────────────────────────────────
def run_tool(name: str, inputs: dict, db: Session) -> str:
    try:
        if name == "buscar_productos":
            return _buscar_productos(inputs, db)
        elif name == "productos_sin_movimiento":
            return _productos_sin_movimiento(inputs, db)
        elif name == "resumen_catalogo":
            return _resumen_catalogo(db)
        elif name == "pendientes_catalogo":
            return _pendientes_catalogo(db)
        elif name == "actualizar_producto":
            return _actualizar_producto(inputs, db)
        return json.dumps({"error": f"Tool desconocida: {name}"})
    except Exception as e:
        logger.error("Tool %s error: %s", name, e)
        return json.dumps({"error": str(e)})


def _buscar_productos(inp: dict, db: Session) -> str:
    wheres, params = ["p.is_active = true", "p.catalog_visible = true"], {}
    if inp.get("q"):
        wheres.append("(p.sku ILIKE :q OR p.name ILIKE :q)")
        params["q"] = f"%{inp['q']}%"
    if inp.get("marca"):
        wheres.append("UPPER(p.marca) ILIKE :marca")
        params["marca"] = f"%{inp['marca'].upper()}%"
    if inp.get("categoria"):
        wheres.append("(UPPER(c.name) ILIKE :cat OR UPPER(cp.name) ILIKE :cat)")
        params["cat"] = f"%{inp['categoria'].upper()}%"
    if inp.get("sin_precio"):
        wheres.append("(p.precio_publico IS NULL OR p.precio_publico = 0)")
    if inp.get("sin_cat"):
        wheres.append("p.categoria_id IS NULL")
    limit = min(inp.get("limit", 20), 50)
    rows = db.execute(text(f"""
        SELECT p.sku, p.name, p.marca, p.precio_publico,
               COALESCE(c.name,'Sin categoría') AS categoria,
               COALESCE(sv.stock_fisico,0) AS stock
        FROM productos p
        LEFT JOIN categoria c  ON c.id  = p.categoria_id
        LEFT JOIN categoria cp ON cp.id = c.parent_id
        LEFT JOIN v_stock_libros sv ON sv.product_id = p.id
        WHERE {' AND '.join(wheres)}
        ORDER BY p.name LIMIT :lim
    """), {**params, "lim": limit}).mappings().all()
    return json.dumps([dict(r) for r in rows], default=str, ensure_ascii=False)


def _productos_sin_movimiento(inp: dict, db: Session) -> str:
    dias  = inp.get("dias", 180)
    limit = min(inp.get("limit", 30), 100)
    cat_filter = ""
    params: dict = {"dias": dias, "lim": limit}
    if inp.get("categoria"):
        cat_filter = "AND (UPPER(c.name) ILIKE :cat OR UPPER(cp.name) ILIKE :cat)"
        params["cat"] = f"%{inp['categoria'].upper()}%"
    rows = db.execute(text(f"""
        SELECT p.sku, p.name, p.marca,
               COALESCE(c.name,'Sin categoría') AS categoria,
               COALESCE(sv.stock_fisico,0) AS stock,
               MAX(mi.movement_date)::date AS ultima_venta
        FROM productos p
        LEFT JOIN categoria c  ON c.id  = p.categoria_id
        LEFT JOIN categoria cp ON cp.id = c.parent_id
        LEFT JOIN v_stock_libros sv ON sv.product_id = p.id
        LEFT JOIN movimientos_inventario mi
               ON mi.product_id = p.id
              AND mi.evento::text = 'VENTA_FACTURADA'
        WHERE p.is_active = true AND p.catalog_visible = true
          {cat_filter}
        GROUP BY p.sku, p.name, p.marca, c.name, cp.name, sv.stock_fisico
        HAVING MAX(mi.movement_date) < NOW() - INTERVAL ':dias days'
            OR MAX(mi.movement_date) IS NULL
        ORDER BY ultima_venta ASC NULLS FIRST
        LIMIT :lim
    """), params).mappings().all()
    return json.dumps([dict(r) for r in rows], default=str, ensure_ascii=False)


def _resumen_catalogo(db: Session) -> str:
    r = db.execute(text("""
        SELECT
            COUNT(*)                                                        AS total_activos,
            COUNT(*) FILTER (WHERE categoria_id IS NULL)                   AS sin_categoria,
            COUNT(*) FILTER (WHERE precio_publico IS NULL OR precio_publico=0) AS sin_precio_publico,
            COUNT(*) FILTER (WHERE marca IS NULL OR marca='')              AS sin_marca,
            COUNT(*) FILTER (WHERE NOT catalog_visible)                    AS no_visibles
        FROM productos WHERE is_active = true
    """)).mappings().first()
    sin_mov = db.execute(text("""
        SELECT COUNT(DISTINCT p.id) AS cnt
        FROM productos p
        WHERE p.is_active = true AND p.catalog_visible = true
          AND NOT EXISTS (
            SELECT 1 FROM movimientos_inventario mi
            WHERE mi.product_id = p.id
              AND mi.evento::text = 'VENTA_FACTURADA'
              AND mi.movement_date > NOW() - INTERVAL '180 days'
          )
    """)).scalar()
    return json.dumps({**dict(r), "sin_venta_180_dias": sin_mov}, default=str)


def _pendientes_catalogo(db: Session) -> str:
    tasks = []
    r = _resumen_catalogo(db)
    data = json.loads(r)
    if data["sin_categoria"] > 0:
        tasks.append({"prioridad": "alta", "tipo": "sin_categoria",
                      "cantidad": data["sin_categoria"],
                      "descripcion": f"{data['sin_categoria']} productos activos sin categoría asignada"})
    if data["sin_precio_publico"] > 0:
        tasks.append({"prioridad": "alta", "tipo": "sin_precio",
                      "cantidad": data["sin_precio_publico"],
                      "descripcion": f"{data['sin_precio_publico']} productos sin precio público"})
    if data["sin_marca"] > 0:
        tasks.append({"prioridad": "media", "tipo": "sin_marca",
                      "cantidad": data["sin_marca"],
                      "descripcion": f"{data['sin_marca']} productos sin marca"})
    if data["sin_venta_180_dias"] > 0:
        tasks.append({"prioridad": "baja", "tipo": "sin_movimiento",
                      "cantidad": data["sin_venta_180_dias"],
                      "descripcion": f"{data['sin_venta_180_dias']} productos sin ventas en 180 días"})
    return json.dumps({"tareas": tasks, "resumen": data}, ensure_ascii=False)


def _actualizar_producto(inp: dict, db: Session) -> str:
    sku = inp.get("sku")
    prod = db.execute(text("SELECT id FROM productos WHERE sku=:s"), {"s": sku}).scalar()
    if not prod:
        return json.dumps({"error": f"Producto no encontrado: {sku}"})
    sets, params = [], {"id": prod}
    if "nombre"         in inp: sets.append("name=:nombre");         params["nombre"]         = inp["nombre"]
    if "marca"          in inp: sets.append("marca=:marca");          params["marca"]          = inp["marca"]
    if "categoria_id"   in inp: sets.append("categoria_id=:cat");     params["cat"]            = inp["categoria_id"]
    if "precio_publico" in inp: sets.append("precio_publico=:pp");    params["pp"]             = inp["precio_publico"]
    if "is_active"      in inp: sets.append("is_active=:active");     params["active"]         = inp["is_active"]
    if not sets:
        return json.dumps({"error": "Sin campos para actualizar"})
    db.execute(text(f"UPDATE productos SET {','.join(sets)} WHERE id=:id"), params)
    db.commit()
    return json.dumps({"ok": True, "sku": sku, "campos_actualizados": list(inp.keys())})


# ── System prompt ──────────────────────────────────────────────────────────────
SYSTEM_PROMPT = """Eres el asistente de catálogo de Refacciones y Llantas Jaime S.A. de C.V.

Tu rol es ayudar a organizar, consultar y mejorar el catálogo de inventario de una refaccionaria real. Tienes acceso a herramientas para consultar datos del catálogo y proponer actualizaciones controladas.

Reglas de conversación:
- Si el usuario saluda, agradece, pregunta qué puedes hacer, o hace una pregunta general sin pedir datos concretos del inventario, responde de forma natural SIN usar herramientas.
- No uses herramientas solo para demostrar capacidad.
- Usa herramientas únicamente cuando la respuesta requiera datos reales del sistema: productos, SKU, precios públicos, marca, categoría, stock, pendientes o movimientos.
- Nunca muestres nombres internos de herramientas, JSON, parámetros ni comandos al usuario.
- Si no necesitas consultar datos, responde breve y claro.

Reglas operativas:
- SIEMPRE muestra los datos encontrados antes de proponer cambios.
- NUNCA ejecutes actualizar_producto sin confirmación explícita del usuario.
- Si el usuario pide modificar un producto, prepara la acción como pendiente de confirmación; no afirmes que ya se aplicó.
- Cuando hagas búsquedas, resume los resultados de forma clara y concisa.
- Usa lenguaje directo y operacional; este es un sistema ERP, no un chatbot de consumo.
- Si el usuario pregunta en español, responde en español.
- Las cantidades de unidades se expresan en piezas (PZA), pares (PAR), juegos (JGO) según el producto.
- Para precios al cliente usa precio_publico. No uses price como precio de venta.
"""


# ── Request / Response schemas ─────────────────────────────────────────────────
class Message(BaseModel):
    role: str    # "user" | "assistant"
    content: str

class ChatRequest(BaseModel):
    messages: list[Message]
    api_key:  Optional[str] = None  # override si el usuario lo provee en config

class ChatResponse(BaseModel):
    reply:        str
    tool_calls:   list[dict] = []
    pending_action: Optional[dict] = None  # acción pendiente de confirmación
    meta:         Optional[dict] = None     # metadatos seguros (provider/model/latencia); sin keys ni prompts


# ── Chat endpoint ──────────────────────────────────────────────────────────────
@router.post("/chat")
def chat(payload: ChatRequest, db: Session = Depends(get_db)):
    messages = [{"role": m.role, "content": m.content} for m in payload.messages]

    try:
        result = generate_chat_response(
            messages=messages,
            system=SYSTEM_PROMPT,
            tools=TOOLS,
            tool_runner=lambda name, inp: run_tool(name, inp, db),
            max_iters=5,
            mutating_tools=("actualizar_producto",),
            api_key_override=payload.api_key,
        )
    except LLMProviderError as e:
        # Error esperable (sin API key, Ollama caído, timeout) → mensaje amable
        return ChatResponse(reply=f"⚠ {e}")
    except Exception as e:
        logger.error("Chat error inesperado: %s", e)
        return ChatResponse(reply="⚠ Error inesperado en el asistente. Revisa el log del backend.")

    return ChatResponse(
        reply=result.reply,
        tool_calls=result.tool_calls,
        pending_action=result.pending_action,
        meta={
            "provider": result.provider,
            "model": result.model,
            "latency_ms": result.latency_ms,
            "tool_call_count": result.tool_call_count,
        },
    )


# ── Pendientes endpoint (para la pestaña de tareas) ───────────────────────────
@router.get("/pendientes")
def get_pendientes(db: Session = Depends(get_db)):
    result = _pendientes_catalogo(db)
    return json.loads(result)
