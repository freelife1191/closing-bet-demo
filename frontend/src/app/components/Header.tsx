'use client';

import Link from 'next/link';
import { usePathname } from 'next/navigation';

export default function Header() {
  const pathname = usePathname();

  // Breadcrumb generator
  const getBreadcrumbs = () => {
    const paths = pathname.split('/').filter(Boolean);
    const labelMap: Record<string, string> = {
      'Dashboard': '대시보드',
      'Kr': '국내 시장',
      'Data status': '데이터 상태',
      'Vcp': 'VCP 시그널',
      'Closing bet': '종가베팅',
      'Chatbot': 'AI 상담'
    };

    return (
      <div className="flex items-center gap-2 text-sm text-gray-400">
        <Link href="/" className="hover:text-white transition-colors">
          <i className="fas fa-home"></i>
        </Link>
        <span>/</span>
        {paths.map((path, index) => {
          const isLast = index === paths.length - 1;
          const rawLabel = path.charAt(0).toUpperCase() + path.slice(1).replace(/-/g, ' ');
          const label = labelMap[rawLabel] || rawLabel;

          return (
            <div key={path} className="flex items-center gap-2">
              <span className={isLast ? 'text-white font-medium' : ''}>{label}</span>
              {!isLast && <span>/</span>}
            </div>
          );
        })}
      </div>
    );
  };

  return (
    <header className="h-16 border-b border-white/10 bg-[#000000]/95 backdrop-blur supports-[backdrop-filter]:bg-[#000000]/60 flex items-center justify-between px-4 md:px-6 fixed top-0 md:left-64 left-0 right-0 z-40 transition-all duration-300">
      {/* Left: Breadcrumb & Mobile Menu */}
      <div className="flex items-center gap-3">
        {/* Mobile Menu Button */}
        <button
          onClick={() => window.dispatchEvent(new Event('sidebar-toggle'))}
          className="md:hidden text-gray-400 hover:text-white p-2 -ml-2 transition-colors"
        >
          <i className="fas fa-bars text-xl"></i>
        </button>

        {/* Breadcrumbs (Mobile: Hidden on very small screens if needed, usually fine) */}
        <div className="hidden sm:block">{getBreadcrumbs()}</div>
        <div className="sm:hidden text-sm font-bold text-white">KR Market</div>
      </div>

      {/* Right: Search & Actions */}
      <div className="flex items-center gap-2 md:gap-4">
        {/* Search Bar */}
        <div className="relative hidden md:block">
          <i className="fas fa-search absolute left-3 top-1/2 -translate-y-1/2 text-gray-500 text-sm"></i>
          <input
            type="text"
            placeholder="Search markets, tickers..."
            className="w-full md:w-80 bg-[#1c1c1e] border border-white/10 rounded-lg py-2 pl-10 pr-12 text-sm text-white placeholder-gray-500 focus:outline-none focus:border-blue-500/50 transition-colors"
          />
          <div className="absolute right-3 top-1/2 -translate-y-1/2 text-xs text-gray-500 border border-white/10 rounded px-1.5 py-0.5">
            ⌘K
          </div>
        </div>
        {/* Mobile Search Icon */}
        <button className="md:hidden w-9 h-9 flex items-center justify-center rounded-lg hover:bg-white/5 text-gray-400">
          <i className="fas fa-search"></i>
        </button>

        {/* Notifications */}
        <button
          onClick={() => window.dispatchEvent(new Event('open-settings'))}
          className="w-9 h-9 flex items-center justify-center rounded-lg hover:bg-white/5 text-gray-400 hover:text-white transition-colors relative"
        >
          <i className="far fa-bell text-lg"></i>
          <span className="absolute top-2 right-2 w-2 h-2 bg-rose-500 rounded-full border-2 border-[#000000]"></span>
        </button>
      </div>
    </header>
  );
}
