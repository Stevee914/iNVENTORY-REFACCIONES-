import type { Product, StockItem, Movement, ForecastItem, DashboardStats, TrendPoint } from '@/types';

// ─── Productos mock ────────────────────────────────────────────

export const mockProducts: Product[] = [
  { id: '1', sku: 'AMO-0012', name: 'Amortiguador Delantero Monroe Matic Plus', description: 'Amortiguador delantero gas para pickup y SUV', category: 'Amortiguadores', unit: 'PZA', stockMin: 8, brand: 'Monroe', supplier: 'Tenneco México', active: true, createdAt: '2024-01-15', updatedAt: '2025-03-01' },
  { id: '2', sku: 'AMO-0034', name: 'Amortiguador Trasero KYB Excel-G', description: 'Amortiguador trasero bitubo gas', category: 'Amortiguadores', unit: 'PZA', stockMin: 6, brand: 'KYB', supplier: 'Distribuidora KYB', active: true, createdAt: '2024-02-10', updatedAt: '2025-02-20' },
  { id: '3', sku: 'BAL-0087', name: 'Balero de Rueda Delantera Koyo 6205', description: 'Balero sellado para rueda delantera', category: 'Baleros', unit: 'PZA', stockMin: 15, brand: 'Koyo', supplier: 'JTEKT México', active: true, createdAt: '2024-01-20', updatedAt: '2025-03-05' },
  { id: '4', sku: 'BAL-0092', name: 'Balero de Rueda Trasera NTN', description: 'Balero cónico para rueda trasera camioneta', category: 'Baleros', unit: 'PZA', stockMin: 10, brand: 'NTN', supplier: 'NTN Bearing', active: true, createdAt: '2024-03-01', updatedAt: '2025-02-28' },
  { id: '5', sku: 'BAN-0145', name: 'Banda de Alternador Gates K060923', description: 'Banda serpentina micro-v 6 costillas', category: 'Bandas', unit: 'PZA', stockMin: 12, brand: 'Gates', supplier: 'Gates Corp', active: true, createdAt: '2024-01-10', updatedAt: '2025-03-10' },
  { id: '6', sku: 'BAN-0156', name: 'Banda de Tiempo Gates PowerGrip', description: 'Kit de distribución con tensor', category: 'Bandas', unit: 'JGO', stockMin: 5, brand: 'Gates', supplier: 'Gates Corp', active: true, createdAt: '2024-04-15', updatedAt: '2025-01-20' },
  { id: '7', sku: 'BAT-0023', name: 'Batería LTH L-35-575', description: 'Batería 12V 575 CCA para auto compacto', category: 'Baterías', unit: 'PZA', stockMin: 10, brand: 'LTH', supplier: 'Clarios México', active: true, createdAt: '2024-02-01', updatedAt: '2025-03-08' },
  { id: '8', sku: 'BAT-0041', name: 'Batería LTH L-65-850', description: 'Batería 12V 850 CCA para camioneta/SUV', category: 'Baterías', unit: 'PZA', stockMin: 8, brand: 'LTH', supplier: 'Clarios México', active: true, createdAt: '2024-02-01', updatedAt: '2025-03-01' },
  { id: '9', sku: 'BIR-0201', name: 'Birlo de Rueda M12x1.5 Cromado', description: 'Birlo estándar cromado para rin de acero', category: 'Birlos y Tornillería', unit: 'PZA', stockMin: 100, brand: 'Dorman', supplier: 'AutoZone Industrial', active: true, createdAt: '2024-01-05', updatedAt: '2025-02-15' },
  { id: '10', sku: 'BGA-0067', name: 'Bomba de Gasolina Airtex E2068', description: 'Bomba eléctrica sumergible para tanque', category: 'Bombas de Gasolina', unit: 'PZA', stockMin: 4, brand: 'Airtex', supplier: 'Airtex Products', active: true, createdAt: '2024-05-01', updatedAt: '2025-02-01' },
  { id: '11', sku: 'BAG-0078', name: 'Bomba de Agua GMB GWT-116A', description: 'Bomba de agua para motor 4 cil Toyota', category: 'Bombas de Agua', unit: 'PZA', stockMin: 6, brand: 'GMB', supplier: 'GMB México', active: true, createdAt: '2024-03-10', updatedAt: '2025-01-30' },
  { id: '12', sku: 'BUJ-0310', name: 'Bujía NGK BKR6E-11', description: 'Bujía de encendido convencional níquel', category: 'Bujías', unit: 'PZA', stockMin: 50, brand: 'NGK', supplier: 'NGK Spark Plugs', active: true, createdAt: '2024-01-01', updatedAt: '2025-03-10' },
  { id: '13', sku: 'BUJ-0325', name: 'Bujía Denso Iridium IK20TT', description: 'Bujía iridium TT twin-tip', category: 'Bujías', unit: 'PZA', stockMin: 30, brand: 'Denso', supplier: 'Denso México', active: true, createdAt: '2024-02-15', updatedAt: '2025-03-05' },
  { id: '14', sku: 'CLU-0089', name: 'Kit de Clutch LuK RepSet 623 3098 09', description: 'Kit completo clutch con disco, plato y collarín', category: 'Clutch y Collarines', unit: 'JGO', stockMin: 3, brand: 'LuK', supplier: 'Schaeffler México', active: true, createdAt: '2024-06-01', updatedAt: '2025-02-20' },
  { id: '15', sku: 'FRE-0412', name: 'Balatas Delanteras Wagner ThermoQuiet QC1001', description: 'Balatas cerámicas delanteras', category: 'Frenos', unit: 'JGO', stockMin: 10, brand: 'Wagner', supplier: 'Federal-Mogul', active: true, createdAt: '2024-01-20', updatedAt: '2025-03-10' },
  { id: '16', sku: 'FRE-0428', name: 'Disco de Freno Brembo 09.A820.11', description: 'Disco ventilado delantero', category: 'Frenos', unit: 'PZA', stockMin: 6, brand: 'Brembo', supplier: 'Brembo México', active: true, createdAt: '2024-03-05', updatedAt: '2025-02-28' },
  { id: '17', sku: 'FIL-0510', name: 'Filtro de Aceite Wix WL7154', description: 'Filtro aceite rosca estándar', category: 'Filtros', unit: 'PZA', stockMin: 25, brand: 'Wix', supplier: 'Mann+Hummel', active: true, createdAt: '2024-01-01', updatedAt: '2025-03-12' },
  { id: '18', sku: 'FIL-0525', name: 'Filtro de Aire Mann C 27 114', description: 'Filtro aire rectangular motor 4 cil', category: 'Filtros', unit: 'PZA', stockMin: 20, brand: 'Mann', supplier: 'Mann+Hummel', active: true, createdAt: '2024-01-01', updatedAt: '2025-03-11' },
  { id: '19', sku: 'LLA-0601', name: 'Llanta General Tire Grabber AT3 265/70R17', description: 'Llanta todo terreno para camioneta', category: 'Llantas', unit: 'PZA', stockMin: 8, brand: 'General Tire', supplier: 'Continental México', active: true, createdAt: '2024-04-01', updatedAt: '2025-03-05' },
  { id: '20', sku: 'LLA-0618', name: 'Llanta Firestone Destination LE3 235/65R17', description: 'Llanta carretera para SUV', category: 'Llantas', unit: 'PZA', stockMin: 8, brand: 'Firestone', supplier: 'Bridgestone México', active: true, createdAt: '2024-04-01', updatedAt: '2025-02-28' },
  { id: '21', sku: 'LLA-0640', name: 'Llanta Hankook Ventus V2 205/55R16', description: 'Llanta deportiva para sedán', category: 'Llantas', unit: 'PZA', stockMin: 6, brand: 'Hankook', supplier: 'Hankook Tire México', active: true, createdAt: '2024-05-10', updatedAt: '2025-03-01' },
  { id: '22', sku: 'MAZ-0180', name: 'Maza Delantera Timken HA590242', description: 'Maza con rodamiento integrado', category: 'Mazas y Crucetas', unit: 'PZA', stockMin: 4, brand: 'Timken', supplier: 'Timken México', active: true, createdAt: '2024-06-15', updatedAt: '2025-02-15' },
  { id: '23', sku: 'RET-0250', name: 'Retén de Cigüeñal National 710544', description: 'Retén trasero de cigüeñal', category: 'Retenes', unit: 'PZA', stockMin: 8, brand: 'National', supplier: 'SKF México', active: true, createdAt: '2024-03-20', updatedAt: '2025-01-30' },
  { id: '24', sku: 'JMO-0115', name: 'Junta de Cabeza Felpro 26223PT', description: 'Junta cabeza MLS multicapa', category: 'Juntas de Motor', unit: 'PZA', stockMin: 3, brand: 'Felpro', supplier: 'Federal-Mogul', active: true, createdAt: '2024-07-01', updatedAt: '2025-02-01' },
  { id: '25', sku: 'CRE-0045', name: 'Cremallera Dirección Hidráulica Cardone 22-1010', description: 'Cremallera remanufacturada dirección hidráulica', category: 'Cremalleras y Controles', unit: 'PZA', stockMin: 2, brand: 'Cardone', supplier: 'Cardone Industries', active: true, createdAt: '2024-08-01', updatedAt: '2025-02-10' },
  { id: '26', sku: 'DIF-0030', name: 'Kit Reparación Diferencial Yukon YK GM14T-B', description: 'Kit maestro instalación diferencial', category: 'Diferencial', unit: 'JGO', stockMin: 2, brand: 'Yukon', supplier: 'Yukon Gear', active: true, createdAt: '2024-09-01', updatedAt: '2025-01-15' },
  { id: '27', sku: 'MHI-0088', name: 'Manguera Hidráulica Alta Presión 3/8" x 1m', description: 'Manguera SAE 100R2AT con conexiones', category: 'Mangueras Hidráulicas', unit: 'PZA', stockMin: 10, brand: 'Parker', supplier: 'Parker Hannifin', active: true, createdAt: '2024-02-20', updatedAt: '2025-03-01' },
  { id: '28', sku: 'AMO-0056', name: 'Amortiguador Cabina Tractocamión', description: 'Amortiguador cabina Kenworth/Peterbilt', category: 'Amortiguadores', unit: 'PZA', stockMin: 4, brand: 'Sachs', supplier: 'ZF México', active: true, createdAt: '2024-10-01', updatedAt: '2025-02-25' },
  { id: '29', sku: 'FRE-0450', name: 'Zapatas de Freno Aire Meritor Q Plus', description: 'Zapatas freno aire 16.5" eje tractocamión', category: 'Frenos', unit: 'JGO', stockMin: 4, brand: 'Meritor', supplier: 'Meritor México', active: true, createdAt: '2024-05-20', updatedAt: '2025-03-08' },
  { id: '30', sku: 'FIL-0550', name: 'Filtro Diésel Racor R90P', description: 'Filtro separador agua/diésel', category: 'Filtros', unit: 'PZA', stockMin: 15, brand: 'Racor', supplier: 'Parker Hannifin', active: true, createdAt: '2024-01-15', updatedAt: '2025-03-10' },
];

