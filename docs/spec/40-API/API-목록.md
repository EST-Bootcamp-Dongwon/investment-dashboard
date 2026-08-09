# API 목록

> - **버전**: v2.0
> - **최종 수정**: 2026-08-09 (KST)
> - **상태**: 초안
> - **기준 코드**: `main` @ `f5d770d`
> - **역할**: 서버에 존재하는 **모든** 엔드포인트를 한 장에 세운다.
>   요청·응답 스키마는 [`API-상세명세.md`](API-상세명세.md), 에러·캐시 규약은
>   [`공통-응답과-에러.md`](공통-응답과-에러.md) 에 있다.
> - **관련**: [기능ID-대장](../00-index/기능ID-대장.md) · [변경이력](../00-index/변경이력.md)

---

## 0. 이 문서를 읽는 법

### 측정 방법

이 문서의 51이라는 숫자는 아래 명령의 결과입니다 (2026-08-09 실측).

```bash
grep -rnE '@(app|router)\.(get|post|put|patch|delete|head|options)\(' app/backend --include="*.py"
```

`routers/backtest_lab.py` 만 `APIRouter(prefix="/api/backtest-lab")` 를 쓰므로
(`app/backend/routers/backtest_lab.py:40`), 그 3개는 선언 경로 앞에 접두사를 붙여 세었습니다.
나머지 4개 라우터는 `APIRouter()` 에 전체 경로를 직접 적습니다
(`quant.py:19` · `ml.py:17` · `rag.py:14` · `tax.py:8`).

### 열 읽는 법

| 열 | 뜻 |
| --- | --- |
| **Swagger** | `openapi_docs.py` 의 `FRONTEND_API_PATHS` 화이트리스트에 있는가. **없으면 Swagger UI 에 뜨지 않는다** (필터: `app/backend/openapi_docs.py:152~156`) |
| **호출처** | 프런트엔드에서 실제로 부르는 파일과 줄. `api.js` 바인딩 호출 · 직접 `fetch()` · `apiGet/apiPost/post` 헬퍼를 **모두** 훑은 결과 |
| **등급** | [기능ID-대장](../00-index/기능ID-대장.md) 의 A/B/C·아카이브·폐기 |

---

## 1. 한눈에 보기

