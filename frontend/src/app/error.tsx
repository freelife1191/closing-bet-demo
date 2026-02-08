'use client'

/**
 * Global Error Boundary for Next.js 16
 *
 * This component catches errors in the entire app and displays a user-friendly error message.
 * It's a client component because it uses React hooks and state.
 */

import { useEffect } from 'react'
import Link from 'next/link'

export default function Error({
  error,
  reset,
}: {
  error: Error & { digest?: string }
  reset: () => void
}) {
  useEffect(() => {
    // Log the error to an error reporting service
    console.error('Global error caught:', error)
  }, [error])

  return (
    <div className="min-h-screen bg-[#0E1117] text-white flex items-center justify-center p-4">
      <div className="max-w-md w-full text-center">
        {/* Error Icon */}
        <div className="mb-6 flex justify-center">
          <div className="w-20 h-20 rounded-full bg-red-500/10 flex items-center justify-center">
            <i className="fas fa-exclamation-triangle text-4xl text-red-500"></i>
          </div>
        </div>

        {/* Error Message */}
        <h1 className="text-2xl font-bold mb-4">오류가 발생했습니다</h1>
        <p className="text-gray-400 mb-6">
          죄송합니다. 예기치 않은 오류가 발생했습니다.
        </p>

        {/* Error Details (Development Only) */}
        {process.env.NODE_ENV === 'development' && (
          <div className="bg-[#1c1c1e] border border-red-500/20 rounded-lg p-4 mb-6 text-left">
            <p className="text-red-400 text-sm font-mono break-all">
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
            href="/"
            className="px-6 py-3 bg-[#1c1c1e] hover:bg-[#2c2c2e] border border-white/10 text-white font-bold rounded-xl transition-all"
          >
            <i className="fas fa-home mr-2"></i>
            홈으로
          </Link>
        </div>

        {/* Support Link */}
        <div className="mt-8 text-sm text-gray-500">
          문제가 지속되면{' '}
          <a href="mailto:support@example.com" className="text-blue-400 hover:underline">
            지원팀에 문의
          </a>
          하세요.
        </div>
      </div>
    </div>
  )
}
