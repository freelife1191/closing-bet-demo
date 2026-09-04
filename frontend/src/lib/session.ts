// 로그인하지 않은 사용자의 사용량을 세는 기준이 되는 브라우저 세션 ID.
//
// `crypto.randomUUID` 는 보안 컨텍스트(https 또는 localhost)에서만 존재한다. 사내망
// http 주소로 열면 없으므로 폴백이 필요하다.
// ponytail: 폴백 값은 충돌할 수 있다. 비보안 컨텍스트 접속이 실제로 많아지면 서버가
// 발급하는 방식으로 올린다.
export function getBrowserSessionId(): string {
  const stored = readStored();
  if (stored) return stored;

  const random =
    typeof crypto !== 'undefined' && crypto.randomUUID
      ? crypto.randomUUID()
      : Math.random().toString(36).substring(2) + Date.now().toString(36);

  const sessionId = 'anon_' + random;
  try {
    localStorage.setItem('browser_session_id', sessionId);
  } catch (e) {
    // 저장 공간이 꽉 찼거나 저장을 막아 둔 브라우저. 이 호출 동안만 쓰는 값이 되어
    // 사용량 집계가 방문마다 갈리지만, 화면 전체가 무너지는 것보다는 낫다.
  }
  return sessionId;
}

function readStored(): string | null {
  try {
    return localStorage.getItem('browser_session_id');
  } catch (e) {
    return null;
  }
}
