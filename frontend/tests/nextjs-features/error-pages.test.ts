/**
 * Next.js 16 Error Pages 테스트
 *
 * error.tsx, not-found.tsx, loading.tsx 파일들의
 * 내용과 구조를 검증합니다. React 19 호환성을 위해
 * 파일 내용 검증 방식을 사용합니다.
 */

import { describe, it, expect } from 'vitest'
import { readFileSync, existsSync } from 'fs'
import { join } from 'path'

const ROOT_DIR = process.cwd()

describe('Global Error Boundary (error.tsx)', () => {
  it('should exist and have correct structure', () => {
    const errorPath = join(ROOT_DIR, 'src/app/error.tsx')
    expect(existsSync(errorPath)).toBe(true)
  })

  it('should have use client directive', () => {
    const errorContent = readFileSync(join(ROOT_DIR, 'src/app/error.tsx'), 'utf-8')
    expect(errorContent).toContain("'use client'")
  })

  it('should have Korean error messages', () => {
    const errorContent = readFileSync(join(ROOT_DIR, 'src/app/error.tsx'), 'utf-8')
    expect(errorContent).toContain('오류가 발생했습니다')
    expect(errorContent).toContain('다시 시도')
    expect(errorContent).toContain('홈으로')
  })

  it('should have error parameter types', () => {
    const errorContent = readFileSync(join(ROOT_DIR, 'src/app/error.tsx'), 'utf-8')
    expect(errorContent).toContain('error: Error')
    expect(errorContent).toContain('reset: () => void')
    expect(errorContent).toContain('digest?: string')
  })

  it('should have useEffect for error logging', () => {
    const errorContent = readFileSync(join(ROOT_DIR, 'src/app/error.tsx'), 'utf-8')
    expect(errorContent).toContain('useEffect')
    expect(errorContent).toContain('console.error')
  })

  it('should have development mode error details', () => {
    const errorContent = readFileSync(join(ROOT_DIR, 'src/app/error.tsx'), 'utf-8')
    expect(errorContent).toContain('NODE_ENV')
    expect(errorContent).toContain('development')
  })

  it('should have reset button and home link', () => {
    const errorContent = readFileSync(join(ROOT_DIR, 'src/app/error.tsx'), 'utf-8')
    expect(errorContent).toContain('onClick={reset}')
    expect(errorContent).toContain('href="/"')
  })
})

describe('Not Found Page (not-found.tsx)', () => {
  it('should exist and have correct structure', () => {
    const notFoundPath = join(ROOT_DIR, 'src/app/not-found.tsx')
    expect(existsSync(notFoundPath)).toBe(true)
  })

  it('should have Korean 404 messages', () => {
    const notFoundContent = readFileSync(join(ROOT_DIR, 'src/app/not-found.tsx'), 'utf-8')
    expect(notFoundContent).toContain('페이지를 찾을 수 없습니다')
    expect(notFoundContent).toContain('404')
  })

  it('should have navigation links', () => {
    const notFoundContent = readFileSync(join(ROOT_DIR, 'src/app/not-found.tsx'), 'utf-8')
    expect(notFoundContent).toContain('/dashboard/kr')
    expect(notFoundContent).toContain('href="/"')
  })

  it('should have helpful tips', () => {
    const notFoundContent = readFileSync(join(ROOT_DIR, 'src/app/not-found.tsx'), 'utf-8')
    expect(notFoundContent).toContain('URL이 정확한지 확인해보세요')
    expect(notFoundContent).toContain('검색 기능')
  })

  it('should use correct styling', () => {
    const notFoundContent = readFileSync(join(ROOT_DIR, 'src/app/not-found.tsx'), 'utf-8')
    expect(notFoundContent).toContain('bg-[#0E1117]')
  })
})