// ─── Stock actual (derivado) ───────────────────────────────────

const stockValues: Record<string, number> = {
  '1': 12, '2': 3, '3': 18, '4': 7, '5': 14, '6': 2, '7': 11, '8': 5,
  '9': 145, '10': 6, '11': 4, '12': 62, '13': 15, '14': 1, '15': 8,
  '16': 3, '17': 28, '18': 12, '19': 10, '20': 3, '21': 9, '22': 2,
  '23': 5, '24': 1, '25': 3, '26': 1, '27': 7, '28': 6, '29': 2, '30': 18,
};

function getStockStatus(current: number, min: number): 'ok' | 'warn' | 'critical' {
  if (current <= 0) return 'critical';
  if (current <= min * 0.5) return 'critical';
  if (current <= min) return 'warn';
  return 'ok';
}

export const mockStock: StockItem[] = mockProducts.map((p) => ({
  productId: p.id,
  sku: p.sku,
  name: p.name,
  category: p.category,
  currentStock: stockValues[p.id] ?? 0,
  stockMin: p.stockMin,
  unit: p.unit,
  status: getStockStatus(stockValues[p.id] ?? 0, p.stockMin),
}));

// ─── Movimientos mock ──────────────────────────────────────────

export const mockMovements: Movement[] = [
  { id: 'M001', productId: '1', sku: 'AMO-0012', productName: 'Amortiguador Delantero Monroe Matic Plus', type: 'IN', quantity: 10, reference: 'FAC-2025-0312', user: 'Carlos López', createdAt: '2025-03-12T08:30:00', balanceAfter: 12 },
  { id: 'M002', productId: '15', sku: 'FRE-0412', productName: 'Balatas Delanteras Wagner ThermoQuiet QC1001', type: 'OUT', quantity: 2, reference: 'VTA-4521', user: 'Miguel Reyes', createdAt: '2025-03-12T09:15:00', balanceAfter: 8 },
  { id: 'M003', productId: '12', sku: 'BUJ-0310', productName: 'Bujía NGK BKR6E-11', type: 'OUT', quantity: 8, reference: 'VTA-4522', user: 'Miguel Reyes', createdAt: '2025-03-12T09:45:00', balanceAfter: 62 },
  { id: 'M004', productId: '7', sku: 'BAT-0023', productName: 'Batería LTH L-35-575', type: 'IN', quantity: 6, reference: 'FAC-2025-0311', user: 'Carlos López', createdAt: '2025-03-11T16:20:00', balanceAfter: 11 },
  { id: 'M005', productId: '19', sku: 'LLA-0601', productName: 'Llanta General Tire Grabber AT3 265/70R17', type: 'IN', quantity: 8, reference: 'FAC-2025-0310', user: 'Carlos López', createdAt: '2025-03-11T10:00:00', balanceAfter: 10 },
  { id: 'M006', productId: '20', sku: 'LLA-0618', productName: 'Llanta Firestone Destination LE3 235/65R17', type: 'OUT', quantity: 4, reference: 'VTA-4519', user: 'Pedro Garza', createdAt: '2025-03-11T11:30:00', balanceAfter: 3 },
  { id: 'M007', productId: '9', sku: 'BIR-0201', productName: 'Birlo de Rueda M12x1.5 Cromado', type: 'OUT', quantity: 20, reference: 'VTA-4518', user: 'Miguel Reyes', createdAt: '2025-03-11T14:00:00', balanceAfter: 145 },
  { id: 'M008', productId: '14', sku: 'CLU-0089', productName: 'Kit de Clutch LuK RepSet 623 3098 09', type: 'ADJUST', quantity: -1, reference: 'AJ-INV-003 Faltante físico', user: 'Jaime Hernández', createdAt: '2025-03-10T17:00:00', balanceAfter: 1 },
  { id: 'M009', productId: '17', sku: 'FIL-0510', productName: 'Filtro de Aceite Wix WL7154', type: 'IN', quantity: 24, reference: 'FAC-2025-0308', user: 'Carlos López', createdAt: '2025-03-10T09:00:00', balanceAfter: 28 },
  { id: 'M010', productId: '30', sku: 'FIL-0550', productName: 'Filtro Diésel Racor R90P', type: 'IN', quantity: 12, reference: 'FAC-2025-0307', user: 'Carlos López', createdAt: '2025-03-10T09:30:00', balanceAfter: 18 },
  { id: 'M011', productId: '5', sku: 'BAN-0145', productName: 'Banda de Alternador Gates K060923', type: 'OUT', quantity: 3, reference: 'VTA-4515', user: 'Pedro Garza', createdAt: '2025-03-09T15:00:00', balanceAfter: 14 },
  { id: 'M012', productId: '3', sku: 'BAL-0087', productName: 'Balero de Rueda Delantera Koyo 6205', type: 'OUT', quantity: 2, reference: 'VTA-4514', user: 'Miguel Reyes', createdAt: '2025-03-09T13:00:00', balanceAfter: 18 },
  { id: 'M013', productId: '22', sku: 'MAZ-0180', productName: 'Maza Delantera Timken HA590242', type: 'OUT', quantity: 1, reference: 'VTA-4513', user: 'Pedro Garza', createdAt: '2025-03-09T10:30:00', balanceAfter: 2 },
  { id: 'M014', productId: '29', sku: 'FRE-0450', productName: 'Zapatas de Freno Aire Meritor Q Plus', type: 'OUT', quantity: 2, reference: 'VTA-4510', user: 'Miguel Reyes', createdAt: '2025-03-08T14:20:00', balanceAfter: 2 },
  { id: 'M015', productId: '6', sku: 'BAN-0156', productName: 'Banda de Tiempo Gates PowerGrip', type: 'OUT', quantity: 1, reference: 'VTA-4509', user: 'Pedro Garza', createdAt: '2025-03-08T11:00:00', balanceAfter: 2 },
  { id: 'M016', productId: '2', sku: 'AMO-0034', productName: 'Amortiguador Trasero KYB Excel-G', type: 'OUT', quantity: 2, reference: 'VTA-4507', user: 'Miguel Reyes', createdAt: '2025-03-07T16:45:00', balanceAfter: 3 },
  { id: 'M017', productId: '8', sku: 'BAT-0041', productName: 'Batería LTH L-65-850', type: 'OUT', quantity: 1, reference: 'VTA-4505', user: 'Pedro Garza', createdAt: '2025-03-07T10:00:00', balanceAfter: 5 },
  { id: 'M018', productId: '16', sku: 'FRE-0428', productName: 'Disco de Freno Brembo 09.A820.11', type: 'IN', quantity: 4, reference: 'FAC-2025-0305', user: 'Carlos López', createdAt: '2025-03-06T08:45:00', balanceAfter: 3 },
  { id: 'M019', productId: '24', sku: 'JMO-0115', productName: 'Junta de Cabeza Felpro 26223PT', type: 'OUT', quantity: 1, reference: 'VTA-4502', user: 'Miguel Reyes', createdAt: '2025-03-05T14:00:00', balanceAfter: 1 },
  { id: 'M020', productId: '21', sku: 'LLA-0640', productName: 'Llanta Hankook Ventus V2 205/55R16', type: 'IN', quantity: 12, reference: 'FAC-2025-0303', user: 'Carlos López', createdAt: '2025-03-04T09:00:00', balanceAfter: 9 },
];

