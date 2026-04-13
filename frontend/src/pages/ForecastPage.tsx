import { useEffect, useRef, useState } from 'react';
import { Link } from 'react-router-dom';
import {
  Search, AlertCircle, Download, TrendingUp, Activity,
  ShoppingCart, Archive, ChevronLeft, ChevronRight,
  ChevronsLeft, ChevronsRight,
} from 'lucide-react';
import { PageHeader, KpiCard } from '@/components/shared';
import { reportesService, type ForecastItemReal, type ForecastKpis } from '@/services/reportesService';
import { useFilterOptions } from '@/hooks/useFilterOptions';
import { cn } from '@/lib/utils';

const PAGE_SIZES = [25, 50, 100];
const HORIZONS = [7, 15, 30, 60] as const;

function fmtDate(iso: string | null): string {
  if (!iso) return '—';
  return new Date(iso).toLocaleDateString('es-MX', { day: '2-digit', month: 'short', year: '2-digit' });
}

function CoberturaCell({ dias, stock }: { dias: number | null; stock: number }) {
  if (stock === 0) return (
    <span className="inline-flex items-center gap-1 text-[11px] font-medium text-red-600">
      ⚠ SIN STOCK
    </span>
  );
  if (dias === null) return <span className="text-brand-400 text-[13px]">∞</span>;
  const cls =
    dias < 7  ? 'text-red-600 font-semibold' :
    dias < 15 ? 'text-amber-600 font-semibold' :
    'text-emerald-600';
  return <span className={cn('tabular-nums text-[13px]', cls)}>{dias.toFixed(0)}d</span>;
}

