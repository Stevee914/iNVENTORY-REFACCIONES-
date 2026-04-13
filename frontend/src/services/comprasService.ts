import { api } from './client';

export interface Compra {
  id: number;
  folio_factura: string | null;
  folio_captura: string | null;
  fecha: string;
  subtotal: number;
  iva: number;
  total: number;
  estatus: 'PENDIENTE' | 'RECIBIDA' | 'PAGADA' | 'PARCIAL' | 'CANCELADA';
  metodo_pago: string | null;
  notas: string | null;
  origen: 'MANUAL' | 'POS';
  tipo_compra: 'CON_FACTURA' | 'SIN_FACTURA';
  pos_compra_id: number | null;
  created_at: string;
  proveedor_id: number;
  proveedor_nombre: string;
  proveedor_codigo: string;
}

export interface ResumenCompras {
  total_compras: number;
  monto_total: number;
  monto_pagado: number;
  monto_pendiente: number;
  monto_parcial: number;
  compras_pagadas: number;
  compras_pendientes: number;
  compras_parciales: number;
  compras_pos: number;
  compras_manual: number;
}

export interface DetalleItem {
  product_id:   number;
  cantidad:     number;
  precio_unit?: number | null;
  supplier_sku?: string | null;
}

export interface DetalleRow extends DetalleItem {
  id: number;
  compra_id: number;
  sku: string;
  product_name: string;
  marca: string | null;
  unit: string | null;
  created_at: string;
}

export interface CompraCreate {
  proveedor_id:  number;
  folio_factura?: string;
  folio_captura?: string;
  fecha:         string;
  subtotal:      number;
  iva:           number;
  total:         number;
  estatus:       string;
  metodo_pago?:  string;
  notas?:        string;
  tipo_compra?:  string;
  detalle?:      DetalleItem[];
}

export interface CompraUpdate {
  folio_factura?: string;
  folio_captura?: string;
  fecha?:         string;
  subtotal?:      number;
  iva?:           number;
  total?:         number;
  estatus?:       string;
  metodo_pago?:   string;
  notas?:         string;
  tipo_compra?:   string;
}

// ── Dashboard types ───────────────────────────────────────────────────────────

export interface DashboardKPIs {
  total_compras:     number;
  total_monto:       number;
  con_factura_monto: number;
  con_factura_count: number;
  sin_factura_monto: number;
  sin_factura_count: number;
  compras_pendientes: number;
  compras_recibidas:  number;
  compras_pos:        number;
  compras_manuales:   number;
  ticket_promedio:    number;
}

export interface DashboardResponse {
  anio: number;
  mes:  number;
  kpis: DashboardKPIs;
}

export interface ProveedorRanking {
  proveedor_id:     number;
  proveedor_nombre: string;
  total_monto:      number;
  con_factura:      number;
  sin_factura:      number;
  num_compras:      number;
  ticket_promedio:  number;
  ultima_compra:    string | null;
}

export interface TopProveedoresResponse {
  anio:       number;
  mes:        number;
  proveedores: ProveedorRanking[];
}

export interface TopProducto {
  product_id:    number;
  sku:           string;
  product_name:  string;
  cantidad_total: number;
  monto_total:   number;
}

export interface CompraReciente {
  compra_id:    number;
  fecha:        string;
  folio_factura: string | null;
  tipo_compra:  string;
  total:        number;
  estatus:      string;
}

export interface ProveedorDetalleStats {
  num_compras:     number;
  total_monto:     number;
  con_factura:     number;
  sin_factura:     number;
  ticket_promedio: number;
  ultima_compra:   string | null;
}

export interface ProveedorDetalleResponse {
  proveedor_id:      number;
  proveedor_nombre:  string;
  anio:              number;
  mes:               number;
  stats:             ProveedorDetalleStats;
  top_productos:     TopProducto[];
  compras_recientes: CompraReciente[];
}

