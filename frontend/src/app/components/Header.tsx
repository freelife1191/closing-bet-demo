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
      <nav aria-label="현재 위치">
        <ol className="flex items-center gap-2 text-sm text-gray-400">
          <li aria-current={paths.length === 0 ? 'page' : undefined}>
            <Link href="/" aria-label="홈" className="hover:text-white transition-colors">
              <i className="fas fa-home" aria-hidden="true"></i>
            </Link>
          </li>
          {paths.map((path, index) => {
            const isLast = index === paths.length - 1;
            const rawLabel = path.charAt(0).toUpperCase() + path.slice(1).replace(/-/g, ' ');
            const label = labelMap[rawLabel] || rawLabel;

            return (
              <li key={path} aria-current={isLast ? 'page' : undefined} className="flex items-center gap-2">
                <span aria-hidden="true">/</span>
                <span className={isLast ? 'text-white font-medium' : ''}>{label}</span>
              </li>
            );
          })}
        </ol>
      </nav>
    );
  };

  return (
    <header className="h-16 border-b border-white/10 bg-[#000000]/95 backdrop-blur supports-[backdrop-filter]:bg-[#000000]/60 flex items-center justify-between pl-4 md:pl-6 pr-16 fixed top-0 lg:left-64 left-0 right-0 z-40 transition-all duration-300">
      {/* Left: Breadcrumb & Mobile Menu */}
      <div className="flex items-center gap-3">
        {/* Mobile Menu Button */}
        <button
          onClick={() => window.dispatchEvent(new Event('sidebar-toggle'))}
          aria-label="메뉴 열고 닫기"
          className="lg:hidden text-gray-400 hover:text-white p-2 -ml-2 transition-colors"
        >
          <i className="fas fa-bars text-xl"></i>
        </button>

        {/* Breadcrumbs (Mobile: Hidden on very small screens if needed, usually fine) */}
        <div className="hidden sm:block">{getBreadcrumbs()}</div>
        <div className="sm:hidden text-sm font-bold text-white">KR Market</div>
      </div>

      {/* Right: Actions (right padding reserves the chat launcher) */}
      <div className="flex items-center gap-2 md:gap-4">
        {/* Notifications: 종 아이콘이지만 여는 것은 사이드바의 설정 창이다 */}
        <button
          onClick={() => window.dispatchEvent(new Event('open-settings'))}
          aria-label="설정 열기"
          className="w-9 h-9 flex items-center justify-center rounded-lg hover:bg-white/5 text-gray-400 hover:text-white transition-colors relative"
        >
          <i className="far fa-bell text-lg"></i>
          <span className="absolute top-2 right-2 w-2 h-2 bg-rose-500 rounded-full border-2 border-[#000000]"></span>
        </button>
      </div>
    </header>
  );
}
