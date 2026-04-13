import { useEffect, useRef, useState } from 'react';
import { useNavigate, useParams } from 'react-router-dom';
import {
  ArrowLeft, Check, AlertTriangle, XCircle, Minus,
  Search, Plus, Package, FileText, X, Loader2, Trash2, Ban,
} from 'lucide-react';
import { PageHeader } from '@/components/shared';
import { comprasXmlService } from '@/services/comprasXmlService';
import { productService } from '@/services';
import { useDebounce } from '@/hooks/useDebounce';
import type { RevisionData, LineaDetalle, Candidate } from '@/services/comprasXmlService';
import type { Product } from '@/types';

function fmt(n: number) {
  return `$${Number(n).toLocaleString('es-MX', { minimumFractionDigits: 2 })}`;
}

const STATUS_CONFIG: Record<string, { label: string; rowBg: string; badge: string }> = {
  MATCHED:         { label: 'Vinculado',    rowBg: 'bg-emerald-50/60',  badge: 'bg-emerald-50 text-emerald-700 border border-emerald-200' },
  SUGGESTED_MATCH: { label: 'Sugerido',     rowBg: 'bg-amber-50/60',    badge: 'bg-amber-50 text-amber-700 border border-amber-200' },
  UNRESOLVED:      { label: 'Sin resolver', rowBg: 'bg-red-50/60',      badge: 'bg-red-50 text-red-700 border border-red-200' },
  SERVICE:         { label: 'Servicio',     rowBg: 'bg-surface-50',     badge: 'bg-surface-100 text-brand-400 border border-surface-200' },
  EXCLUDED:        { label: 'Excluida',     rowBg: 'bg-surface-50',     badge: 'bg-surface-100 text-brand-300 border border-surface-200' },
};

interface CrearForm {
  sku: string;
  name: string;
  marca: string;
  unit: string;
  price: string;
  precio_publico: string;
  codigo_cat: string;
}

// ── Main page ────────────────────────────────────────────────────────────────

