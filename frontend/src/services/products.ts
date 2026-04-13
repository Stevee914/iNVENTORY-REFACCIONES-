import { api } from './client';
import type { Product, ProductFormData, TechFormData, ProductMargen } from '@/types';

export type CatalogProduct = Product & { stock_fisico: number; stock_pos: number };

export interface CatalogListResult {
  items: CatalogProduct[];
  total: number;
  page: number;
  page_size: number;
}

export const productService = {
  // GET /products
  async getAll(): Promise<Product[]> {
    const res = await api<{ items: Product[]; total: number }>('/products?page_size=50000');
    return res.items;
  },

  // GET /products/{sku} — detalle completo con campos técnicos
  async getBySku(sku: string): Promise<Product> {
    return api<Product>(`/products/${encodeURIComponent(sku)}`);
  },

  // GET /products/search?q=...&limit=...
  async search(q: string, limit = 20): Promise<{ items: Product[]; count: number }> {
    return api(`/products/search?q=${encodeURIComponent(q)}&limit=${limit}`);
  },

  // GET /products/count
  async count(): Promise<number> {
    const res = await api<{ count: number }>('/products/count');
    return res.count;
  },

  // POST /products (upsert por SKU)
  async create(data: ProductFormData): Promise<{ ok: boolean; action: string; product: Product }> {
    return api('/products', {
      method: 'POST',
      body: JSON.stringify({
        sku: data.sku,
        name: data.name,
        categoria_id: data.categoria_id,
        unit: data.unit,
        min_stock: data.min_stock,
        price: data.price,
        is_active: data.is_active,
        codigo_cat: data.codigo_cat || undefined,
        codigo_pos: data.codigo_pos || undefined,
        marca: data.marca || undefined,
      }),
    });
  },

  // PATCH /products/{sku} — actualización parcial (datos base)
  async update(sku: string, data: Partial<ProductFormData>): Promise<{ ok: boolean; product: Product }> {
    return api(`/products/${encodeURIComponent(sku)}`, {
      method: 'PATCH',
      body: JSON.stringify(data),
    });
  },

  // GET /products — paginated catalog with stock, category and brand filters
  async listCatalog(params: {
    categoria_id?: number;
    parent_categoria_id?: number;
    marca?: string;
    q?: string;
    sort?: string;
    page?: number;
    page_size?: number;
  }): Promise<CatalogListResult> {
    const p = new URLSearchParams();
    if (params.page != null) p.set('page', String(params.page));
    if (params.page_size != null) p.set('page_size', String(params.page_size));
    if (params.categoria_id != null) p.set('categoria_id', String(params.categoria_id));
    if (params.parent_categoria_id != null) p.set('parent_categoria_id', String(params.parent_categoria_id));
    if (params.marca) p.set('marca', params.marca);
    if (params.q) p.set('q', params.q);
    if (params.sort) p.set('sort', params.sort);
    return api(`/products?${p.toString()}`);
  },

  // GET /products/marcas — filtered brand list for dropdowns
  async getMarcasByCat(params: {
    categoria_id?: number;
    parent_categoria_id?: number;
  }): Promise<string[]> {
    const p = new URLSearchParams();
    if (params.categoria_id != null) p.set('categoria_id', String(params.categoria_id));
    if (params.parent_categoria_id != null) p.set('parent_categoria_id', String(params.parent_categoria_id));
    return api(`/products/marcas?${p.toString()}`);
  },

  // GET /products/{sku}/margen — pricing & margin data
  async getMargen(sku: string): Promise<ProductMargen> {
    return api<ProductMargen>(`/products/${encodeURIComponent(sku)}/margen`);
  },

  // PATCH /products/{sku} — actualización parcial (ficha técnica)
  async updateTech(sku: string, data: Partial<TechFormData>): Promise<{ ok: boolean; product: Product }> {
    // Filtramos campos vacíos para no enviar strings vacíos como null
    const payload: Record<string, unknown> = {};
    for (const [key, value] of Object.entries(data)) {
      if (value !== undefined && value !== '') {
        payload[key] = value;
      } else if (value === '') {
        payload[key] = null; // Limpiar campo
      }
    }
    return api(`/products/${encodeURIComponent(sku)}`, {
      method: 'PATCH',
      body: JSON.stringify(payload),
    });
  },
};