export const comprasService = {
  async getResumen(): Promise<ResumenCompras> {
    return api<ResumenCompras>('/compras/resumen');
  },

  async getAll(params?: {
    q?:            string;
    proveedor_id?: number;
    estatus?:      string;
    origen?:       string;
    tipo_compra?:  string;
    fecha_inicio?: string;
    fecha_fin?:    string;
    page?:         number;
    page_size?:    number;
  }): Promise<{ items: Compra[]; total: number; page: number; page_size: number }> {
    const sp = new URLSearchParams();
    if (params?.q)            sp.set('q',            params.q);
    if (params?.proveedor_id) sp.set('proveedor_id', String(params.proveedor_id));
    if (params?.estatus)      sp.set('estatus',      params.estatus);
    if (params?.origen)       sp.set('origen',       params.origen);
    if (params?.tipo_compra)  sp.set('tipo_compra',  params.tipo_compra);
    if (params?.fecha_inicio) sp.set('fecha_inicio', params.fecha_inicio);
    if (params?.fecha_fin)    sp.set('fecha_fin',    params.fecha_fin);
    if (params?.page)         sp.set('page',         String(params.page));
    if (params?.page_size)    sp.set('page_size',    String(params.page_size));
    const qs = sp.toString();
    return api(`/compras${qs ? '?' + qs : ''}`);
  },

  async getById(id: number): Promise<Compra> {
    return api<Compra>(`/compras/${id}`);
  },

  async create(data: CompraCreate): Promise<{ ok: boolean; id: number }> {
    return api('/compras', { method: 'POST', body: JSON.stringify(data) });
  },

  async update(id: number, data: CompraUpdate): Promise<{ ok: boolean }> {
    return api(`/compras/${id}`, { method: 'PATCH', body: JSON.stringify(data) });
  },

  async delete(id: number): Promise<{ ok: boolean }> {
    return api(`/compras/${id}`, { method: 'DELETE' });
  },

  async getDetalle(id: number): Promise<{ items: DetalleRow[]; count: number }> {
    return api(`/compras/${id}/detalle`);
  },

  async replaceDetalle(id: number, items: DetalleItem[]): Promise<{ ok: boolean; count: number }> {
    return api(`/compras/${id}/detalle`, { method: 'PUT', body: JSON.stringify(items) });
  },

  async getDashboard(anio?: number, mes?: number): Promise<DashboardResponse> {
    const sp = new URLSearchParams();
    if (anio) sp.set('anio', String(anio));
    if (mes)  sp.set('mes',  String(mes));
    const qs = sp.toString();
    return api(`/compras/dashboard${qs ? '?' + qs : ''}`);
  },

  async getTopProveedores(anio?: number, mes?: number, limit?: number): Promise<TopProveedoresResponse> {
    const sp = new URLSearchParams();
    if (anio)  sp.set('anio',  String(anio));
    if (mes)   sp.set('mes',   String(mes));
    if (limit) sp.set('limit', String(limit));
    const qs = sp.toString();
    return api(`/compras/dashboard/top-proveedores${qs ? '?' + qs : ''}`);
  },

  async getProveedorDetalle(proveedorId: number, anio?: number, mes?: number): Promise<ProveedorDetalleResponse> {
    const sp = new URLSearchParams();
    if (anio) sp.set('anio', String(anio));
    if (mes)  sp.set('mes',  String(mes));
    const qs = sp.toString();
    return api(`/compras/dashboard/proveedor/${proveedorId}${qs ? '?' + qs : ''}`);
  },

  async registrarCompraFromFaltantes(data: {
    proveedor_id: number;
    faltante_ids: number[];
    notas?: string;
  }): Promise<{
    ok: boolean;
    compra_id: number;
    fecha: string;
    estatus: string;
    proveedor_nombre: string;
    lineas_creadas: number;
    errores_validacion: Array<{ faltante_id: number; error: string }>;
  }> {
    return api('/compras/desde-faltantes', { method: 'POST', body: JSON.stringify(data) });
  },
};
