import { api } from './client';

export interface Faltante {
  id: number;
  product_id: number;
  sku: string;
  product_name: string;
  marca: string | null;
  cantidad_faltante: number;
  comentario: string | null;
  fecha_detectado: string;
  status: 'pendiente' | 'comprado' | 'cancelado';
  proveedor_id: number | null;
  proveedor_nombre: string | null;
}

export interface FaltanteGrupo {
  proveedor_id: number | null;
  proveedor_nombre: string;
  productos: {
    faltante_id: number;
    product_id: number;
    sku: string;
    product_name: string;
    marca: string | null;
    unit: string | null;
    cantidad_faltante: number;
    comentario: string | null;
    fecha_detectado: string;
    supplier_sku: string | null;
    precio_proveedor: number | null;
  }[];
  total_items: number;
}

export const faltantesService = {
  async getAll(status?: string): Promise<{ items: Faltante[]; count: number }> {
    const params = status ? `?status=${status}` : '';
    return api(`/faltantes${params}`);
  },

  async create(data: { product_id: number; cantidad_faltante: number; comentario?: string }): Promise<{ ok: boolean }> {
    return api('/faltantes', {
      method: 'POST',
      body: JSON.stringify(data),
    });
  },

  async update(id: number, data: {
    product_id?:        number;
    cantidad_faltante?: number;
    comentario?:        string | null;
    status?:            string;
  }): Promise<{ ok: boolean }> {
    return api(`/faltantes/${id}`, {
      method: 'PATCH',
      body: JSON.stringify(data),
    });
  },

  async updateStatus(id: number, status: string): Promise<{ ok: boolean }> {
    return api(`/faltantes/${id}`, {
      method: 'PATCH',
      body: JSON.stringify({ status }),
    });
  },

  async delete(id: number): Promise<{ ok: boolean }> {
    return api(`/faltantes/${id}`, { method: 'DELETE' });
  },

  async getPorProveedor(): Promise<{ grupos: FaltanteGrupo[]; total_proveedores: number }> {
    return api('/faltantes/por-proveedor');
  },
};
