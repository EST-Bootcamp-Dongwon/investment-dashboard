# 기능 ID 대장

> - **버전**: v2.1
> - **최종 수정**: 2026-08-10 (KST)
> - **상태**: 초안
> - **기준 코드**: `main` @ `718f161`
> - **역할**: 이 프로젝트의 **모든** 기능에 영구 ID 를 부여하는 단 하나의 대장.

---

## 0. 읽는 법

### 등급

| 등급 | 뜻 | 명세 깊이 |
| --- | --- | --- |
| **A** | 강사님 필수 요구에 직결. 이게 없으면 프로젝트가 성립하지 않음 | 전체 명세 (기능·API·UI·데이터·테스트) |
| **B** | 제품의 본체. 있어야 "SI 수준" 이라고 부를 수 있음 | 기능·API·UI |
| **C** | 보조·부가. 없어도 되지만 있으면 완성도가 올라감 | 기능·UI 요약 |
| **아카이브** | 수업 실습 잔재. 코드는 남기되 제품 기능으로 세지 않음 | 존재·폐기 사유만 |
| **폐기** | 제거 대상. 무거운 의존성을 데리고 다님 | 폐기 근거만 |

### 상태

| 상태 | 뜻 |
| --- | --- |
| `동작` | 코드가 있고 화면에서 실제로 돌아감 |
| `프론트전용` | 화면은 있으나 **백엔드 호출이 없음**. 계산이 브라우저에서만 일어남 |
| `미연결` | 코드는 있으나 어디서도 진입할 수 없음 |
| `재작성` | 동작하지만 v2.0 에서 구조를 다시 짬 |
| `제거예정` | v2.0 에서 코드를 지움 |

### ID 규칙

- `F##` — 제품 기능. **재사용 금지.** 폐기해도 번호를 회수하지 않는다.
- `A##` — 아카이브(수업 실습). 별도 번호 공간.
- `X##` — 폐기. 별도 번호 공간.

---

## 1. 제품 기능 F01 ~ F29

### 1.1 홈과 공통

| ID | 기능 | SPA 라우트 | 백엔드 | 등급 | 상태 |
| --- | --- | --- | --- | --- | --- |
| F01 | 대시보드 (홈) | `home` | `GET /api/home/market-candle`<br>`POST /api/market/snapshot`<br>`GET /api/home/box-range` **(v2.1 신규 연결)** | B | 동작 |
| F02 | 서버 리소스 모니터 | `server-resources` | `GET /api/system/resources`<br>`GET /api/health`<br>`POST /api/visitors/heartbeat` | C | 동작 |

