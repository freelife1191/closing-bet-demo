import { render, screen, within } from '@testing-library/react';
import { describe, expect, it } from 'vitest';
import ClosingBetCriteriaModal from './ClosingBetCriteriaModal';

describe('종가베팅 가격 기준 안내', () => {
  it('기본 폭과 개별 저장 가격 우선 원칙을 같은 모달에서 설명한다', () => {
    render(<ClosingBetCriteriaModal isOpen onClose={() => {}} />);
    const modal = screen.getByRole('dialog');
    expect(within(modal).getByText('+5%')).toBeTruthy();
    expect(within(modal).getByText('-3%')).toBeTruthy();
    expect(within(modal).getByText(/저장된 목표가·손절가를 우선/)).toBeTruthy();
  });
});
