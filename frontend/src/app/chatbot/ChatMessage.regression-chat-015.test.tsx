import { fireEvent, render, screen } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';
import { ChatMessage } from './ChatMessage';

describe('CHAT-015 실제 Markdown 제목 렌더', () => {
  it('번호로 시작한 소제목을 한 개의 이름 있는 h3로 렌더한다', () => {
    const onSuggestionClick = vi.fn();
    render(<ChatMessage
      message={{ role: 'model', parts: ['### 1. 시장 환경 및 섹터 강도\n본문 1. 첫 항목 2. 둘째 항목\n[추천 질문]\n- 첫 질문\n- 둘째 질문\n- 셋째 질문\n- 넷째 질문'] }}
      index={0}
      onDeleteTurn={vi.fn()}
      onDeleteMessage={vi.fn()}
      onSuggestionClick={onSuggestionClick}
    />);
    expect(screen.getByRole('heading', { level: 3, name: '1. 시장 환경 및 섹터 강도' })).toBeTruthy();
    expect(screen.getAllByRole('heading')).toHaveLength(1);
    expect(screen.queryByRole('button', { name: '넷째 질문' })).toBeNull();
    fireEvent.click(screen.getByRole('button', { name: '첫 질문' }));
    expect(onSuggestionClick).toHaveBeenCalledWith('첫 질문');
  });

  it('reasoning 안의 번호 제목도 토글 뒤 빈 h3 없이 그대로 렌더한다', () => {
    render(<ChatMessage
      message={{ role: 'model', parts: ['본문'], reasoning: '### 2. 수급 흐름\n본문 1. 첫 항목 2. 둘째 항목' }}
      index={0}
      onDeleteTurn={vi.fn()}
      onDeleteMessage={vi.fn()}
      onSuggestionClick={vi.fn()}
    />);

    fireEvent.click(screen.getByRole('button', { name: '생각하는 과정 표시' }));
    expect(screen.getByRole('heading', { level: 3, name: '2. 수급 흐름' })).toBeTruthy();
    expect(screen.getAllByRole('heading', { level: 3 })).toHaveLength(1);
  });

  it('reasoning 본문의 공백 없는 1) dense numbering은 두 ordered list item으로 유지한다', () => {
    render(<ChatMessage
      message={{ role: 'model', parts: ['본문'], reasoning: '1)첫째 항목 2)둘째 항목' }}
      index={0}
      onDeleteTurn={vi.fn()}
      onDeleteMessage={vi.fn()}
      onSuggestionClick={vi.fn()}
    />);

    fireEvent.click(screen.getByRole('button', { name: '생각하는 과정 표시' }));
    expect(screen.getAllByRole('listitem')).toHaveLength(2);
    expect(screen.getByText('첫째 항목')).toBeTruthy();
    expect(screen.getByText('둘째 항목')).toBeTruthy();
  });
});
