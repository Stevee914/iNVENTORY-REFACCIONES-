import { useState, useEffect } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import {
  ArrowLeft, Save, Pencil, Package, Ruler, MapPin, Car, CheckCircle, AlertTriangle, TrendingUp,
} from 'lucide-react';
import { PageHeader } from '@/components/shared';
import { productService } from '@/services';
import { getFichaLevel, type Product, type TechFormData, type ProductMargen } from '@/types';
import { VehicleCompatSection } from '@/components/VehicleCompatSection';
import { cn, formatDate } from '@/lib/utils';

export function ProductDetailPage() {
  const { sku } = useParams();
  const navigate = useNavigate();

  const [product, setProduct] = useState<Product | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [margen, setMargen] = useState<ProductMargen | null>(null);

  // Ficha técnica editable
  const [editing, setEditing] = useState(false);
  const [saving, setSaving] = useState(false);
  const [saveMsg, setSaveMsg] = useState('');
  const [saveError, setSaveError] = useState('');

  const [form, setForm] = useState<TechFormData>({
    aplicacion: '',
    equivalencia: '',
    ubicacion: '',
    descripcion_larga: '',
    anio_inicio: null,
    anio_fin: null,
    dim_largo: null,
    dim_ancho: null,
    dim_alto: null,
    imagen_url: '',
  });

  useEffect(() => {
    if (!sku) return;
    setLoading(true);
    productService.getBySku(sku)
      .then((p) => {
        setProduct(p);
        // Fetch margin data in parallel — silently ignore if unavailable
        productService.getMargen(p.sku).then(setMargen).catch(() => {});
        setForm({
          aplicacion: p.aplicacion || '',
          equivalencia: p.equivalencia || '',
          ubicacion: p.ubicacion || '',
          descripcion_larga: p.descripcion_larga || '',
          anio_inicio: p.anio_inicio,
          anio_fin: p.anio_fin,
          dim_largo: p.dim_largo,
          dim_ancho: p.dim_ancho,
          dim_alto: p.dim_alto,
          imagen_url: p.imagen_url || '',
        });
      })
      .catch((e) => setError(e.message || 'Producto no encontrado'))
      .finally(() => setLoading(false));
  }, [sku]);

  async function handleSaveTech() {
    if (!sku) return;
    setSaving(true);
    setSaveError('');
    setSaveMsg('');

    try {
      // Solo enviar campos que cambiaron
      const payload: Partial<TechFormData> = {};
      if (form.aplicacion !== (product?.aplicacion || '')) payload.aplicacion = form.aplicacion;
      if (form.equivalencia !== (product?.equivalencia || '')) payload.equivalencia = form.equivalencia;
      if (form.ubicacion !== (product?.ubicacion || '')) payload.ubicacion = form.ubicacion;
      if (form.descripcion_larga !== (product?.descripcion_larga || '')) payload.descripcion_larga = form.descripcion_larga;
      if (form.anio_inicio !== product?.anio_inicio) payload.anio_inicio = form.anio_inicio;
      if (form.anio_fin !== product?.anio_fin) payload.anio_fin = form.anio_fin;
      if (form.dim_largo !== product?.dim_largo) payload.dim_largo = form.dim_largo;
      if (form.dim_ancho !== product?.dim_ancho) payload.dim_ancho = form.dim_ancho;
      if (form.dim_alto !== product?.dim_alto) payload.dim_alto = form.dim_alto;
      if (form.imagen_url !== (product?.imagen_url || '')) payload.imagen_url = form.imagen_url;

      if (Object.keys(payload).length === 0) {
        setSaveMsg('No hay cambios que guardar');
        setSaving(false);
        return;
      }

      // Validación: año fin >= año inicio
      if (payload.anio_inicio !== undefined && payload.anio_fin !== undefined &&
          payload.anio_inicio && payload.anio_fin && payload.anio_fin < payload.anio_inicio) {
        setSaveError('El año final no puede ser menor al año inicial');
        setSaving(false);
        return;
      }

      const res = await productService.updateTech(sku, payload);
      setProduct(res.product);
      setSaveMsg('Ficha técnica actualizada correctamente');
      setEditing(false);
    } catch (err: any) {
      setSaveError(err.message || 'Error al guardar');
    } finally {
      setSaving(false);
    }
  }

  function cancelEdit() {
    if (product) {
      setForm({
        aplicacion: product.aplicacion || '',
        equivalencia: product.equivalencia || '',
        ubicacion: product.ubicacion || '',
        descripcion_larga: product.descripcion_larga || '',
        anio_inicio: product.anio_inicio,
        anio_fin: product.anio_fin,
        dim_largo: product.dim_largo,
        dim_ancho: product.dim_ancho,
        dim_alto: product.dim_alto,
        imagen_url: product.imagen_url || '',
      });
    }
    setEditing(false);
    setSaveError('');
    setSaveMsg('');
  }

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="w-6 h-6 border-2 border-surface-300 border-t-sap-blue rounded-full animate-spin" />
      </div>
    );
  }

  if (error || !product) {
    return (
      <div className="card p-8 text-center">
        <AlertTriangle className="w-10 h-10 mx-auto text-status-critical mb-3" />
        <p className="text-[13px] text-brand-500 mb-4">{error || 'Producto no encontrado'}</p>
        <button onClick={() => navigate('/productos')} className="btn-secondary">
          <ArrowLeft className="w-4 h-4" /> Volver a productos
        </button>
      </div>
    );
  }

  const ficha = getFichaLevel(product);

  const fichaLevelColors = {
    'Básico': 'bg-surface-100 text-brand-500',
    'Parcial': 'bg-amber-50 text-amber-700 border border-amber-200',
    'Completo': 'bg-emerald-50 text-emerald-700 border border-emerald-200',
  };

  return (
    <div className="max-w-4xl">
      <PageHeader
        title={product.name}
        description={`SKU: ${product.sku}${product.marca ? ` — ${product.marca}` : ''}`}
        actions={
          <div className="flex items-center gap-2">
            <button onClick={() => navigate(`/productos/${product.sku}/editar`)} className="btn-secondary">
              <Pencil className="w-4 h-4" /> Editar Datos Base
            </button>
            <button onClick={() => navigate(-1)} className="btn-ghost">
              <ArrowLeft className="w-4 h-4" /> Volver
            </button>
          </div>
        }
      />

      {/* Datos base (solo lectura) */}
      <div className="card p-5 mb-6">
        <div className="flex items-center gap-2 mb-4">
          <Package className="w-5 h-5 text-brand-500" />
          <h2 className="text-[13px] font-semibold text-brand-800">Datos del Producto</h2>
          <span className={cn('badge ml-auto text-xs', fichaLevelColors[ficha.level])}>
            Ficha: {ficha.level} ({ficha.filled}/{ficha.total})
          </span>
        </div>

        <div className="grid grid-cols-2 sm:grid-cols-4 gap-4">
          <InfoField label="SKU" value={product.sku} mono />
          <InfoField label="Código POS" value={product.codigo_pos} mono />
          <InfoField label="Código CAT" value={product.codigo_cat} mono />
          <InfoField label="Marca" value={product.marca} />
          <InfoField label="Unidad" value={product.unit} />
          <InfoField label="Stock Mínimo" value={String(product.min_stock)} />
          <InfoField
            label="Precio c/IVA"
            value={product.costo_pos_con_iva != null && product.costo_pos_con_iva > 0
              ? `$${product.costo_pos_con_iva.toLocaleString('es-MX', { minimumFractionDigits: 2 })}`
              : '—'}
          />
          <InfoField label="Estado" value={product.is_active ? 'Activo' : 'Inactivo'} />
          <InfoField label="Creado" value={formatDate(product.created_at)} className="col-span-2" />
        </div>
      </div>

      {/* Precios y Costos */}
      <div className="card p-5 mb-6">
        <div className="flex items-center gap-2 mb-4">
          <TrendingUp className="w-5 h-5 text-brand-500" />
          <h2 className="text-[13px] font-semibold text-brand-800">Precios y Costos</h2>
          {margen?.fuente_costo && (
            <span className={cn(
              'badge ml-auto text-xs',
              margen.fuente_costo === 'REAL'
                ? 'bg-emerald-50 text-emerald-700 border border-emerald-200'
                : 'bg-amber-50 text-amber-700 border border-amber-200'
            )}>
              Fuente: {margen.fuente_costo}
            </span>
          )}
        </div>
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-4">
          <PriceField label="Costo POS con IVA" value={product.costo_pos_con_iva} />
          <PriceField
            label="Costo Base sin IVA"
            value={margen?.costo_base ?? (product.costo_pos_con_iva ? product.costo_pos_con_iva / 1.16 : null)}
          />
          <PriceField label="Costo Real sin IVA" value={margen?.costo_real_sin_iva} />
          <div>
            <p className="text-[10px] font-semibold text-brand-400 uppercase tracking-[0.06em]">Fuente de Costo</p>
            <p className={cn('mt-1 text-[13px] font-semibold',
              margen?.fuente_costo === 'REAL' ? 'text-emerald-600'
              : margen?.fuente_costo === 'POS' ? 'text-amber-600'
              : 'text-brand-300 italic font-normal'
            )}>
              {margen?.fuente_costo ?? '—'}
            </p>
          </div>
          <PriceField label="Precio Público (venta)" value={product.precio_publico} highlight />
          <PriceField label="Utilidad" value={margen?.utilidad} highlight={!!margen?.utilidad && margen.utilidad > 0} />
          <div>
            <p className="text-[10px] font-semibold text-brand-400 uppercase tracking-[0.06em]">Margen %</p>
            <p className={cn('mt-1 text-[13px] font-semibold tabular-nums',
              margen?.margen_porcentaje == null ? 'text-brand-300 italic font-normal'
              : margen.margen_porcentaje >= 20 ? 'text-emerald-600'
              : margen.margen_porcentaje >= 10 ? 'text-amber-600'
              : 'text-red-600'
            )}>
              {margen?.margen_porcentaje != null ? `${margen.margen_porcentaje.toFixed(1)}%` : '—'}
            </p>
          </div>
        </div>
      </div>

      {/* Ficha Técnica (editable) */}
      <div className="card p-5">
        <div className="flex items-center justify-between mb-4">
          <div className="flex items-center gap-2">
            <Ruler className="w-5 h-5 text-brand-500" />
            <h2 className="text-[13px] font-semibold text-brand-800">Datos Técnicos</h2>
          </div>
          {!editing && (
            <button
              onClick={() => { setEditing(true); setSaveMsg(''); }}
              className="btn-secondary text-xs"
            >
              <Pencil className="w-3.5 h-3.5" /> Completar Ficha
            </button>
          )}
        </div>

        {saveMsg && (
          <div className="p-3 rounded-lg bg-status-ok-muted border border-emerald-200 text-[13px] text-emerald-700 mb-4 flex items-center gap-2">
            <CheckCircle className="w-4 h-4 flex-shrink-0" /> {saveMsg}
          </div>
        )}
        {saveError && (
          <div className="p-3 rounded-lg bg-status-critical-muted border border-red-200 text-[13px] text-red-700 mb-4">{saveError}</div>
        )}

        {editing ? (
          /* ─── Modo edición ─── */
          <div className="space-y-4">
            {/* Aplicación */}
            <div>
              <label className="label flex items-center gap-1.5">
                <Car className="w-3.5 h-3.5" /> Aplicación
              </label>
              <input
                value={form.aplicacion}
                onChange={(e) => setForm((f) => ({ ...f, aplicacion: e.target.value }))}
                placeholder="Ej: Nissan Tsuru, Toyota Hilux 2.7L, Freightliner M2..."
                className="input-field"
              />
            </div>

            {/* Equivalencia */}
            <div>
              <label className="label">Equivalencia</label>
              <input
                value={form.equivalencia}
                onChange={(e) => setForm((f) => ({ ...f, equivalencia: e.target.value }))}
                placeholder="Ej: OEM 48520-12340, Monroe 71964..."
                className="input-field"
              />
            </div>

            {/* Ubicación */}
            <div>
              <label className="label flex items-center gap-1.5">
                <MapPin className="w-3.5 h-3.5" /> Ubicación en almacén
              </label>
              <input
                value={form.ubicacion}
                onChange={(e) => setForm((f) => ({ ...f, ubicacion: e.target.value }))}
                placeholder="Ej: Pasillo 3, Estante B, Nivel 2"
                className="input-field"
              />
            </div>

            {/* Descripción larga */}
            <div>
              <label className="label">Descripción larga</label>
              <textarea
                value={form.descripcion_larga}
                onChange={(e) => setForm((f) => ({ ...f, descripcion_larga: e.target.value }))}
                placeholder="Detalles adicionales, compatibilidades, notas técnicas..."
                rows={3}
                className="input-field resize-none"
              />
            </div>

            {/* Dimensiones */}
            <div>
              <label className="label flex items-center gap-1.5 mb-2">
                <Ruler className="w-3.5 h-3.5" /> Dimensiones (cm)
              </label>
              <div className="grid grid-cols-3 gap-3">
                <div>
                  <span className="text-[10px] text-brand-400 uppercase">Largo</span>
                  <input
                    type="number"
                    value={form.dim_largo ?? ''}
                    onChange={(e) => setForm((f) => ({ ...f, dim_largo: e.target.value ? parseFloat(e.target.value) : null }))}
                    placeholder="0.0"
                    step="0.1"
                    min={0}
                    className="input-field tabular-nums"
                  />
                </div>
                <div>
                  <span className="text-[10px] text-brand-400 uppercase">Ancho</span>
                  <input
                    type="number"
                    value={form.dim_ancho ?? ''}
                    onChange={(e) => setForm((f) => ({ ...f, dim_ancho: e.target.value ? parseFloat(e.target.value) : null }))}
                    placeholder="0.0"
                    step="0.1"
                    min={0}
                    className="input-field tabular-nums"
                  />
                </div>
                <div>
                  <span className="text-[10px] text-brand-400 uppercase">Alto</span>
                  <input
                    type="number"
                    value={form.dim_alto ?? ''}
                    onChange={(e) => setForm((f) => ({ ...f, dim_alto: e.target.value ? parseFloat(e.target.value) : null }))}
                    placeholder="0.0"
                    step="0.1"
                    min={0}
                    className="input-field tabular-nums"
                  />
                </div>
              </div>
            </div>

            {/* URL de imagen */}
            <div>
              <label className="label">URL de imagen</label>
              <input
                value={form.imagen_url || ''}
                onChange={(e) => setForm((f) => ({ ...f, imagen_url: e.target.value }))}
                placeholder="https://drive.google.com/... o https://imgur.com/..."
                className="input-field"
              />
              <p className="text-[10px] text-brand-400 mt-0.5">Link a foto del producto (Google Drive, Imgur, etc.)</p>
              {form.imagen_url && (
                <img
                  src={form.imagen_url}
                  alt="Preview"
                  className="mt-2 max-w-[120px] max-h-24 rounded border border-surface-200 object-contain"
                  onError={(e) => { (e.target as HTMLImageElement).style.display = 'none'; }}
                />
              )}
            </div>

            {/* Botones */}
            <div className="flex items-center justify-end gap-3 pt-4 border-t border-surface-200">
              <button type="button" onClick={cancelEdit} className="btn-secondary">
                Cancelar
              </button>
              <button onClick={handleSaveTech} disabled={saving} className="btn-primary">
                <Save className="w-4 h-4" />
                {saving ? 'Guardando...' : 'Guardar Ficha Técnica'}
              </button>
            </div>
          </div>
        ) : (
          /* ─── Modo lectura ─── */
          <div className="flex gap-6">
            <div className="flex-1 grid grid-cols-1 sm:grid-cols-2 gap-4">
              <InfoField label="Aplicación" value={product.aplicacion} icon={<Car className="w-3.5 h-3.5" />} className="sm:col-span-2" />
              <InfoField label="Equivalencia" value={product.equivalencia} className="sm:col-span-2" />
              <InfoField label="Ubicación" value={product.ubicacion} icon={<MapPin className="w-3.5 h-3.5" />} />
              <InfoField label="Descripción larga" value={product.descripcion_larga} className="sm:col-span-2" />
              <InfoField
                label="Dimensiones (L × A × A)"
                value={
                  product.dim_largo || product.dim_ancho || product.dim_alto
                    ? `${product.dim_largo || '—'} × ${product.dim_ancho || '—'} × ${product.dim_alto || '—'} cm`
                    : null
                }
                icon={<Ruler className="w-3.5 h-3.5" />}
              />
            </div>
            {product.imagen_url && (
              <div className="flex-shrink-0">
                <p className="text-[10px] font-semibold text-brand-400 uppercase tracking-[0.06em] mb-2">Imagen</p>
                <img
                  src={product.imagen_url}
                  alt={product.name}
                  className="w-64 max-h-64 rounded-lg border border-surface-200 object-contain"
                  onError={(e) => { (e.target as HTMLImageElement).style.display = 'none'; }}
                />
              </div>
            )}
          </div>
        )}
      </div>

      {/* Compatibilidad de vehículos */}
      <VehicleCompatSection productId={product.id} />
    </div>
  );
}

