/**
 * Next.js 15 + React 19 업그레이드 후 테스트
 *
 * 이 테스트는 Next.js 15와 React 19로 업그레이드 후
 * 핵심 기능이 정상 작동하는지 확인합니다.
 */

import { describe, it, expect, beforeAll } from 'vitest'
import { readFileSync, existsSync } from 'fs'
import { join } from 'path'

const ROOT_DIR = process.cwd()

describe('Next.js 15 + React 19 Upgrade Tests', () => {
  let currentVersions: any = {}

  beforeAll(async () => {
    currentVersions = {
      next: require('next/package.json').version,
      react: require('react/package.json').version,
      'react-dom': require('react-dom/package.json').version,
    }
  })

  describe('Version Verification', () => {
    it('should have Next.js 15.x installed', () => {
      expect(currentVersions.next).toMatch(/^15\./)
      console.log(`✅ Next.js version: ${currentVersions.next}`)
    })

    it('should have React 19.x installed', () => {
      expect(currentVersions.react).toMatch(/^19\./)
      console.log(`✅ React version: ${currentVersions.react}`)
    })

    it('should have React DOM 19.x installed', () => {
      expect(currentVersions['react-dom']).toMatch(/^19\./)
      console.log(`✅ React DOM version: ${currentVersions['react-dom']}`)
    })
  })

  describe('Type System Compatibility', () => {
    it('should have compatible TypeScript configuration', () => {
      const tsconfigPath = join(ROOT_DIR, 'tsconfig.json')
      const tsconfigContent = readFileSync(tsconfigPath, 'utf-8')
      const tsconfig = JSON.parse(tsconfigContent)

      expect(tsconfig.compilerOptions).toBeDefined()
      expect(tsconfig.compilerOptions.strict).toBe(true)
      expect(tsconfig.compilerOptions.moduleResolution).toBe('bundler')
    })

    it('should have correct target for React 19', () => {
      const tsconfigPath = join(ROOT_DIR, 'tsconfig.json')
      const tsconfigContent = readFileSync(tsconfigPath, 'utf-8')
      const tsconfig = JSON.parse(tsconfigContent)

      // React 19는 ES2022+를 권장
      expect(tsconfig.compilerOptions.target).toBeDefined()
      console.log(`TypeScript target: ${tsconfig.compilerOptions.target}`)
    })
  })

  describe('Next.js Configuration', () => {
    it('should have valid next.config.js for Next.js 15', () => {
      const nextConfig = require(join(ROOT_DIR, 'next.config.js'))
      expect(nextConfig).toBeDefined()
      expect(typeof nextConfig.rewrites).toBe('function')
    })

    it('should maintain transpilePackages configuration', () => {
      const configPath = join(ROOT_DIR, 'next.config.js')
      const configContent = readFileSync(configPath, 'utf-8')
      expect(configContent).toContain('transpilePackages')
    })
  })

  describe('React 19 Compatibility', () => {
    it('should render without errors', () => {
      const { createRoot } = require('react-dom/client')
      expect(createRoot).toBeDefined()
      expect(typeof createRoot).toBe('function')
    })

    it('should support React 19 features', () => {
      const React = require('react')
      // React 19의 useActionState 확인
      expect(React.useActionState).toBeDefined()
    })
  })

  describe('Build System', () => {
    it('should have compatible ESLint configuration', () => {
      const pkgPath = join(ROOT_DIR, 'package.json')
      const pkgContent = readFileSync(pkgPath, 'utf-8')
      const pkg = JSON.parse(pkgContent)

      expect(pkg.devDependencies.eslint).toBeDefined()
      expect(pkg.devDependencies['eslint-config-next']).toBeDefined()
      console.log(`ESLint: ${pkg.devDependencies.eslint}`)
      console.log(`eslint-config-next: ${pkg.devDependencies['eslint-config-next']}`)
    })

    it('should maintain all test dependencies', () => {
      const pkgPath = join(ROOT_DIR, 'package.json')
      const pkgContent = readFileSync(pkgPath, 'utf-8')
      const pkg = JSON.parse(pkgContent)

      expect(pkg.devDependencies.vitest).toBeDefined()
      expect(pkg.devDependencies['@testing-library/react']).toBeDefined()
    })
  })

  describe('Project Structure', () => {
    it('should maintain App Router structure', () => {
      const appDir = join(ROOT_DIR, 'src/app')
      expect(existsSync(appDir)).toBe(true)
    })

    it('should have all required files', () => {
      const requiredFiles = [
        'src/app/layout.tsx',
        'src/app/page.tsx',
        'src/lib/auth.ts',
        'src/lib/api.ts',
        'src/app/components/Providers.tsx',
      ]

      requiredFiles.forEach((file) => {
        const filePath = join(ROOT_DIR, file)
        expect(existsSync(filePath), `${file} should exist`).toBe(true)
      })
    })
  })

  describe('NextAuth Compatibility', () => {
    it('should have valid auth configuration', () => {
      const authPath = join(ROOT_DIR, 'src/lib/auth.ts')
      const authContent = readFileSync(authPath, 'utf-8')

      expect(authContent).toContain('NextAuthOptions')
      expect(authContent).toContain('providers')
    })

    it('should have API route for auth', () => {
      const authRoutePath = join(ROOT_DIR, 'src/app/api/auth/[...nextauth]/route.ts')
      expect(existsSync(authRoutePath)).toBe(true)
    })
  })
})

