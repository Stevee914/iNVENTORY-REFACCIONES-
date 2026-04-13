import { cn } from '@/lib/utils';
import type { StockStatus, MovementType, Evento } from '@/types';
import { EVENTO_LABELS, EVENTO_COLORS } from '@/types';

export function StockStatusBadge({ status }: { status: StockStatus }) {
  return (
    <span
      className={cn(
        'badge',
        status === 'ok' && 'badge-ok',
        status === 'warn' && 'badge-warn',
        status === 'critical' && 'badge-critical'
      )}
    >
      {status === 'ok' && 'OK'}
      {status === 'warn' && 'Bajo'}
      {status === 'critical' && 'Crítico'}
    </span>
  );
}

export function MovementTypeBadge({ type }: { type: MovementType }) {
  return (
    <span
      className={cn(
        type === 'IN' && 'badge-in',
        type === 'OUT' && 'badge-out',
        type === 'ADJUST' && 'badge-adjust'
      )}
    >
      {type === 'IN' && 'Entrada'}
      {type === 'OUT' && 'Salida'}
      {type === 'ADJUST' && 'Ajuste'}
    </span>
  );
}

export function EventoBadge({ evento }: { evento: Evento }) {
  return (
    <span className={cn('badge border text-[10px]', EVENTO_COLORS[evento])}>
      {EVENTO_LABELS[evento]}
    </span>
  );
}
