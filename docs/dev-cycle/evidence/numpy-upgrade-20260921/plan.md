# NumPy Upgrade Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: superpowers:executing-plans. Parent implements, independent reviewers.

**Goal:** INFRA-018 NumPy2/pykrx상한동시해소.
**Architecture:** 공용JSONEncoder와기존API유지, alias삭제와2핀동반승격. 정본편집은develop원작업트리, 실행은복사한scratch만사용.
**Tech Stack:** Python3.11.16, NumPy2.4.6, pykrx1.2.7, pandas2.3.3, pytest, Next/Vitest/ego.
**Spec:** design.md

## Global Constraints

원본venv/.env/data/logs/3500/5501/live 변경·제품실행금지. 원본package.json보존. 실제KRX로그인·수집/LLM/거래/설정저장금지.
stdlib downloader는공식PyPI/파일호스트만HTTPS로읽어wheel해시를검증한다. pip설치와제품검사sandbox는외부네트워크전부거부(웹QA의소유loopback만허용). 환경은PATH/HOME/USER/LANG/TMPDIR allowlist, PYTHON_DOTENV_DISABLED=1; KRX_ID/KRX_PW 및모든인증변수미전달.
사용자승인판단위임. 한연속목표의소유Space20/p1을taskSpace(20)으로재사용; 소유권agent아니면중단. finish는목표마지막에한번만호출.
명령최대300초, 리뷰15분, QA5cycles/동일실패3회. 안전한의존성설치불가면제품완료처리하지않음.

## Review Focus

- clonedvenv의sys.prefix, numpy/pip.__file__ 모두소유venv안인지실측; bin activate/pip/pytest스크립트실행금지, 항상소유python -m모듈사용.
- 전체requirements와pipcheck를검증하여Flask/pytest가없는환경으로부분성공을주장하지않음.
- float16/32/64/int/bool/array/date/datetime/Timestamp의정확한JSON.
- 실제pykrx 고수준함수+DataFrame변환은유지; Post.read/메타이름·ISIN경계만합성대역. 외부요청시즉시실패.
- KRX실서버/로그인변경은오프라인검증으로증명하지않음.

## Task 1: 고정된 격리 설치

Files: evidence/numpy-upgrade-20260921/setup.py, install.py, review-input.json.

- [ ] git archive 현재HEAD로고유temp scratch생성. 원본.env/data는복사하지않음. 현재미커밋대상source가있으면범위명시복사.
- [ ] 전체baseline의존성이있는원본venv를APFS cp -cR로소유scratch/venv에복제한다(심볼릭링크로공유하지않음). site-packages 실제경로가복제경로아래임을확인.
- [ ] `<scratch>/venv/bin/python -c`로sys.prefix, numpy.__file__, pip.__file__을JSON기록하고모두소유경로인지assert. 원본작업트리write를OSsandbox로금지. clone안의pip/pytest실행스크립트는쓰지않음.
- [ ] scratch의전체requirements.txt에서2핀만후보로바꾸고download_wheels.py가고정된공식PyPI2개wheel을호스트·SHA검증하여소유wheelhouse에저장한뒤아래명령으로전체요구를확인/설치. 나머지직접핀은동일하고설치된transitive를불필요하게upgrade하지않는다.
```text
<owned-python> -m pip install --only-binary=:all: --no-cache-dir --no-index --find-links <scratch>/wheelhouse -r <scratch>/requirements.txt
<owned-python> -m pip check
```
PIP_CONFIG_FILE=/dev/null, PIP_DISABLE_PIP_VERSION_CHECK=1. wheel이없거나설치/검사가실패하면중단·원인기록. 루트venv는읽기전용으로유지.
- [ ] importlib.metadata의numpy/pykrxversion,Requires-Python/Requires-Dist와pipcheck결과기록. metadata만으로실측성공주장금지.

## Task 2: Encoder RED→GREEN과정본수정

Files: numpy_json_encoder.py, requirements.txt, tests/test_numpy_encoder_compat.py.

- [ ] 영구테스트를원작업트리에먼저작성하고scratch로복사. 기존encoder를새NumPy2환경에서실행하여np.float_ AttributeError RED확인.
```python
payload = {
 'f16': np.float16(1.5), 'f32': np.float32(2.5), 'f64': np.float64(3.5),
 'integer': np.int64(7), 'boolean': np.bool_(True), 'array': np.array([1, 2]),
 'date': date(2026, 9, 21), 'time': datetime(2026, 9, 21, 1, 2, 3),
 'stamp': pd.Timestamp('2026-09-21T04:05:06'),
}
assert json.loads(json.dumps(payload, cls=NumpyEncoder)) == {
 'f16': 1.5, 'f32': 2.5, 'f64': 3.5, 'integer': 7, 'boolean': True,
 'array': [1, 2], 'date': '2026-09-21', 'time': '2026-09-21T01:02:03',
 'stamp': '2026-09-21T04:05:06',
}
```
Run: `<owned-python> -m pytest -q tests/test_numpy_encoder_compat.py`.
- [ ] 원작업트리encoder의np.float_참조만삭제하고requirements두핀·주석동시갱신. 두수정파일을scratch에다시복사, 설치version과최종핀동일확인 후targetGREEN.
- [ ] 새환경에서 `<owned-python> -m pytest -q -ra` 전체실행. Frontend는복제node_modules로 `(cd <scratch>/frontend && npx vitest run)`, npm run type-check/lint/test:build.

## Task 3: 실제 pykrx 오프라인 계약

File: tests/engine/test_pykrx_numpy2_contract.py (새pytest회귀). 실제stock.*함수를대체하지않음.

