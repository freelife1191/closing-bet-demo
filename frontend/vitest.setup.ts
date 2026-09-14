import { expect, afterEach, vi } from 'vitest'
import { cleanup } from '@testing-library/react'
import * as matchers from '@testing-library/jest-dom/matchers'

// Extend Vitest's expect with jest-dom matchers
expect.extend(matchers)

const mediaQueries = new Map<string, MediaQueryList>()

Object.defineProperty(window, 'matchMedia', {
  configurable: true,
  value: (query: string): MediaQueryList => {
    const existing = mediaQueries.get(query)
    if (existing) return existing
    const events = new EventTarget()
    // jsdom에 없는 API의 사용 경계만 구현하고 이벤트 처리는 DOM에 맡긴다.
    const mediaQuery = Object.assign(events, {
      media: query,
      matches: false,
      onchange: null,
      addListener: (listener: EventListener | null) => events.addEventListener('change', listener),
      removeListener: (listener: EventListener | null) => events.removeEventListener('change', listener),
    }) as MediaQueryList
    mediaQueries.set(query, mediaQuery)
    return mediaQuery
  },
})

// Cleanup after each test
afterEach(() => {
  cleanup()
  mediaQueries.clear()
})

// Mock Next.js router
vi.mock('next/navigation', () => ({
  useRouter: () => ({
    push: vi.fn(),
    replace: vi.fn(),
    prefetch: vi.fn(),
    back: vi.fn(),
    pathname: '/',
    query: {},
  }),
  usePathname: () => '/',
  useSearchParams: () => new URLSearchParams(),
}))

// Mock Next.js image
vi.mock('next/image', () => ({
  default: vi.fn().mockImplementation(({ src, alt, ...props }: any) =>
    // @ts-ignore - JSX in setup file
    'img' as any
  ),
}))

// Mock next-auth
vi.mock('next-auth/react', () => ({
  useSession: () => ({
    data: null,
    status: 'unauthenticated',
  }),
  SessionProvider: ({ children }: { children: any }) => children,
  signIn: vi.fn(),
  signOut: vi.fn(),
}))
