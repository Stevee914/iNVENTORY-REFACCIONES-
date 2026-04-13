import { api } from './client';

export interface Cliente {
  id: number;
  nombre: string;
  rfc: string | null;
  direccion: string | null;
  telefono: string | null;
  correo: string | null;
  tipo: string;
  notas: string | null;
  is_active: boolean;
  created_at: string;
  total_facturas?: number;
  total_compras?: number;
  saldo_pendiente?: number;
}

export interface ClienteFormData {
  nombre: string;
  rfc?: string;
  direccion?: string;
  telefono?: string;
  correo?: string;
  tipo: string;
  notas?: string;
}

export const clienteService = {
  async getAll(q?: string, tipo?: string): Promise<{ items: Cliente[]; count: number }> {
    const params = new URLSearchParams();
    if (q) params.set('q', q);
    if (tipo) params.set('tipo', tipo);
    params.set('only_active', 'false');
    return api(`/clientes?${params}`);
  },

  async getById(id: number): Promise<Cliente> {
    return api(`/clientes/${id}`);
  },

  async getResumen(): Promise<{ items: Cliente[]; count: number }> {
    return api('/clientes/resumen');
  },

  async getTop(minMonto?: number): Promise<{ items: Cliente[]; count: number }> {
    const p = minMonto ? `?min_monto=${minMonto}` : '';
    return api(`/clientes/top${p}`);
  },

  async getDeudores(): Promise<{ items: Cliente[]; count: number }> {
    return api('/clientes/deudores');
  },

  async create(data: ClienteFormData): Promise<{ ok: boolean; cliente: Cliente }> {
    return api('/clientes', { method: 'POST', body: JSON.stringify(data) });
  },

  async update(id: number, data: Partial<ClienteFormData & { is_active: boolean }>): Promise<{ ok: boolean; cliente: Cliente }> {
    return api(`/clientes/${id}`, { method: 'PATCH', body: JSON.stringify(data) });
  },

  async delete(id: number): Promise<{ ok: boolean }> {
    return api(`/clientes/${id}`, { method: 'DELETE' });
  },
};
