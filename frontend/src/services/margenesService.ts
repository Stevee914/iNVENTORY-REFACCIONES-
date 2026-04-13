import { api } from './client';

export interface MargenItem {
  producto_id: number;
  sku: string;
  name: string;
  marca: string | null;
  categoria: string | null;
  costo_pos_con_iva: number | null;
  costo_real_sin_iva: number | null;
  costo_base: number | null;
  fuente_costo: 'REAL' | 'POS' | 'MANUAL' | null;
  precio_publico: number | null;
  precio_final: number | null;
  porcentaje_margen_objetivo: number | null;
  precio_sugerido: number | null;
  costo_real_updated_at: string | null;
  utilidad: number | null;
  margen_porcentaje: number | null;
  markup_porcentaje: number | null;
  proveedor: string | null;
}

export interface MargenesTotals {
  total: number;
  sin_costo: number;
  sin_precio_publico: number;
  margen_promedio: number | null;
  en_riesgo: number;
}

export interface MargenesResponse {
  totals: MargenesTotals;
  page: number;
  page_size: number;
  total: number;
  items: MargenItem[];
}

export interface MargenesParams {
  q?: string;
  categoriaId?: number;
  marca?: string;
  proveedorId?: number;
  sinCosto?: boolean;
  sinPrecioPublico?: boolean;
  margenBajo?: number;
  margenNegativo?: boolean;
  page: number;
  pageSize: number;
}

export const margenesService = {
  getAll(p: MargenesParams): Promise<MargenesResponse> {
    const ps = new URLSearchParams();
    if (p.q)               ps.set('q', p.q);
    if (p.categoriaId)     ps.set('categoria_id', String(p.categoriaId));
    if (p.marca)           ps.set('marca', p.marca);
    if (p.proveedorId)     ps.set('proveedor_id', String(p.proveedorId));
    if (p.sinCosto)        ps.set('sin_costo', 'true');
    if (p.sinPrecioPublico) ps.set('sin_precio_publico', 'true');
    if (p.margenNegativo)  ps.set('margen_negativo', 'true');
    else if (p.margenBajo !== undefined && p.margenBajo !== null)
      ps.set('margen_bajo', String(p.margenBajo));
    ps.set('page', String(p.page));
    ps.set('page_size', String(p.pageSize));
    return api<MargenesResponse>(`/reportes/margenes?${ps}`);
  },
};
