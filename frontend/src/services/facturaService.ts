import { api } from './client';

export interface Factura {
  id: number;
  folio: string;
  cliente_id: number;
  cliente_nombre: string;
  cliente_rfc: string | null;
  monto: number;
  fecha: string;
  estatus: string;
  tipo_documento: string;
  condicion_pago: string;
  fecha_vencimiento: string | null;
  metodo_pago: string | null;
  notas: string | null;
  created_at: string;
  total_pagado: number;
  saldo_pendiente: number;
}

export interface FacturaDetalle extends Factura {
  cliente_telefono: string | null;
  cliente_direccion: string | null;
}

export interface Pago {
  id: number;
  factura_id: number;
  monto: number;
  fecha: string;
  metodo_pago: string | null;
  referencia: string | null;
  notas: string | null;
  created_at: string;
}

export interface ResumenCobranza {
  total_documentos: number;
  total_vendido: number;
  total_por_cobrar: number;
  docs_pendientes: number;
  docs_vencidos: number;
}

export interface ReporteDiario {
  fecha: string;
  total_facturas: number;
  rango_folios: string;
  total_dia: number;
  facturas: { folio: string; cliente: string; monto: number; estatus: string; tipo_documento: string; metodo_pago: string | null }[];
}

export interface ReporteMensualDia {
  fecha: string;
  folio_inicio: string;
  folio_fin: string;
  num_facturas: number;
  total_dia: number;
}

export interface ReporteMensual {
  anio: number;
  mes: number;
  dias: ReporteMensualDia[];
  total_dias_con_ventas: number;
  total_facturas: number;
  gran_total: number;
}

// ── Ventas Dashboard types ────────────────────────────────────────────────────

export interface VentasDashboardKPIs {
  total_documentos:   number;
  total_vendido:      number;
  clientes_con_compra: number;
  total_por_cobrar:   number;
  docs_pendientes:    number;
  docs_vencidos:      number;
  clientes_arriba:    number;
}

export interface VentasDashboardResponse {
  anio:      number;
  mes:       number;
  min_monto: number;
  kpis:      VentasDashboardKPIs;
}

export interface ClienteRanking {
  cliente_id:          number;
  cliente_nombre:      string;
  tipo:                string;
  num_docs:            number;
  total_mes:           number;
  saldo_pendiente_mes: number;
  ultima_compra:       string | null;
}

export interface TopClientesResponse {
  anio:      number;
  mes:       number;
  min_monto: number;
  clientes:  ClienteRanking[];
}

export interface ClienteDetalleStats {
  num_docs:              number;
  total_mes:             number;
  ultima_compra:         string | null;
  saldo_pendiente_total: number;
  total_historico:       number;
}

export interface DocResumen {
  id:              number;
  folio:           string;
  fecha:           string;
  monto:           number;
  estatus:         string;
  tipo_documento:  string;
  saldo_pendiente: number;
}

export interface ClienteDetalleResponse {
  cliente_id:           number;
  cliente_nombre:       string;
  tipo:                 string;
  anio:                 number;
  mes:                  number;
  stats:                ClienteDetalleStats;
  documentos_recientes: DocResumen[];
}

