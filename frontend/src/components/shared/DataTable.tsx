import { useState, useMemo, type ReactNode } from 'react';
import { Search, ChevronLeft, ChevronRight, ChevronsLeft, ChevronsRight } from 'lucide-react';

export interface Column<T> {
  key: string;
  header: string;
  render: (item: T) => ReactNode;
  sortable?: boolean;
  className?: string;
}

interface DataTableProps<T> {
  data: T[];
  columns: Column<T>[];
  searchPlaceholder?: string;
  searchFn?: (item: T, query: string) => boolean;
  pageSize?: number;
  emptyMessage?: string;
  filters?: ReactNode;
  /** When provided, search query and page number are persisted to sessionStorage under this key. */
  storageKey?: string;
}

/**
 * Normaliza texto para búsqueda: quita acentos, minúsculas, trim
 */
function normalize(text: string): string {
  return text
    .toLowerCase()
    .normalize('NFD')
    .replace(/[\u0300-\u036f]/g, '')
    .trim();
}

/**
 * Búsqueda inteligente: cada palabra del query debe aparecer en el texto.
 * Funciona con palabras parciales y en cualquier orden.
 * Ej: "monroe delantero" matchea "Amortiguador Delantero Monroe Matic Plus"
 */
export function fuzzyMatch(text: string, query: string): boolean {
  const normalizedText = normalize(text);
  const words = normalize(query).split(/\s+/).filter(Boolean);
  return words.every((word) => normalizedText.includes(word));
}

export function DataTable<T>({
  data,
  columns,
  searchPlaceholder = 'Buscar...',
  searchFn,
  pageSize = 25,
  emptyMessage = 'No se encontraron registros',
  filters,
  storageKey,
}: DataTableProps<T>) {
  const [search, setSearch] = useState(() =>
    storageKey ? (sessionStorage.getItem(`${storageKey}_q`) ?? '') : ''
  );
  const [page, setPage] = useState(() =>
    storageKey ? parseInt(sessionStorage.getItem(`${storageKey}_p`) ?? '0', 10) : 0
  );

  function updateSearch(value: string) {
    if (storageKey) sessionStorage.setItem(`${storageKey}_q`, value);
    setSearch(value);
    updatePage(0);
  }

  function updatePage(value: number) {
    if (storageKey) sessionStorage.setItem(`${storageKey}_p`, String(value));
    setPage(value);
  }

  const filtered = useMemo(() => {
    if (!search || !searchFn) return data;
    return data.filter((item) => searchFn(item, search));
  }, [data, search, searchFn]);

  const totalPages = Math.ceil(filtered.length / pageSize);
  const paginated = filtered.slice(page * pageSize, (page + 1) * pageSize);

  return (
    <div className="card overflow-hidden">
      {/* Toolbar */}
      <div className="px-5 py-4 border-b border-surface-200 flex flex-col sm:flex-row gap-3 items-start sm:items-center">
        {searchFn && (
          <div className="relative flex-1 max-w-md">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-brand-300" />
            <input
              type="text"
              value={search}
              onChange={(e) => updateSearch(e.target.value)}
              placeholder={searchPlaceholder}
              className="input-field pl-10 py-2"
            />
            {search && (
              <button
                onClick={() => updateSearch('')}
                className="absolute right-3 top-1/2 -translate-y-1/2 text-brand-300 hover:text-brand-500 text-xs font-medium transition-colors"
              >
                ✕
              </button>
            )}
          </div>
        )}
        {filters && <div className="flex items-center gap-2 flex-wrap">{filters}</div>}
        <div className="text-[11px] text-brand-400 ml-auto flex-shrink-0 font-medium tabular-nums">
          {filtered.length} registro{filtered.length !== 1 ? 's' : ''}
          {search && data.length !== filtered.length && ` de ${data.length}`}
        </div>
      </div>

      {/* Table */}
      <div className="overflow-x-auto">
        <table className="w-full">
          <thead>
            <tr className="border-b border-surface-200">
              {columns.map((col) => (
                <th key={col.key} className={`table-header ${col.className || ''}`}>
                  {col.header}
                </th>
              ))}
            </tr>
          </thead>
          <tbody className="divide-y divide-surface-100">
            {paginated.length === 0 ? (
              <tr>
                <td colSpan={columns.length} className="px-5 py-16 text-center text-[13px] text-brand-400">
                  {search ? `Sin resultados para "${search}"` : emptyMessage}
                </td>
              </tr>
            ) : (
              paginated.map((item, i) => (
                <tr key={i} className="hover:bg-surface-50 transition-colors duration-100">
                  {columns.map((col) => (
                    <td key={col.key} className={`table-cell ${col.className || ''}`}>
                      {col.render(item)}
                    </td>
                  ))}
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>

      {/* Pagination */}
      {totalPages > 1 && (
        <div className="px-5 py-3 border-t border-surface-200 flex items-center justify-between">
          <p className="text-[11px] text-brand-400 font-medium tabular-nums">
            Página {page + 1} de {totalPages} — mostrando {paginated.length} de {filtered.length}
          </p>
          <div className="flex items-center gap-0.5">
            <button onClick={() => updatePage(0)} disabled={page === 0} className="btn-ghost p-1.5 disabled:opacity-20" title="Primera página">
              <ChevronsLeft className="w-4 h-4" />
            </button>
            <button onClick={() => updatePage(Math.max(0, page - 1))} disabled={page === 0} className="btn-ghost p-1.5 disabled:opacity-20">
              <ChevronLeft className="w-4 h-4" />
            </button>
            <button onClick={() => updatePage(Math.min(totalPages - 1, page + 1))} disabled={page >= totalPages - 1} className="btn-ghost p-1.5 disabled:opacity-20">
              <ChevronRight className="w-4 h-4" />
            </button>
            <button onClick={() => updatePage(totalPages - 1)} disabled={page >= totalPages - 1} className="btn-ghost p-1.5 disabled:opacity-20" title="Última página">
              <ChevronsRight className="w-4 h-4" />
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
