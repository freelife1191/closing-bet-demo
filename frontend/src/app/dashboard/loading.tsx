/**
 * Dashboard Loading State for Next.js 16
 *
 * This component is displayed while dashboard pages are being loaded.
 * It's specifically styled to match the dashboard UI.
 */

export default function DashboardLoading() {
  return (
    <div className="min-h-screen bg-black text-white">
      {/* Sidebar Skeleton */}
      <div className="fixed left-0 top-0 bottom-0 w-64 bg-[#0E1117] border-r border-white/5 p-4 hidden lg:block">
        <div className="h-12 bg-white/5 rounded-lg mb-6 animate-pulse"></div>
        <div className="space-y-2">
          {[1, 2, 3, 4, 5].map((i) => (
            <div
              key={i}
              className="h-10 bg-white/5 rounded-lg animate-pulse"
              style={{ animationDelay: `${i * 100}ms` }}
            ></div>
          ))}
        </div>
      </div>

      {/* Main Content Skeleton */}
      <div className="lg:pl-64 pt-16 min-h-screen">
        {/* Header Skeleton */}
        <div className="fixed top-0 left-0 right-0 lg:left-64 h-16 bg-[#0E1117]/80 backdrop-blur-md border-b border-white/5 p-4 flex items-center gap-4">
          <div className="h-8 w-48 bg-white/5 rounded-lg animate-pulse"></div>
          <div className="flex-1"></div>
          <div className="h-10 w-10 bg-white/5 rounded-full animate-pulse"></div>
        </div>

        {/* Page Content Skeleton */}
        <div className="p-4 md:p-8 max-w-[1600px] mx-auto">
          {/* Title Skeleton */}
          <div className="mb-8">
            <div className="h-10 w-64 bg-white/5 rounded-lg mb-2 animate-pulse"></div>
            <div className="h-5 w-96 bg-white/5 rounded-lg animate-pulse"></div>
          </div>

          {/* Cards Skeleton */}
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6 mb-8">
            {[1, 2, 3, 4].map((i) => (
              <div
                key={i}
                className="bg-[#1c1c1e] border border-white/5 rounded-xl p-6"
                style={{ animationDelay: `${i * 150}ms` }}
              >
                <div className="h-4 w-24 bg-white/5 rounded mb-4 animate-pulse"></div>
                <div className="h-8 w-16 bg-white/5 rounded animate-pulse"></div>
              </div>
            ))}
          </div>

          {/* Table Skeleton */}
          <div className="bg-[#1c1c1e] border border-white/5 rounded-xl overflow-hidden">
            <div className="p-6 border-b border-white/5">
              <div className="h-6 w-48 bg-white/5 rounded animate-pulse"></div>
            </div>
            <div className="p-6">
              {[1, 2, 3, 4, 5].map((i) => (
                <div
                  key={i}
                  className="flex items-center gap-4 py-3 border-b border-white/5 last:border-0"
                  style={{ animationDelay: `${i * 100}ms` }}
                >
                  <div className="h-12 w-12 bg-white/5 rounded-lg animate-pulse"></div>
                  <div className="flex-1">
                    <div className="h-4 w-32 bg-white/5 rounded mb-2 animate-pulse"></div>
                    <div className="h-3 w-24 bg-white/5 rounded animate-pulse"></div>
                  </div>
                  <div className="h-8 w-20 bg-white/5 rounded animate-pulse"></div>
                </div>
              ))}
            </div>
          </div>
        </div>
      </div>

      {/* Loading Overlay */}
      <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50">
        <div className="bg-[#1c1c1e] border border-white/10 rounded-2xl p-8 text-center">
          <div className="relative w-16 h-16 mx-auto mb-4">
            <div className="absolute inset-0 border-4 border-white/10 rounded-full"></div>
            <div className="absolute inset-0 border-4 border-transparent border-t-blue-500 rounded-full animate-spin"></div>
            <div className="absolute inset-0 flex items-center justify-center">
              <i className="fas fa-chart-line text-xl text-blue-400"></i>
            </div>
          </div>
          <p className="text-white font-medium">대시보드 로딩 중...</p>
        </div>
      </div>
    </div>
  )
}
