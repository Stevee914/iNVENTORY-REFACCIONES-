import { useEffect, useState } from 'react';
import { ChevronLeft, ChevronRight, Store } from 'lucide-react';
import { comprasService } from '@/services';
import type {
  DashboardKPIs,
  ProveedorRanking,
  ProveedorDetalleResponse,
} from '@/services/comprasService';
import { cn } from '@/lib/utils';

// ── Constants ─────────────────────────────────────────────────────────────────

const MES_NOMBRES = [
  'Enero','Febrero','Marzo','Abril','Mayo','Junio',
  'Julio','Agosto','Septiembre','Octubre','Noviembre','Diciembre',
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
  accent:      string;   // border-l color class
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
    <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-5 gap-3">
      {Array.from({ length: 5 }).map((_, i) => (
        <div key={i} className="h-[72px] bg-surface-100 rounded-lg animate-pulse" />
      ))}
    </div>
  );
}

function ListSkeletons() {
  return (
    <div className="space-y-2 mt-1">
      {Array.from({ length: 6 }).map((_, i) => (
        <div key={i} className="h-10 bg-surface-100 rounded-lg animate-pulse" />
      ))}
    </div>
  );
}

// ── Main Component ────────────────────────────────────────────────────────────

export function ComprasDashboard() {
  const today = new Date();

  const [anio, setAnio] = useState(today.getFullYear());
  const [mes,  setMes]  = useState(today.getMonth() + 1);

  const [kpis,        setKpis]        = useState<DashboardKPIs | null>(null);
  const [topProvs,    setTopProvs]    = useState<ProveedorRanking[]>([]);
  const [loadingMain, setLoadingMain] = useState(true);

  const [selectedProvId,  setSelectedProvId]  = useState<number | null>(null);
  const [detalle,         setDetalle]         = useState<ProveedorDetalleResponse | null>(null);
  const [loadingDetalle,  setLoadingDetalle]  = useState(false);

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

  // ── Load KPIs + top providers when month changes ───────────────────────────

  useEffect(() => {
    setLoadingMain(true);
    setSelectedProvId(null);
    setDetalle(null);

    Promise.all([
      comprasService.getDashboard(anio, mes),
      comprasService.getTopProveedores(anio, mes),
    ])
      .then(([dash, top]) => {
        setKpis(dash.kpis);
        setTopProvs(top.proveedores);
      })
      .catch(console.error)
      .finally(() => setLoadingMain(false));
  }, [anio, mes]);

  // ── Load supplier detail on click ──────────────────────────────────────────

  useEffect(() => {
    if (selectedProvId == null) { setDetalle(null); return; }
    setLoadingDetalle(true);
    comprasService.getProveedorDetalle(selectedProvId, anio, mes)
      .then(setDetalle)
      .catch(console.error)
      .finally(() => setLoadingDetalle(false));
  }, [selectedProvId, anio, mes]);

  const maxMonto = Number(topProvs[0]?.total_monto ?? 0);

  // ── Render ─────────────────────────────────────────────────────────────────

  return (
    <div className="mb-8 space-y-4">

      {/* ── Month selector ── */}
      <div className="flex items-center gap-1">
        <button
          onClick={goToPrevMonth}
          className="btn-ghost p-1.5"
          title="Mes anterior"
        >
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
        <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-5 gap-3">
          <KpiCard
            label="Total del Mes"
            value={fmtK(kpis.total_monto)}
            accent="border-l-sap-blue"
          />
          <KpiCard
            label="Con Factura"
            value={fmtK(kpis.con_factura_monto)}
            secondary={`${kpis.con_factura_count} compras`}
            accent="border-l-emerald-500"
            valueClass="text-emerald-700"
          />
          <KpiCard
            label="Sin Factura"
            value={fmtK(kpis.sin_factura_monto)}
            secondary={`${kpis.sin_factura_count} compras`}
            accent="border-l-amber-500"
            valueClass="text-amber-700"
          />
          <KpiCard
            label="Compras"
            value={String(kpis.total_compras)}
            secondary={`${kpis.compras_pos} POS · ${kpis.compras_manuales} Manual`}
            accent="border-l-slate-300"
          />
          <KpiCard
            label="Pendientes"
            value={String(kpis.compras_pendientes)}
            accent={kpis.compras_pendientes > 0 ? 'border-l-red-500' : 'border-l-slate-200'}
            valueClass={kpis.compras_pendientes > 0 ? 'text-red-600' : 'text-brand-800'}
          />
        </div>
      )}

      {/* ── Top providers + detail panel ── */}
      <div className="bg-white border border-surface-100 rounded-lg shadow-sm overflow-hidden flex flex-col lg:flex-row divide-y lg:divide-y-0 lg:divide-x divide-surface-200">

        {/* Left — ranked list */}
        <div className="lg:w-[55%] p-5">
          <p className="text-[11px] font-semibold text-brand-400 uppercase tracking-wide mb-3">
            Top Proveedores — {MES_NOMBRES[mes - 1]} {anio}
          </p>

          {loadingMain ? (
            <ListSkeletons />
          ) : topProvs.length === 0 ? (
            <div className="flex flex-col items-center justify-center py-10 text-brand-400">
              <Store className="w-7 h-7 mb-2 opacity-20" />
              <p className="text-sm">Sin compras en este período</p>
            </div>
          ) : (
            <div className="space-y-0.5">
              {topProvs.map((prov, idx) => {
                const isSelected = selectedProvId === prov.proveedor_id;
                const barPct = maxMonto > 0 ? (Number(prov.total_monto) / maxMonto) * 100 : 0;
                return (
                  <button
                    key={prov.proveedor_id}
                    onClick={() => setSelectedProvId(isSelected ? null : prov.proveedor_id)}
                    className={cn(
                      'w-full text-left px-3 py-2 rounded-lg transition-colors',
                      isSelected
                        ? 'bg-sap-blue/10 border border-sap-blue/20'
                        : 'hover:bg-surface-50 border border-transparent',
                    )}
                  >
                    {/* Row: rank · name · amount */}
                    <div className="flex items-center gap-2">
                      <span className="text-[11px] text-brand-400 w-4 shrink-0 tabular-nums text-right">
                        {idx + 1}
                      </span>
                      <span className="text-[13px] font-semibold text-brand-800 flex-1 truncate">
                        {prov.proveedor_nombre}
                      </span>
                      <span className="text-[13px] font-semibold text-brand-700 tabular-nums shrink-0">
                        {fmtK(prov.total_monto)}
                      </span>
                    </div>

                    {/* Proportional bar */}
                    <div className="ml-6 mt-1.5 h-1 bg-surface-100 rounded-full overflow-hidden">
                      <div
                        className="h-full bg-sap-blue/50 rounded-full transition-all"
                        style={{ width: `${barPct}%` }}
                      />
                    </div>

                    {/* Sub-info: con/sin factura + count */}
                    <div className="ml-6 flex items-center gap-3 mt-1">
                      <span className="text-[10px] text-emerald-600">● {fmtK(prov.con_factura)}</span>
                      <span className="text-[10px] text-amber-600">● {fmtK(prov.sin_factura)}</span>
                      <span className="text-[10px] text-brand-400">{prov.num_compras} compras</span>
                    </div>
                  </button>
                );
              })}
            </div>
          )}
        </div>

        {/* Right — supplier detail */}
        <div className="lg:w-[45%] p-5">
          {loadingDetalle ? (
            <div className="flex items-center justify-center h-52">
              <div className="w-5 h-5 border-2 border-surface-300 border-t-sap-blue rounded-full animate-spin" />
            </div>

          ) : !selectedProvId || !detalle ? (
            <div className="flex flex-col items-center justify-center h-52 text-brand-400">
              <Store className="w-8 h-8 mb-2 opacity-15" />
              <p className="text-[13px]">Selecciona un proveedor para ver el detalle</p>
            </div>

          ) : (
            <div className="space-y-5">

              {/* Header */}
              <div>
                <p className="text-[16px] font-bold text-brand-800 leading-tight">{detalle.proveedor_nombre}</p>
                <p className="text-[12px] text-brand-400 mt-0.5">{MES_NOMBRES[mes - 1]} {anio}</p>
              </div>

              {/* Stats 2×3 grid */}
              <div className="grid grid-cols-2 gap-x-6 gap-y-3">
                <div>
                  <p className="text-[10px] text-brand-400 uppercase tracking-wide">Total del mes</p>
                  <p className="text-[14px] font-bold text-brand-800 tabular-nums">
                    {fmtMXN(detalle.stats.total_monto)}
                  </p>
                </div>
                <div>
                  <p className="text-[10px] text-brand-400 uppercase tracking-wide"># Compras</p>
                  <p className="text-[14px] font-bold text-brand-800">{detalle.stats.num_compras}</p>
                </div>
                <div>
                  <p className="text-[10px] text-brand-400 uppercase tracking-wide">Con Factura</p>
                  <p className="text-[14px] font-semibold text-emerald-700 tabular-nums">
                    {fmtMXN(detalle.stats.con_factura)}
                  </p>
                </div>
                <div>
                  <p className="text-[10px] text-brand-400 uppercase tracking-wide">Sin Factura</p>
                  <p className="text-[14px] font-semibold text-amber-700 tabular-nums">
                    {fmtMXN(detalle.stats.sin_factura)}
                  </p>
                </div>
                <div>
                  <p className="text-[10px] text-brand-400 uppercase tracking-wide">Ticket Prom.</p>
                  <p className="text-[14px] font-semibold text-brand-800 tabular-nums">
                    {fmtMXN(detalle.stats.ticket_promedio)}
                  </p>
                </div>
                <div>
                  <p className="text-[10px] text-brand-400 uppercase tracking-wide">Última compra</p>
                  <p className="text-[14px] font-semibold text-brand-800">
                    {detalle.stats.ultima_compra ? fmtFechaCorta(String(detalle.stats.ultima_compra)) : '—'}
                  </p>
                </div>
              </div>

              {/* Top productos */}
              {detalle.top_productos.length > 0 && (
                <div>
                  <p className="text-[11px] font-semibold text-brand-400 uppercase tracking-wide mb-2">
                    Productos más comprados
                  </p>
                  <div>
                    {detalle.top_productos.slice(0, 5).map((p) => (
                      <div
                        key={p.product_id}
                        className="flex items-center gap-2 py-1.5 border-b border-surface-100 last:border-0"
                      >
                        <span className="font-mono text-[11px] text-brand-500 w-[72px] shrink-0 truncate">
                          {p.sku}
                        </span>
                        <span className="text-[12px] text-brand-700 flex-1 truncate min-w-0">
                          {p.product_name}
                        </span>
                        <span className="text-[11px] text-brand-400 shrink-0 tabular-nums w-8 text-right">
                          {p.cantidad_total}
                        </span>
                        <span className="text-[12px] font-semibold text-brand-700 shrink-0 tabular-nums w-16 text-right">
                          {fmtK(p.monto_total)}
                        </span>
                      </div>
                    ))}
                  </div>
                </div>
              )}

              {/* Compras recientes */}
              {detalle.compras_recientes.length > 0 && (
                <div>
                  <p className="text-[11px] font-semibold text-brand-400 uppercase tracking-wide mb-2">
                    Compras recientes
                  </p>
                  <div>
                    {detalle.compras_recientes.map((c) => (
                      <div
                        key={c.compra_id}
                        className="flex items-center gap-2 py-1.5 border-b border-surface-100 last:border-0"
                      >
                        <span className="text-[11px] text-brand-400 shrink-0 w-10">
                          {fmtFechaCorta(c.fecha)}
                        </span>
                        <span className="font-mono text-[11px] text-brand-600 flex-1 truncate min-w-0">
                          {c.folio_factura ?? '—'}
                        </span>
                        <span className="text-[12px] font-semibold text-brand-700 tabular-nums shrink-0">
                          {fmtK(c.total)}
                        </span>
                        <span className={cn(
                          'text-[10px] font-semibold px-1.5 py-0.5 rounded-full shrink-0',
                          c.tipo_compra === 'CON_FACTURA'
                            ? 'bg-emerald-50 text-emerald-700 border border-emerald-200'
                            : 'bg-amber-50 text-amber-700 border border-amber-200',
                        )}>
                          {c.tipo_compra === 'CON_FACTURA' ? 'C/Fact' : 'S/Fact'}
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
