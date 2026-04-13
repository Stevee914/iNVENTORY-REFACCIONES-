import { useEffect, useState } from 'react';
import { Plus, Pencil, Trash2, Truck, AlertTriangle, X, Save } from 'lucide-react';
import { PageHeader } from '@/components/shared';
import { proveedorService } from '@/services';
import type { Proveedor, ProveedorFormData } from '@/types';

const emptyForm: ProveedorFormData = { nombre: '', codigo_corto: '', rfc: '' };

export function ProveedoresPage() {
  const [proveedores, setProveedores] = useState<Proveedor[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  const [showModal, setShowModal] = useState(false);
  const [editingId, setEditingId] = useState<number | null>(null);
  const [form, setForm] = useState<ProveedorFormData>(emptyForm);
  const [formError, setFormError] = useState('');
  const [saving, setSaving] = useState(false);

  async function load() {
    try {
      const data = await proveedorService.getAll();
      setProveedores(data);
    } catch (e: any) {
      setError(e.message);
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => { load(); }, []);

  function openNew() {
    setForm(emptyForm);
    setEditingId(null);
    setFormError('');
    setShowModal(true);
  }

  function openEdit(p: Proveedor) {
    setForm({ nombre: p.nombre, codigo_corto: p.codigo_corto, rfc: p.rfc || '' });
    setEditingId(p.id);
    setFormError('');
    setShowModal(true);
  }

  async function handleSubmit() {
    if (!form.nombre.trim() || !form.codigo_corto.trim()) {
      setFormError('Nombre y código corto son obligatorios');
      return;
    }
    setSaving(true);
    setFormError('');
    try {
      if (editingId) {
        await proveedorService.update(editingId, form);
      } else {
        await proveedorService.create(form);
      }
      setShowModal(false);
      await load();
    } catch (e: any) {
      setFormError(e.message);
    } finally {
      setSaving(false);
    }
  }

  async function handleDelete(p: Proveedor) {
    if (!confirm(`¿Eliminar proveedor "${p.nombre}"?`)) return;
    try {
      await proveedorService.delete(p.id);
      await load();
    } catch (e: any) {
      alert(e.message);
    }
  }

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
        title="Proveedores"
        description={`${proveedores.length} proveedores registrados`}
        actions={
          <button onClick={openNew} className="btn-primary">
            <Plus className="w-4 h-4" /> Nuevo Proveedor
          </button>
        }
      />

      <div className="card overflow-hidden">
        <table className="w-full">
          <thead>
            <tr className="bg-surface-50 border-b border-surface-200">
              <th className="table-header">ID</th>
              <th className="table-header">Nombre</th>
              <th className="table-header">Código Corto</th>
              <th className="table-header">RFC</th>
              <th className="table-header">Creado</th>
              <th className="table-header w-24"></th>
            </tr>
          </thead>
          <tbody className="divide-y divide-surface-100">
            {proveedores.length === 0 ? (
              <tr>
                <td colSpan={6} className="px-4 py-12 text-center text-[13px] text-brand-400">
                  No hay proveedores registrados
                </td>
              </tr>
            ) : (
              proveedores.map((p) => (
                <tr key={p.id} className="hover:bg-surface-50">
                  <td className="table-cell text-xs text-brand-400 tabular-nums">{p.id}</td>
                  <td className="table-cell font-medium">{p.nombre}</td>
                  <td className="table-cell">
                    <span className="badge bg-brand-50 text-brand-600 font-mono">{p.codigo_corto}</span>
                  </td>
                  <td className="table-cell text-xs text-brand-500 font-mono">{p.rfc || '—'}</td>
                  <td className="table-cell text-xs text-brand-400">
                    {new Date(p.created_at).toLocaleDateString('es-MX')}
                  </td>
                  <td className="table-cell">
                    <div className="flex items-center gap-0.5">
                      <button onClick={() => openEdit(p)} className="btn-ghost p-1.5" title="Editar">
                        <Pencil className="w-4 h-4" />
                      </button>
                      <button onClick={() => handleDelete(p)} className="btn-ghost p-1.5 text-red-500 hover:text-red-700" title="Eliminar">
                        <Trash2 className="w-4 h-4" />
                      </button>
                    </div>
                  </td>
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>

      {/* Modal */}
      {showModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-brand-950/40 backdrop-blur-sm">
          <div className="card p-6 w-full max-w-md mx-4 shadow-modal">
            <div className="flex items-center justify-between mb-4">
              <div className="flex items-center gap-2">
                <Truck className="w-5 h-5 text-brand-500" />
                <h2 className="text-[13px] font-semibold text-brand-800">
                  {editingId ? 'Editar Proveedor' : 'Nuevo Proveedor'}
                </h2>
              </div>
              <button onClick={() => setShowModal(false)} className="btn-ghost p-1">
                <X className="w-4 h-4" />
              </button>
            </div>

            {formError && (
              <div className="p-3 rounded-lg bg-status-critical-muted border border-red-200 text-[13px] text-red-700 mb-4">{formError}</div>
            )}

            <div className="space-y-4">
              <div>
                <label className="label">Nombre *</label>
                <input
                  value={form.nombre}
                  onChange={(e) => setForm((f) => ({ ...f, nombre: e.target.value }))}
                  placeholder="Gonher, Monroe, KYB..."
                  className="input-field"
                />
              </div>
              <div>
                <label className="label">Código Corto *</label>
                <input
                  value={form.codigo_corto}
                  onChange={(e) => setForm((f) => ({ ...f, codigo_corto: e.target.value.toUpperCase() }))}
                  placeholder="GON, MON, KYB..."
                  maxLength={10}
                  className="input-field font-mono"
                />
                <p className="text-[10px] text-brand-400 mt-0.5">Abreviatura única para etiquetas</p>
              </div>
              <div>
                <label className="label">RFC</label>
                <input
                  value={form.rfc}
                  onChange={(e) => setForm((f) => ({ ...f, rfc: e.target.value.toUpperCase() }))}
                  placeholder="XAXX010101000"
                  maxLength={13}
                  className="input-field font-mono"
                />
              </div>
            </div>

            <div className="flex items-center justify-end gap-3 mt-6 pt-4 border-t border-surface-200">
              <button onClick={() => setShowModal(false)} className="btn-secondary">Cancelar</button>
              <button onClick={handleSubmit} disabled={saving} className="btn-primary">
                <Save className="w-4 h-4" />
                {saving ? 'Guardando...' : editingId ? 'Actualizar' : 'Guardar'}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
