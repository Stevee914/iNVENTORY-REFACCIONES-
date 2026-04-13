import { api } from './client';

export interface Marca {
  id: number;
  nombre: string;
  slug: string;
  primer_anio: number | null;
  ultimo_anio: number | null;
}

export interface Modelo {
  id: number;
  nombre: string;
  vehicle_type: string | null;
}

export interface Aplicacion {
  id: number;
  motor: string;
  traccion: string | null;
  carroceria: string | null;
}

export interface ProductoAplicacion {
  id: number;
  sku: string;
  codigo_pos: string | null;
  marca: string | null;
  name: string;
  unit: string | null;
  price: number | null;
  costo_pos_con_iva: number | null;
  min_stock: number | null;
  is_active: boolean;
  imagen_url: string | null;
  notas_aplicacion: string | null;
  stock: number;
}

export interface AplicacionProducto {
  marca_id: number;
  marca: string;
  modelo_id: number;
  modelo: string;
  anio: number;
  aplicacion_id: number;
  motor: string;
  traccion: string | null;
  carroceria: string | null;
  notas_aplicacion: string | null;
}

export const vehiculosService = {
  getMarcas: () =>
    api<Marca[]>('/vehiculos/marcas'),

  getModelos: (marcaId: number) =>
    api<Modelo[]>(`/vehiculos/modelos?marca_id=${marcaId}`),

  getAnios: (modeloId: number) =>
    api<number[]>(`/vehiculos/anios?modelo_id=${modeloId}`),

  getAplicaciones: (modeloId: number, anio: number) =>
    api<Aplicacion[]>(`/vehiculos/aplicaciones?modelo_id=${modeloId}&anio=${anio}`),

  getProductosByModeloAnio: (modeloId: number, anio: number, motor?: string) => {
    const qs = motor ? `&motor=${encodeURIComponent(motor)}` : '';
    return api<{ motores: string[]; items: ProductoAplicacion[] }>(
      `/vehiculos/productos?modelo_id=${modeloId}&anio=${anio}${qs}`
    );
  },

  getProductosByAplicacion: (aplicacionId: number) =>
    api<ProductoAplicacion[]>(`/vehiculos/aplicaciones/${aplicacionId}/productos`),

  getAplicacionesByProducto: (productoId: number) =>
    api<AplicacionProducto[]>(`/vehiculos/productos/${productoId}/aplicaciones`),

  linkProducto: (aplicacionId: number, productoId: number, notas?: string) => {
    const qs = notas ? `?notas=${encodeURIComponent(notas)}` : '';
    return api<{ ok: boolean }>(`/vehiculos/aplicaciones/${aplicacionId}/productos/${productoId}${qs}`, {
      method: 'POST',
    });
  },

  unlinkProducto: (aplicacionId: number, productoId: number) =>
    api<{ ok: boolean }>(`/vehiculos/aplicaciones/${aplicacionId}/productos/${productoId}`, {
      method: 'DELETE',
    }),
};