export function CompraXmlReviewPage() {
  const { compraId } = useParams<{ compraId: string }>();
  const navigate = useNavigate();
  const compraIdNum = Number(compraId);

  const [revision, setRevision] = useState<RevisionData | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  // Inline expanded action: which line and what mode
  const [expanded, setExpanded] = useState<{ lineaId: number; mode: 'confirmar' | 'vincular' } | null>(null);
  const [savingLineId, setSavingLineId] = useState<number | null>(null);

  // Inline search state (shared by both Vincular and Buscar-otro flows)
  const [searchQ, setSearchQ] = useState('');
  const debouncedQ = useDebounce(searchQ, 300);
  const [searchResults, setSearchResults] = useState<Product[]>([]);
  const [searchLoading, setSearchLoading] = useState(false);
  // searchMode: lineaId currently showing the search input inside the confirmar panel
  const [searchMode, setSearchMode] = useState<number | null>(null);

  // Crear product modal
  const [crearModal, setCrearModal] = useState<{ lineaId: number; linea: LineaDetalle } | null>(null);
  const [crearForm, setCrearForm] = useState<CrearForm>({ sku: '', name: '', marca: '', unit: 'PZA', price: '', precio_publico: '', codigo_cat: '' });
  const [crearSaving, setCrearSaving] = useState(false);
  const [crearError, setCrearError] = useState('');

  // Import
  const [importConfirm, setImportConfirm] = useState(false);
  const [importing, setImporting] = useState(false);
  const [imported, setImported] = useState(false);

  // Cancel compra
  const [cancelConfirm, setCancelConfirm] = useState(false);
  const [cancelling, setCancelling] = useState(false);

  // Financial discount
  const [descuentoInput, setDescuentoInput] = useState('');
  const [descuentoSaving, setDescuentoSaving] = useState(false);

  // Toast
  const [toast, setToast] = useState<string | null>(null);
  const toastTimer = useRef<ReturnType<typeof setTimeout> | null>(null);

  function showToast(msg: string) {
    setToast(msg);
    if (toastTimer.current) clearTimeout(toastTimer.current);
    toastTimer.current = setTimeout(() => setToast(null), 5000);
  }

  // ── Load revision ──────────────────────────────────────────────────────────

  const loadRevision = async () => {
    setLoading(true);
    try {
      const data = await comprasXmlService.getRevision(compraIdNum);
      setRevision(data);
      if (data.compra.estatus_workflow === 'IMPORTED') setImported(true);
      setDescuentoInput(String(data.compra.descuento_financiero ?? 0));
    } catch (e: any) {
      setError(e.message);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { loadRevision(); }, [compraIdNum]);

  // ── Vincular search ────────────────────────────────────────────────────────

  useEffect(() => {
    if (!debouncedQ || debouncedQ.length < 2) { setSearchResults([]); return; }
    setSearchLoading(true);
    productService.search(debouncedQ, 10)
      .then(res => setSearchResults(res.items))
      .catch(() => setSearchResults([]))
      .finally(() => setSearchLoading(false));
  }, [debouncedQ]);

  // ── Actions ────────────────────────────────────────────────────────────────

  function toggleExpanded(lineaId: number, mode: 'confirmar' | 'vincular') {
    setExpanded(prev =>
      prev?.lineaId === lineaId && prev.mode === mode ? null : { lineaId, mode }
    );
    setSearchQ('');
    setSearchResults([]);
    setSearchMode(null);
  }

  function enterSearchMode(lineaId: number) {
    setSearchMode(lineaId);
    setSearchQ('');
    setSearchResults([]);
  }

  async function handleConfirmar(lineaId: number, productId: number) {
    setSavingLineId(lineaId);
    try {
      const res: any = await comprasXmlService.confirmarMatch(compraIdNum, lineaId, productId);
      setExpanded(null);
      setSearchMode(null);
      setSearchQ('');
      setSearchResults([]);
      showToast(`Vinculado correctamente. Pendientes: ${res.lineas_pendientes}`);
      await loadRevision();
    } catch (e: any) {
      showToast(`Error: ${e.message}`);
    } finally {
      setSavingLineId(null);
    }
  }

  function openCrearModal(linea: LineaDetalle) {
    const rawSku = (linea.codigo_proveedor || '').toUpperCase().replace(/[^A-Z0-9]/g, '');
    setCrearForm({
      sku: rawSku,
      name: `${linea.descripcion_xml || ''} ${linea.codigo_proveedor || ''}`.trim(),
      marca: '',
      unit: 'PZA',
      price: linea.precio_unit != null ? String(linea.precio_unit) : '',
      precio_publico: '',
      codigo_cat: '',
    });
    setCrearError('');
    setCrearModal({ lineaId: linea.id, linea });
  }

  async function handleCrearProducto() {
    if (!crearModal) return;
    if (!crearForm.sku.trim()) { setCrearError('SKU es obligatorio'); return; }
    if (!crearForm.name.trim()) { setCrearError('Nombre es obligatorio'); return; }

    setCrearSaving(true);
    setCrearError('');
    try {
      const res: any = await comprasXmlService.crearProducto(compraIdNum, crearModal.lineaId, {
        sku: crearForm.sku.trim(),
        name: crearForm.name.trim(),
        marca: crearForm.marca.trim() || undefined,
        unit: crearForm.unit,
        price: crearForm.price ? parseFloat(crearForm.price) : 0,
        precio_publico: crearForm.precio_publico ? parseFloat(crearForm.precio_publico) : undefined,
        codigo_cat: crearForm.codigo_cat.trim() || undefined,
      });
      setCrearModal(null);
      showToast(`Producto creado: ${res.product_created?.sku}. Pendientes: ${res.lineas_pendientes}`);
      await loadRevision();
    } catch (e: any) {
      setCrearError(e.message);
    } finally {
      setCrearSaving(false);
    }
  }

  async function handleImportar() {
    setImporting(true);
    try {
      const res: any = await comprasXmlService.importar(compraIdNum);
      setImportConfirm(false);
      setImported(true);
      showToast(`Compra importada. ${res.movements_created} movimientos generados.`);
      await loadRevision();
    } catch (e: any) {
      setImportConfirm(false);
      showToast(`Error: ${e.message}`);
    } finally {
      setImporting(false);
    }
  }

  async function handleCancelarCompra() {
    setCancelling(true);
    try {
      await comprasXmlService.cancelarCompra(compraIdNum);
      navigate('/compras');
    } catch (e: any) {
      setCancelConfirm(false);
      showToast(`Error: ${e.message}`);
    } finally {
      setCancelling(false);
    }
  }

  async function handleExcluir(lineaId: number) {
    setSavingLineId(lineaId);
    try {
      await comprasXmlService.excluirLinea(compraIdNum, lineaId);
      setExpanded(null);
      await loadRevision();
    } catch (e: any) {
      showToast(`Error: ${e.message}`);
    } finally {
      setSavingLineId(null);
    }
  }

  async function handleIncluir(lineaId: number) {
    setSavingLineId(lineaId);
    try {
      await comprasXmlService.incluirLinea(compraIdNum, lineaId);
      await loadRevision();
    } catch (e: any) {
      showToast(`Error: ${e.message}`);
    } finally {
      setSavingLineId(null);
    }
  }

  async function handleDescuentoFinanciero() {
    const pct = parseFloat(descuentoInput);
    if (isNaN(pct) || pct < 0 || pct > 100) {
      showToast('Porcentaje inválido (0–100)');
      return;
    }
    setDescuentoSaving(true);
    try {
      await comprasXmlService.setDescuentoFinanciero(compraIdNum, pct);
      await loadRevision();
    } catch (e: any) {
      showToast(`Error: ${e.message}`);
    } finally {
      setDescuentoSaving(false);
    }
  }

  // ── Render helpers ─────────────────────────────────────────────────────────

  // Shared inline search input + results — used by both Vincular and Buscar-otro flows
  function renderInlineSearch(linea: LineaDetalle, onClose: () => void) {
    const isSaving = savingLineId === linea.id;
    return (
      <div className="space-y-2">
        <div className="relative">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-3.5 h-3.5 text-brand-300 pointer-events-none" />
          <input
            autoFocus
            value={searchQ}
            onChange={e => setSearchQ(e.target.value)}
            placeholder="Buscar por nombre, SKU, marca..."
            className="input-field pl-8 py-2 text-[12px]"
          />
          {searchLoading && (
            <Loader2 className="absolute right-3 top-1/2 -translate-y-1/2 w-3.5 h-3.5 animate-spin text-brand-300" />
          )}
        </div>
        {searchResults.length > 0 && (
          <div className="border border-surface-200 rounded-lg overflow-hidden shadow-sm">
            {searchResults.map(p => (
              <div
                key={p.id}
                className="flex items-center justify-between px-3 py-2 bg-white hover:bg-surface-50 cursor-pointer border-b border-surface-100 last:border-0 group"
                onClick={() => !isSaving && handleConfirmar(linea.id, p.id)}
              >
                <div className="min-w-0">
                  <span className="text-[12px] font-semibold text-brand-800">{p.sku}</span>
                  {p.marca && <span className="text-[11px] text-brand-400 ml-1.5">{p.marca}</span>}
                  <span className="text-[12px] text-brand-500 ml-2">{p.name}</span>
                </div>
                {isSaving
                  ? <Loader2 className="w-3 h-3 animate-spin text-brand-400 shrink-0" />
                  : <Check className="w-3 h-3 text-brand-200 group-hover:text-sap-blue shrink-0" />
                }
              </div>
            ))}
          </div>
        )}
        {debouncedQ.length >= 2 && !searchLoading && searchResults.length === 0 && (
          <p className="text-[12px] text-brand-400 px-1">Sin resultados para "{debouncedQ}"</p>
        )}
        <div className="flex items-center gap-2">
          <button
            onClick={() => { onClose(); openCrearModal(linea); }}
            className="btn-ghost py-1 px-2 text-[12px]"
          >
            <Plus className="w-3 h-3" /> Crear producto nuevo
          </button>
          <button
            onClick={onClose}
            className="btn-ghost py-1 px-2 text-[12px]"
          >
            <X className="w-3 h-3" /> Cancelar
          </button>
        </div>
      </div>
    );
  }

  function renderConfirmarExpanded(linea: LineaDetalle) {
    const candidates = linea.candidates || [];
    const isSaving = savingLineId === linea.id;

    // Search sub-mode: "Buscar otro" was clicked
    if (searchMode === linea.id) {
      return (
        <div className="space-y-2">
          <div className="flex items-center justify-between mb-1">
            <button
              onClick={() => { setSearchMode(null); setSearchQ(''); setSearchResults([]); }}
              className="btn-ghost py-0.5 px-2 text-[11px] text-brand-400"
            >
              <ArrowLeft className="w-3 h-3" /> Volver a candidatos
            </button>
            <button onClick={() => setExpanded(null)} className="btn-ghost p-1">
              <X className="w-3.5 h-3.5" />
            </button>
          </div>
          {renderInlineSearch(linea, () => { setSearchMode(null); setSearchQ(''); setSearchResults([]); })}
        </div>
      );
    }

    // Candidate list view
    return (
      <div className="space-y-2">
        <div className="flex items-center justify-between">
          <p className="text-[11px] font-semibold text-brand-500 uppercase tracking-wide">
            {candidates.length === 0
              ? 'Sin candidatos automáticos'
              : `${candidates.length} candidato${candidates.length > 1 ? 's' : ''} — elige uno:`}
          </p>
          <button onClick={() => setExpanded(null)} className="btn-ghost p-1">
            <X className="w-3.5 h-3.5" />
          </button>
        </div>

        {candidates.length > 0 && (
          <div className="border border-surface-200 rounded-lg overflow-hidden">
            {candidates.map((c: Candidate) => (
              <div
                key={c.product_id}
                className="flex items-center justify-between gap-3 px-3 py-2 bg-white hover:bg-surface-50 border-b border-surface-100 last:border-0 cursor-pointer group"
                onClick={() => !isSaving && handleConfirmar(linea.id, c.product_id)}
              >
                <div className="min-w-0">
                  <span className="text-[12px] font-semibold text-brand-800">{c.sku}</span>
                  <span className="text-[12px] text-brand-500 ml-2">{c.name}</span>
                </div>
                {isSaving
                  ? <Loader2 className="w-3 h-3 animate-spin text-brand-400 shrink-0" />
                  : <Check className="w-3 h-3 text-brand-200 group-hover:text-sap-blue shrink-0" />
                }
              </div>
            ))}
          </div>
        )}

        <button
          onClick={() => enterSearchMode(linea.id)}
          className="btn-ghost py-1 px-2 text-[12px]"
        >
          <Search className="w-3 h-3" /> Buscar otro producto
        </button>
      </div>
    );
  }

  function renderVincularExpanded(linea: LineaDetalle) {
    return renderInlineSearch(linea, () => {
      setExpanded(null);
      setSearchQ('');
      setSearchResults([]);
    });
  }

  function renderLineActions(linea: LineaDetalle) {
    if (imported) return null;

    const isSaving = savingLineId === linea.id;

    if (linea.status_match === 'EXCLUDED') {
      return (
        <button
          onClick={() => !isSaving && handleIncluir(linea.id)}
          disabled={isSaving}
          className="btn-ghost py-1 px-2 text-[12px] text-brand-400 hover:text-brand-600"
        >
          {isSaving ? <Loader2 className="w-3 h-3 animate-spin" /> : <Ban className="w-3 h-3" />}
          Incluir
        </button>
      );
    }

    if (linea.es_servicio || linea.status_match === 'MATCHED') return null;

    const isExp = expanded?.lineaId === linea.id;

    const excludeBtn = (
      <button
        onClick={() => !isSaving && handleExcluir(linea.id)}
        disabled={isSaving}
        title="Excluir línea"
        className="btn-ghost py-1 px-1.5 text-[12px] text-brand-300 hover:text-red-500"
      >
        {isSaving ? <Loader2 className="w-3 h-3 animate-spin" /> : <Ban className="w-3 h-3" />}
      </button>
    );

    if (linea.status_match === 'SUGGESTED_MATCH') {
      return (
        <div className="flex items-center gap-1">
          <button
            onClick={() => toggleExpanded(linea.id, 'confirmar')}
            className={isExp && expanded?.mode === 'confirmar'
              ? 'btn-secondary py-1 px-3 text-[12px]'
              : 'btn-primary py-1 px-3 text-[12px]'}
          >
            <Check className="w-3 h-3" />
            {isExp && expanded?.mode === 'confirmar' ? 'Cancelar' : 'Confirmar'}
          </button>
          <button
            onClick={() => openCrearModal(linea)}
            className="btn-ghost py-1 px-3 text-[12px]"
          >
            <Plus className="w-3 h-3" />
            Crear
          </button>
          {excludeBtn}
        </div>
      );
    }

    if (linea.status_match === 'UNRESOLVED') {
      return (
        <div className="flex gap-1.5 items-center">
          <button
            onClick={() => toggleExpanded(linea.id, 'vincular')}
            className="btn-secondary py-1 px-3 text-[12px]"
          >
            <Search className="w-3 h-3" />
            Vincular
          </button>
          <button
            onClick={() => openCrearModal(linea)}
            className="btn-ghost py-1 px-3 text-[12px]"
          >
            <Plus className="w-3 h-3" />
            Crear
          </button>
          {excludeBtn}
        </div>
      );
    }

    return null;
  }

  // ── Early returns ──────────────────────────────────────────────────────────

  if (loading) {
    return (
      <div className="flex items-center justify-center min-h-[60vh]">
        <div className="w-6 h-6 border-2 border-shell/30 border-t-shell rounded-full animate-spin" />
      </div>
    );
  }

  if (error) {
    return (
      <div className="card p-8 text-center">
        <AlertTriangle className="w-10 h-10 mx-auto text-status-critical mb-3" />
        <p className="text-[13px] text-brand-500">{error}</p>
        <button onClick={() => navigate('/compras')} className="btn-secondary mt-4">
          Volver a Compras
        </button>
      </div>
    );
  }

  if (!revision) return null;

  const { compra, lineas, counts, puede_importar } = revision;
  const pendientes = (counts.SUGGESTED_MATCH ?? 0) + (counts.UNRESOLVED ?? 0);

  // ── Render ─────────────────────────────────────────────────────────────────

  return (
    <div>
      <PageHeader
        title="Revisión de Compra XML"
        description={`Folio ${compra.folio_factura ?? '—'} · ${compra.proveedor_nombre ?? 'Proveedor no identificado'}`}
        actions={
          <div className="flex items-center gap-2">
            {!imported && (
              <button
                onClick={() => setCancelConfirm(true)}
                className="inline-flex items-center gap-1.5 px-3 py-2 text-[13px] font-medium text-red-600 border border-red-200 rounded-lg hover:bg-red-50 transition-colors"
              >
                <Trash2 className="w-3.5 h-3.5" /> Cancelar compra
              </button>
            )}
            <button onClick={() => navigate('/compras')} className="btn-secondary">
              <ArrowLeft className="w-4 h-4" /> Volver a Compras
            </button>
          </div>
        }
      />

      {/* ── Header card ── */}
      <div className="card p-4 mb-4 grid grid-cols-2 md:grid-cols-4 gap-x-6 gap-y-3">
        <div>
          <p className="label">Folio</p>
          <p className="text-[13px] font-semibold text-brand-800">{compra.folio_factura ?? '—'}</p>
        </div>
        <div>
          <p className="label">Proveedor</p>
          <p className="text-[13px] font-semibold text-brand-800">{compra.proveedor_nombre ?? '—'}</p>
          {compra.proveedor_rfc && <p className="text-[11px] text-brand-400">{compra.proveedor_rfc}</p>}
        </div>
        <div>
          <p className="label">Fecha</p>
          <p className="text-[13px] text-brand-700">{compra.fecha}</p>
        </div>
        {/* Totals: 3-column when discount is active */}
        {compra.descuento_financiero > 0 ? (
          <>
            <div>
              <p className="label">Total original</p>
              <p className="text-[13px] font-semibold text-brand-500 line-through">{fmt(compra.total_original ?? compra.total)}</p>
              <p className="text-[11px] text-brand-300">Sub {fmt(compra.subtotal_original ?? compra.subtotal)} + IVA {fmt(compra.iva_original ?? compra.iva)}</p>
            </div>
            <div>
              <p className="label">Desc. financiero</p>
              <div className="flex items-center gap-1.5 mt-0.5">
                <input
                  type="number"
                  min="0"
                  max="100"
                  step="0.1"
                  value={descuentoInput}
                  onChange={e => setDescuentoInput(e.target.value)}
                  onKeyDown={e => e.key === 'Enter' && handleDescuentoFinanciero()}
                  disabled={imported || descuentoSaving}
                  className="input-field w-16 py-1 px-2 text-[12px] text-center"
                />
                <span className="text-[12px] text-brand-400">%</span>
                {!imported && (
                  <button
                    onClick={handleDescuentoFinanciero}
                    disabled={descuentoSaving}
                    className="btn-secondary py-1 px-2 text-[12px]"
                  >
                    {descuentoSaving ? <Loader2 className="w-3 h-3 animate-spin" /> : 'Aplicar'}
                  </button>
                )}
              </div>
              <p className="text-[11px] text-emerald-600 mt-0.5">
                Ahorro: {fmt((compra.total_original ?? compra.total) - compra.total)}
              </p>
            </div>
            <div>
              <p className="label">Total a pagar</p>
              <p className="text-[13px] font-semibold text-emerald-700">{fmt(compra.total)}</p>
              <p className="text-[11px] text-brand-400">Sub {fmt(compra.subtotal)} + IVA {fmt(compra.iva)}</p>
            </div>
          </>
        ) : (
          <>
            <div>
              <p className="label">Total</p>
              <p className="text-[13px] font-semibold text-brand-800">{fmt(compra.total)}</p>
              <p className="text-[11px] text-brand-400">Sub {fmt(compra.subtotal)} + IVA {fmt(compra.iva)}</p>
            </div>
            {!imported && (
              <div>
                <p className="label">Desc. financiero</p>
                <div className="flex items-center gap-1.5 mt-0.5">
                  <input
                    type="number"
                    min="0"
                    max="100"
                    step="0.1"
                    value={descuentoInput}
                    onChange={e => setDescuentoInput(e.target.value)}
                    onKeyDown={e => e.key === 'Enter' && handleDescuentoFinanciero()}
                    disabled={descuentoSaving}
                    className="input-field w-16 py-1 px-2 text-[12px] text-center"
                    placeholder="0"
                  />
                  <span className="text-[12px] text-brand-400">%</span>
                  <button
                    onClick={handleDescuentoFinanciero}
                    disabled={descuentoSaving}
                    className="btn-secondary py-1 px-2 text-[12px]"
                  >
                    {descuentoSaving ? <Loader2 className="w-3 h-3 animate-spin" /> : 'Aplicar'}
                  </button>
                </div>
              </div>
            )}
          </>
        )}
        <div>
          <p className="label">Método de pago</p>
          <p className="text-[13px] text-brand-700">
            {compra.metodo_pago === 'PPD' ? 'PPD (Crédito)' : compra.metodo_pago === 'PUE' ? 'PUE (Contado)' : (compra.metodo_pago ?? '—')}
          </p>
        </div>
        <div>
          <p className="label">Estatus pago</p>
          <p className="text-[13px] text-brand-700">{compra.estatus}</p>
        </div>
        <div>
          <p className="label">Workflow</p>
          <span className={`badge ${
            compra.estatus_workflow === 'IMPORTED' ? 'bg-emerald-50 text-emerald-700 border border-emerald-200'
            : compra.estatus_workflow === 'READY' ? 'bg-blue-50 text-blue-700 border border-blue-200'
            : 'bg-amber-50 text-amber-700 border border-amber-200'
          }`}>
            {compra.estatus_workflow}
          </span>
        </div>
        <div className="col-span-2 md:col-span-1">
          <p className="label">UUID Fiscal</p>
          <p className="text-[11px] text-brand-400 font-mono break-all">{compra.uuid_fiscal ?? '—'}</p>
        </div>
      </div>

      {/* ── Status bar ── */}
      <div className="card p-4 mb-4 flex flex-wrap items-center gap-4">
        <div className="flex items-center gap-2">
          <Check className="w-4 h-4 text-emerald-600" />
          <span className="text-[13px] font-semibold text-emerald-700">{counts.MATCHED ?? 0} vinculados</span>
        </div>
        <div className="flex items-center gap-2">
          <AlertTriangle className="w-4 h-4 text-amber-500" />
          <span className="text-[13px] font-semibold text-amber-700">{counts.SUGGESTED_MATCH ?? 0} sugeridos</span>
        </div>
        <div className="flex items-center gap-2">
          <XCircle className="w-4 h-4 text-red-500" />
          <span className="text-[13px] font-semibold text-red-700">{counts.UNRESOLVED ?? 0} sin resolver</span>
        </div>
        <div className="flex items-center gap-2">
          <Minus className="w-4 h-4 text-brand-400" />
          <span className="text-[13px] text-brand-500">{counts.SERVICE ?? 0} servicio</span>
        </div>
        {(counts.EXCLUDED ?? 0) > 0 && (
          <div className="flex items-center gap-2">
            <Ban className="w-4 h-4 text-brand-300" />
            <span className="text-[13px] text-brand-400">{counts.EXCLUDED} excluida{counts.EXCLUDED !== 1 ? 's' : ''}</span>
          </div>
        )}
        {!imported && pendientes > 0 && (
          <p className="text-[12px] text-amber-600 ml-auto">
            {pendientes} {pendientes === 1 ? 'línea requiere' : 'líneas requieren'} revisión antes de importar
          </p>
        )}
        {imported && (
          <span className="ml-auto badge bg-emerald-50 text-emerald-700 border border-emerald-200 flex items-center gap-1">
            <Check className="w-3 h-3" /> IMPORTADA
          </span>
        )}
      </div>

      {/* ── Lines table ── */}
      <div className="card overflow-hidden mb-4">
        <div className="overflow-x-auto">
          <table className="w-full text-[12px]">
            <thead>
              <tr className="bg-surface-50 border-b border-surface-200">
                <th className="px-3 py-2.5 text-left font-semibold text-brand-500 text-[11px] uppercase tracking-wide w-8">#</th>
                <th className="px-3 py-2.5 text-left font-semibold text-brand-500 text-[11px] uppercase tracking-wide">Cód. Prov.</th>
                <th className="px-3 py-2.5 text-left font-semibold text-brand-500 text-[11px] uppercase tracking-wide">Descripción XML</th>
                <th className="px-3 py-2.5 text-right font-semibold text-brand-500 text-[11px] uppercase tracking-wide">Cant.</th>
                <th className="px-3 py-2.5 text-right font-semibold text-brand-500 text-[11px] uppercase tracking-wide">P. Unit.</th>
                <th className="px-3 py-2.5 text-left font-semibold text-brand-500 text-[11px] uppercase tracking-wide">Producto</th>
                <th className="px-3 py-2.5 text-left font-semibold text-brand-500 text-[11px] uppercase tracking-wide">Estado</th>
                <th className="px-3 py-2.5 text-left font-semibold text-brand-500 text-[11px] uppercase tracking-wide">Acción</th>
              </tr>
            </thead>
            <tbody>
              {lineas.map((l, idx) => {
                const cfg = STATUS_CONFIG[l.status_match] ?? STATUS_CONFIG.UNRESOLVED;
                const isExpanded = expanded?.lineaId === l.id;
                const isExcluded = l.status_match === 'EXCLUDED';
                const dimClass = isExcluded ? 'opacity-40 line-through' : '';
                return (
                  <>
                    <tr key={l.id} className={`border-b border-surface-100 ${cfg.rowBg}`}>
                      <td className={`px-3 py-2 text-brand-400 ${dimClass}`}>{idx + 1}</td>
                      <td className={`px-3 py-2 font-mono text-[11px] text-brand-700 font-semibold ${dimClass}`}>{l.codigo_proveedor ?? '—'}</td>
                      <td className={`px-3 py-2 text-brand-600 max-w-[200px] truncate ${dimClass}`} title={l.descripcion_xml ?? ''}>
                        {l.descripcion_xml ?? '—'}
                      </td>
                      <td className={`px-3 py-2 text-right text-brand-700 ${dimClass}`}>{l.cantidad}</td>
                      <td className={`px-3 py-2 text-right text-brand-700 ${dimClass}`}>
                        {l.precio_unit != null ? fmt(l.precio_unit) : '—'}
                      </td>
                      <td className={`px-3 py-2 max-w-[220px] ${dimClass}`}>
                        {l.product_id ? (
                          <div>
                            <span className="font-semibold text-brand-800">{l.product_sku}</span>
                            <span className="text-brand-500 ml-1.5">{l.product_name}</span>
                          </div>
                        ) : l.es_servicio ? (
                          <span className="text-brand-400 italic">Servicio / cargo</span>
                        ) : l.status_match === 'SUGGESTED_MATCH' && l.candidates.length > 0 ? (
                          <div className="truncate">
                            <span className="text-[11px] font-semibold text-brand-700">{l.candidates[0].sku}</span>
                            <span className="text-xs text-gray-500 ml-1.5 truncate">{l.candidates[0].name}</span>
                            {l.candidates.length > 1 && (
                              <span className="text-[10px] text-brand-300 ml-1">+{l.candidates.length - 1}</span>
                            )}
                          </div>
                        ) : (
                          <span className="text-brand-300">—</span>
                        )}
                      </td>
                      <td className="px-3 py-2">
                        <span className={`badge ${cfg.badge}`}>{cfg.label}</span>
                      </td>
                      <td className="px-3 py-2">
                        {renderLineActions(l)}
                      </td>
                    </tr>
                    {isExpanded && (
                      <tr key={`exp-${l.id}`} className="border-b border-surface-200">
                        <td colSpan={8} className="px-4 py-3 bg-white">
                          {expanded.mode === 'confirmar' && renderConfirmarExpanded(l)}
                          {expanded.mode === 'vincular' && renderVincularExpanded(l)}
                        </td>
                      </tr>
                    )}
                  </>
                );
              })}
            </tbody>
          </table>
        </div>
      </div>

      {/* ── Import button ── */}
      {!imported && (
        <div className="flex justify-end">
          <button
            disabled={!puede_importar || importing}
            onClick={() => setImportConfirm(true)}
            className="btn-primary disabled:opacity-40 disabled:cursor-not-allowed"
            title={!puede_importar ? 'Resuelve todas las líneas antes de importar' : undefined}
          >
            <FileText className="w-4 h-4" />
            {puede_importar ? 'Importar Compra' : `Importar (faltan ${pendientes} líneas)`}
          </button>
        </div>
      )}

      {/* ── Import confirm modal ── */}
      {importConfirm && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-brand-950/40 backdrop-blur-sm">
          <div className="card p-6 w-full max-w-sm mx-4 shadow-modal">
            <div className="flex items-center gap-2 mb-4">
              <FileText className="w-5 h-5 text-sap-blue" />
              <h2 className="text-[14px] font-semibold text-brand-800">Confirmar importación</h2>
            </div>
            <p className="text-[13px] text-brand-600 mb-2">
              ¿Importar compra <b>{compra.folio_factura}</b>?
            </p>
            <p className="text-[12px] text-brand-500 mb-5">
              Se generarán <b>{counts.MATCHED ?? 0}</b> movimientos de inventario (libro FÍSICO, tipo IN).
              Esta acción no se puede deshacer.
            </p>
            <div className="flex justify-end gap-2">
              <button onClick={() => setImportConfirm(false)} disabled={importing} className="btn-secondary">
                Cancelar
              </button>
              <button onClick={handleImportar} disabled={importing} className="btn-primary">
                {importing ? <Loader2 className="w-4 h-4 animate-spin" /> : <Check className="w-4 h-4" />}
                {importing ? 'Importando...' : 'Sí, importar'}
              </button>
            </div>
          </div>
        </div>
      )}

      {/* ── Cancel compra modal ── */}
      {cancelConfirm && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-brand-950/40 backdrop-blur-sm">
          <div className="card p-6 w-full max-w-sm mx-4 shadow-modal">
            <div className="flex items-center gap-2 mb-4">
              <Trash2 className="w-5 h-5 text-red-500" />
              <h2 className="text-[14px] font-semibold text-brand-800">Cancelar compra</h2>
            </div>
            <p className="text-[13px] text-brand-600 mb-5">
              ¿Cancelar esta compra? Se eliminará <b>{compra.folio_factura}</b> y todas sus líneas. Esta acción no se puede deshacer.
            </p>
            <div className="flex justify-end gap-2">
              <button onClick={() => setCancelConfirm(false)} disabled={cancelling} className="btn-secondary">
                Volver
              </button>
              <button
                onClick={handleCancelarCompra}
                disabled={cancelling}
                className="inline-flex items-center gap-2 px-4 py-2.5 text-[13px] font-semibold text-white bg-red-600 rounded-lg hover:bg-red-700 disabled:opacity-40 transition-colors"
              >
                {cancelling ? <Loader2 className="w-4 h-4 animate-spin" /> : <Trash2 className="w-4 h-4" />}
                {cancelling ? 'Cancelando...' : 'Sí, cancelar'}
              </button>
            </div>
          </div>
        </div>
      )}

      {/* ── Crear producto modal ── */}
      {crearModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-brand-950/40 backdrop-blur-sm">
          <div className="card p-6 w-full max-w-lg mx-4 shadow-modal overflow-y-auto max-h-[90vh]">
            <div className="flex items-center justify-between mb-4">
              <div className="flex items-center gap-2">
                <Package className="w-5 h-5 text-brand-500" />
                <h2 className="text-[14px] font-semibold text-brand-800">Crear Producto</h2>
              </div>
              <button onClick={() => setCrearModal(null)} className="btn-ghost p-1">
                <X className="w-4 h-4" />
              </button>
            </div>

            <div className="text-[11px] text-brand-400 bg-surface-50 rounded-lg px-3 py-2 mb-4">
              Línea XML: <b>{crearModal.linea.codigo_proveedor}</b> — {crearModal.linea.descripcion_xml}
            </div>

            {crearError && (
              <div className="p-3 rounded-lg bg-status-critical-muted border border-red-200 text-[12px] text-red-700 mb-4">
                {crearError}
              </div>
            )}

            <div className="space-y-3">
              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="label">SKU *</label>
                  <input
                    value={crearForm.sku}
                    onChange={e => setCrearForm(f => ({ ...f, sku: e.target.value.toUpperCase() }))}
                    className="input-field"
                    placeholder="Ej: A39"
                  />
                </div>
                <div>
                  <label className="label">Unidad</label>
                  <select
                    value={crearForm.unit}
                    onChange={e => setCrearForm(f => ({ ...f, unit: e.target.value }))}
                    className="select-field"
                  >
                    <option value="PZA">PZA</option>
                    <option value="JGO">JGO</option>
                    <option value="LT">LT</option>
                    <option value="KG">KG</option>
                    <option value="MT">MT</option>
                    <option value="PAR">PAR</option>
                  </select>
                </div>
              </div>

              <div>
                <label className="label">Nombre *</label>
                <input
                  value={crearForm.name}
                  onChange={e => setCrearForm(f => ({ ...f, name: e.target.value }))}
                  className="input-field"
                  placeholder="Nombre del producto"
                />
              </div>

              <div>
                <label className="label">Marca</label>
                <input
                  value={crearForm.marca}
                  onChange={e => setCrearForm(f => ({ ...f, marca: e.target.value.toUpperCase() }))}
                  className="input-field"
                  placeholder="Ej: GATES"
                />
              </div>

              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="label">Costo sin IVA</label>
                  <input
                    type="number"
                    min="0"
                    step="0.01"
                    value={crearForm.price}
                    onChange={e => setCrearForm(f => ({ ...f, price: e.target.value }))}
                    className="input-field"
                    placeholder="0.00"
                  />
                </div>
                <div>
                  <label className="label">Precio público</label>
                  <input
                    type="number"
                    min="0"
                    step="0.01"
                    value={crearForm.precio_publico}
                    onChange={e => setCrearForm(f => ({ ...f, precio_publico: e.target.value }))}
                    className="input-field"
                    placeholder="0.00"
                  />
                </div>
              </div>

              <div>
                <label className="label">Cód. categoría POS (4 dígitos)</label>
                <input
                  value={crearForm.codigo_cat}
                  onChange={e => setCrearForm(f => ({ ...f, codigo_cat: e.target.value }))}
                  className="input-field"
                  placeholder="Ej: 1234"
                  maxLength={4}
                />
              </div>
            </div>

            <div className="flex justify-end gap-2 mt-5 pt-4 border-t border-surface-200">
              <button onClick={() => setCrearModal(null)} className="btn-secondary">Cancelar</button>
              <button onClick={handleCrearProducto} disabled={crearSaving} className="btn-primary">
                {crearSaving ? <Loader2 className="w-4 h-4 animate-spin" /> : <Package className="w-4 h-4" />}
                {crearSaving ? 'Creando...' : 'Crear y vincular'}
              </button>
            </div>
          </div>
        </div>
      )}

      {/* ── Toast ── */}
      {toast && (
        <div className="fixed bottom-6 right-6 z-[60] flex items-center gap-3 px-4 py-3 rounded-xl shadow-lg border bg-emerald-50 border-emerald-200 text-emerald-800 max-w-sm">
          <p className="text-[13px] font-medium flex-1">{toast}</p>
          <button onClick={() => setToast(null)} className="shrink-0 opacity-60 hover:opacity-100">
            <X className="w-4 h-4" />
          </button>
        </div>
      )}
    </div>
  );
}
