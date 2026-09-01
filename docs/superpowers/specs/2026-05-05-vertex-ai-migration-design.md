# Vertex AI 전환 설계

작성일: 2026-05-05
상태: 승인 대기

## 1. 배경

현재 이 프로젝트는 Google AI Studio의 API Key 방식으로 Gemini를 호출한다. AI Studio는 Google Cloud 결제 계정과 분리되어 있어 GCP 무료 크레딧·기존 GCP 약정 할인을 사용할 수 없다. Vertex AI로 전환하면 GCP 결제 체계를 그대로 활용할 수 있고 IAM·VPC·감사 로그 등 엔터프라이즈 기능도 함께 얻는다.

기존 코드는 이미 신규 `google-genai` SDK(`from google import genai`)를 사용하고 있어, SDK 교체가 아닌 **Client 초기화 방식 변경**만으로 전환이 가능하다.

## 2. 목표

- AI Studio API Key 의존 완전 제거
- `google-genai` SDK의 Vertex AI 모드(`vertexai=True`)로 일원화
- 인증을 서비스 계정 JSON 키 방식으로 통일
- Gemini 3 / 3.1 프리뷰 모델을 메인으로, 2.5 안정 모델은 폴백으로만 사용
- 기존 호출부(`generate_content` 등)는 변경 없음

## 3. 비목표

- 호환 모드(API Key 폴백) 제공하지 않는다 — Vertex AI 단일 경로
- 다른 LLM 프로바이더(Z.ai, Perplexity 등) 변경 없음
- 모델 호출 인터페이스(프롬프트 구성, retry 로직) 변경 없음

## 4. GCP 자원

기존 자원 재사용 (이미 구성됨):

- 프로젝트: `midyear-data-492623-q2`
- 서비스 계정: `vertex-ai-runtime@midyear-data-492623-q2.iam.gserviceaccount.com`
- IAM 권한: `roles/aiplatform.user`, `roles/monitoring.viewer`
- API: `aiplatform.googleapis.com` 활성화됨

신규 작업:

- 이 프로젝트 전용 서비스 계정 키 1개 발급 (기존 키와 독립 회전 가능하도록)
- 키 파일은 `secrets/vertex-ai-runtime.json`에 저장
- `secrets/`를 `.gitignore`에 추가

## 5. 인증 방식

서비스 계정 JSON 파일을 `GOOGLE_APPLICATION_CREDENTIALS` 환경변수로 지정한다 (Application Default Credentials 표준 경로). `genai.Client(vertexai=True, ...)`는 이 환경변수를 자동 인식한다.

코드에서 키 파일 경로를 직접 읽지 않는다 — ADC 표준에 위임.

## 6. 리전

`global` (Vertex AI 멀티리전 엔드포인트). 신규 프리뷰 모델 가용성이 가장 높고 리전 락인이 없다.

## 7. 모델 전략

### 7.1 메인 모델 (프리뷰, 우선)

체인 순서대로 시도:

1. `gemini-3.1-flash-lite-preview` — 경량/저비용
2. `gemini-3-flash-preview` — 표준 Flash (기본)
3. `gemini-3.1-pro-preview` — 고품질

### 7.2 폴백 모델 (안정, 메인 전체 실패 시)

4. `gemini-2.5-flash`
5. `gemini-2.5-pro`

### 7.3 용도별 기본값 분리

```bash
GEMINI_MODEL=gemini-3.1-flash-lite-preview   # 배치 사전 분석 (대량/단순) - engine/llm_analyzer.py
ANALYSIS_GEMINI_MODEL=gemini-3-flash-preview  # Phase 3 LLM 분석 (의미 합성)
VCP_GEMINI_MODEL=gemini-3-flash-preview       # VCP 시그널 생성
```

근거: `GEMINI_MODEL`은 가장 호출량이 많은 사전 분석 경로에서 사용되므로 lite로 비용을 줄이고, 품질 핵심 경로(분석/시그널)는 표준 flash를 유지해 추론 품질을 보호한다.

### 7.4 폴백 체인 정의 위치

두 군데 하드코딩 리스트를 동일하게 갱신:

- `engine/llm_analyzer_retry.py` `_FALLBACK_GEMINI_MODELS`
- `engine/vcp_ai_analyzer.py` (44~47행)

```python
_FALLBACK_GEMINI_MODELS = [
    "gemini-3.1-flash-lite-preview",
    "gemini-3-flash-preview",
    "gemini-3.1-pro-preview",
    "gemini-2.5-flash",
    "gemini-2.5-pro",
]
```

## 8. 환경 변수

### 8.1 제거

- `GOOGLE_API_KEY`
- `GEMINI_API_KEY` (있다면)

### 8.2 추가

```bash
GOOGLE_GENAI_USE_VERTEXAI=true
GOOGLE_CLOUD_PROJECT=midyear-data-492623-q2
GOOGLE_CLOUD_LOCATION=global
GOOGLE_APPLICATION_CREDENTIALS=./secrets/vertex-ai-runtime.json
```

