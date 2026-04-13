import { useEffect, useRef, useState } from 'react';
import { X, Search, Trash2, Package } from 'lucide-react';
import { productService, productoProveedorService, comprasService } from '@/services';
import type { Product, Proveedor } from '@/types';
import { cn } from '@/lib/utils';

const METODOS_PAGO = ['EFECTIVO', 'TRANSFERENCIA', 'CHEQUE', 'TARJETA', 'CONTADO', 'CREDITO', 'OTRO'];

interface LineItem {
  product_id:   number;
  sku:          string;
  product_name: string;
  marca:        string | null;
  supplier_sku: string;
  cantidad:     number;
  precio_unit:  string; // string so the input can be empty
}

interface Props {
  proveedores: Proveedor[];
  onSuccess:   (compraId: number, lineCount: number) => void;
  onClose:     () => void;
}

function fmt(n: number) {
  return `$${n.toLocaleString('es-MX', { minimumFractionDigits: 2 })}`;
}

export function CompraForm({ proveedores, onSuccess, onClose }: Props) {
  // Header fields
  const [proveedorId, setProveedorId] = useState<number | ''>('');
  const [fecha,        setFecha]       = useState(new Date().toISOString().slice(0, 10));
  const [folioFactura, setFolioFactura] = useState('');
  const [folioCaptura, setFolioCaptura] = useState('');
  const [metodoPago,   setMetodoPago]   = useState('');
  const [tipoCompra,   setTipoCompra]   = useState<'CON_FACTURA' | 'SIN_FACTURA'>('SIN_FACTURA');
  const [notas,        setNotas]        = useState('');

  // Product lines
  const [lines,      setLines]      = useState<LineItem[]>([]);
  const [dupWarning, setDupWarning] = useState('');

  // Product search
  const [searchQ,      setSearchQ]      = useState('');
  const [searchResults, setSearchResults] = useState<Product[]>([]);
  const [showDropdown, setShowDropdown] = useState(false);
  const searchRef = useRef<HTMLDivElement>(null);

  // Totals — auto-computed from lines, but directly editable
  const [subtotal, setSubtotal] = useState(0);
  const [iva,      setIva]      = useState(0);
  const [total,    setTotal]    = useState(0);

  // Save state
  const [saving,    setSaving]    = useState(false);
  const [formError, setFormError] = useState('');

  // ── Product search (debounced 300ms) ────────────────────────────────────
  useEffect(() => {
    if (searchQ.length < 2) {
      setSearchResults([]);
      setShowDropdown(false);
      return;
    }
    const timer = setTimeout(async () => {
      try {
        const res = await productService.search(searchQ);
        setSearchResults(res.items);
        setShowDropdown(res.items.length > 0);
      } catch {}
    }, 300);
    return () => clearTimeout(timer);
  }, [searchQ]);

  // Close dropdown on outside click
  useEffect(() => {
    function onMouseDown(e: MouseEvent) {
      if (searchRef.current && !searchRef.current.contains(e.target as Node)) {
        setShowDropdown(false);
      }
    }
    document.addEventListener('mousedown', onMouseDown);
    return () => document.removeEventListener('mousedown', onMouseDown);
  }, []);

  // ── Auto-recompute totals when lines change ─────────────────────────────
  useEffect(() => {
    const s = lines.reduce((acc, l) => {
      const p = parseFloat(l.precio_unit);
      return isNaN(p) ? acc : acc + l.cantidad * p;
    }, 0);
    const rounded  = Math.round(s * 100) / 100;
    const ivaCalc  = Math.round(rounded * 0.16 * 100) / 100;
    setSubtotal(rounded);
    setIva(ivaCalc);
    setTotal(rounded + ivaCalc);
  }, [lines]);

  // ── Select a product from the search dropdown ───────────────────────────
  async function selectProduct(product: Product) {
    if (lines.some((l) => l.product_id === product.id)) {
      setDupWarning(`${product.sku} ya está en la orden`);
      setSearchQ('');
      setShowDropdown(false);
      return;
    }
    setDupWarning('');

    let supplier_sku = '';
    let precio_unit  = '';

    if (proveedorId !== '') {
      try {
        const res = await productoProveedorService.getByProduct(product.id);
        const mapping = res.items.find((m) => m.proveedor_id === proveedorId);
        if (mapping) {
          supplier_sku = (mapping as any).supplier_sku ?? '';
          const pp     = (mapping as any).precio_proveedor;
          if (pp != null && Number(pp) !== 0) {
            precio_unit = String(pp);
          }
        }
      } catch {}
    }

    setLines((prev) => [
      ...prev,
      {
        product_id:   product.id,
        sku:          product.sku,
        product_name: product.name,
        marca:        product.marca || null,
        supplier_sku,
        cantidad:     1,
        precio_unit,
      },
    ]);
    setSearchQ('');
    setShowDropdown(false);
  }

  function removeLine(index: number) {
    setLines((prev) => prev.filter((_, i) => i !== index));
  }

  function updateLine<K extends keyof LineItem>(index: number, field: K, value: LineItem[K]) {
    setLines((prev) => prev.map((l, i) => (i === index ? { ...l, [field]: value } : l)));
  }

  function calcImporte(line: LineItem): string {
    const p = parseFloat(line.precio_unit);
    return isNaN(p) ? '—' : fmt(line.cantidad * p);
  }

  // ── Save ────────────────────────────────────────────────────────────────
  async function handleSave() {
    setFormError('');
    if (!proveedorId)      { setFormError('Selecciona un proveedor'); return; }
    if (!fecha)            { setFormError('La fecha es requerida'); return; }
    if (lines.length === 0){ setFormError('Agrega al menos un producto'); return; }
    const badQty = lines.find((l) => !(l.cantidad > 0));
    if (badQty)            { setFormError(`Cantidad inválida en ${badQty.sku}`); return; }

    setSaving(true);
    try {
      const res = await comprasService.create({
        proveedor_id:  proveedorId as number,
        fecha,
        folio_factura: folioFactura || undefined,
        folio_captura: folioCaptura || undefined,
        subtotal,
        iva,
        total,
        estatus:       'PENDIENTE',
        metodo_pago:   metodoPago  || undefined,
        notas:         notas       || undefined,
        tipo_compra:   tipoCompra,
        detalle: lines.map((l) => ({
          product_id:   l.product_id,
          cantidad:     l.cantidad,
          precio_unit:  l.precio_unit !== '' ? parseFloat(l.precio_unit) : null,
          supplier_sku: l.supplier_sku || null,
        })),
      });
      onSuccess(res.id, lines.length);
    } catch (e: any) {
      setFormError(e.message);
    } finally {
      setSaving(false);
    }
  }

  function handleClose() {
    if (lines.length > 0) {
      if (!confirm('¿Descartar la compra? Se perderán los cambios no guardados.')) return;
    }
    onClose();
  }

  const hasPrices = lines.some((l) => l.precio_unit !== '');

  return (
    <div className="fixed inset-0 z-50 bg-white flex flex-col">

      {/* ── Top bar ─────────────────────────────────────────────────────────── */}
      <div className="px-6 py-4 border-b border-surface-200 flex items-center justify-between shrink-0">
        <div className="flex items-center gap-3">
          <h2 className="text-[15px] font-semibold text-brand-800">Nueva Compra</h2>
          <span className="text-[10px] font-semibold px-2 py-0.5 rounded-full bg-amber-50 text-amber-700 border border-amber-200">
            PENDIENTE
          </span>
        </div>
        <button onClick={handleClose} className="btn-ghost p-1.5 text-brand-400">
          <X className="w-5 h-5" />
        </button>
      </div>

      {/* ── Scrollable body ──────────────────────────────────────────────────── */}
      <div className="flex-1 overflow-y-auto px-6 py-6 space-y-8 max-w-5xl w-full mx-auto">

        {/* Section 1 — Header fields */}
        <section>
          <p className="text-[11px] font-semibold text-brand-400 uppercase tracking-wide mb-4">Datos de la compra</p>
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">

            <div className="sm:col-span-2 lg:col-span-1">
              <label className="label">Proveedor *</label>
              <select
                value={proveedorId}
                onChange={(e) => setProveedorId(e.target.value === '' ? '' : Number(e.target.value))}
                className="select-field w-full"
              >
                <option value="">Seleccionar proveedor...</option>
                {proveedores.map((p) => (
                  <option key={p.id} value={p.id}>{p.nombre}</option>
                ))}
              </select>
            </div>

            <div>
              <label className="label">Fecha *</label>
              <input
                type="date"
                value={fecha}
                onChange={(e) => setFecha(e.target.value)}
                className="input-field w-full"
              />
            </div>

            <div>
              <label className="label">Método / Condición de pago</label>
              <select
                value={metodoPago}
                onChange={(e) => setMetodoPago(e.target.value)}
                className="select-field w-full"
              >
                <option value="">— Sin especificar —</option>
                {METODOS_PAGO.map((m) => (
                  <option key={m} value={m}>{m}</option>
                ))}
              </select>
            </div>

            <div>
              <label className="label">Tipo de compra</label>
              <select
                value={tipoCompra}
                onChange={(e) => setTipoCompra(e.target.value as 'CON_FACTURA' | 'SIN_FACTURA')}
                className="select-field w-full"
              >
                <option value="SIN_FACTURA">Sin Factura / Remisión</option>
                <option value="CON_FACTURA">Con Factura</option>
              </select>
            </div>

            <div>
              <label className="label">Folio factura proveedor</label>
              <input
                value={folioFactura}
                onChange={(e) => setFolioFactura(e.target.value)}
                placeholder="Ej. FAC-2026-001"
                className="input-field w-full"
              />
            </div>

            <div>
              <label className="label">Folio captura</label>
              <input
                value={folioCaptura}
                onChange={(e) => setFolioCaptura(e.target.value)}
                placeholder="Ref. interna"
                className="input-field w-full"
              />
            </div>

            <div className="sm:col-span-2 lg:col-span-3">
              <label className="label">Notas / Observaciones</label>
              <textarea
                value={notas}
                onChange={(e) => setNotas(e.target.value)}
                placeholder="Observaciones opcionales..."
                rows={2}
                className="input-field w-full resize-none"
              />
            </div>
          </div>
        </section>

        {/* Section 2 — Product lines */}
        <section>
          <p className="text-[11px] font-semibold text-brand-400 uppercase tracking-wide mb-4">
            Productos {lines.length > 0 && <span className="normal-case font-normal">({lines.length})</span>}
          </p>

          {/* Search bar */}
          <div ref={searchRef} className="relative mb-3 max-w-lg">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-brand-300 pointer-events-none" />
            <input
              value={searchQ}
              onChange={(e) => { setSearchQ(e.target.value); setDupWarning(''); }}
              placeholder={
                proveedorId === ''
                  ? 'Selecciona un proveedor antes de agregar productos...'
                  : 'Buscar producto (SKU, nombre, cód. POS)...'
              }
              disabled={proveedorId === ''}
              className={cn('input-field pl-10 w-full', proveedorId === '' && 'opacity-50 cursor-not-allowed')}
            />
            {showDropdown && searchResults.length > 0 && (
              <div className="absolute z-10 w-full mt-1 bg-white border border-surface-200 rounded-lg shadow-lg max-h-60 overflow-y-auto">
                {searchResults.map((p) => (
                  <button
                    key={p.id}
                    onMouseDown={() => selectProduct(p)}
                    className="w-full text-left px-3 py-2.5 hover:bg-surface-50 border-b border-surface-100 last:border-0"
                  >
                    <span className="font-mono text-xs font-semibold text-brand-600">{p.sku}</span>
                    <span className="text-sm text-brand-800 ml-2">{p.name}</span>
                    {p.marca && <span className="text-xs text-brand-400 ml-1">({p.marca})</span>}
                  </button>
                ))}
              </div>
            )}
          </div>

          {dupWarning && (
            <div className="mb-3 px-3 py-2 rounded-lg bg-amber-50 border border-amber-200 text-xs text-amber-700">
              {dupWarning}
            </div>
          )}

          {/* Lines table or empty state */}
          {lines.length === 0 ? (
            <div className="border border-dashed border-surface-300 rounded-xl p-10 text-center text-brand-400">
              <Package className="w-8 h-8 mx-auto mb-2 opacity-25" />
              <p className="text-sm">Sin productos. Busca arriba para agregar.</p>
            </div>
          ) : (
            <div className="border border-surface-200 rounded-xl overflow-hidden">
              <div className="overflow-x-auto">
                <table className="w-full text-[13px] min-w-[750px]">
                  <thead>
                    <tr className="bg-surface-50 border-b border-surface-200">
                      <th className="text-left px-3 py-2.5 text-[11px] font-semibold text-brand-400 uppercase tracking-wide">SKU</th>
                      <th className="text-left px-3 py-2.5 text-[11px] font-semibold text-brand-400 uppercase tracking-wide">Producto</th>
                      <th className="text-left px-3 py-2.5 text-[11px] font-semibold text-brand-400 uppercase tracking-wide w-36">Cód. Proveedor</th>
                      <th className="text-right px-3 py-2.5 text-[11px] font-semibold text-brand-400 uppercase tracking-wide w-28">Cantidad</th>
                      <th className="text-right px-3 py-2.5 text-[11px] font-semibold text-brand-400 uppercase tracking-wide w-36">Precio Unit.</th>
                      <th className="text-right px-3 py-2.5 text-[11px] font-semibold text-brand-400 uppercase tracking-wide w-28">Importe</th>
                      <th className="w-10" />
                    </tr>
                  </thead>
                  <tbody>
                    {lines.map((line, i) => (
                      <tr key={line.product_id} className="border-b border-surface-100 hover:bg-surface-50/50">
                        <td className="px-3 py-2">
                          <span className="font-mono text-xs font-medium text-brand-600">{line.sku}</span>
                        </td>
                        <td className="px-3 py-2">
                          <p className="text-[13px] text-brand-800 truncate max-w-[200px]">{line.product_name}</p>
                          {line.marca && <p className="text-[11px] text-brand-400">{line.marca}</p>}
                        </td>
                        <td className="px-3 py-2">
                          <input
                            value={line.supplier_sku}
                            onChange={(e) => updateLine(i, 'supplier_sku', e.target.value)}
                            placeholder="Cód. prov."
                            className="input-field text-xs py-1 w-32 font-mono"
                          />
                        </td>
                        <td className="px-3 py-2 text-right">
                          <input
                            type="number"
                            min={0.01}
                            step="any"
                            value={line.cantidad}
                            onChange={(e) => updateLine(i, 'cantidad', parseFloat(e.target.value) || 0)}
                            className="input-field text-xs py-1 w-20 text-right tabular-nums"
                          />
                        </td>
                        <td className="px-3 py-2 text-right">
                          <input
                            type="number"
                            min={0}
                            step="0.01"
                            value={line.precio_unit}
                            onChange={(e) => updateLine(i, 'precio_unit', e.target.value)}
                            placeholder="—"
                            className="input-field text-xs py-1 w-32 text-right tabular-nums"
                          />
                        </td>
                        <td className="px-3 py-2 text-right tabular-nums text-[13px] text-brand-700 font-medium">
                          {calcImporte(line)}
                        </td>
                        <td className="px-2 py-2">
                          <button
                            onClick={() => removeLine(i)}
                            className="btn-ghost p-1 text-brand-300 hover:text-status-critical"
                            title="Quitar línea"
                          >
                            <Trash2 className="w-3.5 h-3.5" />
                          </button>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>

              {/* Section 3 — Totals */}
              <div className="border-t border-surface-200 bg-surface-50/60 px-4 py-3">
                {!hasPrices ? (
                  <p className="text-xs text-brand-400 text-right italic">
                    Sin precios — los totales se calcularán al ingresar precios
                  </p>
                ) : (
                  <div className="flex flex-wrap items-center justify-end gap-x-6 gap-y-2">
                    <label className="flex items-center gap-2">
                      <span className="text-xs text-brand-400 whitespace-nowrap">Subtotal</span>
                      <div className="relative">
                        <span className="absolute left-2.5 top-1/2 -translate-y-1/2 text-xs text-brand-400 pointer-events-none">$</span>
                        <input
                          type="number" step="0.01"
                          value={subtotal}
                          onChange={(e) => setSubtotal(Number(e.target.value))}
                          className="input-field text-xs py-1 w-32 text-right tabular-nums pl-6"
                        />
                      </div>
                    </label>
                    <label className="flex items-center gap-2">
                      <span className="text-xs text-brand-400 whitespace-nowrap">IVA (16%)</span>
                      <div className="relative">
                        <span className="absolute left-2.5 top-1/2 -translate-y-1/2 text-xs text-brand-400 pointer-events-none">$</span>
                        <input
                          type="number" step="0.01"
                          value={iva}
                          onChange={(e) => {
                            const v = Number(e.target.value);
                            setIva(v);
                            setTotal(subtotal + v);
                          }}
                          className="input-field text-xs py-1 w-28 text-right tabular-nums pl-6"
                        />
                      </div>
                    </label>
                    <label className="flex items-center gap-2">
                      <span className="text-xs font-semibold text-brand-700 whitespace-nowrap">Total</span>
                      <div className="relative">
                        <span className="absolute left-2.5 top-1/2 -translate-y-1/2 text-xs text-brand-500 pointer-events-none">$</span>
                        <input
                          type="number" step="0.01"
                          value={total}
                          onChange={(e) => setTotal(Number(e.target.value))}
                          className="input-field text-xs py-1 w-32 text-right tabular-nums pl-6 font-semibold"
                        />
                      </div>
                    </label>
                  </div>
                )}
              </div>
            </div>
          )}
        </section>
      </div>

      {/* ── Footer ──────────────────────────────────────────────────────────── */}
      <div className="px-6 py-4 border-t border-surface-200 flex items-center justify-between shrink-0 bg-white">
        <div>
          {formError && (
            <p className="text-xs text-red-600 mb-0.5">{formError}</p>
          )}
          <p className="text-xs text-brand-400">
            {lines.length > 0
              ? `${lines.length} producto${lines.length !== 1 ? 's' : ''} · ${hasPrices ? `Total: ${fmt(total)}` : 'sin precios'}`
              : 'Sin productos agregados'}
          </p>
        </div>
        <div className="flex gap-2">
          <button onClick={handleClose} disabled={saving} className="btn-secondary">
            Cancelar
          </button>
          <button
            onClick={handleSave}
            disabled={saving || lines.length === 0}
            className="btn-primary"
          >
            {saving ? 'Guardando...' : 'Guardar Compra'}
          </button>
        </div>
      </div>
    </div>
  );
}
