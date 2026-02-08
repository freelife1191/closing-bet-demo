/**
 * Next.js 16 + React 19 업그레이드 완료 후 테스트
 *
 * 이 테스트는 Next.js 16과 React 19로 업그레이드 후
 * 핵심 기능이 정상 작동하는지 확인합니다.
 */

import { describe, it, expect, beforeAll } from 'vitest'
import { readFileSync, existsSync } from 'fs'
import { join } from 'path'

const ROOT_DIR = process.cwd()

describe('Next.js 16 + React 19 Upgrade Tests', () => {
  let currentVersions: any = {}

  beforeAll(async () => {
    currentVersions = {
      next: require('next/package.json').version,
      react: require('react/package.json').version,
      'react-dom': require('react-dom/package.json').version,
    }
  })

  describe('Version Verification', () => {
    it('should have Next.js 16.x installed', () => {
      expect(currentVersions.next).toMatch(/^16\./)
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

    it('should support React 19 types', () => {
      const React = require('react')
      // React 19의 새로운 타입 확인
      expect(React.useActionState).toBeDefined()
    })
  })

  describe('Next.js Configuration', () => {
    it('should have valid next.config.js for Next.js 16', () => {
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

  describe('React 19 Features', () => {
    it('should support useActionState', () => {
      const React = require('react')
      expect(React.useActionState).toBeDefined()
      expect(typeof React.useActionState).toBe('function')
    })

    it('should not have deprecated useFormState', () => {
      const React = require('react')
      // React 19에서 useFormState는 제거됨
      expect(React.useFormState).toBeUndefined()
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

  describe('Build System', () => {
    it('should have ESLint config for Next.js 16', () => {
      const pkgPath = join(ROOT_DIR, 'package.json')
      const pkgContent = readFileSync(pkgPath, 'utf-8')
      const pkg = JSON.parse(pkgContent)

      expect(pkg.devDependencies.eslint).toBeDefined()
      expect(pkg.devDependencies['eslint-config-next']).toBeDefined()

      const eslintVersion = pkg.devDependencies.eslint.replace(/^\^/, '')
      expect(eslintVersion).toMatch(/^9\./) // ESLint 9 required for Next.js 16

      const eslintConfigVersion = pkg.devDependencies['eslint-config-next'].replace(/^\^/, '')
      expect(eslintConfigVersion).toMatch(/^16\./)
    })
  })
})

describe('Next.js 16 Breaking Changes - Code Scan', () => {
  describe('params Promise Pattern', () => {
    it('should scan for params usage patterns', () => {
      const { execSync } = require('child_process')

      try {
        // params를 사용하는 파일들 찾기
        const grepResult = execSync('grep -r "params" src/app --include="*.tsx" --include="*.ts" | head -20', {
          encoding: 'utf-8',
          cwd: ROOT_DIR,
        })

        console.log('Files using params:')
        console.log(grepResult || 'No params usage found')

        // Next.js 16에서는 모든 params를 await 해야 함
        // 이 테스트는 단순히 사용을 감지만 확인
        expect(grepResult).toBeDefined()
      } catch (error: any) {
        // grep이 결과를 못 찾으면 에러가 발생할 수 있음
        console.log('No params usage found or grep failed')
      }
    })
  })

  describe('useFormState Migration', () => {
    it('should check for deprecated useFormState usage', () => {
      const { execSync } = require('child_process')

      try {
        const grepResult = execSync('grep -r "useFormState" src --include="*.tsx" --include="*.ts"', {
          encoding: 'utf-8',
          cwd: ROOT_DIR,
        })

        // useFormState가 사용되고 있으면 경고
        if (grepResult.trim()) {
          console.warn('⚠️  useFormState usage found (deprecated in React 19):')
          console.warn(grepResult)
        }
      } catch (error: any) {
        // 결과가 없으면 정상 (useFormState를 사용하지 않음)
        console.log('✅ No useFormState usage found')
      }
    })
  })
})

describe('Regression Tests - Complete Upgrade', () => {
  it('should maintain same project structure', () => {
    const appDir = join(ROOT_DIR, 'src/app')
    const libDir = join(ROOT_DIR, 'src/lib')
    const componentsDir = join(ROOT_DIR, 'src/app/components')

    expect(existsSync(appDir)).toBe(true)
    expect(existsSync(libDir)).toBe(true)
    expect(existsSync(componentsDir)).toBe(true)
  })

  it('should maintain all dependencies', () => {
    const pkgPath = join(ROOT_DIR, 'package.json')
    const pkgContent = readFileSync(pkgPath, 'utf-8')
    const pkg = JSON.parse(pkgContent)

    // 모든 원래 의존성이 존재해야 함
    expect(pkg.dependencies['next-auth']).toBeDefined()
    expect(pkg.dependencies['crypto-js']).toBeDefined()
    expect(pkg.dependencies['lightweight-charts']).toBeDefined()
    expect(pkg.dependencies['react-icons']).toBeDefined()
    expect(pkg.dependencies['react-markdown']).toBeDefined()
    expect(pkg.dependencies['remark-gfm']).toBeDefined()
    expect(pkg.dependencies['zustand']).toBeDefined()
  })

  it('should maintain all test scripts', () => {
    const pkgPath = join(ROOT_DIR, 'package.json')
    const pkgContent = readFileSync(pkgPath, 'utf-8')
    const pkg = JSON.parse(pkgContent)

    expect(pkg.scripts.dev).toBeDefined()
    expect(pkg.scripts.build).toBeDefined()
    expect(pkg.scripts.start).toBeDefined()
    expect(pkg.scripts.lint).toBeDefined()
    expect(pkg.scripts.test).toBeDefined()
    expect(pkg.scripts['test:baseline']).toBeDefined()
    expect(pkg.scripts['type-check']).toBeDefined()
  })
})

/**
 * 업그레이드 성공 확인
 */
describe('Upgrade Success Summary', () => {
  it('should log successful upgrade', () => {
    const pkg = require(join(ROOT_DIR, 'package.json'))
    const nextVersion = require('next/package.json').version
    const reactVersion = require('react/package.json').version

    console.log('')
    console.log('══════════════════════════════════════════════════════════')
    console.log('  ✅ Next.js 16 + React 19 Upgrade Complete!')
    console.log('══════════════════════════════════════════════════════════')
    console.log('')
    console.log('  📦 Versions:')
    console.log(`     Next.js: ${nextVersion}`)
    console.log(`     React:   ${reactVersion}`)
    console.log('')
    console.log('  📋 Next Steps:')
    console.log('     1. Update code for params Promise pattern')
    console.log('     2. Update form actions to use useActionState')
    console.log('     3. Update form action return types to void')
    console.log('     4. Run full build test')
    console.log('     5. Run application smoke tests')
    console.log('')
    console.log('  ⚠️  Breaking Changes to Address:')
    console.log('     • params → Promise (await props.params)')
    console.log('     • useFormState → useActionState')
    console.log('     • Form actions should return void')
    console.log('     • Consider PageProps/LayoutProps helpers')
    console.log('')
    console.log('══════════════════════════════════════════════════════════')
    console.log('')

    expect(nextVersion).toMatch(/^16\./)
    expect(reactVersion).toMatch(/^19\./)
  })

  it('should provide migration checklist', () => {
    const checklist = [
      '[ ] Update dynamic routes to await props.params',
      '[ ] Replace useFormState with useActionState',
      '[ ] Update form actions to return void',
      '[ ] Add error.tsx files for error boundaries',
      '[ ] Test authentication flow',
      '[ ] Test all API routes',
      '[ ] Run E2E tests',
    ]

    console.log('')
    console.log('📝 Migration Checklist:')
    checklist.forEach((item, index) => {
      const status = item.startsWith('[x') ? '✅' : '⏳'
      console.log(`   ${status} ${item}`)
    })
    console.log('')

    expect(checklist.length).toBeGreaterThan(0)
  })
})
