import { useState, useEffect, useRef, useCallback } from 'react';
import { ArrowRightLeft, Save, AlertTriangle, X, Search } from 'lucide-react';
import { PageHeader, MovementTypeBadge } from '@/components/shared';
import { movementService, productService } from '@/services';
import { formatDateTime } from '@/lib/utils';
import type { Product, Movement, MovementType } from '@/types';

export function MovementsPage() {
  const [recentMov, setRecentMov] = useState<Movement[]>([]);
  const [loading, setLoading] = useState(false);
  const [saving, setSaving] = useState(false);
  const [success, setSuccess] = useState('');
  const [error, setError] = useState('');
  const [formError, setFormError] = useState('');

  // Product combobox state
  const [query, setQuery] = useState('');
  const [suggestions, setSuggestions] = useState<Product[]>([]);
  const [searching, setSearching] = useState(false);
  const [open, setOpen] = useState(false);
  const [selectedProduct, setSelectedProduct] = useState<Product | null>(null);
  const comboRef = useRef<HTMLDivElement>(null);
  const debounceRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  const [sku, setSku] = useState('');
  const [movType, setMovType] = useState<MovementType>('IN');
  const [quantity, setQuantity] = useState<number>(0);
  const [reference, setReference] = useState('');
  const [notes, setNotes] = useState('');
  const [libro, setLibro] = useState<'FISICO' | 'FISCAL_POS'>('FISICO');
  const [kardexSku, setKardexSku] = useState('');

  const [errors, setErrors] = useState<Record<string, string>>({});

  // Close dropdown on outside click
  useEffect(() => {
    function handleClick(e: MouseEvent) {
      if (comboRef.current && !comboRef.current.contains(e.target as Node)) {
        setOpen(false);
      }
    }
    document.addEventListener('mousedown', handleClick);
    return () => document.removeEventListener('mousedown', handleClick);
  }, []);

  // Debounced search
  const handleQueryChange = useCallback((val: string) => {
    setQuery(val);
    if (!val.trim()) {
      setSuggestions([]);
      setOpen(false);
      return;
    }
    if (debounceRef.current) clearTimeout(debounceRef.current);
    debounceRef.current = setTimeout(async () => {
      setSearching(true);
      try {
        const res = await productService.search(val.trim(), 20);
        setSuggestions(res.items);
        setOpen(true);
      } catch {
        setSuggestions([]);
      } finally {
        setSearching(false);
      }
    }, 250);
  }, []);

  function selectProduct(p: Product) {
    setSelectedProduct(p);
    setSku(p.sku);
    setKardexSku(p.sku);
    setQuery('');
    setSuggestions([]);
    setOpen(false);
    if (errors.sku) setErrors((prev) => { const n = { ...prev }; delete n.sku; return n; });
  }

  function clearProduct() {
    setSelectedProduct(null);
    setSku('');
    setKardexSku('');
    setQuery('');
    setSuggestions([]);
  }

  // Cargar kardex cuando se selecciona un SKU
  useEffect(() => {
    if (kardexSku) {
      movementService.getKardex(kardexSku, 20)
        .then((res) => setRecentMov(res.items))
        .catch(() => setRecentMov([]));
    }
  }, [kardexSku]);

  function validate(): boolean {
    const e: Record<string, string> = {};
    if (!sku) e.sku = 'Selecciona un producto';
    if (!quantity || quantity <= 0) e.quantity = 'La cantidad debe ser mayor a 0';
    setErrors(e);
    return Object.keys(e).length === 0;
  }

  async function handleSubmit(ev: React.FormEvent) {
    ev.preventDefault();
    if (!validate()) return;
    setFormError('');
    setSuccess('');
    setSaving(true);

    try {
      await movementService.create({
        sku,
        movement_type: movType,
        quantity,
        reference,
        libro,
        notes,
      });
      setSuccess(`Movimiento registrado: ${movType} x${quantity} para ${sku}`);
      setQuantity(0);
      setReference('');
      setNotes('');

      // Refrescar kardex
      if (sku) {
        const res = await movementService.getKardex(sku, 20);
        setRecentMov(res.items);
        setKardexSku(sku);
      }
    } catch (err: any) {
      setFormError(err.message || 'Error al registrar movimiento');
    } finally {
      setSaving(false);
    }
  }

  const typeOptions: { value: MovementType; label: string; color: string }[] = [
    { value: 'IN', label: 'Entrada', color: 'bg-emerald-50 border-emerald-300 text-emerald-800' },
    { value: 'OUT', label: 'Salida', color: 'bg-red-50 border-red-300 text-red-800' },
    { value: 'ADJUST', label: 'Ajuste', color: 'bg-amber-50 border-amber-300 text-amber-800' },
  ];

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
        title="Registro de Movimientos"
        description="Captura entradas, salidas y ajustes de inventario"
      />

      <div className="grid grid-cols-1 lg:grid-cols-5 gap-6">
        {/* Form */}
        <div className="lg:col-span-2">
          <form onSubmit={handleSubmit} className="card p-5 space-y-4">
            <div className="flex items-center gap-2 mb-2">
              <ArrowRightLeft className="w-5 h-5 text-brand-500" />
              <h2 className="text-[13px] font-semibold text-brand-800">Nuevo Movimiento</h2>
            </div>

            {formError && (
              <div className="p-3 rounded-lg bg-status-critical-muted border border-red-200 text-[13px] text-red-700">{formError}</div>
            )}
            {success && (
              <div className="p-3 rounded-lg bg-status-ok-muted border border-emerald-200 text-[13px] text-emerald-700">{success}</div>
            )}

            {/* Product combobox */}
            <div>
              <label className="label">Producto *</label>
              <div ref={comboRef} className="relative">
                {selectedProduct ? (
                  <div className="flex items-center gap-2 px-3 py-2 rounded-lg border border-brand-300 bg-brand-50">
                    <span className="text-[12px] font-mono font-semibold text-brand-700">{selectedProduct.sku}</span>
                    <span className="text-[12px] text-brand-600 truncate flex-1">{selectedProduct.name}</span>
                    {selectedProduct.marca && (
                      <span className="text-[11px] text-brand-400 shrink-0">{selectedProduct.marca}</span>
                    )}
                    <button type="button" onClick={clearProduct} className="ml-1 text-brand-400 hover:text-red-500 shrink-0">
                      <X className="w-3.5 h-3.5" />
                    </button>
                  </div>
                ) : (
                  <div className="relative">
                    <Search className="absolute left-2.5 top-1/2 -translate-y-1/2 w-3.5 h-3.5 text-brand-400 pointer-events-none" />
                    <input
                      type="text"
                      value={query}
                      onChange={(e) => handleQueryChange(e.target.value)}
                      onFocus={() => suggestions.length > 0 && setOpen(true)}
                      placeholder="Buscar por SKU, código o nombre..."
                      className="input-field pl-8 pr-8"
                      autoComplete="off"
                    />
                    {searching && (
                      <span className="absolute right-2.5 top-1/2 -translate-y-1/2 w-3.5 h-3.5 border-2 border-surface-300 border-t-brand-500 rounded-full animate-spin" />
                    )}
                  </div>
                )}

                {open && suggestions.length > 0 && !selectedProduct && (
                  <ul className="absolute z-50 left-0 right-0 mt-1 bg-white border border-surface-200 rounded-lg shadow-lg max-h-52 overflow-y-auto">
                    {suggestions.map((p) => (
                      <li
                        key={p.id}
                        onMouseDown={() => selectProduct(p)}
                        className="flex items-center gap-2 px-3 py-2 cursor-pointer hover:bg-brand-50 border-b border-surface-100 last:border-0"
                      >
                        <span className="text-[11px] font-mono font-semibold text-brand-600 shrink-0 w-24 truncate">{p.sku}</span>
                        <span className="text-[12px] text-brand-800 truncate flex-1">{p.name}</span>
                        {p.marca && <span className="text-[11px] text-brand-400 shrink-0">{p.marca}</span>}
                      </li>
                    ))}
                  </ul>
                )}

                {open && suggestions.length === 0 && query.length > 1 && !searching && !selectedProduct && (
                  <div className="absolute z-50 left-0 right-0 mt-1 bg-white border border-surface-200 rounded-lg shadow px-3 py-2 text-[12px] text-brand-400">
                    Sin resultados para "{query}"
                  </div>
                )}
              </div>
              {errors.sku && <p className="text-xs text-status-critical mt-1">{errors.sku}</p>}
            </div>

            {/* Libro */}
            <div>
              <label className="label">Libro</label>
              <div className="flex gap-2">
                <button
                  type="button"
                  onClick={() => setLibro('FISICO')}
                  className={`flex-1 px-3 py-2 text-xs font-semibold rounded-lg border-2 transition-all ${
                    libro === 'FISICO' ? 'bg-brand-50 border-brand-400 text-brand-800' : 'border-surface-200 text-brand-400 bg-white'
                  }`}
                >
                  Físico
                </button>
                <button
                  type="button"
                  onClick={() => setLibro('FISCAL_POS')}
                  className={`flex-1 px-3 py-2 text-xs font-semibold rounded-lg border-2 transition-all ${
                    libro === 'FISCAL_POS' ? 'bg-brand-50 border-brand-400 text-brand-800' : 'border-surface-200 text-brand-400 bg-white'
                  }`}
                >
                  Fiscal / POS
                </button>
              </div>
            </div>

            {/* Type selector */}
            <div>
              <label className="label">Tipo de Movimiento</label>
              <div className="flex gap-2">
                {typeOptions.map((opt) => (
                  <button
                    type="button"
                    key={opt.value}
                    onClick={() => setMovType(opt.value)}
                    className={`flex-1 px-3 py-2.5 text-xs font-semibold rounded-lg border-2 transition-all ${
                      movType === opt.value ? opt.color : 'border-surface-200 text-brand-400 bg-white'
                    }`}
                  >
                    {opt.label}
                  </button>
                ))}
              </div>
            </div>

            {/* Quantity */}
            <div>
              <label className="label">Cantidad *</label>
              <input
                type="number"
                value={quantity || ''}
                onChange={(e) => {
                  setQuantity(parseFloat(e.target.value) || 0);
                  if (errors.quantity) setErrors((p) => { const n = { ...p }; delete n.quantity; return n; });
                }}
                min={0.01}
                step="any"
                className="input-field tabular-nums text-lg font-bold"
                placeholder="0"
              />
              {errors.quantity && <p className="text-xs text-status-critical mt-1">{errors.quantity}</p>}
            </div>

            {/* Reference */}
            <div>
              <label className="label">Referencia</label>
              <input
                value={reference}
                onChange={(e) => setReference(e.target.value)}
                placeholder="FAC-2025-0312, VTA-4521..."
                className="input-field"
              />
            </div>

            {/* Notes */}
            <div>
              <label className="label">Notas</label>
              <input
                value={notes}
                onChange={(e) => setNotes(e.target.value)}
                placeholder="Comentario adicional..."
                className="input-field"
              />
            </div>

            <button type="submit" disabled={saving} className="btn-primary w-full mt-2">
              <Save className="w-4 h-4" />
              {saving ? 'Registrando...' : 'Registrar Movimiento'}
            </button>
          </form>
        </div>

        {/* Kardex del producto seleccionado */}
        <div className="lg:col-span-3">
          <div className="card overflow-hidden">
            <div className="p-4 border-b border-surface-200">
              <h2 className="text-[13px] font-semibold text-brand-800">
                {kardexSku ? `Kardex: ${kardexSku}` : 'Historial del producto'}
              </h2>
              <p className="text-[11px] text-brand-400 mt-0.5">
                {kardexSku ? 'Últimos 20 movimientos' : 'Selecciona un producto para ver su kardex'}
              </p>
            </div>
            <div className="overflow-x-auto">
              <table className="w-full">
                <thead>
                  <tr className="bg-surface-50 border-b border-surface-200">
                    <th className="table-header">Fecha</th>
                    <th className="table-header">Libro</th>
                    <th className="table-header">Tipo</th>
                    <th className="table-header text-right">Cant.</th>
                    <th className="table-header">Referencia</th>
                    <th className="table-header">Notas</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-surface-100">
                  {recentMov.length === 0 ? (
                    <tr>
                      <td colSpan={6} className="px-4 py-8 text-center text-[13px] text-brand-400">
                        {kardexSku ? 'Sin movimientos registrados' : 'Selecciona un producto arriba'}
                      </td>
                    </tr>
                  ) : (
                    recentMov.map((m) => (
                      <tr key={m.id} className="hover:bg-surface-50">
                        <td className="table-cell text-xs text-brand-500 whitespace-nowrap">{formatDateTime(m.movement_date)}</td>
                        <td className="table-cell">
                          <span className={`badge text-[10px] ${m.libro === 'FISICO' ? 'bg-brand-50 text-brand-600' : 'bg-purple-50 text-purple-600'}`}>
                            {m.libro === 'FISICO' ? 'FIS' : 'POS'}
                          </span>
                        </td>
                        <td className="table-cell"><MovementTypeBadge type={m.movement_type} /></td>
                        <td className="table-cell text-right tabular-nums font-medium">{m.quantity}</td>
                        <td className="table-cell text-xs text-brand-500 truncate max-w-[140px]">{m.reference || '—'}</td>
                        <td className="table-cell text-xs text-brand-400 truncate max-w-[140px]">{m.notes || '—'}</td>
                      </tr>
                    ))
                  )}
                </tbody>
              </table>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
