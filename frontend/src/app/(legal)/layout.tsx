import Link from 'next/link';

/**
 * 개인정보처리방침과 서비스 약관이 함께 쓰는 문서 틀이다. 두 문서만 이 그룹에 들어가므로
 * 라우트 그룹의 layout 하나로 머리글과 본문 서식을 공유한다.
 */
export default function LegalLayout({ children }: { children: React.ReactNode }) {
  return (
    <div className="min-h-screen bg-[#0E1117] text-gray-300 font-sans">
      <header className="border-b border-white/10">
        <div className="max-w-3xl mx-auto px-6 h-16 flex items-center justify-between">
          <Link href="/" className="flex items-center gap-2 group">
            <span className="w-8 h-8 rounded-lg bg-gradient-to-br from-indigo-500 to-purple-600 flex items-center justify-center">
              <i className="fas fa-chart-line text-white text-sm"></i>
            </span>
            <span className="text-lg font-bold text-white group-hover:text-gray-300 transition-colors">
              Smart Money Bot
            </span>
          </Link>
          <nav className="flex items-center gap-5 text-sm text-gray-400">
            <Link href="/privacy" className="hover:text-white transition-colors">
              개인정보처리방침
            </Link>
            <Link href="/terms" className="hover:text-white transition-colors">
              서비스 약관
            </Link>
          </nav>
        </div>
      </header>

      <main className="max-w-3xl mx-auto px-6 py-12 leading-relaxed [&_h2]:text-lg [&_h2]:font-bold [&_h2]:text-white [&_h2]:mt-10 [&_h2]:mb-3 [&_h3]:font-bold [&_h3]:text-gray-100 [&_h3]:mt-6 [&_h3]:mb-2 [&_p]:my-3 [&_ul]:my-3 [&_ul]:space-y-2 [&_ul]:list-disc [&_ul]:pl-5 [&_li]:marker:text-gray-600 [&_table]:w-full [&_table]:my-4 [&_table]:text-sm [&_th]:text-left [&_th]:font-bold [&_th]:text-gray-200 [&_th]:border-b [&_th]:border-white/20 [&_th]:py-2 [&_th]:pr-4 [&_th]:align-top [&_td]:border-b [&_td]:border-white/5 [&_td]:py-2 [&_td]:pr-4 [&_td]:align-top">
        {children}
      </main>

      <footer className="border-t border-white/10 py-8 text-center text-xs text-gray-600">
        © 2026 KR Market Analysis System
      </footer>
    </div>
  );
}