// ─── Dashboard stats ───────────────────────────────────────────

export const mockDashboardStats: DashboardStats = {
  totalSKUs: 30,
  totalStock: Object.values(stockValues).reduce((a, b) => a + b, 0),
  lowStockCount: mockStock.filter((s) => s.status === 'warn' || s.status === 'critical').length,
  noMovementCount: 5,
  movementsToday: 3,
};

// ─── Trend data (últimos 14 días) ──────────────────────────────

export const mockTrend: TrendPoint[] = [
  { date: '27 Feb', entries: 12, exits: 8 },
  { date: '28 Feb', entries: 5, exits: 14 },
  { date: '01 Mar', entries: 18, exits: 10 },
  { date: '02 Mar', entries: 0, exits: 6 },
  { date: '03 Mar', entries: 8, exits: 9 },
  { date: '04 Mar', entries: 15, exits: 7 },
  { date: '05 Mar', entries: 3, exits: 11 },
  { date: '06 Mar', entries: 6, exits: 5 },
  { date: '07 Mar', entries: 10, exits: 12 },
  { date: '08 Mar', entries: 4, exits: 8 },
  { date: '09 Mar', entries: 7, exits: 9 },
  { date: '10 Mar', entries: 22, exits: 6 },
  { date: '11 Mar', entries: 14, exits: 15 },
  { date: '12 Mar', entries: 10, exits: 10 },
];

