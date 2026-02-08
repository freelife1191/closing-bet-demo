/**
 * Global Loading State for Next.js 16
 *
 * This component is displayed while pages are being loaded.
 * It automatically wraps Suspense boundaries during navigation.
 *
 * Note: In Next.js 16, loading.tsx is automatically shown for:
 * - Initial page load
 * - Client-side navigation
 * - Server Actions execution
 */

export default function Loading() {
  return (
    <div className="min-h-screen bg-[#0E1117] text-white flex items-center justify-center">
      <div className="text-center">
        {/* Loading Spinner */}
        <div className="relative w-24 h-24 mx-auto mb-6">
          {/* Outer Ring */}
          <div className="absolute inset-0 border-4 border-white/10 rounded-full"></div>

          {/* Animated Ring */}
          <div className="absolute inset-0 border-4 border-transparent border-t-blue-500 rounded-full animate-spin"></div>

          {/* Inner Ring */}
          <div className="absolute inset-4 border-2 border-transparent border-t-purple-500 rounded-full animate-spin" style={{ animationDirection: 'reverse', animationDuration: '1.5s' }}></div>

          {/* Center Icon */}
          <div className="absolute inset-0 flex items-center justify-center">
            <i className="fas fa-chart-line text-2xl text-blue-400 animate-pulse"></i>
          </div>
        </div>

        {/* Loading Text */}
        <h2 className="text-xl font-bold mb-2">로딩 중...</h2>
        <p className="text-gray-400 text-sm">
          데이터를 불러오고 있습니다
        </p>

        {/* Loading Dots */}
        <div className="flex justify-center gap-2 mt-4">
          <div className="w-2 h-2 bg-blue-500 rounded-full animate-bounce" style={{ animationDelay: '0ms' }}></div>
          <div className="w-2 h-2 bg-blue-500 rounded-full animate-bounce" style={{ animationDelay: '150ms' }}></div>
          <div className="w-2 h-2 bg-blue-500 rounded-full animate-bounce" style={{ animationDelay: '300ms' }}></div>
        </div>

        {/* Progress Bar */}
        <div className="w-64 h-1 bg-white/10 rounded-full overflow-hidden mt-6 mx-auto">
          <div className="h-full bg-gradient-to-r from-blue-500 to-purple-500 rounded-full animate-pulse" style={{ width: '60%' }}></div>
        </div>
      </div>
    </div>
  )
}