describe('Global Loading State (loading.tsx)', () => {
  it('should exist and have correct structure', () => {
    const loadingPath = join(ROOT_DIR, 'src/app/loading.tsx')
    expect(existsSync(loadingPath)).toBe(true)
  })

  it('should have Korean loading messages', () => {
    const loadingContent = readFileSync(join(ROOT_DIR, 'src/app/loading.tsx'), 'utf-8')
    expect(loadingContent).toContain('로딩 중...')
    expect(loadingContent).toContain('데이터를 불러오고 있습니다')
  })

  it('should have animated spinner', () => {
    const loadingContent = readFileSync(join(ROOT_DIR, 'src/app/loading.tsx'), 'utf-8')
    expect(loadingContent).toContain('animate-spin')
    expect(loadingContent).toContain('border-t-blue-500')
  })

  it('should have chart icon', () => {
    const loadingContent = readFileSync(join(ROOT_DIR, 'src/app/loading.tsx'), 'utf-8')
    expect(loadingContent).toContain('fa-chart-line')
  })

  it('should have animated dots', () => {
    const loadingContent = readFileSync(join(ROOT_DIR, 'src/app/loading.tsx'), 'utf-8')
    expect(loadingContent).toContain('animate-bounce')
  })

  it('should have progress bar', () => {
    const loadingContent = readFileSync(join(ROOT_DIR, 'src/app/loading.tsx'), 'utf-8')
    expect(loadingContent).toContain('bg-gradient-to-r')
    expect(loadingContent).toContain('from-blue-500')
  })
})

describe('Dashboard Error Boundary', () => {
  it('should exist and have correct structure', () => {
    const dashboardErrorPath = join(ROOT_DIR, 'src/app/dashboard/error.tsx')
    expect(existsSync(dashboardErrorPath)).toBe(true)
  })

  it('should have use client directive', () => {
    const dashboardErrorContent = readFileSync(join(ROOT_DIR, 'src/app/dashboard/error.tsx'), 'utf-8')
    expect(dashboardErrorContent).toContain("'use client'")
  })

  it('should have dashboard-specific error messages', () => {
    const dashboardErrorContent = readFileSync(join(ROOT_DIR, 'src/app/dashboard/error.tsx'), 'utf-8')
    expect(dashboardErrorContent).toContain('대시보드 오류')
    expect(dashboardErrorContent).toContain('대시보드를 불러오는 중')
  })

  it('should have dashboard-specific styling', () => {
    const dashboardErrorContent = readFileSync(join(ROOT_DIR, 'src/app/dashboard/error.tsx'), 'utf-8')
    expect(dashboardErrorContent).toContain('bg-black')
    expect(dashboardErrorContent).toContain('text-white')
  })

  it('should have return home link', () => {
    const dashboardErrorContent = readFileSync(join(ROOT_DIR, 'src/app/dashboard/error.tsx'), 'utf-8')
    expect(dashboardErrorContent).toContain('홈으로 돌아가기')
    expect(dashboardErrorContent).toContain('href="/"')
  })
})

describe('Dashboard Loading State', () => {
  it('should exist and have correct structure', () => {
    const dashboardLoadingPath = join(ROOT_DIR, 'src/app/dashboard/loading.tsx')
    expect(existsSync(dashboardLoadingPath)).toBe(true)
  })

  it('should have dashboard-specific loading UI', () => {
    const dashboardLoadingContent = readFileSync(join(ROOT_DIR, 'src/app/dashboard/loading.tsx'), 'utf-8')
    expect(dashboardLoadingContent).toContain('대시보드 로딩 중...')
  })

  it('should have sidebar skeleton', () => {
    const dashboardLoadingContent = readFileSync(join(ROOT_DIR, 'src/app/dashboard/loading.tsx'), 'utf-8')
    expect(dashboardLoadingContent).toContain('w-64')
    expect(dashboardLoadingContent).toContain('bg-[#0E1117]')
  })

  it('should have card skeletons', () => {
    const dashboardLoadingContent = readFileSync(join(ROOT_DIR, 'src/app/dashboard/loading.tsx'), 'utf-8')
    expect(dashboardLoadingContent).toContain('animate-pulse')
    expect(dashboardLoadingContent).toContain('bg-white/5')
  })

  it('should have loading overlay', () => {
    const dashboardLoadingContent = readFileSync(join(ROOT_DIR, 'src/app/dashboard/loading.tsx'), 'utf-8')
    expect(dashboardLoadingContent).toContain('fixed inset-0')
    expect(dashboardLoadingContent).toContain('z-50')
  })
})

