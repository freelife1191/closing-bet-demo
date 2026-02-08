'use client'

/**
 * Dashboard Error Boundary for Next.js 16
 *
 * This component catches errors specifically in the dashboard section
 * and provides a recovery option.
 */

import { useEffect } from 'react'
import Link from 'next/link'

export default function DashboardError({
  error,
  reset,
}: {
  error: Error & { digest?: string }
  reset: () => void
}) {
  useEffect(() => {
    console.error('Dashboard error:', error)
  }, [error])

  return (
    <div className="min-h-screen bg-black text-white flex items-center justify-center p-4">
      <div className="max-w-md w-full text-center">
        {/* Error Icon */}
        <div className="mb-6 flex justify-center">
          <div className="w-20 h-20 rounded-full bg-orange-500/10 flex items-center justify-center">
            <i className="fas fa-exclamation-circle text-4xl text-orange-500"></i>
          </div>
        </div>

        {/* Error Message */}
        <h1 className="text-2xl font-bold mb-4">대시보드 오류</h1>
        <p className="text-gray-400 mb-6">
          대시보드를 불러오는 중 오류가 발생했습니다.
        </p>

        {/* Error Details (Development Only) */}
        {process.env.NODE_ENV === 'development' && (
          <div className="bg-[#1c1c1e] border border-orange-500/20 rounded-lg p-4 mb-6 text-left">
            <p className="text-orange-400 text-sm font-mono break-all">
              {error.message}
            </p>
            {error.digest && (
              <p className="text-gray-500 text-xs mt-2">
                Error ID: {error.digest}
              </p>
            )}
          </div>
        )}

        {/* Action Buttons */}
        <div className="flex flex-col sm:flex-row gap-4 justify-center">
          <button
            onClick={reset}
            className="px-6 py-3 bg-blue-600 hover:bg-blue-500 text-white font-bold rounded-xl transition-all"
          >
            <i className="fas fa-redo mr-2"></i>
            다시 시도
          </button>
          <Link
            href="/dashboard/kr"
            className="px-6 py-3 bg-[#1c1c1e] hover:bg-[#2c2c2e] border border-white/10 text-white font-bold rounded-xl transition-all"
          >
            <i className="fas fa-sync mr-2"></i>
            대시보드 새로고침
          </Link>
        </div>

        {/* Return Home */}
        <div className="mt-6">
          <Link
            href="/"
            className="text-sm text-gray-400 hover:text-white transition-colors"
          >
            <i className="fas fa-arrow-left mr-2"></i>
            홈으로 돌아가기
          </Link>
        </div>
      </div>
    </div>
  )
}