| 구분 | 개수 |
| --- | --- |
| **라우트 총계** | **51** |
| ─ `main.py` | 22 |
| ─ `routers/ml.py` | 14 |
| ─ `routers/quant.py` | 6 |
| ─ `routers/backtest_lab.py` | 3 |
| ─ `routers/rag.py` | 3 |
| ─ `routers/tax.py` | 3 |
| **Swagger 에 노출** | 43 |
| **Swagger 누락** | **8** ← [2.1절](#21-swagger-에서-빠진-8개--cn-005-정정) |
| **프런트에서 호출되지 않음** | **4** ← [2.2절](#22-호출되지-않는-4개) |
| 메서드 분포 | POST 40 · GET 11 |

### 1.1 v2.0 에서 달라질 것

| 변화 | 개수 | 근거 |
| --- | --- | --- |
| **삭제** (폐기 X01~X05) | −6 | [기능ID-대장 3절](../00-index/기능ID-대장.md#3-폐기-x01--x05--v20-에서-제거) |
| **신설** (F03 백엔드화) | +4 | [API-상세명세 2절](API-상세명세.md#2-f03-신설-api--포트폴리오-추천-백엔드화) |
| **결과** | 51 → **49** | |

---

## 2. 이번 세션에서 정정한 것

### 2.1 Swagger 에서 빠진 8개 — CN-005 정정

> ⚠ **[CN-005](../00-index/변경이력.md#cn-005) 의 "누락 3건" 은 틀렸습니다.**
> 실제로는 **8건**이고, 목록도 다릅니다.

```
$ python3 -c "라우트 경로 집합 − FRONTEND_API_PATHS"    # 2026-08-09
```

| # | 경로 | 담당 | 등급 | `OPERATION_DOCS` 설명 |
| --- | --- | --- | :---: | --- |
| 1 | `POST /api/market/portfolio-combination` | F04 | **A** | **없음** |
| 2 | `POST /api/quant/portfolio-scenario` | F05 | **A** | **없음** |
| 3 | `POST /api/rag/search` | F27 | **A** | 있음 (`openapi_docs.py:120`) |
| 4 | `POST /api/rag/ask` | F27 | **A** | 있음 (`openapi_docs.py:121`) |
| 5 | `GET /api/rag/status` | F27 | **A** | 있음 (`openapi_docs.py:122`) |
| 6 | `POST /api/quant/financial-knowledge` | F24 | C | 있음 (`openapi_docs.py:110`) |
| 7 | `GET /api/home/kospi-candle` | F01 | B | 있음 (`openapi_docs.py:96`) |
| 8 | `GET /api/home/box-range` | F01 | B | 있음 (`openapi_docs.py:97`) |

**CN-005 가 틀린 지점 둘.**

1. **`/api/backtest-lab/*` 는 누락이 아닙니다.** 커밋 `718f161` 이 라우트와 함께
   화이트리스트·설명을 같이 넣었습니다 (`git show 718f161 -- app/backend/openapi_docs.py`
   → `+6 lines`). CN-005 는 그 커밋 **이전** 상태를 본 것입니다.
2. **RAG 3개가 통째로 빠져 있습니다.** CN-005 는 이걸 잡지 못했습니다.

**이게 왜 중요한가.** A등급 기능 4개 중 **F03 은 백엔드가 아예 없고**,
나머지 **F04·F05·F27 의 엔드포인트가 전부 Swagger 에 없습니다.**
즉 **A등급 4개 중 문서화된 것이 0개**입니다.
[R-08 의 "API 문서화" 축](../00-index/강사님-요구사항-대조표.md#11-r-08-세부--si-수준-판정)이
🔶 로 매겨져 있는데, A등급만 놓고 보면 ❌ 입니다. → [CN-025](../00-index/변경이력.md#cn-025)

**6·7·8 은 성격이 다릅니다.** `OPERATION_DOCS` 에 한국어 설명까지 써 놓고
화이트리스트에만 안 넣어서 필터에서 잘려 나갑니다 (`openapi_docs.py:152~156`).
설명을 쓴 사람은 노출할 의도였다고 보는 게 자연스럽습니다.

### 2.2 호출되지 않는 4개

| 경로 | 담당 | 상태 |
| --- | --- | --- |
| `GET /api/home/kospi-candle` | F01 | 프런트 전수 검색 **0건** |
| `GET /api/home/box-range` | F01 | 프런트 전수 검색 **0건** |
| `POST /api/quant/financial-knowledge` | F24 | 프런트 전수 검색 **0건** |
| `POST /api/rag/search` | F27 | 프런트 전수 검색 **0건** |

`GET /files/{file_name}` 은 `fetch` 로는 안 부르지만 **간접 사용 중**이라 위 표에서 뺐습니다 —
`opencv.js:40` 이 응답의 `video_url` 을 `<video src>` 에 그대로 넣습니다.

> `kospi-candle` · `box-range` 는 **기능ID-대장에도 없던 라우트**입니다.
> 대장 1.1절이 F01 의 백엔드를 `market-candle` + `snapshot` 두 개로 적었는데,
> 실제로는 홈 계열 GET 이 3개입니다. → [CN-026](../00-index/변경이력.md#cn-026)

### 2.3 CN-006 재확인 — 15건 중 14건이 오탐

> ✅ **[CN-006](../00-index/변경이력.md#cn-006) 의 "미사용 바인딩" 목록은 거의 전부 오탐이었습니다.**

CN-006 은 `api.<name>(` 형태의 **정적 호출만** 셌습니다. 실제 호출 경로는 셋입니다.

| 호출 방식 | 예 |
| --- | --- |
| ① `api.<name>(...)` | `views/portfolio.js:36` |
| ② `apiGet` / `apiPost` 헬퍼 | `api.js:5~6` 에 정의. `api` 객체를 거치지 않는다 |
| ③ 뷰 지역 헬퍼 `post()` / 직접 `fetch()` | `pages/backtest-lab.js:231` · `views/ragChat.js:114` |

셋을 모두 훑은 결과:

| 판정 | 개수 | 목록 |
| --- | --- | --- |
| **진짜 미사용** | **1** | `api.financialKnowledge` → `POST /api/quant/financial-knowledge` |
| 오탐 (실제로는 호출됨) | 14 | `health`(`app.js:280`) · `visitorHeartbeat`(`app.js:375`) · `crossValidation`(`crossValidation.js:41`) · `decisionBoundary`(`decisionBoundary.js:20`) · `randomForest`(`randomForest.js:29`) · `kmeans`(`kmeans.js:41`) · `svm`(`svm.js:40`) · `mlp`(`mlp.js:41`) · `linearRegression`(`linearRegression.js:41`) · `opencv`(`opencv.js:39`) · `huggingface`(`huggingface.js:47`) · `dartFinancialAnalysis`(`dartFinancialAnalysis.js:456`) · `taxSample`(`taxAccounting.js:517`) · `taxSimulate`(`taxAccounting.js:571`) |

CN-006 이 이미 의심했던 대로 `financialKnowledge` **하나만** 진짜였습니다.

**반대 방향의 누락도 있습니다.** `api.js` 에 바인딩이 **없는데** 뷰가 직접 부르는 경로가 5개입니다.

| 경로 | 호출처 |
| --- | --- |
| `POST /api/tax/upload` | `taxAccounting.js:501` |
| `POST /api/rag/ask` | `ragChat.js:114` |
| `GET /api/rag/status` | `ragChat.js:79` |
| `GET /api/home/market-candle` | `home.js:130` |
| `GET /api/backtest-lab/config`·`run`·`report` | `pages/backtest-lab.js:249,290,313` |

즉 `api.js` 는 **API 클라이언트의 단일 창구가 아닙니다.** A등급 F27 이 그 밖에 있습니다.
→ [CN-027](../00-index/변경이력.md#cn-027)

---

## 3. 전수 목록 51개

경로 사전순입니다. `등급` 은 기능ID-대장 기준.

| # | M | 경로 | 기능 | 등급 | 핸들러 | Swagger | 프런트 호출처 |
| --- | --- | --- | --- | :---: | --- | :---: | --- |
| 1 | GET | `/api/backtest-lab/config` | F28 | B | `backtest_lab.py:232` | ✅ | `backtest-lab.js:249` |
| 2 | POST | `/api/backtest-lab/report` | F28 | B | `backtest_lab.py:257` | ✅ | `backtest-lab.js:313` |
| 3 | POST | `/api/backtest-lab/run` | F28 | B | `backtest_lab.py:251` | ✅ | `backtest-lab.js:290` |
| 4 | POST | `/api/cv/circle-animation` | X05 | 폐기 | `ml.py:244` | ✅ | `opencv.js:39` |
| 5 | POST | `/api/dart/company-list` | F21 | C | `main.py:539` | ✅ | `dartRegionSearch.js:155` |
| 6 | POST | `/api/dart/company-search` | F20·F23 | B | `main.py:323` | ✅ | `dartCompanySearch.js:95`<br>`dartFinancialAnalysis.js:382` |
| 7 | POST | `/api/dart/financial-analysis` | F23 | B | `main.py:2580` | ✅ | `dartFinancialAnalysis.js:456` |
| 8 | POST | `/api/dart/group-network` | F22 | C | `main.py:389` | ✅ | `groupNetwork.js:127` |
| 9 | POST | `/api/dl/cnn-timeseries` | X01 | 폐기 | `ml.py:572` | ✅ | `cnnTimeseries.js:38` |
| 10 | POST | `/api/dl/lstm-predictor` | X02 | 폐기 | `ml.py:659` | ✅ | `lstm.js:42` |
| 11 | POST | `/api/dl/transformer-timeseries` | X03 | 폐기 | `ml.py:741` | ✅ | `transformer.js:42` |
| 12 | POST | `/api/finance/company-financials` | F17·F20 | B | `main.py:1964` | ✅ | `companyFinancial.js:87`<br>`dartCompanySearch.js:53` |
| 13 | POST | `/api/genai/text-to-image` | X04 | 폐기 | `ml.py:538` | ✅ | `huggingface.js:47` |
| 14 | GET | `/api/health` | F02 | C | `main.py:159` | ✅ | `app.js:280` |
| 15 | GET | `/api/home/box-range` | F01 | B | `main.py:2187` | **❌** | **없음** |
| 16 | GET | `/api/home/kospi-candle` | F01 | B | `main.py:2181` | **❌** | **없음** |
| 17 | GET | `/api/home/market-candle` | F01 | B | `main.py:2125` | ✅ | `home.js:130` |
| 18 | POST | `/api/industry/lifecycle` | F16 | B | `main.py:971` | ✅ | `industryAnalysis.js:602` |
| 19 | POST | `/api/industry/peer` | F16 | B | `main.py:859` | ✅ | `industryAnalysis.js:291` |
| 20 | POST | `/api/industry/porter` | F16 | B | `main.py:626` | ✅ | `industryAnalysis.js:126` |
| 21 | POST | `/api/industry/sector` | F16 | B | `main.py:753` | ✅ | `industryAnalysis.js:514` |
| 22 | POST | `/api/macro/kospi-ex` | F15 | B | `main.py:1589` | ✅ | `kospiExcluded.js:189` |
| 23 | GET | `/api/macro/kospi-ex/meta` | F15 | B | `main.py:1814` | ✅ | `kospiExcluded.js:64` |
| 24 | POST | `/api/macro/realtime` | F13 | B | `main.py:1362` | ✅ | `macroRealtime.js:116` |
| 25 | POST | `/api/macro/simulation` | F14 | B | `main.py:1832` | ✅ | `macroSimulation.js:53` |
| 26 | POST | `/api/market/portfolio-combination` | **F04** | **A** | `main.py:1167` | **❌** | `portfolioCombination.js:257` |
| 27 | POST | `/api/market/snapshot` | F01·F11 | B | `main.py:1246` | ✅ | `app.js:318`<br>`home.js:204`<br>`worldMarkets.js:104` |
| 28 | GET | `/api/market/volume-cloud` | F10 | C | `main.py:1302` | ✅ | `volumeCloud.js:108` |
| 29 | POST | `/api/ml/cross-validation` | A01 | 아카이브 | `ml.py:142` | ✅ | `crossValidation.js:41` |
| 30 | GET | `/api/ml/decision-boundary` | A02 | 아카이브 | `ml.py:167` | ✅ | `decisionBoundary.js:20` |
| 31 | POST | `/api/ml/kmeans` | A04 | 아카이브 | `ml.py:266` | ✅ | `kmeans.js:41` |
| 32 | POST | `/api/ml/linear-regression` | A07 | 아카이브 | `ml.py:431` | ✅ | `linearRegression.js:41` |
| 33 | POST | `/api/ml/mlp` | A06 | 아카이브 | `ml.py:380` | ✅ | `mlp.js:41` |
| 34 | POST | `/api/ml/random-forest` | A03 | 아카이브 | `ml.py:213` | ✅ | `randomForest.js:29` |
| 35 | POST | `/api/ml/svm` | A05 | 아카이브 | `ml.py:324` | ✅ | `svm.js:40` |
| 36 | POST | `/api/nlp/text-classify` | A08 | 아카이브 | `ml.py:485` | ✅ | `textClassify.js:40`<br>`sentiment.js:37` ※ |
| 37 | POST | `/api/quant/backtest` | F08 | B | `quant.py:106` | ✅ | `backtest.js:46` |
| 38 | POST | `/api/quant/financial-knowledge` | F24 | C | `quant.py:325` | **❌** | **없음** |
| 39 | POST | `/api/quant/pipeline` | F09 | B | `quant.py:605` | ✅ | `pipeline.js:51` |
| 40 | POST | `/api/quant/portfolio` | F06 | B | `quant.py:231` | ✅ | `portfolio.js:36` |
| 41 | POST | `/api/quant/portfolio-scenario` | **F05** | **A** | `quant.py:60` | **❌** | `portfolioSimulation.js:56` |
| 42 | POST | `/api/quant/risk` | F07 | B | `quant.py:542` | ✅ | `risk.js:40` |
| 43 | POST | `/api/rag/ask` | **F27** | **A** | `rag.py:171` | **❌** | `ragChat.js:114` |
| 44 | POST | `/api/rag/search` | **F27** | **A** | `rag.py:163` | **❌** | **없음** |
| 45 | GET | `/api/rag/status` | **F27** | **A** | `rag.py:187` | **❌** | `ragChat.js:79` |
| 46 | GET | `/api/system/resources` | F02 | C | `main.py:194` | ✅ | `serverResources.js:136` |
| 47 | GET | `/api/tax/sample` | F26 | C | `tax.py:185` | ✅ | `taxAccounting.js:517` |
| 48 | POST | `/api/tax/simulate` | F26 | C | `tax.py:248` | ✅ | `taxAccounting.js:571` |
| 49 | POST | `/api/tax/upload` | F26 | C | `tax.py:144` | ✅ | `taxAccounting.js:501` |
| 50 | POST | `/api/visitors/heartbeat` | F02 | C | `main.py:232` | ✅ | `app.js:375` |
| 51 | GET | `/files/{file_name}` | X04 | 폐기 | `ml.py:564` | ✅ | `opencv.js:40` (간접) |

> ※ `sentiment.js` 는 `app.js` 의 `routes` 에 등록되지 않아 **진입할 수 없습니다**
> ([기능ID-대장 3.1절](../00-index/기능ID-대장.md#31-파일만-삭제-라우팅되지-않음)).
> A08 의 실사용 호출처는 `textClassify.js:40` 입니다.

---

## 4. 기능 ID → 엔드포인트 역인덱스

명세를 쓸 때 "이 기능이 무슨 API 를 쓰나" 를 찾는 표입니다.

### 4.1 A등급 4개

| 기능 | 엔드포인트 | 상태 |
| --- | --- | --- |
| **F03** 포트폴리오 추천 | **없음** | 프런트 전용. [신설 4개 설계](API-상세명세.md#2-f03-신설-api--포트폴리오-추천-백엔드화) |
| **F04** 포트폴리오 조합 | `POST /api/market/portfolio-combination` | 동작 · **Swagger 누락** |
| **F05** 포트폴리오 시뮬레이션 | `POST /api/quant/portfolio-scenario` | 동작 · **Swagger 누락** |
| **F27** AI 투자 도우미 | `POST /api/rag/ask`<br>`GET /api/rag/status`<br>`POST /api/rag/search` | 앞 둘 동작 · 셋 다 **Swagger 누락** · `search` **미호출** |

### 4.2 B·C등급

| 기능 | 엔드포인트 |
| --- | --- |
| F01 대시보드 | `GET /api/home/market-candle` · `POST /api/market/snapshot` · (`GET /api/home/kospi-candle` · `GET /api/home/box-range` — **미호출**) |
| F02 서버 리소스 | `GET /api/system/resources` · `GET /api/health` · `POST /api/visitors/heartbeat` |
| F06 포트폴리오 최적화 | `POST /api/quant/portfolio` |
| F07 리스크 분석 | `POST /api/quant/risk` |
| F08 백테스트 엔진 | `POST /api/quant/backtest` |
| F09 퀀트 파이프라인 | `POST /api/quant/pipeline` |
| F10 거래량 클라우드 | `GET /api/market/volume-cloud` |
| F11 세계 증시 | `POST /api/market/snapshot` |
| F12 기술적 분석 | **없음** (프런트 전용) |
| F13 거시경제 현황 | `POST /api/macro/realtime` |
| F14 거시경제 시뮬레이션 | `POST /api/macro/simulation` |
| F15 KOSPI 제외 분석 | `POST /api/macro/kospi-ex` · `GET /api/macro/kospi-ex/meta` |
| F16 산업 경쟁력 | `POST /api/industry/porter` · `sector` · `peer` · `lifecycle` |
| F17 기업 파이낸셜 | `POST /api/finance/company-financials` |
| F18 재무제표 분석 | **없음** (프런트 전용) |
| F19 밸류에이션 | **없음** (프런트 전용) |
| F20 DART 기업 검색 | `POST /api/dart/company-search` · `POST /api/finance/company-financials` |
| F21 DART 지역 조회 | `POST /api/dart/company-list` |
| F22 그룹사 네트워크 | `POST /api/dart/group-network` |
| F23 DART 재무 AI | `POST /api/dart/financial-analysis` · `POST /api/dart/company-search` |
| F24 금융상품 학습 | **없음** (`POST /api/quant/financial-knowledge` 는 존재하나 **미호출**) |
| F25 투자 성향 | **없음** (프런트 전용) |
| F26 세무 시뮬레이션 | `POST /api/tax/upload` · `GET /api/tax/sample` · `POST /api/tax/simulate` |
| F28 백테스트 실험실 | `GET /api/backtest-lab/config` · `POST /api/backtest-lab/run` · `POST /api/backtest-lab/report` |
| F29 유튜브 자료실 | **없음** (정적 JSON) |

### 4.3 아카이브·폐기

| ID | 엔드포인트 | 처리 |
| --- | --- | --- |
| A01~A08 | `/api/ml/*` 7개 + `/api/nlp/text-classify` | **유지** (sklearn 만 씀 → 의존성 부담 없음) |
| X01 | `POST /api/dl/cnn-timeseries` | **삭제** (`torch`) |
| X02 | `POST /api/dl/lstm-predictor` | **삭제** (`torch`) |
| X03 | `POST /api/dl/transformer-timeseries` | **삭제** (`torch`) |
| X04 | `POST /api/genai/text-to-image` · `GET /files/{file_name}` | **삭제** (`diffusers`+`torch`) |
| X05 | `POST /api/cv/circle-animation` | **삭제** (`opencv`) |

> **삭제 시 `openapi_docs.py` 도 같이 고쳐야 합니다** — `FRONTEND_API_PATHS` 에서 6줄,
> `OPERATION_DOCS` 에서 6줄을 지웁니다. 안 지우면 화이트리스트가 존재하지 않는 경로를
> 가리키게 됩니다 (현재는 그런 항목이 0건임을 확인했습니다).

---

## 5. 명명 규칙 실태

신설 API 를 설계할 때 따를 기준입니다.

| 관찰 | 실측 |
| --- | --- |
| 경로 형태 | `/api/<도메인>/<동작>` 이 48개. 예외는 `/files/{file_name}`(`ml.py:564`) 1개 |
| 도메인 어휘 | `backtest-lab` · `cv` · `dart` · `dl` · `finance` · `genai` · `health` · `home` · `industry` · `macro` · `market` · `ml` · `nlp` · `quant` · `rag` · `system` · `tax` · `visitors` (18종) |
| **경로 파라미터** | **`/files/{file_name}` 단 1개.** 나머지는 전부 본문 또는 쿼리스트링 |
| 동사형 경로 | 이미 쓰임 — `/api/tax/simulate` · `/api/tax/upload` · `/api/backtest-lab/run` · `/api/nlp/text-classify` |
| 하이픈 표기 | 복합어는 케밥 케이스 (`portfolio-combination` · `kospi-ex` · `text-to-image`) |
| GET / POST 구분 | GET 11개는 **전부 조회형**. 계산·제출은 POST |

> **신설 F03 API 는 이 규칙을 따릅니다** — 도메인 `recommendation`, 케밥 케이스,
> 조회는 GET + 쿼리스트링, 판정·저장은 POST.
> 경로 파라미터는 쓰지 않습니다 (선례가 1개뿐이고 그마저 폐기 대상입니다).

---

## 6. 남은 확인 사항

| # | 내용 | 상태 |
| --- | --- | --- |
| 1 | `kospi-candle` · `box-range` 를 홈 화면에 연결할지, 지울지 | **미결** → [CN-026](../00-index/변경이력.md#cn-026) |
| 2 | `POST /api/rag/search` 를 F27 화면에 노출할지 (지금은 `ask` 만 씀) | **미결** → [CN-028](../00-index/변경이력.md#cn-028) |
| 3 | `POST /api/quant/financial-knowledge` 를 F24 에 연결할지, 지울지 | **미결** → [CN-028](../00-index/변경이력.md#cn-028) |
| 4 | `api.js` 를 단일 창구로 되돌릴지 | **미결** → [CN-027](../00-index/변경이력.md#cn-027) |
