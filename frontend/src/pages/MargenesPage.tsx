import { useEffect, useRef, useState } from 'react';
import { Link } from 'react-router-dom';
import {
  Search, TrendingDown, AlertTriangle, Package, DollarSign, Tag,
  ChevronLeft, ChevronRight, ChevronsLeft, ChevronsRight, Download,
} from 'lucide-react';
import { PageHeader, KpiCard } from '@/components/shared';
import { margenesService, type MargenItem, type MargenesTotals } from '@/services/margenesService';
import { useFilterOptions } from '@/hooks/useFilterOptions';
import { cn } from '@/lib/utils';

const PAGE_SIZES = [25, 50, 100];

function fmt(n: number | null, d = 2): string {
  if (n === null || n === undefined) return '—';
  return Number(n).toLocaleString('es-MX', { minimumFractionDigits: d, maximumFractionDigits: d });
}
function fmtMoney(n: number | null): string { return n === null ? '—' : '$' + fmt(n); }
function fmtPct(n: number | null): string   { return n === null ? '—' : Number(n).toFixed(1) + '%'; }

function margenColor(pct: number | null): string {
  if (pct === null) return 'text-surface-400';
  if (pct < 0)   return 'text-red-700 font-semibold';
  if (pct < 15)  return 'text-red-600 font-semibold';
  if (pct < 25)  return 'text-amber-600 font-semibold';
  return 'text-emerald-600 font-semibold';
}

function FuenteBadge({ fuente }: { fuente: 'REAL' | 'POS' | 'MANUAL' | null }) {
  if (!fuente) return <span className="px-2 py-0.5 rounded text-[10px] font-medium bg-surface-100 text-surface-400">—</span>;
  if (fuente === 'REAL') return <span className="px-2 py-0.5 rounded text-[10px] font-medium bg-emerald-100 text-emerald-700">REAL</span>;
  if (fuente === 'MANUAL') return <span className="px-2 py-0.5 rounded text-[10px] font-medium bg-blue-100 text-blue-700">MANUAL</span>;
  return <span className="px-2 py-0.5 rounded text-[10px] font-medium bg-amber-100 text-amber-700">POS</span>;
}

