import { useEffect, useState } from 'react';
import { Plus, Pencil, FolderTree, ChevronRight, AlertTriangle, X, Save } from 'lucide-react';
import { PageHeader } from '@/components/shared';
import { categoriaService } from '@/services';
import { cn } from '@/lib/utils';
import type { Categoria, CategoriaFormData } from '@/types';

const emptyForm: CategoriaFormData = { name: '', description: '', parent_id: null };

function ProductCount({ count }: { count?: number }) {
  if (!count) return null;
  return (
    <span className="badge bg-brand-100 text-brand-500 text-[10px]">{count} prod.</span>
  );
}

export function CategoriasPage() {
  const [tree, setTree] = useState<Categoria[]>([]);
  const [allCats, setAllCats] = useState<Categoria[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  const [showModal, setShowModal] = useState(false);
  const [editingId, setEditingId] = useState<number | null>(null);
  const [form, setForm] = useState<CategoriaFormData>(emptyForm);
  const [formError, setFormError] = useState('');
  const [saving, setSaving] = useState(false);

  async function load() {
    try {
      const [treeData, allData] = await Promise.all([
        categoriaService.getTree(),
        categoriaService.getAll(),
      ]);
      setTree(treeData);
      setAllCats(allData);
    } catch (e: any) {
      setError(e.message);
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => { load(); }, []);

  function openNew(parentId: number | null = null) {
    setForm({ ...emptyForm, parent_id: parentId });
    setEditingId(null);
    setFormError('');
    setShowModal(true);
  }

  function openEdit(c: Categoria) {
    setForm({ name: c.name, description: c.description || '', parent_id: c.parent_id });
    setEditingId(c.id);
    setFormError('');
    setShowModal(true);
  }

  async function handleSubmit() {
    if (!form.name.trim()) {
      setFormError('El nombre es obligatorio');
      return;
    }
    setSaving(true);
    setFormError('');
    try {
      if (editingId) {
        await categoriaService.update(editingId, form);
      } else {
        await categoriaService.create(form);
      }
      setShowModal(false);
      await load();
    } catch (e: any) {
      setFormError(e.message);
    } finally {
      setSaving(false);
    }
  }

  // All non-root categories (level 1+) — usable as parents for grandchildren
  const roots = allCats.filter((c) => c.parent_id === null);
  const nonRoots = allCats.filter((c) => c.parent_id !== null && c.parent_id !== editingId && c.id !== editingId);

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

  const totalProducts = allCats.reduce((sum, c) => sum + 0, 0); // counts come from tree

  return (
    <div>
      <PageHeader
        title="Categorías"
        description={`${allCats.length} categorías — estructura de árbol`}
        actions={
          <button onClick={() => openNew(null)} className="btn-primary">
            <Plus className="w-4 h-4" /> Nueva Categoría
          </button>
        }
      />

      <div className="card p-5">
        {tree.length === 0 ? (
          <p className="text-[13px] text-brand-400 text-center py-8">No hay categorías registradas</p>
        ) : (
          <div className="space-y-1">
            {tree.map((parent) => (
              <div key={parent.id}>
                {/* Level 0 — Root */}
                <div className="flex items-center justify-between p-3 rounded-lg hover:bg-surface-50 group">
                  <div className="flex items-center gap-2">
                    <FolderTree className="w-4 h-4 text-brand-400" />
                    <span className="text-[13px] font-semibold text-brand-800">{parent.name}</span>
                    {parent.description && (
                      <span className="text-xs text-brand-400">— {parent.description}</span>
                    )}
                    <span className="badge bg-surface-100 text-brand-400 text-[10px]">
                      {parent.subcategorias?.length || 0} sub
                    </span>
                    <ProductCount count={parent.total_productos} />
                  </div>
                  <div className="flex items-center gap-1 opacity-0 group-hover:opacity-100 transition-opacity">
                    <button onClick={() => openNew(parent.id)} className="btn-ghost p-1.5 text-xs" title="Agregar subcategoría">
                      <Plus className="w-3.5 h-3.5" />
                    </button>
                    <button onClick={() => openEdit(parent)} className="btn-ghost p-1.5" title="Editar">
                      <Pencil className="w-3.5 h-3.5" />
                    </button>
                  </div>
                </div>

                {/* Level 1 — Children */}
                {parent.subcategorias && parent.subcategorias.length > 0 && (
                  <div className="ml-8 border-l-2 border-surface-100">
                    {parent.subcategorias.map((child) => (
                      <div key={child.id}>
                        <div className="flex items-center justify-between p-2.5 pl-4 hover:bg-surface-50 group rounded-r-lg">
                          <div className="flex items-center gap-2">
                            <ChevronRight className="w-3 h-3 text-brand-300" />
                            <span className="text-[13px] font-medium text-brand-700">{child.name}</span>
                            {child.description && (
                              <span className="text-xs text-brand-400">— {child.description}</span>
                            )}
                            {child.subcategorias && child.subcategorias.length > 0 && (
                              <span className="badge bg-surface-100 text-brand-400 text-[10px]">
                                {child.subcategorias.length} sub
                              </span>
                            )}
                            <ProductCount count={child.total_productos} />
                          </div>
                          <div className="flex items-center gap-1 opacity-0 group-hover:opacity-100 transition-opacity">
                            <button onClick={() => openNew(child.id)} className="btn-ghost p-1.5 text-xs" title="Agregar subcategoría">
                              <Plus className="w-3.5 h-3.5" />
                            </button>
                            <button onClick={() => openEdit(child)} className="btn-ghost p-1" title="Editar">
                              <Pencil className="w-3.5 h-3.5" />
                            </button>
                          </div>
                        </div>

                        {/* Level 2 — Grandchildren */}
                        {child.subcategorias && child.subcategorias.length > 0 && (
                          <div className="ml-8 border-l-2 border-surface-50">
                            {child.subcategorias.map((grandchild) => (
                              <div
                                key={grandchild.id}
                                className="flex items-center justify-between p-2 pl-4 hover:bg-surface-50 group rounded-r-lg"
                              >
                                <div className="flex items-center gap-2">
                                  <ChevronRight className="w-3 h-3 text-brand-200" />
                                  <span className="text-[13px] text-brand-600">{grandchild.name}</span>
                                  {grandchild.description && (
                                    <span className="text-xs text-brand-400">— {grandchild.description}</span>
                                  )}
                                  <ProductCount count={grandchild.total_productos} />
                                </div>
                                <button
                                  onClick={() => openEdit(grandchild)}
                                  className="btn-ghost p-1 opacity-0 group-hover:opacity-100 transition-opacity"
                                  title="Editar"
                                >
                                  <Pencil className="w-3.5 h-3.5" />
                                </button>
                              </div>
                            ))}
                          </div>
                        )}
                      </div>
                    ))}
                  </div>
                )}
              </div>
            ))}
          </div>
        )}
      </div>

      {/* Modal */}
      {showModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-brand-950/40 backdrop-blur-sm">
          <div className="card p-6 w-full max-w-md mx-4 shadow-modal">
            <div className="flex items-center justify-between mb-4">
              <div className="flex items-center gap-2">
                <FolderTree className="w-5 h-5 text-brand-500" />
                <h2 className="text-[13px] font-semibold text-brand-800">
                  {editingId ? 'Editar Categoría' : 'Nueva Categoría'}
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
                  value={form.name}
                  onChange={(e) => setForm((f) => ({ ...f, name: e.target.value }))}
                  placeholder="FILTROS, FRENOS, SUSPENSION..."
                  className="input-field"
                />
              </div>
              <div>
                <label className="label">Descripción</label>
                <input
                  value={form.description}
                  onChange={(e) => setForm((f) => ({ ...f, description: e.target.value }))}
                  placeholder="Descripción opcional..."
                  className="input-field"
                />
              </div>
              <div>
                <label className="label">Categoría Padre</label>
                <select
                  value={form.parent_id ?? ''}
                  onChange={(e) => setForm((f) => ({ ...f, parent_id: e.target.value ? parseInt(e.target.value) : null }))}
                  className="select-field"
                >
                  <option value="">— Ninguna (categoría raíz) —</option>
                  {roots
                    .filter((r) => r.id !== editingId)
                    .map((r) => (
                      <option key={r.id} value={r.id}>{r.name}</option>
                    ))}
                  {nonRoots.length > 0 && (
                    <optgroup label="── Subcategorías ──">
                      {nonRoots.map((c) => (
                        <option key={c.id} value={c.id}>
                          {allCats.find((p) => p.id === c.parent_id)?.name} › {c.name}
                        </option>
                      ))}
                    </optgroup>
                  )}
                </select>
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
