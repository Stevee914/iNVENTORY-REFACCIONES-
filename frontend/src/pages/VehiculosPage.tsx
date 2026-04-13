import { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { Car, ChevronRight, Package, AlertCircle } from 'lucide-react';
import {
  vehiculosService,
  type Marca,
  type Modelo,
  type ProductoAplicacion,
} from '@/services/vehiculosService';

// ─── Sub-components ───────────────────────────────────────────────────────────

function SelectField({
  label,
  value,
  onChange,
  disabled,
  placeholder,
  children,
}: {
  label: string;
  value: string;
  onChange: (v: string) => void;
  disabled?: boolean;
  placeholder: string;
  children: React.ReactNode;
}) {
  return (
    <div className="flex flex-col gap-1">
      <label className="text-[11px] font-semibold text-surface-500 uppercase tracking-wide">
        {label}
      </label>
      <select
        value={value}
        onChange={(e) => onChange(e.target.value)}
        disabled={disabled}
        className="h-9 rounded-lg border border-surface-200 bg-white px-3 text-sm text-surface-800
                   disabled:opacity-40 disabled:cursor-not-allowed
                   focus:outline-none focus:ring-2 focus:ring-sap-blue/30 focus:border-sap-blue
                   transition-colors"
      >
        <option value="">{placeholder}</option>
        {children}
      </select>
    </div>
  );
}

function StockBadge({ qty, min }: { qty: number; min: number | null }) {
  if (qty <= 0)
    return <span className="px-2 py-0.5 rounded text-[11px] font-medium bg-red-100 text-red-700">Sin stock</span>;
  if (min !== null && qty <= min)
    return <span className="px-2 py-0.5 rounded text-[11px] font-medium bg-amber-100 text-amber-700">{qty}</span>;
  return <span className="px-2 py-0.5 rounded text-[11px] font-medium bg-emerald-100 text-emerald-700">{qty}</span>;
}

// ─── Main Page ────────────────────────────────────────────────────────────────

export function VehiculosPage() {
  const [marcas, setMarcas]   = useState<Marca[]>([]);
  const [modelos, setModelos] = useState<Modelo[]>([]);
  const [anios, setAnios]     = useState<number[]>([]);
  const [motores, setMotores] = useState<string[]>([]);
  const [productos, setProductos] = useState<ProductoAplicacion[]>([]);

  const [marcaId, setMarcaId]   = useState('');
  const [modeloId, setModeloId] = useState('');
  const [anio, setAnio]         = useState('');
  const [motor, setMotor]       = useState('');

  const [loading, setLoading] = useState<'modelos' | 'anios' | 'productos' | null>(null);
  const [cascadeError, setCascadeError]     = useState<string | null>(null);
  const [productosError, setProductosError] = useState<string | null>(null);

  useEffect(() => {
    vehiculosService.getMarcas()
      .then(setMarcas)
      .catch(() => setCascadeError('No se pudo cargar las marcas'));
  }, []);

  function handleMarcaChange(v: string) {
    setMarcaId(v);
    setModeloId(''); setAnio(''); setMotor('');
    setModelos([]); setAnios([]); setMotores([]); setProductos([]);
    setCascadeError(null); setProductosError(null);
    if (!v) return;
    setLoading('modelos');
    vehiculosService.getModelos(Number(v))
      .then(setModelos)
      .catch(() => setCascadeError('Error cargando modelos'))
      .finally(() => setLoading(null));
  }

  function handleModeloChange(v: string) {
    setModeloId(v);
    setAnio(''); setMotor('');
    setAnios([]); setMotores([]); setProductos([]);
    setCascadeError(null); setProductosError(null);
    if (!v) return;
    setLoading('anios');
    vehiculosService.getAnios(Number(v))
      .then(setAnios)
      .catch(() => setCascadeError('Error cargando años'))
      .finally(() => setLoading(null));
  }

  function fetchProductos(midStr: string, anioStr: string, motorStr: string) {
    setProductos([]);
    setProductosError(null);
    setLoading('productos');
    vehiculosService.getProductosByModeloAnio(
      Number(midStr),
      Number(anioStr),
      motorStr || undefined,
    )
      .then(res => { setMotores(res.motores); setProductos(res.items); })
      .catch(() => setProductosError('Error al cargar los productos. Intenta de nuevo.'))
      .finally(() => setLoading(null));
  }

  function handleAnioChange(v: string) {
    setAnio(v);
    setMotor('');
    setMotores([]); setProductos([]);
    setProductosError(null);
    if (!v || !modeloId) return;
    fetchProductos(modeloId, v, '');
  }

  function handleMotorChange(v: string) {
    setMotor(v);
    if (!anio || !modeloId) return;
    fetchProductos(modeloId, anio, v);
  }

  const marcaNombre  = marcas.find(m => String(m.id) === marcaId)?.nombre ?? '';
  const modeloNombre = modelos.find(m => String(m.id) === modeloId)?.nombre ?? '';
  const selectionComplete = !!marcaId && !!modeloId && !!anio;

  return (
    <div className="space-y-5">
      {/* ── Header ── */}
      <div className="flex items-center gap-3">
        <div className="w-8 h-8 rounded-lg bg-sap-blue/10 flex items-center justify-center">
          <Car className="w-4 h-4 text-sap-blue" />
        </div>
        <div>
          <h1 className="text-lg font-semibold text-surface-900">Búsqueda por Vehículo</h1>
          <p className="text-[12px] text-surface-400">Selecciona marca · modelo · año</p>
        </div>
      </div>

      {/* ── Cascade error ── */}
      {cascadeError && (
        <div className="flex items-center gap-2 px-4 py-3 rounded-lg bg-red-50 border border-red-200 text-red-700 text-sm">
          <AlertCircle className="w-4 h-4 flex-shrink-0" />
          {cascadeError}
        </div>
      )}

      {/* ── Selectors ── */}
      <div className="bg-white rounded-xl border border-surface-200 p-4 shadow-sm">
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-3">
          <SelectField label="Marca" value={marcaId} onChange={handleMarcaChange} placeholder="— Selecciona —">
            {marcas.map(m => <option key={m.id} value={m.id}>{m.nombre}</option>)}
          </SelectField>

          <SelectField
            label="Modelo" value={modeloId} onChange={handleModeloChange}
            disabled={!marcaId || loading === 'modelos'}
            placeholder={loading === 'modelos' ? 'Cargando…' : '— Selecciona —'}
          >
            {modelos.map(m => <option key={m.id} value={m.id}>{m.nombre}</option>)}
          </SelectField>

          <SelectField
            label="Año" value={anio} onChange={handleAnioChange}
            disabled={!modeloId || loading === 'anios'}
            placeholder={loading === 'anios' ? 'Cargando…' : '— Selecciona —'}
          >
            {anios.map(a => <option key={a} value={a}>{a}</option>)}
          </SelectField>

          <SelectField
            label="Motor (opcional)" value={motor} onChange={handleMotorChange}
            disabled={!anio || loading === 'productos' || motores.length === 0}
            placeholder={motores.length === 0 ? '— sin opciones —' : '— Todos —'}
          >
            {motores.map(m => <option key={m} value={m}>{m}</option>)}
          </SelectField>
        </div>

        {/* Breadcrumb once marca + modelo + año are chosen */}
        {selectionComplete && (
          <div className="mt-3 pt-3 border-t border-surface-100 flex flex-wrap items-center gap-1 text-[12px] text-surface-500">
            <span className="font-medium text-surface-700">{marcaNombre}</span>
            <ChevronRight className="w-3 h-3" />
            <span className="font-medium text-surface-700">{modeloNombre}</span>
            <ChevronRight className="w-3 h-3" />
            <span className="font-medium text-surface-700">{anio}</span>
            {motor && (
              <>
                <ChevronRight className="w-3 h-3" />
                <span className="font-medium text-surface-700">{motor}</span>
              </>
            )}
          </div>
        )}
      </div>

      {/* ── Results ── */}
      {selectionComplete && (
        <div className="bg-white rounded-xl border border-surface-200 shadow-sm overflow-hidden">
          <div className="px-4 py-3 border-b border-surface-100 flex items-center justify-between">
            <div className="flex items-center gap-2">
              <Package className="w-4 h-4 text-surface-400" />
              <span className="text-sm font-medium text-surface-700">Refacciones compatibles</span>
            </div>
            {loading === 'productos' ? (
              <span className="text-xs text-surface-400">Cargando…</span>
            ) : productosError ? (
              <span className="text-xs text-red-400">Error</span>
            ) : (
              <span className="text-xs text-surface-400">
                {productos.length} resultado{productos.length !== 1 ? 's' : ''}
              </span>
            )}
          </div>

          {loading === 'productos' ? (
            <div className="flex items-center justify-center py-12">
              <div className="w-5 h-5 border-2 border-sap-blue/30 border-t-sap-blue rounded-full animate-spin" />
            </div>
          ) : productosError ? (
            <div className="flex items-center gap-2 mx-4 my-6 px-4 py-3 rounded-lg bg-red-50 border border-red-200 text-red-700 text-sm">
              <AlertCircle className="w-4 h-4 flex-shrink-0" />
              {productosError}
            </div>
          ) : productos.length === 0 ? (
            <div className="flex flex-col items-center justify-center py-12 text-surface-400">
              <Package className="w-8 h-8 mb-2 opacity-30" />
              <p className="text-sm">Ninguna refacción vinculada a este vehículo todavía</p>
              <p className="text-xs mt-1 text-surface-300">
                Puedes vincular productos desde la ficha técnica del producto
              </p>
            </div>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="text-[11px] font-semibold text-surface-400 uppercase tracking-wide bg-surface-50 border-b border-surface-100">
                    <th className="px-4 py-2.5 text-left">SKU</th>
                    <th className="px-4 py-2.5 text-left">Descripción</th>
                    <th className="px-4 py-2.5 text-left">Marca</th>
                    <th className="px-4 py-2.5 text-right">Precio</th>
                    <th className="px-4 py-2.5 text-center">Stock</th>
                    <th className="px-4 py-2.5 text-left">Notas</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-surface-50">
                  {productos.map(p => (
                    <tr key={p.id} className="hover:bg-surface-50/60 transition-colors">
                      <td className="px-4 py-3 font-mono text-xs text-surface-600 whitespace-nowrap">
                        <Link to={`/productos/${p.sku}`} className="hover:text-sap-blue hover:underline">
                          {p.sku}
                        </Link>
                      </td>
                      <td className="px-4 py-3 text-surface-800 font-medium">
                        <Link to={`/productos/${p.sku}`} className="hover:text-sap-blue hover:underline">
                          {p.name}
                        </Link>
                      </td>
                      <td className="px-4 py-3 text-surface-500 text-xs">{p.marca ?? '—'}</td>
                      <td className="px-4 py-3 text-right font-medium text-surface-800 tabular-nums whitespace-nowrap">
                        {p.costo_pos_con_iva != null && p.costo_pos_con_iva > 0
                          ? `$${Number(p.costo_pos_con_iva).toLocaleString('es-MX', { minimumFractionDigits: 2 })}`
                          : '—'}
                      </td>
                      <td className="px-4 py-3 text-center">
                        <StockBadge qty={p.stock} min={p.min_stock} />
                      </td>
                      <td className="px-4 py-3 text-xs text-surface-400 italic">
                        {p.notas_aplicacion ?? ''}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      )}

      {/* Prompt when nothing selected yet */}
      {!selectionComplete && !cascadeError && !loading && (
        <div className="flex flex-col items-center justify-center py-14 text-surface-300">
          <Car className="w-10 h-10 mb-3 opacity-30" />
          <p className="text-sm">Selecciona un vehículo para ver refacciones compatibles</p>
        </div>
      )}
    </div>
  );
}
