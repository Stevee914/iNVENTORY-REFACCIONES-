import { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { Plus, Pencil, AlertTriangle } from 'lucide-react';
import { PageHeader, DataTable, fuzzyMatch, type Column } from '@/components/shared';
import { productService, stockService } from '@/services';
import { categoriaService } from '@/services/categorias';
import { type Product, type Categoria } from '@/types';
import { cn } from '@/lib/utils';

type StockMap = Record<string, { stock_fisico: number; stock_pos: number }>;

const CACHE_KEY = 'products_cache';
const CACHE_TTL = 5 * 60 * 1000; // 5 minutes

interface ProductsCache {
  products: Product[];
  stockMap: StockMap;
  categorias: Categoria[];
  cachedAt: number;
}

function readCache(): ProductsCache | null {
  try {
    const raw = sessionStorage.getItem(CACHE_KEY);
    if (!raw) return null;
    const parsed: ProductsCache = JSON.parse(raw);
    if (Date.now() - parsed.cachedAt > CACHE_TTL) {
      sessionStorage.removeItem(CACHE_KEY);
      return null;
    }
    return parsed;
  } catch {
    return null;
  }
}

function writeCache(data: Omit<ProductsCache, 'cachedAt'>) {
  try {
    sessionStorage.setItem(CACHE_KEY, JSON.stringify({ ...data, cachedAt: Date.now() }));
  } catch {
    // sessionStorage quota exceeded — silently skip
  }
}

export function ProductsPage() {
  const navigate = useNavigate();

  const cached = readCache();

  const [products, setProducts] = useState<Product[]>(cached?.products ?? []);
  const [stockMap, setStockMap] = useState<StockMap>(cached?.stockMap ?? {});
  const [loading, setLoading] = useState(cached === null);
  const [error, setError] = useState('');
  const [statusFilter, setStatusFilter] = useState<'all' | 'active' | 'inactive'>(
    () => (sessionStorage.getItem('products_status') as 'all' | 'active' | 'inactive') ?? 'all'
  );
  const [categorias, setCategorias] = useState<Categoria[]>(cached?.categorias ?? []);
  const [filterCatId, setFilterCatId] = useState<number | ''>(
    () => { const v = sessionStorage.getItem('products_cat'); return v ? Number(v) : ''; }
  );
  const [filterSubcatId, setFilterSubcatId] = useState<number | ''>(
    () => { const v = sessionStorage.getItem('products_subcat'); return v ? Number(v) : ''; }
  );

  useEffect(() => {
    // If we loaded from cache, re-fetch silently in background to stay fresh.
    // If no cache, this is the blocking load — show spinner until done.
    const background = cached !== null;

    Promise.all([
      productService.getAll(),
      stockService.getAll({ pageSize: 50000 }),
      categoriaService.getAll(),
    ])
      .then(([prods, stockRes, cats]) => {
        const map: StockMap = {};
        for (const s of stockRes.items) {
          map[s.sku] = { stock_fisico: Number(s.stock_fisico), stock_pos: Number(s.stock_pos) };
        }
        setProducts(prods);
        setStockMap(map);
        setCategorias(cats);
        writeCache({ products: prods, stockMap: map, categorias: cats });
      })
      .catch((e) => { if (!background) setError(e.message); })
      .finally(() => { if (!background) setLoading(false); });
  }, []);

  // Flat lists derived from loaded categories
  const parentCats = categorias.filter((c) => c.parent_id === null);
  const subcats = filterCatId !== ''
    ? categorias.filter((c) => c.parent_id === filterCatId)
    : [];

  // All categoria_ids that belong to the selected parent (parent itself + its children)
  const catIdSet: Set<number> = filterCatId !== ''
    ? new Set([filterCatId, ...categorias.filter((c) => c.parent_id === filterCatId).map((c) => c.id)])
    : new Set();

  const filtered = products.filter((p) => {
    if (statusFilter === 'active' && !p.is_active) return false;
    if (statusFilter === 'inactive' && p.is_active) return false;
    if (filterSubcatId !== '') return p.categoria_id === filterSubcatId;
    if (filterCatId !== '') return p.categoria_id !== null && catIdSet.has(p.categoria_id);
    return true;
  });

  const columns: Column<Product>[] = [
    {
      key: 'sku',
      header: 'SKU',
      render: (p) => <span className="font-mono text-xs font-medium text-brand-600">{p.sku}</span>,
      className: 'w-32',
    },
    {
      key: 'codigo_pos',
      header: 'Cód. POS',
      render: (p) => <span className="font-mono text-xs text-brand-400">{p.codigo_pos || '—'}</span>,
      className: 'hidden sm:table-cell w-28',
    },
    {
      key: 'name',
      header: 'Producto',
      render: (p) => (
        <div className="cursor-pointer" onClick={() => navigate(`/productos/${p.sku}`)}>
          <p className="text-[13px] font-medium text-brand-800 truncate max-w-xs hover:text-status-info transition-colors">{p.name}</p>
          {p.marca && <p className="text-xs text-brand-400">{p.marca}</p>}
        </div>
      ),
    },
    {
      key: 'unit',
      header: 'Unidad',
      render: (p) => <span className="text-xs text-brand-500">{p.unit}</span>,
      className: 'hidden sm:table-cell w-20',
    },
    {
      key: 'costo_pos_con_iva',
      header: 'Costo c/IVA',
      render: (p) => (
        <span className="tabular-nums text-xs text-brand-500">
          {p.costo_pos_con_iva != null && p.costo_pos_con_iva > 0
            ? `$${p.costo_pos_con_iva.toLocaleString('es-MX', { minimumFractionDigits: 2 })}`
            : '—'}
        </span>
      ),
      className: 'w-24 text-right',
    },
    {
      key: 'precio_publico',
      header: 'Precio venta',
      render: (p) => (
        <span className="tabular-nums text-xs font-semibold text-emerald-700">
          {p.precio_publico != null && p.precio_publico > 0
            ? `$${p.precio_publico.toLocaleString('es-MX', { minimumFractionDigits: 2 })}`
            : '—'}
        </span>
      ),
      className: 'w-24 text-right',
    },
    {
      key: 'stock_fisico' as keyof Product,
      header: 'Stock Físico',
      render: (p) => {
        const s = stockMap[p.sku];
        const val = s ? s.stock_fisico : 0;
        return (
          <span className={cn('tabular-nums text-xs font-medium', val < 0 ? 'text-status-critical' : 'text-brand-700')}>
            {val}
          </span>
        );
      },
      className: 'w-24 text-right',
    },
    {
      key: 'stock_pos' as keyof Product,
      header: 'Stock POS',
      render: (p) => {
        const s = stockMap[p.sku];
        const val = s ? s.stock_pos : 0;
        return (
          <span className={cn('tabular-nums text-xs font-medium', val < 0 ? 'text-status-critical' : 'text-brand-500')}>
            {val}
          </span>
        );
      },
      className: 'hidden sm:table-cell w-24 text-right',
    },
    {
      key: 'active',
      header: 'Activo',
      render: (p) => (
        <span className={cn('w-2 h-2 rounded-full inline-block', p.is_active ? 'bg-status-ok' : 'bg-surface-300')} />
      ),
      className: 'hidden sm:table-cell w-14 text-center',
    },
    {
      key: 'actions',
      header: '',
      render: (p) => (
        <div className="flex items-center gap-0.5">
          <button
            onClick={() => navigate(`/productos/${p.sku}/editar`)}
            className="btn-ghost p-1.5"
            title="Editar datos base"
          >
            <Pencil className="w-4 h-4" />
          </button>
        </div>
      ),
      className: 'w-16',
    },
  ];

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="w-6 h-6 border-2 border-surface-300 border-t-sap-blue rounded-full animate-spin" />
      </div>
    );
  }

  if (error) {
    return (
      <div className="card p-8 text-center">
        <AlertTriangle className="w-10 h-10 mx-auto text-status-critical mb-3" />
        <p className="text-[13px] text-brand-500">{error}</p>
      </div>
    );
  }

  return (
    <div>
      <PageHeader
        title="Catálogo de Productos"
        description={`${products.length} productos`}
        actions={
          <button onClick={() => navigate('/productos/nuevo')} className="btn-primary">
            <Plus className="w-4 h-4" /> Nuevo Producto
          </button>
        }
      />

      <DataTable
        data={filtered}
        columns={columns}
        storageKey="products"
        searchPlaceholder="Buscar por SKU, nombre, marca, cód. POS..."
        searchFn={(p, q) => {
          const text = [p.sku, p.name, p.marca, p.codigo_pos].filter(Boolean).join(' ');
          return fuzzyMatch(text, q);
        }}
        filters={
          <>
            <select
              value={statusFilter}
              onChange={(e) => { const v = e.target.value as typeof statusFilter; sessionStorage.setItem('products_status', v); setStatusFilter(v); }}
              className="select-field w-32 py-2 text-xs"
            >
              <option value="all">Todos</option>
              <option value="active">Activos</option>
              <option value="inactive">Inactivos</option>
            </select>
            <select
              value={filterCatId}
              onChange={(e) => {
                const val = e.target.value === '' ? '' : Number(e.target.value);
                sessionStorage.setItem('products_cat', e.target.value);
                sessionStorage.removeItem('products_subcat');
                setFilterCatId(val);
                setFilterSubcatId('');
              }}
              className="select-field w-40 py-2 text-xs"
            >
              <option value="">Categoría</option>
              {parentCats.map((c) => (
                <option key={c.id} value={c.id}>{c.name}</option>
              ))}
            </select>
            {subcats.length > 0 && (
              <select
                value={filterSubcatId}
                onChange={(e) => { sessionStorage.setItem('products_subcat', e.target.value); setFilterSubcatId(e.target.value === '' ? '' : Number(e.target.value)); }}
                className="select-field w-44 py-2 text-xs"
              >
                <option value="">Todas las subcategorías</option>
                {subcats.map((c) => (
                  <option key={c.id} value={c.id}>{c.name}</option>
                ))}
              </select>
            )}
          </>
        }
      />
    </div>
  );
}
