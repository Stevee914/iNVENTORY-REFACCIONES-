// ─── Tipos alineados al backend FastAPI refactorizado ──────────

export interface Product {
  id: number;
  sku: string;
  codigo_pos: string | null;
  codigo_cat: string | null;
  marca: string | null;
  name: string;
  categoria_id: number | null;
  unit: string;
  min_stock: number;
  price: number;
  is_active: boolean;
  created_at: string;
  aplicacion: string | null;
  equivalencia: string | null;
  ubicacion: string | null;
  descripcion_larga: string | null;
  anio_inicio: number | null;
  anio_fin: number | null;
  dim_largo: number | null;
  dim_ancho: number | null;
  dim_alto: number | null;
  imagen_url: string | null;
}

// ─── Completitud de ficha técnica ──────────────────────────────

const FICHA_FIELDS: (keyof Product)[] = [
  'aplicacion', 'equivalencia', 'ubicacion', 'descripcion_larga',
  'dim_largo', 'dim_ancho', 'dim_alto',
];

export type FichaLevel = 'Básico' | 'Parcial' | 'Completo';

export function getFichaLevel(product: Product): { level: FichaLevel; filled: number; total: number } {
  const total = FICHA_FIELDS.length;
  const filled = FICHA_FIELDS.filter((f) => {
    const v = product[f];
    return v !== null && v !== undefined && v !== '' && v !== 0;
  }).length;
  let level: FichaLevel = 'Básico';
  if (filled === total) level = 'Completo';
  else if (filled > 0) level = 'Parcial';
  return { level, filled, total };
}

// ─── Stock ─────────────────────────────────────────────────────

export interface StockItem {
  product_id: number;
  sku: string;
  name: string;
  min_stock: number;
  stock_fisico: number;
  stock_pos: number;
  stock_total: number;
}

export type StockStatus = 'ok' | 'warn' | 'critical';

export function getStockStatus(stockFisico: number, minStock: number): StockStatus {
  if (stockFisico <= 0) return 'critical';
  if (stockFisico <= minStock * 0.5) return 'critical';
  if (stockFisico <= minStock) return 'warn';
  return 'ok';
}

// ─── Movimientos ───────────────────────────────────────────────

export type MovementType = 'IN' | 'OUT' | 'ADJUST';
export type Libro = 'FISICO' | 'FISCAL_POS';
export type Evento = 'ENTRADA_FACTURA' | 'ENTRADA_MOSTRADOR' | 'VENTA_FACTURADA' | 'VENTA_MOSTRADOR' | 'AJUSTE';

export interface Movement {
  id: number;
  sku: string;
  libro: Libro;
  movement_type: MovementType;
  evento: Evento;
  quantity: number;
  reference: string | null;
  notes: string | null;
  proveedor_id: number | null;
  costo_unit_sin_iva: number | null;
  tasa_iva: number;
  costo_unit_con_iva: number | null;
  precio_venta_unit: number | null;
  movement_date: string;
  created_at: string;
}

export interface MovementFormData {
  sku: string;
  movement_type: MovementType;
  quantity: number;
  libro: Libro;
  evento?: Evento;
  reference: string;
  notes: string;
  proveedor_id?: number | null;
  costo_unit_sin_iva?: number | null;
  tasa_iva?: number;
  precio_venta_unit?: number | null;
}

// ─── Proveedores ───────────────────────────────────────────────

export interface Proveedor {
  id: number;
  nombre: string;
  codigo_corto: string;
  rfc: string | null;
  created_at: string;
}

export interface ProveedorFormData {
  nombre: string;
  codigo_corto: string;
  rfc: string;
}

// ─── Categorías ────────────────────────────────────────────────

export interface Categoria {
  id: number;
  name: string;
  description: string | null;
  parent_id: number | null;
  parent_name?: string | null;
  created_at: string;
  subcategorias?: Categoria[];
}

export interface CategoriaFormData {
  name: string;
  description: string;
  parent_id: number | null;
}

// ─── Producto-Proveedor ────────────────────────────────────────

export interface ProductoProveedor {
  id: number;
  proveedor_id: number;
  proveedor_nombre: string;
  product_id: number;
  sku: string;
  product_name: string;
  supplier_sku: string;
  descripcion_proveedor: string | null;
  is_primary: boolean;
  created_at: string;
}

// ─── Dashboard ─────────────────────────────────────────────────

export interface DashboardResumen {
  total_productos: number;
  productos_activos: number;
  stock_negativo: number;
  bajo_minimo: number;
  sin_stock_con_minimo: number;
  valor_inventario_fisico: number;
  movimientos_30d: {
    total: number;
    entradas: number;
    salidas: number;
    ajustes: number;
  };
  total_categorias: number;
  total_proveedores: number;
}

export interface ProductoCritico {
  product_id: number;
  sku: string;
  name: string;
  min_stock: number;
  stock_fisico: number;
  stock_pos: number;
  stock_total: number;
  price: number;
  marca: string | null;
}

// ─── Formularios ───────────────────────────────────────────────

export interface ProductFormData {
  sku: string;
  name: string;
  categoria_id: number | null;
  unit: string;
  min_stock: number;
  price: number;
  is_active: boolean;
  codigo_cat: string;
  codigo_pos: string;
  marca: string;
}

export interface TechFormData {
  aplicacion: string;
  equivalencia: string;
  ubicacion: string;
  descripcion_larga: string;
  anio_inicio: number | null;
  anio_fin: number | null;
  dim_largo: number | null;
  dim_ancho: number | null;
  dim_alto: number | null;
  imagen_url: string | null;
}

// ─── Forecast (provisional) ────────────────────────────────────

export interface ForecastItem {
  sku: string;
  productName: string;
  category: string;
  currentStock: number;
  avgMonthlyDemand: number;
  forecast30d: number;
  suggestedReorder: number;
  leadTimeDays: number;
  safetyStock: number;
  status: 'Reordenar' | 'Revisar' | 'OK';
}

export interface TrendPoint {
  date: string;
  entries: number;
  exits: number;
}

// ─── Helpers de evento ─────────────────────────────────────────

export const EVENTO_LABELS: Record<Evento, string> = {
  ENTRADA_FACTURA: 'Entrada Factura',
  ENTRADA_MOSTRADOR: 'Entrada Mostrador',
  VENTA_FACTURADA: 'Venta Facturada',
  VENTA_MOSTRADOR: 'Venta Mostrador',
  AJUSTE: 'Ajuste',
};

export const EVENTO_COLORS: Record<Evento, string> = {
  ENTRADA_FACTURA: 'bg-emerald-50 text-emerald-700 border-emerald-200',
  ENTRADA_MOSTRADOR: 'bg-teal-50 text-teal-700 border-teal-200',
  VENTA_FACTURADA: 'bg-purple-50 text-purple-700 border-purple-200',
  VENTA_MOSTRADOR: 'bg-red-50 text-red-700 border-red-200',
  AJUSTE: 'bg-amber-50 text-amber-700 border-amber-200',
};