// ─── Componente auxiliar PriceField ─────────────────────────────

function PriceField({
  label,
  value,
  highlight,
}: {
  label: string;
  value: number | null | undefined;
  highlight?: boolean;
}) {
  const hasValue = value != null && value !== 0;
  return (
    <div>
      <p className="text-[10px] font-semibold text-brand-400 uppercase tracking-[0.06em]">{label}</p>
      <p className={cn(
        'mt-1 text-[13px] tabular-nums',
        !hasValue ? 'text-brand-300 italic' : highlight ? 'text-brand-800 font-semibold' : 'text-brand-800'
      )}>
        {hasValue
          ? `$${(value as number).toLocaleString('es-MX', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`
          : '—'}
      </p>
    </div>
  );
}

// ─── Componente auxiliar InfoField ──────────────────────────────

function InfoField({
  label,
  value,
  mono,
  icon,
  className,
}: {
  label: string;
  value: string | number | null | undefined;
  mono?: boolean;
  icon?: React.ReactNode;
  className?: string;
}) {
  return (
    <div className={className}>
      <p className="text-[10px] font-semibold text-brand-400 uppercase tracking-[0.06em] flex items-center gap-1">
        {icon} {label}
      </p>
      <p
        className={cn(
          'mt-1 text-[13px]',
          value ? 'text-brand-800' : 'text-brand-300 italic',
          mono && 'font-mono'
        )}
      >
        {value || 'Sin datos'}
      </p>
    </div>
  );
}
