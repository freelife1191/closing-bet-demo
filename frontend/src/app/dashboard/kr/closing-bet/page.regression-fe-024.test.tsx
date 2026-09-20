// Regression: [FE-024] — 실제 비용을 일으키는 버튼에 이름도 확인 절차도 없던 문제
// 근거: docs/dev-cycle/TODO.md [FE-024] (2026-09-03 JONGGA-005 사이클의 /qa-only ISSUE-002)
//
// 종가베팅 화면에서 접근 가능한 이름이 없는 버튼이 여덟 개였고, 그 가운데 셋은 누르는
// 순간 되돌릴 수 없는 지출을 일으켰다. 스크리너 전체 업데이트는 엔진을 통째로 돌리고,
// GEMINI AI 재분석과 카드별 「이 종목만 재분석」은 같은 Gemini 엔드포인트를 호출한다.
// 아이콘만 있어서 스크린 리더에는 「버튼」이라고만 읽혔고, 키보드로 탐색하다 스페이스바를
// 누르면 그대로 실행되었다.
//
// 검사는 두 갈래다. 이름이 비어 있지 않은 것과, 비용을 일으키는 조작이 확인 모달을 거치는
// 것이다. 뒤의 것이 분기를 만들었으므로 취소와 실행 두 경로를 모두 고정한다.
//
// 이름을 셀 때 `title` 은 이름으로 치지 않는다. accname 명세의 최후 폴백이라 터치
// 기기에서는 노출되지 않고 일부 스크린 리더 설정은 읽지 않는다. `title` 을 인정하면
// 카드의 재분석 버튼이 이름 없이도 통과한다.

import { fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import JonggaV2Page from './page';
import ChatWidget from '@/app/components/ChatWidget';
import Header from '@/app/components/Header';

const KST_DATE = new Intl.DateTimeFormat('sv-SE', { timeZone: 'Asia/Seoul' });
const TODAY = () => `${KST_DATE.format(new Date())}T12:00:00+09:00`;

const SIGNAL = {
  stock_code: '044490',
  stock_name: '태웅',
  market: 'KOSDAQ',
  sector: '기계',
  grade: 'B',
  score: { total: 12, base_score: 12, bonus_score: 0 },
  checklist: { has_news: false, volume_surge: false, supply_positive: false },
  current_price: 37_250,
  entry_price: 37_200,
  stop_price: 36_084,
  target_price: 39_060,
  change_pct: 11.5,
  trading_value: 100_000_000_000,
  signal_date: KST_DATE.format(new Date()),
};

const api = vi.hoisted(() => ({ fetchAPI: vi.fn() }));

vi.mock('@/lib/api', () => ({
  fetchAPI: api.fetchAPI,
}));

// `next/navigation` 과 `next-auth/react` 는 vitest.setup.ts 가 이미 목킹한다.
// 여기서 다시 목킹하면 그쪽이 함께 주는 useRouter 와 useSearchParams 를 잃는다.
vi.mock('@/hooks/useAdmin', () => ({
  useAdmin: () => ({ isAdmin: true, isLoading: false }),
}));

vi.mock('@/app/components/BuyStockModal', () => ({ default: () => null }));
vi.mock('@/app/components/ClosingBetCriteriaModal', () => ({ default: () => null }));

// 비용을 일으키는 조작의 API 경로. 확인을 거치지 않고 이 경로로 나가면 결함이다.
const COSTLY_PATHS = ['/api/kr/jongga-v2/run', '/api/kr/jongga-v2/reanalyze-gemini'];

function costlyCalls() {
  return api.fetchAPI.mock.calls.filter(([path]) => COSTLY_PATHS.includes(path as string));
}

// 접근 가능한 이름이 없는 컨트롤. `title` 은 이름으로 치지 않고, select 의 option
// 텍스트도 select 자체의 이름으로 오인하지 않는다.
function unnamedControls() {
  return Array.from(document.querySelectorAll('button, select, a')).filter((control) => {
    if (control instanceof HTMLSelectElement) {
      return !(
        control.getAttribute('aria-label')
        || control.getAttribute('aria-labelledby')
        || control.labels?.length
      );
    }

    return !(
      (control.textContent || '').trim()
      || control.getAttribute('aria-label')
      || control.getAttribute('aria-labelledby')
    );
  });
}

async function renderPage() {
  render(<JonggaV2Page />);
  await screen.findByText('₩37,250');
}

function dialog() {
  return document.querySelector('[role="dialog"], [role="alertdialog"]') as HTMLElement | null;
}

beforeEach(() => {
  api.fetchAPI.mockReset();
  api.fetchAPI.mockImplementation(async (path: string) => {
    if (path === '/api/kr/jongga-v2/dates') return [];
    if (path === '/api/kr/jongga-v2/latest') {
      return {
        date: KST_DATE.format(new Date()),
        total_candidates: 1,
        filtered_count: 1,
        signals: [SIGNAL],
        updated_at: TODAY(),
        status: 'ok',
      };
    }
    if (path === '/api/kr/jongga-v2/status') return { is_running: false };
    return {};
  });
});

describe('[FE-024] 버튼의 접근 가능한 이름', () => {
  it('종가베팅 화면의 모든 버튼이 이름을 가진다', async () => {
    await renderPage();

    expect(unnamedControls().map((control) => control.outerHTML.slice(0, 120))).toEqual([]);
  });

  it('종가베팅 선택 상자 다섯 개가 화면 문구와 같은 정확한 이름을 가진다', async () => {
    await renderPage();

    expect(screen.getByRole('combobox', { name: '거래대금' })).toBeTruthy();
    expect(screen.getByRole('combobox', { name: '상승률' })).toBeTruthy();
    expect(screen.getByRole('combobox', { name: '등급' })).toBeTruthy();
    expect(screen.getByRole('combobox', { name: '총점' })).toBeTruthy();
    expect(screen.getByRole('combobox', { name: '리포트 날짜' })).toBeTruthy();
  });

  it('모달을 열어도 이름 없는 버튼이 생기지 않는다', async () => {
    await renderPage();

    // 상세 분석 모달과 차트 모달의 닫기 버튼은 모달이 닫혀 있으면 DOM 에 없다.
    fireEvent.click(screen.getAllByRole('button', { name: '상세 분석 보기' })[0]);

    await waitFor(() => expect(screen.getAllByRole('button', { name: '닫기' }).length).toBeGreaterThan(0));
    expect(unnamedControls().map((control) => control.outerHTML.slice(0, 120))).toEqual([]);
  });

  it('종목 상세를 이름 있는 대화상자로 열고 Escape 한 번으로 닫는다', async () => {
    await renderPage();

    fireEvent.click(screen.getAllByRole('button', { name: '상세 분석 보기' })[0]);

    const detail = await screen.findByRole('dialog', { name: '태웅' });
    const layer = detail.closest('[data-modal-layer]') as HTMLElement;
    expect(layer).not.toBeNull();
    expect(layer.className).not.toContain('animate-fade-in');
    expect(detail.className).toContain('animate-fade-in');
    expect(within(detail).getByRole('button', { name: '닫기' })).toBeTruthy();

    fireEvent.keyDown(document, { key: 'Escape' });
    await waitFor(() => expect(screen.queryByRole('dialog', { name: '태웅' })).toBeNull());
  });

  it('차트를 이름 있는 대화상자로 열고 애니메이션을 고정 host가 아닌 카드에 둔다', async () => {
    await renderPage();

    fireEvent.click(screen.getByTestId('mini-chart'));

    const chart = await screen.findByRole('dialog', { name: '태웅' });
    const layer = chart.closest('[data-modal-layer]') as HTMLElement;
    expect(layer).not.toBeNull();
    expect(layer.className).not.toContain('animate-fade-in');
    expect(chart.className).toContain('animate-fade-in');
    for (const deadClass of ['animate-in', 'fade-in', 'zoom-in-95']) {
      expect(chart.classList.contains(deadClass)).toBe(false);
    }
  });

  it('헤더의 아이콘 버튼 셋이 이름을 가진다', () => {
    render(<Header />);

    // 사이드바를 여닫는 토글이므로 「열기」로 고정하지 않는다.
    expect(screen.getByRole('button', { name: '메뉴 열고 닫기' })).toBeTruthy();
    expect(screen.getByRole('button', { name: '검색' })).toBeTruthy();
    expect(screen.getByRole('button', { name: '설정 열기' })).toBeTruthy();
  });

  it('챗봇 토글의 이름은 고정이고 상태는 aria-expanded 가 말한다', () => {
    render(<ChatWidget />);

    const toggle = screen.getByRole('button', { name: 'AI 상담' });
    expect(toggle.getAttribute('aria-expanded')).toBe('false');

    fireEvent.click(toggle);

    expect(toggle.getAttribute('aria-expanded')).toBe('true');
    expect(unnamedControls().map((control) => control.outerHTML.slice(0, 120))).toEqual([]);
  });
});

describe('[FE-024] 비용을 일으키는 조작의 확인 절차', () => {
  it('버튼을 눌러도 곧바로 API 를 부르지 않고 확인을 묻는다', async () => {
    await renderPage();

    fireEvent.click(screen.getByRole('button', { name: 'GEMINI AI 재분석' }));

    expect(costlyCalls()).toEqual([]);
    expect(dialog()).toBeTruthy();
    expect(dialog()!.textContent).toContain('실제 요금이 발생');
  });

  it('취소를 누르면 아무것도 실행하지 않는다', async () => {
    await renderPage();

    fireEvent.click(screen.getByRole('button', { name: 'GEMINI AI 재분석' }));
    fireEvent.click(within(dialog()!).getByRole('button', { name: '취소' }));

    expect(costlyCalls()).toEqual([]);
    expect(dialog()).toBeNull();
  });

  it('실행을 눌러야 Gemini 재분석이 나간다', async () => {
    await renderPage();

    fireEvent.click(screen.getByRole('button', { name: 'GEMINI AI 재분석' }));
    fireEvent.click(within(dialog()!).getByRole('button', { name: '실행' }));

    await waitFor(() =>
      expect(costlyCalls().map(([path]) => path)).toEqual(['/api/kr/jongga-v2/reanalyze-gemini'])
    );
  });

  it('실행을 눌러야 스크리너 전체 업데이트가 나간다', async () => {
    await renderPage();

    fireEvent.click(screen.getByRole('button', { name: '스크리너 전체 업데이트' }));
    fireEvent.click(within(dialog()!).getByRole('button', { name: '실행' }));

    await waitFor(() =>
      expect(costlyCalls().map(([path]) => path)).toEqual(['/api/kr/jongga-v2/run'])
    );
  });

  it('카드별 재분석도 같은 확인을 거친다', async () => {
    await renderPage();

    fireEvent.click(screen.getByRole('button', { name: '태웅 이 종목만 재분석' }));

    expect(costlyCalls()).toEqual([]);
    expect(dialog()!.textContent).toContain('실제 요금이 발생');

    fireEvent.click(within(dialog()!).getByRole('button', { name: '실행' }));

    await waitFor(() =>
      expect(costlyCalls().map(([path]) => path)).toEqual(['/api/kr/jongga-v2/reanalyze-gemini'])
    );
    expect(costlyCalls().at(-1)?.[1]?.body).toContain('044490');
  });
});


describe('[FE-034] 제목 계층', () => {
  it('페이지 제목과 펼친 전략 및 종목을 연속된 제목 계층으로 제공한다', async () => {
    await renderPage();
    expect(screen.getAllByRole('heading', { level: 1 })).toHaveLength(1);
    expect(screen.getByRole('heading', { level: 1 }).textContent?.replace(/\s/g, '')).toBe('종가베팅');
    expect(screen.getByRole('heading', { level: 2, name: '태웅' })).toBeTruthy();
    const tips = screen.getByRole('button', { name: /Trading Tips & Strategy/ });
    fireEvent.click(tips);
    expect(screen.getByRole('heading', { level: 2, name: 'Trading Tips & Strategy' })).toBeTruthy();
    expect(screen.getByRole('heading', { level: 3, name: 'Market Adaptation Strategy' })).toBeTruthy();
    expect(screen.getByRole('heading', { level: 4, name: '1) 신고가 조정 후 반등' })).toBeTruthy();
  });
});
