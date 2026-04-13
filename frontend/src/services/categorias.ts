import { api } from './client';
import type { Categoria, CategoriaFormData } from '@/types';

export const categoriaService = {
  async getAll(): Promise<Categoria[]> {
    return api<Categoria[]>('/categorias');
  },

  async getTree(): Promise<Categoria[]> {
    return api<Categoria[]>('/categorias/tree');
  },

  async getById(id: number): Promise<Categoria> {
    return api<Categoria>(`/categorias/${id}`);
  },

  async create(data: CategoriaFormData): Promise<{ ok: boolean; categoria: Categoria }> {
    return api('/categorias', {
      method: 'POST',
      body: JSON.stringify({
        name: data.name,
        description: data.description || undefined,
        parent_id: data.parent_id,
      }),
    });
  },

  async update(id: number, data: Partial<CategoriaFormData>): Promise<{ ok: boolean; categoria: Categoria }> {
    return api(`/categorias/${id}`, {
      method: 'PATCH',
      body: JSON.stringify(data),
    });
  },
};
