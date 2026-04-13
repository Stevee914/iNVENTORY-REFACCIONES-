import { api } from './client';
import type { DashboardResumen, ProductoCritico, StockItem } from '@/types';

export const dashboardService = {
  async getResumen(): Promise<DashboardResumen> {
    return api<DashboardResumen>('/dashboard/resumen');
  },

  async getProductosCriticos(): Promise<{ items: ProductoCritico[]; count: number }> {
    return api('/dashboard/productos-criticos');
  },

  async getDiferenciasLibros(): Promise<{ items: StockItem[]; count: number }> {
    return api('/dashboard/diferencias-libros');
  },
};