export function MargenesPage() {
  const opts = useFilterOptions();

  // Filters
  const [searchInput,      setSearchInput     ] = useState('');
  const [searchQ,          setSearchQ         ] = useState('');
  const [catId,            setCatId           ] = useState<number | ''>('');
  const [marcaF,           setMarcaF          ] = useState('');
  const [provId,           setProvId          ] = useState<number | ''>('');
  const [sinCosto,         setSinCosto        ] = useState(false);
  const [sinPrecioPublico, setSinPrecioPublico] = useState(false);
  const [margenNegativo,   setMargenNegativo  ] = useState(false);
  const [margenBajoInput,  setMargenBajoInput ] = useState('');
  const [margenBajo,       setMargenBajo      ] = useState<number | undefined>();

  // Data
  const [items,   setItems  ] = useState<MargenItem[]>([]);
  const [totals,  setTotals ] = useState<MargenesTotals | null>(null);
  const [loading, setLoading] = useState(true);
  const [error,   setError  ] = useState<string | null>(null);

  // Pagination
  const [page,     setPage    ] = useState(1);
  const [pageSize, setPageSize] = useState(50);

  const searchRef  = useRef<ReturnType<typeof setTimeout> | null>(null);
  const margenRef  = useRef<ReturnType<typeof setTimeout> | null>(null);

  function handleSearch(v: string) {
    setSearchInput(v);
    if (searchRef.current) clearTimeout(searchRef.current);
    searchRef.current = setTimeout(() => { setSearchQ(v); setPage(1); }, 300);
  }

  function handleMargenBajo(raw: string) {
    setMargenBajoInput(raw);
    if (margenNegativo) return;
    if (margenRef.current) clearTimeout(margenRef.current);
    margenRef.current = setTimeout(() => {
      const n = parseFloat(raw);
      setMargenBajo(!raw || isNaN(n) ? undefined : n);
      setPage(1);
    }, 400);
  }

  useEffect(() => { load(); }, [searchQ, catId, marcaF, provId, sinCosto, sinPrecioPublico, margenNegativo, margenBajo, page, pageSize]);

  async function load() {
    setLoading(true); setError(null);
    try {
      const res = await margenesService.getAll({
        q:               searchQ || undefined,
        categoriaId:     catId   !== '' ? Number(catId)  : undefined,
        marca:           marcaF  || undefined,
        proveedorId:     provId  !== '' ? Number(provId) : undefined,
        sinCosto:        sinCosto        || undefined,
        sinPrecioPublico: sinPrecioPublico || undefined,
        margenNegativo:  margenNegativo  || undefined,
        margenBajo:      !margenNegativo ? margenBajo : undefined,
        page,
        pageSize,
      });
      setItems(res.items);
      setTotals(res.totals);
    } catch (e: any) {
      setError(e.message || 'Error cargando datos');
    } finally {
      setLoading(false);
    }
  }

  function resetFilters() {
    setSearchInput(''); setSearchQ(''); setCatId(''); setMarcaF(''); setProvId('');
    setSinCosto(false); setSinPrecioPublico(false); setMargenNegativo(false);
    setMargenBajoInput(''); setMargenBajo(undefined); setPage(1);
  }

  async function exportCSV() {
    try {
      const res = await margenesService.getAll({
        q: searchQ || undefined, categoriaId: catId !== '' ? Number(catId) : undefined,
        marca: marcaF || undefined, proveedorId: provId !== '' ? Number(provId) : undefined,
        sinCosto: sinCosto || undefined, sinPrecioPublico: sinPrecioPublico || undefined,
        margenNegativo: margenNegativo || undefined,
        margenBajo: !margenNegativo ? margenBajo : undefined,
        page: 1, pageSize: 10000,
      });
      const header = ['SKU','Producto','Marca','Categoría','Costo Base','Fuente','Precio Público','Precio Venta','Utilidad','Margen %','Markup %','Proveedor'];
      const escape = (v: string | number | null) => {
        const s = String(v ?? '');
        return s.includes(',') || s.includes('"') ? `"${s.replace(/"/g,'""')}"` : s;
      };
      const rows = res.items.map(r => [
        r.sku, r.name, r.marca??'', r.categoria??'',
        r.costo_base, r.fuente_costo??'',
        r.precio_publico, r.precio_final, r.utilidad,
        r.margen_porcentaje, r.markup_porcentaje, r.proveedor??'',
      ].map(escape).join(','));
      const csv = [header.join(','), ...rows].join('\r\n');
      const blob = new Blob(['\uFEFF' + csv], { type: 'text/csv;charset=utf-8;' });
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a'); a.href = url;
      a.download = `margenes_${new Date().toISOString().slice(0,10)}.csv`;
      a.click(); URL.revokeObjectURL(url);
    } catch {}
  }

  const totalPages = Math.ceil((totals?.total ?? 0) / pageSize);

  return (
    <div>
      <PageHeader
        title="Análisis de Márgenes"
        description="Rentabilidad por producto — ordenado de menor a mayor margen"
        actions={
          <button className="btn-secondary" onClick={exportCSV}>
            <Download className="w-4 h-4" /> Exportar CSV
          </button>
        }
      />

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

          {/* Margen bajo */}
          {!margenNegativo && (
            <div className="flex items-center gap-1.5">
              <label className="text-[12px] text-brand-500 whitespace-nowrap">Margen &lt;</label>
              <input type="number" value={margenBajoInput} onChange={e => handleMargenBajo(e.target.value)}
                placeholder="ej. 30" min={0} max={100} className="input-field py-1.5 w-16 text-center text-[13px]" />
              <span className="text-[12px] text-brand-400">%</span>
            </div>
          )}

          {/* Quick toggles */}
          <div className="flex flex-wrap gap-1.5 items-center">
            {([
              ['Sin costo',      sinCosto,         setSinCosto,         'text-amber-700 bg-amber-50 border-amber-300'],
              ['Sin precio púb.', sinPrecioPublico, setSinPrecioPublico, 'text-blue-700 bg-blue-50 border-blue-300'],
              ['Margen negativo', margenNegativo,   (v: boolean) => { setMargenNegativo(v); if (v) { setMargenBajoInput(''); setMargenBajo(undefined); } }, 'text-red-700 bg-red-50 border-red-300'],
            ] as const).map(([label, val, setter, activeClass]) => (
              <button key={label} onClick={() => { (setter as any)(!val); setPage(1); }}
                className={cn(
                  'px-2.5 py-1 rounded-full text-[11px] font-medium border transition-colors',
                  val ? activeClass : 'text-brand-400 bg-surface-50 border-surface-200 hover:border-surface-300'
                )}>
                {label}
              </button>
            ))}
          </div>

          <div className="ml-auto flex items-center gap-3">
            {(searchQ || catId !== '' || marcaF || provId !== '' || sinCosto || sinPrecioPublico || margenNegativo || margenBajo !== undefined) && (
              <button onClick={resetFilters} className="text-[12px] text-brand-400 hover:text-brand-600">Limpiar</button>
            )}
            <span className="text-xs text-brand-400">{(totals?.total ?? 0).toLocaleString('es-MX')} resultado{(totals?.total ?? 0) !== 1 ? 's' : ''}</span>
          </div>
        </div>
      </div>

      {/* KPI Cards — always full dataset (totals from backend) */}
      <div className="grid grid-cols-2 lg:grid-cols-5 gap-3 mb-4">
        <KpiCard title="Total Productos"   value={(totals?.total ?? '—').toLocaleString?.() ?? '—'}         icon={Package}      subtitle="en esta consulta" />
        <KpiCard title="Sin Costo"         value={totals?.sin_costo ?? '—'}                                  icon={DollarSign}   subtitle="sin costo registrado"  variant={totals && totals.sin_costo > 0 ? 'warning' : 'default'} />
        <KpiCard title="Sin Precio Púb."   value={totals?.sin_precio_publico ?? '—'}                         icon={Tag}          subtitle="sin precio público"     variant={totals && totals.sin_precio_publico > 0 ? 'warning' : 'default'} />
        <KpiCard
          title="Margen Promedio"
          value={totals?.margen_promedio !== null && totals?.margen_promedio !== undefined ? fmtPct(totals.margen_promedio) : '—'}
          icon={TrendingDown}
          subtitle="del conjunto filtrado"
          variant={totals?.margen_promedio !== null && totals?.margen_promedio !== undefined
            ? (totals.margen_promedio < 15 ? 'critical' : totals.margen_promedio < 25 ? 'warning' : 'default')
            : 'default'}
        />
        <KpiCard title="En Riesgo < 15%"   value={totals?.en_riesgo ?? '—'}                                  icon={AlertTriangle} subtitle="margen bajo umbral"    variant={totals && totals.en_riesgo > 0 ? 'critical' : 'default'} />
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
                <th className="table-header text-right">Costo Base</th>
                <th className="table-header text-center">Fuente</th>
                <th className="table-header text-right">Precio Púb.</th>
                <th className="table-header text-right">Precio Venta</th>
                <th className="table-header text-right">Utilidad</th>
                <th className="table-header text-right">Margen %</th>
                <th className="table-header text-right">Markup %</th>
                <th className="table-header">Proveedor</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-surface-100">
              {loading && items.length === 0 ? (
                <tr><td colSpan={12} className="px-4 py-12 text-center">
                  <div className="w-6 h-6 border-2 border-surface-300 border-t-sap-blue rounded-full animate-spin mx-auto" />
                </td></tr>
              ) : error ? (
                <tr><td colSpan={12} className="px-4 py-10 text-center text-status-critical text-[13px]">{error}</td></tr>
              ) : items.length === 0 ? (
                <tr><td colSpan={12} className="px-4 py-12 text-center text-[13px] text-brand-400">
                  {sinCosto
                    ? 'Sin costo registrado. Se actualizarán con la sincronización POS o al registrar compras.'
                    : 'No se encontraron productos con los filtros aplicados.'}
                </td></tr>
              ) : items.map(row => {
                const negativo = row.margen_porcentaje !== null && row.margen_porcentaje < 0;
                return (
                  <tr key={row.producto_id} className={cn(
                    'transition-colors',
                    negativo ? 'bg-red-50/50 hover:bg-red-50' : 'hover:bg-surface-50',
                    loading && 'opacity-50',
                  )}>
                    <td className="table-cell">
                      <Link to={`/productos/${row.sku}`} className="font-mono text-xs font-medium text-brand-600 hover:text-sap-blue hover:underline">{row.sku}</Link>
                    </td>
                    <td className="table-cell max-w-[200px]"><span className="text-[13px] truncate block" title={row.name}>{row.name}</span></td>
                    <td className="table-cell text-[12px] text-brand-500 whitespace-nowrap">{row.marca ?? '—'}</td>
                    <td className="table-cell text-[12px] text-brand-500 max-w-[140px]"><span className="truncate block" title={row.categoria ?? ''}>{row.categoria ?? '—'}</span></td>
                    <td className="table-cell text-right"><span className={cn('tabular-nums text-[13px]', row.costo_base === null && 'text-surface-400')}>{fmtMoney(row.costo_base)}</span></td>
                    <td className="table-cell text-center"><FuenteBadge fuente={row.fuente_costo} /></td>
                    <td className="table-cell text-right"><span className={cn('tabular-nums text-[13px]', row.precio_publico === null && 'text-surface-400')}>{fmtMoney(row.precio_publico)}</span></td>
                    <td className="table-cell text-right"><span className={cn('tabular-nums text-[13px]', row.precio_final === null && 'text-surface-400')}>{fmtMoney(row.precio_final)}</span></td>
                    <td className="table-cell text-right">
                      <span className={cn('tabular-nums text-[13px] font-medium',
                        row.utilidad === null ? 'text-surface-400' : row.utilidad < 0 ? 'text-red-600' : 'text-emerald-600'
                      )}>{fmtMoney(row.utilidad)}</span>
                    </td>
                    <td className="table-cell text-right"><span className={cn('tabular-nums text-[13px]', margenColor(row.margen_porcentaje))}>{fmtPct(row.margen_porcentaje)}</span></td>
                    <td className="table-cell text-right"><span className={cn('tabular-nums text-[13px]', row.markup_porcentaje === null && 'text-surface-400')}>{fmtPct(row.markup_porcentaje)}</span></td>
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
            <p className="text-xs text-brand-400">Página {page} de {Math.max(1, totalPages)} — {(totals?.total ?? 0).toLocaleString('es-MX')} productos</p>
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
