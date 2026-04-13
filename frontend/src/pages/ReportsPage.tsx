import { useEffect, useRef, useState } from 'react';
import { Link } from 'react-router-dom';
import {
  Search, Download, Package, Warehouse, AlertTriangle,
  ShoppingCart, Clock, ChevronLeft, ChevronRight,
  ChevronsLeft, ChevronsRight,
} from 'lucide-react';
import { PageHeader, KpiCard } from '@/components/shared';
import { reportesService, type InventarioItem, type InventarioKpis } from '@/services/reportesService';
import { useFilterOptions } from '@/hooks/useFilterOptions';
import { cn } from '@/lib/utils';

const PAGE_SIZES = [25, 50, 100];

function fmtDate(iso: string | null): string {
  if (!iso) return '—';
  return new Date(iso).toLocaleDateString('es-MX', {
    day: '2-digit', month: 'short', year: '2-digit',
  });
}

function StockCell({ value, minStock }: { value: number; minStock: number }) {
  const cls =
    value < 0 ? 'text-red-700 font-semibold' :
    value === 0 ? 'text-red-600 font-semibold' :
    value < minStock ? 'text-amber-600 font-semibold' :
    'text-brand-800';
  return <span className={cn('tabular-nums text-[13px]', cls)}>{value}</span>;
}

