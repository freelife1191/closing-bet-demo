# Independent reviews

## Ponytail / agent_registration_review
Lean already. Ship. net: -0 lines possible. 설치책임을helper로옮기고실패시기동중단. Pythonrequirements검증,Nodefingerprint/hiddenlock/npm ls는변경감지에직접필요. ci후재검증과venvgunicorn직접실행은중복wrapper가아님. 과잉추상화없음.

## Architect / quota_ticker_fixture
CLEAR. Python설치와pipcheck는venv/bin/python만사용. Nodefingerprint에manifest/lock/hiddenlock/Nodeversion/platform/arch포함,npmls실패도복구대상. stamp는ci와검증후기록. 동기화실패시양쪽서버기동전종료. 시스템pip설치/자동gitpull/임의버전업데이트없음. frozen4개일치,표적18·전체2519/3skip증거확인. 리뷰어원본서비스실행없음.

## Code / vcp_real_code
APPROVE. 4paths, CRITICAL/HIGH/MEDIUM/LOW0. 명시적venv install/check,필수파일/tools확인,manifest/lock/hiddenlock/Node환경fingerprint,next+npmls정상시만skip,ci검증뒤stamp. restart는설치실패시서버기동전종료,venvgunicorn사용. 실패fixture/실제scratch반복설치/README일치. 전체2519/3skip,Vitest641,frozen일치. 기존서비스먼저종료하므로설치실패시내려간상태유지하는가용성절충은명시된동작.
