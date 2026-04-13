import { useEffect, useState, useCallback } from 'react';
import { Search, AlertTriangle, ChevronLeft, ChevronRight, ChevronsLeft, ChevronsRight } from 'lucide-react';
import { PageHeader, StockStatusBadge } from '@/components/shared';
import { stockService } from '@/services';
import { getStockStatus, type StockItem } from '@/types';
import { cn } from '@/lib/utils';

const PAGE_SIZE = 50;

export function StockPage() {
  const [items, setItems] = useState<StockItem[]>([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  // Filters
  const [searchInput, setSearchInput] = useState('');
  const [searchQuery, setSearchQuery] = useState('');
  const [statusFilter, setStatusFilter] = useState<'all' | 'below' | 'negative'>('all');

  // Debounced search
  useEffect(() => {
    const timer = setTimeout(() => {
      setSearchQuery(searchInput);
      setPage(1);
    }, 350);
    return () => clearTimeout(timer);
  }, [searchInput]);

  // Load data from backend
  useEffect(() => {
    loadStock();
  }, [searchQuery, statusFilter, page]);

  async function loadStock() {
    setLoading(true);
    try {
      const res = await stockService.getAll({
        q: searchQuery || undefined,
        page,
        pageSize: PAGE_SIZE,
        belowMinStock: statusFilter === 'below',
        onlyNegative: statusFilter === 'negative',
      });
      setItems(res.items);
      setTotal(res.total);
    } catch (e: any) {
      setError(e.message);
    } finally {
      setLoading(false);
    }
  }

  const totalPages = Math.ceil(total / PAGE_SIZE);

  if (error && items.length === 0) {
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
        title="Stock Actual"
        description={`Vista consolidada — ${total} productos con stock calculado`}
      />

      {/* Search + Filters */}
      <div className="card px-5 py-4 mb-4">
        <div className="flex flex-col sm:flex-row gap-3 items-start sm:items-center">
          <div className="relative flex-1 max-w-md">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-brand-300" />
            <input
              type="text"
              value={searchInput}
              onChange={(e) => setSearchInput(e.target.value)}
              placeholder="Buscar por SKU, nombre, marca, código POS..."
              className="input-field pl-10 py-2"
            />
            {searchInput && (
              <button
                onClick={() => { setSearchInput(''); setSearchQuery(''); setPage(1); }}
                className="absolute right-3 top-1/2 -translate-y-1/2 text-brand-300 hover:text-brand-500 text-xs"
              >
                ✕
              </button>
            )}
          </div>
          <select
            value={statusFilter}
            onChange={(e) => { setStatusFilter(e.target.value as typeof statusFilter); setPage(1); }}
            className="select-field w-48 py-2 text-xs"
          >
            <option value="all">Todos los productos</option>
            <option value="below">Solo bajo mínimo</option>
            <option value="negative">Solo stock negativo</option>
          </select>
          <div className="text-xs text-brand-400 ml-auto">
            {total} resultado{total !== 1 ? 's' : ''}
          </div>
        </div>
      </div>

      {/* Table */}
      <div className="card overflow-hidden">
        <div className="overflow-x-auto">
          <table className="w-full">
            <thead>
              <tr className="bg-surface-50 border-b border-surface-200">
                <th className="table-header">SKU</th>
                <th className="table-header">Producto</th>
                <th className="table-header text-right">Stock Físico</th>
                <th className="table-header text-right">Stock POS</th>
                <th className="table-header text-right">Total</th>
                <th className="table-header text-right">Mínimo</th>
                <th className="table-header text-right">Dif. vs Mín</th>
                <th className="table-header">Estado</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-surface-100">
              {loading && items.length === 0 ? (
                <tr>
                  <td colSpan={8} className="px-4 py-12 text-center">
                    <div className="w-6 h-6 border-2 border-surface-300 border-t-sap-blue rounded-full animate-spin mx-auto" />
                  </td>
                </tr>
              ) : items.length === 0 ? (
                <tr>
                  <td colSpan={8} className="px-4 py-12 text-center text-[13px] text-brand-400">
                    {searchQuery ? `Sin resultados para "${searchQuery}"` : 'No se encontraron registros'}
                  </td>
                </tr>
              ) : (
                items.map((s) => {
                  const status = getStockStatus(s.stock_fisico, s.min_stock);
                  const diff = s.stock_fisico - s.min_stock;
                  return (
                    <tr key={s.sku} className={cn('hover:bg-surface-50 transition-colors', loading && 'opacity-50')}>
                      <td className="table-cell">
                        <span className="font-mono text-xs font-medium text-brand-600">{s.sku}</span>
                      </td>
                      <td className="table-cell">
                        <span className="text-[13px] text-brand-800 truncate max-w-xs block">{s.name}</span>
                      </td>
                      <td className="table-cell text-right">
                        <span className={cn('text-base font-bold tabular-nums', status === 'critical' && 'text-status-critical', status === 'warn' && 'text-status-warn')}>
                          {s.stock_fisico}
                        </span>
                      </td>
                      <td className="table-cell text-right">
                        <span className="tabular-nums text-[13px] text-brand-500">{s.stock_pos}</span>
                      </td>
                      <td className="table-cell text-right">
                        <span className="tabular-nums text-[13px] font-semibold text-brand-800">{s.stock_total}</span>
                      </td>
                      <td className="table-cell text-right">
                        <span className="tabular-nums text-[13px] text-brand-400">{s.min_stock}</span>
                      </td>
                      <td className="table-cell text-right">
                        <span className={cn('tabular-nums text-sm font-medium', diff < 0 ? 'text-status-critical' : diff === 0 ? 'text-status-warn' : 'text-brand-500')}>
                          {diff >= 0 ? '+' : ''}{diff}
                        </span>
                      </td>
                      <td className="table-cell">
                        <StockStatusBadge status={status} />
                      </td>
                    </tr>
                  );
                })
              )}
            </tbody>
          </table>
        </div>

        {/* Pagination */}
        {totalPages > 1 && (
          <div className="p-3 border-t border-surface-200 flex items-center justify-between">
            <p className="text-xs text-brand-400">
              Página {page} de {totalPages} — {total} productos
            </p>
            <div className="flex items-center gap-0.5">
              <button onClick={() => setPage(1)} disabled={page <= 1} className="btn-ghost p-1.5 disabled:opacity-30">
                <ChevronsLeft className="w-4 h-4" />
              </button>
              <button onClick={() => setPage((p) => Math.max(1, p - 1))} disabled={page <= 1} className="btn-ghost p-1.5 disabled:opacity-30">
                <ChevronLeft className="w-4 h-4" />
              </button>
              <button onClick={() => setPage((p) => Math.min(totalPages, p + 1))} disabled={page >= totalPages} className="btn-ghost p-1.5 disabled:opacity-30">
                <ChevronRight className="w-4 h-4" />
              </button>
              <button onClick={() => setPage(totalPages)} disabled={page >= totalPages} className="btn-ghost p-1.5 disabled:opacity-30">
                <ChevronsRight className="w-4 h-4" />
              </button>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
