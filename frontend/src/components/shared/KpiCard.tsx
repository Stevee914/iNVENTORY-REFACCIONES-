import { cn } from '@/lib/utils';
import type { LucideIcon } from 'lucide-react';

interface KpiCardProps {
  title: string;
  value: string | number;
  subtitle?: string;
  icon: LucideIcon;
  trend?: 'up' | 'down' | 'neutral';
  variant?: 'default' | 'warning' | 'critical';
}

export function KpiCard({ title, value, subtitle, icon: Icon, variant = 'default' }: KpiCardProps) {
  return (
    <div className="card p-5 hover:shadow-card-hover transition-shadow duration-300">
      <div className="flex items-start justify-between">
        <div className="flex-1 min-w-0">
          <p className="text-[11px] font-semibold text-brand-400 uppercase tracking-[0.05em]">{title}</p>
          <p
            className={cn(
              'mt-2 text-[26px] font-bold tabular-nums leading-none tracking-tight',
              variant === 'warning' && 'text-status-warn',
              variant === 'critical' && 'text-status-critical',
              variant === 'default' && 'text-brand-800'
            )}
          >
            {value}
          </p>
          {subtitle && <p className="mt-1.5 text-[11px] text-brand-400 font-medium">{subtitle}</p>}
        </div>
        <div
          className={cn(
            'w-9 h-9 rounded-lg flex items-center justify-center flex-shrink-0',
            variant === 'warning' && 'bg-status-warn-muted text-status-warn',
            variant === 'critical' && 'bg-status-critical-muted text-status-critical',
            variant === 'default' && 'bg-surface-100 text-brand-400'
          )}
        >
          <Icon className="w-[18px] h-[18px]" strokeWidth={1.8} />
        </div>
      </div>
    </div>
  );
}
