import { useEffect, useState } from 'react';
import {
  Package, Warehouse, AlertTriangle, ArrowRightLeft, TrendingUp, DollarSign, Truck, FolderTree,
} from 'lucide-react';
import { KpiCard, PageHeader, StockStatusBadge } from '@/components/shared';
import { dashboardService } from '@/services';
import { formatNumber } from '@/lib/utils';
import { getStockStatus } from '@/types';
import type { DashboardResumen, ProductoCritico } from '@/types';

export function DashboardPage() {
  const [resumen, setResumen] = useState<DashboardResumen | null>(null);
  const [criticos, setCriticos] = useState<ProductoCritico[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  useEffect(() => {
    async function load() {
      try {
        const [res, crit] = await Promise.all([
          dashboardService.getResumen(),
          dashboardService.getProductosCriticos(),
        ]);
        setResumen(res);
        setCriticos(crit.items);
      } catch (e: any) {
        setError(e.message || 'Error conectando con el servidor');
      } finally {
        setLoading(false);
      }
    }
    load();
  }, []);

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="w-6 h-6 border-2 border-surface-300 border-t-sap-blue rounded-full animate-spin" />
      </div>
    );
  }

  if (error || !resumen) {
    return (
      <div className="card p-8 text-center">
        <AlertTriangle className="w-10 h-10 mx-auto text-status-critical mb-3" />
        <h2 className="text-lg font-semibold text-brand-800 mb-1">Error de conexión</h2>
        <p className="text-[13px] text-brand-500 mb-4">{error}</p>
        <p className="text-xs text-brand-400">
          Verifica que tu backend FastAPI esté corriendo en <code className="font-mono bg-surface-100 px-1.5 py-0.5 rounded">http://localhost:8000</code>
        </p>
      </div>
    );
  }

  return (
    <div>
      <PageHeader
        title="Dashboard"
        description="Resumen general del inventario — Refacciones y Llantas Jaime"
      />

      {/* KPIs principales */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4 mb-6">
        <KpiCard
          title="Total SKUs"
          value={formatNumber(resumen.total_productos)}
          icon={Package}
          subtitle={`${resumen.productos_activos} activos`}
        />
        <KpiCard
          title="Valor Inventario"
          value={`$${formatNumber(Math.round(resumen.valor_inventario_fisico))}`}
          icon={DollarSign}
          subtitle="Stock físico × precio"
        />
        <KpiCard
          title="Bajo Mínimo"
          value={resumen.bajo_minimo}
          icon={AlertTriangle}
          variant="critical"
          subtitle={`${resumen.sin_stock_con_minimo} sin stock`}
        />
        <KpiCard
          title="Movimientos 30d"
          value={resumen.movimientos_30d.total}
          icon={ArrowRightLeft}
          subtitle={`${resumen.movimientos_30d.entradas} ent. / ${resumen.movimientos_30d.salidas} sal.`}
        />
      </div>

      {/* Segunda fila de KPIs */}
      <div className="grid grid-cols-1 sm:grid-cols-3 gap-4 mb-6">
        <KpiCard
          title="Proveedores"
          value={resumen.total_proveedores}
          icon={Truck}
          subtitle="Registrados"
        />
        <KpiCard
          title="Categorías"
          value={resumen.total_categorias}
          icon={FolderTree}
          subtitle="En catálogo"
        />
        <KpiCard
          title="Stock Negativo"
          value={resumen.stock_negativo}
          icon={AlertTriangle}
          variant={resumen.stock_negativo > 0 ? 'warning' : 'default'}
          subtitle="Productos por revisar"
        />
      </div>

      {/* Alertas de stock */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6 mb-6">
        <div className="card p-5">
          <div className="flex items-center justify-between mb-4">
            <div>
              <h2 className="text-[13px] font-semibold text-brand-800">Productos Críticos</h2>
              <p className="text-[11px] text-brand-400 mt-0.5">Stock bajo nivel mínimo</p>
            </div>
            <AlertTriangle className="w-4 h-4 text-status-critical" />
          </div>
          <div className="space-y-2 max-h-[40vh] md:max-h-[360px] overflow-y-auto">
            {criticos.length === 0 ? (
              <p className="text-[13px] text-brand-400 text-center py-8">Sin alertas de stock</p>
            ) : (
              criticos.slice(0, 12).map((item) => {
                const status = getStockStatus(item.stock_fisico, item.min_stock);
                return (
                  <div
                    key={item.sku}
                    className="flex items-center justify-between p-2.5 rounded-lg bg-surface-50 border border-surface-100"
                  >
                    <div className="min-w-0 flex-1">
                      <p className="text-xs font-mono text-brand-500">{item.sku}</p>
                      <p className="text-[13px] font-medium text-brand-800 truncate">{item.name}</p>
                      {item.marca && <p className="text-[10px] text-brand-400">{item.marca}</p>}
                    </div>
                    <div className="text-right flex-shrink-0 ml-3">
                      <p className={`text-lg font-bold tabular-nums ${status === 'critical' ? 'text-status-critical' : 'text-status-warn'}`}>
                        {item.stock_fisico}
                      </p>
                      <p className="text-[10px] text-brand-400">mín: {item.min_stock}</p>
                    </div>
                  </div>
                );
              })
            )}
          </div>
        </div>

        {/* Actividad reciente */}
        <div className="card p-5">
          <div className="flex items-center justify-between mb-4">
            <div>
              <h2 className="text-[13px] font-semibold text-brand-800">Actividad Últimos 30 Días</h2>
              <p className="text-[11px] text-brand-400 mt-0.5">Resumen de movimientos</p>
            </div>
            <TrendingUp className="w-4 h-4 text-brand-300" />
          </div>
          <div className="space-y-4">
            {[
              { label: 'Entradas', value: resumen.movimientos_30d.entradas, color: 'bg-status-ok' },
              { label: 'Salidas', value: resumen.movimientos_30d.salidas, color: 'bg-status-critical' },
              { label: 'Ajustes', value: resumen.movimientos_30d.ajustes, color: 'bg-status-warn' },
            ].map((item) => {
              const total = resumen.movimientos_30d.total || 1;
              return (
                <div key={item.label}>
                  <div className="flex justify-between text-sm mb-1.5">
                    <span className="text-brand-600 font-medium">{item.label}</span>
                    <span className="tabular-nums text-brand-500">{item.value} movimientos</span>
                  </div>
                  <div className="w-full bg-surface-100 rounded-full h-3">
                    <div
                      className={`${item.color} h-3 rounded-full transition-all`}
                      style={{ width: `${Math.max((item.value / total) * 100, 2)}%` }}
                    />
                  </div>
                </div>
              );
            })}
          </div>
        </div>
      </div>
    </div>
  );
}
