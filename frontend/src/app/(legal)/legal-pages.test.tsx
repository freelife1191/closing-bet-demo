import { render, screen } from '@testing-library/react';
import { describe, expect, it } from 'vitest';

import PrivacyPage, { metadata as privacyMetadata } from './privacy/page';
import TermsPage, { metadata as termsMetadata } from './terms/page';
import HomePage from '../page';

const CONTACT_EMAIL = 'freeopen1191@gmail.com';
const OPERATOR = 'Smart Money Bot 운영자';

// 법적 고지는 조항이 하나만 빠져도 문서로서 구실을 못 하므로 제목을 값으로 고정한다.
const PRIVACY_SECTIONS = [
  '1. 수집하는 개인정보 항목과 수집 방법',
  '2. 개인정보의 처리 목적',
  '3. 개인정보의 보유 및 이용 기간',
  '4. 개인정보의 제3자 제공',
  '5. 개인정보 처리의 위탁과 국외 이전',
  // 6·7 은 개인정보 보호법 제30조 제1항 제7호와 제22조의2 가 요구하는 자리다.
  '6. 쿠키와 브라우저 저장소의 운영과 거부 방법',
  '7. 만 14세 미만 아동의 개인정보',
  '8. 정보주체의 권리와 행사 방법',
  '9. 개인정보의 파기 절차와 방법',
  '10. 개인정보의 안전성 확보 조치',
  '11. 개인정보 보호책임자와 문의처',
  '12. 방침의 변경',
];

const TERMS_SECTIONS = [
  '제1조 (목적)',
  '제2조 (용어의 정의)',
  '제3조 (약관의 효력과 변경)',
  '제4조 (서비스의 내용)',
  '제5조 (계정의 생성과 관리)',
  '제6조 (이용자의 의무)',
  '제7조 (투자 정보의 성격과 면책)',
  '제8조 (데이터의 정확성과 면책)',
  '제9조 (서비스 제공의 중단)',
  '제10조 (이용 계약의 해지)',
  '제11조 (준거법과 관할)',
];