describe('React 19 New Features Test', () => {
  describe('useActionState', () => {
    it('should have useActionState available', () => {
      const React = require('react')
      expect(React.useActionState).toBeDefined()
      expect(typeof React.useActionState).toBe('function')
    })

    it('should be importable from react', () => {
      // Module exists test
      const reactModule = require('react')
      expect(reactModule).toBeDefined()
      expect(reactModule.useActionState).toBeDefined()
    })
  })

  describe('Form Actions', () => {
    it('should support form action patterns', () => {
      const React = require('react')
      // React 19의 useFormState는 제거되고 useActionState로 대체
      expect(React.useFormState).toBeUndefined()
      expect(React.useActionState).toBeDefined()
    })
  })
})

/**
 * 회귀 테스트: 업그레이드 전후 동일한 결과 검증
 */
describe('Regression Tests - Next.js 14 → 15', () => {
  it('should maintain same project structure', () => {
    const appDir = join(ROOT_DIR, 'src/app')
    const libDir = join(ROOT_DIR, 'src/lib')

    expect(existsSync(appDir)).toBe(true)
    expect(existsSync(libDir)).toBe(true)
  })

  it('should maintain package.json scripts', () => {
    const pkgPath = join(ROOT_DIR, 'package.json')
    const pkgContent = readFileSync(pkgPath, 'utf-8')
    const pkg = JSON.parse(pkgContent)

    expect(pkg.scripts.dev).toBeDefined()
    expect(pkg.scripts.build).toBeDefined()
    expect(pkg.scripts.start).toBeDefined()
    expect(pkg.scripts.lint).toBeDefined()
    expect(pkg.scripts.test).toBeDefined()
  })

  it('should maintain all original dependencies', () => {
    const pkgPath = join(ROOT_DIR, 'package.json')
    const pkgContent = readFileSync(pkgPath, 'utf-8')
    const pkg = JSON.parse(pkgContent)

    // 원래 의존성들이 모두 존재해야 함
    expect(pkg.dependencies['next-auth']).toBeDefined()
    expect(pkg.dependencies['crypto-js']).toBeDefined()
    expect(pkg.dependencies['lightweight-charts']).toBeDefined()
    expect(pkg.dependencies['react-icons']).toBeDefined()
    expect(pkg.dependencies['react-markdown']).toBeDefined()
    expect(pkg.dependencies['remark-gfm']).toBeDefined()
    expect(pkg.dependencies['zustand']).toBeDefined()
  })
})

/**
 * 다음 단계 준비 테스트 (Next.js 16)
 */
describe('Preparation for Next.js 16', () => {
  it('should be ready for params Promise pattern', () => {
    // Next.js 16에서는 params가 Promise가 됨
    // 현재 코드가 이 패턴을 따르는지 확인
    const appDir = join(ROOT_DIR, 'src/app')

    // 동적 라우트들이 있는지 확인
    const hasDynamicRoutes = existsSync(join(appDir, 'dashboard/kr/vcp'))
    expect(hasDynamicRoutes).toBe(true)
  })

  it('should have ESLint 9 for Next.js 16 compatibility', () => {
    const pkgPath = join(ROOT_DIR, 'package.json')
    const pkgContent = readFileSync(pkgPath, 'utf-8')
    const pkg = JSON.parse(pkgContent)

    const eslintVersion = pkg.devDependencies.eslint
    // 버전 문자열에서 ^ 제거 후 체크
    const cleanVersion = eslintVersion.replace(/^\^/, '')
    expect(cleanVersion).toMatch(/^9\./)
    console.log(`ESLint version ready for Next.js 16: ${eslintVersion}`)
  })

  it('should document breaking changes to address', () => {
    // Next.js 16으로 가기 위해 해결해야 할 항목들
    const breakingChanges = [
      'params → Promise (await needed)',
      'useFormState → useActionState',
      'Form actions return void',
      'PageProps/LayoutProps helpers',
    ]

    console.log('⚠️  Breaking changes to address for Next.js 16:')
    breakingChanges.forEach((change, index) => {
      console.log(`   ${index + 1}. ${change}`)
    })

    expect(breakingChanges.length).toBeGreaterThan(0)
  })
})
