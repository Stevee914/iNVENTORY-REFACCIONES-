import { useEffect, useState } from 'react';
import { Plus, Pencil, X, Save, Search, Users, AlertTriangle, Trash2 } from 'lucide-react';
import { PageHeader } from '@/components/shared';
import { clienteService, type Cliente, type ClienteFormData } from '@/services/clienteService';
import { formatDateTime, cn } from '@/lib/utils';

const emptyForm: ClienteFormData = { nombre: '', rfc: '', direccion: '', telefono: '', correo: '', tipo: 'MOSTRADOR', notas: '' };

const tipoColors: Record<string, string> = {
  MOSTRADOR: 'bg-surface-100 text-brand-500',
  CREDITO: 'bg-blue-50 text-blue-700',
  TALLER: 'bg-amber-50 text-amber-700',
};

export function ClientesPage() {
  const [clientes, setClientes] = useState<Cliente[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [searchQ, setSearchQ] = useState('');
  const [tipoFilter, setTipoFilter] = useState('');

  const [showModal, setShowModal] = useState(false);
  const [editingId, setEditingId] = useState<number | null>(null);
  const [form, setForm] = useState<ClienteFormData>(emptyForm);
  const [formError, setFormError] = useState('');
  const [saving, setSaving] = useState(false);

  async function load() {
    setLoading(true);
    try {
      const res = await clienteService.getAll(searchQ || undefined, tipoFilter || undefined);
      setClientes(res.items);
    } catch (e: any) { setError(e.message); }
    finally { setLoading(false); }
  }

  useEffect(() => { load(); }, [searchQ, tipoFilter]);

  function openNew() {
    setForm(emptyForm); setEditingId(null); setFormError(''); setShowModal(true);
  }

  function openEdit(c: Cliente) {
    setForm({
      nombre: c.nombre, rfc: c.rfc || '', direccion: c.direccion || '',
      telefono: c.telefono || '', correo: c.correo || '', tipo: c.tipo, notas: c.notas || '',
    });
    setEditingId(c.id); setFormError(''); setShowModal(true);
  }

  async function handleSubmit() {
    if (!form.nombre.trim()) { setFormError('El nombre es obligatorio'); return; }
    setSaving(true); setFormError('');
    try {
      if (editingId) { await clienteService.update(editingId, form); }
      else { await clienteService.create(form); }
      setShowModal(false); await load();
    } catch (e: any) { setFormError(e.message); }
    finally { setSaving(false); }
  }

  async function handleDelete(c: Cliente) {
    if (!confirm(`¿Eliminar cliente "${c.nombre}"?`)) return;
    try { await clienteService.delete(c.id); await load(); }
    catch (e: any) { alert(e.message); }
  }

  const totalCompras = clientes.reduce((s, c) => s + (c.total_compras || 0), 0);
  const conCredito = clientes.filter((c) => c.tipo === 'CREDITO').length;

  if (error && clientes.length === 0) {
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
        title="Clientes"
        description={`${clientes.length} clientes — ${conCredito} a crédito`}
        actions={
          <button onClick={openNew} className="btn-primary">
            <Plus className="w-4 h-4" /> Nuevo Cliente
          </button>
        }
      />

      {/* KPIs */}
      <div className="grid grid-cols-1 sm:grid-cols-3 gap-4 mb-5">
        <div className="card p-4">
          <p className="text-[11px] font-semibold text-brand-400 uppercase tracking-wide">Total clientes</p>
          <p className="text-[22px] font-bold text-brand-800 mt-1">{clientes.length}</p>
        </div>
        <div className="card p-4">
          <p className="text-[11px] font-semibold text-brand-400 uppercase tracking-wide">Total facturado</p>
          <p className="text-[22px] font-bold text-brand-800 mt-1">${totalCompras.toLocaleString('es-MX', { minimumFractionDigits: 2 })}</p>
        </div>
        <div className="card p-4">
          <p className="text-[11px] font-semibold text-brand-400 uppercase tracking-wide">Clientes a crédito</p>
          <p className="text-[22px] font-bold text-brand-800 mt-1">{conCredito}</p>
        </div>
      </div>

      {/* Search + Filter */}
      <div className="card px-5 py-4 mb-4">
        <div className="flex flex-col sm:flex-row gap-3 items-start sm:items-center">
          <div className="relative flex-1 max-w-md">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-brand-300" />
            <input type="text" value={searchQ} onChange={(e) => setSearchQ(e.target.value)}
              placeholder="Buscar por nombre, RFC o teléfono..." className="input-field pl-10 py-2" />
          </div>
          <select value={tipoFilter} onChange={(e) => setTipoFilter(e.target.value)} className="select-field w-40 py-2 text-xs">
            <option value="">Todos los tipos</option>
            <option value="MOSTRADOR">Mostrador</option>
            <option value="CREDITO">Crédito</option>
            <option value="TALLER">Taller</option>
          </select>
          <span className="text-[11px] text-brand-400 ml-auto">{clientes.length} resultados</span>
        </div>
      </div>

      {/* Table */}
      <div className="card overflow-hidden">
        <div className="overflow-x-auto">
          <table className="w-full">
            <thead>
              <tr className="border-b border-surface-200">
                <th className="table-header">Nombre</th>
                <th className="table-header">RFC</th>
                <th className="table-header">Teléfono</th>
                <th className="table-header">Tipo</th>
                <th className="table-header text-right">Facturas</th>
                <th className="table-header text-right">Total compras</th>
                <th className="table-header w-24"></th>
              </tr>
            </thead>
            <tbody className="divide-y divide-surface-100">
              {loading ? (
                <tr><td colSpan={7} className="px-4 py-12 text-center">
                  <div className="w-5 h-5 border-2 border-surface-300 border-t-sap-blue rounded-full animate-spin mx-auto" />
                </td></tr>
              ) : clientes.length === 0 ? (
                <tr><td colSpan={7} className="px-4 py-12 text-center text-[13px] text-brand-400">
                  {searchQ ? `Sin resultados para "${searchQ}"` : 'No hay clientes registrados'}
                </td></tr>
              ) : clientes.map((c) => (
                <tr key={c.id} className="hover:bg-surface-50 transition-colors">
                  <td className="table-cell">
                    <p className="text-[13px] font-medium text-brand-800">{c.nombre}</p>
                    {c.correo && <p className="text-[11px] text-brand-400">{c.correo}</p>}
                  </td>
                  <td className="table-cell font-mono text-[12px] text-brand-500">{c.rfc || '—'}</td>
                  <td className="table-cell text-[13px] text-brand-500">{c.telefono || '—'}</td>
                  <td className="table-cell">
                    <span className={cn('badge text-[10px]', tipoColors[c.tipo] || tipoColors.MOSTRADOR)}>{c.tipo}</span>
                  </td>
                  <td className="table-cell text-right tabular-nums text-[13px] text-brand-500">{c.total_facturas || 0}</td>
                  <td className="table-cell text-right tabular-nums text-[13px] font-medium text-brand-800">
                    {(c.total_compras || 0) > 0 ? `$${(c.total_compras || 0).toLocaleString('es-MX', { minimumFractionDigits: 2 })}` : '—'}
                  </td>
                  <td className="table-cell">
                    <div className="flex items-center gap-0.5">
                      <button onClick={() => openEdit(c)} className="btn-ghost p-1.5" title="Editar"><Pencil className="w-4 h-4" /></button>
                      <button onClick={() => handleDelete(c)} className="btn-ghost p-1.5 text-brand-300 hover:text-status-critical" title="Eliminar"><Trash2 className="w-4 h-4" /></button>
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      {/* Modal */}
      {showModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-brand-950/40 backdrop-blur-sm">
          <div className="card p-6 w-full max-w-lg mx-4 shadow-modal">
            <div className="flex items-center justify-between mb-4">
              <div className="flex items-center gap-2">
                <Users className="w-5 h-5 text-brand-500" />
                <h2 className="text-[13px] font-semibold text-brand-800">{editingId ? 'Editar Cliente' : 'Nuevo Cliente'}</h2>
              </div>
              <button onClick={() => setShowModal(false)} className="btn-ghost p-1"><X className="w-4 h-4" /></button>
            </div>

            {formError && <div className="p-3 rounded-lg bg-status-critical-muted border border-red-200 text-[12px] text-red-700 mb-4">{formError}</div>}

            <div className="space-y-4">
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                <div className="sm:col-span-2">
                  <label className="label">Nombre / Razón social *</label>
                  <input value={form.nombre} onChange={(e) => setForm((f) => ({ ...f, nombre: e.target.value }))} placeholder="TALLER MECÁNICO EL GÜERO..." className="input-field" />
                </div>
                <div>
                  <label className="label">RFC</label>
                  <input value={form.rfc} onChange={(e) => setForm((f) => ({ ...f, rfc: e.target.value.toUpperCase() }))} placeholder="XAXX010101000" maxLength={13} className="input-field font-mono" />
                </div>
                <div>
                  <label className="label">Tipo</label>
                  <select value={form.tipo} onChange={(e) => setForm((f) => ({ ...f, tipo: e.target.value }))} className="select-field">
                    <option value="MOSTRADOR">Mostrador</option>
                    <option value="CREDITO">Crédito</option>
                    <option value="TALLER">Taller</option>
                  </select>
                </div>
              </div>
              <div>
                <label className="label">Dirección</label>
                <input value={form.direccion} onChange={(e) => setForm((f) => ({ ...f, direccion: e.target.value }))} placeholder="Calle, número, colonia, CP..." className="input-field" />
              </div>
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                <div>
                  <label className="label">Teléfono</label>
                  <input value={form.telefono} onChange={(e) => setForm((f) => ({ ...f, telefono: e.target.value }))} placeholder="447 123 4567" className="input-field" />
                </div>
                <div>
                  <label className="label">Correo</label>
                  <input value={form.correo} onChange={(e) => setForm((f) => ({ ...f, correo: e.target.value }))} placeholder="cliente@email.com" className="input-field" />
                </div>
              </div>
              <div>
                <label className="label">Notas</label>
                <input value={form.notas} onChange={(e) => setForm((f) => ({ ...f, notas: e.target.value }))} placeholder="Observaciones..." className="input-field" />
              </div>
            </div>

            <div className="flex items-center justify-end gap-3 mt-6 pt-4 border-t border-surface-200">
              <button onClick={() => setShowModal(false)} className="btn-secondary">Cancelar</button>
              <button onClick={handleSubmit} disabled={saving} className="btn-primary">
                <Save className="w-4 h-4" /> {saving ? 'Guardando...' : editingId ? 'Actualizar' : 'Guardar'}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
