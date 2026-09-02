# 낡은 업그레이드 베이스라인 테스트 정리 실행 계획

> **For agentic workers:** 이 문서는 `[FE-001]` 한 항목의 계획입니다. `tier-rules.md`
> §1 이 T3 에 요구하는 근거 기록이며, 체크박스는 `docs/dev-cycle/TODO.md` 가 갖고
> 있으므로 여기에 중복해 두지 않습니다.

**목표:** 업그레이드 시점마다 늘어난 베이스라인 테스트 네 파일 가운데, 지난 시점을
검사하느라 지금은 아무것도 막지 못하는 두 파일을 걷어내고 `test:baseline` 게이트가
현재 버전을 실제로 검사하게 만든다.

**접근:** 두 파일에만 있던 검사를 `upgrade-nextjs16.test.ts` 로 옮긴 뒤 삭제한다.
검사를 하나도 잃지 않으면서 503줄을 줄인다. npm 스크립트는 이름을 유지한 채 가리키는
파일만 바꾸므로, 그 이름을 참조하는 `AGENTS.md`, `rollback-upgrade.sh`, 그리고 스크립트
존재를 검사하는 테스트 두 곳은 손대지 않아도 된다.

**기술 스택:** vitest 2.1.9, Next.js 16.1.6, React 19.2.4

**근거 문서:** `docs/dev-cycle/TODO.md` 의 `[FE-001]`,
`docs/dev-cycle/audits/AUDIT-INFRA.md` 의 「기존 백로그와의 관계」

---

## 전제 조건 검증 결과

착수 전에 백로그가 적은 전제를 실측했고 두 가지가 사실과 달랐다.

| 백로그의 서술 | 실측 |
|---|---|
| 「세 건이 과거 버전을 고정 검사해 항상 실패한다」 | 실패 0건. 커밋 `4fafd29` 가 이미 제거했다 |
| 「vitest 160개 전체 통과 확인」 | 현재 25파일 206개다 |

따라서 이 항목의 실질은 실패를 고치는 일이 아니라, 실패하지 않으면서 아무것도 검사하지
않는 파일을 걷어내는 일이다.

## 파일 구조

| 파일 | 처리 |
|---|---|
| `frontend/tests/baseline/upgrade-baseline.test.ts` | 삭제 (245줄) |
| `frontend/tests/baseline/upgrade-nextjs15.test.ts` | 삭제 (258줄) |
| `frontend/tests/baseline/upgrade-nextjs16.test.ts` | 검사 네 가지 이관 |
| `frontend/package.json` | `test:baseline` 이 가리키는 파일 변경 |
| `README.md` | 477행의 참조 갱신 |

## 삭제 근거

`.claude/skills/dev-cycle/SKILL.md` 의 「테스트 정책」이 정한 세 기준 가운데 두 가지에
해당한다.

**기준 2 — 같은 대상을 검사하는 테스트가 여럿이고 그중 하나가 나머지를 포함한다.**
`upgrade-nextjs15.test.ts` 의 검사는 `Version Verification`, `Type System
Compatibility`, `Next.js Configuration`, `Project Structure`, `NextAuth
Compatibility`, `React 19 New Features` 까지 모두 `upgrade-nextjs16.test.ts` 에 같은
형태로 있다. `Build System` 의 eslint 검사는 16 쪽이 더 강하다. 15 쪽은 존재만 보는데
16 쪽은 `eslint-config-next` 의 메이저 버전까지 본다.

**기준 3 — 검사 대상이 사라져 아무것도 검사하지 않는다.**
세 갈래가 해당한다.

1. `upgrade-baseline.test.ts:231` 의 `regressionTests` export 는 호출하는 쪽이 저장소에
   없다. 정의가 유일한 등장이므로 실행되지 않는다.
2. `upgrade-baseline.test.ts:116-148` 의 `Build Compatibility` 는 `npx tsc --noEmit` 과
   `npm run lint` 를 try/catch 로 감싸 실패를 삼킨다. 두 검사에 12.9초가 드는데 결과는
   언제나 통과다. 같은 대상을 `tests/smoke/upgrade-smoke.test.ts:94` 가 실제 단언과 함께
   검사한다.
3. `upgrade-nextjs15.test.ts:219-257` 의 `Preparation for Next.js 16` 은 16 으로 올린
   뒤라 준비할 대상이 없다. `should document breaking changes to address` 는 하드코딩한
   배열의 길이가 0보다 큰지 보므로 언제나 참이다.

## 이관하는 검사 네 가지

삭제되는 두 파일에만 있고 `upgrade-nextjs16.test.ts` 와 `upgrade-smoke.test.ts` 어느
쪽에도 없는 검사다.

