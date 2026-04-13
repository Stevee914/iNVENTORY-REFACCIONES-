import { useEffect, useRef, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useDebounce } from '@/hooks/useDebounce';
import { Plus, Pencil, Trash2, AlertTriangle, ShoppingBag, X, Upload } from 'lucide-react';
import { PageHeader } from '@/components/shared';
import { comprasService, proveedorService } from '@/services';
import { comprasXmlService } from '@/services/comprasXmlService';
import type { Compra, ResumenCompras, CompraCreate } from '@/services/comprasService';
import type { Proveedor } from '@/types';
import { cn } from '@/lib/utils';
import { CompraForm } from '@/components/CompraForm';
import { ComprasDashboard } from '@/components/ComprasDashboard';

const ESTATUS_OPTIONS = ['PENDIENTE', 'RECIBIDA', 'PAGADA', 'PARCIAL', 'CANCELADA'];
const METODOS_PAGO    = ['EFECTIVO', 'TRANSFERENCIA', 'CHEQUE', 'TARJETA', 'CONTADO', 'CREDITO', 'OTRO'];

const estatusStyle: Record<string, string> = {
  PAGADA:    'bg-emerald-50 text-emerald-700 border border-emerald-200',
  RECIBIDA:  'bg-blue-50 text-blue-700 border border-blue-200',
  PENDIENTE: 'bg-amber-50 text-amber-700 border border-amber-200',
  PARCIAL:   'bg-purple-50 text-purple-700 border border-purple-200',
  CANCELADA: 'bg-surface-100 text-brand-400 border border-surface-200',
};

const origenStyle: Record<string, string> = {
  MANUAL: 'bg-surface-100 text-brand-500',
  POS:    'bg-sap-blue/10 text-sap-blue',
};

function fmt(n: number) {
  return `$${Number(n).toLocaleString('es-MX', { minimumFractionDigits: 2 })}`;
}

const emptyForm: CompraCreate = {
  proveedor_id:  0,
  folio_factura: '',
  folio_captura: '',
  fecha:         new Date().toISOString().slice(0, 10),
  subtotal:      0,
  iva:           0,
  total:         0,
  estatus:       'PENDIENTE',
  metodo_pago:   '',
  notas:         '',
  tipo_compra:   'SIN_FACTURA',
};