describe('개인정보처리방침', () => {
  it('필수 조항을 모두 담는다', () => {
    render(<PrivacyPage />);
    for (const section of PRIVACY_SECTIONS) {
      screen.getByRole('heading', { name: section });
    }
  });

  it('운영자 표기와 문의 이메일, 시행일을 밝힌다', () => {
    const { container } = render(<PrivacyPage />);
    expect(container.textContent).toContain(OPERATOR);
    expect(container.textContent).toContain(CONTACT_EMAIL);
    expect(container.textContent).toMatch(/시행일[^\n]*\d{4}년 \d{1,2}월 \d{1,2}일/);
  });

  it('실제로 저장하는 항목과 보관 기간을 사실대로 적는다', () => {
    const { container } = render(<PrivacyPage />);
    const text = container.textContent ?? '';
    // services/activity_logger.py 는 회전 파일을 마지막 수정 시각 기준
    // ACTIVITY_LOG_RETENTION_DAYS(30) 일로 지운다. 챗봇 블루프린트를 등록할 때 전역 로거가
    // 만들어지므로 기동 때 한 번, 그 뒤로는 자정 뒤 첫 기록(회전) 때 지운다. 삭제가 늦어지는
    // 경우까지 사실대로 적는지 고정한다.
    expect(text).toContain('마지막 기록 후 30일이 지난 파일');
    expect(text).toContain('서버를 다시 시작할 때와 날짜가 바뀐 뒤 처음 기록을 남길 때');
    expect(text).toContain('접속과 서버 재시작이 모두 없는 기간에는 그 기간만큼 삭제가 늦어집니다');
    // 10항의 권한 제한: DB 파일은 0600, 로그는 restart_all.sh 가 logs/ 를 0700 으로 좁힌다.
    expect(text).toContain('로그 파일과 데이터베이스 파일은 서버를 실행하는 계정만 읽고 쓸 수 있도록');
    // 이용을 멈추는 것만으로는 기록이 지워지지 않는다는 사실을 밝힌다.
    expect(text).toContain('이미 저장된 기록이 지워지지 않습니다');
    // 챗봇 대화가 활동 로그에도 남는다는 사실을 감추지 않는다.
    expect(text).toContain('질문과 챗봇의 답변이 각각 앞 2000자까지');
    // 국외 이전 표의 행을 지우면 실패하도록 이전 국가까지 함께 고정한다.
    expect(text).toContain('Google LLC');
    expect(text).toContain('OpenAI, L.L.C.');
    expect(text).not.toContain('Perplexity');
    expect(text).toContain('이전 국가: 미국');
    expect(text).toContain('이전 국가: 중국');
    // 거부할 수단이 없는 경로를 숨기지 않는다.
    expect(text).toContain('이용자가 개별로 거부할 수단이 없습니다');
  });

  it('브라우저에 저장한 값이 서버로도 간다는 사실을 감추지 않는다', () => {
    // ChatWidget.tsx:231 과 useChatStream.ts:201 이 관심 종목을 채팅 요청마다 실어 보내고,
    // chatHelpers.ts 의 saveUserProfile 은 서버에 먼저 저장한 뒤 로컬에 복사한다.
    // 「브라우저에만 남는다」고 적으면 수집 범위를 실제보다 좁게 알리는 셈이 된다.
    const { container } = render(<PrivacyPage />);
    const text = container.textContent ?? '';
    expect(text).not.toContain('서버로 보내지 않고');
    expect(text).toContain('요청에 함께 실려 서버로');
    expect(text).toContain('설정을 저장할 때 서버에 먼저 기록된 뒤');
    // 국외 이전 표의 Google 행에도 관심 종목이 들어가야 한다.
    expect(text).toContain('이용자가 저장한 메모리와 관심 종목 목록');
  });

  it('서버 데이터를 지우지 않는 「계정 삭제」 버튼의 실제 동작을 밝힌다', () => {
    // SettingsModal.tsx 의 버튼은 localStorage·sessionStorage 만 비우고 로그아웃한다.
    // 화면과 방침이 어긋난 채 공개되지 않도록 고정한다.
    const { container } = render(<PrivacyPage />);
    expect(container.textContent).toContain('서버에 저장된 기록을 지우지 않습니다');
  });

  it('페이지 메타데이터에 제목을 둔다', () => {
    expect(privacyMetadata.title).toContain('개인정보처리방침');
  });
});

describe('서비스 약관', () => {
  it('필수 조항을 모두 담는다', () => {
    render(<TermsPage />);
    for (const section of TERMS_SECTIONS) {
      screen.getByRole('heading', { name: section });
    }
  });

  it('투자 면책과 무상 제공, 모의투자 사실을 밝힌다', () => {
    const { container } = render(<TermsPage />);
    const text = container.textContent ?? '';
    expect(text).toContain('투자자문업자나 투자일임업자로');
    expect(text).toContain('전부 모의투자입니다');
    expect(text).toContain('무료로 제공됩니다');
    expect(text).toContain(CONTACT_EMAIL);
  });

  it('면책 조항에 고의와 중대한 과실의 유보를 남긴다', () => {
    // 「약관의 규제에 관한 법률」 제7조 제1호는 고의·중과실까지 면책하는 조항을 무효로
    // 삼는다. 유보 문구가 사라지면 조항 자체가 효력을 잃으므로 세 자리를 고정한다.
    const { container } = render(<TermsPage />);
    const text = container.textContent ?? '';
    const reservations = text.match(/고의 또는 중대한 과실이 없는 한/g) ?? [];
    expect(reservations.length).toBeGreaterThanOrEqual(3);
    expect(text).not.toContain('어떠한 책임도 지지 않습니다');
  });

  it('페이지 메타데이터에 제목을 둔다', () => {
    expect(termsMetadata.title).toContain('서비스 약관');
  });
});

describe('랜딩 페이지 푸터', () => {
  it('두 문서로 가는 링크를 노출한다', () => {
    render(<HomePage />);
    expect(screen.getByRole('link', { name: '개인정보처리방침' }).getAttribute('href')).toBe('/privacy');
    expect(screen.getByRole('link', { name: '서비스 약관' }).getAttribute('href')).toBe('/terms');
  });
});