export function ForecastPage() {
  const opts = useFilterOptions();

  // Filters
  const [searchInput, setSearchInput] = useState('');
  const [searchQ,     setSearchQ    ] = useState('');
  const [catId,       setCatId      ] = useState<number | ''>('');
  const [marcaF,      setMarcaF     ] = useState('');
  const [provId,      setProvId     ] = useState<number | ''>('');
  const [horizon,     setHorizon    ] = useState<number>(30);
  const [status,      setStatus     ] = useState('');

  // Data
  const [items,   setItems  ] = useState<ForecastItemReal[]>([]);
  const [total,   setTotal  ] = useState(0);
  const [kpis,    setKpis   ] = useState<ForecastKpis | null>(null);
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

  useEffect(() => { load(); }, [searchQ, catId, marcaF, provId, horizon, status, page, pageSize]);

  async function load() {
    setLoading(true); setError(null);
    try {
      const res = await reportesService.getForecast({
        q:           searchQ || undefined,
        categoriaId: catId !== '' ? Number(catId) : undefined,
        marca:       marcaF || undefined,
        proveedorId: provId !== '' ? Number(provId) : undefined,
        horizon,
        status:      status || undefined,
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
    setProvId(''); setStatus(''); setPage(1);
  }

  async function exportCSV() {
    try {
      const res = await reportesService.getForecast({
        q: searchQ || undefined, categoriaId: catId !== '' ? Number(catId) : undefined,
        marca: marcaF || undefined, proveedorId: provId !== '' ? Number(provId) : undefined,
        horizon, status: status || undefined, page: 1, pageSize: 10000,
      });
      const header = ['SKU','Producto','Marca','Stock Actual','Consumo Diario','Cobertura (días)','Demanda Proyectada','Sugerido Comprar','Último Mov. OUT','Proveedor'];
      const escape = (v: string | number | null) => {
        const s = String(v ?? '');
        return s.includes(',') || s.includes('"') ? `"${s.replace(/"/g,'""')}"` : s;
      };
      const rows = res.items.map(r => [
        r.sku, r.name, r.marca??'', r.stock_fisico,
        r.consumo_promedio_diario, r.cobertura_dias??'∞',
        r.demanda_proyectada, r.sugerido_comprar,
        fmtDate(r.ultimo_mov_out), r.proveedor??'',
      ].map(escape).join(','));
      const csv = [header.join(','), ...rows].join('\r\n');
      const blob = new Blob(['\uFEFF' + csv], { type: 'text/csv;charset=utf-8;' });
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a'); a.href = url;
      a.download = `sugerido_compra_${horizon}d_${new Date().toISOString().slice(0,10)}.csv`;
      a.click(); URL.revokeObjectURL(url);
    } catch {}
  }

  const totalPages = Math.ceil(total / pageSize);

  return (
    <div>
      <PageHeader
        title="Planeación y Rotación"
        description={`Análisis de consumo y cobertura — horizonte ${horizon} días`}
        actions={
          <button className="btn-secondary" onClick={exportCSV}>
            <Download className="w-4 h-4" /> Exportar Sugerido de Compra
          </button>
        }
      />

      {/* Notice */}
      <div className="flex items-start gap-3 p-3 mb-4 rounded-xl bg-blue-50 border border-blue-200">
        <AlertCircle className="w-4 h-4 text-blue-500 flex-shrink-0 mt-0.5" />
        <p className="text-[12px] text-blue-700">
          Estimaciones basadas en historial de movimientos. La precisión mejora conforme se registren más datos en el sistema.
        </p>
      </div>

      {/* KPI Cards */}
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 mb-4">
        <KpiCard title="Productos Analizados" value={kpis?.productos_analizados ?? '—'} icon={Activity}      subtitle="con ≥ 3 salidas en 90d" />
        <KpiCard title="Rotación Promedio"    value={kpis ? `${kpis.rotacion_promedio.toFixed(2)}/d` : '—'} icon={TrendingUp}   subtitle="unidades diarias promedio" />
        <KpiCard title="Alta Rotación"        value={kpis?.alta_rotacion ?? '—'}         icon={ShoppingCart}  subtitle="> 1 unidad/día"     variant={kpis && kpis.alta_rotacion > 0 ? 'default' : 'default'} />
        <KpiCard title="Sin Rotación 60d"     value={kpis?.sin_rotacion_60d ?? '—'}      icon={Archive}       subtitle="inventario detenido"  variant={kpis && kpis.sin_rotacion_60d > 0 ? 'warning' : 'default'} />
      </div>

      {/* Filter Bar */}
      <div className="card px-4 py-3 mb-4">
        <div className="flex flex-wrap gap-2 items-center">
          {/* Search */}
          <div className="relative min-w-[160px] flex-1 max-w-xs">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-brand-300 pointer-events-none" />
            <input type="text" value={searchInput} onChange={e => handleSearch(e.target.value)}
              placeholder="SKU o nombre…" className="input-field pl-9 py-1.5 w-full text-[13px]" />
            {searchInput && <button onClick={() => handleSearch('')} className="absolute right-2 top-1/2 -translate-y-1/2 text-brand-300 hover:text-brand-500 text-xs">✕</button>}
          </div>

          {/* Category */}
          <select value={catId} onChange={e => { setCatId(e.target.value === '' ? '' : Number(e.target.value)); setPage(1); }}
            className="select-field py-1.5 text-[13px] max-w-[180px]">
            <option value="">— Categoría —</option>
            {opts.categorias.map(c => (
              <option key={c.id} value={c.id}>{c.parent_name ? `${c.parent_name} › ${c.name}` : c.name}</option>
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

          {/* Horizon */}
          <div className="flex items-center gap-1">
            <span className="text-[11px] text-brand-400 whitespace-nowrap">Horizonte</span>
            <div className="flex rounded-lg border border-surface-200 overflow-hidden">
              {HORIZONS.map(h => (
                <button key={h} onClick={() => { setHorizon(h); setPage(1); }}
                  className={cn('px-2.5 py-1 text-[11px] font-medium transition-colors',
                    horizon === h ? 'bg-sap-blue text-white' : 'text-brand-500 hover:bg-surface-100'
                  )}>
                  {h}d
                </button>
              ))}
            </div>
          </div>

          {/* Status filter */}
          <select value={status} onChange={e => { setStatus(e.target.value); setPage(1); }}
            className="select-field py-1.5 text-[13px] max-w-[180px]">
            <option value="">Todos</option>
            <option value="reorden">Necesita reorden</option>
            <option value="cobertura_baja">Cobertura &lt; 15 días</option>
            <option value="sin_rotacion">Sin rotación</option>
          </select>

          <div className="ml-auto flex items-center gap-3">
            {(searchQ || catId !== '' || marcaF || provId !== '' || status) && (
              <button onClick={resetFilters} className="text-[12px] text-brand-400 hover:text-brand-600">Limpiar</button>
            )}
            <span className="text-xs text-brand-400">{total.toLocaleString('es-MX')} productos</span>
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
                <th className="table-header text-right">Stock</th>
                <th className="table-header text-right">Consumo/día</th>
                <th className="table-header text-right">Cobertura</th>
                <th className="table-header text-right">Dem. {horizon}d</th>
                <th className="table-header text-right">Sug. Comprar</th>
                <th className="table-header">Último OUT</th>
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
                const sinRotacion = row.consumo_promedio_diario === 0 && row.stock_fisico > 0;
                const coberturaBaja = row.cobertura_dias !== null && row.cobertura_dias < 7;
                const coberturaMedia = row.cobertura_dias !== null && row.cobertura_dias >= 7 && row.cobertura_dias < 15;
                return (
                  <tr key={row.producto_id} className={cn(
                    'transition-colors',
                    coberturaBaja  ? 'bg-red-50/50 hover:bg-red-50'
                    : coberturaMedia ? 'bg-amber-50/40 hover:bg-amber-50'
                    : sinRotacion   ? 'bg-surface-100/60 hover:bg-surface-100'
                    : 'hover:bg-surface-50',
                    loading && 'opacity-50',
                  )}>
                    <td className="table-cell">
                      <Link to={`/productos/${row.sku}`} className="font-mono text-xs font-medium text-brand-600 hover:text-sap-blue hover:underline">{row.sku}</Link>
                    </td>
                    <td className="table-cell max-w-[180px]">
                      <div className="flex items-center gap-1.5">
                        <span className="text-[13px] truncate block" title={row.name}>{row.name}</span>
                        {sinRotacion && <span className="flex-shrink-0 text-[10px] px-1.5 py-0.5 rounded bg-surface-200 text-brand-400 font-medium">Sin rotación</span>}
                      </div>
                    </td>
                    <td className="table-cell text-[12px] text-brand-500 whitespace-nowrap">{row.marca ?? '—'}</td>
                    <td className="table-cell text-right tabular-nums text-[13px]">{row.stock_fisico}</td>
                    <td className="table-cell text-right tabular-nums text-[13px] text-brand-500">
                      {row.consumo_promedio_diario > 0 ? row.consumo_promedio_diario.toFixed(2) : '—'}
                    </td>
                    <td className="table-cell text-right">
                      <CoberturaCell dias={row.cobertura_dias} stock={row.stock_fisico} />
                    </td>
                    <td className="table-cell text-right tabular-nums text-[13px] text-brand-500">
                      {row.demanda_proyectada > 0 ? row.demanda_proyectada.toFixed(0) : '—'}
                    </td>
                    <td className="table-cell text-right">
                      {row.sugerido_comprar > 0
                        ? <span className="tabular-nums text-[13px] font-semibold text-red-600">{row.sugerido_comprar.toFixed(0)}</span>
                        : <span className="text-brand-300">—</span>}
                    </td>
                    <td className="table-cell text-[12px] text-brand-500 whitespace-nowrap">{fmtDate(row.ultimo_mov_out)}</td>
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