| 검사 | 원래 위치 | 남겨야 하는 이유 |
|---|---|---|
| `next.config.js` 의 `/api/:path` rewrite | `upgrade-baseline.test.ts:213` | 이 프록시 설정이 사라지면 프런트엔드가 Flask 에 닿지 못해 화면 전체가 빈다 |
| 대시보드 네 페이지 존재 | `upgrade-baseline.test.ts:194-199` | 라우트가 사라진 것을 빌드 성공만으로는 잡지 못한다 |
| `Providers.tsx` 의 `SessionProvider` 와 `'use client'` | `upgrade-baseline.test.ts:170-172` | 세션 공급자가 빠지면 인증이 조용히 끊긴다 |
| `dashboard/layout.tsx` 존재 | `upgrade-baseline.test.ts:176` | 필수 파일 목록에 한 줄 더하는 것으로 끝난다 |
| `package.json` 의 `react-dom` 선언 존재 | `upgrade-baseline.test.ts:72` | 남은 검사는 모두 설치본을 보므로, 선언이 빠져도 `node_modules` 에 남은 잔여물이 통과시킨다 |

옮기지 않는 검사와 그 이유를 함께 적는다.

- `react-dom/client` 의 `createRoot` 존재: React DOM 이 설치되어 있으면 반드시 있다.
- `devDependencies` 의 `vitest` 와 `@testing-library/react` 존재: 없으면 이 테스트 자체가
  실행되지 않으므로 자기 참조다.
- `tsconfig.compilerOptions.target` 존재: `toBeDefined()` 하나뿐이라 값을 검사하지 않는다.
- `page.tsx` 가 `'use client'` 를 담고 있는지: 그 페이지를 서버 컴포넌트로 바꾸는 것은
  개선일 수 있는데, 이 검사가 있으면 개선이 실패로 잡힌다.
- `page.tsx` 가 `export default function` 을 담고 있는지: 기본 내보내기가 없으면 Next.js
  빌드가 그 자리에서 실패하고, `tests/smoke/upgrade-smoke.test.ts:58` 이 실제로 빌드를
  돌린다. 문자열 검사는 `export default async function` 이나 `const Page = () => {}` 뒤에
  오는 `export default Page` 를 오히려 실패로 잡으므로 되살리지 않는다.

`devDependencies.typescript` 존재 검사는 처음에 빠뜨렸다가 `/code-review` 의 지적으로
되살렸다. `npx tsc --noEmit` 은 로컬에 없으면 전역에 설치된 `tsc` 로 넘어갈 수 있어서,
선언이 사라진 상태를 타입 검사만으로는 잡지 못한다. `Build System` 의 eslint 검사 옆에
한 줄로 넣었다.

## 버전 검사를 유지하는 판단

`TODO.md` 의 세 번째 체크박스가 묻는 「유지할지 삭제할지, 하한선 검사로 바꾸는 방안
포함」에 대한 답이다.

`upgrade-nextjs16.test.ts` 의 `/^16\./` 와 `/^19\./` 는 **유지한다**. 이미 걷어낸
14.x·18.x·15.x 검사와 성격이 다르다. 그것들은 지난 버전을 검사해 구조적으로 실패하고
있었지만, 이 검사는 현재 버전을 검사하며 통과한다. 하한선 비교로 바꾸면 메이저 경계를
넘는 사고를 잡지 못한다. Next 17 로 올릴 때 이 줄을 함께 고치는 것이 정상 절차다.

`[FE-002]` 가 16.1.6 을 16.3.4 로 올려도 `/^16\./` 는 그대로 통과하므로 선행 조건을
막지 않는다.

## 검증

- `npx vitest run` 전체 통과. 삭제 전 25파일 206개에서 두 파일의 41개(`upgrade-baseline`
  18개, `upgrade-nextjs15` 23개)가 빠지고 이관분 2개가 더해져 23파일 167개가 된다.
  대시보드 라우트 검사는 기존 `should have all required files` 에 흡수되어 개수를
  늘리지 않는다.
- `npm run test:baseline` 이 새 경로로 실제 실행되는지 확인한다. 23개가 나와야 한다.
- `npm run type-check`, `npm run lint` 통과.
- pytest 전체 통과. 파이썬을 건드리지 않았음을 확인하는 용도다.
- `/qa-only` 는 `tier-rules.md` §1 의 「테스트 파일만 바꾸는 작업」 제외에 해당한다.
  `package.json` 이 함께 바뀌지만 변경 대상은 npm 스크립트가 가리키는 파일 경로 하나이며
  애플리케이션이 실행하는 코드가 아니다. 브라우저로 확인할 동작이 없다.
