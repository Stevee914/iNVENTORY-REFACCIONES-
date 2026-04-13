import { useEffect, useRef, useState } from 'react';
import { useDebounce } from '@/hooks/useDebounce';
import {
  Plus, X, Save, Search, FileText, AlertTriangle, DollarSign,
  Calendar, ChevronLeft, ChevronRight, CreditCard, CheckCircle, Printer, Download,
  Filter, Eye, Pencil, RefreshCw, Trash2,
} from 'lucide-react';
import { PageHeader, KpiCard } from '@/components/shared';
import { facturaService, type Factura, type Pago } from '@/services/facturaService';
import { VentasDashboard } from '@/components/VentasDashboard';
import { clienteService, type Cliente } from '@/services/clienteService';
import { cn, formatDateTime } from '@/lib/utils';

type TabId = 'documentos' | 'reporte-diario' | 'reporte-mensual' | 'control-cfdi';

const estatusColors: Record<string, string> = {
  PAGADA: 'bg-emerald-50 text-emerald-700',
  CREDITO: 'bg-red-50 text-red-700',
  PARCIAL: 'bg-amber-50 text-amber-700',
};

const tipoColors: Record<string, string> = {
  FACTURA: 'bg-blue-50 text-blue-700',
  NOTA_VENTA: 'bg-surface-100 text-brand-600',
  CREDITO: 'bg-orange-50 text-orange-700',
  REMISION: 'bg-purple-50 text-purple-700',
};

const tipoLabels: Record<string, string> = {
  FACTURA: 'Factura',
  NOTA_VENTA: 'Nota de venta',
  CREDITO: 'Crédito',
  REMISION: 'Remisión',
};

function fmt(n: number) { return n.toLocaleString('es-MX', { minimumFractionDigits: 2, maximumFractionDigits: 2 }); }