- [ ] import 전 `requests.sessions.Session.request`를AssertionError를던지는함수로patch하고OSsandbox네트워크전부차단. 정제환경에KRX_ID/PW없음확인. 실제pykrx1.2.7을import.
- [ ] `pykrx.website.comm.webio.Post.read`만아래대역으로교체한다. KRX 공식응답을축소한합성값이며실제외부요청없음.
```python
seen = []
def fake_post(self, **params):
    seen.append(dict(params))
    return SimpleNamespace(json=lambda: fixtures[params['bld'].rsplit('/', 1)[-1]])
monkeypatch.setattr('pykrx.website.comm.webio.Post.read', fake_post)
```
- [ ] 실제설치소스의wrap 메타조회심볼을확인하고 `pykrx.website.krx.market.wrap.get_stock_ticker_isin`을합성ISIN으로, `pykrx.stock.stock_api.get_index_ticker_name`을합성이름으로대체. 태그소스와심볼이다르면실행하지말고설치소스를읽어차이를기록·계획수정. silent monkeypatch raising=False 금지.

| 공개호출 | fixture envelope / 행 | assertion |
|---|---|---|
| stock.get_market_ohlcv_by_ticker('20260102','ALL') | MDCSTAT01501 / OutBlock_1: ISU_SRT_CD=005930,TDD_OPNPRC=70000,TDD_HGPRC=72000,TDD_LWPRC=69000,TDD_CLSPRC=71000,ACC_TRDVOL=1000,ACC_TRDVAL=71000000,FLUC_RT=1.43,MKTCAP=1000000000 (숫자는문자열) | index005930,종가71000,거래량1000,mktId=ALL,trdDd=20260102,bldsuffix01501 |
| stock.get_market_fundamental_by_ticker('20260102','ALL') | MDCSTAT03501 / output: ISU_SRT_CD=005930,BPS=10000,PER=10,PBR=1,EPS=1000,DVD_YLD=2,DPS=500 | index005930,EPS1000,PER10,DIV2,요청날짜/시장 |
| stock.get_market_net_purchases_of_equities_by_ticker('20260102','20260102','ALL','외국인') | MDCSTAT02401 / output: ISU_SRT_CD=005930,ISU_NM=합성,ASK_TRDVOL=1000,BID_TRDVOL=2000,NETBID_TRDVOL=1000,ASK_TRDVAL=70000000,BID_TRDVAL=140000000,NETBID_TRDVAL=70000000 | index005930,순매수거래량1000,순매수거래대금70000000,날짜·투자자요청인자 |
| stock.get_index_ohlcv_by_date('20260102','20260102','1001') | MDCSTAT00301 / output: TRD_DD=2026/01/02,OPNPRC_IDX=2500,HGPRC_IDX=2600,LWPRC_IDX=2400,CLSPRC_IDX=2550,ACC_TRDVOL=1000,ACC_TRDVAL=1000000,MKTCAP=10000000 | datetime index2026-01-02,종가2550,indIdx=1,indIdx2=001 |
| stock.get_nearest_business_day_in_a_week('20260103') | 같은00301응답 | 반환20260102,지수1001요청확인 |

- [ ] unexpectedbld/HTTP는KeyError/AssertionError로실패. 빈/잘못된가격·수급과프로젝트fallback은기존collector/pricefetcher전체테스트를유지해보완.
Run: `<owned-python> -m pytest -q tests/engine/test_pykrx_numpy2_contract.py`.

## Task 4: 리뷰·실제 UI QA·마감

- [ ] ponytail→code-review/architect→T3심층. 후보환경·diff/hash·wheelmetadata·테스트실행을증거에고정.
- [ ] QA행렬과정적통과후제품·테스트·행렬첫커밋(TODO유지).
- [ ] 새NumPy환경Flask fixture57982, Next57981(API_URL=57982), gateway57980을소유sandbox로띄운다. 원본포트사용금지, bind전점유확인. 기존evidence/infra-read-boundaries-20260921/serve.py/gateway.py수명주기방식을적용하고새경로/포트를명시변경.
- [ ] `GET /api/kr/signals`와`/api/kr/ai-analysis`, 합성`POST /api/kr/realtime-prices`는NumpyEncoder로직접직렬화한다. ticker005930/name배열검증, np.int64 price71000, np.float32 score85/confidence75, date=datetime2026-09-21. 원본데이터·실제모델없이합성응답만제공.
- [ ] taskSpace(20).page('p1')에서 http://127.0.0.1:57980/dashboard/kr/vcp 열기→종목클릭→3탭75%·가격71,000·점수85·날짜정상 확인. JSON500/HTML응답없음,HTTP200,console/pageerrors0을확인. backend API값과DOM·스크린샷을함께보존/직접열람.
- [ ] PID/cwd/PGID검증후소유3서버만종료,포트닫힘·scratch/venv삭제·원본package/venv버전불변증거. Space20은마지막관련라운드일때finish({keep:[]})단한번,후속라운드가있으면about:blank에명시유지.
- [ ] 필수전체통과후에만INFRA018제거/아카이브. 원본venv/실서비스미적용,실제KRX서버행동미검증을명시.

실측 설치 조정: macOS sandbox는literalIP필터/DNS가제약돼직접pip온라인설치2회는설치전실패. stdlib downloader가공식PyPI2개wheel을허용호스트/sha256검증으로확보한뒤pip --no-index --find-links wheelhouse로정상네트워크차단sandbox에서설치. 전체requirements와pipcheck통과.
실제설치소스에서이름조회소유자는stock_api.get_index_ticker_name으로확인했고대체했다. 일별수급API(MDCSTAT02302)도추가검사했다. 테스트는clean subprocess로기존suite의sys.modules대역/인증env를격리한다.
