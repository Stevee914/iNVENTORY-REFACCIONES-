import { api } from './client';
import type { ProductoProveedor } from '@/types';

export interface ProductoProveedorCreateData {
  product_id: number;
  proveedor_id: number;
  supplier_sku: string;
  descripcion_proveedor?: string;
  is_primary?: boolean;
  precio_proveedor?: number;
}

export interface ProductoProveedorUpdateData {
  supplier_sku?: string;
  descripcion_proveedor?: string;
  is_primary?: boolean;
  precio_proveedor?: number;
}

export const productoProveedorService = {
  async getByProduct(productId: number): Promise<{ items: ProductoProveedor[]; count: number }> {
    return api(`/producto-proveedor?product_id=${productId}`);
  },

  async getByProveedor(proveedorId: number): Promise<{ items: ProductoProveedor[]; count: number }> {
    return api(`/producto-proveedor?proveedor_id=${proveedorId}`);
  },

  async create(data: ProductoProveedorCreateData): Promise<{ ok: boolean; mapping: ProductoProveedor }> {
    return api('/producto-proveedor', {
      method: 'POST',
      body: JSON.stringify(data),
    });
  },

  async update(id: number, data: ProductoProveedorUpdateData): Promise<{ ok: boolean; mapping: ProductoProveedor }> {
    return api(`/producto-proveedor/${id}`, {
      method: 'PATCH',
      body: JSON.stringify(data),
    });
  },

  async delete(id: number): Promise<{ ok: boolean; deleted: number }> {
    return api(`/producto-proveedor/${id}`, { method: 'DELETE' });
  },
};