export function ReportsPage() {
  const opts = useFilterOptions();

  // Filters
  const [searchInput, setSearchInput] = useState('');
  const [searchQ,     setSearchQ    ] = useState('');
  const [catId,       setCatId      ] = useState<number | ''>('');
  const [marcaF,      setMarcaF     ] = useState('');
  const [provId,      setProvId     ] = useState<number | ''>('');
  const [bajoMinimo,      setBajoMinimo     ] = useState(false);
  const [stockCero,       setStockCero      ] = useState(false);
  const [stockNegativo,   setStockNegativo  ] = useState(false);
  const [sinMovimiento30d, setSinMovimiento30d] = useState(false);

  // Data
  const [items,   setItems  ] = useState<InventarioItem[]>([]);
  const [total,   setTotal  ] = useState(0);
  const [kpis,    setKpis   ] = useState<InventarioKpis | null>(null);
  const [loading, setLoading] = useState(true);
  const [error,   setError  ] = useState<string | null>(null);

  // Pagination
  const [page,     setPage    ] = useState(1);
  const [pageSize, setPageSize] = useState(50);

  const debounceRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  function handleSearch(v: string) {
    setSearchInput(v);
    if (debounceRef.current) clearTimeout(debounceRef.current);
    debounceRef.current = setTimeout(() => { setSearchQ(v); setPage(1); }, 300);
  }

  useEffect(() => { load(); }, [searchQ, catId, marcaF, provId, bajoMinimo, stockCero, stockNegativo, sinMovimiento30d, page, pageSize]);

  async function load() {
    setLoading(true);
    setError(null);
    try {
      const res = await reportesService.getInventario({
        q:              searchQ || undefined,
        categoriaId:    catId    !== '' ? Number(catId)  : undefined,
        marca:          marcaF   || undefined,
        proveedorId:    provId   !== '' ? Number(provId) : undefined,
        bajoMinimo:     bajoMinimo     || undefined,
        stockCero:      stockCero      || undefined,
        stockNegativo:  stockNegativo  || undefined,
        sinMovimiento30d: sinMovimiento30d || undefined,
        page,
        pageSize,
      });
      setItems(res.items);
      setTotal(res.total);
      setKpis(res.kpis);
    } catch (e: any) {
      setError(e.message || 'Error cargando datos');
    } finally {
      setLoading(false);
    }
  }

  function resetFilters() {
    setSearchInput(''); setSearchQ(''); setCatId(''); setMarcaF('');
    setProvId(''); setBajoMinimo(false); setStockCero(false);
    setStockNegativo(false); setSinMovimiento30d(false); setPage(1);
  }

  async function exportCSV() {
    try {
      const res = await reportesService.getInventario({
        q: searchQ || undefined,
        categoriaId: catId !== '' ? Number(catId) : undefined,
        marca: marcaF || undefined,
        proveedorId: provId !== '' ? Number(provId) : undefined,
        bajoMinimo: bajoMinimo || undefined,
        stockCero: stockCero || undefined,
        stockNegativo: stockNegativo || undefined,
        sinMovimiento30d: sinMovimiento30d || undefined,
        page: 1,
        pageSize: 10000,
      });
      const header = ['SKU','Producto','Marca','Categoría','Stock Físico','Stock POS','Mínimo','Déficit','Último Mov.','Proveedor'];
      const escape = (v: string | number | null) => {
        const s = String(v ?? '');
        return s.includes(',') || s.includes('"') ? `"${s.replace(/"/g,'""')}"` : s;
      };
      const rows = res.items.map(r => [
        r.sku, r.name, r.marca??'', r.categoria??'',
        r.stock_fisico, r.stock_pos, r.min_stock, r.deficit,
        fmtDate(r.ultimo_mov), r.proveedor??'',
      ].map(escape).join(','));
      const csv = [header.join(','), ...rows].join('\r\n');
      const blob = new Blob(['\uFEFF' + csv], { type: 'text/csv;charset=utf-8;' });
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a'); a.href = url;
      a.download = `inventario_alertas_${new Date().toISOString().slice(0,10)}.csv`;
      a.click(); URL.revokeObjectURL(url);
    } catch {}
  }

  const totalPages = Math.ceil(total / pageSize);

  return (
    <div>
      <PageHeader
        title="Alertas de Inventario"
        description="Productos activos ordenados por déficit — stock bajo mínimo primero"
        actions={
          <button className="btn-secondary" onClick={exportCSV}>
            <Download className="w-4 h-4" /> Exportar CSV
          </button>
        }
      />

      {/* KPI Cards */}
      <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-6 gap-3 mb-4">
        <KpiCard title="Activos"           value={kpis?.total_activos ?? '—'}       icon={Package}       subtitle="productos activos" />
        <KpiCard title="Stock Físico"      value={kpis ? Math.round(kpis.stock_fisico_total).toLocaleString('es-MX') : '—'} icon={Warehouse} subtitle="unidades totales" />
        <KpiCard title="Stock POS"         value={kpis ? Math.round(kpis.stock_pos_total).toLocaleString('es-MX') : '—'}   icon={Warehouse} subtitle="unidades POS" />
        <KpiCard title="Bajo Mínimo"       value={kpis?.bajo_minimo ?? '—'}         icon={AlertTriangle} subtitle="necesitan reorden"   variant={kpis && kpis.bajo_minimo > 0 ? 'warning' : 'default'} />
        <KpiCard title="Stock Cero"        value={kpis?.stock_cero  ?? '—'}         icon={ShoppingCart}  subtitle="sin unidades"        variant={kpis && kpis.stock_cero  > 0 ? 'critical' : 'default'} />
        <KpiCard title="Sin Movimiento 30d" value={kpis?.sin_movimiento_30d ?? '—'} icon={Clock}         subtitle="últimos 30 días"     variant={kpis && kpis.sin_movimiento_30d > 0 ? 'warning' : 'default'} />
      </div>

      {/* Filter Bar */}
      <div className="card px-4 py-3 mb-4">
        <div className="flex flex-wrap gap-2 items-center">
          {/* Search */}
          <div className="relative min-w-[180px] flex-1 max-w-xs">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-brand-300 pointer-events-none" />
            <input
              type="text" value={searchInput} onChange={e => handleSearch(e.target.value)}
              placeholder="SKU, nombre, marca…"
              className="input-field pl-9 py-1.5 w-full text-[13px]"
            />
            {searchInput && (
              <button onClick={() => handleSearch('')} className="absolute right-2 top-1/2 -translate-y-1/2 text-brand-300 hover:text-brand-500 text-xs">✕</button>
            )}
          </div>

          {/* Category */}
          <select value={catId} onChange={e => { setCatId(e.target.value === '' ? '' : Number(e.target.value)); setPage(1); }}
            className="select-field py-1.5 text-[13px] max-w-[180px]">
            <option value="">— Categoría —</option>
            {opts.categorias.map(c => (
              <option key={c.id} value={c.id}>
                {c.parent_name ? `${c.parent_name} › ${c.name}` : c.name}
              </option>
            ))}
          </select>

          {/* Brand */}
          <select value={marcaF} onChange={e => { setMarcaF(e.target.value); setPage(1); }}
            className="select-field py-1.5 text-[13px] max-w-[160px]">
            <option value="">— Marca —</option>
            {opts.marcas.map(m => <option key={m} value={m}>{m}</option>)}
          </select>

          {/* Supplier */}
          <select value={provId} onChange={e => { setProvId(e.target.value === '' ? '' : Number(e.target.value)); setPage(1); }}
            className="select-field py-1.5 text-[13px] max-w-[180px]">
            <option value="">— Proveedor —</option>
            {opts.proveedores.map(p => <option key={p.id} value={p.id}>{p.nombre}</option>)}
          </select>

          {/* Quick filter toggles */}
          <div className="flex flex-wrap gap-2 items-center ml-1">
            {([
              ['Bajo mínimo',    bajoMinimo,       setBajoMinimo,       'text-amber-700 bg-amber-50 border-amber-300'],
              ['Stock cero',     stockCero,         setStockCero,         'text-red-700 bg-red-50 border-red-300'],
              ['Stock negativo', stockNegativo,     setStockNegativo,     'text-red-700 bg-red-50 border-red-300'],
              ['Sin mov. 30d',   sinMovimiento30d,  setSinMovimiento30d,  'text-blue-700 bg-blue-50 border-blue-300'],
            ] as const).map(([label, val, setter, activeClass]) => (
              <button
                key={label}
                onClick={() => { (setter as any)(!val); setPage(1); }}
                className={cn(
                  'px-2.5 py-1 rounded-full text-[11px] font-medium border transition-colors',
                  val ? activeClass : 'text-brand-400 bg-surface-50 border-surface-200 hover:border-surface-300'
                )}
              >
                {label}
              </button>
            ))}
          </div>

          <div className="ml-auto flex items-center gap-3">
            {(searchQ || catId !== '' || marcaF || provId !== '' || bajoMinimo || stockCero || stockNegativo || sinMovimiento30d) && (
              <button onClick={resetFilters} className="text-[12px] text-brand-400 hover:text-brand-600">Limpiar</button>
            )}
            <span className="text-xs text-brand-400">{total.toLocaleString('es-MX')} resultado{total !== 1 ? 's' : ''}</span>
          </div>
        </div>
      </div>

      {/* Table */}
      <div className="card overflow-hidden">
        <div className="overflow-x-auto">
          <table className="w-full">
            <thead>
              <tr className="bg-surface-50 border-b border-surface-200">
                <th className="table-header">SKU</th>
                <th className="table-header">Producto</th>
                <th className="table-header">Marca</th>
                <th className="table-header">Categoría</th>
                <th className="table-header text-right">Stock Fís.</th>
                <th className="table-header text-right">Stock POS</th>
                <th className="table-header text-right">Mínimo</th>
                <th className="table-header text-right">Déficit</th>
                <th className="table-header">Último Mov.</th>
                <th className="table-header">Proveedor</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-surface-100">
              {loading && items.length === 0 ? (
                <tr><td colSpan={10} className="px-4 py-12 text-center">
                  <div className="w-6 h-6 border-2 border-surface-300 border-t-sap-blue rounded-full animate-spin mx-auto" />
                </td></tr>
              ) : error ? (
                <tr><td colSpan={10} className="px-4 py-10 text-center text-status-critical text-[13px]">{error}</td></tr>
              ) : items.length === 0 ? (
                <tr><td colSpan={10} className="px-4 py-12 text-center text-[13px] text-brand-400">
                  No hay productos con los filtros aplicados.
                </td></tr>
              ) : items.map(row => {
                const isZero    = row.stock_fisico === 0;
                const isBelowMin = !isZero && row.min_stock > 0 && row.stock_fisico < row.min_stock;
                return (
                  <tr key={row.producto_id} className={cn(
                    'transition-colors',
                    isZero     ? 'bg-red-50/60 hover:bg-red-50'
                    : isBelowMin ? 'bg-amber-50/60 hover:bg-amber-50'
                    : 'hover:bg-surface-50',
                    loading && 'opacity-50',
                  )}>
                    <td className="table-cell">
                      <Link to={`/productos/${row.sku}`} className="font-mono text-xs font-medium text-brand-600 hover:text-sap-blue hover:underline">{row.sku}</Link>
                    </td>
                    <td className="table-cell max-w-[200px]"><span className="text-[13px] truncate block" title={row.name}>{row.name}</span></td>
                    <td className="table-cell text-[12px] text-brand-500 whitespace-nowrap">{row.marca ?? '—'}</td>
                    <td className="table-cell text-[12px] text-brand-500 max-w-[140px]"><span className="truncate block" title={row.categoria ?? ''}>{row.categoria ?? '—'}</span></td>
                    <td className="table-cell text-right"><StockCell value={row.stock_fisico} minStock={row.min_stock} /></td>
                    <td className="table-cell text-right tabular-nums text-[13px] text-brand-500">{row.stock_pos}</td>
                    <td className="table-cell text-right tabular-nums text-[13px] text-brand-400">{row.min_stock}</td>
                    <td className="table-cell text-right">
                      {row.deficit > 0
                        ? <span className="tabular-nums text-[13px] font-semibold text-red-600">{row.deficit}</span>
                        : <span className="text-brand-300">—</span>}
                    </td>
                    <td className="table-cell text-[12px] text-brand-500 whitespace-nowrap">{fmtDate(row.ultimo_mov)}</td>
                    <td className="table-cell text-[12px] text-brand-500 max-w-[120px]"><span className="truncate block">{row.proveedor ?? '—'}</span></td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>

        {/* Pagination */}
        <div className="px-4 py-3 border-t border-surface-200 flex items-center justify-between gap-3 flex-wrap">
          <div className="flex items-center gap-3">
            <p className="text-xs text-brand-400">Página {page} de {Math.max(1, totalPages)} — {total.toLocaleString('es-MX')} productos</p>
            <select value={pageSize} onChange={e => { setPageSize(Number(e.target.value)); setPage(1); }} className="select-field py-1 text-xs w-24">
              {PAGE_SIZES.map(s => <option key={s} value={s}>{s} / pág.</option>)}
            </select>
          </div>
          <div className="flex items-center gap-0.5">
            <button onClick={() => setPage(1)}                                  disabled={page <= 1}          className="btn-ghost p-1.5 disabled:opacity-30"><ChevronsLeft  className="w-4 h-4" /></button>
            <button onClick={() => setPage(p => Math.max(1, p - 1))}           disabled={page <= 1}          className="btn-ghost p-1.5 disabled:opacity-30"><ChevronLeft   className="w-4 h-4" /></button>
            <button onClick={() => setPage(p => Math.min(totalPages, p + 1))}  disabled={page >= totalPages} className="btn-ghost p-1.5 disabled:opacity-30"><ChevronRight  className="w-4 h-4" /></button>
            <button onClick={() => setPage(totalPages)}                         disabled={page >= totalPages} className="btn-ghost p-1.5 disabled:opacity-30"><ChevronsRight className="w-4 h-4" /></button>
          </div>
        </div>
      </div>
    </div>
  );
}
