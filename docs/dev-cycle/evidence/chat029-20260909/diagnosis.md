# CHAT-029 검증 진단

- setup zsh 한 readonly문에서 ROOT/R을 정의하고 곧바로참조해 parameter not set. 분리선언으로수정후기동성공.
- wait --text는placeholder를본문문구로찾지못해25초실패. snapshot에서입력존재확인하고후속은CSS/ref상태기다림.
- 첫syntheticSSE가헤더를즉시응답하자중단버튼사라짐. 실제useChatStream은헤더후setIsLoading(false), pageisBusy는isLoading/history만계산한다. 기존CHAT013스트리밍상태결함에해당하며이번label2줄로바뀐동작아님.
- 최초fixture는프레임구분자를문자열escape로보내답변chunk표시도되지않았다. 원문gzip보존후정상개행으로수정.
- S2의이름/중단동작은버튼이존재하는응답대기단계에서검증한다. headers20초지연으로외부응답대기를모사하고실제abort를확인. 응답chunk를받은뒤중단성공으로주장하지않는다. 첫관찰기록은보존.

독립architect(notification_round_map)판정 WATCH: 라벨2줄 범위는유지, headers지연상태에서명시aria+abort경로+종료UI만검증한다. chunk수신후버튼유지/중단을보장하려면CHAT013별도수정이필요. 근거useChatStream122-126(controller),83-90(stop),168-172(headers후loadingfalse),245-254(abort정리),page164(isBusy),1028-1038(button).
최종3회차에실제중단클릭후UI종료성공. 서버완료로그는브라우저abort와별도이며backend중단성공을주장하지않는다.
