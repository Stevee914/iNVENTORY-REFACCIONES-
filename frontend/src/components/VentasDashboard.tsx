import { useEffect, useRef, useState } from 'react';
import { ChevronLeft, ChevronRight, Users } from 'lucide-react';
import { facturaService } from '@/services';
import type {
  VentasDashboardKPIs,
  ClienteRanking,
  ClienteDetalleResponse,
} from '@/services/facturaService';
import { cn } from '@/lib/utils';

// ── Module-level cache ────────────────────────────────────────────────────────
// Keyed by "anio-mes-minMonto". Entries expire after 5 minutes so stale data
// is never shown for more than one session segment. The cache lives as long as
// the JS bundle is loaded (i.e. within a single browser session / PWA launch).

const CACHE_TTL_MS = 5 * 60 * 1000; // 5 minutes

interface CacheEntry {
  kpis: VentasDashboardKPIs;
  clientes: ClienteRanking[];
  ts: number;
}

const _dashCache = new Map<string, CacheEntry>();

function getCached(key: string): CacheEntry | null {
  const entry = _dashCache.get(key);
  if (!entry) return null;
  if (Date.now() - entry.ts > CACHE_TTL_MS) { _dashCache.delete(key); return null; }
  return entry;
}

// ── Constants ─────────────────────────────────────────────────────────────────

const MES_NOMBRES = [
  'Enero','Febrero','Marzo','Abril','Mayo','Junio',
  'Julio','Agosto','Septiembre','Octubre','Noviembre','Diciembre',
];

const TIPO_CLIENTE_COLORS: Record<string, string> = {
  CREDITO:   'bg-red-50 text-red-700 border border-red-200',
  TALLER:    'bg-purple-50 text-purple-700 border border-purple-200',
  MOSTRADOR: 'bg-surface-100 text-brand-600 border border-surface-200',
};

const ESTATUS_COLORS: Record<string, string> = {
  PAGADA:  'bg-emerald-50 text-emerald-700 border border-emerald-200',
  CREDITO: 'bg-red-50 text-red-700 border border-red-200',
  PARCIAL: 'bg-amber-50 text-amber-700 border border-amber-200',
};

const MIN_MONTO_OPTIONS = [
  { label: '$1k',  value: 1000 },
  { label: '$5k',  value: 5000 },
  { label: '$10k', value: 10000 },
  { label: '$20k', value: 20000 },
];

// ── Formatters ────────────────────────────────────────────────────────────────

function fmtMXN(n: number | string) {
  return '$' + Number(n).toLocaleString('es-MX', { minimumFractionDigits: 2, maximumFractionDigits: 2 });
}

function fmtK(n: number | string) {
  const v = Number(n);
  if (v >= 1_000_000) return `$${(v / 1_000_000).toFixed(1)}M`;
  if (v >= 1_000)     return `$${(v / 1_000).toFixed(0)}k`;
  return `$${v.toFixed(0)}`;
}

function fmtFechaCorta(s: string) {
  const [, m, d] = s.split('-').map(Number);
  const meses = ['Ene','Feb','Mar','Abr','May','Jun','Jul','Ago','Sep','Oct','Nov','Dic'];
  return `${d} ${meses[m - 1]}`;
}

// ── KPI Card ──────────────────────────────────────────────────────────────────

interface KpiCardProps {
  label:       string;
  value:       string;
  secondary?:  string;
  accent:      string;
  valueClass?: string;
}

function KpiCard({ label, value, secondary, accent, valueClass }: KpiCardProps) {
  return (
    <div className={cn(
      'bg-white border border-surface-100 rounded-lg shadow-sm px-4 py-3 border-l-2',
      accent,
    )}>
      <p className="text-[11px] text-brand-400 uppercase tracking-wide leading-none truncate">{label}</p>
      <p className={cn('text-[19px] font-bold mt-1 leading-tight tabular-nums', valueClass ?? 'text-brand-800')}>
        {value}
      </p>
      {secondary && (
        <p className="text-[10px] text-brand-400 mt-0.5 truncate">{secondary}</p>
      )}
    </div>
  );
}

