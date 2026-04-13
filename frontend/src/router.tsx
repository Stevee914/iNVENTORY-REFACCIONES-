import { lazy, Suspense } from 'react';
import { createBrowserRouter, Navigate } from 'react-router-dom';
import { MainLayout } from '@/components/layout/MainLayout';

// All pages are lazy-loaded so each route is a separate JS chunk.
// The initial bundle only ships the shell (MainLayout + router).
const DashboardPage     = lazy(() => import('@/pages/DashboardPage').then(m => ({ default: m.DashboardPage })));
const ProductsPage      = lazy(() => import('@/pages/ProductsPage').then(m => ({ default: m.ProductsPage })));
const ProductFormPage   = lazy(() => import('@/pages/ProductFormPage').then(m => ({ default: m.ProductFormPage })));
const ProductDetailPage = lazy(() => import('@/pages/ProductDetailPage').then(m => ({ default: m.ProductDetailPage })));
const MovementsPage     = lazy(() => import('@/pages/MovementsPage').then(m => ({ default: m.MovementsPage })));
const StockPage         = lazy(() => import('@/pages/StockPage').then(m => ({ default: m.StockPage })));
const KardexPage        = lazy(() => import('@/pages/KardexPage').then(m => ({ default: m.KardexPage })));
const ReportsPage       = lazy(() => import('@/pages/ReportsPage').then(m => ({ default: m.ReportsPage })));
const ForecastPage      = lazy(() => import('@/pages/ForecastPage').then(m => ({ default: m.ForecastPage })));
const ProveedoresPage   = lazy(() => import('@/pages/ProveedoresPage').then(m => ({ default: m.ProveedoresPage })));
const CategoriasPage    = lazy(() => import('@/pages/CategoriasPage').then(m => ({ default: m.CategoriasPage })));
const CatalogoPage      = lazy(() => import('@/pages/CatalogoPage').then(m => ({ default: m.CatalogoPage })));
const FaltantesPage     = lazy(() => import('@/pages/FaltantesPage').then(m => ({ default: m.FaltantesPage })));
const ClientesPage      = lazy(() => import('@/pages/ClientesPage').then(m => ({ default: m.ClientesPage })));
const FacturasPage      = lazy(() => import('@/pages/FacturasPage').then(m => ({ default: m.FacturasPage })));
const ComprasPage          = lazy(() => import('@/pages/ComprasPage').then(m => ({ default: m.ComprasPage })));
const CompraXmlReviewPage  = lazy(() => import('@/pages/CompraXmlReviewPage').then(m => ({ default: m.CompraXmlReviewPage })));
const VehiculosPage     = lazy(() => import('@/pages/VehiculosPage').then(m => ({ default: m.VehiculosPage })));
const MargenesPage      = lazy(() => import('@/pages/MargenesPage').then(m => ({ default: m.MargenesPage })));

// Minimal skeleton shown while a page chunk is downloading.
// Uses the same shell background so the transition feels instant.
function PageSkeleton() {
  return (
    <div className="flex items-center justify-center min-h-[60vh]">
      <div className="w-6 h-6 border-2 border-shell/30 border-t-shell rounded-full animate-spin" />
    </div>
  );
}

function Lazy({ children }: { children: React.ReactNode }) {
  return <Suspense fallback={<PageSkeleton />}>{children}</Suspense>;
}

export const router = createBrowserRouter([
  {
    path: '/',
    element: <MainLayout />,
    children: [
      { index: true, element: <Navigate to="/dashboard" replace /> },
      { path: 'dashboard',          element: <Lazy><DashboardPage /></Lazy> },
      { path: 'productos',          element: <Lazy><ProductsPage /></Lazy> },
      { path: 'productos/nuevo',    element: <Lazy><ProductFormPage /></Lazy> },
      { path: 'productos/:sku',     element: <Lazy><ProductDetailPage /></Lazy> },
      { path: 'productos/:id/editar', element: <Lazy><ProductFormPage /></Lazy> },
      { path: 'movimientos',        element: <Lazy><MovementsPage /></Lazy> },
      { path: 'stock',              element: <Lazy><StockPage /></Lazy> },
      { path: 'kardex',             element: <Lazy><KardexPage /></Lazy> },
      { path: 'proveedores',        element: <Lazy><ProveedoresPage /></Lazy> },
      { path: 'catalogo',            element: <Lazy><CatalogoPage /></Lazy> },
      { path: 'categorias',         element: <Lazy><CategoriasPage /></Lazy> },
      { path: 'faltantes',          element: <Lazy><FaltantesPage /></Lazy> },
      { path: 'clientes',           element: <Lazy><ClientesPage /></Lazy> },
      { path: 'facturas',           element: <Lazy><FacturasPage /></Lazy> },
      { path: 'compras',            element: <Lazy><ComprasPage /></Lazy> },
      { path: 'compras/xml/:compraId', element: <Lazy><CompraXmlReviewPage /></Lazy> },
      { path: 'vehiculos',          element: <Lazy><VehiculosPage /></Lazy> },
      { path: 'reportes',             element: <Lazy><ReportsPage /></Lazy> },
      { path: 'reportes/margenes',   element: <Lazy><MargenesPage /></Lazy> },
      { path: 'forecast',           element: <Lazy><ForecastPage /></Lazy> },
    ],
  },
]);
