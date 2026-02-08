/**
 * Global Not Found Page (404) for Next.js 16
 *
 * This component is displayed when a user visits a URL that doesn't exist.
 * It's a server component by default (no 'use client' directive needed).
 */

import Link from 'next/link'

export default function NotFound() {
  return (
    <div className="min-h-screen bg-[#0E1117] text-white flex items-center justify-center p-4">
      <div className="max-w-md w-full text-center">
        {/* 404 Icon */}
        <div className="mb-6 flex justify-center">
          <div className="relative">
            <div className="w-32 h-32 rounded-full bg-gray-500/10 flex items-center justify-center">
              <span className="text-6xl font-black text-gray-600">404</span>
            </div>
            <div className="absolute -top-2 -right-2 w-10 h-10 rounded-full bg-blue-500 flex items-center justify-center">
              <i className="fas fa-search text-white"></i>
            </div>
          </div>
        </div>

        {/* Not Found Message */}
        <h1 className="text-3xl font-bold mb-4">페이지를 찾을 수 없습니다</h1>
        <p className="text-gray-400 mb-8">
          요청하신 페이지가 존재하지 않거나 이동되었을 수 있습니다.
        </p>

        {/* Quick Links */}
        <div className="space-y-3 mb-8">
          <Link
            href="/dashboard/kr"
            className="flex items-center justify-center gap-3 px-6 py-3 bg-[#1c1c1e] hover:bg-[#2c2c2e] border border-white/10 rounded-xl transition-all"
          >
            <i className="fas fa-chart-line text-blue-400"></i>
            <span>대시보드</span>
          </Link>
          <Link
            href="/"
            className="flex items-center justify-center gap-3 px-6 py-3 bg-blue-600 hover:bg-blue-500 rounded-xl transition-all"
          >
            <i className="fas fa-home"></i>
            <span>홈으로</span>
          </Link>
        </div>

        {/* Helpful Tips */}
        <div className="text-sm text-gray-500 space-y-2">
          <p>💡 URL이 정확한지 확인해보세요.</p>
          <p>💡 검색 기능을 사용하여 원하는 페이지를 찾을 수 있습니다.</p>
        </div>
      </div>
    </div>
  )
}
