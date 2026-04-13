/**
 * VehicleCompatSection
 *
 * Shows vehicle applications linked to a product and lets the user
 * add or remove them via the cascading make → model → year → style flow.
 *
 * Used inside ProductDetailPage below the Datos Técnicos card.
 */

import { useEffect, useRef, useState } from 'react';
import { Car, Plus, Trash2, ChevronRight, X, AlertCircle, Check } from 'lucide-react';
import {
  vehiculosService,
  type AplicacionProducto,
  type Marca,
  type Modelo,
  type Aplicacion,
} from '@/services/vehiculosService';
import { cn } from '@/lib/utils';

// ─── Motor label helper ───────────────────────────────────────────────────────

function motorLabel(a: { motor?: string | null; traccion?: string | null; carroceria?: string | null }): string {
  const parts: string[] = [];
  if (a.motor) parts.push(a.motor);
  if (a.traccion) parts.push(a.traccion);
  if (a.carroceria) parts.push(a.carroceria);
  return parts.join(' · ');
}

// ─── Cascade select ───────────────────────────────────────────────────────────

function CascadeSelect({
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
      <label className="text-[10px] font-semibold text-surface-500 uppercase tracking-wide">{label}</label>
      <select
        value={value}
        onChange={(e) => onChange(e.target.value)}
        disabled={disabled}
        className="h-8 rounded-lg border border-surface-200 bg-white px-2.5 text-[13px] text-surface-800
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

// ─── Add-application modal ────────────────────────────────────────────────────

interface AddModalProps {
  onClose: () => void;
  onAdded: () => void;
  productoId: number;
  existingIds: Set<number>;
}

function AddModal({ onClose, onAdded, productoId, existingIds }: AddModalProps) {
  const [marcas, setMarcas]         = useState<Marca[]>([]);
  const [modelos, setModelos]       = useState<Modelo[]>([]);
  const [anios, setAnios]           = useState<number[]>([]);
  const [aplicaciones, setAplicaciones] = useState<Aplicacion[]>([]);

  const [marcaId, setMarcaId]           = useState('');
  const [modeloId, setModeloId]         = useState('');
  const [anio, setAnio]                 = useState('');
  const [aplicacionId, setAplicacionId] = useState('');
  const [notas, setNotas]               = useState('');

  const [loading, setLoading]   = useState<string | null>(null);
  const [saving, setSaving]     = useState(false);
  const [error, setError]       = useState<string | null>(null);

  const overlayRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    vehiculosService.getMarcas().then(setMarcas).catch(() => setError('Error cargando marcas'));
  }, []);

  // Close on outside click
  function handleOverlayClick(e: React.MouseEvent) {
    if (e.target === overlayRef.current) onClose();
  }

  function handleMarcaChange(v: string) {
    setMarcaId(v); setModeloId(''); setAnio(''); setAplicacionId('');
    setModelos([]); setAnios([]); setAplicaciones([]);
    if (!v) return;
    setLoading('modelos');
    vehiculosService.getModelos(Number(v))
      .then(setModelos).catch(() => setError('Error cargando modelos')).finally(() => setLoading(null));
  }

  function handleModeloChange(v: string) {
    setModeloId(v); setAnio(''); setAplicacionId('');
    setAnios([]); setAplicaciones([]);
    if (!v) return;
    setLoading('anios');
    vehiculosService.getAnios(Number(v))
      .then(setAnios).catch(() => setError('Error cargando años')).finally(() => setLoading(null));
  }

  function handleAnioChange(v: string) {
    setAnio(v); setAplicacionId('');
    setAplicaciones([]);
    if (!v || !modeloId) return;
    setLoading('apls');
    vehiculosService.getAplicaciones(Number(modeloId), Number(v))
      .then(setAplicaciones).catch(() => setError('Error cargando versiones')).finally(() => setLoading(null));
  }

  async function handleConfirm() {
    if (!aplicacionId) return;
    setSaving(true);
    setError(null);
    try {
      await vehiculosService.linkProducto(Number(aplicacionId), productoId, notas || undefined);
      onAdded();
    } catch {
      setError('No se pudo guardar. Intenta de nuevo.');
    } finally {
      setSaving(false);
    }
  }

  const aplSel = aplicaciones.find(a => String(a.id) === aplicacionId);
  const alreadyLinked = aplicacionId ? existingIds.has(Number(aplicacionId)) : false;
  const canConfirm = !!aplicacionId && !alreadyLinked && !saving;

  return (
    <div
      ref={overlayRef}
      onClick={handleOverlayClick}
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 backdrop-blur-sm p-4"
    >
      <div className="bg-white rounded-xl shadow-xl w-full max-w-lg">
        {/* Header */}
        <div className="flex items-center justify-between px-5 py-4 border-b border-surface-100">
          <div className="flex items-center gap-2">
            <Car className="w-4 h-4 text-sap-blue" />
            <h3 className="text-[14px] font-semibold text-surface-900">Asignar vehículo compatible</h3>
          </div>
          <button onClick={onClose} className="p-1 rounded-lg text-surface-400 hover:text-surface-600 hover:bg-surface-100 transition-colors">
            <X className="w-4 h-4" />
          </button>
        </div>

        {/* Body */}
        <div className="px-5 py-4 space-y-4">
          {error && (
            <div className="flex items-center gap-2 text-[12px] text-red-600 bg-red-50 rounded-lg px-3 py-2 border border-red-100">
              <AlertCircle className="w-3.5 h-3.5 flex-shrink-0" /> {error}
            </div>
          )}

          <div className="grid grid-cols-2 gap-3">
            <CascadeSelect label="Marca" value={marcaId} onChange={handleMarcaChange} placeholder="— Selecciona —">
              {marcas.map(m => <option key={m.id} value={m.id}>{m.nombre}</option>)}
            </CascadeSelect>

            <CascadeSelect
              label="Modelo" value={modeloId} onChange={handleModeloChange}
              disabled={!marcaId || loading === 'modelos'}
              placeholder={loading === 'modelos' ? 'Cargando…' : '— Selecciona —'}
            >
              {modelos.map(m => <option key={m.id} value={m.id}>{m.nombre}</option>)}
            </CascadeSelect>

            <CascadeSelect
              label="Año" value={anio} onChange={handleAnioChange}
              disabled={!modeloId || loading === 'anios'}
              placeholder={loading === 'anios' ? 'Cargando…' : '— Selecciona —'}
            >
              {anios.map(a => <option key={a} value={a}>{a}</option>)}
            </CascadeSelect>

            <CascadeSelect
              label="Versión / Estilo" value={aplicacionId} onChange={setAplicacionId}
              disabled={!anio || loading === 'apls'}
              placeholder={loading === 'apls' ? 'Cargando…' : '— Selecciona —'}
            >
              {aplicaciones.map(a => {
                const meta = motorLabel(a);
                const dup = existingIds.has(a.id);
                return (
                  <option key={a.id} value={a.id} disabled={dup}>
                    {a.motor}{meta ? ` — ${[a.traccion, a.carroceria].filter(Boolean).join(' · ')}` : ''}{dup ? ' ✓' : ''}
                  </option>
                );
              })}
            </CascadeSelect>
          </div>

          {/* Selected breadcrumb */}
          {aplSel && (
            <div className="flex flex-wrap items-center gap-1 text-[11px] text-surface-500 bg-surface-50 rounded-lg px-3 py-2">
              <span className="font-medium text-surface-700">{marcas.find(m => String(m.id) === marcaId)?.nombre}</span>
              <ChevronRight className="w-3 h-3" />
              <span className="font-medium text-surface-700">{modelos.find(m => String(m.id) === modeloId)?.nombre}</span>
              <ChevronRight className="w-3 h-3" />
              <span className="font-medium text-surface-700">{anio}</span>
              <ChevronRight className="w-3 h-3" />
              <span>{aplSel.motor}</span>
              {motorLabel(aplSel) && (
                <span className="ml-1 px-1.5 py-0.5 rounded-full bg-surface-200 text-surface-600">
                  {motorLabel(aplSel)}
                </span>
              )}
              {alreadyLinked && (
                <span className="ml-auto flex items-center gap-1 text-amber-600">
                  <Check className="w-3 h-3" /> Ya asignado
                </span>
              )}
            </div>
          )}

          {/* Optional notes */}
          <div>
            <label className="text-[10px] font-semibold text-surface-500 uppercase tracking-wide block mb-1">
              Notas (opcional)
            </label>
            <input
              value={notas}
              onChange={(e) => setNotas(e.target.value)}
              placeholder="Ej: Solo modelos con A/C, Requiere adaptador…"
              className="w-full h-8 rounded-lg border border-surface-200 px-3 text-[13px] text-surface-800
                         focus:outline-none focus:ring-2 focus:ring-sap-blue/30 focus:border-sap-blue transition-colors"
            />
          </div>
        </div>

        {/* Footer */}
        <div className="flex items-center justify-end gap-2 px-5 py-4 border-t border-surface-100">
          <button onClick={onClose} className="btn-secondary text-xs">Cancelar</button>
          <button
            onClick={handleConfirm}
            disabled={!canConfirm}
            className={cn(
              'btn-primary text-xs',
              !canConfirm && 'opacity-50 cursor-not-allowed'
            )}
          >
            {saving ? 'Guardando…' : 'Confirmar asignación'}
          </button>
        </div>
      </div>
    </div>
  );
}

