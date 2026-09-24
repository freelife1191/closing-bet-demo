# Shared runtime state
STOP_REQUESTED = False
# [INFRA-097] 이 워커에서 마지막으로 시작한 수동 업데이트의 startTime
LOCAL_RUN_START_TIME = None
# [INFRA-099] 이 워커에서 수동 업데이트 파이프라인이 도는 중인지. 도는 동안 이 워커는 새 시작을 받지 않는다
LOCAL_PIPELINE_ACTIVE = False