> `home.js:130,204` 확인. **README 3절의 홈 화면 API 목록은 틀렸습니다** → [CN-004](변경이력.md#cn-004)
>
> ✅ **고아 라우트 2개가 v2.1 에서 정리됐습니다** → [CN-053](변경이력.md#cn-053).
> `kospi-candle`(`main.py:2181`)은 **삭제**합니다 — 본문이 `home_market_candle("kospi", …)`
> 위임 한 줄이고 `?market=kospi` 로 같은 응답을 받습니다.
> `box-range`(`main.py:2187`)는 **홈에 연결**합니다 — 홈 시장 카드 4개(`home.js:30~54`)
> 하단에 박스권 위치 막대를 붙입니다.
>
> ⚠ **`box-range` 연결 전에 난수 폴백을 먼저 없앱니다.** 지금은 표시할 화면이 없어
> [CN-041](변경이력.md#cn-041) 이 면제해 뒀지만, **연결하는 순간 면제가 사라집니다.**
> 실패 시 502 로 바꿉니다 ([CN-036](변경이력.md#cn-036) 코드 정책).

### 1.2 포트폴리오 — 프로젝트의 심장

강사님 요구 4화면이 전부 여기에 있습니다.
[요구사항 대조표](강사님-요구사항-대조표.md) 의 R-01~R-04 와 짝을 이룹니다.

| ID | 기능 | SPA 라우트 | 백엔드 | 등급 | 상태 |
| --- | --- | --- | --- | --- | --- |
| **F03** | **포트폴리오 추천** — 목표·기간·하락 반응 → 안정/균형/성장 구성 | `portfolio-guide` | **없음** | **A** | **프론트전용** |
| **F04** | **포트폴리오 조합** — 두 종목 상관 비교(신호등) | `portfolio-combination` | `POST /api/market/portfolio-combination` | **A** | 동작 |
| **F05** | **포트폴리오 시뮬레이션** — 몬테카를로 경로 범위 | `portfolio-simulation` | `POST /api/quant/portfolio-scenario` | **A** | 동작 |
| F06 | 포트폴리오 최적화 (MPT) | `portfolio` | `POST /api/quant/portfolio` | B | 동작 |
| F07 | 리스크 분석 (VaR) | `risk` | `POST /api/quant/risk` | B | 동작 |
| F08 | 백테스트 엔진 (내장) | `backtest` | `POST /api/quant/backtest` | B | 동작 |
| F09 | 퀀트 파이프라인 | `pipeline` | `POST /api/quant/pipeline` | B | 동작 |

> ⚠ **F03 이 A등급인데 백엔드가 없습니다.** 추천 로직이 브라우저 안에만 있어
> 저장·재현·검증이 불가능합니다. SI 수준 요구(R-08)와 정면으로 충돌합니다.
> → [CN-011](변경이력.md#cn-011) · **[CN-047](변경이력.md#cn-047) 이 "프론트전용 6개" 를
> F03 하나로 좁혔습니다** — 나머지 5개는 학습·실습 화면이라 프론트전용이 옳습니다.
>
> ✅ **신설 API 4개가 확정됐습니다** → [CN-039](변경이력.md#cn-039).
> `POST /api/recommendation/preview` · `create` · `GET …/history` · `detail`.
> 저장은 `recommendation` + `recommendation_item`
> ([`테이블-정의서.md` 4.2~4.3절](../30-데이터/테이블-정의서.md#42-recommendation--f03-포트폴리오-추천-결과)).
> **[CN-065](변경이력.md#cn-065) 3계층 분해의 첫 적용 대상이기도 합니다.**

### 1.3 시장과 시세

| ID | 기능 | SPA 라우트 | 백엔드 | 등급 | 상태 |
| --- | --- | --- | --- | --- | --- |
| F10 | 거래량 클라우드 | `volume-cloud` | `GET /api/market/volume-cloud` | C | 동작 |
| F11 | 세계 증시 현황 | `world-markets` | `POST /api/market/snapshot` | B | 동작 |
| F12 | 기술적 분석 실습 | `technical-chart` | **없음** | B | 프론트전용 |

### 1.4 거시경제

| ID | 기능 | SPA 라우트 | 백엔드 | 등급 | 상태 |
| --- | --- | --- | --- | --- | --- |
| F13 | 거시경제 현황 (실시간) | `macro-realtime` | `POST /api/macro/realtime` | B | 동작 |
| F14 | 거시경제 시뮬레이션 (GBM) | `macro-simulation` | `POST /api/macro/simulation` | B | 동작 |
| F15 | KOSPI 제외 지수 분석 | `kospi-excluded` | `POST /api/macro/kospi-ex`<br>`GET /api/macro/kospi-ex/meta` | B | 동작 |

### 1.5 산업과 기업

| ID | 기능 | SPA 라우트 | 백엔드 | 등급 | 상태 |
| --- | --- | --- | --- | --- | --- |
| F16 | 산업 경쟁력 분석 (Porter 5 Forces) | `industry-analysis` | `POST /api/industry/porter`<br>`POST /api/industry/sector`<br>`POST /api/industry/peer`<br>`POST /api/industry/lifecycle` | B | 동작 |
| F17 | 기업 파이낸셜 분석 | `company-financial` | `POST /api/finance/company-financials` | B | 동작 |
| F18 | 재무제표 분석 | `financial-statement` | **없음** | B | 프론트전용 |
| F19 | 밸류에이션 실습 | `valuation` | **없음** | C | 프론트전용 |
| F20 | DART 상장기업 검색 | `dart-company-search` | `POST /api/dart/company-search`<br>`POST /api/finance/company-financials` | B | 동작 |
| F21 | DART 지역·종사자수 조회 | `dart-region-search` | `POST /api/dart/company-list` | C | 동작 |
| F22 | 그룹사 계열사 네트워크 | `group-network` | `POST /api/dart/group-network` | C | 동작 |
| F23 | DART 재무 AI 분석 | `dart-financial-analysis` | `POST /api/dart/financial-analysis`<br>`POST /api/dart/company-search` | B | 동작 |

### 1.6 학습과 AI

| ID | 기능 | SPA 라우트 | 백엔드 | 등급 | 상태 |
| --- | --- | --- | --- | --- | --- |
| F24 | 금융상품·자산배분 학습 | `financial-knowledge` | **없음** (`POST /api/quant/financial-knowledge` 는 **삭제 확정**) | C | 프론트전용 |
| F25 | 투자 성향 분석 (의사결정 트리) | `investment-tree` | **없음** | B | 프론트전용 |
| F26 | 세무·회계 시뮬레이션 | `tax-accounting` | `POST /api/tax/upload`<br>`GET /api/tax/sample`<br>`POST /api/tax/simulate` | C | 동작 |
| **F27** | **AI 투자 도우미 (RAG 챗)** | `rag-chat` | `POST /api/rag/ask`<br>`GET /api/rag/status`<br>(`POST /api/rag/search` 는 **삭제 확정**) | **A** | 동작 |

> **미호출 엔드포인트 2개는 [CN-028](변경이력.md#cn-028) 에서 삭제로 확정됐습니다.**
> 라우트 51 → 49 가 되는 변동입니다 ([4.1절](#41-라우트-수-계보)).
>
> ⚠ **F25 는 실명 금융상품 19개를 추천합니다** → [CN-048](변경이력.md#cn-048).
> 지금까지 확인된 R-07(투자권유 금지) 이슈 중 가장 셉니다. 상품명을 유형명으로 교체합니다.
>
> ⚠ **F27 에는 면책 문구가 아예 없습니다** → [CN-016](변경이력.md#cn-016) ·
> [CN-060](변경이력.md#cn-060) 공통 컴포넌트가 F27·F25 를 1순위로 잡습니다.

### 1.7 별도 페이지 (SPA 밖)

| ID | 기능 | 진입 경로 | 백엔드 | 등급 | 상태 |
| --- | --- | --- | --- | --- | --- |
| F28 | 백테스트 실험실 (LEAN 워크포워드) | `pages/backtest-lab.html`<br>← `index.html:130`, `sidebar-nav.html:34` | `GET /api/backtest-lab/config`<br>`POST /api/backtest-lab/run`<br>`POST /api/backtest-lab/report` | B | 동작 |
| F29 | 유튜브 학습 자료실 (**10주제 · 영상 30개**) | `pages/youtube.html`<br>← **사이드바 링크 신설 예정** | 없음 (프런트 전용) | C | **미연결** |

> **F28·F29 는 세션 2에서 새로 부여한 ID 입니다.** 직전 대장은 F01~F27 까지였고,
> F28 은 커밋 `718f161` 로 들어온 신규 기능입니다. → [CN-007](변경이력.md#cn-007)
>
> ✅ **F29 는 살리기로 결정됐습니다** (2026-08-10) → [CN-051](변경이력.md#cn-051).
> **"없음 (정적 JSON 13.8 KB)" 이라는 이전 서술은 과소평가였습니다.**

**F29 실측 (2026-08-10)** — 백엔드가 없다는 것과 기능이 빈약하다는 것은 다릅니다.

| 항목 | 값 | 측정 |
| --- | ---: | --- |
| 학습 주제 | **10개** | `youtubeVideos.json` 최상위 키 |
| 영상 | **30개** (주제당 3개) · **30/30 유효** | 각 주제 `videos` 배열 · [CN-061](변경이력.md#cn-061) |
| JS 규모 | **334줄** | `wc -l js/pages/youtube.js` |
| JSON 크기 | 13.8 KB | `ls -la` |

**구현돼 있는 것**: 자체 iframe 플레이어(외부 youtube.com 으로 내보내지 않음) ·
YouTube IFrame Player API 로 재생·일시정지·종료 이벤트 추적 ·
시청 시작~종료 시각을 `localStorage` 에 기록·표시 · `ResizeObserver` 크기 맞춤
(`youtube.js:1~9,26~44`).

> **빠진 것은 링크 하나입니다.** `pages/backtest-lab.html`(F28)은 `index.html:130` 과
> `sidebar-nav.html:34` 양쪽에 링크가 있는데, **F29 는 같은 구조인데 링크만 없습니다.**
> 의도적으로 뺀 것이 아니라 작업 누락으로 봅니다.
> [CN-012](변경이력.md#cn-012) 는 이것으로 해소됩니다 → [CN-052](변경이력.md#cn-052) 3계층 IA 의 "학습" 층에 들어갑니다.
>
> **두 기능의 상세 명세는 `20-기능명세/` 의 부록에 있습니다** —
> F28 → [02-포트폴리오 6절](../20-기능명세/02-포트폴리오.md#6-부록--f28--백테스트-실험실-spa-밖) ·
> F29 → [06-학습과-AI 5절](../20-기능명세/06-학습과-AI.md#5-부록--f29--유튜브-학습-자료실-spa-밖).

---

## 2. 아카이브 A01 ~ A08 — sklearn 수업 실습

코드는 남기되 **제품 기능으로 세지 않습니다.** 20-기능명세/90 에서 존재와 사유만 기록합니다.
등급 판단 근거: 포트폴리오 분석과 무관하고, 입력이 실제 시장 데이터가 아니라 실습용 더미입니다.

| ID | 기능 | SPA 라우트 | 백엔드 |
| --- | --- | --- | --- |
| A01 | Cross Validation | `cross-validation` | `POST /api/ml/cross-validation` |
| A02 | Decision Boundary | `decision-boundary` | `GET /api/ml/decision-boundary` |
| A03 | Random Forest | `random-forest` | `POST /api/ml/random-forest` |
| A04 | KMeans 클러스터링 | `kmeans` | `POST /api/ml/kmeans` |
| A05 | SVM 분류기 | `svm` | `POST /api/ml/svm` |
| A06 | MLP 신경망 | `mlp` | `POST /api/ml/mlp` |
| A07 | 선형 회귀 | `linear-regression` | `POST /api/ml/linear-regression` |
| A08 | 텍스트 분류 (TF-IDF) | `text-classify` | `POST /api/nlp/text-classify` |

> 이 8개는 `scikit-learn` 만 쓰므로 **의존성 부담이 없습니다.** 그래서 지우지 않습니다.
> 다만 사이드바에서는 "실습" 섹션으로 분리해 제품 기능과 섞이지 않게 합니다.

---

## 3. 폐기 X01 ~ X05 — v2.0 에서 제거

전부 `torch` · `diffusers` · `opencv` 에 의존합니다.
이 셋이 백엔드 이미지 **2.49GB** 의 대부분을 차지하며, 포트폴리오 분석에는 쓰이지 않습니다.

| ID | 기능 | SPA 라우트 | 백엔드 | 무거운 의존성 |
| --- | --- | --- | --- | --- |
| X01 | 1D CNN 시계열 | `cnn-timeseries` | `POST /api/dl/cnn-timeseries` | `torch` |
| X02 | LSTM 예측기 | `lstm` | `POST /api/dl/lstm-predictor` | `torch` |
| X03 | Transformer 시계열 | `transformer` | `POST /api/dl/transformer-timeseries` | `torch` |
| X04 | HuggingFace 이미지 생성 | `huggingface` | `POST /api/genai/text-to-image`<br>`GET /files/{file_name}` | `diffusers` + `torch` |
| X05 | OpenCV 애니메이션 | `opencv` | `POST /api/cv/circle-animation` | `opencv-python-headless` |

**제거 시 함께 지울 것**

- `requirements.txt` 의 `torch` · `diffusers` · `opencv-python-headless`
- `app/backend/routers/ml.py` 의 해당 라우트 6개 (`/files/{file_name}` 포함)
- `app/frontend/js/views/` 의 5개 파일
- `app/frontend/js/app.js` 의 import·routes 항목

> **시계열 예측 자체를 버리는 것이 아닙니다.** LSTM·Transformer 를 지우는 대신,
> 수업 `learning/05-time-series` 의 통계적 시계열(분해·ARIMA·계절성)을
> **F05·F28 안으로 흡수**합니다. → [CN-009](변경이력.md#cn-009)

<a id="31-파일만-삭제-라우팅되지-않음"></a>
### 3.1 라우팅되지 않는 view 2개 — 한쪽만 삭제합니다

**이 절은 [CN-050](변경이력.md#cn-050) 으로 정정된 내용입니다.**
v2.0 초판은 둘 다 "`app.js` 의 `routes` 에 없음 → 파일만 삭제" 로 적었고,
**절반이 틀렸습니다.**

| 파일 | v2.0 초판 판정 | **실측 (2026-08-10)** | 조치 |
| --- | --- | --- | --- |
| `app/frontend/js/views/cloudAiResources.js` | ~~삭제~~ | ❌ **12개 뷰가 import 중** | **유지** |
| `app/frontend/js/views/sentiment.js` | 삭제 | ✅ 참조 0건 | **삭제** |

```
$ grep -rln "from './cloudAiResources.js'" app/frontend/js/views/ | wc -l
12                                                          # 실측 2026-08-10
```

**import 하는 12개**: `backtest` · `crossValidation` · `cnnTimeseries` · `kmeans` ·
`linearRegression` · `lstm` · `mlp` · `randomForest` · `pipeline` · `svm` ·
`technicalChart` · `transformer`.
그중 폐기 대상은 **3개**(`cnnTimeseries`·`lstm`·`transformer`)뿐이라,
**X01~X05 를 지운 뒤에도 9개 뷰가 남아 계속 씁니다.**

> **"라우팅되지 않는다 = 죽은 코드" 라는 추론이 틀렸습니다.**
> `cloudAiResources.js` 는 화면이 아니라 **공용 부품**입니다 —
> `cloudResourceCard(viewName)`(`cloudAiResources.js:1~4`)이 각 모듈을 AWS·Azure·GCP
> 관리형 AI 서비스로 구현하면 어떤 리소스를 쓰는지 설명하는 카드를 만듭니다.
> **라우트가 없는 것이 당연합니다.**
>
> `sentiment.js` 쪽은 판정이 맞았습니다. `financialStatement.js:176` 의
> `images/sentiment.png` 는 **이미지 경로일 뿐 이 모듈과 무관**합니다.
>
> 상세는 [`../20-기능명세/99-폐기-기능.md` 3.1절](../20-기능명세/99-폐기-기능.md#31-미라우팅-view-2개--한쪽은-지우면-안-됩니다).

---

## 4. 집계

| 구분 | 개수 | 근거 |
| --- | --- | --- |
| SPA 라우트 총계 | 40 | `app.js` `routes` 객체 (실측 2026-08-10) |
| ─ 제품 기능 (F) | 27 | 40 − 8(A) − 5(X) |
| ─ 아카이브 (A) | 8 | |
| ─ 폐기 (X) | 5 | |
| 별도 페이지 (F28·F29) | 2 | `pages/*.html` |
| **명세 대상 기능 총계** | **29** | F01 ~ F29 |
| view 파일 | 42 | 실측 `ls js/views/*.js` 2026-08-10. 라우트 40 + 비라우팅 2 (3.1절) |
| ─ 그중 삭제 대상 | **1** | `sentiment.js` 만. `cloudAiResources.js` 는 **유지** ([CN-050](변경이력.md#cn-050)) |
| 백엔드 라우트 (현행) | 51 | 데코레이터 실측 (2026-08-10 재확인) |
| ─ 폐기 대상 라우트 | 6 | X01~X05 (X04 가 2개) |
| ─ 아카이브 라우트 | 8 | A01~A08 |
| ─ 잔존 라우트 | 37 | 51 − 6 − 8 |

<a id="41-라우트-수-계보"></a>
### 4.1 백엔드 라우트 수 계보 — 51 에서 52 로

숫자가 여러 문서에 흩어져 있어 **여기를 정본으로 둡니다.**

| 단계 | 라우트 수 | 변동 | 근거 |
| --- | ---: | --- | --- |
| 현행 (실측) | **51** | — | `grep -rnE '@(app\|router)\.(get\|post\|…)\('` |
| [CN-028](변경이력.md#cn-028) 반영 | **49** | −2 | 호출되지 않는 `POST /api/rag/search` · `POST /api/quant/financial-knowledge` 삭제 |
| [CN-053](변경이력.md#cn-053) 반영 | **48** | −1 | `GET /api/home/kospi-candle` 삭제 (위임 한 줄) |
| [CN-039](변경이력.md#cn-039) 반영 | **52** | +4 | F03 백엔드화 — `/api/recommendation/` `preview`·`create`·`history`·`detail` |

> **51 은 "지금", 52 는 "v2.0 구현 완료 시점" 입니다.** 두 숫자가 문서에 같이 나오면
> 어느 시점인지 확인하세요. 폐기(X01~X05 · 6개)·아카이브(8개) 라우트는 이 계보와
> **별개 축**입니다 — 폐기는 배포본에서 빠지지만 코드는 로컬에 남습니다
> ([CN-063](변경이력.md#cn-063)).

### 등급 분포

| 등급 | 개수 | ID |
| --- | --- | --- |
| **A** | 4 | F03 · F04 · F05 · F27 |
| B | 17 | F01 · F06 · F07 · F08 · F09 · F11 · F12 · F13 · F14 · F15 · F16 · F17 · F18 · F20 · F23 · F25 · F28 |
| C | 8 | F02 · F10 · F19 · F21 · F22 · F24 · F26 · F29 |
| 합계 | 29 | |

> A등급 4개 중 **F03 은 백엔드가 없습니다.** 여기가 v2.0 의 1순위 작업입니다.

---

## 5. 눈에 띄는 구조적 문제 — v2.1 시점 정리

v2.0 초판이 올린 7건입니다. **v2.1 기준으로 전부 결정되거나 정정됐습니다.**
상세는 [변경이력](변경이력.md) 참고.

| # | v2.0 초판이 올린 문제 | v2.1 처리 | 결과 |
| --- | --- | --- | --- |
| 0 | **사이드바에서 갈 수 있는 화면이 9개뿐** — 라우트 40개 중 32개가 링크 없음 | [CN-052](변경이력.md#cn-052) **제품·학습·실습 3계층 IA 확정** | **해소** |
| 1 | **프론트전용 기능이 6개** (F03·F12·F18·F19·F24·F25) | [CN-047](변경이력.md#cn-047) — **6개 중 F03 하나만 진짜 문제**. 나머지 5개는 학습·실습 화면이라 프론트전용이 옳음 | **정정** |
| 2 | `POST /api/quant/financial-knowledge` 미호출 (F24) | [CN-028](변경이력.md#cn-028) **삭제 확정** | **결정** |
| 3 | `POST /api/rag/search` 미호출 (F27) | [CN-028](변경이력.md#cn-028) **삭제 확정** | **결정** |
| 4 | `openapi_docs.py` 화이트리스트 **3개 누락** | [CN-025](변경이력.md#cn-025) — **3건이 아니라 8건**. A등급 4개가 전멸 | **정정 (확대)** |
| 5 | `api.js` 바인딩 중 정적 호출이 없는 것 다수 | [CN-027](변경이력.md#cn-027) — **15건 중 14건이 오탐**. `api.js` 가 단일 창구가 아니었을 뿐 | **해소** |
| 6 | `app/backend/services/` 가 **빈 껍데기** (`__init__.py` 만) | [CN-065](변경이력.md#cn-065) **3계층 분해 설계 확정** (D-02) | **해소** |

> **1번과 4번의 방향이 반대입니다.** 프론트전용 문제는 **좁아졌고**(6→1),
> Swagger 누락은 **넓어졌습니다**(3→8). v2.0 초판의 추정이 한쪽은 과했고
> 한쪽은 모자랐다는 뜻이라, **양쪽 다 실측으로 다시 센 것**이 이번 정리의 핵심입니다.

### 5.1 v2.1 이 새로 올린 것 — 구현 전에 알아야 할 3건

| # | 문제 | 근거 | 영향 |
| --- | --- | --- | --- |
| 1 | **X01~X05 를 다 폐기해도 Vercel 500 MB 에 못 들어감** (564.5 MB) | [CN-063](변경이력.md#cn-063) | 배포 전체. matplotlib 을 빼서 429.8 MB |
| 2 | **F07·F08·F09 의 화면 입력이 서버에 전달되지 않음** | [CN-043](변경이력.md#cn-043) | 파라미터를 바꿔도 결과가 안 바뀜 |
| 3 | **테스트 코드가 0건** — `test/` 는 수업 실습이고 단정문이 한 줄도 없음 | [CN-076](변경이력.md#cn-076) | R-08 심사 |