describe('Error Pages Integration', () => {
  it('should have consistent Korean language', () => {
    const errorContent = readFileSync(join(ROOT_DIR, 'src/app/error.tsx'), 'utf-8')
    const notFoundContent = readFileSync(join(ROOT_DIR, 'src/app/not-found.tsx'), 'utf-8')
    const loadingContent = readFileSync(join(ROOT_DIR, 'src/app/loading.tsx'), 'utf-8')

    // All pages should have Korean text
    expect(errorContent).toMatch(/[\uAC00-\uD7A3]/) // Korean characters
    expect(notFoundContent).toMatch(/[\uAC00-\uD7A3]/)
    expect(loadingContent).toMatch(/[\uAC00-\uD7A3]/)
  })

  it('should have consistent dark theme', () => {
    const errorContent = readFileSync(join(ROOT_DIR, 'src/app/error.tsx'), 'utf-8')
    const notFoundContent = readFileSync(join(ROOT_DIR, 'src/app/not-found.tsx'), 'utf-8')
    const dashboardErrorContent = readFileSync(join(ROOT_DIR, 'src/app/dashboard/error.tsx'), 'utf-8')

    // Check for dark theme classes
    expect(errorContent).toContain('bg-[#0E1117]')
    expect(notFoundContent).toContain('bg-[#0E1117]')
    expect(dashboardErrorContent).toContain('bg-black')
  })

  it('should use Font Awesome icons', () => {
    const errorContent = readFileSync(join(ROOT_DIR, 'src/app/error.tsx'), 'utf-8')
    const notFoundContent = readFileSync(join(ROOT_DIR, 'src/app/not-found.tsx'), 'utf-8')
    const loadingContent = readFileSync(join(ROOT_DIR, 'src/app/loading.tsx'), 'utf-8')

    expect(errorContent).toContain('fa-')
    expect(notFoundContent).toContain('fa-')
    expect(loadingContent).toContain('fa-')
  })

  it('should have proper export structure', () => {
    const errorContent = readFileSync(join(ROOT_DIR, 'src/app/error.tsx'), 'utf-8')
    const notFoundContent = readFileSync(join(ROOT_DIR, 'src/app/not-found.tsx'), 'utf-8')
    const loadingContent = readFileSync(join(ROOT_DIR, 'src/app/loading.tsx'), 'utf-8')

    expect(errorContent).toContain('export default function')
    expect(notFoundContent).toContain('export default function')
    expect(loadingContent).toContain('export default function')
  })
})

describe('File Organization', () => {
  it('should have error pages in correct locations', () => {
    // Global error pages
    expect(existsSync(join(ROOT_DIR, 'src/app/error.tsx'))).toBe(true)
    expect(existsSync(join(ROOT_DIR, 'src/app/not-found.tsx'))).toBe(true)
    expect(existsSync(join(ROOT_DIR, 'src/app/loading.tsx'))).toBe(true)

    // Dashboard error pages
    expect(existsSync(join(ROOT_DIR, 'src/app/dashboard/error.tsx'))).toBe(true)
    expect(existsSync(join(ROOT_DIR, 'src/app/dashboard/loading.tsx'))).toBe(true)
  })

  it('should follow Next.js 16 conventions', () => {
    const errorContent = readFileSync(join(ROOT_DIR, 'src/app/error.tsx'), 'utf-8')

    // error.tsx should be client component
    expect(errorContent).toContain("'use client'")

    // Should have correct parameter types for Next.js 16
    expect(errorContent).toContain('error: Error')
    expect(errorContent).toContain('digest?: string')
  })
})
