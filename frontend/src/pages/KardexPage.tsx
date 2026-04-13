import { useState } from 'react';
import { Search, AlertTriangle } from 'lucide-react';
import { PageHeader, MovementTypeBadge, EventoBadge } from '@/components/shared';
import { movementService } from '@/services';
import { formatDateTime } from '@/lib/utils';
import type { Movement } from '@/types';

export function KardexPage() {
  const [skuInput, setSkuInput] = useState('');
  const [searchedSku, setSearchedSku] = useState('');
  const [movements, setMovements] = useState<Movement[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [searched, setSearched] = useState(false);

  async function handleSearch(e: React.FormEvent) {
    e.preventDefault();
    const sku = skuInput.trim().toUpperCase();
    if (!sku) return;
    setLoading(true);
    setError('');
    setSearched(true);
    setSearchedSku(sku);
    try {
      const res = await movementService.getKardex(sku, 200);
      setMovements(res.items);
    } catch (err: any) {
      setError(err.message || 'Error al buscar kardex');
      setMovements([]);
    } finally {
      setLoading(false);
    }
  }

  return (
    <div>
      <PageHeader
        title="Kardex — Historial de Movimientos"
        description="Busca por SKU para ver el historial completo de transacciones"
      />

      <form onSubmit={handleSearch} className="card px-5 py-4 mb-6">
        <div className="flex items-center gap-3">
          <div className="relative flex-1 max-w-md">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-brand-300" />
            <input
              type="text"
              value={skuInput}
              onChange={(e) => setSkuInput(e.target.value.toUpperCase())}
              placeholder="Escribe un SKU... (ej: GAD-1)"
              className="input-field pl-10 font-mono"
            />
          </div>
          <button type="submit" disabled={loading || !skuInput.trim()} className="btn-primary">
            {loading ? 'Buscando...' : 'Buscar Kardex'}
          </button>
        </div>
      </form>

      {error && (
        <div className="card p-6 text-center mb-6">
          <AlertTriangle className="w-8 h-8 mx-auto text-status-critical mb-2" />
          <p className="text-[13px] text-brand-500">{error}</p>
        </div>
      )}

      {searched && !error && (
        <div className="card overflow-hidden">
          <div className="p-4 border-b border-surface-200">
            <h2 className="text-[13px] font-semibold text-brand-800">
              Kardex: <span className="font-mono">{searchedSku}</span>
            </h2>
            <p className="text-[11px] text-brand-400 mt-0.5">{movements.length} movimientos encontrados</p>
          </div>

          {loading ? (
            <div className="flex items-center justify-center h-32">
              <div className="w-6 h-6 border-2 border-surface-300 border-t-sap-blue rounded-full animate-spin" />
            </div>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full">
                <thead>
                  <tr className="bg-surface-50 border-b border-surface-200">
                    <th className="table-header">ID</th>
                    <th className="table-header">Fecha</th>
                    <th className="table-header">Libro</th>
                    <th className="table-header">Tipo</th>
                    <th className="table-header">Evento</th>
                    <th className="table-header text-right">Cantidad</th>
                    <th className="table-header text-right">Costo Unit.</th>
                    <th className="table-header">Referencia</th>
                    <th className="table-header">Notas</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-surface-100">
                  {movements.length === 0 ? (
                    <tr>
                      <td colSpan={9} className="px-4 py-12 text-center text-[13px] text-brand-400">
                        No hay movimientos para este SKU
                      </td>
                    </tr>
                  ) : (
                    movements.map((m) => (
                      <tr key={m.id} className="hover:bg-surface-50">
                        <td className="table-cell text-xs text-brand-400 tabular-nums">{m.id}</td>
                        <td className="table-cell text-xs text-brand-500 whitespace-nowrap">{formatDateTime(m.movement_date)}</td>
                        <td className="table-cell">
                          <span className={`badge text-[10px] ${m.libro === 'FISICO' ? 'bg-brand-50 text-brand-600' : 'bg-purple-50 text-purple-600'}`}>
                            {m.libro === 'FISICO' ? 'Físico' : 'POS'}
                          </span>
                        </td>
                        <td className="table-cell"><MovementTypeBadge type={m.movement_type} /></td>
                        <td className="table-cell"><EventoBadge evento={m.evento} /></td>
                        <td className="table-cell text-right tabular-nums font-medium">{m.quantity}</td>
                        <td className="table-cell text-right tabular-nums text-xs text-brand-500">
                          {m.costo_unit_sin_iva ? `$${m.costo_unit_sin_iva.toFixed(2)}` : '—'}
                        </td>
                        <td className="table-cell text-xs text-brand-500 truncate max-w-[140px]">{m.reference || '—'}</td>
                        <td className="table-cell text-xs text-brand-400 truncate max-w-[140px]">{m.notes || '—'}</td>
                      </tr>
                    ))
                  )}
                </tbody>
              </table>
            </div>
          )}
        </div>
      )}

      {!searched && (
        <div className="card p-12 text-center text-brand-400">
          <Search className="w-10 h-10 mx-auto mb-3 text-brand-200" />
          <p className="text-sm">Ingresa un SKU arriba para consultar su kardex completo</p>
        </div>
      )}
    </div>
  );
}
