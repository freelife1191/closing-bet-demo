import type { AIRecommendation } from '@/lib/api';

export type SecondaryAI = 'gpt' | 'perplexity';

/**
 * Decide which secondary AI provider to surface in the VCP table.
 *
 * GPT 가 두 번째 AI 다 [VCP-046]. Perplexity 는 그 이전 캐시(2026-02 등)에만 있으므로
 * 그 날짜에 GPT 판정이 하나도 없을 때만 보여 준다. 과거 날짜를 재분석해 GPT 판정이
 * 생기면 열은 GPT 로 바뀌고, 옛 Perplexity 판정은 상세 탭에서 볼 수 있다.
 * 둘 다 없으면 'gpt' 를 기본값으로 둬 빈 Perplexity 열을 만들지 않는다.
 */
export function decideSecondaryAI(hasPerplexity: boolean, hasGpt: boolean): SecondaryAI {
  if (hasGpt) return 'gpt';
  if (hasPerplexity) return 'perplexity';
  return 'gpt';
}

// 백엔드가 실패 판정에 쓰는 기준을 그대로 옮겨 둔다. 출처는
// app/routes/kr_market_signal_common.py 의 _VALID_AI_ACTIONS 와 _INVALID_AI_REASONS 다.
// 응답을 조립하는 경로는 실패 기록을 이미 걸러 내지만, 화면은 병합된 값이 비면
// aiData.signals 를 다시 본다. 그 자료는 원시 캐시라서 실패 기록이 그대로 남아 있다.
const VALID_AI_ACTIONS = new Set(['BUY', 'SELL', 'HOLD']);
const INVALID_AI_REASONS = new Set([
  '-',
  'n/a',
  'na',
  'none',
  'null',
  '분석 실패',
  '분석 대기중',
  '분석 대기 중',
  '분석중',
  '분석 중',
  'no analysis available.',
  'no analysis available',
  'analysis failed',
  'failed',
]);

/**
 * AI 추천 한 건이 실제 분석 결과인지 판별한다.
 *
 * 재분석이 실패하면 action 에 'N/A' 가, reason 에 '분석 실패' 가 채워진다.
 * 값의 존재만 보면 그 기록이 정상 분석으로 통과하므로, 탭이 활성 상태로 보이고
 * 사용자가 눌렀을 때 모든 행이 '-' 인 빈 열을 만난다.
 */
export function isValidAIRecommendation(
  rec: AIRecommendation | null | undefined,
): rec is AIRecommendation {
  if (!rec) return false;
  if (!VALID_AI_ACTIONS.has((rec.action ?? '').trim().toUpperCase())) return false;
  const reason = (rec.reason ?? '').trim().toLowerCase();
  return !!reason && !INVALID_AI_REASONS.has(reason);
}
