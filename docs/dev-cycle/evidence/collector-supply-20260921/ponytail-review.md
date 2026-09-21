engine/collectors/krx_local_data_mixin.py:L736-855 (+ engine/collectors/krx.py:L54-60, tests/engine/test_collectors_refactor.py:L1230-1246,L1306-1307): delete: Naver가 자체 NaverPykrxMixin 캐시를 사용한 뒤 호출자가 사라진 KRX 펀더멘털 캐시 전체와 무효한 테스트 설정. 아무것도 대체하지 않는다.

engine/collectors/krx.py:L19,L76-84: yagni: 기존 BaseCollector의 생성자·비동기 컨텍스트 계약을 다시 구현한다. BaseCollector 상속과 super().__init__(config)로 복귀하고 종목명 캐시 초기화만 남긴다.

net: -145 lines possible.

조치: 두 지적 모두 반영. 실사용 Naver 캐시/회귀 단언은 보존.
