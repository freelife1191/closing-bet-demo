import { describe, expect, it } from 'vitest';

import { resolveJonggaAiEvaluation } from './displayHelpers';

describe('[JONGGA-028] 화면 AI 판정 우선순위', () => {
  it('첫 유효한 최상위 판정을 선택하고 사유가 비었을 때만 legacy 본문을 보충한다', () => {
    expect(resolveJonggaAiEvaluation(
      [
        { action: 'HOLD', confidence: 0, reason: '' },
        { action: 'BUY', confidence: 91, reason: '오래된 매수 판정' },
      ],
      '호환용 오래된 본문 사유',
    )).toEqual({ action: 'HOLD', confidence: 0, reason: '호환용 오래된 본문 사유', model: undefined });
  });

  it('action이 잘못돼도 먼저 온 사유와 bare string을 HOLD로 읽는다', () => {
    expect(resolveJonggaAiEvaluation(
      [{ action: 'UNKNOWN', reason: '최신 사유' }, { action: 'BUY', reason: '오래된 사유' }],
      '',
    )).toEqual({ action: 'HOLD', confidence: undefined, reason: '최신 사유' });
    expect(resolveJonggaAiEvaluation(['사유만 남은 최신 판정'], '')).toEqual({
      action: 'HOLD', confidence: null, reason: '사유만 남은 최신 판정',
    });
  });

  it('숫자·객체·배열 action 또는 사유는 비어 있는 값으로 보고 다음 후보를 쓴다', () => {
    expect(resolveJonggaAiEvaluation(
      [
        { action: ['BUY'], reason: { text: '잘못된 사유' } },
        { action: 'SELL', reason: '다음 유효한 판정' },
        { action: 123, reason: ['잘못된 세부 사유'] },
      ],
      123,
    )).toEqual({ action: 'SELL', confidence: undefined, model: undefined, reason: '다음 유효한 판정' });
  });

  it('legacy 본문만으로는 새 매매 추천을 만들지 않는다', () => {
    expect(resolveJonggaAiEvaluation([], '사유만 남은 오래된 본문')).toBeNull();
  });

  it('NaN·Infinity confidence는 출력 경계에서 버리고 문자열·null만 보존한다', () => {
    for (const confidence of [NaN, Infinity, -Infinity, true, {}]) {
      expect(resolveJonggaAiEvaluation(
        [{ action: 'BUY', reason: {}, confidence, model: {} }],
        '',
      )).toEqual({ action: 'BUY', confidence: undefined, model: undefined, reason: undefined });
    }

    expect(resolveJonggaAiEvaluation(
      [{ action: 'BUY', reason: '근거', confidence: '80', model: 'gemini' }],
      '',
    )).toEqual({ action: 'BUY', confidence: '80', model: 'gemini', reason: '근거' });
    expect(resolveJonggaAiEvaluation(
      [{ action: 'BUY', reason: '근거', confidence: null, model: 'gemini' }],
      '',
    )).toEqual({ action: 'BUY', confidence: null, model: 'gemini', reason: '근거' });
  });
});