// ─── Forecast mock ─────────────────────────────────────────────

export const mockForecast: ForecastItem[] = [
  { sku: 'FRE-0412', productName: 'Balatas Wagner ThermoQuiet QC1001', category: 'Frenos', currentStock: 8, avgMonthlyDemand: 14, forecast30d: 16, suggestedReorder: 20, leadTimeDays: 5, safetyStock: 5, status: 'Reordenar' },
  { sku: 'BUJ-0310', productName: 'Bujía NGK BKR6E-11', category: 'Bujías', currentStock: 62, avgMonthlyDemand: 45, forecast30d: 50, suggestedReorder: 0, leadTimeDays: 3, safetyStock: 15, status: 'OK' },
  { sku: 'FIL-0510', productName: 'Filtro Aceite Wix WL7154', category: 'Filtros', currentStock: 28, avgMonthlyDemand: 30, forecast30d: 32, suggestedReorder: 25, leadTimeDays: 4, safetyStock: 10, status: 'Reordenar' },
  { sku: 'LLA-0601', productName: 'Llanta General Tire Grabber AT3', category: 'Llantas', currentStock: 10, avgMonthlyDemand: 8, forecast30d: 10, suggestedReorder: 8, leadTimeDays: 7, safetyStock: 4, status: 'Revisar' },
  { sku: 'BAT-0023', productName: 'Batería LTH L-35-575', category: 'Baterías', currentStock: 11, avgMonthlyDemand: 9, forecast30d: 10, suggestedReorder: 0, leadTimeDays: 3, safetyStock: 3, status: 'OK' },
  { sku: 'AMO-0034', productName: 'Amortiguador Trasero KYB Excel-G', category: 'Amortiguadores', currentStock: 3, avgMonthlyDemand: 5, forecast30d: 6, suggestedReorder: 10, leadTimeDays: 6, safetyStock: 3, status: 'Reordenar' },
  { sku: 'CLU-0089', productName: 'Kit Clutch LuK RepSet', category: 'Clutch y Collarines', currentStock: 1, avgMonthlyDemand: 3, forecast30d: 3, suggestedReorder: 5, leadTimeDays: 8, safetyStock: 2, status: 'Reordenar' },
  { sku: 'LLA-0618', productName: 'Llanta Firestone Destination LE3', category: 'Llantas', currentStock: 3, avgMonthlyDemand: 7, forecast30d: 8, suggestedReorder: 12, leadTimeDays: 7, safetyStock: 4, status: 'Reordenar' },
  { sku: 'BAN-0156', productName: 'Banda de Tiempo Gates PowerGrip', category: 'Bandas', currentStock: 2, avgMonthlyDemand: 4, forecast30d: 4, suggestedReorder: 6, leadTimeDays: 5, safetyStock: 2, status: 'Reordenar' },
  { sku: 'FRE-0450', productName: 'Zapatas Freno Aire Meritor Q Plus', category: 'Frenos', currentStock: 2, avgMonthlyDemand: 3, forecast30d: 3, suggestedReorder: 5, leadTimeDays: 10, safetyStock: 2, status: 'Reordenar' },
];
