# 기능 ID 대장

> - **버전**: v2.0
> - **최종 수정**: 2026-08-07 (KST)
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
| F01 | 대시보드 (홈) | `home` | `GET /api/home/market-candle`<br>`POST /api/market/snapshot` | B | 동작 |
| F02 | 서버 리소스 모니터 | `server-resources` | `GET /api/system/resources`<br>`GET /api/health`<br>`POST /api/visitors/heartbeat` | C | 동작 |

> `home.js:130,204` 확인. **README 3절의 홈 화면 API 목록은 틀렸습니다** → [CN-004](변경이력.md#cn-004)

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
> → [CN-011](변경이력.md#cn-011)

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
| F24 | 금융상품·자산배분 학습 | `financial-knowledge` | **없음** (※ `POST /api/quant/financial-knowledge` 가 존재하나 호출되지 않음) | C | 프론트전용 |
| F25 | 투자 성향 분석 (의사결정 트리) | `investment-tree` | **없음** | B | 프론트전용 |
| F26 | 세무·회계 시뮬레이션 | `tax-accounting` | `POST /api/tax/upload`<br>`GET /api/tax/sample`<br>`POST /api/tax/simulate` | C | 동작 |
| **F27** | **AI 투자 도우미 (RAG 챗)** | `rag-chat` | `POST /api/rag/ask`<br>`GET /api/rag/status`<br>(`POST /api/rag/search` 미호출) | **A** | 동작 |

### 1.7 별도 페이지 (SPA 밖)

| ID | 기능 | 진입 경로 | 백엔드 | 등급 | 상태 |
| --- | --- | --- | --- | --- | --- |
| F28 | 백테스트 실험실 (LEAN 워크포워드) | `pages/backtest-lab.html`<br>← `index.html:130`, `sidebar-nav.html:34` | `GET /api/backtest-lab/config`<br>`POST /api/backtest-lab/run`<br>`POST /api/backtest-lab/report` | B | 동작 |
| F29 | 유튜브 학습 자료실 | `pages/youtube.html` | 없음 (정적 JSON) | C | **미연결** |

> **F28·F29 는 이번 세션에서 새로 부여한 ID 입니다.** 직전 대장은 F01~F27 까지였고,
> F28 은 커밋 `718f161` 로 들어온 신규 기능입니다. → [CN-007](변경이력.md#cn-007)
> **F29 는 어느 화면에서도 링크가 없습니다.** 연결하거나 지워야 합니다. → [CN-012](변경이력.md#cn-012)

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

### 3.1 파일만 삭제 (라우팅되지 않음)

| 파일 | 사유 |
| --- | --- |
| `app/frontend/js/views/cloudAiResources.js` | `app.js` 의 `routes` 에 없음. 진입 불가 |
| `app/frontend/js/views/sentiment.js` | 위와 동일 |

---

## 4. 집계

| 구분 | 개수 | 근거 |
| --- | --- | --- |
| SPA 라우트 총계 | 40 | `app.js` `routes` 객체 |
| ─ 제품 기능 (F) | 27 | 40 − 8(A) − 5(X) |
| ─ 아카이브 (A) | 8 | |
| ─ 폐기 (X) | 5 | |
| 별도 페이지 (F28·F29) | 2 | `pages/*.html` |
| **명세 대상 기능 총계** | **29** | F01 ~ F29 |
| view 파일 | 42 | 40 + 삭제 대상 2 |
| 백엔드 라우트 | 51 | 데코레이터 실측 |
| ─ 폐기 대상 라우트 | 6 | X01~X05 (X04 가 2개) |
| ─ 아카이브 라우트 | 8 | A01~A08 |
| ─ 잔존 라우트 | 37 | 51 − 6 − 8 |

### 등급 분포

| 등급 | 개수 | ID |
| --- | --- | --- |
| **A** | 4 | F03 · F04 · F05 · F27 |
| B | 17 | F01 · F06 · F07 · F08 · F09 · F11 · F12 · F13 · F14 · F15 · F16 · F17 · F18 · F20 · F23 · F25 · F28 |
| C | 8 | F02 · F10 · F19 · F21 · F22 · F24 · F26 · F29 |
| 합계 | 29 | |

> A등급 4개 중 **F03 은 백엔드가 없습니다.** 여기가 v2.0 의 1순위 작업입니다.

---

## 5. 눈에 띄는 구조적 문제

명세를 쓰기 전에 알아야 할 것들입니다. 상세는 [변경이력](변경이력.md) 참고.

| # | 문제 | 영향받는 기능 |
| --- | --- | --- |
| 1 | **프론트전용 기능이 6개** (F03·F12·F18·F19·F24·F25) — 서버 검증·저장·재현이 없음 | A등급 F03 포함 |
| 2 | `POST /api/quant/financial-knowledge` 가 **어디서도 호출되지 않음** | F24 |
| 3 | `POST /api/rag/search` 가 호출되지 않음 | F27 |
| 4 | `openapi_docs.py` 화이트리스트에 **3개 누락** | F04 · F05 · F28 |
| 5 | `api.js` 바인딩 중 정적 호출이 없는 것 다수 | 40-API 세션에서 정리 |
| 6 | `app/backend/services/` 가 **빈 껍데기** (`__init__.py` 만) | 전체 (D-02 분해의 착지점) |
