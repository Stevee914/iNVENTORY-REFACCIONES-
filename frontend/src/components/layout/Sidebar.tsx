import { NavLink } from 'react-router-dom';
import {
  LayoutDashboard, Package, ArrowRightLeft, Warehouse, ScrollText,
  BarChart3, TrendingDown, TrendingUp, Truck, FolderTree, ShoppingCart, Users, Receipt, ShoppingBag, Car, X, LayoutGrid,
} from 'lucide-react';
import { cn } from '@/lib/utils';
import { useState } from 'react';

const navSections = [
  {
    label: 'Principal',
    items: [
      { to: '/dashboard',   label: 'Dashboard',    icon: LayoutDashboard },
      { to: '/productos',   label: 'Productos',    icon: Package },
      { to: '/movimientos', label: 'Movimientos',  icon: ArrowRightLeft },
      { to: '/stock',       label: 'Stock Actual', icon: Warehouse },
    ],
  },
  {
    label: 'Operación',
    items: [
      { to: '/catalogo',    label: 'Catálogo',           icon: LayoutGrid },
      { to: '/kardex',      label: 'Kardex',            icon: ScrollText },
      { to: '/faltantes',   label: 'Faltantes',         icon: ShoppingCart },
      { to: '/proveedores', label: 'Proveedores',        icon: Truck },
      { to: '/categorias',  label: 'Categorías',         icon: FolderTree },
      { to: '/clientes',    label: 'Clientes',           icon: Users },
      { to: '/facturas',    label: 'Ventas y Cobranza',  icon: Receipt },
      { to: '/compras',     label: 'Compras',            icon: ShoppingBag },
      { to: '/vehiculos',   label: 'Por Vehículo',       icon: Car },
    ],
  },
  {
    label: 'Análisis',
    items: [
      { to: '/reportes', label: 'Reportes',  icon: BarChart3   },
      { to: '/forecast', label: 'Forecast',  icon: TrendingUp  },
      { to: '/reportes/margenes', label: 'Márgenes', icon: TrendingDown },
    ],
  },
];

interface SidebarProps {
  mobileOpen: boolean;
  onClose: () => void;
}

export function Sidebar({ mobileOpen, onClose }: SidebarProps) {
  const [hovered, setHovered] = useState(false);

  // On desktop: expand on hover. On mobile: controlled by mobileOpen prop.
  const expanded = hovered || mobileOpen;

  return (
    <aside
      onMouseEnter={() => setHovered(true)}
      onMouseLeave={() => setHovered(false)}
      className={cn(
        'fixed left-0 top-0 z-40 h-screen flex flex-col overflow-hidden',
        'bg-shell text-white',
        'transition-all duration-[400ms] ease-[cubic-bezier(0.25,0.1,0.25,1)]',
        // Desktop: always visible, collapses to icon strip
        'md:translate-x-0',
        // Mobile: hidden by default, slides in when open
        mobileOpen ? 'translate-x-0' : '-translate-x-full md:translate-x-0',
        expanded ? 'w-[230px] shadow-sidebar' : 'w-[230px] md:w-[56px]'
      )}
    >
      {/* Brand + mobile close button */}
      <div className="flex items-center gap-3 px-[14px] h-[56px] border-b border-white/[0.08] flex-shrink-0">
        <div className="w-7 h-7 rounded-lg bg-sap-blue flex items-center justify-center font-semibold text-[11px] text-white flex-shrink-0">
          RJ
        </div>
        <div className={cn(
          'overflow-hidden transition-all duration-300 flex-1',
          expanded ? 'opacity-100 translate-x-0' : 'opacity-0 -translate-x-1'
        )}>
          <p className="text-[13px] font-semibold leading-tight truncate whitespace-nowrap">Refacciones Jaime</p>
          <p className="text-[10px] text-white/40 leading-tight whitespace-nowrap">Inventario v1</p>
        </div>
        {/* Close button — mobile only */}
        <button
          onClick={onClose}
          className="md:hidden flex-shrink-0 p-1 rounded-lg text-white/50 hover:text-white hover:bg-white/10 transition-colors"
          aria-label="Cerrar menú"
        >
          <X className="w-4 h-4" />
        </button>
      </div>

      {/* Nav */}
      <nav className="flex-1 py-3 overflow-y-auto overflow-x-hidden">
        {navSections.map((section) => (
          <div key={section.label}>
            <div className={cn(
              'px-[14px] mb-1 mt-3 first:mt-0 transition-all duration-300',
              expanded ? 'opacity-100 h-auto' : 'opacity-0 h-0 overflow-hidden'
            )}>
              <p className="text-[10px] font-semibold text-white/30 uppercase tracking-[0.08em] whitespace-nowrap">
                {section.label}
              </p>
            </div>

            <div className="px-2 space-y-0.5">
              {section.items.map((item) => (
                <NavLink
                  key={item.to}
                  to={item.to}
                  onClick={onClose}
                  className={({ isActive }) =>
                    cn(
                      'group flex items-center gap-3 px-[10px] py-2 rounded-lg text-[13px] font-medium',
                      'transition-all duration-200',
                      isActive
                        ? 'bg-sap-blue/20 text-white'
                        : 'text-white/45 hover:text-white/70 hover:bg-white/[0.06]'
                    )
                  }
                >
                  {({ isActive }) => (
                    <>
                      <item.icon className={cn(
                        'w-[18px] h-[18px] flex-shrink-0 transition-colors duration-200',
                        isActive ? 'text-[#6cb4ff]' : 'text-white/35 group-hover:text-white/55'
                      )} />
                      <span className={cn(
                        'truncate whitespace-nowrap transition-all duration-300',
                        expanded ? 'opacity-100 translate-x-0' : 'opacity-0 -translate-x-1'
                      )}>
                        {item.label}
                      </span>
                    </>
                  )}
                </NavLink>
              ))}
            </div>
          </div>
        ))}
      </nav>

      {/* User at bottom */}
      <div className="px-[14px] py-3 border-t border-white/[0.08] flex items-center gap-3">
        <div className="w-7 h-7 rounded-full bg-white/10 flex items-center justify-center flex-shrink-0">
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="rgba(255,255,255,0.45)" strokeWidth="2">
            <path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2" />
            <circle cx="12" cy="7" r="4" />
          </svg>
        </div>
        <div className={cn(
          'overflow-hidden transition-all duration-300 whitespace-nowrap',
          expanded ? 'opacity-100 translate-x-0' : 'opacity-0 -translate-x-1'
        )}>
          <p className="text-[12px] font-medium text-white/80 leading-tight">Esteban López</p>
          <p className="text-[10px] text-white/35 leading-tight">Administrador</p>
        </div>
      </div>
    </aside>
  );
}