export function FacturasPage() {
  const [tab, setTab] = useState<TabId>('documentos');
  const [facturas, setFacturas] = useState<Factura[]>([]);
  const [totalFacturas, setTotalFacturas] = useState(0);
  const [clientes, setClientes] = useState<Cliente[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [page, setPage] = useState(1);
  const [dashboardKey, setDashboardKey] = useState(0);

  // Filtros
  const [filtroEstatus, setFiltroEstatus] = useState('');
  const [filtroTipo, setFiltroTipo] = useState('');
  const [filtroFecha, setFiltroFecha] = useState('');
  const [filtroPendientes, setFiltroPendientes] = useState(false);
  const [filtroQ, setFiltroQ] = useState('');

  // Modal nueva factura
  const [showModal, setShowModal] = useState(false);
  const [folio, setFolio] = useState('');
  const [clienteId, setClienteId] = useState<number | null>(null);
  const [monto, setMonto] = useState<number>(0);
  const [fecha, setFecha] = useState(new Date().toISOString().split('T')[0]);
  const [estatus, setEstatus] = useState('PAGADA');
  const [tipoDocumento, setTipoDocumento] = useState('FACTURA');
  const [condicionPago, setCondicionPago] = useState('CONTADO');
  const [metodoPago, setMetodoPago] = useState('');
  const [notas, setNotas] = useState('');
  const [clienteSearch, setClienteSearch] = useState('');
  const [saving, setSaving] = useState(false);
  const [formError, setFormError] = useState('');

  // Modal pago
  const [showPagoModal, setShowPagoModal] = useState(false);
  const [pagoFactura, setPagoFactura] = useState<Factura | null>(null);
  const [pagoMonto, setPagoMonto] = useState<number>(0);
  const [pagoMetodo, setPagoMetodo] = useState('');
  const [pagoRef, setPagoRef] = useState('');
  const [savingPago, setSavingPago] = useState(false);

  // Modal detalle
  const [showDetalle, setShowDetalle] = useState(false);
  const [detalleDoc, setDetalleDoc] = useState<any>(null);
  const [detallePagos, setDetallePagos] = useState<Pago[]>([]);

  // Modal editar
  const [showEditModal, setShowEditModal] = useState(false);
  const [editFactura, setEditFactura] = useState<Factura | null>(null);
  const [editFolio, setEditFolio] = useState('');
  const [editFecha, setEditFecha] = useState('');
  const [editMonto, setEditMonto] = useState(0);
  const [editTipo, setEditTipo] = useState('');
  const [editEstatus, setEditEstatus] = useState('');
  const [editCondicion, setEditCondicion] = useState('');
  const [editMetodo, setEditMetodo] = useState('');
  const [editNotas, setEditNotas] = useState('');
  const [savingEdit, setSavingEdit] = useState(false);
  const [editError, setEditError] = useState('');

  // Sync modal
  const today = new Date().toISOString().split('T')[0];
  const [showSyncModal, setShowSyncModal] = useState(false);
  const [syncDesde, setSyncDesde] = useState(today);
  const [syncing, setSyncing] = useState(false);
  const [syncToast, setSyncToast] = useState<{ ok: boolean; msg: string } | null>(null);
  const toastTimer = useRef<ReturnType<typeof setTimeout> | null>(null);

  // Reportes
  const [reporteDiario, setReporteDiario] = useState<any>(null);
  const [reporteFecha, setReporteFecha] = useState(new Date().toISOString().split('T')[0]);
  const [reporteMensual, setReporteMensual] = useState<any>(null);
  const [reporteAnio, setReporteAnio] = useState(new Date().getFullYear());
  const [reporteMes, setReporteMes] = useState(new Date().getMonth() + 1);

  // Control CFDI
  const thisMonth = new Date().toISOString().slice(0, 7);
  const [controlFechaInicio, setControlFechaInicio] = useState(`${thisMonth}-01`);
  const [controlFechaFin, setControlFechaFin]       = useState(new Date().toISOString().split('T')[0]);
  const [controlData, setControlData]               = useState<any>(null);
  const [loadingControl, setLoadingControl]         = useState(false);

  async function loadControl() {
    setLoadingControl(true);
    try {
      setControlData(await facturaService.controlCancelados(controlFechaInicio, controlFechaFin));
    } catch (e: any) { alert(e.message); }
    finally { setLoadingControl(false); }
  }

  // Debounce free-text search so the API is only called after the user
  // pauses typing, not on every keystroke.
  const debouncedQ = useDebounce(filtroQ, 400);

  async function loadFacturas() {
    setLoading(true);
    try {
      const res = await facturaService.getAll({
        estatus: filtroEstatus || undefined,
        tipo_documento: filtroTipo || undefined,
        fecha_inicio: filtroFecha || undefined,
        fecha_fin: filtroFecha || undefined,
        solo_pendientes: filtroPendientes || undefined,
        q: debouncedQ || undefined,
        page,
        page_size: 50,
      });
      setFacturas(res.items);
      setTotalFacturas(res.total);
    } catch (e: any) { setError(e.message); }
    finally { setLoading(false); }
  }

  useEffect(() => { loadFacturas(); }, [filtroEstatus, filtroTipo, filtroFecha, filtroPendientes, debouncedQ, page]);
  useEffect(() => { clienteService.getAll().then((r) => setClientes(r.items)).catch(() => {}); }, []);

  const filteredClientes = clienteSearch.length >= 1
    ? clientes.filter((c) => {
        const q = clienteSearch.toLowerCase();
        return c.nombre.toLowerCase().includes(q) || (c.rfc || '').toLowerCase().includes(q);
      }).slice(0, 6)
    : [];

  async function handleCreate() {
    if (!folio.trim()) { setFormError('El folio es obligatorio'); return; }
    if (!clienteId) { setFormError('Selecciona un cliente'); return; }
    if (monto <= 0) { setFormError('El monto debe ser mayor a 0'); return; }
    setSaving(true); setFormError('');
    try {
      await facturaService.create({
        folio: folio.trim().toUpperCase(),
        cliente_id: clienteId,
        monto,
        fecha: fecha || undefined,
        estatus,
        tipo_documento: tipoDocumento,
        condicion_pago: condicionPago,
        metodo_pago: metodoPago || undefined,
        notas: notas || undefined,
      });
      setShowModal(false);
      setFolio(''); setClienteId(null); setMonto(0); setEstatus('PAGADA');
      setTipoDocumento('FACTURA'); setCondicionPago('CONTADO');
      setMetodoPago(''); setNotas(''); setClienteSearch('');
      await loadFacturas();
      setDashboardKey(k => k + 1);
    } catch (e: any) { setFormError(e.message); }
    finally { setSaving(false); }
  }

  function openPago(f: Factura) {
    setPagoFactura(f); setPagoMonto(f.saldo_pendiente); setPagoMetodo(''); setPagoRef(''); setShowPagoModal(true);
  }

  async function handlePago() {
    if (!pagoFactura || pagoMonto <= 0) return;
    setSavingPago(true);
    try {
      await facturaService.createPago(pagoFactura.id, {
        monto: pagoMonto,
        metodo_pago: pagoMetodo || undefined,
        referencia: pagoRef || undefined,
      });
      setShowPagoModal(false);
      await loadFacturas();
      setDashboardKey(k => k + 1);
    } catch (e: any) { alert(e.message); }
    finally { setSavingPago(false); }
  }

  async function handleMarcarPagada(f: Factura) {
    if (!confirm(`¿Marcar ${f.folio} como PAGADA?\nSe registrará pago automático por $${fmt(f.saldo_pendiente)}.`)) return;
    try {
      await facturaService.update(f.id, { estatus: 'PAGADA' });
      await loadFacturas();
      setDashboardKey(k => k + 1);
    } catch (e: any) { alert(e.message); }
  }

  async function openDetalle(f: Factura) {
    try {
      const res = await facturaService.getDetalle(f.id);
      setDetalleDoc(res.documento);
      setDetallePagos(res.pagos);
      setShowDetalle(true);
    } catch (e: any) { alert(e.message); }
  }

  function openEdit(f: Factura) {
    setEditFactura(f);
    setEditFolio(f.folio);
    setEditFecha(f.fecha);
    setEditMonto(f.monto);
    setEditTipo(f.tipo_documento);
    setEditEstatus(f.estatus);
    setEditCondicion(f.condicion_pago);
    setEditMetodo(f.metodo_pago ?? '');
    setEditNotas(f.notas ?? '');
    setEditError('');
    setShowEditModal(true);
  }

  async function handleEdit() {
    if (!editFactura) return;
    if (!editFolio.trim()) { setEditError('El folio es obligatorio'); return; }
    if (!editFecha) { setEditError('La fecha es obligatoria'); return; }
    if (editMonto <= 0) { setEditError('El monto debe ser mayor a 0'); return; }
    setSavingEdit(true); setEditError('');
    try {
      await facturaService.update(editFactura.id, {
        folio: editFolio.trim().toUpperCase(),
        fecha: editFecha,
        monto: editMonto,
        tipo_documento: editTipo,
        estatus: editEstatus,
        condicion_pago: editCondicion,
        metodo_pago: editMetodo || undefined,
        notas: editNotas || undefined,
      });
      setShowEditModal(false);
      await loadFacturas();
      setDashboardKey(k => k + 1);
    } catch (e: any) { setEditError(e.message); }
    finally { setSavingEdit(false); }
  }

  async function handleDelete(f: Factura) {
    if (!confirm(`¿Eliminar ${f.folio} de ${f.cliente_nombre}?\nEsta acción no se puede deshacer.`)) return;
    try {
      await facturaService.delete(f.id);
      await loadFacturas();
      setDashboardKey(k => k + 1);
    } catch (e: any) { alert(e.message); }
  }

  function showToast(ok: boolean, msg: string) {
    if (toastTimer.current) clearTimeout(toastTimer.current);
    setSyncToast({ ok, msg });
    toastTimer.current = setTimeout(() => setSyncToast(null), 6000);
  }

  async function handleSync() {
    setSyncing(true);
    try {
      const res = await facturaService.syncFacturas(syncDesde);
      setShowSyncModal(false);
      const dias = res.dias_procesados;
      const label = dias === 1 ? `${res.fecha_inicio}` : `${res.fecha_inicio} – ${res.fecha_fin} (${dias} días)`;
      showToast(true, `Sincronizado ${label}: ${res.inserted} insertados, ${res.updated} actualizados${res.skipped_no_client > 0 ? `, ${res.skipped_no_client} sin cliente` : ''}${res.errors.length > 0 ? `, ${res.errors.length} error(es)` : ''}.`);
      await loadFacturas();
      setDashboardKey(k => k + 1);
    } catch (e: any) {
      showToast(false, e.message || 'Error al sincronizar');
    } finally {
      setSyncing(false);
    }
  }

  const meses = ['Enero','Febrero','Marzo','Abril','Mayo','Junio','Julio','Agosto','Septiembre','Octubre','Noviembre','Diciembre'];

  // ── Print helpers ──
  function buildReporteHTML(titulo: string, subtitulo: string, kpis: { label: string; value: string }[], tableHTML: string) {
    return `<!DOCTYPE html>
<html><head><meta charset="utf-8"><title>${titulo}</title>
<style>
*{margin:0;padding:0;box-sizing:border-box}
body{font-family:Arial,Helvetica,sans-serif;padding:32px;color:#1a1a1a;font-size:12px}
.header{margin-bottom:20px;padding-bottom:14px;border-bottom:2px solid #222}
.empresa{font-size:15px;font-weight:700;color:#222}
h1{font-size:18px;margin-top:8px}
.sub{color:#666;font-size:12px;margin-top:2px}
.kpis{display:flex;gap:28px;margin:16px 0 20px;padding:12px 16px;background:#f8f9fa;border-radius:6px}
.kpi-label{font-size:9px;color:#888;text-transform:uppercase;font-weight:700;letter-spacing:.5px}
.kpi-value{font-size:18px;font-weight:700;margin-top:2px}
table{width:100%;border-collapse:collapse}
th{text-align:left;padding:8px 10px;font-size:10px;font-weight:700;color:#555;text-transform:uppercase;letter-spacing:.3px;border-bottom:2px solid #333}
th.r{text-align:right}
td{padding:7px 10px;border-bottom:1px solid #eee;font-size:12px}
td.r{text-align:right;font-variant-numeric:tabular-nums}
td.mono{font-family:'Courier New',monospace}
.total-row td{font-weight:700;border-top:2px solid #333;border-bottom:none;font-size:13px;padding-top:10px}
.badge{display:inline-block;padding:2px 8px;border-radius:4px;font-size:10px;font-weight:600}
.b-pagada{background:#ecfdf5;color:#047857}.b-credito{background:#fef2f2;color:#b91c1c}.b-parcial{background:#fffbeb;color:#b45309}
.footer{margin-top:32px;padding-top:10px;border-top:1px solid #ddd;font-size:9px;color:#aaa;text-align:center}
@media print{body{padding:16px}.kpis{background:#f8f9fa!important;-webkit-print-color-adjust:exact;print-color-adjust:exact}.badge{-webkit-print-color-adjust:exact;print-color-adjust:exact}}
</style></head><body>
<div class="header"><div class="empresa">Refacciones y Llantas Jaime S.A. de C.V.</div><h1>${titulo}</h1><div class="sub">${subtitulo}</div></div>
<div class="kpis">${kpis.map(k => `<div><div class="kpi-label">${k.label}</div><div class="kpi-value">${k.value}</div></div>`).join('')}</div>
${tableHTML}
<div class="footer">Generado el ${new Date().toLocaleString('es-MX')} — Refacciones y Llantas Jaime</div>
</body></html>`;
  }

  function badgeHTML(estatus: string) {
    const cls = estatus === 'PAGADA' ? 'b-pagada' : estatus === 'CREDITO' ? 'b-credito' : 'b-parcial';
    return `<span class="badge ${cls}">${estatus}</span>`;
  }

  function buildDiarioHTML() {
    if (!reporteDiario) return '';
    const rows = reporteDiario.facturas.map((f: any) =>
      `<tr><td class="mono">${f.folio}</td><td>${f.tipo_documento || ''}</td><td>${f.cliente}</td><td class="r">$${fmt(f.monto)}</td><td>${badgeHTML(f.estatus)}</td></tr>`
    ).join('');
    const totalRow = `<tr class="total-row"><td colspan="3">Total</td><td class="r">$${fmt(reporteDiario.total_dia)}</td><td></td></tr>`;
    const table = `<table><thead><tr><th>Folio</th><th>Tipo</th><th>Cliente</th><th class="r">Monto</th><th>Estatus</th></tr></thead><tbody>${rows}${totalRow}</tbody></table>`;
    return buildReporteHTML('Reporte Diario de Ventas', `Fecha: ${reporteFecha}`,
      [{ label: 'Documentos', value: String(reporteDiario.total_facturas) }, { label: 'Folios', value: reporteDiario.rango_folios }, { label: 'Total del día', value: `$${fmt(reporteDiario.total_dia)}` }], table);
  }

  function buildMensualHTML() {
    if (!reporteMensual) return '';
    const rows = reporteMensual.dias.map((d: any) =>
      `<tr><td>${d.fecha}</td><td class="mono">${d.folio_inicio} — ${d.folio_fin}</td><td class="r">${d.num_facturas}</td><td class="r">$${fmt(d.total_dia)}</td></tr>`
    ).join('');
    const totalRow = `<tr class="total-row"><td colspan="2">Total</td><td class="r">${reporteMensual.total_facturas}</td><td class="r">$${fmt(reporteMensual.gran_total)}</td></tr>`;
    const table = `<table><thead><tr><th>Fecha</th><th>Folios</th><th class="r"># Docs</th><th class="r">Total del día</th></tr></thead><tbody>${rows}${totalRow}</tbody></table>`;
    return buildReporteHTML('Reporte Mensual de Ventas', `${meses[reporteMes - 1]} ${reporteAnio}`,
      [{ label: 'Días con ventas', value: String(reporteMensual.total_dias_con_ventas) }, { label: 'Total docs', value: String(reporteMensual.total_facturas) }, { label: 'Gran total', value: `$${fmt(reporteMensual.gran_total)}` }], table);
  }

  function handlePrint(tipo: 'diario' | 'mensual') {
    const html = tipo === 'diario' ? buildDiarioHTML() : buildMensualHTML();
    if (!html) return;
    const win = window.open('', '_blank');
    if (!win) return;
    win.document.write(html); win.document.close();
    setTimeout(() => win.print(), 400);
  }

  function handleDownloadPDF(tipo: 'diario' | 'mensual') {
    const html = tipo === 'diario' ? buildDiarioHTML() : buildMensualHTML();
    if (!html) return;
    const win = window.open('', '_blank');
    if (!win) return;
    win.document.write(html); win.document.close();
    setTimeout(() => win.print(), 400);
  }

  async function loadReporteDiario() {
    try { const r = await facturaService.reporteDiario(reporteFecha); setReporteDiario(r); }
    catch { setReporteDiario(null); }
  }

  async function loadReporteMensual() {
    try { const r = await facturaService.reporteMensual(reporteAnio, reporteMes); setReporteMensual(r); }
    catch { setReporteMensual(null); }
  }

  useEffect(() => { if (tab === 'reporte-diario') loadReporteDiario(); }, [tab, reporteFecha]);
  useEffect(() => { if (tab === 'reporte-mensual') loadReporteMensual(); }, [tab, reporteAnio, reporteMes]);
  useEffect(() => { if (tab === 'control-cfdi') loadControl(); }, [tab]);

  return (
    <div>
      <PageHeader
        title="Ventas y Cobranza"
        description="Facturas, notas de venta, créditos y cuentas por cobrar"
        actions={
          <div className="flex items-center gap-2">
            <button
              onClick={() => { setSyncDesde(new Date().toISOString().split('T')[0]); setShowSyncModal(true); }}
              className="btn-secondary flex items-center gap-1.5"
            >
              <RefreshCw className="w-4 h-4" /> Sincronizar
            </button>
            <button onClick={() => setShowModal(true)} className="btn-primary"><Plus className="w-4 h-4" /> Nuevo Documento</button>
          </div>
        }
      />

      {/* Dashboard de ventas y cobranza */}
      <VentasDashboard refreshKey={dashboardKey} />

      {/* Separator */}
      <div className="flex items-center gap-3 mb-4">
        <div className="flex-1 h-px bg-surface-200" />
        <span className="text-[11px] font-semibold text-brand-300 uppercase tracking-wider">Registros</span>
        <div className="flex-1 h-px bg-surface-200" />
      </div>

      {/* Tabs */}
      <div className="flex items-center gap-1 mb-6 border-b border-surface-200">
        {([
          { id: 'documentos' as TabId,    label: 'Documentos' },
          { id: 'reporte-diario' as TabId, label: 'Reporte Diario' },
          { id: 'reporte-mensual' as TabId, label: 'Reporte Mensual' },
          { id: 'control-cfdi' as TabId,  label: 'Control CFDI' },
        ]).map((t) => (
          <button key={t.id} onClick={() => setTab(t.id)}
            className={`px-4 py-2.5 text-[13px] font-medium border-b-2 transition-colors ${
              tab === t.id ? 'border-sap-blue text-sap-blue' : 'border-transparent text-brand-400 hover:text-brand-700'
            }`}>{t.label}</button>
        ))}
      </div>

      {/* ─── TAB: DOCUMENTOS ──────────────────────────── */}
      {tab === 'documentos' && (
        <>
          {/* Filtros */}
          <div className="card px-5 py-4 mb-4">
            <div className="flex flex-col sm:flex-row gap-3 items-start sm:items-center flex-wrap">
              <div className="relative">
                <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-3.5 h-3.5 text-brand-300" />
                <input value={filtroQ} onChange={(e) => { setFiltroQ(e.target.value); setPage(1); }}
                  placeholder="Buscar folio o cliente..." className="input-field w-52 py-2 pl-9 text-xs" />
              </div>
              <input type="date" value={filtroFecha} onChange={(e) => { setFiltroFecha(e.target.value); setPage(1); }} className="input-field w-40 py-2 text-xs" />
              <select value={filtroTipo} onChange={(e) => { setFiltroTipo(e.target.value); setPage(1); }} className="select-field w-36 py-2 text-xs">
                <option value="">Todos los tipos</option>
                <option value="FACTURA">Factura</option>
                <option value="NOTA_VENTA">Nota de venta</option>
                <option value="CREDITO">Crédito</option>
                <option value="REMISION">Remisión</option>
              </select>
              <select value={filtroEstatus} onChange={(e) => { setFiltroEstatus(e.target.value); setPage(1); }} className="select-field w-32 py-2 text-xs">
                <option value="">Todos</option>
                <option value="PAGADA">Pagadas</option>
                <option value="CREDITO">A crédito</option>
                <option value="PARCIAL">Parcial</option>
              </select>
              <label className="flex items-center gap-1.5 text-[12px] text-brand-500 cursor-pointer select-none">
                <input type="checkbox" checked={filtroPendientes} onChange={(e) => { setFiltroPendientes(e.target.checked); setPage(1); }}
                  className="rounded border-surface-300 text-sap-blue focus:ring-sap-blue" />
                Solo con saldo
              </label>
              {(filtroFecha || filtroTipo || filtroEstatus || filtroPendientes || filtroQ) && (
                <button onClick={() => { setFiltroFecha(''); setFiltroTipo(''); setFiltroEstatus(''); setFiltroPendientes(false); setFiltroQ(''); }}
                  className="btn-ghost text-xs">Limpiar</button>
              )}
              <span className="text-[11px] text-brand-400 ml-auto">{totalFacturas} documentos</span>
            </div>
          </div>

          {/* Tabla */}
          <div className="card overflow-hidden">
            <div className="overflow-x-auto">
              <table className="w-full">
                <thead>
                  <tr className="border-b border-surface-200">
                    <th className="table-header">Folio</th>
                    <th className="table-header">Tipo</th>
                    <th className="table-header">Cliente</th>
                    <th className="table-header">Fecha</th>
                    <th className="table-header text-right">Monto</th>
                    <th className="table-header text-right">Pagado</th>
                    <th className="table-header text-right">Saldo</th>
                    <th className="table-header">Estatus</th>
                    <th className="table-header w-28"></th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-surface-100">
                  {loading ? (
                    <tr><td colSpan={9} className="px-4 py-12 text-center">
                      <div className="w-5 h-5 border-2 border-surface-300 border-t-sap-blue rounded-full animate-spin mx-auto" />
                    </td></tr>
                  ) : facturas.length === 0 ? (
                    <tr><td colSpan={9} className="px-4 py-12 text-center text-[13px] text-brand-400">No hay documentos registrados</td></tr>
                  ) : facturas.map((f) => (
                    <tr key={f.id} className="hover:bg-surface-50 transition-colors">
                      <td className="table-cell font-mono text-[12px] font-medium text-brand-600">{f.folio}</td>
                      <td className="table-cell">
                        <span className={cn('badge text-[10px]', tipoColors[f.tipo_documento] || 'bg-surface-100 text-brand-500')}>
                          {tipoLabels[f.tipo_documento] || f.tipo_documento}
                        </span>
                      </td>
                      <td className="table-cell">
                        <p className="text-[13px] text-brand-800">{f.cliente_nombre}</p>
                        {f.cliente_rfc && <p className="text-[11px] text-brand-400 font-mono">{f.cliente_rfc}</p>}
                      </td>
                      <td className="table-cell text-[12px] text-brand-500 whitespace-nowrap">{f.fecha}</td>
                      <td className="table-cell text-right tabular-nums text-[13px] font-medium text-brand-800">${fmt(f.monto)}</td>
                      <td className="table-cell text-right tabular-nums text-[12px] text-brand-500">${fmt(f.total_pagado)}</td>
                      <td className="table-cell text-right tabular-nums text-[13px] font-medium">
                        <span className={f.saldo_pendiente > 0 ? 'text-status-critical' : 'text-status-ok'}>
                          ${fmt(f.saldo_pendiente)}
                        </span>
                      </td>
                      <td className="table-cell">
                        <span className={cn('badge text-[10px]', estatusColors[f.estatus] || 'bg-surface-100 text-brand-500')}>{f.estatus}</span>
                      </td>
                      <td className="table-cell">
                        <div className="flex items-center gap-0.5">
                          <button onClick={() => openDetalle(f)} className="btn-ghost p-1.5 text-brand-400 hover:text-brand-700" title="Ver detalle">
                            <Eye className="w-3.5 h-3.5" />
                          </button>
                          <button onClick={() => openEdit(f)} className="btn-ghost p-1.5 text-brand-400 hover:text-brand-700" title="Editar">
                            <Pencil className="w-3.5 h-3.5" />
                          </button>
                          <button onClick={() => handleDelete(f)} className="btn-ghost p-1.5 text-brand-300 hover:text-red-600" title="Eliminar">
                            <Trash2 className="w-3.5 h-3.5" />
                          </button>
                          {(f.estatus === 'CREDITO' || f.estatus === 'PARCIAL') && f.saldo_pendiente > 0 && (
                            <>
                              <button onClick={() => openPago(f)} className="btn-ghost p-1.5 text-status-ok hover:text-emerald-800" title="Registrar abono">
                                <DollarSign className="w-3.5 h-3.5" />
                              </button>
                              <button onClick={() => handleMarcarPagada(f)} className="btn-ghost p-1.5 text-brand-400 hover:text-emerald-700" title="Marcar como pagada">
                                <CheckCircle className="w-3.5 h-3.5" />
                              </button>
                            </>
                          )}
                        </div>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        </>
      )}

      {/* ─── TAB: REPORTE DIARIO ────────────────────────── */}
      {tab === 'reporte-diario' && (
        <div>
          <div className="card px-5 py-4 mb-4">
            <div className="flex items-center gap-3">
              <Calendar className="w-4 h-4 text-brand-400" />
              <input type="date" value={reporteFecha} onChange={(e) => setReporteFecha(e.target.value)} className="input-field w-44 py-2 text-xs" />
              {reporteDiario && (
                <div className="flex items-center gap-2 ml-auto">
                  <button onClick={() => handlePrint('diario')} className="btn-secondary text-xs py-1.5 px-3 flex items-center gap-1.5">
                    <Printer className="w-3.5 h-3.5" /> Imprimir
                  </button>
                  <button onClick={() => handleDownloadPDF('diario')} className="btn-secondary text-xs py-1.5 px-3 flex items-center gap-1.5">
                    <Download className="w-3.5 h-3.5" /> PDF
                  </button>
                </div>
              )}
            </div>
          </div>
          {reporteDiario && (
            <>
              <div className="grid grid-cols-1 sm:grid-cols-3 gap-4 mb-5">
                <div className="card p-4">
                  <p className="text-[11px] font-semibold text-brand-400 uppercase">Documentos del día</p>
                  <p className="text-[22px] font-bold text-brand-800 mt-1">{reporteDiario.total_facturas}</p>
                </div>
                <div className="card p-4">
                  <p className="text-[11px] font-semibold text-brand-400 uppercase">Rango de folios</p>
                  <p className="text-[16px] font-bold text-brand-800 mt-1 font-mono">{reporteDiario.rango_folios}</p>
                </div>
                <div className="card p-4">
                  <p className="text-[11px] font-semibold text-brand-400 uppercase">Total del día</p>
                  <p className="text-[22px] font-bold text-brand-800 mt-1">${fmt(reporteDiario.total_dia)}</p>
                </div>
              </div>
              <div className="card overflow-hidden">
                <table className="w-full">
                  <thead>
                    <tr className="border-b border-surface-200">
                      <th className="table-header">Folio</th>
                      <th className="table-header">Tipo</th>
                      <th className="table-header">Cliente</th>
                      <th className="table-header text-right">Monto</th>
                      <th className="table-header">Estatus</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-surface-100">
                    {reporteDiario.facturas.map((f: any, i: number) => (
                      <tr key={i} className="hover:bg-surface-50">
                        <td className="table-cell font-mono text-[12px] font-medium text-brand-600">{f.folio}</td>
                        <td className="table-cell">
                          <span className={cn('badge text-[10px]', tipoColors[f.tipo_documento] || 'bg-surface-100 text-brand-500')}>
                            {tipoLabels[f.tipo_documento] || f.tipo_documento}
                          </span>
                        </td>
                        <td className="table-cell text-[13px] text-brand-800">{f.cliente}</td>
                        <td className="table-cell text-right tabular-nums text-[13px] font-medium">${fmt(f.monto)}</td>
                        <td className="table-cell"><span className={cn('badge text-[10px]', estatusColors[f.estatus])}>{f.estatus}</span></td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </>
          )}
        </div>
      )}

      {/* ─── TAB: REPORTE MENSUAL ───────────────────────── */}
      {tab === 'reporte-mensual' && (
        <div>
          <div className="card px-5 py-4 mb-4">
            <div className="flex items-center gap-3">
              <select value={reporteMes} onChange={(e) => setReporteMes(Number(e.target.value))} className="select-field w-36 py-2 text-xs">
                {meses.map((m, i) => (<option key={i} value={i + 1}>{m}</option>))}
              </select>
              <input type="number" value={reporteAnio} onChange={(e) => setReporteAnio(Number(e.target.value))} className="input-field w-24 py-2 text-xs tabular-nums" />
              {reporteMensual && (
                <div className="flex items-center gap-2 ml-auto">
                  <button onClick={() => handlePrint('mensual')} className="btn-secondary text-xs py-1.5 px-3 flex items-center gap-1.5">
                    <Printer className="w-3.5 h-3.5" /> Imprimir
                  </button>
                  <button onClick={() => handleDownloadPDF('mensual')} className="btn-secondary text-xs py-1.5 px-3 flex items-center gap-1.5">
                    <Download className="w-3.5 h-3.5" /> PDF
                  </button>
                </div>
              )}
            </div>
          </div>
          {reporteMensual && (
            <>
              <div className="grid grid-cols-1 sm:grid-cols-3 gap-4 mb-5">
                <div className="card p-4">
                  <p className="text-[11px] font-semibold text-brand-400 uppercase">Días con ventas</p>
                  <p className="text-[22px] font-bold text-brand-800 mt-1">{reporteMensual.total_dias_con_ventas}</p>
                </div>
                <div className="card p-4">
                  <p className="text-[11px] font-semibold text-brand-400 uppercase">Total documentos</p>
                  <p className="text-[22px] font-bold text-brand-800 mt-1">{reporteMensual.total_facturas}</p>
                </div>
                <div className="card p-4">
                  <p className="text-[11px] font-semibold text-brand-400 uppercase">Gran total del mes</p>
                  <p className="text-[22px] font-bold text-brand-800 mt-1">${fmt(reporteMensual.gran_total)}</p>
                </div>
              </div>
              <div className="card overflow-hidden">
                <table className="w-full">
                  <thead>
                    <tr className="border-b border-surface-200">
                      <th className="table-header">Fecha</th>
                      <th className="table-header">Folios</th>
                      <th className="table-header text-right"># Docs</th>
                      <th className="table-header text-right">Total del día</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-surface-100">
                    {reporteMensual.dias.map((d: any, i: number) => (
                      <tr key={i} className="hover:bg-surface-50">
                        <td className="table-cell text-[13px] text-brand-800 whitespace-nowrap">{d.fecha}</td>
                        <td className="table-cell font-mono text-[12px] text-brand-500">{d.folio_inicio} — {d.folio_fin}</td>
                        <td className="table-cell text-right tabular-nums text-[13px] text-brand-500">{d.num_facturas}</td>
                        <td className="table-cell text-right tabular-nums text-[13px] font-medium text-brand-800">${fmt(d.total_dia)}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </>
          )}
        </div>
      )}

      {/* ─── TOAST ────────────────────────────────────── */}
      {syncToast && (
        <div className={`fixed bottom-5 left-1/2 -translate-x-1/2 z-[60] flex items-center gap-3 px-4 py-3 rounded-lg shadow-lg text-[13px] font-medium text-white transition-all ${syncToast.ok ? 'bg-emerald-600' : 'bg-red-600'}`}>
          {syncToast.ok ? <CheckCircle className="w-4 h-4 shrink-0" /> : <AlertTriangle className="w-4 h-4 shrink-0" />}
          <span>{syncToast.msg}</span>
          <button onClick={() => setSyncToast(null)} className="ml-2 opacity-70 hover:opacity-100"><X className="w-3.5 h-3.5" /></button>
        </div>
      )}

      {/* ─── TAB: CONTROL CFDI ───────────────────────── */}
      {tab === 'control-cfdi' && (
        <div>
          {/* Filters */}
          <div className="card px-5 py-4 mb-4">
            <div className="flex flex-wrap items-end gap-3">
              <div>
                <label className="block text-[10px] font-semibold text-brand-400 uppercase mb-1">Desde</label>
                <input type="date" value={controlFechaInicio}
                  onChange={(e) => setControlFechaInicio(e.target.value)}
                  className="input-field w-40 py-2 text-xs" />
              </div>
              <div>
                <label className="block text-[10px] font-semibold text-brand-400 uppercase mb-1">Hasta</label>
                <input type="date" value={controlFechaFin}
                  onChange={(e) => setControlFechaFin(e.target.value)}
                  className="input-field w-40 py-2 text-xs" />
              </div>
              <button onClick={loadControl} disabled={loadingControl}
                className="btn-secondary text-xs py-2 px-4 flex items-center gap-1.5">
                <Search className="w-3.5 h-3.5" />
                {loadingControl ? 'Consultando...' : 'Consultar'}
              </button>
              {controlData && (
                <div className="ml-auto flex items-center gap-4 text-[11px] text-brand-500">
                  <span><span className="font-semibold text-red-600">{controlData.total_cancelados}</span> cancelados</span>
                  <span><span className="font-semibold text-red-600">${controlData.total_monto_cancelado?.toLocaleString('es-MX', { minimumFractionDigits: 2 })}</span> monto total</span>
                </div>
              )}
            </div>
          </div>

          {/* Table */}
          {controlData && (
            <div className="card overflow-hidden">
              <div className="overflow-x-auto">
                <table className="w-full">
                  <thead>
                    <tr className="border-b border-surface-200">
                      <th className="table-header">Fecha</th>
                      <th className="table-header">Folio cancelado</th>
                      <th className="table-header">Cliente</th>
                      <th className="table-header text-right">Monto</th>
                      <th className="table-header">UUID (cancelado)</th>
                      <th className="table-header">
                        <div className="flex flex-col gap-0.5">
                          <span>Posible sustitución</span>
                          <span className="text-[9px] font-normal text-brand-400 normal-case">
                            mismo cliente · monto similar · fecha cercana
                          </span>
                        </div>
                      </th>
                      <th className="table-header">En sistema</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-surface-100">
                    {controlData.cancelados.length === 0 ? (
                      <tr>
                        <td colSpan={7} className="table-cell text-center text-[12px] text-brand-400 py-8">
                          No hay CFDIs cancelados en el período seleccionado
                        </td>
                      </tr>
                    ) : controlData.cancelados.map((row: any) => (
                      <tr key={row.pos_cfd_id} className="hover:bg-surface-50">
                        <td className="table-cell text-[12px] text-brand-500 whitespace-nowrap">{row.fecha}</td>
                        <td className="table-cell font-mono text-[12px] font-medium text-red-600">{row.folio}</td>
                        <td className="table-cell text-[12px] text-brand-700">{row.cliente}</td>
                        <td className="table-cell text-right tabular-nums text-[13px] font-medium text-red-600">
                          ${Number(row.monto).toLocaleString('es-MX', { minimumFractionDigits: 2 })}
                        </td>
                        <td className="table-cell font-mono text-[10px] text-brand-400">{(row.uuid || '').slice(0, 18)}…</td>
                        <td className="table-cell">
                          {row.reemplazo ? (
                            <div className="flex flex-col gap-0.5">
                              <div>
                                <span className="font-mono text-[12px] font-medium text-amber-700">{row.reemplazo.folio}</span>
                                <span className="text-[10px] text-brand-400 ml-1">({row.reemplazo.fecha})</span>
                              </div>
                              <span className="text-[9px] text-brand-400 italic">coincidencia heurística · no confirmado</span>
                            </div>
                          ) : (
                            <span className="text-[11px] text-brand-400">Sin coincidencia</span>
                          )}
                        </td>
                        <td className="table-cell">
                          {row.en_sistema ? (
                            <span className="badge text-[10px] bg-red-50 text-red-700">Stale en BD</span>
                          ) : (
                            <span className="badge text-[10px] bg-emerald-50 text-emerald-700">Excluido</span>
                          )}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          )}
        </div>
      )}

      {/* ─── MODAL: SINCRONIZAR ───────────────────────── */}
      {showSyncModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-brand-950/40 backdrop-blur-sm">
          <div className="card p-6 w-full max-w-xs mx-4 shadow-modal">
            <div className="flex items-center justify-between mb-4">
              <h2 className="text-[15px] font-semibold text-brand-800">Sincronizar ventas</h2>
              <button onClick={() => setShowSyncModal(false)} disabled={syncing} className="btn-ghost p-1.5"><X className="w-4 h-4" /></button>
            </div>
            <label className="block text-[11px] font-semibold text-brand-500 uppercase tracking-wide mb-1.5">Desde</label>
            <input
              type="date"
              value={syncDesde}
              onChange={(e) => setSyncDesde(e.target.value)}
              disabled={syncing}
              className="input-field w-full mb-2"
            />
            <p className="text-[11px] text-brand-400 mb-5">
              Se sincronizarán las facturas desde la fecha seleccionada hasta hoy.
            </p>
            <div className="flex justify-end gap-2">
              <button onClick={() => setShowSyncModal(false)} disabled={syncing} className="btn-secondary">Cancelar</button>
              <button onClick={handleSync} disabled={syncing || !syncDesde} className="btn-primary flex items-center gap-1.5">
                {syncing ? <div className="w-4 h-4 border-2 border-white/40 border-t-white rounded-full animate-spin" /> : <RefreshCw className="w-4 h-4" />}
                {syncing ? 'Sincronizando…' : 'Sincronizar'}
              </button>
            </div>
          </div>
        </div>
      )}

      {/* ─── MODAL: NUEVO DOCUMENTO ───────────────────── */}
      {showModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-brand-950/40 backdrop-blur-sm">
          <div className="card p-6 w-full max-w-lg mx-4 shadow-modal max-h-[90vh] overflow-y-auto">
            <div className="flex items-center justify-between mb-4">
              <div className="flex items-center gap-2">
                <FileText className="w-5 h-5 text-brand-500" />
                <h2 className="text-[13px] font-semibold text-brand-800">Nuevo Documento</h2>
              </div>
              <button onClick={() => setShowModal(false)} className="btn-ghost p-1"><X className="w-4 h-4" /></button>
            </div>

            {formError && <div className="p-3 rounded-lg bg-status-critical-muted border border-red-200 text-[12px] text-red-700 mb-4">{formError}</div>}

            <div className="space-y-4">
              {/* Tipo de documento */}
              <div>
                <label className="label">Tipo de documento</label>
                <div className="grid grid-cols-2 sm:grid-cols-4 gap-2">
                  {([
                    { val: 'FACTURA', label: 'Factura', color: 'blue' },
                    { val: 'NOTA_VENTA', label: 'Nota venta', color: 'gray' },
                    { val: 'CREDITO', label: 'Crédito', color: 'orange' },
                    { val: 'REMISION', label: 'Remisión', color: 'purple' },
                  ] as const).map((t) => (
                    <button key={t.val} type="button" onClick={() => {
                      setTipoDocumento(t.val);
                      if (t.val === 'CREDITO') { setEstatus('CREDITO'); setCondicionPago('CREDITO_30'); }
                      else if (t.val === 'NOTA_VENTA') { setEstatus('PAGADA'); setCondicionPago('CONTADO'); }
                    }}
                      className={`px-2 py-2 text-[11px] font-semibold rounded-lg border-2 transition-all text-center ${
                        tipoDocumento === t.val
                          ? `bg-${t.color}-50 border-${t.color}-300 text-${t.color}-800`
                          : 'border-surface-200 text-brand-400 bg-white'
                      }`}>
                      {t.label}
                    </button>
                  ))}
                </div>
              </div>

              <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                <div>
                  <label className="label">Folio *</label>
                  <input value={folio} onChange={(e) => setFolio(e.target.value.toUpperCase())} placeholder="9876" className="input-field font-mono" />
                </div>
                <div>
                  <label className="label">Fecha</label>
                  <input type="date" value={fecha} onChange={(e) => setFecha(e.target.value)} className="input-field" />
                </div>
              </div>

              {/* Cliente selector */}
              <div>
                <label className="label">Cliente *</label>
                {clienteId ? (
                  <div className="flex items-center justify-between p-3 rounded-lg bg-surface-50 border border-surface-200">
                    <p className="text-[13px] font-medium text-brand-800">{clientes.find((c) => c.id === clienteId)?.nombre}</p>
                    <button type="button" onClick={() => { setClienteId(null); setClienteSearch(''); }} className="text-brand-400 hover:text-brand-600"><X className="w-4 h-4" /></button>
                  </div>
                ) : (
                  <div className="relative">
                    <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-brand-300" />
                    <input value={clienteSearch} onChange={(e) => setClienteSearch(e.target.value)} placeholder="Buscar cliente por nombre o RFC..." className="input-field pl-10" />
                    {filteredClientes.length > 0 && (
                      <div className="absolute z-10 w-full mt-1 bg-white border border-surface-200 rounded-lg shadow-lg max-h-48 overflow-y-auto">
                        {filteredClientes.map((c) => (
                          <button key={c.id} type="button" onClick={() => { setClienteId(c.id); setClienteSearch(''); }}
                            className="w-full text-left px-3 py-2.5 hover:bg-surface-50 border-b border-surface-100 last:border-0">
                            <p className="text-[13px] font-medium text-brand-800">{c.nombre}</p>
                            {c.rfc && <p className="text-[11px] text-brand-400 font-mono">{c.rfc}</p>}
                          </button>
                        ))}
                      </div>
                    )}
                  </div>
                )}
              </div>

              <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                <div>
                  <label className="label">Monto *</label>
                  <div className="relative">
                    <span className="absolute left-3 top-1/2 -translate-y-1/2 text-sm text-brand-400">$</span>
                    <input type="number" value={monto || ''} onChange={(e) => setMonto(parseFloat(e.target.value) || 0)} min={0} step={0.01} className="input-field pl-7 tabular-nums text-lg font-bold" />
                  </div>
                </div>
                <div>
                  <label className="label">Estatus</label>
                  <div className="flex gap-2">
                    <button type="button" onClick={() => setEstatus('PAGADA')}
                      className={`flex-1 px-3 py-2.5 text-xs font-semibold rounded-lg border-2 transition-all ${estatus === 'PAGADA' ? 'bg-emerald-50 border-emerald-300 text-emerald-800' : 'border-surface-200 text-brand-400 bg-white'}`}>
                      Pagada
                    </button>
                    <button type="button" onClick={() => setEstatus('CREDITO')}
                      className={`flex-1 px-3 py-2.5 text-xs font-semibold rounded-lg border-2 transition-all ${estatus === 'CREDITO' ? 'bg-red-50 border-red-300 text-red-800' : 'border-surface-200 text-brand-400 bg-white'}`}>
                      Crédito
                    </button>
                  </div>
                </div>
              </div>

              <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                <div>
                  <label className="label">Condición de pago</label>
                  <select value={condicionPago} onChange={(e) => setCondicionPago(e.target.value)} className="select-field">
                    <option value="CONTADO">Contado</option>
                    <option value="CREDITO_15">Crédito 15 días</option>
                    <option value="CREDITO_30">Crédito 30 días</option>
                    <option value="CREDITO_60">Crédito 60 días</option>
                  </select>
                </div>
                <div>
                  <label className="label">Método de pago</label>
                  <select value={metodoPago} onChange={(e) => setMetodoPago(e.target.value)} className="select-field">
                    <option value="">—</option>
                    <option value="EFECTIVO">Efectivo</option>
                    <option value="TRANSFERENCIA">Transferencia</option>
                    <option value="CHEQUE">Cheque</option>
                    <option value="TARJETA">Tarjeta</option>
                    <option value="MIXTO">Mixto</option>
                  </select>
                </div>
              </div>

              <div>
                <label className="label">Notas</label>
                <input value={notas} onChange={(e) => setNotas(e.target.value)} placeholder="Observaciones..." className="input-field" />
              </div>
            </div>

            <div className="flex items-center justify-end gap-3 mt-6 pt-4 border-t border-surface-200">
              <button onClick={() => setShowModal(false)} className="btn-secondary">Cancelar</button>
              <button onClick={handleCreate} disabled={saving} className="btn-primary">
                <Save className="w-4 h-4" /> {saving ? 'Guardando...' : 'Registrar'}
              </button>
            </div>
          </div>
        </div>
      )}

      {/* ─── MODAL: REGISTRAR PAGO ──────────────────── */}
      {showPagoModal && pagoFactura && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-brand-950/40 backdrop-blur-sm">
          <div className="card p-6 w-full max-w-sm mx-4 shadow-modal">
            <div className="flex items-center justify-between mb-4">
              <div className="flex items-center gap-2">
                <DollarSign className="w-5 h-5 text-status-ok" />
                <h2 className="text-[13px] font-semibold text-brand-800">Registrar Pago</h2>
              </div>
              <button onClick={() => setShowPagoModal(false)} className="btn-ghost p-1"><X className="w-4 h-4" /></button>
            </div>

            <div className="p-3 rounded-lg bg-surface-50 border border-surface-200 mb-4">
              <p className="text-[12px] text-brand-400">{tipoLabels[pagoFactura.tipo_documento] || 'Documento'} <span className="font-mono font-medium">{pagoFactura.folio}</span></p>
              <p className="text-[13px] font-medium text-brand-800">{pagoFactura.cliente_nombre}</p>
              <div className="flex justify-between mt-2 text-[12px]">
                <span className="text-brand-400">Monto: ${fmt(pagoFactura.monto)}</span>
                <span className="text-status-critical font-medium">Saldo: ${fmt(pagoFactura.saldo_pendiente)}</span>
              </div>
            </div>

            <div className="space-y-3">
              <div>
                <label className="label">Monto del pago *</label>
                <div className="relative">
                  <span className="absolute left-3 top-1/2 -translate-y-1/2 text-sm text-brand-400">$</span>
                  <input type="number" value={pagoMonto || ''} onChange={(e) => setPagoMonto(parseFloat(e.target.value) || 0)}
                    min={0} max={pagoFactura.saldo_pendiente} step={0.01} className="input-field pl-7 tabular-nums text-lg font-bold" />
                </div>
              </div>
              <div>
                <label className="label">Método de pago</label>
                <select value={pagoMetodo} onChange={(e) => setPagoMetodo(e.target.value)} className="select-field">
                  <option value="">—</option>
                  <option value="EFECTIVO">Efectivo</option>
                  <option value="TRANSFERENCIA">Transferencia</option>
                  <option value="CHEQUE">Cheque</option>
                </select>
              </div>
              <div>
                <label className="label">Referencia</label>
                <input value={pagoRef} onChange={(e) => setPagoRef(e.target.value)} placeholder="# transferencia, # cheque..." className="input-field" />
              </div>
            </div>

            <div className="flex items-center justify-end gap-3 mt-6 pt-4 border-t border-surface-200">
              <button onClick={() => setShowPagoModal(false)} className="btn-secondary">Cancelar</button>
              <button onClick={handlePago} disabled={savingPago} className="btn-primary">
                <DollarSign className="w-4 h-4" /> {savingPago ? 'Registrando...' : 'Registrar Pago'}
              </button>
            </div>
          </div>
        </div>
      )}

      {/* ─── MODAL: DETALLE DOCUMENTO ──────────────────── */}
      {showDetalle && detalleDoc && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-brand-950/40 backdrop-blur-sm">
          <div className="card p-6 w-full max-w-lg mx-4 shadow-modal max-h-[85vh] overflow-y-auto">
            <div className="flex items-center justify-between mb-4">
              <div className="flex items-center gap-2">
                <FileText className="w-5 h-5 text-brand-500" />
                <h2 className="text-[13px] font-semibold text-brand-800">Detalle del Documento</h2>
              </div>
              <button onClick={() => setShowDetalle(false)} className="btn-ghost p-1"><X className="w-4 h-4" /></button>
            </div>

            {/* Info principal */}
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-x-6 gap-y-2 text-[12px] mb-4">
              <div><span className="text-brand-400">Folio:</span> <span className="font-mono font-medium">{detalleDoc.folio}</span></div>
              <div><span className="text-brand-400">Tipo:</span> <span className={cn('badge text-[10px] ml-1', tipoColors[detalleDoc.tipo_documento])}>{tipoLabels[detalleDoc.tipo_documento]}</span></div>
              <div><span className="text-brand-400">Fecha:</span> {detalleDoc.fecha}</div>
              <div><span className="text-brand-400">Estatus:</span> <span className={cn('badge text-[10px] ml-1', estatusColors[detalleDoc.estatus])}>{detalleDoc.estatus}</span></div>
              <div><span className="text-brand-400">Condición:</span> {detalleDoc.condicion_pago}</div>
              {detalleDoc.fecha_vencimiento && <div><span className="text-brand-400">Vencimiento:</span> {detalleDoc.fecha_vencimiento}</div>}
              {detalleDoc.metodo_pago && <div><span className="text-brand-400">Método:</span> {detalleDoc.metodo_pago}</div>}
            </div>

            {/* Cliente */}
            <div className="p-3 rounded-lg bg-surface-50 border border-surface-200 mb-4">
              <p className="text-[11px] text-brand-400 font-semibold uppercase mb-1">Cliente</p>
              <p className="text-[13px] font-medium text-brand-800">{detalleDoc.cliente_nombre}</p>
              {detalleDoc.cliente_rfc && <p className="text-[11px] text-brand-400 font-mono">{detalleDoc.cliente_rfc}</p>}
              {detalleDoc.cliente_telefono && <p className="text-[11px] text-brand-400">{detalleDoc.cliente_telefono}</p>}
            </div>

            {/* Montos */}
            <div className="grid grid-cols-1 sm:grid-cols-3 gap-3 mb-4">
              <div className="text-center p-3 rounded-lg bg-surface-50 border border-surface-200">
                <p className="text-[10px] text-brand-400 font-semibold uppercase">Monto</p>
                <p className="text-[16px] font-bold text-brand-800">${fmt(detalleDoc.monto)}</p>
              </div>
              <div className="text-center p-3 rounded-lg bg-surface-50 border border-surface-200">
                <p className="text-[10px] text-brand-400 font-semibold uppercase">Pagado</p>
                <p className="text-[16px] font-bold text-status-ok">${fmt(detalleDoc.total_pagado)}</p>
              </div>
              <div className="text-center p-3 rounded-lg bg-surface-50 border border-surface-200">
                <p className="text-[10px] text-brand-400 font-semibold uppercase">Saldo</p>
                <p className={`text-[16px] font-bold ${detalleDoc.saldo_pendiente > 0 ? 'text-status-critical' : 'text-status-ok'}`}>
                  ${fmt(detalleDoc.saldo_pendiente)}
                </p>
              </div>
            </div>

            {detalleDoc.notas && (
              <div className="p-3 rounded-lg bg-amber-50 border border-amber-200 mb-4 text-[12px] text-amber-800">
                <span className="font-semibold">Notas:</span> {detalleDoc.notas}
              </div>
            )}

            {/* Historial de pagos */}
            <div>
              <p className="text-[11px] font-semibold text-brand-400 uppercase mb-2">Historial de Pagos ({detallePagos.length})</p>
              {detallePagos.length === 0 ? (
                <p className="text-[12px] text-brand-400 italic">Sin pagos registrados</p>
              ) : (
                <div className="space-y-2">
                  {detallePagos.map((p) => (
                    <div key={p.id} className="flex items-center justify-between p-2.5 rounded-lg bg-surface-50 border border-surface-100">
                      <div>
                        <p className="text-[12px] text-brand-600">{p.fecha} {p.metodo_pago && `· ${p.metodo_pago}`}</p>
                        {p.referencia && <p className="text-[11px] text-brand-400">Ref: {p.referencia}</p>}
                        {p.notas && <p className="text-[11px] text-brand-400 italic">{p.notas}</p>}
                      </div>
                      <p className="text-[13px] font-bold text-status-ok">${fmt(p.monto)}</p>
                    </div>
                  ))}
                </div>
              )}
            </div>

            <div className="flex items-center justify-end gap-3 mt-6 pt-4 border-t border-surface-200">
              <button onClick={() => setShowDetalle(false)} className="btn-secondary">Cerrar</button>
            </div>
          </div>
        </div>
      )}

      {/* ─── MODAL: EDITAR DOCUMENTO ──────────────────── */}
      {showEditModal && editFactura && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-brand-950/40 backdrop-blur-sm">
          <div className="card p-6 w-full max-w-lg mx-4 shadow-modal max-h-[90vh] overflow-y-auto">
            <div className="flex items-center justify-between mb-4">
              <div className="flex items-center gap-2">
                <Pencil className="w-5 h-5 text-brand-500" />
                <h2 className="text-[13px] font-semibold text-brand-800">Editar Documento</h2>
              </div>
              <button onClick={() => setShowEditModal(false)} className="btn-ghost p-1"><X className="w-4 h-4" /></button>
            </div>

            {editError && <div className="p-3 rounded-lg bg-status-critical-muted border border-red-200 text-[12px] text-red-700 mb-4">{editError}</div>}

            {/* Cliente (read-only) + editable folio + fecha */}
            <div className="p-3 rounded-lg bg-surface-50 border border-surface-200 mb-4 text-[12px]">
              <p className="text-brand-400 text-[10px] uppercase font-semibold mb-0.5">Cliente</p>
              <p className="text-brand-800 font-medium">{editFactura.cliente_nombre}</p>
            </div>

            <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 mb-4">
              <div>
                <label className="label">Folio *</label>
                <input
                  className="input-field w-full font-mono"
                  value={editFolio}
                  onChange={e => setEditFolio(e.target.value.toUpperCase())}
                  placeholder="Ej. 9876"
                />
              </div>
              <div>
                <label className="label">Fecha *</label>
                <input
                  type="date"
                  className="input-field w-full"
                  value={editFecha}
                  onChange={e => setEditFecha(e.target.value)}
                />
              </div>
            </div>

            <div className="space-y-4">
              {/* Tipo de documento */}
              <div>
                <label className="label">Tipo de documento</label>
                <div className="grid grid-cols-2 sm:grid-cols-4 gap-2">
                  {([
                    { val: 'FACTURA', label: 'Factura', color: 'blue' },
                    { val: 'NOTA_VENTA', label: 'Nota venta', color: 'gray' },
                    { val: 'CREDITO', label: 'Crédito', color: 'orange' },
                    { val: 'REMISION', label: 'Remisión', color: 'purple' },
                  ] as const).map((t) => (
                    <button key={t.val} type="button" onClick={() => setEditTipo(t.val)}
                      className={`px-2 py-2 text-[11px] font-semibold rounded-lg border-2 transition-all text-center ${
                        editTipo === t.val
                          ? `bg-${t.color}-50 border-${t.color}-300 text-${t.color}-800`
                          : 'border-surface-200 text-brand-400 bg-white'
                      }`}>
                      {t.label}
                    </button>
                  ))}
                </div>
              </div>

              <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                <div>
                  <label className="label">Monto *</label>
                  <div className="relative">
                    <span className="absolute left-3 top-1/2 -translate-y-1/2 text-sm text-brand-400">$</span>
                    <input type="number" value={editMonto || ''} onChange={(e) => setEditMonto(parseFloat(e.target.value) || 0)}
                      min={0} step={0.01} className="input-field pl-7 tabular-nums text-lg font-bold" />
                  </div>
                </div>
                <div>
                  <label className="label">Estatus</label>
                  <div className="flex gap-2">
                    {['PAGADA', 'CREDITO', 'PARCIAL'].map((s) => (
                      <button key={s} type="button" onClick={() => setEditEstatus(s)}
                        className={`flex-1 px-2 py-2.5 text-[10px] font-semibold rounded-lg border-2 transition-all ${
                          editEstatus === s
                            ? s === 'PAGADA' ? 'bg-emerald-50 border-emerald-300 text-emerald-800'
                              : s === 'CREDITO' ? 'bg-red-50 border-red-300 text-red-800'
                              : 'bg-amber-50 border-amber-300 text-amber-800'
                            : 'border-surface-200 text-brand-400 bg-white'
                        }`}>
                        {s}
                      </button>
                    ))}
                  </div>
                </div>
              </div>

              <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                <div>
                  <label className="label">Condición de pago</label>
                  <select value={editCondicion} onChange={(e) => setEditCondicion(e.target.value)} className="select-field">
                    <option value="CONTADO">Contado</option>
                    <option value="CREDITO_15">Crédito 15 días</option>
                    <option value="CREDITO_30">Crédito 30 días</option>
                    <option value="CREDITO_60">Crédito 60 días</option>
                  </select>
                </div>
                <div>
                  <label className="label">Método de pago</label>
                  <select value={editMetodo} onChange={(e) => setEditMetodo(e.target.value)} className="select-field">
                    <option value="">—</option>
                    <option value="EFECTIVO">Efectivo</option>
                    <option value="TRANSFERENCIA">Transferencia</option>
                    <option value="CHEQUE">Cheque</option>
                    <option value="TARJETA">Tarjeta</option>
                    <option value="MIXTO">Mixto</option>
                  </select>
                </div>
              </div>

              <div>
                <label className="label">Notas</label>
                <input value={editNotas} onChange={(e) => setEditNotas(e.target.value)} placeholder="Observaciones..." className="input-field" />
              </div>
            </div>

            <div className="flex items-center justify-end gap-3 mt-6 pt-4 border-t border-surface-200">
              <button onClick={() => setShowEditModal(false)} className="btn-secondary">Cancelar</button>
              <button onClick={handleEdit} disabled={savingEdit} className="btn-primary">
                <Save className="w-4 h-4" /> {savingEdit ? 'Guardando...' : 'Guardar cambios'}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
