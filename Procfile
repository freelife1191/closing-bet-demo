# 이 경로로 배포하지 않는다. 이 파일은 Flask 만 띄우는데, [INFRA-027] 이후 신원 확정은
# Next 의 proxy.ts 가 맡는다. proxy 가 없으면 X-Auth-Identity 를 붙이는 자리가 없어 모든
# 요청이 익명이 되고, 동시에 Flask 가 라우터를 통해 인터넷에 직접 노출된다. 다른 자리는
# [INFRA-039] 가 loopback 으로 좁혔지만 여기만 그럴 수 없는 것도 그 노출 때문이다.
# 이 파일의 처리는 [INFRA-046] 이다.
web: gunicorn flask_app:app --bind 0.0.0.0:$PORT --workers 2 --threads 8 --timeout 120
