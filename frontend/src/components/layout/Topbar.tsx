import { Search, Bell, User, Menu } from 'lucide-react';

interface TopbarProps {
  onMenuClick: () => void;
}

export function Topbar({ onMenuClick }: TopbarProps) {
  return (
    <header className="h-[52px] bg-white border-b border-surface-200 flex items-center gap-3 px-3 sm:px-4 md:px-6 flex-shrink-0">
      {/* Hamburger — mobile only */}
      <button
        onClick={onMenuClick}
        className="md:hidden p-2 rounded-lg text-brand-400 hover:bg-surface-100 hover:text-brand-600 transition-all duration-150 flex-shrink-0"
        aria-label="Abrir menú"
      >
        <Menu className="w-[18px] h-[18px]" />
      </button>

      {/* Search */}
      <div className="relative flex-1 sm:flex-none sm:w-80">
        <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-brand-300" />
        <input
          type="text"
          placeholder="Buscar SKU, producto, categoría..."
          className="w-full pl-10 pr-4 py-2 text-[13px] bg-surface-50 border border-surface-200 rounded-lg
                     placeholder:text-brand-300
                     focus:outline-none focus:ring-2 focus:ring-sap-blue/15 focus:border-sap-blue focus:bg-white
                     hover:border-surface-300
                     transition-all duration-200"
        />
      </div>

      {/* Right side */}
      <div className="flex items-center gap-2 ml-auto">
        <button className="relative p-2 rounded-lg text-brand-400 hover:bg-surface-100 hover:text-brand-600 transition-all duration-150">
          <Bell className="w-[18px] h-[18px]" />
          <span className="absolute top-1.5 right-1.5 w-[7px] h-[7px] bg-status-critical rounded-full ring-2 ring-white" />
        </button>
        <div className="w-px h-7 bg-surface-200 mx-1 hidden sm:block" />
        <div className="flex items-center gap-2.5 pl-1">
          <div className="w-8 h-8 rounded-full bg-shell flex items-center justify-center flex-shrink-0">
            <User className="w-3.5 h-3.5 text-white" />
          </div>
          <div className="hidden sm:block">
            <p className="text-[13px] font-semibold leading-tight text-brand-800">Esteban López</p>
            <p className="text-[11px] text-brand-400 leading-tight">Administrador</p>
          </div>
        </div>
      </div>
    </header>
  );
}
