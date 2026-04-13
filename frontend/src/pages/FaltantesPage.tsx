import { useEffect, useRef, useState } from 'react';
import { Plus, Check, X, Truck, Search, AlertTriangle, ShoppingCart, Package, FileDown, Pencil, ClipboardCheck } from 'lucide-react';
import { PageHeader } from '@/components/shared';
import { faltantesService, type Faltante, type FaltanteGrupo } from '@/services/faltantes';
import { productService } from '@/services';
import { comprasService } from '@/services';
import { formatDateTime } from '@/lib/utils';
import { cn } from '@/lib/utils';
import { generarOrdenCompra } from '@/lib/generarOrdenCompra';
import type { Product } from '@/types';

type TabId = 'lista' | 'por-proveedor';

export function FaltantesPage() {
  const [tab, setTab] = useState<TabId>('lista');
  const [faltantes, setFaltantes] = useState<Faltante[]>([]);
  const [grupos, setGrupos] = useState<FaltanteGrupo[]>([]);
  const [products, setProducts] = useState<Product[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  // Filtro
  const [statusFilter, setStatusFilter] = useState<string>('pendiente');

  // Form
  const [showForm, setShowForm] = useState(false);
  const [searchQ, setSearchQ] = useState('');
  const [selectedProduct, setSelectedProduct] = useState<Product | null>(null);
  const [cantidad, setCantidad] = useState<number>(1);
  const [comentario, setComentario] = useState('');
  const [saving, setSaving] = useState(false);
  const [formError, setFormError] = useState('');

  // Edit modal
  const [showEditModal, setShowEditModal]     = useState(false);
  const [editingId, setEditingId]             = useState<number | null>(null);
  const [editProduct, setEditProduct]         = useState<Product | null>(null);
  const [editSearchQ, setEditSearchQ]         = useState('');
  const [editCantidad, setEditCantidad]       = useState<number>(1);
  const [editComentario, setEditComentario]   = useState('');
  const [editStatus, setEditStatus]           = useState('pendiente');
  const [editSaving, setEditSaving]           = useState(false);
  const [editError, setEditError]             = useState('');

  // Modal: Generar Orden PDF (DO NOT MODIFY)
  const [showOrdenModal, setShowOrdenModal] = useState(false);
  const [ordenGrupo, setOrdenGrupo] = useState<FaltanteGrupo | null>(null);
  const [ordenObs, setOrdenObs] = useState('');

  // Selection state for "por proveedor" tab
  const [selectedFaltantes, setSelectedFaltantes] = useState<Record<string, Set<number>>>({});

  // Modal: Registrar en Sistema
  const [showRegistrarModal, setShowRegistrarModal] = useState(false);
  const [registrarGrupo, setRegistrarGrupo]         = useState<FaltanteGrupo | null>(null);
  const [registrarNotas, setRegistrarNotas]         = useState('');
  const [registrando, setRegistrando]               = useState(false);
  const [registrarError, setRegistrarError]         = useState('');

  // Toast
  const [toast, setToast] = useState<{ msg: string; type: 'success' | 'warn' } | null>(null);
  const toastTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  function showToast(msg: string, type: 'success' | 'warn') {
    setToast({ msg, type });
    if (toastTimerRef.current) clearTimeout(toastTimerRef.current);
    toastTimerRef.current = setTimeout(() => setToast(null), 6000);
  }

  // ── Selection helpers ──────────────────────────────────────────────────────

  function toggleFaltante(provNombre: string, faltanteId: number) {
    setSelectedFaltantes((prev) => {
      const set = new Set(prev[provNombre] ?? []);
      if (set.has(faltanteId)) set.delete(faltanteId);
      else set.add(faltanteId);
      return { ...prev, [provNombre]: set };
    });
  }

  function toggleAll(grupo: FaltanteGrupo) {
    const key = grupo.proveedor_nombre;
    const allIds = grupo.productos.map((p) => p.faltante_id);
    const current = selectedFaltantes[key] ?? new Set<number>();
    const allSelected = allIds.every((id) => current.has(id));
    setSelectedFaltantes((prev) => ({
      ...prev,
      [key]: allSelected ? new Set() : new Set(allIds),
    }));
  }

  // ── Orden PDF helpers (DO NOT MODIFY) ────────────────────────────────────

  function handleGenerarOrden(grupo: FaltanteGrupo) {
    setOrdenGrupo(grupo);
    setOrdenObs('');
    setShowOrdenModal(true);
  }

  function confirmarOrden() {
    if (ordenGrupo) {
      generarOrdenCompra(ordenGrupo, ordenObs);
      setShowOrdenModal(false);
      setOrdenGrupo(null);
      setOrdenObs('');
    }
  }

  // ── Registrar en Sistema helpers ──────────────────────────────────────────

  function handleRegistrar(grupo: FaltanteGrupo) {
    setRegistrarGrupo(grupo);
    setRegistrarNotas('');
    setRegistrarError('');
    setShowRegistrarModal(true);
  }

  async function confirmarRegistrar() {
    if (!registrarGrupo) return;
    const key = registrarGrupo.proveedor_nombre;
    const selected = Array.from(selectedFaltantes[key] ?? []);
    if (selected.length === 0) return;

    setRegistrando(true);
    setRegistrarError('');
    try {
      const res = await comprasService.registrarCompraFromFaltantes({
        proveedor_id: registrarGrupo.proveedor_id!,
        faltante_ids: selected,
        notas: registrarNotas || undefined,
      });
      setShowRegistrarModal(false);
      setSelectedFaltantes((prev) => ({ ...prev, [key]: new Set() }));
      const msg = `Compra #${res.compra_id} registrada — ${res.lineas_creadas} producto${res.lineas_creadas !== 1 ? 's' : ''}`;
      showToast(msg, res.errores_validacion.length > 0 ? 'warn' : 'success');
      await loadData();
    } catch (e: any) {
      setRegistrarError(e.message);
    } finally {
      setRegistrando(false);
    }
  }

  // ── Data loading ──────────────────────────────────────────────────────────

  async function loadData() {
    try {
      const [faltRes, grupoRes] = await Promise.all([
        faltantesService.getAll(statusFilter || undefined),
        faltantesService.getPorProveedor(),
      ]);
      setFaltantes(faltRes.items);
      setGrupos(grupoRes.grupos);
    } catch (e: any) {
      setError(e.message);
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => { loadData(); }, [statusFilter]);

  useEffect(() => {
    productService.getAll().then(setProducts).catch(() => {});
  }, []);

  // Búsqueda de productos filtrada
  const filteredProducts = searchQ.length >= 2
    ? products.filter((p) => {
        const q = searchQ.toLowerCase();
        return p.sku.toLowerCase().includes(q) ||
               p.name.toLowerCase().includes(q) ||
               (p.marca || '').toLowerCase().includes(q);
      }).slice(0, 8)
    : [];

  async function handleSubmit() {
    if (!selectedProduct) {
      setFormError('Selecciona un producto');
      return;
    }
    if (cantidad <= 0) {
      setFormError('La cantidad debe ser mayor a 0');
      return;
    }
    setSaving(true);
    setFormError('');
    try {
      await faltantesService.create({
        product_id: selectedProduct.id,
        cantidad_faltante: cantidad,
        comentario: comentario || undefined,
      });
      setShowForm(false);
      setSelectedProduct(null);
      setSearchQ('');
      setCantidad(1);
      setComentario('');
      await loadData();
    } catch (e: any) {
      setFormError(e.message);
    } finally {
      setSaving(false);
    }
  }

  function openEdit(f: Faltante) {
    setEditingId(f.id);
    setEditProduct({ id: f.product_id, sku: f.sku, name: f.product_name, marca: f.marca } as Product);
    setEditSearchQ('');
    setEditCantidad(f.cantidad_faltante);
    setEditComentario(f.comentario ?? '');
    setEditStatus(f.status);
    setEditError('');
    setShowEditModal(true);
  }

  async function handleEditSave() {
    if (!editingId) return;
    if (!editProduct) { setEditError('Selecciona un producto'); return; }
    if (editCantidad <= 0) { setEditError('La cantidad debe ser mayor a 0'); return; }
    setEditSaving(true);
    setEditError('');
    try {
      await faltantesService.update(editingId, {
        product_id:        editProduct.id,
        cantidad_faltante: editCantidad,
        comentario:        editComentario || null,
        status:            editStatus,
      });
      setShowEditModal(false);
      await loadData();
    } catch (e: any) {
      setEditError(e.message);
    } finally {
      setEditSaving(false);
    }
  }

  async function markAs(id: number, status: string) {
    try {
      await faltantesService.updateStatus(id, status);
      await loadData();
    } catch (e: any) {
      alert(e.message);
    }
  }

  const statusColors: Record<string, string> = {
    pendiente: 'bg-amber-50 text-amber-700 border-amber-200',
    comprado: 'bg-emerald-50 text-emerald-700 border-emerald-200',
    cancelado: 'bg-surface-100 text-brand-400 border-surface-200',
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="w-6 h-6 border-2 border-brand-300 border-t-brand-700 rounded-full animate-spin" />
      </div>
    );
  }

  if (error) {
    return (
      <div className="card p-8 text-center">
        <AlertTriangle className="w-10 h-10 mx-auto text-status-critical mb-3" />
        <p className="text-sm text-brand-500">{error}</p>
      </div>
    );
  }

  const pendientesCount = faltantes.filter((f) => f.status === 'pendiente').length;

  return (
    <div>
      <PageHeader
        title="Faltantes / Compras"
        description={`${pendientesCount} productos pendientes por comprar`}
        actions={
          <button onClick={() => setShowForm(true)} className="btn-primary">
            <Plus className="w-4 h-4" /> Registrar Faltante
          </button>
        }
      />

      {/* Tabs */}
      <div className="flex items-center gap-1 mb-6 border-b border-surface-200">
        {([
          { id: 'lista' as TabId, label: 'Lista de Faltantes' },
          { id: 'por-proveedor' as TabId, label: 'Por Proveedor' },
        ]).map((t) => (
          <button
            key={t.id}
            onClick={() => setTab(t.id)}
            className={`px-4 py-2.5 text-sm font-medium border-b-2 transition-colors ${
              tab === t.id
                ? 'border-brand-800 text-brand-800'
                : 'border-transparent text-brand-400 hover:text-brand-600'
            }`}
          >
            {t.label}
          </button>
        ))}
      </div>

      {/* Toast */}
      {toast && (
        <div
          className={cn(
            'fixed bottom-6 right-6 z-[60] flex items-start gap-3 px-4 py-3 rounded-xl shadow-lg border max-w-sm',
            toast.type === 'success'
              ? 'bg-emerald-50 border-emerald-200 text-emerald-800'
              : 'bg-amber-50 border-amber-200 text-amber-800',
          )}
        >
          <p className="text-sm font-medium flex-1">{toast.msg}</p>
          <button onClick={() => setToast(null)} className="shrink-0 opacity-60 hover:opacity-100">
            <X className="w-4 h-4" />
          </button>
        </div>
      )}

      {/* Modal: Registrar Faltante */}
      {showForm && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/30 backdrop-blur-sm">
          <div className="card p-6 w-full max-w-md mx-4">
            <div className="flex items-center justify-between mb-4">
              <div className="flex items-center gap-2">
                <ShoppingCart className="w-5 h-5 text-brand-500" />
                <h2 className="text-sm font-semibold text-brand-800">Registrar Faltante</h2>
              </div>
              <button onClick={() => { setShowForm(false); setFormError(''); }} className="btn-ghost p-1">
                <X className="w-4 h-4" />
              </button>
            </div>

            {formError && (
              <div className="p-3 rounded-lg bg-red-50 border border-red-200 text-sm text-red-700 mb-4">{formError}</div>
            )}

            <div className="space-y-4">
              <div>
                <label className="label">Producto *</label>
                {selectedProduct ? (
                  <div className="flex items-center justify-between p-3 rounded-lg bg-surface-50 border border-surface-200">
                    <div>
                      <p className="text-sm font-medium text-brand-800">{selectedProduct.sku} — {selectedProduct.name}</p>
                      {selectedProduct.marca && <p className="text-xs text-brand-400">{selectedProduct.marca}</p>}
                    </div>
                    <button onClick={() => { setSelectedProduct(null); setSearchQ(''); }} className="text-brand-400 hover:text-brand-600">
                      <X className="w-4 h-4" />
                    </button>
                  </div>
                ) : (
                  <div className="relative">
                    <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-brand-300" />
                    <input
                      value={searchQ}
                      onChange={(e) => setSearchQ(e.target.value)}
                      placeholder="Buscar por SKU, nombre o marca..."
                      className="input-field pl-10"
                      autoFocus
                    />
                    {filteredProducts.length > 0 && (
                      <div className="absolute z-10 w-full mt-1 bg-white border border-surface-200 rounded-lg shadow-lg max-h-48 overflow-y-auto">
                        {filteredProducts.map((p) => (
                          <button
                            key={p.id}
                            onClick={() => { setSelectedProduct(p); setSearchQ(''); }}
                            className="w-full text-left px-3 py-2 hover:bg-surface-50 border-b border-surface-100 last:border-0"
                          >
                            <p className="text-sm font-medium text-brand-800">{p.sku} — {p.name}</p>
                            {p.marca && <p className="text-xs text-brand-400">{p.marca}</p>}
                          </button>
                        ))}
                      </div>
                    )}
                  </div>
                )}
              </div>

              <div>
                <label className="label">Cantidad faltante *</label>
                <input
                  type="number"
                  value={cantidad}
                  onChange={(e) => setCantidad(parseFloat(e.target.value) || 0)}
                  min={1}
                  className="input-field tabular-nums text-lg font-bold"
                />
              </div>

              <div>
                <label className="label">Comentario</label>
                <input
                  value={comentario}
                  onChange={(e) => setComentario(e.target.value)}
                  placeholder="Cliente lo pidió, se agotó, etc..."
                  className="input-field"
                />
              </div>
            </div>

            <div className="flex items-center justify-end gap-3 mt-6 pt-4 border-t border-surface-100">
              <button onClick={() => setShowForm(false)} className="btn-secondary">Cancelar</button>
              <button onClick={handleSubmit} disabled={saving} className="btn-primary">
                <ShoppingCart className="w-4 h-4" />
                {saving ? 'Guardando...' : 'Registrar'}
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Modal: Editar Faltante */}
      {showEditModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/30 backdrop-blur-sm">
          <div className="card p-6 w-full max-w-md mx-4">
            <div className="flex items-center justify-between mb-4">
              <div className="flex items-center gap-2">
                <Pencil className="w-4 h-4 text-brand-500" />
                <h2 className="text-sm font-semibold text-brand-800">Editar Faltante</h2>
              </div>
              <button onClick={() => setShowEditModal(false)} className="btn-ghost p-1">
                <X className="w-4 h-4" />
              </button>
            </div>

            {editError && (
              <div className="p-3 rounded-lg bg-red-50 border border-red-200 text-sm text-red-700 mb-4">{editError}</div>
            )}

            <div className="space-y-4">
              <div>
                <label className="label">Producto *</label>
                {editProduct ? (
                  <div className="flex items-center justify-between p-3 rounded-lg bg-surface-50 border border-surface-200">
                    <div>
                      <p className="text-sm font-medium text-brand-800">{editProduct.sku} — {editProduct.name}</p>
                      {editProduct.marca && <p className="text-xs text-brand-400">{editProduct.marca}</p>}
                    </div>
                    <button onClick={() => { setEditProduct(null); setEditSearchQ(''); }} className="text-brand-400 hover:text-brand-600">
                      <X className="w-4 h-4" />
                    </button>
                  </div>
                ) : (
                  <div className="relative">
                    <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-brand-300" />
                    <input
                      value={editSearchQ}
                      onChange={(e) => setEditSearchQ(e.target.value)}
                      placeholder="Buscar por SKU, nombre o marca..."
                      className="input-field pl-10"
                      autoFocus
                    />
                    {editSearchQ.length >= 2 && (
                      <div className="absolute z-10 w-full mt-1 bg-white border border-surface-200 rounded-lg shadow-lg max-h-48 overflow-y-auto">
                        {products
                          .filter(p => {
                            const q = editSearchQ.toLowerCase();
                            return p.sku.toLowerCase().includes(q) ||
                                   p.name.toLowerCase().includes(q) ||
                                   (p.marca || '').toLowerCase().includes(q);
                          })
                          .slice(0, 8)
                          .map(p => (
                            <button
                              key={p.id}
                              onClick={() => { setEditProduct(p); setEditSearchQ(''); }}
                              className="w-full text-left px-3 py-2 hover:bg-surface-50 border-b border-surface-100 last:border-0"
                            >
                              <p className="text-sm font-medium text-brand-800">{p.sku} — {p.name}</p>
                              {p.marca && <p className="text-xs text-brand-400">{p.marca}</p>}
                            </button>
                          ))}
                      </div>
                    )}
                  </div>
                )}
              </div>

              <div>
                <label className="label">Cantidad faltante *</label>
                <input
                  type="number"
                  value={editCantidad}
                  onChange={(e) => setEditCantidad(parseFloat(e.target.value) || 0)}
                  min={1}
                  className="input-field tabular-nums text-lg font-bold"
                />
              </div>

              <div>
                <label className="label">Comentario</label>
                <input
                  value={editComentario}
                  onChange={(e) => setEditComentario(e.target.value)}
                  placeholder="Cliente lo pidió, se agotó, etc..."
                  className="input-field"
                />
              </div>

              <div>
                <label className="label">Status</label>
                <select
                  value={editStatus}
                  onChange={(e) => setEditStatus(e.target.value)}
                  className="select-field w-full"
                >
                  <option value="pendiente">Pendiente</option>
                  <option value="comprado">Comprado</option>
                  <option value="cancelado">Cancelado</option>
                </select>
              </div>
            </div>

            <div className="flex items-center justify-end gap-3 mt-6 pt-4 border-t border-surface-100">
              <button onClick={() => setShowEditModal(false)} className="btn-secondary">Cancelar</button>
              <button onClick={handleEditSave} disabled={editSaving} className="btn-primary">
                {editSaving ? 'Guardando...' : 'Guardar cambios'}
              </button>
            </div>
          </div>
        </div>
      )}

      {/* TAB: Lista */}
      {tab === 'lista' && (
        <>
          <div className="card p-4 mb-4">
            <div className="flex items-center gap-3">
              <select
                value={statusFilter}
                onChange={(e) => setStatusFilter(e.target.value)}
                className="select-field w-48 py-2 text-xs"
              >
                <option value="">Todos</option>
                <option value="pendiente">Pendientes</option>
                <option value="comprado">Comprados</option>
                <option value="cancelado">Cancelados</option>
              </select>
              <span className="text-xs text-brand-400 ml-auto">
                {faltantes.length} registro{faltantes.length !== 1 ? 's' : ''}
              </span>
            </div>
          </div>

          <div className="card overflow-hidden">
            <table className="w-full">
              <thead>
                <tr className="bg-surface-50 border-b border-surface-100">
                  <th className="table-header">SKU</th>
                  <th className="table-header">Producto</th>
                  <th className="table-header text-right">Cant.</th>
                  <th className="table-header">Proveedor</th>
                  <th className="table-header">Comentario</th>
                  <th className="table-header">Fecha</th>
                  <th className="table-header">Status</th>
                  <th className="table-header w-28"></th>
                </tr>
              </thead>
              <tbody className="divide-y divide-surface-100">
                {faltantes.length === 0 ? (
                  <tr>
                    <td colSpan={8} className="px-4 py-12 text-center text-sm text-brand-400">
                      No hay faltantes registrados
                    </td>
                  </tr>
                ) : (
                  faltantes.map((f) => (
                    <tr key={f.id} className="hover:bg-surface-50/50">
                      <td className="table-cell font-mono text-xs font-medium text-brand-600">{f.sku}</td>
                      <td className="table-cell">
                        <p className="text-sm text-brand-800 truncate max-w-[200px]">{f.product_name}</p>
                        {f.marca && <p className="text-xs text-brand-400">{f.marca}</p>}
                      </td>
                      <td className="table-cell text-right tabular-nums font-bold text-brand-800">{f.cantidad_faltante}</td>
                      <td className="table-cell">
                        {f.proveedor_nombre ? (
                          <span className="badge bg-blue-50 text-blue-700 border border-blue-200 text-[10px]">
                            {f.proveedor_nombre}
                          </span>
                        ) : (
                          <span className="text-xs text-brand-300 italic">Sin proveedor</span>
                        )}
                      </td>
                      <td className="table-cell text-xs text-brand-500 truncate max-w-[150px]">{f.comentario || '—'}</td>
                      <td className="table-cell text-xs text-brand-400 whitespace-nowrap">{formatDateTime(f.fecha_detectado)}</td>
                      <td className="table-cell">
                        <span className={cn('badge border text-[10px]', statusColors[f.status])}>
                          {f.status}
                        </span>
                      </td>
                      <td className="table-cell">
                        <div className="flex items-center gap-0.5">
                          <button
                            onClick={() => openEdit(f)}
                            className="btn-ghost p-1.5 text-brand-400 hover:text-brand-700"
                            title="Editar"
                          >
                            <Pencil className="w-3.5 h-3.5" />
                          </button>
                          {f.status === 'pendiente' && (
                            <>
                              <button
                                onClick={() => markAs(f.id, 'comprado')}
                                className="btn-ghost p-1.5 text-emerald-600 hover:text-emerald-800"
                                title="Marcar comprado"
                              >
                                <Check className="w-4 h-4" />
                              </button>
                              <button
                                onClick={() => markAs(f.id, 'cancelado')}
                                className="btn-ghost p-1.5 text-red-400 hover:text-red-600"
                                title="Cancelar"
                              >
                                <X className="w-4 h-4" />
                              </button>
                            </>
                          )}
                        </div>
                      </td>
                    </tr>
                  ))
                )}
              </tbody>
            </table>
          </div>
        </>
      )}

      {/* TAB: Por proveedor */}
      {tab === 'por-proveedor' && (
        <div className="space-y-4">
          {grupos.length === 0 ? (
            <div className="card p-12 text-center text-brand-400">
              <Package className="w-10 h-10 mx-auto mb-3 text-brand-200" />
              <p className="text-sm">No hay faltantes pendientes</p>
            </div>
          ) : (
            grupos.map((g) => {
              const key = g.proveedor_nombre;
              const sel = selectedFaltantes[key] ?? new Set<number>();
              const allIds = g.productos.map((p) => p.faltante_id);
              const allChecked = allIds.length > 0 && allIds.every((id) => sel.has(id));
              const someChecked = allIds.some((id) => sel.has(id));
              const selCount = sel.size;
              const canRegister = g.proveedor_id !== null && selCount > 0;

              return (
                <div key={key} className="card overflow-hidden">
                  <div className="p-4 border-b border-surface-100 flex items-center justify-between">
                    <div className="flex items-center gap-2">
                      <Truck className="w-4 h-4 text-brand-500" />
                      <h3 className="text-sm font-semibold text-brand-800">{g.proveedor_nombre}</h3>
                      <span className="badge bg-surface-100 text-brand-500 text-[10px]">{g.total_items} productos</span>
                    </div>
                    <div className="flex items-center gap-2">
                      <button
                        onClick={() => handleRegistrar(g)}
                        disabled={!canRegister}
                        className="btn-secondary text-[12px] px-3 py-1.5 disabled:opacity-40 disabled:cursor-not-allowed"
                        title={
                          g.proveedor_id === null
                            ? 'Este grupo no tiene proveedor asignado'
                            : selCount === 0
                            ? 'Selecciona al menos un faltante'
                            : `Registrar ${selCount} producto${selCount !== 1 ? 's' : ''} en el sistema`
                        }
                      >
                        <ClipboardCheck className="w-3.5 h-3.5" />
                        {selCount > 0 ? `Registrar (${selCount})` : 'Registrar en Sistema'}
                      </button>
                      <button
                        onClick={() => handleGenerarOrden(g)}
                        className="btn-primary text-[12px] px-3 py-1.5"
                        title={`Generar orden de compra para ${g.proveedor_nombre}`}
                      >
                        <FileDown className="w-3.5 h-3.5" /> Generar Orden
                      </button>
                    </div>
                  </div>
                  <table className="w-full">
                    <thead>
                      <tr className="bg-surface-50 border-b border-surface-100">
                        <th className="table-header w-10 text-center">
                          <input
                            type="checkbox"
                            checked={allChecked}
                            ref={(el) => {
                              if (el) el.indeterminate = someChecked && !allChecked;
                            }}
                            onChange={() => toggleAll(g)}
                            className="w-3.5 h-3.5 rounded border-surface-300 accent-brand-700 cursor-pointer"
                            title="Seleccionar todos"
                          />
                        </th>
                        <th className="table-header">SKU</th>
                        <th className="table-header">Producto</th>
                        <th className="table-header text-right">Cantidad</th>
                        <th className="table-header">Comentario</th>
                        <th className="table-header">Fecha</th>
                        <th className="table-header w-20"></th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-surface-100">
                      {g.productos.map((p) => (
                        <tr
                          key={p.faltante_id}
                          className={cn('hover:bg-surface-50/50', sel.has(p.faltante_id) && 'bg-blue-50/40')}
                        >
                          <td className="table-cell text-center">
                            <input
                              type="checkbox"
                              checked={sel.has(p.faltante_id)}
                              onChange={() => toggleFaltante(key, p.faltante_id)}
                              className="w-3.5 h-3.5 rounded border-surface-300 accent-brand-700 cursor-pointer"
                            />
                          </td>
                          <td className="table-cell font-mono text-xs font-medium text-brand-600">{p.sku}</td>
                          <td className="table-cell">
                            <p className="text-sm text-brand-800 truncate max-w-[200px]">{p.product_name}</p>
                            {p.marca && <p className="text-xs text-brand-400">{p.marca}</p>}
                          </td>
                          <td className="table-cell text-right tabular-nums font-bold">{p.cantidad_faltante}</td>
                          <td className="table-cell text-xs text-brand-500 truncate max-w-[150px]">{p.comentario || '—'}</td>
                          <td className="table-cell text-xs text-brand-400 whitespace-nowrap">{formatDateTime(p.fecha_detectado)}</td>
                          <td className="table-cell">
                            <button
                              onClick={() => markAs(p.faltante_id, 'comprado')}
                              className="btn-ghost p-1.5 text-emerald-600 hover:text-emerald-800"
                              title="Marcar comprado"
                            >
                              <Check className="w-4 h-4" />
                            </button>
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              );
            })
          )}
        </div>
      )}

      {/* Modal: Observaciones para Orden de Compra (DO NOT MODIFY) */}
      {showOrdenModal && ordenGrupo && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/30 backdrop-blur-sm">
          <div className="card p-6 w-full max-w-md mx-4">
            <div className="flex items-center justify-between mb-4">
              <div className="flex items-center gap-2">
                <FileDown className="w-5 h-5 text-brand-500" />
                <h2 className="text-sm font-semibold text-brand-800">Generar Orden de Compra</h2>
              </div>
              <button onClick={() => setShowOrdenModal(false)} className="btn-ghost p-1">
                <X className="w-4 h-4" />
              </button>
            </div>

            <div className="p-3 rounded-lg bg-surface-50 border border-surface-200 mb-4">
              <p className="text-xs text-brand-400">Proveedor</p>
              <p className="text-sm font-semibold text-brand-800">{ordenGrupo.proveedor_nombre}</p>
              <p className="text-xs text-brand-400 mt-1">{ordenGrupo.total_items} producto{ordenGrupo.total_items !== 1 ? 's' : ''}</p>
            </div>

            <div>
              <label className="label">Observaciones (opcional)</label>
              <textarea
                value={ordenObs}
                onChange={(e) => setOrdenObs(e.target.value)}
                placeholder="Ej: Urgente, entregar antes del viernes. Confirmar precios actualizados..."
                rows={3}
                className="input-field resize-none"
              />
              <p className="text-[10px] text-brand-400 mt-1">Se incluirán en el PDF debajo de la tabla de productos</p>
            </div>

            <div className="flex items-center justify-end gap-3 mt-6 pt-4 border-t border-surface-100">
              <button onClick={() => setShowOrdenModal(false)} className="btn-secondary">
                Cancelar
              </button>
              <button onClick={confirmarOrden} className="btn-primary">
                <FileDown className="w-4 h-4" /> Descargar PDF
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Modal: Registrar en Sistema */}
      {showRegistrarModal && registrarGrupo && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/30 backdrop-blur-sm">
          <div className="card p-6 w-full max-w-lg mx-4">
            <div className="flex items-center justify-between mb-4">
              <div className="flex items-center gap-2">
                <ClipboardCheck className="w-5 h-5 text-brand-500" />
                <h2 className="text-sm font-semibold text-brand-800">Registrar Compra en Sistema</h2>
              </div>
              <button onClick={() => setShowRegistrarModal(false)} className="btn-ghost p-1">
                <X className="w-4 h-4" />
              </button>
            </div>

            {registrarError && (
              <div className="p-3 rounded-lg bg-red-50 border border-red-200 text-sm text-red-700 mb-4">
                {registrarError}
              </div>
            )}

            <div className="p-3 rounded-lg bg-surface-50 border border-surface-200 mb-4">
              <p className="text-xs text-brand-400">Proveedor</p>
              <p className="text-sm font-semibold text-brand-800">{registrarGrupo.proveedor_nombre}</p>
              <p className="text-xs text-brand-400 mt-1">
                {(selectedFaltantes[registrarGrupo.proveedor_nombre] ?? new Set()).size} producto{(selectedFaltantes[registrarGrupo.proveedor_nombre] ?? new Set()).size !== 1 ? 's' : ''} seleccionado{(selectedFaltantes[registrarGrupo.proveedor_nombre] ?? new Set()).size !== 1 ? 's' : ''}
              </p>
            </div>

            {/* Selected products list */}
            <div className="mb-4">
              <p className="text-xs font-medium text-brand-600 mb-2">Productos a registrar</p>
              <div className="max-h-48 overflow-y-auto divide-y divide-surface-100 border border-surface-200 rounded-lg">
                {registrarGrupo.productos
                  .filter((p) => (selectedFaltantes[registrarGrupo.proveedor_nombre] ?? new Set()).has(p.faltante_id))
                  .map((p) => (
                    <div key={p.faltante_id} className="flex items-center justify-between px-3 py-2">
                      <div>
                        <span className="font-mono text-xs text-brand-600">{p.sku}</span>
                        <span className="text-xs text-brand-700 ml-2 truncate max-w-[200px] inline-block align-bottom">{p.product_name}</span>
                      </div>
                      <span className="tabular-nums text-xs font-bold text-brand-800 shrink-0 ml-2">×{p.cantidad_faltante}</span>
                    </div>
                  ))}
              </div>
            </div>

            <div>
              <label className="label">Observaciones (opcional)</label>
              <textarea
                value={registrarNotas}
                onChange={(e) => setRegistrarNotas(e.target.value)}
                placeholder="Ej: Urgente, precio acordado, condiciones especiales..."
                rows={3}
                className="input-field resize-none"
              />
            </div>

            <div className="flex items-center justify-end gap-3 mt-6 pt-4 border-t border-surface-100">
              <button onClick={() => setShowRegistrarModal(false)} className="btn-secondary" disabled={registrando}>
                Cancelar
              </button>
              <button onClick={confirmarRegistrar} disabled={registrando} className="btn-primary">
                <ClipboardCheck className="w-4 h-4" />
                {registrando ? 'Registrando...' : 'Registrar Compra'}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
