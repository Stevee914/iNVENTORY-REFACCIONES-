import { useState, useEffect } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { Save, ArrowLeft, Plus, Trash2, Star, Search, X, Truck, Pencil, Check } from 'lucide-react';
import { PageHeader } from '@/components/shared';
import { productService, proveedorService } from '@/services';
import { productoProveedorService } from '@/services/productoProveedor';
import type { ProductFormData, Proveedor, ProductoProveedor } from '@/types';

const emptyForm: ProductFormData = {
  sku: '',
  name: '',
  categoria_id: null,
  unit: 'PZA',
  min_stock: 0,
  price: 0,
  precio_publico: 0,
  is_active: true,
  codigo_cat: '',
  codigo_pos: '',
  marca: '',
};

interface FormErrors {
  [key: string]: string;
}

export function ProductFormPage() {
  const { id } = useParams();
  const navigate = useNavigate();
  const isEdit = Boolean(id && id !== 'nuevo');

  const [form, setForm] = useState<ProductFormData>(emptyForm);
  const [errors, setErrors] = useState<FormErrors>({});
  const [saving, setSaving] = useState(false);
  const [loading, setLoading] = useState(isEdit);
  const [submitError, setSubmitError] = useState('');

  // ─── Proveedores del producto ────────────────────────
  const [productId, setProductId] = useState<number | null>(null);
  const [vinculos, setVinculos] = useState<ProductoProveedor[]>([]);
  const [allProveedores, setAllProveedores] = useState<Proveedor[]>([]);
  const [loadingVinculos, setLoadingVinculos] = useState(false);

  // Form agregar vínculo
  const [showAddProv, setShowAddProv] = useState(false);
  const [provSearch, setProvSearch] = useState('');
  const [selectedProv, setSelectedProv] = useState<Proveedor | null>(null);
  const [supplierSku, setSupplierSku] = useState('');
  const [descripcionProv, setDescripcionProv] = useState('');
  const [precioProv, setPrecioProv] = useState<number>(0);
  const [isPrimary, setIsPrimary] = useState(false);
  const [savingVinculo, setSavingVinculo] = useState(false);
  const [vinculoError, setVinculoError] = useState('');

  // Edición inline de vínculo
  const [editingVinculoId, setEditingVinculoId] = useState<number | null>(null);
  const [editSupplierSku, setEditSupplierSku] = useState('');
  const [editDescripcion, setEditDescripcion] = useState('');
  const [editPrecio, setEditPrecio] = useState<number>(0);
  const [savingEdit, setSavingEdit] = useState(false);

  useEffect(() => {
    if (isEdit && id) {
      productService.getBySku(id).then((p) => {
        setForm({
          sku: p.sku, name: p.name, categoria_id: p.categoria_id, unit: p.unit,
          min_stock: p.min_stock, price: p.price ?? 0, precio_publico: p.precio_publico ?? 0,
          is_active: p.is_active,
          codigo_cat: p.codigo_cat || '', codigo_pos: p.codigo_pos || '', marca: p.marca || '',
        });
        setProductId(p.id);
        setLoading(false);
      }).catch(() => setLoading(false));
    }
  }, [id, isEdit]);

  useEffect(() => { if (productId) loadVinculos(); }, [productId]);
  useEffect(() => { proveedorService.getAll().then(setAllProveedores).catch(() => {}); }, []);

  async function loadVinculos() {
    if (!productId) return;
    setLoadingVinculos(true);
    try {
      const res = await productoProveedorService.getByProduct(productId);
      setVinculos(res.items);
    } catch { setVinculos([]); }
    finally { setLoadingVinculos(false); }
  }

  const filteredProveedores = provSearch.length >= 1
    ? allProveedores.filter((p) => {
        const q = provSearch.toLowerCase();
        if (vinculos.some((v) => v.proveedor_id === p.id)) return false;
        return p.nombre.toLowerCase().includes(q) || p.codigo_corto.toLowerCase().includes(q) || (p.rfc || '').toLowerCase().includes(q);
      }).slice(0, 6)
    : [];

  async function handleAddVinculo() {
    if (!selectedProv || !productId) { setVinculoError('Selecciona un proveedor'); return; }
    if (!supplierSku.trim()) { setVinculoError('El código del proveedor es obligatorio'); return; }
    setSavingVinculo(true);
    setVinculoError('');
    try {
      await productoProveedorService.create({
        product_id: productId, proveedor_id: selectedProv.id,
        supplier_sku: supplierSku.trim().toUpperCase(),
        descripcion_proveedor: descripcionProv.trim() || undefined,
        is_primary: isPrimary,
        precio_proveedor: precioProv > 0 ? precioProv : undefined,
      });
      setSelectedProv(null); setProvSearch(''); setSupplierSku(''); setDescripcionProv(''); setPrecioProv(0); setIsPrimary(false); setShowAddProv(false);
      await loadVinculos();
    } catch (err: any) { setVinculoError(err.message || 'Error al vincular proveedor'); }
    finally { setSavingVinculo(false); }
  }

  async function handleDeleteVinculo(vinculoId: number, provNombre: string) {
    if (!confirm(`¿Eliminar vínculo con "${provNombre}"?`)) return;
    try { await productoProveedorService.delete(vinculoId); await loadVinculos(); }
    catch (err: any) { alert(err.message || 'Error al eliminar'); }
  }

  async function handleTogglePrimary(vinculoId: number, currentValue: boolean) {
    try { await productoProveedorService.update(vinculoId, { is_primary: !currentValue }); await loadVinculos(); }
    catch (err: any) { alert(err.message || 'Error al actualizar'); }
  }

  function startEditVinculo(v: ProductoProveedor) {
    setEditingVinculoId(v.id);
    setEditSupplierSku(v.supplier_sku || '');
    setEditDescripcion(v.descripcion_proveedor || '');
    setEditPrecio(v.precio_proveedor || 0);
  }

  function cancelEditVinculo() {
    setEditingVinculoId(null);
    setEditSupplierSku('');
    setEditDescripcion('');
    setEditPrecio(0);
  }

  async function saveEditVinculo() {
    if (!editingVinculoId) return;
    setSavingEdit(true);
    try {
      await productoProveedorService.update(editingVinculoId, {
        supplier_sku: editSupplierSku.trim().toUpperCase() || undefined,
        descripcion_proveedor: editDescripcion.trim() || undefined,
        precio_proveedor: editPrecio > 0 ? editPrecio : undefined,
      });
      setEditingVinculoId(null);
      await loadVinculos();
    } catch (err: any) { alert(err.message || 'Error al guardar'); }
    finally { setSavingEdit(false); }
  }

  function validate(): boolean {
    const e: FormErrors = {};
    if (!form.sku.trim()) e.sku = 'El SKU es obligatorio';
    if (!form.name.trim()) e.name = 'El nombre es obligatorio';
    if (form.min_stock < 0) e.min_stock = 'No puede ser negativo';
    if (form.price < 0) e.price = 'No puede ser negativo';
    setErrors(e);
    return Object.keys(e).length === 0;
  }

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!validate()) return;
    setSubmitError(''); setSaving(true);
    try {
      if (isEdit) {
        await productService.update(form.sku, {
          name: form.name, categoria_id: form.categoria_id, unit: form.unit,
          min_stock: form.min_stock, price: form.price,
          precio_publico: form.precio_publico > 0 ? form.precio_publico : null,
          is_active: form.is_active,
          codigo_cat: form.codigo_cat || undefined, codigo_pos: form.codigo_pos || undefined, marca: form.marca || undefined,
        } as any);
      } else { await productService.create(form); }
      if (isEdit) { navigate(-1); } else { navigate('/productos'); }
    } catch (err: any) { setSubmitError(err.message || 'Error al guardar'); }
    finally { setSaving(false); }
  }

  function setField<K extends keyof ProductFormData>(key: K, value: ProductFormData[K]) {
    setForm((prev) => ({ ...prev, [key]: value }));
    if (errors[key]) setErrors((prev) => { const n = { ...prev }; delete n[key]; return n; });
  }

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="w-6 h-6 border-2 border-surface-300 border-t-sap-blue rounded-full animate-spin" />
      </div>
    );
  }

  return (
    <div className="max-w-2xl">
      <PageHeader
        title={isEdit ? 'Editar Producto' : 'Nuevo Producto'}
        description={isEdit ? `Editando ${form.sku}` : 'Registra un nuevo producto en el catálogo'}
        actions={<button onClick={() => navigate('/productos')} className="btn-secondary"><ArrowLeft className="w-4 h-4" /> Volver</button>}
      />

      <form onSubmit={handleSubmit} className="card p-6 space-y-5">
        {submitError && (
          <div className="p-3 rounded-lg bg-status-critical-muted border border-red-200 text-[13px] text-red-700">{submitError}</div>
        )}

        <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
          <div>
            <label className="label">SKU *</label>
            <input value={form.sku} onChange={(e) => setField('sku', e.target.value.toUpperCase())} placeholder="AMO-0012" className="input-field font-mono" disabled={isEdit} />
            {errors.sku && <p className="text-xs text-status-critical mt-1">{errors.sku}</p>}
          </div>
          <div className="sm:col-span-2">
            <label className="label">Nombre *</label>
            <input value={form.name} onChange={(e) => setField('name', e.target.value)} placeholder="Amortiguador Delantero Monroe..." className="input-field" />
            {errors.name && <p className="text-xs text-status-critical mt-1">{errors.name}</p>}
          </div>
        </div>

        <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
          <div>
            <label className="label">Código CAT (4 dígitos)</label>
            <input value={form.codigo_cat} onChange={(e) => setField('codigo_cat', e.target.value)} placeholder="0010" maxLength={4} className="input-field font-mono" />
          </div>
          <div>
            <label className="label">Código POS</label>
            <input value={form.codigo_pos} onChange={(e) => setField('codigo_pos', e.target.value.toUpperCase())} placeholder="Auto-generado si vacío" className="input-field font-mono" />
            <p className="text-[10px] text-brand-400 mt-0.5">Se calcula automático si pones Cód. CAT</p>
          </div>
          <div>
            <label className="label">Marca</label>
            <input value={form.marca} onChange={(e) => setField('marca', e.target.value)} placeholder="Monroe, KYB, Gates..." className="input-field" />
          </div>
        </div>

        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
          <div>
            <label className="label">Unidad</label>
            <select value={form.unit} onChange={(e) => setField('unit', e.target.value)} className="select-field">
              <option value="PZA">Pieza (PZA)</option>
              <option value="PAR">Par (PAR)</option>
              <option value="JGO">Juego (JGO)</option>
              <option value="KIT">Kit (KIT)</option>
              <option value="CAJA">Caja (CAJA)</option>
              <option value="LT">Litro (LT)</option>
              <option value="KG">Kilogramo (KG)</option>
              <option value="MT">Metro (MT)</option>
            </select>
          </div>
          <div>
            <label className="label">Stock Mínimo</label>
            <input type="number" value={form.min_stock} onChange={(e) => setField('min_stock', parseFloat(e.target.value) || 0)} min={0} className="input-field tabular-nums" />
            {errors.min_stock && <p className="text-xs text-status-critical mt-1">{errors.min_stock}</p>}
          </div>
          <div>
            <label className="label">Precio POS (costo)</label>
            <div className="relative">
              <span className="absolute left-3 top-1/2 -translate-y-1/2 text-sm text-brand-400">$</span>
              <input type="number" value={form.price || ''} onChange={(e) => setField('price', parseFloat(e.target.value) || 0)} min={0} step={0.01} placeholder="0.00" className="input-field pl-7 tabular-nums" />
            </div>
            {form.price > 0 && (
              <p className="text-[11px] text-brand-400 mt-1">Con IVA: ${(form.price * 1.16).toFixed(2)}</p>
            )}
            {errors.price && <p className="text-xs text-status-critical mt-1">{errors.price}</p>}
          </div>
          <div>
            <label className="label">Precio Público (venta)</label>
            <div className="relative">
              <span className="absolute left-3 top-1/2 -translate-y-1/2 text-sm text-brand-400">$</span>
              <input type="number" value={form.precio_publico || ''} onChange={(e) => setField('precio_publico', parseFloat(e.target.value) || 0)} min={0} step={0.01} placeholder="0.00" className="input-field pl-7 tabular-nums" />
            </div>
            <p className="text-[11px] text-brand-400 mt-1">Precio que paga el cliente</p>
          </div>
        </div>

        <div className="flex items-center gap-3 pt-2">
          <button type="button" role="switch" aria-checked={form.is_active} onClick={() => setField('is_active', !form.is_active)}
            className={`relative inline-flex h-6 w-11 items-center rounded-full transition-colors ${form.is_active ? 'bg-status-ok' : 'bg-surface-300'}`}>
            <span className={`inline-block h-4 w-4 transform rounded-full bg-white transition-transform ${form.is_active ? 'translate-x-6' : 'translate-x-1'}`} />
          </button>
          <span className="text-[13px] text-brand-700">{form.is_active ? 'Producto activo' : 'Producto inactivo'}</span>
        </div>

        <div className="flex items-center justify-end gap-3 pt-4 border-t border-surface-200">
          <button type="button" onClick={() => navigate('/productos')} className="btn-secondary">Cancelar</button>
          <button type="submit" disabled={saving} className="btn-primary">
            <Save className="w-4 h-4" /> {saving ? 'Guardando...' : isEdit ? 'Actualizar' : 'Guardar Producto'}
          </button>
        </div>
      </form>

      {/* ─── SECCIÓN PROVEEDORES ─────────────────────────── */}
      {isEdit && productId && (
        <div className="card p-6 mt-5">
          <div className="flex items-center justify-between mb-4">
            <div className="flex items-center gap-2">
              <Truck className="w-5 h-5 text-brand-400" />
              <div>
                <h2 className="text-[13px] font-semibold text-brand-800">Proveedores de este producto</h2>
                <p className="text-[11px] text-brand-400 mt-0.5">
                  {vinculos.length === 0 ? 'Sin proveedores asignados' : `${vinculos.length} proveedor${vinculos.length !== 1 ? 'es' : ''}`}
                </p>
              </div>
            </div>
            {!showAddProv && (
              <button type="button" onClick={() => setShowAddProv(true)} className="btn-primary text-[12px] px-3 py-1.5">
                <Plus className="w-3.5 h-3.5" /> Agregar Proveedor
              </button>
            )}
          </div>

          {/* ── Formulario agregar ──────────────────────── */}
          {showAddProv && (
            <div className="p-4 mb-4 rounded-lg bg-surface-50 border border-surface-200 space-y-3">
              {vinculoError && (
                <div className="p-2.5 rounded-lg bg-status-critical-muted border border-red-200 text-[12px] text-red-700">{vinculoError}</div>
              )}
              <div>
                <label className="label">Proveedor *</label>
                {selectedProv ? (
                  <div className="flex items-center justify-between p-3 rounded-lg bg-white border border-surface-200">
                    <div>
                      <p className="text-[13px] font-medium text-brand-800">{selectedProv.nombre}</p>
                      <p className="text-[11px] text-brand-400 font-mono">{selectedProv.codigo_corto}{selectedProv.rfc ? ` — ${selectedProv.rfc}` : ''}</p>
                    </div>
                    <button type="button" onClick={() => { setSelectedProv(null); setProvSearch(''); }} className="text-brand-400 hover:text-brand-600"><X className="w-4 h-4" /></button>
                  </div>
                ) : (
                  <div className="relative">
                    <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-brand-300" />
                    <input type="text" value={provSearch} onChange={(e) => setProvSearch(e.target.value)} placeholder="Buscar por nombre, código o RFC..." className="input-field pl-10" autoFocus />
                    {filteredProveedores.length > 0 && (
                      <div className="absolute z-10 w-full mt-1 bg-white border border-surface-200 rounded-lg shadow-lg max-h-48 overflow-y-auto">
                        {filteredProveedores.map((p) => (
                          <button key={p.id} type="button" onClick={() => { setSelectedProv(p); setProvSearch(''); }}
                            className="w-full text-left px-3 py-2.5 hover:bg-surface-50 border-b border-surface-100 last:border-0 transition-colors">
                            <p className="text-[13px] font-medium text-brand-800">{p.nombre}</p>
                            <p className="text-[11px] text-brand-400 font-mono">{p.codigo_corto}{p.rfc ? ` — ${p.rfc}` : ''}</p>
                          </button>
                        ))}
                      </div>
                    )}
                    {provSearch.length >= 1 && filteredProveedores.length === 0 && (
                      <div className="absolute z-10 w-full mt-1 bg-white border border-surface-200 rounded-lg shadow-lg px-3 py-4 text-center">
                        <p className="text-[12px] text-brand-400">No se encontraron proveedores</p>
                      </div>
                    )}
                  </div>
                )}
              </div>
              <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
                <div>
                  <label className="label">Código proveedor *</label>
                  <input type="text" value={supplierSku} onChange={(e) => setSupplierSku(e.target.value.toUpperCase())} placeholder="Código..." className="input-field font-mono" />
                </div>
                <div>
                  <label className="label">Descripción</label>
                  <input type="text" value={descripcionProv} onChange={(e) => setDescripcionProv(e.target.value)} placeholder="Nombre del proveedor..." className="input-field" />
                </div>
                <div>
                  <label className="label">Precio proveedor</label>
                  <div className="relative">
                    <span className="absolute left-3 top-1/2 -translate-y-1/2 text-sm text-brand-400">$</span>
                    <input type="number" value={precioProv || ''} onChange={(e) => setPrecioProv(parseFloat(e.target.value) || 0)} min={0} step={0.01} placeholder="0.00" className="input-field pl-7 tabular-nums" />
                  </div>
                </div>
              </div>
              <div className="flex items-center justify-between pt-2">
                <label className="flex items-center gap-2 cursor-pointer">
                  <input type="checkbox" checked={isPrimary} onChange={(e) => setIsPrimary(e.target.checked)} className="w-4 h-4 rounded border-surface-300" />
                  <span className="text-[12px] text-brand-600">Proveedor principal</span>
                </label>
                <div className="flex items-center gap-2">
                  <button type="button" onClick={() => { setShowAddProv(false); setVinculoError(''); setSelectedProv(null); setProvSearch(''); setSupplierSku(''); setDescripcionProv(''); setPrecioProv(0); setIsPrimary(false); }} className="btn-secondary text-[12px] px-3 py-1.5">Cancelar</button>
                  <button type="button" onClick={handleAddVinculo} disabled={savingVinculo} className="btn-primary text-[12px] px-3 py-1.5">
                    <Plus className="w-3.5 h-3.5" /> {savingVinculo ? 'Guardando...' : 'Vincular'}
                  </button>
                </div>
              </div>
            </div>
          )}

          {/* ── Lista de proveedores vinculados ─────────── */}
          {loadingVinculos ? (
            <div className="flex items-center justify-center py-8">
              <div className="w-5 h-5 border-2 border-surface-300 border-t-sap-blue rounded-full animate-spin" />
            </div>
          ) : vinculos.length === 0 && !showAddProv ? (
            <div className="text-center py-8">
              <Truck className="w-8 h-8 mx-auto text-brand-200 mb-2" />
              <p className="text-[13px] text-brand-400">Sin proveedores asignados</p>
              <p className="text-[11px] text-brand-300 mt-1">Agrega uno para rastrear compras y generar órdenes</p>
            </div>
          ) : (
            <div className="space-y-2">
              {vinculos.map((v) => (
                <div key={v.id} className="rounded-lg bg-surface-50 border border-surface-200 hover:border-surface-300 transition-colors overflow-hidden">

                  {editingVinculoId === v.id ? (
                    /* ── MODO EDICIÓN ────────────────── */
                    <div className="p-4 space-y-3">
                      <div className="flex items-center justify-between mb-1">
                        <div className="flex items-center gap-2">
                          <Truck className="w-4 h-4 text-brand-400" />
                          <p className="text-[13px] font-semibold text-brand-800">{v.proveedor_nombre}</p>
                        </div>
                        <p className="text-[10px] text-brand-400">Editando vínculo</p>
                      </div>
                      <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
                        <div>
                          <label className="label">Código proveedor</label>
                          <input type="text" value={editSupplierSku} onChange={(e) => setEditSupplierSku(e.target.value.toUpperCase())} className="input-field font-mono text-[12px]" />
                        </div>
                        <div>
                          <label className="label">Descripción</label>
                          <input type="text" value={editDescripcion} onChange={(e) => setEditDescripcion(e.target.value)} className="input-field text-[12px]" />
                        </div>
                        <div>
                          <label className="label">Precio proveedor</label>
                          <div className="relative">
                            <span className="absolute left-3 top-1/2 -translate-y-1/2 text-sm text-brand-400">$</span>
                            <input type="number" value={editPrecio || ''} onChange={(e) => setEditPrecio(parseFloat(e.target.value) || 0)} min={0} step={0.01} className="input-field pl-7 tabular-nums text-[12px]" />
                          </div>
                        </div>
                      </div>
                      <div className="flex items-center justify-end gap-2 pt-1">
                        <button type="button" onClick={cancelEditVinculo} className="btn-secondary text-[12px] px-3 py-1.5">Cancelar</button>
                        <button type="button" onClick={saveEditVinculo} disabled={savingEdit} className="btn-primary text-[12px] px-3 py-1.5">
                          <Check className="w-3.5 h-3.5" /> {savingEdit ? 'Guardando...' : 'Guardar'}
                        </button>
                      </div>
                    </div>
                  ) : (
                    /* ── MODO LECTURA ────────────────── */
                    <div className="flex items-center justify-between p-3">
                      <div className="flex items-center gap-3 min-w-0 flex-1">
                        <div className="w-8 h-8 rounded-lg bg-white border border-surface-200 flex items-center justify-center flex-shrink-0">
                          <Truck className="w-4 h-4 text-brand-400" />
                        </div>
                        <div className="min-w-0">
                          <div className="flex items-center gap-2">
                            <p className="text-[13px] font-medium text-brand-800">{v.proveedor_nombre}</p>
                            {v.is_primary && (
                              <span className="inline-flex items-center gap-1 px-1.5 py-0.5 rounded text-[10px] font-semibold bg-sap-blue-light text-sap-blue">
                                <Star className="w-3 h-3" /> Principal
                              </span>
                            )}
                          </div>
                          <div className="flex items-center gap-3 text-[11px] text-brand-400 mt-0.5">
                            <span className="font-mono">Cód: {v.supplier_sku}</span>
                            {v.precio_proveedor != null && v.precio_proveedor > 0 && (
                              <span className="text-brand-600 font-semibold">
                                ${v.precio_proveedor.toLocaleString('es-MX', { minimumFractionDigits: 2 })}
                              </span>
                            )}
                            {v.descripcion_proveedor && <span>— {v.descripcion_proveedor}</span>}
                          </div>
                        </div>
                      </div>
                      <div className="flex items-center gap-0.5 flex-shrink-0 ml-2">
                        <button type="button" onClick={() => startEditVinculo(v)}
                          className="btn-ghost p-1.5 text-brand-300 hover:text-sap-blue" title="Editar">
                          <Pencil className="w-4 h-4" />
                        </button>
                        <button type="button" onClick={() => handleTogglePrimary(v.id, v.is_primary)}
                          className={`btn-ghost p-1.5 ${v.is_primary ? 'text-sap-blue' : 'text-brand-300 hover:text-sap-blue'}`}
                          title={v.is_primary ? 'Quitar como principal' : 'Marcar como principal'}>
                          <Star className="w-4 h-4" />
                        </button>
                        <button type="button" onClick={() => handleDeleteVinculo(v.id, v.proveedor_nombre)}
                          className="btn-ghost p-1.5 text-brand-300 hover:text-status-critical" title="Eliminar">
                          <Trash2 className="w-4 h-4" />
                        </button>
                      </div>
                    </div>
                  )}
                </div>
              ))}
            </div>
          )}
        </div>
      )}
    </div>
  );
}
