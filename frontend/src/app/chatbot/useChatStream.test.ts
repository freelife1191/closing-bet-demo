// Regression: [CHAT-004] — SSE 이벤트 하나를 메시지에 반영하는 규칙
// 근거: docs/dev-cycle/audits/AUDIT-CHAT.md §2.2

import { describe, expect, it } from 'vitest';

import type { Message } from './chatMessageParser';
import { applyStreamEvent } from './useChatStream';

const streamingMessage = (): Message => ({
  role: 'model',
  parts: [''],
  reasoning: '',
  isStreaming: true,
});

const filledMessage = (): Message => ({
  role: 'model',
  parts: ['본문'],
  reasoning: '추론',
  isStreaming: true,
});

describe('applyStreamEvent', () => {
  it('answer_chunk 를 본문 뒤에 잇는다', () => {
    const first = applyStreamEvent(streamingMessage(), { answer_chunk: '안녕' });
    const second = applyStreamEvent(first, { answer_chunk: '하세요' });

    expect(second.parts[0]).toBe('안녕하세요');
  });

  it('answer_chunk 가 없으면 구형 chunk 필드로 물러난다', () => {
    // 기존 회귀 검사(page.regression-chat-001.test.tsx)가 이 형태로 청크를 보낸다.
    const result = applyStreamEvent(streamingMessage(), { chunk: '안녕' });

    expect(result.parts[0]).toBe('안녕');
  });

  it('reasoning_chunk 는 본문이 아니라 추론에 쌓는다', () => {
    const result = applyStreamEvent(streamingMessage(), { reasoning_chunk: '수급을 봤다' });

    expect(result.reasoning).toBe('수급을 봤다');
    expect(result.parts[0]).toBe('');
  });

  it('answer_clear 는 본문만 비우고 추론은 남긴다', () => {
    const result = applyStreamEvent(filledMessage(), { answer_clear: true });

    expect(result.parts[0]).toBe('');
    expect(result.reasoning).toBe('추론');
  });

  it('reasoning_clear 는 추론만 비우고 본문은 남긴다', () => {
    const result = applyStreamEvent(filledMessage(), { reasoning_clear: true });

    expect(result.parts[0]).toBe('본문');
    expect(result.reasoning).toBe('');
  });

  it('clear 는 둘 다 비운다', () => {
    const result = applyStreamEvent(filledMessage(), { clear: true });

    expect(result.parts[0]).toBe('');
    expect(result.reasoning).toBe('');
  });

  it('done 은 스트리밍 표시를 끈다', () => {
    const result = applyStreamEvent(streamingMessage(), { done: true });

    expect(result.isStreaming).toBe(false);
  });

  it('error 는 본문을 오류 문구로 바꾸고 스트리밍을 끝낸다', () => {
    const result = applyStreamEvent(streamingMessage(), { error: '한도를 넘었습니다' });

    expect(result.parts[0]).toBe('한도를 넘었습니다');
    expect(result.isStreaming).toBe(false);
  });

  it('한 이벤트에 비우기와 델타가 함께 오면 비운 뒤에 잇는다', () => {
    const result = applyStreamEvent(filledMessage(), { answer_clear: true, answer_chunk: '새 본문' });

    expect(result.parts[0]).toBe('새 본문');
  });

  it('아무 필드도 없는 이벤트는 메시지를 그대로 돌려준다', () => {
    const original = filledMessage();

    const result = applyStreamEvent(original, { session_id: 'sess-1' });

    expect(result).toBe(original);
  });

  it('원본 메시지를 바꾸지 않는다', () => {
    const original = streamingMessage();

    applyStreamEvent(original, { answer_chunk: '안녕' });

    expect(original.parts[0]).toBe('');
  });
});