// ─── Main component ───────────────────────────────────────────────────────────

interface VehicleCompatSectionProps {
  productId: number;
}

export function VehicleCompatSection({ productId }: VehicleCompatSectionProps) {
  const [applications, setApplications] = useState<AplicacionProducto[]>([]);
  const [loading, setLoading] = useState(true);
  const [showModal, setShowModal] = useState(false);
  const [removing, setRemoving] = useState<number | null>(null);

  function load() {
    setLoading(true);
    vehiculosService.getAplicacionesByProducto(productId)
      .then(setApplications)
      .catch(() => {})
      .finally(() => setLoading(false));
  }

  useEffect(() => { load(); }, [productId]);

  async function handleRemove(aplicacionId: number) {
    if (!confirm('¿Quitar esta compatibilidad?')) return;
    setRemoving(aplicacionId);
    try {
      await vehiculosService.unlinkProducto(aplicacionId, productId);
      setApplications(prev => prev.filter(a => a.aplicacion_id !== aplicacionId));
    } catch {
      // ignore – row stays in list
    } finally {
      setRemoving(null);
    }
  }

  const existingIds = new Set(applications.map(a => a.aplicacion_id));

  // Group by make for compact display
  const byMarca = applications.reduce<Record<string, AplicacionProducto[]>>((acc, a) => {
    (acc[a.marca] ??= []).push(a);
    return acc;
  }, {});

  return (
    <>
      <div className="card p-5 mt-5">
        <div className="flex items-center justify-between mb-4">
          <div className="flex items-center gap-2">
            <Car className="w-5 h-5 text-brand-500" />
            <h2 className="text-[13px] font-semibold text-brand-800">Compatibilidad de Vehículos</h2>
            {!loading && (
              <span className="text-[11px] text-surface-400 font-normal">
                {applications.length} {applications.length === 1 ? 'aplicación' : 'aplicaciones'}
              </span>
            )}
          </div>
          <button
            onClick={() => setShowModal(true)}
            className="btn-secondary text-xs flex items-center gap-1.5"
          >
            <Plus className="w-3.5 h-3.5" /> Asignar vehículo
          </button>
        </div>

        {loading ? (
          <div className="flex items-center justify-center py-6">
            <div className="w-4 h-4 border-2 border-surface-200 border-t-sap-blue rounded-full animate-spin" />
          </div>
        ) : applications.length === 0 ? (
          <div className="flex flex-col items-center justify-center py-8 text-surface-300 border border-dashed border-surface-200 rounded-lg">
            <Car className="w-7 h-7 mb-2 opacity-40" />
            <p className="text-[12px]">Sin vehículos asignados todavía</p>
            <button
              onClick={() => setShowModal(true)}
              className="mt-2 text-[11px] text-sap-blue hover:underline"
            >
              + Asignar primer vehículo
            </button>
          </div>
        ) : (
          <div className="space-y-3">
            {Object.entries(byMarca).map(([marca, rows]) => (
              <div key={marca}>
                {/* Make header */}
                <p className="text-[10px] font-semibold text-surface-400 uppercase tracking-[0.06em] mb-1.5">{marca}</p>
                <div className="space-y-1">
                  {rows.map(a => {
                    const meta = motorLabel(a);
                    return (
                      <div
                        key={a.aplicacion_id}
                        className="flex items-center gap-2 px-3 py-2 rounded-lg bg-surface-50 hover:bg-surface-100 transition-colors group"
                      >
                        {/* Model + year */}
                        <span className="text-[12px] font-medium text-surface-700 min-w-[110px]">
                          {a.modelo} {a.anio}
                        </span>

                        {/* Motor */}
                        <span className="text-[12px] text-surface-500 flex-1 truncate">
                          {a.motor}
                        </span>

                        {/* Motor metadata chips */}
                        {meta && (
                          <span className="hidden sm:inline-flex px-2 py-0.5 rounded-full bg-surface-200/70 text-[10px] text-surface-500 flex-shrink-0">
                            {meta}
                          </span>
                        )}

                        {/* Notes */}
                        {a.notas_aplicacion && (
                          <span className="hidden md:inline text-[11px] text-surface-400 italic truncate max-w-[160px]">
                            {a.notas_aplicacion}
                          </span>
                        )}

                        {/* Remove */}
                        <button
                          onClick={() => handleRemove(a.aplicacion_id)}
                          disabled={removing === a.aplicacion_id}
                          className="ml-auto flex-shrink-0 p-1 rounded text-surface-300
                                     opacity-0 group-hover:opacity-100
                                     hover:text-red-500 hover:bg-red-50 transition-all"
                          title="Quitar compatibilidad"
                        >
                          {removing === a.aplicacion_id
                            ? <div className="w-3.5 h-3.5 border border-current border-t-transparent rounded-full animate-spin" />
                            : <Trash2 className="w-3.5 h-3.5" />}
                        </button>
                      </div>
                    );
                  })}
                </div>
              </div>
            ))}
          </div>
        )}
      </div>

      {showModal && (
        <AddModal
          productoId={productId}
          existingIds={existingIds}
          onClose={() => setShowModal(false)}
          onAdded={() => { setShowModal(false); load(); }}
        />
      )}
    </>
  );
}
