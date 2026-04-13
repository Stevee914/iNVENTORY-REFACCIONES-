import type { ForecastItem } from '@/types';

// El forecast sigue siendo mock hasta que el backend lo implemente
const mockForecast: ForecastItem[] = [
  { sku: 'FRE-0412', productName: 'Balatas Wagner ThermoQuiet QC1001', category: 'Frenos', currentStock: 8, avgMonthlyDemand: 14, forecast30d: 16, suggestedReorder: 20, leadTimeDays: 5, safetyStock: 5, status: 'Reordenar' },
  { sku: 'BUJ-0310', productName: 'Bujía NGK BKR6E-11', category: 'Bujías', currentStock: 62, avgMonthlyDemand: 45, forecast30d: 50, suggestedReorder: 0, leadTimeDays: 3, safetyStock: 15, status: 'OK' },
  { sku: 'FIL-0510', productName: 'Filtro Aceite Wix WL7154', category: 'Filtros', currentStock: 28, avgMonthlyDemand: 30, forecast30d: 32, suggestedReorder: 25, leadTimeDays: 4, safetyStock: 10, status: 'Reordenar' },
  { sku: 'LLA-0601', productName: 'Llanta General Tire Grabber AT3', category: 'Llantas', currentStock: 10, avgMonthlyDemand: 8, forecast30d: 10, suggestedReorder: 8, leadTimeDays: 7, safetyStock: 4, status: 'Revisar' },
  { sku: 'BAT-0023', productName: 'Batería LTH L-35-575', category: 'Baterías', currentStock: 11, avgMonthlyDemand: 9, forecast30d: 10, suggestedReorder: 0, leadTimeDays: 3, safetyStock: 3, status: 'OK' },
  { sku: 'AMO-0034', productName: 'Amortiguador Trasero KYB Excel-G', category: 'Amortiguadores', currentStock: 3, avgMonthlyDemand: 5, forecast30d: 6, suggestedReorder: 10, leadTimeDays: 6, safetyStock: 3, status: 'Reordenar' },
];

export const forecastService = {
  async getAll(): Promise<ForecastItem[]> {
    return Promise.resolve(mockForecast);
  },
};
