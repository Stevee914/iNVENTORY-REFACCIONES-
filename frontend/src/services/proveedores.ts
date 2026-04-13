import { api } from './client';
import type { Proveedor, ProveedorFormData } from '@/types';

export const proveedorService = {
  async getAll(): Promise<Proveedor[]> {
    return api<Proveedor[]>('/proveedores');
  },

  async getById(id: number): Promise<Proveedor> {
    return api<Proveedor>(`/proveedores/${id}`);
  },

  async search(q: string): Promise<{ items: Proveedor[]; count: number }> {
    return api(`/proveedores/search?q=${encodeURIComponent(q)}`);
  },

  async create(data: ProveedorFormData): Promise<{ ok: boolean; proveedor: Proveedor }> {
    return api('/proveedores', {
      method: 'POST',
      body: JSON.stringify({
        nombre: data.nombre,
        codigo_corto: data.codigo_corto,
        rfc: data.rfc || undefined,
      }),
    });
  },

  async update(id: number, data: Partial<ProveedorFormData>): Promise<{ ok: boolean; proveedor: Proveedor }> {
    return api(`/proveedores/${id}`, {
      method: 'PATCH',
      body: JSON.stringify(data),
    });
  },

  async delete(id: number): Promise<{ ok: boolean }> {
    return api(`/proveedores/${id}`, { method: 'DELETE' });
  },
};
