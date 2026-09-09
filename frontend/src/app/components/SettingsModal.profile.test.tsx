import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';

import SettingsModal from './SettingsModal';

vi.mock('next-auth/react', () => ({
  useSession: () => ({ data: null, status: 'unauthenticated' }),
  signIn: vi.fn(),
  signOut: vi.fn(),
}));
vi.mock('next/navigation', () => ({ useRouter: () => ({ refresh: vi.fn(), push: vi.fn() }) }));
vi.mock('@/hooks/useAdmin', () => ({ useAdmin: () => ({ isAdmin: false, isLoading: false }) }));
vi.mock('@/lib/session', () => ({ getBrowserSessionId: () => 'profile-test' }));

const renderModal = (persona: string, onSave = vi.fn(async () => {}), isOpen = true) => {
  return render(
    <SettingsModal
      isOpen={isOpen}
      onClose={() => {}}
      profile={{ name: '테스터', email: 'tester@example.com', persona }}
      onSave={onSave}
    />
  );
};

describe('[FE-039] 저장된 직무 / 역할 표시', () => {
  it('목록 밖 페르소나는 직접 입력으로 보이고 저장 시 원문을 유지한다', async () => {
    const persona = '주식 투자를 배우고 있는 열정적인 투자자';
    const onSave = vi.fn(async () => {});
    const view = renderModal(persona, onSave);

    const roleSelect = document.querySelector('select') as HTMLSelectElement;
    expect(roleSelect.value).toBe('직접 입력');
    expect((screen.getByPlaceholderText('직무를 직접 입력하세요') as HTMLInputElement).value).toBe(persona);

    fireEvent.change(screen.getByDisplayValue('테스터'), { target: { value: '바뀐 이름' } });
    fireEvent.click(screen.getByRole('button', { name: '저장' }));
    await waitFor(() => expect(onSave).toHaveBeenCalled());
    expect(onSave).toHaveBeenCalledWith('바뀐 이름', 'tester@example.com', persona);

    fireEvent.change(screen.getByPlaceholderText('직무를 직접 입력하세요'), { target: { value: '임시 변경' } });
    view.rerender(
      <SettingsModal isOpen={false} onClose={() => {}}
        profile={{ name: '테스터', email: 'tester@example.com', persona }} onSave={onSave} />
    );
    view.rerender(
      <SettingsModal isOpen onClose={() => {}}
        profile={{ name: '테스터', email: 'tester@example.com', persona }} onSave={onSave} />
    );
    expect((screen.getByPlaceholderText('직무를 직접 입력하세요') as HTMLInputElement).value).toBe(persona);
  });

  it('목록 안 역할 선택은 페르소나로 저장되고 다시 열 때 유지된다', async () => {
    const onSave = vi.fn(async () => {});
    renderModal('', onSave);

    fireEvent.change(document.querySelector('select') as HTMLSelectElement, { target: { value: '리서치' } });
    fireEvent.click(screen.getByRole('button', { name: '저장' }));
    await waitFor(() => expect(onSave).toHaveBeenCalledWith('테스터', 'tester@example.com', '리서치'));

    const view = renderModal('리서치');
    view.rerender(
      <SettingsModal isOpen={false} onClose={() => {}}
        profile={{ name: '테스터', email: 'tester@example.com', persona: '리서치' }} onSave={onSave} />
    );
    view.rerender(
      <SettingsModal isOpen onClose={() => {}}
        profile={{ name: '테스터', email: 'tester@example.com', persona: '리서치' }} onSave={onSave} />
    );

    expect((document.querySelector('select') as HTMLSelectElement).value).toBe('리서치');
    expect(screen.queryByPlaceholderText('직무를 직접 입력하세요')).toBeNull();
  });

  it('custom role이 known role 접두어를 지나도 입력 상태를 유지한다', async () => {
    const onSave = vi.fn(async () => {});
    renderModal('', onSave);
    const input = screen.getByPlaceholderText('직무를 직접 입력하세요');

    for (const value of ['리', '리서치', '리서치 분석가']) {
      fireEvent.change(input, { target: { value } });
      expect((screen.getByPlaceholderText('직무를 직접 입력하세요') as HTMLInputElement).value).toBe(value);
      expect((document.querySelector('select') as HTMLSelectElement).value).toBe('직접 입력');
    }

    fireEvent.click(screen.getByRole('button', { name: '저장' }));
    await waitFor(() => expect(onSave).toHaveBeenCalledWith('테스터', 'tester@example.com', '리서치 분석가'));
  });
});
