import { api } from './client';

// ─── Inventario (Operational Alerts) ────────────────────────

export interface InventarioKpis {
  total_activos: number;
  stock_fisico_total: number;
  stock_pos_total: number;
  bajo_minimo: number;
  stock_cero: number;
  sin_movimiento_30d: number;
}

export interface InventarioItem {
  producto_id: number;
  sku: string;
  name: string;
  marca: string | null;
  categoria: string | null;
  stock_fisico: number;
  stock_pos: number;
  min_stock: number;
  deficit: number;
  ultimo_mov: string | null;
  proveedor: string | null;
}

export interface InventarioResponse {
  kpis: InventarioKpis;
  total: number;
  page: number;
  page_size: number;
  items: InventarioItem[];
}

export interface InventarioParams {
  q?: string;
  categoriaId?: number;
  marca?: string;
  proveedorId?: number;
  bajoMinimo?: boolean;
  stockCero?: boolean;
  stockNegativo?: boolean;
  sinMovimiento30d?: boolean;
  page: number;
  pageSize: number;
}

// ─── Forecast (Rotation Analysis) ───────────────────────────

export interface ForecastKpis {
  productos_analizados: number;
  rotacion_promedio: number;
  alta_rotacion: number;
  sin_rotacion_60d: number;
}

export interface ForecastItemReal {
  producto_id: number;
  sku: string;
  name: string;
  marca: string | null;
  categoria: string | null;
  stock_fisico: number;
  consumo_promedio_diario: number;
  cobertura_dias: number | null;
  demanda_proyectada: number;
  sugerido_comprar: number;
  num_out_90d: number;
  ultimo_mov_out: string | null;
  proveedor: string | null;
}

export interface ForecastResponse {
  kpis: ForecastKpis;
  total: number;
  page: number;
  page_size: number;
  items: ForecastItemReal[];
}

export interface ForecastParams {
  q?: string;
  categoriaId?: number;
  marca?: string;
  proveedorId?: number;
  horizon?: number;
  status?: string;
  page: number;
  pageSize: number;
}

// ─── Service ─────────────────────────────────────────────────

export const reportesService = {
  getInventario(p: InventarioParams): Promise<InventarioResponse> {
    const ps = new URLSearchParams();
    if (p.q)              ps.set('q', p.q);
    if (p.categoriaId)    ps.set('categoria_id', String(p.categoriaId));
    if (p.marca)          ps.set('marca', p.marca);
    if (p.proveedorId)    ps.set('proveedor_id', String(p.proveedorId));
    if (p.bajoMinimo)     ps.set('bajo_minimo', 'true');
    if (p.stockCero)      ps.set('stock_cero', 'true');
    if (p.stockNegativo)  ps.set('stock_negativo', 'true');
    if (p.sinMovimiento30d) ps.set('sin_movimiento_30d', 'true');
    ps.set('page', String(p.page));
    ps.set('page_size', String(p.pageSize));
    return api<InventarioResponse>(`/reportes/inventario?${ps}`);
  },

  getForecast(p: ForecastParams): Promise<ForecastResponse> {
    const ps = new URLSearchParams();
    if (p.q)           ps.set('q', p.q);
    if (p.categoriaId) ps.set('categoria_id', String(p.categoriaId));
    if (p.marca)       ps.set('marca', p.marca);
    if (p.proveedorId) ps.set('proveedor_id', String(p.proveedorId));
    if (p.horizon)     ps.set('horizon', String(p.horizon));
    if (p.status)      ps.set('status', p.status);
    ps.set('page', String(p.page));
    ps.set('page_size', String(p.pageSize));
    return api<ForecastResponse>(`/reportes/forecast?${ps}`);
  },
};
