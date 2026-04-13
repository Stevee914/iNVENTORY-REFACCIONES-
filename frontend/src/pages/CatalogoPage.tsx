import { useEffect, useState, useRef, useCallback } from 'react';
import { useSearchParams, useNavigate } from 'react-router-dom';

const SCROLL_KEY = 'catalogo_scroll_y';
import { ChevronRight, Search, X, Package, AlertTriangle } from 'lucide-react';
import { categoriaService } from '@/services/categorias';
import { productService, type CatalogProduct } from '@/services/products';
import { cn } from '@/lib/utils';
import type { Categoria } from '@/types';

// ─── Tree helpers ──────────────────────────────────────────────────────────────

/** Flatten a nested category tree into a Map<id, Categoria> for O(1) lookups. */
function buildFlatMap(cats: Categoria[]): Map<number, Categoria> {
  const map = new Map<number, Categoria>();
  function walk(list: Categoria[]) {
    for (const c of list) {
      map.set(c.id, c);
      if (c.subcategorias?.length) walk(c.subcategorias);
    }
  }
  walk(cats);
  return map;
}

/** Walk parent_id links up to build the breadcrumb path for a given category. */
function buildPath(id: number, flatMap: Map<number, Categoria>): Categoria[] {
  const path: Categoria[] = [];
  let cur = flatMap.get(id);
  while (cur) {
    path.unshift(cur);
    cur = cur.parent_id != null ? flatMap.get(cur.parent_id) : undefined;
  }
  return path;
}

// ─── Misc helpers ──────────────────────────────────────────────────────────────

function fmt(v: number | null | undefined) {
  if (v == null || v <= 0) return '—';
  return `$${v.toLocaleString('es-MX', { minimumFractionDigits: 2 })}`;
}

// ─── Breadcrumb ────────────────────────────────────────────────────────────────

interface Crumb { label: string; onClick?: () => void }

function Breadcrumb({ items }: { items: Crumb[] }) {
  return (
    <nav className="flex items-center gap-1 text-[12px] text-brand-400 mb-5 flex-wrap">
      {items.map((item, i) => (
        <span key={i} className="flex items-center gap-1">
          {i > 0 && <ChevronRight className="w-3 h-3 flex-shrink-0" />}
          {item.onClick ? (
            <button
              onClick={item.onClick}
              className="hover:text-brand-700 transition-colors font-medium"
            >
              {item.label}
            </button>
          ) : (
            <span className="text-brand-700 font-semibold">{item.label}</span>
          )}
        </span>
      ))}
    </nav>
  );
}

// ─── Category Card ─────────────────────────────────────────────────────────────

function CategoryCard({ cat, onClick }: { cat: Categoria; onClick: () => void }) {
  const hasChildren = (cat.subcategorias?.length ?? 0) > 0;
  return (
    <button
      onClick={onClick}
      className={cn(
        'w-full text-left p-5 rounded-xl border border-surface-200 bg-white',
        'hover:border-brand-300 hover:shadow-sm transition-all duration-150',
        'flex flex-col gap-2 group'
      )}
    >
      <p className="text-[13px] font-semibold text-brand-800 group-hover:text-brand-900 leading-tight">
        {cat.name}
      </p>
      {cat.description && (
        <p className="text-[11px] text-brand-400 leading-snug">{cat.description}</p>
      )}
      <div className="flex items-center gap-2 mt-auto pt-1">
        {hasChildren && (
          <span className="badge bg-surface-100 text-brand-400 text-[10px]">
            {cat.subcategorias!.length} subcategorías
          </span>
        )}
        <span className={cn(
          'badge text-[10px]',
          (cat.total_productos ?? 0) > 0 ? 'bg-brand-50 text-brand-600' : 'bg-surface-100 text-brand-400'
        )}>
          {cat.total_productos ?? 0} productos
        </span>
      </div>
    </button>
  );
}

// ─── Product Table ─────────────────────────────────────────────────────────────

const PAGE_SIZE_OPTIONS = [25, 50, 100];

interface ProductTableProps {
  items: CatalogProduct[];
  total: number;
  page: number;
  pageSize: number;
  q: string;
  marca: string;
  sort: string;
  marcas: string[];
  loading: boolean;
  onQ: (v: string) => void;
  onMarca: (v: string) => void;
  onSort: (v: string) => void;
  onPage: (v: number) => void;
  onPageSize: (v: number) => void;
}