export const facturaService = {
  async getAll(params?: {
    fecha_inicio?: string; fecha_fin?: string; cliente_id?: number;
    estatus?: string; tipo_documento?: string; solo_pendientes?: boolean;
    q?: string; page?: number; page_size?: number;
  }): Promise<{ items: Factura[]; total: number; page: number; page_size: number }> {
    const p = new URLSearchParams();
    if (params?.fecha_inicio) p.set('fecha_inicio', params.fecha_inicio);
    if (params?.fecha_fin) p.set('fecha_fin', params.fecha_fin);
    if (params?.cliente_id) p.set('cliente_id', String(params.cliente_id));
    if (params?.estatus) p.set('estatus', params.estatus);
    if (params?.tipo_documento) p.set('tipo_documento', params.tipo_documento);
    if (params?.solo_pendientes) p.set('solo_pendientes', 'true');
    if (params?.q) p.set('q', params.q);
    if (params?.page) p.set('page', String(params.page));
    if (params?.page_size) p.set('page_size', String(params.page_size));
    return api(`/facturas?${p}`);
  },

  async getDetalle(id: number): Promise<{ documento: FacturaDetalle; pagos: Pago[] }> {
    return api(`/facturas/${id}`);
  },

  async resumenCobranza(params?: { fecha_inicio?: string; fecha_fin?: string }): Promise<ResumenCobranza> {
    const p = new URLSearchParams();
    if (params?.fecha_inicio) p.set('fecha_inicio', params.fecha_inicio);
    if (params?.fecha_fin) p.set('fecha_fin', params.fecha_fin);
    const qs = p.toString();
    return api(`/facturas/resumen-cobranza${qs ? `?${qs}` : ''}`);
  },

  async syncFacturas(fechaInicio: string, fechaFin?: string): Promise<{
    ok: boolean;
    fecha_inicio: string; fecha_fin: string; dias_procesados: number;
    total_pos_raw: number; total_pos_eligible: number;
    inserted: number; updated: number;
    skipped_no_client: number; skipped_cancelled: number; skipped_complement: number;
    errors: { pos_documento_id: number; reason?: string; error?: string }[];
  }> {
    const p = new URLSearchParams({ fecha_inicio: fechaInicio });
    if (fechaFin) p.set('fecha_fin', fechaFin);
    return api(`/sync/facturas?${p}`, { method: 'POST' });
  },

  async getByCliente(clienteId: number): Promise<{ items: Factura[]; count: number }> {
    return api(`/facturas/por-cliente/${clienteId}`);
  },

  async create(data: {
    folio: string; cliente_id: number; monto: number;
    fecha?: string; estatus?: string; tipo_documento?: string;
    condicion_pago?: string; fecha_vencimiento?: string;
    metodo_pago?: string; notas?: string;
  }): Promise<{ ok: boolean; factura: Factura }> {
    return api('/facturas', { method: 'POST', body: JSON.stringify(data) });
  },

  async update(id: number, data: Partial<{
    folio: string; fecha: string;
    monto: number; estatus: string; tipo_documento: string;
    condicion_pago: string; fecha_vencimiento: string;
    metodo_pago: string; notas: string;
  }>): Promise<{ ok: boolean }> {
    return api(`/facturas/${id}`, { method: 'PATCH', body: JSON.stringify(data) });
  },

  async delete(id: number): Promise<{ ok: boolean }> {
    return api(`/facturas/${id}`, { method: 'DELETE' });
  },

  async getPagos(facturaId: number): Promise<{ items: Pago[]; count: number }> {
    return api(`/facturas/${facturaId}/pagos`);
  },

  async createPago(facturaId: number, data: {
    monto: number; fecha?: string; metodo_pago?: string; referencia?: string; notas?: string;
  }): Promise<{ ok: boolean; pago: Pago; nuevo_estatus: string }> {
    return api(`/facturas/${facturaId}/pagos`, { method: 'POST', body: JSON.stringify({ ...data, factura_id: facturaId }) });
  },

  async getDashboard(anio?: number, mes?: number, minMonto?: number): Promise<VentasDashboardResponse> {
    const p = new URLSearchParams();
    if (anio)     p.set('anio',      String(anio));
    if (mes)      p.set('mes',       String(mes));
    if (minMonto) p.set('min_monto', String(minMonto));
    return api(`/facturas/dashboard?${p}`);
  },

  async getDashboardTopClientes(anio?: number, mes?: number, minMonto?: number, limit?: number): Promise<TopClientesResponse> {
    const p = new URLSearchParams();
    if (anio)     p.set('anio',      String(anio));
    if (mes)      p.set('mes',       String(mes));
    if (minMonto) p.set('min_monto', String(minMonto));
    if (limit)    p.set('limit',     String(limit));
    return api(`/facturas/dashboard/top-clientes?${p}`);
  },

  async getDashboardClienteDetalle(clienteId: number, anio?: number, mes?: number): Promise<ClienteDetalleResponse> {
    const p = new URLSearchParams();
    if (anio) p.set('anio', String(anio));
    if (mes)  p.set('mes',  String(mes));
    return api(`/facturas/dashboard/cliente/${clienteId}?${p}`);
  },

  async reporteDiario(fecha?: string, tipo_documento?: string): Promise<ReporteDiario> {
    const p = new URLSearchParams();
    if (fecha) p.set('fecha', fecha);
    if (tipo_documento) p.set('tipo_documento', tipo_documento);
    return api(`/facturas/reporte/diario?${p}`);
  },

  async reporteMensual(anio?: number, mes?: number, tipo_documento?: string): Promise<ReporteMensual> {
    const p = new URLSearchParams();
    if (anio) p.set('anio', String(anio));
    if (mes) p.set('mes', String(mes));
    if (tipo_documento) p.set('tipo_documento', tipo_documento);
    return api(`/facturas/reporte/mensual?${p}`);
  },

  async reporteClientesMayores(anio?: number, mes?: number, minMonto?: number): Promise<{ clientes: any[]; total_clientes: number }> {
    const p = new URLSearchParams();
    if (anio) p.set('anio', String(anio));
    if (mes) p.set('mes', String(mes));
    if (minMonto) p.set('min_monto', String(minMonto));
    return api(`/facturas/reporte/clientes-mayores?${p}`);
  },

  async controlCancelados(fechaInicio?: string, fechaFin?: string): Promise<{
    fecha_inicio: string;
    fecha_fin: string;
    total_cancelados: number;
    total_monto_cancelado: number;
    cancelados: {
      folio: string;
      serie: string | null;
      fecha: string;
      monto: number;
      uuid: string;
      cliente: string;
      pos_cfd_id: number;
      en_sistema: boolean;
      reemplazo: { folio: string; fecha: string; monto: number; uuid: string } | null;
    }[];
  }> {
    const p = new URLSearchParams();
    if (fechaInicio) p.set('fecha_inicio', fechaInicio);
    if (fechaFin)    p.set('fecha_fin',    fechaFin);
    const qs = p.toString();
    return api(`/facturas/control/cancelados${qs ? `?${qs}` : ''}`);
  },
};
