import { api } from './client';
import type { Movement, MovementFormData } from '@/types';

export const movementService = {
  async create(data: MovementFormData): Promise<{ ok: boolean; movement: Movement }> {
    return api('/movements', {
      method: 'POST',
      body: JSON.stringify({
        sku: data.sku,
        movement_type: data.movement_type,
        quantity: data.quantity,
        libro: data.libro,
        evento: data.evento || undefined,
        reference: data.reference || undefined,
        notes: data.notes || undefined,
        proveedor_id: data.proveedor_id || undefined,
        costo_unit_sin_iva: data.costo_unit_sin_iva || undefined,
        tasa_iva: data.tasa_iva ?? 0.16,
        precio_venta_unit: data.precio_venta_unit || undefined,
      }),
    });
  },

  async getKardex(sku: string, limit = 100): Promise<{ sku: string; items: Movement[]; count: number }> {
    return api(`/movements/kardex/${encodeURIComponent(sku)}?limit=${limit}`);
  },
};