function ProductTable({
  items, total, page, pageSize,
  q, marca, sort, marcas, loading,
  onQ, onMarca, onSort, onPage, onPageSize,
}: ProductTableProps) {
  const navigate = useNavigate();

  function openProduct(sku: string) {
    sessionStorage.setItem(SCROLL_KEY, String(window.scrollY));
    navigate(`/productos/${sku}`);
  }
  const totalPages = Math.max(1, Math.ceil(total / pageSize));
  const from = total === 0 ? 0 : (page - 1) * pageSize + 1;
  const to = Math.min(page * pageSize, total);

  return (
    <div>
      {/* Filters bar */}
      <div className="flex flex-wrap items-center gap-2 mb-4">
        <div className="relative flex-1 min-w-[200px] max-w-sm">
          <Search className="absolute left-2.5 top-1/2 -translate-y-1/2 w-3.5 h-3.5 text-brand-400" />
          <input
            value={q}
            onChange={(e) => onQ(e.target.value)}
            placeholder="SKU, nombre, marca..."
            className="input-field pl-8 py-2 text-xs"
          />
          {q && (
            <button
              onClick={() => onQ('')}
              className="absolute right-2 top-1/2 -translate-y-1/2 text-brand-400 hover:text-brand-600"
            >
              <X className="w-3 h-3" />
            </button>
          )}
        </div>

        {marcas.length > 0 && (
          <select
            value={marca}
            onChange={(e) => onMarca(e.target.value)}
            className="select-field py-2 text-xs w-44"
          >
            <option value="">Todas las marcas</option>
            {marcas.map((m) => (
              <option key={m} value={m}>{m}</option>
            ))}
          </select>
        )}

        <select
          value={sort}
          onChange={(e) => onSort(e.target.value)}
          className="select-field py-2 text-xs w-36"
        >
          <option value="">Ordenar por ID</option>
          <option value="nombre">Nombre A-Z</option>
          <option value="precio">Mayor precio</option>
          <option value="stock">Mayor stock</option>
        </select>

        <span className="text-xs text-brand-400 ml-auto">
          {loading ? 'Cargando...' : `${from}–${to} de ${total}`}
        </span>
      </div>

      {/* Table */}
      <div className="overflow-x-auto rounded-xl border border-surface-200">
        <table className="w-full text-left">
          <thead>
            <tr className="bg-surface-50 border-b border-surface-200">
              <th className="px-4 py-2.5 text-[11px] font-semibold text-brand-500 uppercase tracking-wide w-32">SKU</th>
              <th className="px-4 py-2.5 text-[11px] font-semibold text-brand-500 uppercase tracking-wide">Producto</th>
              <th className="px-4 py-2.5 text-[11px] font-semibold text-brand-500 uppercase tracking-wide hidden sm:table-cell w-32">Marca</th>
              <th className="px-4 py-2.5 text-[11px] font-semibold text-brand-500 uppercase tracking-wide text-right w-28">Precio</th>
              <th className="px-4 py-2.5 text-[11px] font-semibold text-brand-500 uppercase tracking-wide text-right w-24">Stock Fís.</th>
              <th className="px-4 py-2.5 text-[11px] font-semibold text-brand-500 uppercase tracking-wide text-right hidden sm:table-cell w-24">Stock POS</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-surface-100">
            {loading && items.length === 0 ? (
              <tr>
                <td colSpan={6} className="px-4 py-8 text-center">
                  <div className="w-5 h-5 border-2 border-surface-300 border-t-brand-500 rounded-full animate-spin mx-auto" />
                </td>
              </tr>
            ) : items.length === 0 ? (
              <tr>
                <td colSpan={6} className="px-4 py-8 text-center text-[13px] text-brand-400">
                  No se encontraron productos
                </td>
              </tr>
            ) : items.map((p) => {
              const precio = p.precio_publico ?? (p.costo_pos_con_iva ?? 0);
              const sfisico = Number(p.stock_fisico);
              const spos = Number(p.stock_pos);
              return (
                <tr key={p.sku} className="hover:bg-surface-50 transition-colors">
                  <td className="px-4 py-2.5">
                    <button
                      onClick={() => openProduct(p.sku)}
                      className="font-mono text-xs font-medium text-brand-600 hover:text-status-info transition-colors"
                    >
                      {p.sku}
                    </button>
                  </td>
                  <td className="px-4 py-2.5">
                    <button
                      onClick={() => openProduct(p.sku)}
                      className="text-[13px] text-brand-800 hover:text-status-info transition-colors text-left truncate max-w-xs"
                    >
                      {p.name}
                    </button>
                  </td>
                  <td className="px-4 py-2.5 hidden sm:table-cell">
                    <span className="text-xs text-brand-500">{p.marca || '—'}</span>
                  </td>
                  <td className="px-4 py-2.5 text-right">
                    <span className="tabular-nums text-xs font-semibold text-emerald-700">{fmt(precio)}</span>
                  </td>
                  <td className="px-4 py-2.5 text-right">
                    <span className={cn(
                      'tabular-nums text-xs font-medium',
                      sfisico <= 0 ? 'text-status-critical' : sfisico < (p.min_stock ?? 0) ? 'text-amber-600' : 'text-brand-700'
                    )}>
                      {sfisico}
                    </span>
                  </td>
                  <td className="px-4 py-2.5 text-right hidden sm:table-cell">
                    <span className={cn('tabular-nums text-xs', spos < 0 ? 'text-status-critical' : 'text-brand-500')}>
                      {spos}
                    </span>
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>

      {/* Pagination */}
      <div className="flex items-center justify-between mt-4">
        <div className="flex items-center gap-2">
          <span className="text-xs text-brand-400">Por página:</span>
          {PAGE_SIZE_OPTIONS.map((n) => (
            <button
              key={n}
              onClick={() => onPageSize(n)}
              className={cn(
                'px-2 py-1 rounded text-xs transition-colors',
                pageSize === n ? 'bg-brand-100 text-brand-700 font-semibold' : 'text-brand-400 hover:text-brand-600'
              )}
            >
              {n}
            </button>
          ))}
        </div>
        <div className="flex items-center gap-1">
          <button
            onClick={() => onPage(page - 1)}
            disabled={page <= 1}
            className="btn-ghost px-2 py-1 text-xs disabled:opacity-30"
          >
            ‹ Anterior
          </button>
          <span className="px-3 py-1 text-xs text-brand-500">{page} / {totalPages}</span>
          <button
            onClick={() => onPage(page + 1)}
            disabled={page >= totalPages}
            className="btn-ghost px-2 py-1 text-xs disabled:opacity-30"
          >
            Siguiente ›
          </button>
        </div>
      </div>
    </div>
  );
}

// ─── Main Page ─────────────────────────────────────────────────────────────────

export function CatalogoPage() {
  const [searchParams, setSearchParams] = useSearchParams();

  // ── URL params ─────────────────────────────────────────────────────────────
  // `cat`  — current category ID (any level: root, mid, or leaf)
  // `view` — 'all' forces product table even for non-leaf categories
  const catParam   = searchParams.get('cat');
  const viewParam  = searchParams.get('view');       // 'all' = show products for entire subtree
  const qParam     = searchParams.get('q') ?? '';
  const marcaParam = searchParams.get('marca') ?? '';
  const sortParam  = searchParams.get('sort') ?? '';
  const pageParam  = Math.max(1, parseInt(searchParams.get('page') ?? '1', 10));
  const psParam    = parseInt(searchParams.get('ps') ?? '50', 10);

  const catId   = catParam ? parseInt(catParam, 10) : null;
  const showAll = viewParam === 'all';

  // ── Category tree ──────────────────────────────────────────────────────────
  const [roots, setRoots] = useState<Categoria[]>([]);
  const [flatMap, setFlatMap] = useState<Map<number, Categoria>>(new Map());
  const [treeLoading, setTreeLoading] = useState(true);
  const [treeError, setTreeError] = useState('');

  // Take over scroll restoration so the browser doesn't fire it before content renders
  useEffect(() => {
    const prev = window.history.scrollRestoration;
    window.history.scrollRestoration = 'manual';
    return () => { window.history.scrollRestoration = prev; };
  }, []);

  useEffect(() => {
    categoriaService.getTree()
      .then((tree) => {
        setRoots(tree);
        setFlatMap(buildFlatMap(tree));
      })
      .catch((e) => setTreeError(e.message))
      .finally(() => setTreeLoading(false));
  }, []);

  // ── Product data (only when showing product table) ─────────────────────────
  const [products, setProducts] = useState<CatalogProduct[]>([]);
  const [prodTotal, setProdTotal] = useState(0);
  const [prodLoading, setProdLoading] = useState(false);
  const [marcas, setMarcas] = useState<string[]>([]);

  // Determine if we should show the product table:
  // - cat is null → root grid, no products
  // - cat is a leaf (no subcategorias) → product table
  // - cat has children AND view=all → product table (entire subtree)
  const selectedCat = catId != null ? (flatMap.get(catId) ?? null) : null;
  const hasChildren = (selectedCat?.subcategorias?.length ?? 0) > 0;
  const showProducts = catId !== null && (!hasChildren || showAll);

  // Debounce search
  const debounceRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const [localQ, setLocalQ] = useState(qParam);
  useEffect(() => { setLocalQ(qParam); }, [qParam]);

  // Restore scroll position after returning from a product detail page
  const didRestoreScroll = useRef(false);
  const restoreScroll = useCallback(() => {
    const saved = sessionStorage.getItem(SCROLL_KEY);
    if (!saved) return;
    sessionStorage.removeItem(SCROLL_KEY);
    didRestoreScroll.current = false;
    const target = parseInt(saved, 10);
    // rAF ensures the DOM has rendered before scrolling
    requestAnimationFrame(() => window.scrollTo({ top: target, behavior: 'instant' }));
  }, []);

  // Fetch products when in product-table mode
  useEffect(() => {
    if (!showProducts || treeLoading) return;

    // For leaf: filter by exact categoria_id.
    // For "view=all" on a non-leaf: use parent_categoria_id to get entire subtree.
    const catFilter = (!hasChildren)
      ? { categoria_id: catId! }
      : { parent_categoria_id: catId! };

    setProdLoading(true);
    productService.listCatalog({
      ...catFilter,
      q: qParam || undefined,
      marca: marcaParam || undefined,
      sort: sortParam || undefined,
      page: pageParam,
      page_size: psParam,
    }).then((res) => {
      setProducts(res.items);
      setProdTotal(res.total);
    }).then(restoreScroll).finally(() => setProdLoading(false));
  }, [showProducts, treeLoading, catId, hasChildren, qParam, marcaParam, sortParam, pageParam, psParam]);

  // Fetch brand list when entering product-table mode (once per category)
  useEffect(() => {
    if (!showProducts || treeLoading) return;
    const catFilter = !hasChildren
      ? { categoria_id: catId! }
      : { parent_categoria_id: catId! };
    productService.getMarcasByCat(catFilter).then(setMarcas).catch(() => {});
  }, [showProducts, treeLoading, catId, hasChildren]);

  // ── Navigation helpers ─────────────────────────────────────────────────────

  function goCat(id: number) {
    // Navigate into a category. Product filters reset when changing category.
    setSearchParams({ cat: String(id) }, { replace: false });
  }

  function goRoot() {
    setSearchParams({}, { replace: false });
  }

  function goViewAll(id: number) {
    setSearchParams({ cat: String(id), view: 'all' }, { replace: false });
  }

  // ── Filter handlers ────────────────────────────────────────────────────────

  function handleQ(v: string) {
    setLocalQ(v);
    if (debounceRef.current) clearTimeout(debounceRef.current);
    debounceRef.current = setTimeout(() => {
      setSearchParams((prev) => {
        const next = new URLSearchParams(prev);
        if (v) { next.set('q', v); } else { next.delete('q'); }
        next.delete('page');
        return next;
      }, { replace: true });
    }, 300);
  }

  function handleMarca(v: string) {
    setSearchParams((prev) => {
      const next = new URLSearchParams(prev);
      if (v) { next.set('marca', v); } else { next.delete('marca'); }
      next.delete('page');
      return next;
    }, { replace: true });
  }

  function handleSort(v: string) {
    setSearchParams((prev) => {
      const next = new URLSearchParams(prev);
      if (v) { next.set('sort', v); } else { next.delete('sort'); }
      next.delete('page');
      return next;
    }, { replace: true });
  }

  function handlePage(v: number) {
    setSearchParams((prev) => {
      const next = new URLSearchParams(prev);
      next.set('page', String(v));
      return next;
    }, { replace: true });
  }

  function handlePageSize(v: number) {
    setSearchParams((prev) => {
      const next = new URLSearchParams(prev);
      next.set('ps', String(v));
      next.delete('page');
      return next;
    }, { replace: true });
  }

  // ── Breadcrumb path ────────────────────────────────────────────────────────

  function buildCrumbs(): Crumb[] {
    const crumbs: Crumb[] = [{ label: 'Catálogo', onClick: goRoot }];
    if (catId === null) {
      // Replace last item with non-clickable current
      return [{ label: 'Catálogo' }];
    }
    const path = buildPath(catId, flatMap);
    path.forEach((c, i) => {
      const isLast = i === path.length - 1;
      if (isLast && !showAll) {
        crumbs.push({ label: c.name });
      } else {
        crumbs.push({ label: c.name, onClick: () => goCat(c.id) });
      }
    });
    if (showAll) {
      crumbs.push({ label: 'Todos los productos' });
    }
    return crumbs;
  }

  // ── Loading / error states ─────────────────────────────────────────────────

  if (treeLoading) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="w-6 h-6 border-2 border-surface-300 border-t-brand-500 rounded-full animate-spin" />
      </div>
    );
  }

  if (treeError) {
    return (
      <div className="card p-8 text-center">
        <AlertTriangle className="w-10 h-10 mx-auto text-status-critical mb-3" />
        <p className="text-[13px] text-brand-500">{treeError}</p>
      </div>
    );
  }

  // ── RENDER: root category grid ─────────────────────────────────────────────

  if (catId === null) {
    return (
      <div>
        <div className="mb-6">
          <h1 className="text-[18px] font-semibold text-brand-900">Catálogo</h1>
          <p className="text-[13px] text-brand-400 mt-0.5">{roots.length} categorías principales</p>
        </div>
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-3">
          {roots.map((cat) => (
            <CategoryCard key={cat.id} cat={cat} onClick={() => goCat(cat.id)} />
          ))}
        </div>
      </div>
    );
  }

  // ── RENDER: subcategory card grid (non-leaf, not view=all) ─────────────────

  if (hasChildren && !showAll) {
    const children = selectedCat!.subcategorias!;
    return (
      <div>
        <Breadcrumb items={buildCrumbs()} />
        <div className="flex items-center justify-between mb-5">
          <div>
            <h1 className="text-[18px] font-semibold text-brand-900">{selectedCat!.name}</h1>
            <p className="text-[13px] text-brand-400 mt-0.5">
              {selectedCat!.total_productos ?? 0} productos totales
            </p>
          </div>
          <button
            onClick={() => goViewAll(catId)}
            className="btn-secondary text-xs"
          >
            <Package className="w-3.5 h-3.5" />
            Ver todos los productos
          </button>
        </div>
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-3">
          {children.map((child) => (
            <CategoryCard key={child.id} cat={child} onClick={() => goCat(child.id)} />
          ))}
        </div>
      </div>
    );
  }

  // ── RENDER: product table (leaf or view=all) ───────────────────────────────

  const tableTitle = showAll
    ? `${selectedCat?.name ?? ''} — Todos los productos`
    : (selectedCat?.name ?? '');

  return (
    <div>
      <Breadcrumb items={buildCrumbs()} />
      <div className="mb-5">
        <h1 className="text-[18px] font-semibold text-brand-900">{tableTitle}</h1>
        <p className="text-[13px] text-brand-400 mt-0.5">
          {prodLoading ? 'Cargando...' : `${prodTotal} productos`}
        </p>
      </div>
      <ProductTable
        items={products}
        total={prodTotal}
        page={pageParam}
        pageSize={psParam}
        q={localQ}
        marca={marcaParam}
        sort={sortParam}
        marcas={marcas}
        loading={prodLoading}
        onQ={handleQ}
        onMarca={handleMarca}
        onSort={handleSort}
        onPage={handlePage}
        onPageSize={handlePageSize}
      />
    </div>
  );
}
