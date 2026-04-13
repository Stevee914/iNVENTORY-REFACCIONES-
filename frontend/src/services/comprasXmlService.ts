import { api } from './client';

const BASE_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000';

export interface XmlUploadResult {
  ok: boolean;
  compra_id: number;
  uuid: string;
  folio_factura: string;
  proveedor: {
    resolved: boolean;
    id: number | null;
    nombre: string | null;
    rfc_xml: string;
    nombre_xml: string;
  };
  totales: { subtotal: number; descuento: number; iva: number; total: number };
  lineas: {
    total: number;
    matched: number;
    suggested: number;
    unresolved: number;
    service: number;
  };
  estatus_workflow: string;
}

export interface Candidate {
  product_id: number;
  sku: string;
  name: string;
}

export interface LineaDetalle {
  id: number;
  product_id: number | null;
  cantidad: number;
  precio_unit: number | null;
  supplier_sku: string | null;
  descripcion_xml: string | null;
  codigo_proveedor: string | null;
  clave_prod_serv: string | null;
  descuento: number;
  iva: number;
  status_match: string;
  matched_by: string | null;
  es_servicio: boolean;
  product_sku: string | null;
  product_name: string | null;
  candidates: Candidate[];
}

export interface CompraXmlHeader {
  id: number;
  proveedor_id: number | null;
  folio_factura: string | null;
  fecha: string;
  subtotal: number;
  iva: number;
  total: number;
  estatus: string;
  metodo_pago: string | null;
  estatus_recepcion: string;
  estatus_workflow: string;
  uuid_fiscal: string | null;
  origen: string;
  notas: string | null;
  proveedor_nombre: string | null;
  proveedor_rfc: string | null;
  descuento_financiero: number;
  subtotal_original: number | null;
  iva_original: number | null;
  total_original: number | null;
}

export interface RevisionData {
  compra: CompraXmlHeader;
  lineas: LineaDetalle[];
  counts: Record<string, number>;
  puede_importar: boolean;
}

export const comprasXmlService = {
  async uploadXml(file: File): Promise<XmlUploadResult> {
    const formData = new FormData();
    formData.append('file', file);
    const res = await fetch(`${BASE_URL}/compras/upload-xml`, {
      method: 'POST',
      body: formData,
    });
    if (!res.ok) {
      const err = await res.json().catch(() => ({ detail: 'Error subiendo XML' }));
      throw new Error(err.detail || `Error ${res.status}`);
    }
    return res.json();
  },

  async getRevision(compraId: number): Promise<RevisionData> {
    return api(`/compras/${compraId}/revision`);
  },

  async confirmarMatch(compraId: number, lineaId: number, productId: number) {
    return api(`/compras/${compraId}/lineas/${lineaId}/confirmar`, {
      method: 'PATCH',
      body: JSON.stringify({ product_id: productId }),
    });
  },

  async crearProducto(
    compraId: number,
    lineaId: number,
    data: {
      sku: string;
      name: string;
      marca?: string;
      categoria_id?: number;
      unit?: string;
      min_stock?: number;
      price?: number;
      precio_publico?: number;
      codigo_cat?: string;
    }
  ) {
    return api(`/compras/${compraId}/lineas/${lineaId}/crear-producto`, {
      method: 'POST',
      body: JSON.stringify(data),
    });
  },

  async importar(compraId: number) {
    return api(`/compras/${compraId}/importar`, { method: 'POST' });
  },

  async cancelarCompra(compraId: number) {
    return api(`/compras/${compraId}`, { method: 'DELETE' });
  },

  async setDescuentoFinanciero(compraId: number, porcentaje: number) {
    return api(`/compras/${compraId}/descuento-financiero`, {
      method: 'PATCH',
      body: JSON.stringify({ porcentaje }),
    });
  },

  async excluirLinea(compraId: number, lineaId: number) {
    return api(`/compras/${compraId}/lineas/${lineaId}/excluir`, { method: 'PATCH' });
  },

  async incluirLinea(compraId: number, lineaId: number) {
    return api(`/compras/${compraId}/lineas/${lineaId}/incluir`, { method: 'PATCH' });
  },
};
