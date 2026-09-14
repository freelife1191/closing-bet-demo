# S-3 하네스 진단

## architect 메시지 원문
원인분류 권고: `HARNESS/RENDER-LIFECYCLE`, 제품 FAIL 아님. fast에서 mq.matches/innerWidth만 CDP metrics로 바뀌고 MQL change·resize·rAF가 전부 0인 채 DOM state=true면 브라우저가 update-the-rendering/event dispatch 단계를 수행하지 않은 것. 앱은 이벤트 기반이라 setFalse 기회가 없음(page:197-207). slow에서 동일 코드로 change true/false와 drawer close가 발생하므로 React/capture 원인 반증. S3는 (1) desktop set 후 독립 observer가 `change:true` 또는 resize를 받았음을 prerequisite로 기록, (2) 그 뒤 drawer DOM absent를 확인, (3) mobile 복귀 후 absent 유지로 판정. prerequisite timeout이면 해당 iteration을 harness-inconclusive로 버리고 visible/foreground fresh session 또는 paced command로 재시도. fast 재현은 browser automation stress 증거로 보존하되 제품 실패 1회에 합산하지 않는 것이 맞음. polling/resize fallback을 제품에 추가하면 렌더프레임이 멈춘 harness를 위한 복잡성일 뿐이며 실제 해결도 보장하지 않음.

## 실행자 명령 순서 원문
원본 S3는 하나의 `&&` 셸 체인이었고, 명령 사이 `sleep`/`wait`/request wait는 **전혀 없었습니다**. 정확한 순서: `qa2-s3-desktop: set viewport 1280 720` → snapshot → `qa2-s3-desktop-mobile: set viewport 375 812` → snapshot → `qa2-s3-mobile-open: click @e12` → snapshot → `qa2-s3-mobile-desktop: set viewport 1280 720` → snapshot → `qa2-s3-mobile-desktop-mobile: set viewport 375 812` → `qa2-s3-final-snapshot`. 파일 시각(KST)은 desktop 13:05:14, 첫 mobile·open·desktop snapshot 13:05:15, 최종 mobile 및 final snapshot 13:05:16입니다. 즉 desktop→mobile 재복귀가 같은 초 내에 snapshot completion만 사이에 두고 일어났고 안정화 대기는 없었습니다. 이 coalescing 가능성은 당시 실행에 존재합니다.

## 부모의 최종 관측
앱 소스를 바꾸지 않고 agent-browser headed 재기동. qa3-frame true, qa3-desktop-state에서MQL true/DOM false, qa3-return-state에서MQL false/DOM false. qa3-return.png 직접 열람. 정확한 browser 내부 원인은 단정하지 않고 전달 전제 확인으로 제품 계약을 검증했다.
