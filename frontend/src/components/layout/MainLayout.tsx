import { useState } from 'react';
import { Outlet } from 'react-router-dom';
import { Sidebar } from './Sidebar';
import { Topbar } from './Topbar';

export function MainLayout() {
  const [mobileOpen, setMobileOpen] = useState(false);

  return (
    <div className="min-h-screen bg-surface-50">
      {/* Mobile backdrop */}
      {mobileOpen && (
        <div
          className="fixed inset-0 z-30 bg-black/40 md:hidden"
          onClick={() => setMobileOpen(false)}
        />
      )}

      <Sidebar mobileOpen={mobileOpen} onClose={() => setMobileOpen(false)} />

      <div className="flex flex-col min-h-screen ml-0 md:ml-[56px]">
        <Topbar onMenuClick={() => setMobileOpen(true)} />
        <main className="flex-1 px-3 sm:px-4 md:px-6 py-5 overflow-auto">
          <Outlet />
        </main>
      </div>
    </div>
  );
}