### 8.3 변경

- `GEMINI_MODEL` → `gemini-3.1-flash-lite-preview` (기본값)
- `ANALYSIS_GEMINI_MODEL` → `gemini-3-flash-preview` (기본값)
- `VCP_GEMINI_MODEL` → `gemini-3-flash-preview` (기본값)

## 9. 코드 변경

### 9.1 신규 파일: `engine/genai_client.py`

단일 책임: Vertex 모드 `genai.Client` 팩토리. project/location 환경변수 검증 포함. Vertex 모드가 아닌 경우 명시적으로 실패한다 (silent fallback 없음).

```python
def create_genai_client():
    use_vertex = os.getenv("GOOGLE_GENAI_USE_VERTEXAI", "").lower() == "true"
    if not use_vertex:
        raise RuntimeError(
            "GOOGLE_GENAI_USE_VERTEXAI=true가 필요합니다. "
            "API Key 방식은 더 이상 지원하지 않습니다."
        )
    project = os.environ.get("GOOGLE_CLOUD_PROJECT")
    location = os.environ.get("GOOGLE_CLOUD_LOCATION", "global")
    if not project:
        raise RuntimeError("GOOGLE_CLOUD_PROJECT가 필요합니다.")
    return genai.Client(vertexai=True, project=project, location=location)
```

### 9.2 수정 파일

| 파일 | 변경 |
|---|---|
| `engine/vcp_ai_provider_init_helpers.py` | `GOOGLE_API_KEY` 검증 제거 → `create_genai_client()` 호출로 교체 |
| `chatbot/runtime_setup_service.py` | `api_key` 파라미터/검증 제거 → `create_genai_client()` 호출로 교체 |
| `chatbot/core.py` | `genai.configure(api_key=...)` 호출 제거 (Vertex 모드에서 무의미) |
| `config.py` | `GOOGLE_API_KEY` 필드 제거, `GOOGLE_CLOUD_PROJECT`/`GOOGLE_CLOUD_LOCATION` 추가, 모델 기본값 갱신 |
| `engine/config.py` | 모델 기본값 갱신 (`GEMINI_MODEL`, `ANALYSIS_GEMINI_MODEL`, `VCP_GEMINI_MODEL`) |
| `engine/llm_analyzer_retry.py` | `_FALLBACK_GEMINI_MODELS` 체인 교체 |
| `engine/vcp_ai_analyzer.py` | 동일 모델 체인(44~47행) 교체 |
| `.env`, `.env.example` | 변수 변경 |
| `.gitignore` | `secrets/` 추가 |

### 9.3 호출부 (변경 없음)

- `engine/llm_analyzer.py:304` — `self._client.models.generate_content(...)` Vertex 모드에서도 동일 동작
- 기타 `generate_content` 호출 모두 인터페이스 변경 없음

### 9.4 requirements.txt

- `google-genai`: 유지 (Vertex 내장 지원)
- `requirements.updated.txt`의 `google-generativeai==0.8.6`: 사용처 점검 후 미사용 시 제거

## 10. 검증

### 10.1 단위 검증

```python
from engine.genai_client import create_genai_client
client = create_genai_client()
resp = client.models.generate_content(
    model="gemini-3-flash-preview",
    contents="안녕"
)
print(resp.text)
```

### 10.2 통합 검증

1. `python flask_app.py` 기동
2. 챗봇 엔드포인트 1회 호출 → 정상 응답
3. VCP 시그널 생성 1회 호출 → 정상 응답
4. GCP 콘솔 → Vertex AI → Metrics에서 호출 카운트 증가 확인

### 10.3 잔존 참조 점검

```bash
grep -rn "GOOGLE_API_KEY\|GEMINI_API_KEY" --include="*.py" --include="*.env*"
```

코드/설정에 잔존 참조 없음을 확인.

## 11. 마이그레이션 안전장치

- `.env`를 `.env.bak`로 백업한 뒤 변경
- `secrets/` 디렉터리는 `.gitignore`로 보호하고, `git status`로 키 파일이 추적되지 않는지 변경 직후 확인
- 모델 체인 변경 후 1차 호출에서 프리뷰 모델 화이트리스트 미적용이 발견되면 즉시 폴백 모델(2.5)로 임시 전환 가능

## 12. 롤백

전환 후 문제가 발견되면:

1. `.env`를 `.env.bak`에서 복원
2. `git revert <commit>` 으로 코드 변경 되돌림
3. 즉시 AI Studio 모드 복귀

## 13. 영향 받지 않는 영역

- Z.ai (GPT 호환) 호출 경로
- Perplexity 호출 경로
- 데이터 소스(pykrx, FDR, yfinance)
- Flask 라우트 / Next.js 프론트엔드 / 스케줄러 로직