export function ComprasPage() {
  const navigate = useNavigate();
  const xmlInputRef = useRef<HTMLInputElement>(null);
  const [xmlUploading, setXmlUploading] = useState(false);

  const [items, setItems]               = useState<Compra[]>([]);
  const [resumen, setResumen]           = useState<ResumenCompras | null>(null);
  const [proveedores, setProveedores]   = useState<Proveedor[]>([]);
  const [loading, setLoading]           = useState(true);
  const [error, setError]               = useState('');
  const [total, setTotal]               = useState(0);
  const [page, setPage]                 = useState(1);
  const PAGE_SIZE = 50;

  // Filters
  const [q, setQ]                             = useState('');
  const [filterEstatus, setFilterEstatus]     = useState('');
  const [filterOrigen, setFilterOrigen]       = useState('');
  const [filterProveedor, setFilterProveedor] = useState('');
  const [filterFechaIni, setFilterFechaIni]   = useState('');
  const [filterFechaFin, setFilterFechaFin]   = useState('');
  const [filterTipo, setFilterTipo]           = useState('');

  // Modal
  const [showForm, setShowForm]   = useState(false);
  const [editId, setEditId]       = useState<number | null>(null);
  const [editOrigen, setEditOrigen] = useState<'MANUAL' | 'POS'>('MANUAL');
  const [form, setForm]           = useState<CompraCreate>(emptyForm);
  const [saving, setSaving]       = useState(false);
  const [formError, setFormError] = useState('');

  // Delete confirm
  const [deleteId, setDeleteId] = useState<number | null>(null);

  // Nueva Compra full-form
  const [showCreateForm, setShowCreateForm] = useState(false);

  // Toast
  const [toast,      setToast]      = useState<string | null>(null);
  const toastTimer = useRef<ReturnType<typeof setTimeout> | null>(null);

  function showToast(msg: string) {
    setToast(msg);
    if (toastTimer.current) clearTimeout(toastTimer.current);
    toastTimer.current = setTimeout(() => setToast(null), 6000);
  }

  // Debounce free-text search so the API is only called after the user
  // pauses typing, not on every keystroke.
  const debouncedQ = useDebounce(q, 400);

  const load = async () => {
    setLoading(true);
    try {
      const res = await comprasService.getAll({
        q:            debouncedQ || undefined,
        estatus:      filterEstatus  || undefined,
        origen:       filterOrigen   || undefined,
        tipo_compra:  filterTipo     || undefined,
        proveedor_id: filterProveedor ? Number(filterProveedor) : undefined,
        fecha_inicio: filterFechaIni || undefined,
        fecha_fin:    filterFechaFin || undefined,
        page,
        page_size: PAGE_SIZE,
      });
      setItems(res.items);
      setTotal(res.total);
    } catch (e: any) {
      setError(e.message);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { proveedorService.getAll().then(setProveedores); }, []);
  // Resumen is aggregate data independent of list filters — load once on mount.
  useEffect(() => { comprasService.getResumen().then(setResumen).catch(() => {}); }, []);
  useEffect(() => { load(); }, [debouncedQ, filterEstatus, filterOrigen, filterTipo, filterProveedor, filterFechaIni, filterFechaFin, page]);

  // ── Form helpers ──────────────────────────────────────────────────────────

  const handleXmlFileChange = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;
    e.target.value = '';
    setXmlUploading(true);
    try {
      const res = await comprasXmlService.uploadXml(file);
      navigate(`/compras/xml/${res.compra_id}`);
    } catch (err: any) {
      showToast(`Error importando XML: ${err.message}`);
    } finally {
      setXmlUploading(false);
    }
  };

  const openCreate = () => {
    setShowCreateForm(true);
  };

  const openEdit = (c: Compra) => {
    setEditId(c.id);
    setEditOrigen(c.origen);
    setForm({
      proveedor_id:  c.proveedor_id,
      folio_factura: c.folio_factura ?? '',
      folio_captura: c.folio_captura ?? '',
      fecha:         c.fecha,
      subtotal:      c.subtotal,
      iva:           c.iva,
      total:         c.total,
      estatus:       c.estatus,
      metodo_pago:   c.metodo_pago ?? '',
      notas:         c.notas ?? '',
      tipo_compra:   c.tipo_compra ?? 'SIN_FACTURA',
    });
    setFormError('');
    setShowForm(true);
  };

  const handleSubtotalChange = (subtotal: number) => {
    const iva = Math.round(subtotal * 0.16 * 100) / 100;
    setForm(f => ({ ...f, subtotal, iva, total: subtotal + iva }));
  };

  const handleSave = async () => {
    if (!form.proveedor_id) { setFormError('Selecciona un proveedor'); return; }
    if (!form.fecha)        { setFormError('La fecha es requerida'); return; }
    if (form.total <= 0)    { setFormError('El total debe ser mayor a 0'); return; }

    setSaving(true);
    setFormError('');
    try {
      const payload = {
        ...form,
        folio_factura: form.folio_factura || undefined,
        folio_captura: form.folio_captura || undefined,
        metodo_pago:   form.metodo_pago   || undefined,
        notas:         form.notas         || undefined,
      };
      if (editId !== null) {
        await comprasService.update(editId, payload);
      } else {
        await comprasService.create(payload);
      }
      setShowForm(false);
      setPage(1);
      load();
    } catch (e: any) {
      setFormError(e.message);
    } finally {
      setSaving(false);
    }
  };

  const handleDelete = async () => {
    if (deleteId === null) return;
    try {
      await comprasService.delete(deleteId);
      setDeleteId(null);
      load();
    } catch (e: any) {
      setError(e.message);
    }
  };

  // POS-synced records: financial fields are owned by the sync, show as read-only
  const isPOS = editOrigen === 'POS';

  // ── Render ────────────────────────────────────────────────────────────────

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
      {/* Hidden file input for XML upload */}
      <input
        ref={xmlInputRef}
        type="file"
        accept=".xml"
        className="hidden"
        onChange={handleXmlFileChange}
      />

      <PageHeader
        title="Compras"
        description="Registro de facturas y documentos de compra a proveedores"
        actions={
          <>
            <button
              onClick={() => xmlInputRef.current?.click()}
              disabled={xmlUploading}
              className="btn-secondary"
            >
              <Upload className="w-4 h-4" />
              {xmlUploading ? 'Subiendo...' : 'Importar XML'}
            </button>
            <button onClick={openCreate} className="btn-primary">
              <Plus className="w-4 h-4" /> Nueva Compra
            </button>
          </>
        }
      />

      {/* ── Summary cards ── */}
      {resumen && (
        <div className="grid grid-cols-1 xs:grid-cols-2 lg:grid-cols-4 gap-3 mb-5">
          <div className="card p-4">
            <p className="text-[11px] text-brand-400 uppercase tracking-wide mb-1">Total registros</p>
            <p className="text-2xl font-semibold text-brand-800">{resumen.total_compras}</p>
            <p className="text-[11px] text-brand-400">{resumen.compras_pos} POS · {resumen.compras_manual} manual</p>
          </div>
          <div className="card p-4">
            <p className="text-[11px] text-brand-400 uppercase tracking-wide mb-1">Monto total</p>
            <p className="text-2xl font-semibold text-brand-800">{fmt(resumen.monto_total)}</p>
          </div>
          <div className="card p-4">
            <p className="text-[11px] text-brand-400 uppercase tracking-wide mb-1">Pagadas</p>
            <p className="text-2xl font-semibold text-emerald-600">{fmt(resumen.monto_pagado)}</p>
            <p className="text-[11px] text-brand-400">{resumen.compras_pagadas} docs</p>
          </div>
          <div className="card p-4">
            <p className="text-[11px] text-brand-400 uppercase tracking-wide mb-1">Pendientes</p>
            <p className="text-2xl font-semibold text-amber-600">{fmt(resumen.monto_pendiente)}</p>
            <p className="text-[11px] text-brand-400">{resumen.compras_pendientes} docs</p>
          </div>
        </div>
      )}

      {/* ── Dashboard ── */}
      <ComprasDashboard />

      {/* ── Section separator ── */}
      <div className="flex items-center gap-3 mb-4 -mt-2">
        <div className="flex-1 h-px bg-surface-200" />
        <span className="text-[11px] font-semibold text-brand-400 uppercase tracking-wide">Registros</span>
        <div className="flex-1 h-px bg-surface-200" />
      </div>

      {/* ── Filters ── */}
      <div className="card p-3 mb-4 flex flex-wrap gap-2">
        <input
          className="input-field flex-1 min-w-[180px] text-xs py-2"
          placeholder="Buscar por folio o proveedor..."
          value={q}
          onChange={e => { setQ(e.target.value); setPage(1); }}
        />
        <select
          className="select-field w-full sm:w-36 text-xs py-2"
          value={filterEstatus}
          onChange={e => { setFilterEstatus(e.target.value); setPage(1); }}
        >
          <option value="">Todos los estatus</option>
          {ESTATUS_OPTIONS.map(s => <option key={s} value={s}>{s}</option>)}
        </select>
        <select
          className="select-field w-full sm:w-28 text-xs py-2"
          value={filterOrigen}
          onChange={e => { setFilterOrigen(e.target.value); setPage(1); }}
        >
          <option value="">Origen</option>
          <option value="MANUAL">MANUAL</option>
          <option value="POS">POS</option>
        </select>
        <select
          className="select-field w-full sm:w-36 text-xs py-2"
          value={filterTipo}
          onChange={e => { setFilterTipo(e.target.value); setPage(1); }}
        >
          <option value="">Tipo compra</option>
          <option value="CON_FACTURA">Con Factura</option>
          <option value="SIN_FACTURA">Sin Factura</option>
        </select>
        <select
          className="select-field w-full sm:w-44 text-xs py-2"
          value={filterProveedor}
          onChange={e => { setFilterProveedor(e.target.value); setPage(1); }}
        >
          <option value="">Todos los proveedores</option>
          {proveedores.map(p => (
            <option key={p.id} value={p.id}>{p.nombre}</option>
          ))}
        </select>
        <input
          type="date"
          className="input-field w-full sm:w-36 text-xs py-2"
          value={filterFechaIni}
          onChange={e => { setFilterFechaIni(e.target.value); setPage(1); }}
        />
        <input
          type="date"
          className="input-field w-full sm:w-36 text-xs py-2"
          value={filterFechaFin}
          onChange={e => { setFilterFechaFin(e.target.value); setPage(1); }}
        />
      </div>

      {/* ── Table ── */}
      <div className="card overflow-hidden">
        {loading ? (
          <div className="flex items-center justify-center h-40">
            <div className="w-6 h-6 border-2 border-surface-300 border-t-sap-blue rounded-full animate-spin" />
          </div>
        ) : items.length === 0 ? (
          <div className="flex flex-col items-center justify-center h-40 text-brand-400">
            <ShoppingBag className="w-8 h-8 mb-2 opacity-30" />
            <p className="text-sm">Sin registros</p>
          </div>
        ) : (
          <div className="overflow-x-auto">
          <table className="w-full text-[13px] min-w-[700px]">
            <thead>
              <tr className="border-b border-surface-200 bg-surface-50">
                <th className="text-left px-4 py-2.5 text-[11px] font-semibold text-brand-400 uppercase tracking-wide">Origen</th>
                <th className="text-left px-4 py-2.5 text-[11px] font-semibold text-brand-400 uppercase tracking-wide">Tipo</th>
                <th className="text-left px-4 py-2.5 text-[11px] font-semibold text-brand-400 uppercase tracking-wide">Folio factura</th>
                <th className="text-left px-4 py-2.5 text-[11px] font-semibold text-brand-400 uppercase tracking-wide">Proveedor</th>
                <th className="text-left px-4 py-2.5 text-[11px] font-semibold text-brand-400 uppercase tracking-wide">Fecha</th>
                <th className="text-right px-4 py-2.5 text-[11px] font-semibold text-brand-400 uppercase tracking-wide">Subtotal</th>
                <th className="text-right px-4 py-2.5 text-[11px] font-semibold text-brand-400 uppercase tracking-wide">IVA</th>
                <th className="text-right px-4 py-2.5 text-[11px] font-semibold text-brand-400 uppercase tracking-wide">Total</th>
                <th className="text-left px-4 py-2.5 text-[11px] font-semibold text-brand-400 uppercase tracking-wide">Estatus</th>
                <th className="text-left px-4 py-2.5 text-[11px] font-semibold text-brand-400 uppercase tracking-wide">Método</th>
                <th className="px-4 py-2.5 w-20" />
              </tr>
            </thead>
            <tbody>
              {items.map((c, i) => (
                <tr
                  key={c.id}
                  className={cn('border-b border-surface-100 hover:bg-surface-50 transition-colors', i % 2 === 0 ? '' : 'bg-surface-50/40')}
                >
                  <td className="px-4 py-2.5">
                    <span className={cn('text-[10px] font-semibold px-2 py-0.5 rounded-full', origenStyle[c.origen])}>
                      {c.origen}
                    </span>
                  </td>
                  <td className="px-4 py-2.5">
                    <span className={cn(
                      'text-[10px] font-semibold px-2 py-0.5 rounded-full whitespace-nowrap',
                      c.tipo_compra === 'CON_FACTURA'
                        ? 'bg-emerald-50 text-emerald-700 border border-emerald-200'
                        : 'bg-surface-100 text-brand-500 border border-surface-200',
                    )}>
                      {c.tipo_compra === 'CON_FACTURA' ? 'Con Factura' : 'Sin Factura'}
                    </span>
                  </td>
                  <td className="px-4 py-2.5">
                    <p className="font-mono text-xs font-medium text-brand-600">{c.folio_factura ?? '—'}</p>
                    {c.folio_captura && (
                      <p className="text-[10px] text-brand-400">cap: {c.folio_captura}</p>
                    )}
                  </td>
                  <td className="px-4 py-2.5">
                    <p className="font-medium text-brand-800 text-[13px]">{c.proveedor_nombre}</p>
                    <p className="text-[11px] text-brand-400">{c.proveedor_codigo}</p>
                  </td>
                  <td className="px-4 py-2.5 text-brand-500 text-xs">{c.fecha}</td>
                  <td className="px-4 py-2.5 text-right tabular-nums text-brand-500 text-xs">{fmt(c.subtotal)}</td>
                  <td className="px-4 py-2.5 text-right tabular-nums text-brand-400 text-xs">{fmt(c.iva)}</td>
                  <td className="px-4 py-2.5 text-right tabular-nums font-semibold text-brand-800 text-xs">{fmt(c.total)}</td>
                  <td className="px-4 py-2.5">
                    <span className={cn('badge text-[10px] px-2 py-0.5 rounded-full', estatusStyle[c.estatus] ?? '')}>
                      {c.estatus}
                    </span>
                  </td>
                  <td className="px-4 py-2.5 text-brand-400 text-xs">{c.metodo_pago ?? '—'}</td>
                  <td className="px-4 py-2.5">
                    <div className="flex items-center gap-1 justify-end">
                      <button onClick={() => openEdit(c)} className="btn-ghost p-1.5" title="Editar">
                        <Pencil className="w-3.5 h-3.5" />
                      </button>
                      <button onClick={() => setDeleteId(c.id)} className="btn-ghost p-1.5 text-status-critical hover:bg-red-50" title="Eliminar">
                        <Trash2 className="w-3.5 h-3.5" />
                      </button>
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
          </div>
        )}

        {/* Pagination */}
        {total > PAGE_SIZE && (
          <div className="flex items-center justify-between px-4 py-3 border-t border-surface-200 text-[12px] text-brand-400">
            <span>{total} registros</span>
            <div className="flex gap-2">
              <button
                className="btn-ghost px-3 py-1 text-xs"
                disabled={page === 1}
                onClick={() => setPage(p => p - 1)}
              >Anterior</button>
              <span className="px-2 py-1">Página {page} de {Math.ceil(total / PAGE_SIZE)}</span>
              <button
                className="btn-ghost px-3 py-1 text-xs"
                disabled={page >= Math.ceil(total / PAGE_SIZE)}
                onClick={() => setPage(p => p + 1)}
              >Siguiente</button>
            </div>
          </div>
        )}
      </div>

      {/* ── Create / Edit Modal ── */}
      {showForm && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 backdrop-blur-sm">
          <div className="bg-white rounded-xl shadow-2xl w-full max-w-lg mx-4 overflow-hidden">
            <div className="px-6 py-4 border-b border-surface-200 flex items-center justify-between">
              <div className="flex items-center gap-2">
                <h2 className="text-[15px] font-semibold text-brand-800">
                  {editId !== null ? 'Editar Compra' : 'Nueva Compra'}
                </h2>
                {isPOS && (
                  <span className="text-[10px] font-semibold px-2 py-0.5 rounded-full bg-sap-blue/10 text-sap-blue">
                    POS
                  </span>
                )}
              </div>
              <button onClick={() => setShowForm(false)} className="btn-ghost p-1.5 text-brand-400">✕</button>
            </div>

            <div className="px-6 py-4 space-y-4 max-h-[70vh] overflow-y-auto">
              {formError && (
                <div className="bg-red-50 border border-red-200 text-red-700 text-xs rounded-lg px-3 py-2">
                  {formError}
                </div>
              )}

              {isPOS && (
                <div className="bg-blue-50 border border-blue-200 text-blue-700 text-xs rounded-lg px-3 py-2">
                  Compra sincronizada desde POS. Los montos se actualizan automáticamente al sincronizar.
                </div>
              )}

              <div>
                <label className="label-field">Proveedor *</label>
                <select
                  className="select-field w-full"
                  value={form.proveedor_id || ''}
                  disabled={isPOS}
                  onChange={e => setForm(f => ({ ...f, proveedor_id: Number(e.target.value) }))}
                >
                  <option value="">Seleccionar proveedor...</option>
                  {proveedores.map(p => (
                    <option key={p.id} value={p.id}>{p.nombre}</option>
                  ))}
                </select>
              </div>

              <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                <div>
                  <label className="label-field">Folio factura proveedor</label>
                  <input
                    className={cn('input-field w-full', isPOS && 'bg-surface-50 text-brand-400')}
                    placeholder="Ej. FAC-2026-001"
                    readOnly={isPOS}
                    value={form.folio_factura ?? ''}
                    onChange={e => setForm(f => ({ ...f, folio_factura: e.target.value }))}
                  />
                </div>
                <div>
                  <label className="label-field">Folio captura</label>
                  <input
                    className={cn('input-field w-full', isPOS && 'bg-surface-50 text-brand-400')}
                    placeholder="Ref. interna / POS"
                    readOnly={isPOS}
                    value={form.folio_captura ?? ''}
                    onChange={e => setForm(f => ({ ...f, folio_captura: e.target.value }))}
                  />
                </div>
              </div>

              <div>
                <label className="label-field">Fecha *</label>
                <input
                  type="date"
                  className={cn('input-field w-full', isPOS && 'bg-surface-50 text-brand-400')}
                  readOnly={isPOS}
                  value={form.fecha}
                  onChange={e => setForm(f => ({ ...f, fecha: e.target.value }))}
                />
              </div>

              <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
                <div>
                  <label className="label-field">Subtotal *</label>
                  <input
                    type="number" step="0.01"
                    className={cn('input-field w-full', isPOS && 'bg-surface-50 text-brand-400')}
                    readOnly={isPOS}
                    value={form.subtotal}
                    onChange={e => handleSubtotalChange(Number(e.target.value))}
                  />
                </div>
                <div>
                  <label className="label-field">IVA</label>
                  <input
                    type="number" step="0.01"
                    className={cn('input-field w-full', isPOS && 'bg-surface-50 text-brand-400')}
                    readOnly={isPOS}
                    value={form.iva}
                    onChange={e => setForm(f => ({ ...f, iva: Number(e.target.value), total: f.subtotal + Number(e.target.value) }))}
                  />
                </div>
                <div>
                  <label className="label-field">Total *</label>
                  <input
                    type="number" step="0.01"
                    className={cn('input-field w-full', isPOS && 'bg-surface-50 text-brand-400')}
                    readOnly={isPOS}
                    value={form.total}
                    onChange={e => setForm(f => ({ ...f, total: Number(e.target.value) }))}
                  />
                </div>
              </div>

              <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                <div>
                  <label className="label-field">Tipo de compra</label>
                  <select
                    className="select-field w-full"
                    value={form.tipo_compra ?? 'SIN_FACTURA'}
                    onChange={e => setForm(f => ({ ...f, tipo_compra: e.target.value }))}
                  >
                    <option value="SIN_FACTURA">Sin Factura / Remisión</option>
                    <option value="CON_FACTURA">Con Factura</option>
                  </select>
                </div>
                <div>
                  <label className="label-field">Estatus</label>
                  <select
                    className="select-field w-full"
                    value={form.estatus}
                    onChange={e => setForm(f => ({ ...f, estatus: e.target.value }))}
                  >
                    {ESTATUS_OPTIONS.map(s => <option key={s} value={s}>{s}</option>)}
                  </select>
                </div>
              </div>

              <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                <div>
                  <label className="label-field">Método / Condición de pago</label>
                  <select
                    className="select-field w-full"
                    value={form.metodo_pago ?? ''}
                    onChange={e => setForm(f => ({ ...f, metodo_pago: e.target.value }))}
                  >
                    <option value="">— Sin especificar —</option>
                    {METODOS_PAGO.map(m => <option key={m} value={m}>{m}</option>)}
                  </select>
                </div>
              </div>

              <div>
                <label className="label-field">Notas / Observaciones</label>
                <textarea
                  className="input-field w-full h-20 resize-none"
                  placeholder="Observaciones opcionales..."
                  value={form.notas ?? ''}
                  onChange={e => setForm(f => ({ ...f, notas: e.target.value }))}
                />
              </div>
            </div>

            <div className="px-6 py-4 border-t border-surface-200 flex justify-end gap-2">
              <button onClick={() => setShowForm(false)} className="btn-secondary">Cancelar</button>
              <button onClick={handleSave} disabled={saving} className="btn-primary">
                {saving ? 'Guardando...' : editId !== null ? 'Guardar cambios' : 'Crear compra'}
              </button>
            </div>
          </div>
        </div>
      )}

      {/* ── Nueva Compra full-form ── */}
      {showCreateForm && (
        <CompraForm
          proveedores={proveedores}
          onSuccess={(id, count) => {
            setShowCreateForm(false);
            showToast(`Compra #${id} registrada — ${count} producto${count !== 1 ? 's' : ''}`);
            setPage(1);
            load();
          }}
          onClose={() => setShowCreateForm(false)}
        />
      )}

      {/* ── Toast ── */}
      {toast && (
        <div className="fixed bottom-6 right-6 z-[60] flex items-center gap-3 px-4 py-3 rounded-xl shadow-lg border bg-emerald-50 border-emerald-200 text-emerald-800 max-w-sm">
          <p className="text-sm font-medium flex-1">{toast}</p>
          <button onClick={() => setToast(null)} className="shrink-0 opacity-60 hover:opacity-100">
            <X className="w-4 h-4" />
          </button>
        </div>
      )}

      {/* ── Delete confirm ── */}
      {deleteId !== null && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 backdrop-blur-sm">
          <div className="bg-white rounded-xl shadow-2xl w-full max-w-sm mx-4 p-6">
            <h2 className="text-[15px] font-semibold text-brand-800 mb-2">¿Eliminar compra?</h2>
            <p className="text-[13px] text-brand-500 mb-5">Esta acción no se puede deshacer.</p>
            <div className="flex justify-end gap-2">
              <button onClick={() => setDeleteId(null)} className="btn-secondary">Cancelar</button>
              <button onClick={handleDelete} className="btn-primary bg-red-600 hover:bg-red-700 border-red-600">Eliminar</button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
