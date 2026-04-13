import { api } from './client';
import type { StockItem } from '@/types';

interface StockResponse {
  page: number;
  page_size: number;
  total: number;
  items: StockItem[];
}

export const stockService = {
  // GET /stock?q=...&page=...&page_size=...&below_min_stock=...
  async getAll(params?: {
    q?: string;
    page?: number;
    pageSize?: number;
    belowMinStock?: boolean;
    onlyNegative?: boolean;
  }): Promise<StockResponse> {
    const searchParams = new URLSearchParams();
    if (params?.q) searchParams.set('q', params.q);
    if (params?.page) searchParams.set('page', String(params.page));
    if (params?.pageSize) searchParams.set('page_size', String(params.pageSize));
    if (params?.belowMinStock) searchParams.set('below_min_stock', 'true');
    if (params?.onlyNegative) searchParams.set('only_negative', 'true');

    const qs = searchParams.toString();
    return api<StockResponse>(`/stock${qs ? '?' + qs : ''}`);
  },

  // GET /stock/{sku}
  async getBySku(sku: string): Promise<StockItem> {
    return api<StockItem>(`/stock/${encodeURIComponent(sku)}`);
  },
};
