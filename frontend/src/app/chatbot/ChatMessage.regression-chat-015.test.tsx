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
});