// ── Skeletons ─────────────────────────────────────────────────────────────────

function KpiSkeletons() {
  return (
    <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-6 gap-3">
      {Array.from({ length: 6 }).map((_, i) => (
        <div key={i} className="h-[72px] bg-surface-100 rounded-lg animate-pulse" />
      ))}
    </div>
  );
}

function ListSkeletons() {
  return (
    <div className="space-y-2 mt-1">
      {Array.from({ length: 5 }).map((_, i) => (
        <div key={i} className="h-10 bg-surface-100 rounded-lg animate-pulse" />
      ))}
    </div>
  );
}

// ── Props ─────────────────────────────────────────────────────────────────────

interface Props {
  refreshKey?: number;
}

// ── Main Component ────────────────────────────────────────────────────────────

export function VentasDashboard({ refreshKey }: Props) {
  const today = new Date();

  const [anio, setAnio] = useState(today.getFullYear());
  const [mes,  setMes]  = useState(today.getMonth() + 1);
  const [minMonto, setMinMonto] = useState(5000);

  const [kpis,        setKpis]        = useState<VentasDashboardKPIs | null>(null);
  const [topClientes, setTopClientes] = useState<ClienteRanking[]>([]);
  const [loadingMain, setLoadingMain] = useState(true);

  const [selectedClienteId, setSelectedClienteId]  = useState<number | null>(null);
  const [detalle,            setDetalle]            = useState<ClienteDetalleResponse | null>(null);
  const [loadingDetalle,     setLoadingDetalle]     = useState(false);

  const isCurrentMonth = anio === today.getFullYear() && mes === today.getMonth() + 1;

  // ── Month navigation ───────────────────────────────────────────────────────

  const goToPrevMonth = () => {
    if (mes === 1) { setAnio(a => a - 1); setMes(12); }
    else setMes(m => m - 1);
  };

  const goToNextMonth = () => {
    if (mes === 12) { setAnio(a => a + 1); setMes(1); }
    else setMes(m => m + 1);
  };

  // ── Load KPIs + top clients when month/threshold/refreshKey changes ────────
  // Results are cached by (anio, mes, minMonto) for 5 minutes so navigating
  // away and back doesn't fire two more API calls.  A refreshKey bump (from
  // sync/create/delete) bypasses the cache to force a fresh read.
  const prevRefreshKey = useRef(refreshKey ?? 0);

  useEffect(() => {
    setSelectedClienteId(null);
    setDetalle(null);

    const cacheKey = `${anio}-${mes}-${minMonto}`;
    const forceRefresh = (refreshKey ?? 0) !== prevRefreshKey.current;
    prevRefreshKey.current = refreshKey ?? 0;

    const cached = forceRefresh ? null : getCached(cacheKey);
    if (cached) {
      setKpis(cached.kpis);
      setTopClientes(cached.clientes);
      setLoadingMain(false);
      return;
    }

    setLoadingMain(true);
    Promise.all([
      facturaService.getDashboard(anio, mes, minMonto),
      facturaService.getDashboardTopClientes(anio, mes, minMonto),
    ])
      .then(([dash, top]) => {
        setKpis(dash.kpis);
        setTopClientes(top.clientes);
        _dashCache.set(cacheKey, { kpis: dash.kpis, clientes: top.clientes, ts: Date.now() });
      })
      .catch(console.error)
      .finally(() => setLoadingMain(false));
  }, [anio, mes, minMonto, refreshKey]);

  // ── Load customer detail on click ──────────────────────────────────────────

  useEffect(() => {
    if (selectedClienteId == null) { setDetalle(null); return; }
    setLoadingDetalle(true);
    facturaService.getDashboardClienteDetalle(selectedClienteId, anio, mes)
      .then(setDetalle)
      .catch(console.error)
      .finally(() => setLoadingDetalle(false));
  }, [selectedClienteId, anio, mes]);

  const maxMonto = Number(topClientes[0]?.total_mes ?? 0);

  // ── Render ─────────────────────────────────────────────────────────────────

  return (
    <div className="mb-8 space-y-4">

      {/* ── Month selector ── */}
      <div className="flex items-center gap-1">
        <button onClick={goToPrevMonth} className="btn-ghost p-1.5" title="Mes anterior">
          <ChevronLeft className="w-4 h-4" />
        </button>
        <span className="text-[14px] font-semibold text-brand-700 min-w-[140px] text-center select-none">
          {MES_NOMBRES[mes - 1]} {anio}
        </span>
        <button
          onClick={goToNextMonth}
          disabled={isCurrentMonth}
          className="btn-ghost p-1.5 disabled:opacity-30 disabled:cursor-not-allowed"
          title="Mes siguiente"
        >
          <ChevronRight className="w-4 h-4" />
        </button>
      </div>

      {/* ── KPI cards ── */}
      {loadingMain || !kpis ? (
        <KpiSkeletons />
      ) : (
        <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-6 gap-3">
          <KpiCard
            label="Documentos"
            value={String(kpis.total_documentos)}
            secondary="del mes"
            accent="border-l-sap-blue"
          />
          <KpiCard
            label="Total vendido"
            value={fmtK(kpis.total_vendido)}
            secondary="del mes"
            accent="border-l-emerald-500"
            valueClass="text-emerald-700"
          />
          <KpiCard
            label="Por cobrar"
            value={fmtK(kpis.total_por_cobrar)}
            secondary={`acumulado · ${kpis.docs_pendientes} pend.${kpis.docs_vencidos > 0 ? ` · ${kpis.docs_vencidos} venc.` : ''}`}
            accent={kpis.total_por_cobrar > 0 ? 'border-l-red-500' : 'border-l-slate-200'}
            valueClass={kpis.total_por_cobrar > 0 ? 'text-red-600' : 'text-brand-800'}
          />
          <KpiCard
            label="Pendientes"
            value={String(kpis.docs_pendientes)}
            secondary={`acumulado · ${kpis.docs_vencidos > 0 ? `${kpis.docs_vencidos} vencidos` : 'sin vencer'}`}
            accent={kpis.docs_vencidos > 0 ? 'border-l-red-500' : kpis.docs_pendientes > 0 ? 'border-l-amber-500' : 'border-l-slate-200'}
            valueClass={kpis.docs_vencidos > 0 ? 'text-red-600' : kpis.docs_pendientes > 0 ? 'text-amber-700' : 'text-brand-800'}
          />
          <KpiCard
            label="Clientes activos"
            value={String(kpis.clientes_con_compra)}
            secondary="con compra este mes"
            accent="border-l-slate-300"
          />
          <KpiCard
            label={`Clientes ≥ ${fmtK(minMonto)}`}
            value={String(kpis.clientes_arriba)}
            secondary="en el mes"
            accent="border-l-purple-400"
            valueClass="text-purple-700"
          />
        </div>
      )}

      {/* ── Top clients + detail panel ── */}
      <div className="bg-white border border-surface-100 rounded-lg shadow-sm overflow-hidden flex flex-col lg:flex-row divide-y lg:divide-y-0 lg:divide-x divide-surface-200">

        {/* Left — ranking */}
        <div className="lg:w-[55%] p-5">
          {/* Panel header + threshold selector */}
          <div className="flex items-center justify-between gap-3 mb-3">
            <p className="text-[11px] font-semibold text-brand-400 uppercase tracking-wide">
              Top Clientes — {MES_NOMBRES[mes - 1]} {anio}
            </p>
            <div className="flex items-center gap-1 shrink-0">
              {MIN_MONTO_OPTIONS.map(opt => (
                <button
                  key={opt.value}
                  onClick={() => setMinMonto(opt.value)}
                  className={cn(
                    'px-2 py-0.5 text-[10px] font-semibold rounded transition-colors',
                    minMonto === opt.value
                      ? 'bg-sap-blue text-white'
                      : 'bg-surface-100 text-brand-500 hover:bg-surface-200',
                  )}
                >
                  {opt.label}
                </button>
              ))}
            </div>
          </div>

          {loadingMain ? (
            <ListSkeletons />
          ) : topClientes.length === 0 ? (
            <div className="flex flex-col items-center justify-center py-10 text-brand-400">
              <Users className="w-7 h-7 mb-2 opacity-20" />
              <p className="text-sm">Sin clientes con compras ≥ {fmtK(minMonto)}</p>
            </div>
          ) : (
            <div className="space-y-0.5">
              {topClientes.map((cliente, idx) => {
                const isSelected = selectedClienteId === cliente.cliente_id;
                const barPct = maxMonto > 0 ? (Number(cliente.total_mes) / maxMonto) * 100 : 0;
                return (
                  <button
                    key={cliente.cliente_id}
                    onClick={() => setSelectedClienteId(isSelected ? null : cliente.cliente_id)}
                    className={cn(
                      'w-full text-left px-3 py-2 rounded-lg transition-colors',
                      isSelected
                        ? 'bg-sap-blue/10 border border-sap-blue/20'
                        : 'hover:bg-surface-50 border border-transparent',
                    )}
                  >
                    {/* Rank · name · amount */}
                    <div className="flex items-center gap-2">
                      <span className="text-[11px] text-brand-400 w-4 shrink-0 tabular-nums text-right">
                        {idx + 1}
                      </span>
                      <span className="text-[13px] font-semibold text-brand-800 flex-1 truncate">
                        {cliente.cliente_nombre}
                      </span>
                      {cliente.saldo_pendiente_mes > 0 && (
                        <span className="text-[10px] text-red-600 shrink-0 tabular-nums">
                          -{fmtK(cliente.saldo_pendiente_mes)}
                        </span>
                      )}
                      <span className="text-[13px] font-semibold text-brand-700 tabular-nums shrink-0">
                        {fmtK(cliente.total_mes)}
                      </span>
                    </div>

                    {/* Proportional bar */}
                    <div className="ml-6 mt-1.5 h-1 bg-surface-100 rounded-full overflow-hidden">
                      <div
                        className="h-full bg-sap-blue/50 rounded-full transition-all"
                        style={{ width: `${barPct}%` }}
                      />
                    </div>

                    {/* Sub info */}
                    <div className="ml-6 flex items-center gap-3 mt-1">
                      <span className={cn(
                        'text-[10px] font-semibold px-1.5 py-0 rounded-full',
                        TIPO_CLIENTE_COLORS[cliente.tipo] ?? TIPO_CLIENTE_COLORS.MOSTRADOR,
                      )}>
                        {cliente.tipo}
                      </span>
                      <span className="text-[10px] text-brand-400">{cliente.num_docs} docs</span>
                      {cliente.ultima_compra && (
                        <span className="text-[10px] text-brand-400">
                          último: {fmtFechaCorta(String(cliente.ultima_compra))}
                        </span>
                      )}
                    </div>
                  </button>
                );
              })}
            </div>
          )}
        </div>

        {/* Right — customer detail */}
        <div className="lg:w-[45%] p-5">
          {loadingDetalle ? (
            <div className="flex items-center justify-center h-52">
              <div className="w-5 h-5 border-2 border-surface-300 border-t-sap-blue rounded-full animate-spin" />
            </div>

          ) : !selectedClienteId || !detalle ? (
            <div className="flex flex-col items-center justify-center h-52 text-brand-400">
              <Users className="w-8 h-8 mb-2 opacity-15" />
              <p className="text-[13px]">Selecciona un cliente para ver el detalle</p>
            </div>

          ) : (
            <div className="space-y-5">

              {/* Header */}
              <div className="flex items-start justify-between gap-2">
                <div>
                  <p className="text-[16px] font-bold text-brand-800 leading-tight">{detalle.cliente_nombre}</p>
                  <p className="text-[12px] text-brand-400 mt-0.5">{MES_NOMBRES[mes - 1]} {anio}</p>
                </div>
                <span className={cn(
                  'text-[10px] font-semibold px-2 py-0.5 rounded-full shrink-0 mt-0.5',
                  TIPO_CLIENTE_COLORS[detalle.tipo] ?? TIPO_CLIENTE_COLORS.MOSTRADOR,
                )}>
                  {detalle.tipo}
                </span>
              </div>

              {/* Stats 2×3 grid */}
              <div className="grid grid-cols-2 gap-x-6 gap-y-3">
                <div>
                  <p className="text-[10px] text-brand-400 uppercase tracking-wide">Total del mes</p>
                  <p className="text-[14px] font-bold text-brand-800 tabular-nums">
                    {fmtMXN(detalle.stats.total_mes)}
                  </p>
                </div>
                <div>
                  <p className="text-[10px] text-brand-400 uppercase tracking-wide">Documentos</p>
                  <p className="text-[14px] font-bold text-brand-800">{detalle.stats.num_docs}</p>
                </div>
                <div>
                  <p className="text-[10px] text-brand-400 uppercase tracking-wide">Por cobrar (total)</p>
                  <p className={cn(
                    'text-[14px] font-semibold tabular-nums',
                    detalle.stats.saldo_pendiente_total > 0 ? 'text-red-600' : 'text-emerald-700',
                  )}>
                    {fmtMXN(detalle.stats.saldo_pendiente_total)}
                  </p>
                </div>
                <div>
                  <p className="text-[10px] text-brand-400 uppercase tracking-wide">Histórico total</p>
                  <p className="text-[14px] font-semibold text-brand-800 tabular-nums">
                    {fmtMXN(detalle.stats.total_historico)}
                  </p>
                </div>
                <div className="col-span-2">
                  <p className="text-[10px] text-brand-400 uppercase tracking-wide">Última compra</p>
                  <p className="text-[14px] font-semibold text-brand-800">
                    {detalle.stats.ultima_compra
                      ? fmtFechaCorta(String(detalle.stats.ultima_compra))
                      : '—'}
                  </p>
                </div>
              </div>

              {/* Documentos recientes */}
              {detalle.documentos_recientes.length > 0 && (
                <div>
                  <p className="text-[11px] font-semibold text-brand-400 uppercase tracking-wide mb-2">
                    Documentos del mes
                  </p>
                  <div>
                    {detalle.documentos_recientes.map((doc) => (
                      <div
                        key={doc.id}
                        className="flex items-center gap-2 py-1.5 border-b border-surface-100 last:border-0"
                      >
                        <span className="text-[11px] text-brand-400 shrink-0 w-10">
                          {fmtFechaCorta(doc.fecha)}
                        </span>
                        <span className="font-mono text-[11px] text-brand-600 flex-1 truncate min-w-0">
                          {doc.folio}
                        </span>
                        <span className="text-[12px] font-semibold text-brand-700 tabular-nums shrink-0">
                          {fmtK(doc.monto)}
                        </span>
                        {doc.saldo_pendiente > 0 && (
                          <span className="text-[10px] text-red-600 tabular-nums shrink-0">
                            -{fmtK(doc.saldo_pendiente)}
                          </span>
                        )}
                        <span className={cn(
                          'text-[10px] font-semibold px-1.5 py-0.5 rounded-full shrink-0',
                          ESTATUS_COLORS[doc.estatus] ?? 'bg-surface-100 text-brand-500',
                        )}>
                          {doc.estatus}
                        </span>
                      </div>
                    ))}
                  </div>
                </div>
              )}

            </div>
          )}
        </div>
      </div>
    </div>
  );
}
