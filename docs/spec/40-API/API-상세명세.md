# API 상세 명세

> - **버전**: v2.1
> - **최종 수정**: 2026-08-10 (KST)
> - **상태**: 초안
> - **기준 코드**: `main` @ `718f161`
> - **역할**: 엔드포인트별 요청·응답 스키마. **A등급(F03·F04·F05·F27)을 전체 명세**하고
>   나머지는 요약한다.
> - **관련**: [API-목록](API-목록.md) · [공통-응답과-에러](공통-응답과-에러.md) ·
>   [30-데이터/ERD](../30-데이터/ERD.md)

---

## 0. 읽는 법

### 명세 깊이는 등급을 따른다

[기능ID-대장 0절](../00-index/기능ID-대장.md#0-읽는-법)의 등급 정의에 따라 깊이를 나눴습니다.

| 등급 | 이 문서에서의 깊이 | 절 |
| --- | --- | --- |
| **A** (F03·F04·F05·F27) | 요청 전 필드 · 응답 전 필드 · 에러 전수 · 알고리즘 상수 | [1](#1-a등급-현행-3기능) · [2](#2-f03-신설-api--포트폴리오-추천-백엔드화) |
| B | 요청 필드 · 응답 주요 키 · 특이사항 | [3](#3-b등급-요약) |
| C · 아카이브 · 폐기 | 요청 필드만 | [4](#4-c등급아카이브폐기-요약) |

### 공통 규약은 여기 반복하지 않는다

에러 본문 형태 · HTTP 코드 정책 · 캐시 · CORS 는 전부
[`공통-응답과-에러.md`](공통-응답과-에러.md) 에 있습니다. 이 문서의 에러 표는
**그 엔드포인트에만 있는 조건**을 적습니다.

### 표기

- `O` = 필수, `-` = 선택
- `(확인 필요)` = 코드·실측·공식문서 어디서도 확인하지 못함
- 모든 근거는 `파일:줄`

---

## 1. A등급 현행 3기능

### 1.1 F04 · `POST /api/market/portfolio-combination`

두 종목의 실제 시세로 일간 수익률 상관계수를 구해 **숫자 대신 신호등**으로 답합니다.
R-02 가 요구한 화면입니다.

- **핸들러**: `app/backend/main.py:1167`
- **요청 모델**: `PortfolioCombinationRequest` (`app/backend/main.py:1103`)
- **Content-Type**: `application/json`

**요청**

| 필드 | 타입 | 필수 | 기본 | 제약 |
| --- | --- | :---: | --- | --- |
| `ticker_a` | str | - | `"AAPL"` | `min_length=1, max_length=20` (`main.py:1104`)<br>+ 핸들러 정규식 `^[A-Z0-9.^=\-]{1,20}$` (`main.py:1175`) |
| `ticker_b` | str | - | `"JNJ"` | 위와 동일. 정규화 후 `ticker_a` 와 같으면 422 (`main.py:1181`) |
| `period` | str | - | `"1y"` | `pattern ^(3mo\|6mo\|1y\|2y)$` (`main.py:1106`) |

> 핸들러가 `strip().upper()` 로 정규화한 **뒤** 정규식을 검사합니다 (`main.py:1173~1177`).
> 프런트 입력창은 `maxlength=15` 로 더 좁습니다 (`views/portfolioCombination.js:155`).

**응답** (`main.py:1234~1243`)

| 필드 | 타입 | 설명 |
| --- | --- | --- |
| `ticker_a` · `ticker_b` | str | 정규화된 종목 코드 (`main.py:1179~1180`) |
| `period_label` | str | 한국어 라벨. `main.py:1222` 의 매핑 — 최근 3개월/6개월/1년/2년 |
| `signal` | str | **`green` \| `yellow` \| `red`**. 프런트가 아이콘·라벨로 매핑 (`portfolioCombination.js:9~13`) |
| `summary` | str | 신호등별 고정 한국어 문장 (`main.py:1211`/`1215`/`1219`) |
| `portfolio_hint` | str | 신호등별 고정 조언 문장. 내부 변수명은 `hint` (`main.py:1212`/`1216`/`1220`) |
| `latest_data_at` | str | 마지막 거래일. `pd.Timestamp(...).isoformat()` 이라 **시각 포함** (`main.py:1223`) |
| `chart_points` | list | 기준 100 정규화 흐름. 첫 원소는 항상 `a=b=100.0` (`main.py:1225~1233`) |
| `chart_points[].date` | str | `YYYY-MM-DD` (시각 없음, `main.py:1228`) |
| `chart_points[].a` · `.b` | float | 정규화 가격, 소수 4자리 반올림 (`main.py:1229~1230`) |

**신호등 임계값** — 이 값이 F04 의 전부입니다.

| 상관계수 | `signal` | 근거 |
| --- | --- | --- |
| `< 0.30` | `green` | `main.py:1209` |
| `0.30 이상 0.70 미만` | `yellow` | `main.py:1213` |
| `0.70 이상` | `red` | `main.py:1217` |

프런트 설명 모달도 같은 0.30/0.70 을 명시합니다 (`portfolioCombination.js:135`).
**상관계수 자체는 응답에 없습니다** — 화면에는 신호등과 문장만 나갑니다.

**계산 방식** (`main.py:1203~1207`)

종가를 inner join → `dropna` → `pct_change(fill_method=None)` → `dropna` → `corr().iloc[0,1]`.
로그수익률이 아니라 **단순 변화율**입니다.

**데이터 최소 요건**

| 조건 | 값 | 근거 |
| --- | --- | --- |
| 종목별 종가 | 21개 이상 | `main.py:1191` |
| 정렬 후 일간 변화율 | 20개 이상 | `main.py:1205` |

**에러**

| 코드 | 조건 | 근거 |
| --- | --- | --- |
| 422 | 티커 정규식 위반 → "올바른 종목 코드를 입력해 주세요." | `main.py:1175~1176` |
| 422 | 두 종목이 동일 → "서로 다른 두 종목을 선택해 주세요." | `main.py:1181~1182` |
| 422 | 가격 데이터 부족 → "{종목}의 충분한 가격 데이터를 찾지 못했습니다." | `main.py:1191~1200` |
| 422 | 겹치는 거래일 부족 → "두 종목의 함께 비교할 수 있는 거래일이 부족합니다." | `main.py:1205~1206` |

> ⚠ **외부 장애가 422 로 나갑니다.** `main.py:1195~1196` 이 yfinance 예외를
> `except Exception` 으로 삼켜 "데이터 없음" 으로 바꿉니다. Yahoo 가 죽어도 사용자에게는
> "종목을 잘못 골랐다" 로 보입니다. → [공통-응답과-에러 4.2절](공통-응답과-에러.md#42-외부-데이터-실패는-502503-으로-모은다)

**외부 호출**: `yf.download(ticker, period, interval="1d", auto_adjust=True, threads=False)` 를
**for 루프로 순차 2회** (`main.py:1186~1189`). 캐시·타임아웃·재시도가 없습니다.

---

### 1.2 F05 · `POST /api/quant/portfolio-scenario`

몬테카를로 5,000경로로 **보수·중간·긍정 범위**를 보여줍니다. R-03·R-05 가 요구한 화면입니다.

- **핸들러**: `app/backend/routers/quant.py:60`
- **요청 모델**: `PortfolioScenarioRequest` (`quant.py:51`)

**요청**

| 필드 | 타입 | 필수 | 기본 | 제약 |
| --- | --- | :---: | --- | --- |
| `profile` | str | - | `"balanced"` | `pattern ^(stable\|balanced\|growth)$` (`quant.py:52`) |
| `initial_amount` | int | - | `10000000` | `ge=0, le=1_000_000_000` (`quant.py:53`) |
| `monthly_amount` | int | - | `500000` | `ge=0, le=100_000_000` (`quant.py:54`) |
| `years` | int | - | `10` | `ge=1, le=30` (`quant.py:55`) |

프런트 `<select>` 는 3·5·10·20 년만 제공합니다 (`views/portfolioSimulation.js:38`).

**프로필별 가정** (`quant.py:66~70`)

| `profile` | `profile_label` | 연 기대수익 | 연 변동성 |
| --- | --- | --- | --- |
| `stable` | 안정 중심 | 4.5% | 7% |
| `balanced` | 균형 중심 | 6.5% | 12% |
| `growth` | 성장 중심 | 8.5% | 18% |

**재현성 — ERD 0.2절의 근거**

```python
# app/backend/routers/quant.py:72~73
rng = np.random.default_rng(20260806)
paths = 5_000
```

시드가 **고정 상수**이므로 `(profile, initial_amount, monthly_amount, years)` 네 값만
저장하면 5,000경로가 통째로 재현됩니다. `simulation_run` 테이블이 이 네 값을 컬럼으로
드는 이유입니다 ([ERD 0.2절](../30-데이터/ERD.md#02-입력을-저장하면-결과가-재현된다)).

**응답** (`quant.py:93~104`)

| 필드 | 타입 | 설명 |
| --- | --- | --- |
| `profile_label` | str | 한국어 라벨 (`quant.py:67~69`) |
| `years` | int | 요청 에코 |
| `total_paid` | int | 원금 합계 = `initial + monthly × years × 12` (`quant.py:91`). **수익률 미반영** |
| `points` | list | 연 단위 곡선. 길이 = `years + 1` (0년 포함) |
| `points[].year` | int | `month // 12` (`quant.py:77,85`) |
| `points[].cautious` | int | **10 백분위**. 반올림 후 int (`quant.py:83,86`) |
| `points[].middle` | int | **50 백분위** (`quant.py:83,87`) |
| `points[].positive` | int | **90 백분위** (`quant.py:83,88`) |
| `summary.cautious` · `.middle` · `.positive` | int | `points[-1]` 복사값 (`quant.py:92,99`) |
| `explanation` | str | 한국어 설명 문장 (`quant.py:105`) |

**월 적립 순서** — `monthly_amount` 는 **당월 수익률 적용 이전**에 더해집니다
(`quant.py:81`). 즉 당월 납입액도 그 달의 등락을 함께 겪습니다.

**에러**: Pydantic 422 외에 **없습니다.** `quant.py:9` 가 `HTTPException` 을 import 조차
하지 않습니다. 계산 중 예외가 나면 JSON 이 아닌 **Starlette 기본 500 텍스트**가 나갑니다.
→ [공통-응답과-에러 3.4절](공통-응답과-에러.md#34-quantpy-6개는-에러-처리가-아예-없다)

---

### 1.3 F27 · RAG 3종

R-04 가 요구한 AI 투자 도우미입니다. **세 엔드포인트 모두 Swagger 에 없습니다**
([API-목록 2.1절](API-목록.md#21-swagger-에서-빠진-8개--cn-005-정정)).

#### 공통 — 요청 모델과 임베딩

`RagSearchRequest` (`rag.py:71`) 를 `RagAskRequest` (`rag.py:77`) 가 상속합니다.

| 필드 | 타입 | 필수 | 기본 | 제약 | 비고 |
| --- | --- | :---: | --- | --- | --- |
| `query` | str | O | — | `min_length=1, max_length=2000` (`rag.py:72`) | 응답에 에코 |
| `top_k` | int | - | `5` | `ge=1, le=20` (`rag.py:73`) | Qdrant `limit` 으로 전달 |
| `score_threshold` | float | - | `0.0` | `ge=0.0, le=1.0` (`rag.py:74`) | **0 보다 클 때만** payload 에 키 추가 (`rag.py:83~84`) |
| ~~`provider`~~ | ~~str~~ | - | — | **필드 삭제 (2026-08-16)** — 절대 제약 1. 보내도 무시됩니다 | ~~**`ask` 전용**~~ |

**임베딩 — `_hash_embed` (`rag.py:52~59`)**

기본 **384차원**. SHA-256 부호 해싱입니다.

1. 정규식 `[0-9A-Za-z가-힣_]+` 로 소문자 토큰화 (`rag.py:55`)
2. 토큰마다 `sha256` → 앞 4바이트를 big-endian 정수로 읽어 `% dim` 자리 결정 (`rag.py:57`)
3. `digest[4]` 최하위 비트로 `+1.0` / `-1.0` 누적
4. L2 정규화. norm 이 0이면 영벡터 (`rag.py:58~59`)

학습된 모델을 전혀 쓰지 않으므로 **어휘가 정확히 겹칠 때만 걸립니다.**
→ [CN-021](../00-index/변경이력.md#cn-021) 에서 `gemini-embedding-001` 768차원으로
교체하기로 확정됐습니다. 아래 명세는 **교체 전 현행 코드** 기준입니다.

> 실제 차원은 `_embed_query` (`rag.py:62~68`) 가 컬렉션 설정 `vectors.size` 를 읽어
> 맞춥니다. 조회 실패 시에만 384 로 폴백합니다 (`rag.py:66~67`).

**Qdrant 인증** — 코드 전체에 **인증 헤더가 0건**입니다.
`_qdrant_request` (`rag.py:20~32`) 는 payload 가 있을 때만 `Content-Type` 을 붙이고
(`rag.py:23`), `api-key` · `Authorization` 을 어디에도 넣지 않습니다.
`QDRANT_API_KEY` 류 설정도 없습니다. **인증 없는 내부망 Qdrant 를 전제합니다.**

#### `POST /api/rag/search` — **미호출**

- **핸들러**: `rag.py:164`

| 응답필드 | 타입 | 설명 |
| --- | --- | --- |
| `query` | str | 요청 에코 |
| `embed_method` | str | **항상 `"hash"`** 고정 (`rag.py:168`) |
| `count` | int | `len(chunks)` |
| `results[].score` | float | Qdrant `hit.score` 를 `round(_,4)` (`rag.py:87`) |
| `results[].source_doc` | str | payload. 없으면 `""` (`rag.py:88`) |
| `results[].chunk_index` | int | payload. 없으면 `0` (`rag.py:89`) |
| `results[].text` | str | **청크 원문 무삭제** (`rag.py:90`) |

> ⚠ `results[].text` 에 길이 컷이 없습니다. `ask` 의 500자 컷(`rag.py:113`)이나
> 14,000자 컷(`rag.py:128`)이 여기엔 적용되지 않습니다. `top_k=20` 이면 청크 20개 원문이
> 통째로 나갑니다.

**Qdrant 왕복 횟수**: 1회 요청에 **최대 4회** — 생존 확인(`rag.py:37`) → 컬렉션 확인
(`rag.py:46`) → 차원 조회(`rag.py:64`) → 검색(`rag.py:85`).

#### `POST /api/rag/ask`

- **핸들러**: `rag.py:172`

| 응답필드 | 타입 | 설명 |
| --- | --- | --- |
| `query` | str | 요청 에코 |
| `answer` | str | `provider` 분기 결과 (`rag.py:176,179`) |
| `provider` | str | 요청 에코 |
| `embed_method` | str | 고정 `"hash"` |
| `sources` | list | `search` 의 `results` 와 동일 구조. **원문 무삭제** |
| `source_count` | int | `len(chunks)` |

**~~`provider` 두 갈래~~ → 한 갈래**

> ⚠ **2026-08-16: 외부 AI(`provider=openai_compatible`) 경로를 폐기했습니다.**
> `RAG_LLM_*` 3종과 `clients/rag_llm.py` 가 함께 사라졌고, `provider` 필드 자체가
> 요청 스키마에서 빠졌습니다(보내도 무시됩니다). 근거는 절대 제약 1 —
> **LLM 유료 API 비용 0원**. 아래 표에 취소선이 그것입니다.
> 자세한 경위는 [보안과-시크릿 §1.1](../60-운영/보안과-시크릿.md).

| 값 | 동작 | 외부 호출 |
| --- | --- | --- |
| `rag` (기본) | `_rag_only_answer` (`rag.py:105~114`). **생성 모델 미사용.** 상위 **3개만** 순회(`rag.py:110`) → 공백 정규화 → **500자 컷 + `…`**(`rag.py:113`) → `• ` 불릿 | 0회 |
| ~~`openai_compatible`~~ | **폐기 (2026-08-16)** — `_openai_compatible_answer`·`build_llm_prompt`·`clients/rag_llm.py` 모두 삭제 | ~~외부 호출~~ → **0회** |

**프롬프트 원문** (`rag.py:129~134`)

> "아래 '검색 원문'만 근거로 사용자의 질문에 한국어로 간결하게 답하세요.
> **원문에 없는 사실·숫자·투자 조언을 추가하지 말고**, 정보가 부족하면 부족하다고 밝히세요.
> 출처 번호를 [출처 1]처럼 표시하고 3개 이내의 짧은 문단 또는 목록으로 정리하세요."

system 메시지 (`rag.py:138`): "당신은 제공된 RAG 문서만 다듬어 설명하는 도우미입니다."

> ⚠ **R-04 의 "확인할 질문 제안" 이 이 프롬프트에 없습니다.** 오히려 위 굵은 문장이
> 원문 밖 생성을 금지하므로 정면으로 충돌합니다. → [CN-014](../00-index/변경이력.md#cn-014)

**`provider=rag` 여도 Qdrant 503/502 가 납니다** — `_require_qdrant` + `_search` 가
분기 이전에 항상 실행됩니다 (`rag.py:174~175`).

**전용 에러**

| 코드 | 조건 | 근거 |
| --- | --- | --- |
| 503 | Qdrant 미기동 | `rag.py:95~96` |
| 503 | 컬렉션 미생성 (색인 명령 안내 포함) | `rag.py:97~102` |
| 502 | Qdrant HTTP 에러 — **응답 본문 200자를 그대로 노출** | `rag.py:28~30` |

> ⚠ **502 두 건이 외부 시스템 응답 원문을 사용자에게 흘립니다.**
> → [공통-응답과-에러 5.2절](공통-응답과-에러.md#52-외부-예외-원문을-detail-에-붙이는-19곳)

#### `GET /api/rag/status`

- **핸들러**: `rag.py:188` · 요청 파라미터 **없음** · **에러 없음 (항상 200)**

모든 예외를 삼킵니다 (`rag.py:39~40,48~49,201~202`). Qdrant 가 꺼져 있어도
`200 + available:false` 가 나갑니다.

**응답 스키마가 200 안에서 세 갈래로 갈립니다** — `qdrant` 가 `{...고정4키, **info}`
형태이기 때문입니다 (`rag.py:204`).

| 상황 | `qdrant` 객체의 키 |
| --- | --- |
| `collection_available=false` | `available` · `collection_available` · `url` · `collection` (4개) |
| 조회 성공 | 위 4개 + `points_count` · `vector_size` · `status` |
| 조회 예외 | 위 4개 + `error` (고정 문자열 "컬렉션이 없거나 조회 실패") |

그 밖: `embed_method` (고정 `"hash"`). ~~`external_ai.openai_compatible_available`~~ 는 2026-08-16 에 응답에서 빠졌습니다.

> `qdrant.url` 이 `_QDRANT_URL` 을 **그대로 노출**합니다 (`rag.py:16,204`).
> 인증 없는 상태 조회라 내부 주소가 외부로 나갑니다.

---

## 2. F03 신설 API — 포트폴리오 추천 백엔드화

R-01 이 요구한 A등급 기능인데 **백엔드가 없습니다.** 추천 로직이 브라우저 안에만 있어
저장·재현·검증이 안 됩니다 ([CN-011](../00-index/변경이력.md#cn-011)).
[30-데이터 ERD](../30-데이터/ERD.md) 가 `recommendation` · `recommendation_item` 을
이미 확정했으므로, 그 스키마에 얹어 4개를 신설합니다.

### 2.1 현행 프런트 로직 실측

> ⚠ **"현행" 은 백엔드화 이전(`main` @ `718f161`)의 프런트입니다. 이 절은 그 시점의
> 기록이고, 판정 규칙은 여기 적힌 것을 쓰지 않습니다.**
> [CN-029](../00-index/변경이력.md#cn-029) 가 규칙 교체를 결정했으므로 판정의 정본은
> [02-포트폴리오 1.4절](../20-기능명세/02-포트폴리오.md#14-v20-판정-규칙--cn-029-결정-고칩니다)
> 이고, 구현은 `app/backend/services/recommendation.py:100~135` 입니다.
> **설문 3문항·배분표·`explanation` 실측은 그대로 유효합니다** — 바뀐 것은 판정뿐입니다.

**설문 3문항** (`views/portfolioGuide.js:95~97`) — 입력은 이게 전부입니다.
금액·나이·보유종목 같은 입력은 파일 어디에도 없습니다.

| 문항 | id | value |
| --- | --- | --- |
| 투자 목적 | `guide-goal` | `growth` · `balance` · `protect` |
| 투자 기간 | `guide-horizon` | `short` · `medium` (기본) · `long` |
| 가격 하락 시 반응 | `guide-risk` | `low` · `medium` (기본) · `high` |

**판정 로직 (교체 전)** — 두 곳에 나뉘어 있었습니다.

```javascript
// app/frontend/js/views/portfolioGuide.js:39~43
function suggestedProfile(risk, horizon) {
  if (risk === 'low' || horizon === 'short') return 'stable';
  if (risk === 'high' && horizon === 'long') return 'growth';
  return 'balanced';
}

// app/frontend/js/views/portfolioGuide.js:133
const profile = goal === 'protect' ? 'stable'
  : goal === 'growth' && horizon === 'long' && risk !== 'low' ? 'growth'
  : suggestedProfile(risk, horizon);
```

**27조합 전수 진리표 — 교체 전 규칙의 기록입니다. 이대로 구현하지 마세요.**

| goal | horizon | risk=low | risk=medium | risk=high |
| --- | --- | --- | --- | --- |
| protect | short/medium/long | stable | stable | stable |
| growth | short | stable | stable | stable |
| growth | medium | stable | balanced | balanced |
| growth | long | stable | **growth** | **growth** |
| balance | short | stable | stable | stable |
| balance | medium | stable | balanced | balanced |
| balance | long | stable | balanced | **growth** |

**분포: stable 19 / balanced 5 / growth 3.**

**위 표를 3줄로 줄이면 이렇습니다** — 표와 완전히 등가입니다. 아래 관찰 ①②가 여기서
나왔으므로 **대조 기준으로만** 남깁니다. 서버가 구현한 것은 이 3줄이 아니라
[1.4절](../20-기능명세/02-포트폴리오.md#14-v20-판정-규칙--cn-029-결정-고칩니다) 의 점수제입니다.

1. `goal == protect` **또는** `risk == low` **또는** `horizon == short` → `stable`
2. (그 외) `horizon == long` **이고** (`goal == growth` **또는** `risk == high`) → `growth`
3. 나머지 → `balanced`

> **관찰 3가지.**
> ① `goal` 축은 사실상 두 가지 일만 합니다 — `protect` 면 고정, 그 외에는
> **(기간 × 하락반응) 9칸 중 1칸**(`long`·`medium`)에서만 `growth`/`balance` 차이가
> 납니다. [CN-029](../00-index/변경이력.md#cn-029) 실측과 같은 수입니다 (1 / 9).
> ② `growth` 는 3칸뿐이고 셋 다 `horizon == long` 입니다. 백엔드화 후 분포를 관측하면
> `stable` 이 압도적으로 나옵니다.
> ③ 페이지 진입 시 `renderProfile('balanced')` 가 하드코딩돼 있고(`js:100`),
> 기본 select 값의 판정 결과와 **우연히** 일치합니다.
>
> **관찰 ①② 가 [CN-029](../00-index/변경이력.md#cn-029) 로 이어졌고, 2026-08-10 에
> "규칙을 고칩니다" 로 결정됐습니다.** 새 규칙의 분포는 **stable 10 / balanced 10 /
> growth 7**, `goal` 이 결과를 바꾸는 칸은 4/9 → **8/9** 입니다
> (전수 대조 `python3 scripts/verify_recommendation_rule.py`, 2026-08-10).
> ③ 의 하드코딩은 진입 시 `preview` 호출로 대체됐습니다
> → [CN-085](../00-index/변경이력.md#cn-085).

**배분표** (`views/portfolioGuide.js:1~37`) — `items` 원소는 `[자산명, 비중, 색상, 설명]` 입니다.

| profile | 자산 (비중%) | 합계 |
| --- | --- | :---: |
| `stable` | 현금성 자산 35 · 채권·안정형 자산 35 · 글로벌 주식 20 · 배당·방어형 주식 10 | 100 |
| `balanced` | 글로벌 주식 45 · 채권·안정형 자산 25 · 국내 주식 15 · 현금성 자산 10 · 대체 자산 5 | 100 |
| `growth` | 글로벌 주식 60 · 국내 주식 20 · 테마·성장 자산 10 · 채권·안정형 자산 5 · 현금성 자산 5 | 100 |

**확정 스키마 정합 검증** (2026-08-09)

| 검증 | 결과 |
| --- | --- |
| `asset_name` ≤ 40자 (`테이블-정의서.md:135`) | 통과 (최장 "배당·방어형 주식" 10자) |
| `explanation` ≤ 200자 (`테이블-정의서.md:137`) | 통과 (최장 26자) |
| `weight_pct` 0~100 (`테이블-정의서.md:136`) | 통과 (5~60) |
| `profile_label` ≤ 40자 (`테이블-정의서.md:105`) | 통과 (7~8자) |

**색상을 저장하지 않기로 한 결정이 실측으로 뒷받침됩니다.** 자산명 → 색상이 세 프로필에
걸쳐 **모순 없는 함수**입니다 (현금성 자산 `#38bdf8` — `js:6,20,33` / 채권·안정형 자산
`#818cf8` — `js:7,18,32` / 글로벌 주식 `#22c55e` — `js:8,17,29` / 국내 주식 `#0078d4` —
`js:19,30`). 프런트가 `asset_name` 으로 되찾을 수 있습니다.

**반대로 `explanation` 은 반드시 저장해야 합니다.** 같은 자산이라도 프로필마다 문구가
다릅니다 — 현금성 자산: "급한 상황이나 기회를 위한 여유 자금"(`js:6`) /
"예상치 못한 지출과 추가 투자 여유"(`js:20`) / "기본적인 유동성 확보"(`js:33`).
`asset_name` 만으로 복원할 수 없습니다. 컬럼이 있는 이유가 실측으로 확인됩니다.

### 2.2 신설 4개 요약

| 메서드 | 경로 | 역할 | DB |
| --- | --- | --- | :---: |
| POST | `/api/recommendation/preview` | 판정만. 저장 안 함 | — |
| POST | `/api/recommendation/create` | 판정 + 저장 (트랜잭션) | 쓰기 |
| GET | `/api/recommendation/history` | 내 추천 이력 목록 | 읽기 |
| GET | `/api/recommendation/detail` | 단건 재현 | 읽기 |

**도메인을 `recommendation` 으로 고른 이유**: ⓐ 저장 테이블 이름과 일치
(`테이블-정의서.md:92`) ⓑ `/api/quant/portfolio`(F06 MPT) · `/api/quant/portfolio-scenario`
(F05)와 이름이 섞이지 않습니다. `portfolio` 를 도메인으로 쓰면 셋의 경계가 흐려집니다.

**응답 형태를 기존 A등급 2건에 맞춘 근거** — F04(`main.py:1231~1240`) ·
F05(`quant.py:96~106`) 에서 공통 규칙을 추출했습니다.

| 규칙 | 실측 |
| --- | --- |
| 봉투(`{data:...}`) 없이 **평면 dict** | 둘 다 최상위가 도메인 필드 |
| 키는 **snake_case** | `period_label` · `profile_label` · `chart_points` |
| **한국어 설명 문장을 응답에 포함** | `summary` · `portfolio_hint` · `explanation` |
| 시계열·목록은 **작은 dict 의 배열** | `chart_points[{date,a,b}]` · `points[{year,...}]` |
| 라벨은 **서버가 완성해서** 보냄 | `period_labels`(`main.py:1222`) · `profiles[*].label`(`quant.py:67~69`) |
| 시각은 **ISO 8601 문자열** | `latest_data_at`(`main.py:1227`) · `fetched_at`(`main.py:222`) |

### 2.3 `POST /api/recommendation/preview`

**판정만 하고 저장하지 않습니다.** DB 를 전혀 건드리지 않는 순수 함수입니다.

**왜 필요한가.** ⓐ 진입 시 하드코딩된 `renderProfile('balanced')`(`js:100`)의 우연한
일치에 의존하지 않게 됩니다. ⓑ 방문만 해도 `recommendation` 행이 쌓이는 것을 막습니다.
ⓒ **Supabase 장애 시에도 화면이 동작합니다** — `create` 는 503 이 되지만 `preview` 는
살아 있습니다. 백엔드화 때문에 오늘보다 나빠지는 상황을 피합니다.

**요청**

| 필드 | 타입 | 필수 | 검증 | 근거 |
| --- | --- | :---: | --- | --- |
| `goal` | str | O | `^(growth\|balance\|protect)$` | `js:95` · `테이블-정의서.md:41` |
| `horizon` | str | O | `^(short\|medium\|long)$` | `js:96` · `테이블-정의서.md:42` |
| `risk` | str | O | `^(low\|medium\|high)$` | `js:97` · `테이블-정의서.md:43` |

**셋 다 기본값을 주지 않고 필수로 둡니다.** 설문 답을 서버가 임의로 채우면 판정 근거가
흐려집니다. (`PortfolioScenarioRequest` 가 `profile` 에 기본값을 준 것은 판정 **결과**를
직접 받는 경우라 성격이 다릅니다.)

**응답**

| 필드 | 타입 | 출처 |
| --- | --- | --- |
| `goal` · `horizon` · `risk` | str | 요청 에코 (재현 검증용) |
| `profile` | str | `stable` \| `balanced` \| `growth` |
| `profile_label` | str | `js:3,14,26` |
| `badge` · `intro` · `note` | str | `js:3,14,26` / `js:4,15,27` / `js:11,23,35` |
| `items[].sort_order` | int | 배열 인덱스 (0-based) |
| `items[].asset_name` · `.weight_pct` · `.explanation` | str/int/str | `js:6~9` 등 |
| `total_weight_pct` | int | 서버 합산. 항상 100 |
| `disclaimer` | str | `js:103` 고정 문구 |

`color` 는 응답에 넣지 않습니다 (2.1절 근거).

**에러**: 422 (enum 위반·필드 누락) **뿐입니다.** 외부 I/O 와 DB 가 없으므로 502·503 이
나올 수 없습니다. [CN-017](../00-index/변경이력.md#cn-017) 의 콜드 스타트 대응에도 유리합니다.

### 2.4 `POST /api/recommendation/create`

**판정 + 저장.** `recommendation` 1행과 `recommendation_item` 3~5행을 **한 트랜잭션**으로
넣습니다. 합계 100 검증을 서버 계층에서 하기로 한 결정(`테이블-정의서.md:150~156`)의
구현처가 여기입니다.

**요청** — `preview` 3필드 + `anon_id`

| 필드 | 타입 | 필수 | 검증 |
| --- | --- | :---: | --- |
| `goal` · `horizon` · `risk` | str | O | `preview` 와 동일 |
| `anon_id` | str \| null | **조건부** | `min_length=16, max_length=64`, `^[A-Za-z0-9_-]+$` |

**헤더**: `Authorization: Bearer <Supabase access_token>` (선택).
있으면 검증 후 `sub` 를 `user_id` 로 저장하고 `anon_id` 는 무시합니다.

**소유자 규칙** — `ck_recommendation_owner`(`테이블-정의서.md:112~113`)가 `user_id` 와
`anon_id` 중 하나는 NOT NULL 이길 요구합니다. **토큰도 `anon_id` 도 없으면 400** 으로
막습니다. DB 제약 위반을 500 으로 흘리지 않습니다.

`anon_id` 는 프런트에 이미 있는 `visitorId()` 를 재사용합니다 —
`crypto.randomUUID().replaceAll('-','')` 로 32자를 만들어 localStorage 에 보관합니다.
기준 코드에서는 `app.js:354~367` 의 **모듈 비공개 함수**였고, 뷰가 쓰려면 `app.js` 를
import 해야 해서 순환 참조가 됩니다. **`utils/localState.js:85~96` 으로 옮겼습니다**
(저장 키 `investment_analysis_visitor_id` 는 그대로) → [CN-090](../00-index/변경이력.md#cn-090).

> ⚠ **검증 상한이 기존과 다릅니다.** `POST /api/visitors/heartbeat` 는
> `min_length=16, max_length=80` 인데(`main.py:228`) `recommendation.anon_id` 는
> **≤ 64** 입니다(`테이블-정의서.md:100`). **상한을 80 으로 맞추면 pydantic 을 통과한 값이
> DB 에서 터져 500 이 됩니다.** 그래서 위 표를 `16~64` 로 정했습니다.
>
> **[CN-030](../00-index/변경이력.md#cn-030) 이 (확인 필요)로 남긴 폴백 길이는
> 확인됐고, 고쳤습니다** → [CN-090](../00-index/변경이력.md#cn-090).
> `Math.random().toString(36).slice(2)` 는 길이가 들쭉날쭉하고 `Math.random()` 이 0 이면
> **빈 문자열**이 나옵니다(`"0".slice(2) === ""`). 그러면 폴백 식별자가 8자가 되어
> `min_length=16` 에 걸려 **422** 입니다. 지금은 16자에 못 미치면 채우고 64자에서
> 자릅니다(`utils/localState.js:72~79`). `randomUUID` 경로는 원래대로 32자 고정입니다.

**응답** — `preview` 응답 + 아래 2필드

| 필드 | 타입 | 출처 |
| --- | --- | --- |
| `recommendation_id` | int | `recommendation.id` (`테이블-정의서.md:98`) |
| `created_at` | str | ISO 8601 **UTC**. 표시용 KST 변환은 프런트가 함 (`테이블-정의서.md:27`) |

**에러**

| 코드 | 조건 | `detail` |
| --- | --- | --- |
| 400 | 토큰도 `anon_id` 도 없음 | "로그인하거나 브라우저 식별자를 함께 보내 주세요." |
| 401 | `Authorization` 이 있으나 검증 실패 | "로그인 정보가 유효하지 않습니다. 다시 로그인해 주세요." |
| 422 | enum 위반 / `anon_id` 형식·길이 위반 | FastAPI 표준 |
| 500 | 배분표 합계가 100 이 아님 (서버 상수 손상) | "자산 배분 구성이 올바르지 않습니다." |
| 503 | Supabase 연결·삽입 실패 | "추천 결과를 저장할 수 없습니다. 잠시 후 다시 시도해 주세요." |

**503 을 택하고 "판정만 성공" 으로 눙치지 않는 이유.** F03 백엔드화의 목적 자체가
저장·재현입니다. 저장이 실패했는데 200 을 주면 사용자는 이력에 남았다고 믿습니다.
대신 프런트가 503 을 받으면 `preview` 로 폴백하고 **"결과는 보여드리지만 이력에 저장되지
않았습니다"** 를 표시합니다.

### 2.5 `GET /api/recommendation/history`

확정된 인덱스 2개(`idx_recommendation_user_created` · `idx_recommendation_anon_created`,
`테이블-정의서.md:120~121`)가 정확히 이 조회를 위해 존재합니다.

**요청 (쿼리스트링)**

| 필드 | 타입 | 필수 | 검증 |
| --- | --- | :---: | --- |
| `anon_id` | str | 비로그인 시 O | `min_length=16, max_length=64`, `^[A-Za-z0-9_-]+$` |
| `limit` | int | - | `default=20, ge=1, le=100` |

GET + 쿼리스트링을 쓰는 근거: 기존 조회 전용 엔드포인트가 그 형태입니다
(`/api/market/volume-cloud?market=` — `main.py:1302`).

**토큰이 있으면 `user_id` 기준, 없으면 `anon_id` 기준입니다. 둘을 OR 로 합치지 않습니다** —
비로그인 이력이 로그인 계정에 자동 병합되면 소유 관계가 흐려집니다. 병합이 필요하면
별도 기능으로 다룹니다.

**응답**

| 필드 | 타입 | 설명 |
| --- | --- | --- |
| `total` | int | 반환 행 수 |
| `limit` | int | 적용값 에코 |
| `owner_type` | str | `"user"` \| `"anon"` — 무엇을 기준으로 찾았는지 |
| `items[]` | list | `created_at desc` |
| `items[].recommendation_id` | int | |
| `items[].goal` · `.horizon` · `.risk` | str | 재실행용 |
| `items[].profile` · `.profile_label` | str | |
| `items[].item_count` | int | `recommendation_item` 개수 |
| `items[].created_at` | str | ISO 8601 UTC |

**배분 상세는 목록에 넣지 않습니다** — 20건 × 5행 = 100행을 매번 조인할 이유가 없고,
상세는 `detail` 이 담당합니다.

**에러**: 400 (대상 불명) · 401 (토큰 검증 실패) · 422 (`limit` 범위) · 503 (조회 실패).
**결과 0건은 에러가 아닙니다** — `total: 0`, `items: []` 로 200 을 줍니다.

### 2.6 `GET /api/recommendation/detail`

저장된 스냅샷을 그대로 되살립니다. "저장·재현·검증이 불가능했음"에서 **재현**을 담당합니다.

**요청 (쿼리스트링)**

| 필드 | 타입 | 필수 | 검증 |
| --- | --- | :---: | --- |
| `id` | int | O | `ge=1` |
| `anon_id` | str | 비로그인 시 O | `create` 와 동일 |

경로 파라미터(`/api/recommendation/{id}`) 대신 쿼리를 씁니다 — 51개 라우트 중 경로
파라미터는 `/files/{file_name}`(`ml.py:564`) 단 하나이고 그마저 폐기 대상입니다.

**응답**: `create` 응답과 **완전히 동일한 형태**입니다. 프런트가 렌더 함수 하나
(`renderProfile` 상당, `js:45~61`)를 그대로 재사용할 수 있게 맞춥니다.

단 `total_weight_pct` 는 **100 이 아닐 수 있습니다** — 저장된 행들의 실제 합이며,
감시용 뷰 `v_recommendation_weight_check`(`테이블-정의서.md:160~163`)와 같은 값이므로
그대로 노출합니다.

**에러**

| 코드 | 조건 |
| --- | --- |
| 400 | 토큰도 `anon_id` 도 없음 |
| 401 | 토큰 검증 실패 |
| 403 | 행은 있으나 소유자가 다름 |
| 404 | `id` 에 해당하는 행 없음 |
| 422 | `id` 형식 위반 |
| 503 | Supabase 조회 실패 |

> **403 과 404 를 분리할지는 판단이 필요합니다.** 분리하면 "그 id 는 존재한다" 가 새어
> 나가고, `id` 가 순번 정수(`generated always as identity`, `테이블-정의서.md:98`)라
> 열거가 쉽습니다. 학습용 데이터라 민감도가 낮으므로 **분리(403 유지)를 권하되**,
> 리뷰에서 지적되면 남의 행도 404 로 통일하면 됩니다.

### 2.7 배선 — 엔드포인트만 짜면 화면에 붙지 않습니다

> ✅ **7개 항목 전부 반영됐습니다** (2026-08-10, `44bf0c6`) → [CN-085](../00-index/변경이력.md#cn-085).
> 아래 `손댈 곳` 의 줄 번호는 **기준 코드(`718f161`) 기준**이라 지금 파일과 다릅니다 —
> 실제 등록 위치는 `main.py:121`, 태그·문서는 `openapi_docs.py:16,31~34,85~88`,
> 프런트는 `api.js:59~64` 입니다. 표는 **무엇을 왜 손대야 했는지의 기록**으로 남깁니다.

| # | 손댈 곳 | 내용 |
| --- | --- | --- |
| 1 | `app/backend/routers/recommendation.py` 신설 | `APIRouter(prefix="/api/recommendation", tags=["추천"])`. `backtest_lab.py:40` 이 유일한 prefix 선례인데, 한 도메인만 다루므로 이 방식이 맞습니다 |
| 2 | `app/backend/main.py:116~118` | `app.include_router(recommendation_router)` 추가. 등록이 `116~118` 과 `2682~2683` 두 군데로 갈려 있는데 앞 블록에 붙입니다 |
| 3 | `openapi_docs.py:29~72` | `FRONTEND_API_PATHS` 에 4경로 추가. **안 넣으면 Swagger 에 안 뜹니다** (F04·F05·F27 이 겪는 문제) |
| 4 | `openapi_docs.py:12~21` | `TAG_DESCRIPTIONS` 에 **"추천" 태그 신설.** 기존 8개에 없습니다. "퀀트" 에 얹으면 그 설명(`openapi_docs.py:16`)과 성격이 어긋납니다 |
| 5 | `openapi_docs.py:76~` | `OPERATION_DOCS` 에 `(태그, 한국어 제목, 응답 계약)` 3-튜플 4개 |
| 6 | `app/frontend/js/api.js:36~79` | `api` 객체에 4개 메서드. 조회형 2개는 `marketVolumeCloud`(`api.js:60`)처럼 `encodeURIComponent` 사용 |
| 7 | `views/portfolioGuide.js` | `PROFILES`(`js:1~37`) · `suggestedProfile`(`js:39~43`) · `js:133` 삼항을 **삭제**하고 `renderProfile`(`js:45~61`)이 서버 응답 dict 를 받도록 변경 |

> 7번 삭제가 끝나야 [프로젝트-개요](../10-기획/프로젝트-개요.md) 의 S-02 판정 기준
> ("`views/portfolioGuide.js` 에 `api.` 호출 존재")이 충족됩니다.

**계층 분리**는 라우터 안에서 3단으로 나눕니다 — Controller(`@router.post`) →
Service(판정 함수 + 프로필 상수) → Repository(Supabase 삽입·조회).
`quant.py` 처럼 한 함수에 다 넣지 않습니다. [CN-003](../00-index/변경이력.md#cn-003) 이
합격선에 "계층 분리" 를 넣었고, **F03 이 그 첫 적용 대상**입니다.

### 2.8 남은 설계 이슈 — `badge` · `intro` · `note` 는 저장할 자리가 없습니다

`recommendation` 이 저장하는 표시 문구는 `profile_label` **하나뿐**입니다
(`테이블-정의서.md:105`). 그런데 화면이 출력하는 문구는 넷입니다.

| 문구 | 프런트 | 저장 |
| --- | --- | :---: |
| `title` → `profile_label` | `js:3,14,26` · 렌더 `js:53` | ✅ |
| `badge` | `js:3,14,26` · 렌더 `js:53` | ❌ |
| `intro` | `js:4,15,27` · 렌더 `js:56` | ❌ |
| `note` | `js:11,23,35` · 렌더 `js:59` | ❌ |

**결과.** `detail` 로 과거 추천을 재현할 때 셋은 저장값이 아니라 **현재 서버 상수에서
`profile` 키로 다시 꺼낸 값**입니다. 반면 `items[].explanation` 은 스냅샷입니다
(`테이블-정의서.md:137`). 즉 **한 화면 안에 시점이 다른 두 종류의 문구가 섞입니다.**
문구를 개정하면 옛 추천의 배분 설명은 옛 문구인데 `intro`·`note` 는 새 문구로 나옵니다.

**확정 스키마 안에서는 이게 유일한 방법입니다** — 컬럼 추가는 스키마 변경이라 임의로
하지 않습니다. 문구 개정이 필요해지면 `recommendation` 컬럼 추가와 함께 판단합니다.
→ [CN-031](../00-index/변경이력.md#cn-031)

---

## 3. B등급 요약

### 3.1 F28 · `/api/backtest-lab/*`

라우터 prefix `"/api/backtest-lab"` (`backtest_lab.py:40`).

**`GET /config`** (`backtest_lab.py:232`) — 파라미터 없음. 화면 초기값·프리셋·주의문구.
`hd_core` import 실패 시에도 **200 으로 `available:false`** 를 알리고 `import_error` 에
원인을 담습니다 (`backtest_lab.py:238`).

**`POST /run`** (`backtest_lab.py:251`) — `RunRequest` (`backtest_lab.py:62`)

| 필드 | 기본 | 제약 |
| --- | --- | --- |
| `ticker` | `005380.KS` | `max_length=24`. `_valid_ticker` 가 `A-Za-z0-9.^=-` 만 허용 (`:85~95`) |
| `name` | `현대차` | `max_length=40`. 빈 문자열이면 `meta.name` 에 ticker 대입 (`:208`) |
| `train_start` · `train_end` | `2025-01-01` · `2025-12-31` | `date.fromisoformat` 파싱 (`:76~83`) |
| `test_start` · `test_end` | `2026-01-01` · `2026-06-30` | 위와 동일 |
| `initial_cash` | `100000000` | `ge=1_000_000, le=1_000_000_000_000` |
| `commission_rate` | `0.00015` | `ge=0, le=0.02` |

**날짜 검증 400 이 5갈래입니다** (`backtest_lab.py:118~132`): 학습 시작>종료 ·
검증 시작>종료 · 검증이 학습보다 앞 · 검증 종료가 오늘 이후 · 그 외 구간 정합성.

응답은 `prediction_metrics`(13키) · `feature_importance` · `rows[]`(일별 예측) ·
`simple_backtest`(`curve` 포함) 입니다. **`rows` 와 `curve` 는 DB 에 저장하지 않습니다**
([ERD 0.1절](../30-데이터/ERD.md#01-시세-원본은-db-에-넣지-않는다-제약-c-04)).

**`POST /report`** (`backtest_lab.py:257`) — `run` 과 같은 계산 후 **자체완결 HTML 본문**을
반환하고 `app/generated/backtest-lab/` 에도 사본을 남깁니다.

> ⚠ 디스크 쓰기가 **서버리스에서 실패합니다.** [CN-017](../00-index/변경이력.md#cn-017)
> 과 같은 계열입니다.

**캐시**: `_price_cache` TTL **900초** (`backtest_lab.py:57~58`). 이 저장소에서 **TTL 을
가진 유일한 캐시**입니다.

### 3.2 퀀트 4종

| 엔드포인트 | 요청 필드 (기본 · 제약) | 응답 주요 키 |
| --- | --- | --- |
| `POST /api/quant/backtest`<br>(F08, `quant.py:106`) | `fast_ma` 20 `ge=5,le=60` · `slow_ma` 60 `ge=20,le=200` · `n_days` 1260 `ge=252,le=5040` | `image`(base64) · `metrics.{cagr,sharpe,mdd,win_rate,profit_factor,n_trades,total_return,bh_return}` |
| `POST /api/quant/portfolio`<br>(F06, `quant.py:231`) | `n_simulations` 3000 `ge=500,le=10000` · `risk_free` 0.03 `ge=0,le=0.1` | `image` · `optimal_weights` · `optimal_{return,vol,sharpe}` · `riskparity_weights` |
| `POST /api/quant/risk`<br>(F07, `quant.py:542`) | `confidence` 0.95 `ge=0.90,le=0.99` · `n_scenarios` 10000 `ge=1000,le=100000` · `portfolio_value` 1억 `ge=1_000_000` **상한 없음** | `image` · `var_pct` · `cvar_pct` · `var_amount` · `cvar_amount` |
| `POST /api/quant/pipeline`<br>(F09, `quant.py:605`) | `ticker` `"SPY"` **제약 없음** · `fast_ma` · `slow_ma` | `image` · `metrics.{cagr,sharpe,mdd,ml_accuracy}` |

> ⚠ **`pipeline` 의 `ticker` 는 실제 데이터 조회에 쓰이지 않습니다.** 차트 제목
> (`quant.py:675,702`)과 응답 에코(`quant.py:710`)에만 들어가며 길이·정규식 검증이
> 전혀 없습니다.
>
> ⚠ **`risk` 의 `portfolio_value` 는 상한이 없습니다** (`quant.py:36`). 다른 금액 필드
> (`PortfolioScenarioRequest.initial_amount` = `le=1_000_000_000`)와 대비됩니다.

**네 개 모두 `image` 가 base64 PNG 입니다** ([5절](#5-응답-크기와-vercel-45mb-제한) 참고).

> ⚠ **v2.1 에서 이 네 곳의 `image` 는 `chart_points` 로 바뀝니다** —
> [D-10](../00-index/마스터인덱스.md#2-지금-확정된-설계-결정) 파급, [6절](#6-d-10-파급--차트-응답이-바뀝니다).
> 지표 키(`metrics`·`var_pct` 등)는 그대로입니다.
>
> ⚠ **F07·F08·F09 는 위 요청 필드가 서버에 도달하지 않습니다** —
> 화면이 값을 보내지 않아 항상 기본값으로 계산됩니다
> → [CN-043](../00-index/변경이력.md#cn-043). 표의 제약은 **서버가 받을 준비만 된 상태**입니다.

### 3.3 거시·시장

`POST /api/macro/simulation` (F14, `main.py:1832`) 은 **Field 제약이 없고 핸들러가
조용히 클램프**합니다 — `max(60, min(n_days, 1260))` (`main.py:1850`). 음수나 거대값을
보내도 422 가 아니라 보정됩니다. `seed` 기본 42 로 **재현 가능**합니다 (`main.py:1849`).

`POST /api/macro/realtime`(F13) · `POST /api/macro/kospi-ex`(F15) · `GET /api/home/market-candle`(F01) ·
`GET /api/home/box-range` 는 **실패 시 가짜 데이터를 200 으로 돌려줍니다.**
→ [공통-응답과-에러 3.3절](공통-응답과-에러.md#33-실패를-200-으로-숨기는-곳이-8곳)

### 3.4 산업·DART

`POST /api/dart/company-list` (F21, `main.py:539`) 가 **DART 쿼터의 핵심 위험**입니다.
`_load_all_listed_details()` (`main.py:466`) 를 부르며, 1회 미스에 상장사 N건 ×
`company.json` + (종사자수 필터 시) N건 × `empSttus.json` = **최대 2N건**을 소모합니다.
DART 일일 한도는 20,000건입니다.
→ [공통-응답과-에러 6.2절](공통-응답과-에러.md#62-dart-쿼터--cn-023-의-정량화)

`limit`(≤200) 을 줄여도 **외부 호출량은 줄지 않습니다** — 필터를 다 돌린 뒤에 자르기
때문입니다 (`main.py:574`).

---

## 4. C등급·아카이브·폐기 요약

### 4.1 F26 세무 (`routers/tax.py`)

| 엔드포인트 | 요청 |
| --- | --- |
| `POST /api/tax/upload` (`:144`) | `multipart/form-data`, 파라미터명 `file`. CSV/Excel. **최대 500건** 반환 |
| `GET /api/tax/sample` (`:185`) | 없음 |
| `POST /api/tax/simulate` (`:248`) | `transactions` list[dict] **필수** · `entity_type` `^(individual\|corporate)$` · `tax_year` 2024 `ge=2020,le=2030` · `business_name` · `taxpayer_id` · `vat_registered` true · `standard_deduction` `ge=0` |

> ⚠ `transactions` 가 `list[dict]` 라 **원소 스키마 검증이 없습니다** (`tax.py:13`).
> 핸들러가 `.get()` 으로 읽습니다 (`tax.py:259~263`).
>
> ⚠ `taxpayer_id` 는 **계산에 쓰이지 않고 응답에 그대로 에코**됩니다 (`tax.py:17,341`).
> 사업자·주민번호 성격인데 마스킹·검증 코드가 없습니다. → [CN-032](../00-index/변경이력.md#cn-032)

### 4.2 아카이브 A01~A08

전부 **합성 데이터 실습**입니다. 실제 시장 데이터를 쓰지 않습니다.

| ID | 엔드포인트 | 요청 필드 |
| --- | --- | --- |
| A01 | `POST /api/ml/cross-validation` | `n_samples` 1000 · `n_splits` · `random_state` |
| A02 | `GET /api/ml/decision-boundary` | 없음 (고정 합성 데이터) |
| A03 | `POST /api/ml/random-forest` | `n_estimators` · `max_depth` |
| A04 | `POST /api/ml/kmeans` | `n_clusters` · `n_samples` |
| A05 | `POST /api/ml/svm` | `kernel` · `C` |
| A06 | `POST /api/ml/mlp` | `hidden_layer_sizes` · `max_iter` |
| A07 | `POST /api/ml/linear-regression` | `degree` · `n_samples` · `noise` |
| A08 | `POST /api/nlp/text-classify` | `text` |

**8개 중 차트를 내려주는 것은 5개뿐입니다** (실측 2026-08-10).

| 차트 있음 — `image_base64` | 차트 없음 — 지표만 |
| --- | --- |
| A02 `decision-boundary`(`ml.py:210`) · A04 `kmeans`(`:317`) · A05 `svm`(`:373`) · A06 `mlp`(`:424`) · A07 `linear-regression`(`:478`) | A01 `cross-validation` · A03 `random-forest` · A08 `text-classify` |

```
$ grep -nE '"(image|image_base64)"' app/backend/routers/ml.py | wc -l
5                                                          # 실측 2026-08-10
```

> **이 5곳의 `image_base64` 는 v2.1 에서도 그대로 둡니다.**
> 배포본에서는 라우트째 내리고 **로컬에서만 동작**시키므로 통일할 이유가 없습니다
> ([6.2절](#62-어디가-바뀌고-어디는-그대로인가)).

### 4.3 폐기 X01~X05

**전부 삭제 대상**이므로 요청 스키마를 명세하지 않습니다.

| ID | 엔드포인트 | 무거운 의존성 | 503 조건 |
| --- | --- | --- | --- |
| X01 | `POST /api/dl/cnn-timeseries` | `torch` | `ml.py:581` |
| X02 | `POST /api/dl/lstm-predictor` | `torch` | `ml.py:668` |
| X03 | `POST /api/dl/transformer-timeseries` | `torch` | `ml.py:751` |
| X04 | `POST /api/genai/text-to-image`<br>`GET /files/{file_name}` | `diffusers` + `torch` | `ml.py:544,547` |
| X05 | `POST /api/cv/circle-animation` | `opencv-python-headless` | — |

> **무거운 import 는 전부 함수 안 지연 import 입니다** (`ml.py:544,581,668,751` 이
> `except ImportError → 503`). 모듈 최상단이 아니므로 **패키지만 지우면 라우트는 503 을
> 반환하며 서버는 뜹니다.** 삭제 순서에 여유가 있다는 뜻입니다.

---

## 5. 응답 크기와 Vercel 4.5MB 제한

[CN-019](../00-index/변경이력.md#cn-019) 가 확인한 대로 Vercel 요청·응답 본문 상한은
**4.5MB** 입니다. 응답이 입력에 비례해 커지는 곳을 정리합니다.

| 엔드포인트 | 큰 필드 | 크기 결정 요인 |
| --- | --- | --- |
| `POST /api/rag/search` · `/ask` | `results[].text` · `sources[].text` | **청크 원문 무삭제** × `top_k`(최대 20). 컷이 없음 (`rag.py:90`) |
| `POST /api/backtest-lab/run` | `rows[]` · `simple_backtest.curve` | 검증 구간 거래일 수 |
| `POST /api/backtest-lab/report` | HTML 본문 전체 | 자체완결 HTML (인라인 SVG) |
| `POST /api/market/portfolio-combination` | `chart_points` | `2y` 기준 약 500개 ≈ 30KB. 여유 있음 |
| base64 차트 **16곳** | `image` / `image_base64` | `dpi=130~140` PNG |

**base64 차트를 반환하는 곳은 16곳입니다** — `main.py` 6
(`:738,848,1085,1525,1788,1949`) · `quant.py` 5 (`:224,316,528,595,708`) ·
`ml.py` 5 (`:210,317,373,424,478`). `savefig` 도 같은 16곳입니다.
전부 `BytesIO` 버퍼로 쓰고 디스크를 건드리지 않아 **콜드 스타트에는 안전합니다**
([CN-017](../00-index/변경이력.md#cn-017)).

**압축**: `GZipMiddleware(minimum_size=1024)` (`main.py:93`) 가 1KB 이상 응답을 압축합니다.
base64 PNG 는 이미 압축된 바이너리라 gzip 이득이 작습니다.

> **(확인 필요)** 실제 응답 바이트는 서버를 띄워 측정해야 합니다. 지금은 어느 필드가
> 커지는지만 지목했고, 4.5MB 를 실제로 넘는지는 **첫 배포에서 실측**합니다.
>
> ✅ **다만 이 표의 마지막 줄은 6절 때문에 대부분 사라집니다.**

---

## 6. D-10 파급 — 차트 응답이 바뀝니다

### 6.1 왜 바뀌나

[D-10](../00-index/마스터인덱스.md#2-지금-확정된-설계-결정)([CN-063](../00-index/변경이력.md#cn-063))이
**배포 의존성에서 matplotlib 을 뺐습니다.** X01~X05 를 다 폐기해도 `site-packages` 가
564.5 MB 로 Vercel 상한 500 MB 를 넘었고, matplotlib 계열 91.7 MB 를 빼서
**429.8 MB (86.0 %)** 로 맞췄습니다.

**matplotlib 이 없으면 서버가 PNG 를 만들 수 없습니다.** 따라서 위 16곳 중
배포본에 남는 곳의 응답에서 **`image` 필드가 사라지고, 그 자리에 숫자 시계열이 들어갑니다.**

### 6.2 어디가 바뀌고 어디는 그대로인가

| 묶음 | 곳 | 조치 | 근거 |
| --- | ---: | --- | --- |
| `main.py` — F16×3 · F13 · F14 · F15 | **6** | **프런트 렌더로 이전** | `:742,856,1087,1540,1791,1956` |
| `quant.py` — F08 · F06 · F07 · F09 | **4** | **프런트 렌더로 이전** | `:224,316,595,708` |
| `quant.py` — F24 `financial-knowledge` | 1 | **엔드포인트째 삭제** | [CN-028](../00-index/변경이력.md#cn-028) · `:528` |
| `ml.py` — A01~A08 | **5** | **옮기지 않음 · 로컬 전용** | `:210,317,373,424,478` |
| **이전 대상 합계** | **10** | | |

**아카이브 5곳을 옮기지 않는 이유**: A01~A08 은 제품 기능이 아니고
([기능ID-대장 2절](../00-index/기능ID-대장.md#2-아카이브-a01--a08--sklearn-수업-실습)),
배포본에서 라우트를 내리면 그만입니다. sklearn 은 F28·F09 때문에 어차피 남으므로
([CN-064](../00-index/변경이력.md#cn-064)) **로컬에서는 계속 동작합니다.**

> **A등급 4개는 어느 쪽에도 걸리지 않습니다** — F04(`main.py:1168~1243`) ·
> F05(`quant.py:60~104`) · F27(`rag.py`) 모두 `savefig`·`b64encode` **0건**이고,
> F03 은 [CN-039](../00-index/변경이력.md#cn-039) 신설이라 차트가 없습니다 (실측 2026-08-10).
> **D-10 은 A등급을 건드리지 않습니다.**

### 6.3 새 응답 규칙 — 이미 있는 관례를 따릅니다

새 형식을 발명하지 않습니다. 이 저장소에는 **이미 숫자 시계열을 내려주는 두 응답**이
있고, [공통-응답과-에러 1.2절](공통-응답과-에러.md#12-공통-규칙)이 그것을 규칙으로
적어 뒀습니다 — *"시계열은 작은 dict 의 배열"*.

| 기존 사례 | 형태 | 위치 |
| --- | --- | --- |
| F04 `chart_points` | `[{date, a, b}]` | `main.py:1228,1242` |
| F05 `points` | `[{year, cautious, middle, positive}]` | `quant.py:77` |

**따라서 `image` 를 걷어낸 자리에는 같은 모양을 넣습니다.**

```jsonc
// 이전 — POST /api/quant/backtest (F08)
{ "image": "data:image/png;base64,iVBOR…", "metrics": { "cagr": 0.11, … } }

// 이후
{
  "chart_points": [                       // ← 배열 이름은 F04 와 같은 chart_points
    { "date": "2021-01-04", "equity": 100.0, "benchmark": 100.0 },
    { "date": "2021-01-05", "equity": 100.7, "benchmark": 100.2 }
  ],
  "metrics": { "cagr": 0.11, … }          // ← 지표는 그대로
}
```

| 규칙 | 내용 |
| --- | --- |
| 배열 이름 | **`chart_points`** 로 통일. F04 가 이미 쓰는 이름입니다 |
| 원소 | 작은 평면 dict. 중첩하지 않습니다 |
| x축 키 | 날짜는 **`date`(`YYYY-MM-DD`)**, 그 외는 의미 있는 이름(`year` 등) |
| 여러 계열 | **키를 나눕니다** (`equity`·`benchmark`). 계열별 배열을 따로 두지 않습니다 |
| 지표 | 기존 키(`metrics`·`var_pct` 등)를 **그대로 둡니다.** 바뀌는 것은 그림뿐입니다 |
| 색·축·제목 | **응답에 넣지 않습니다.** UI 테마의 관심사이고, 이미 같은 이유로 `recommendation_item` 에서 색을 뺐습니다 ([`테이블-정의서.md` 4.3절](../30-데이터/테이블-정의서.md#43-recommendation_item--추천-자산-배분-라인)) |

> **다중 패널은 어떻게 하나.** F13 은 지금 **4패널을 PNG 한 장**에 그립니다
> (`main.py:1437~1544`). 패널마다 데이터의 성격이 달라 한 배열에 담기지 않으므로,
> **패널별로 키를 나눕니다** — `chart_points`(가격 추이) · `normalized_points`(정규화
> 누적수익률) · `correlation`(상관행렬) · `period_returns`(기간 수익률).
> [`../20-기능명세/04-거시경제.md` 1.5절](../20-기능명세/04-거시경제.md#15-지금-문제)이
> 지적한 **"패널 1 이 첫 종목만 그린다"** 문제가 이 과정에서 자연히 사라집니다 —
> 축이 겹쳐 생략하던 것이 프런트에서는 제약이 아닙니다.

### 6.4 곁다리 이득 3가지

| # | 이득 | 근거 |
| --- | --- | --- |
| 1 | **[CN-033](../00-index/변경이력.md#cn-033) 이 소멸합니다** | 배포본에 base64 필드가 **0개**가 됩니다. 통일할 대상이 없어집니다 |
| 2 | **응답이 작아집니다** | 5절의 4.5MB 위험에서 `dpi=130` PNG 16곳이 빠집니다. `chart_points` 500개 ≈ 30KB (F04 실측) |
| 3 | **gzip 이 실제로 듣습니다** | base64 PNG 는 이미 압축돼 있어 `GZipMiddleware`(`main.py:93`) 이득이 작았습니다. JSON 숫자 배열은 잘 줄어듭니다 |

### 6.5 대가 — 정직하게 적습니다

| 대가 | 내용 |
| --- | --- |
| **프런트 작업량** | 10곳에 차트 렌더링을 새로 붙여야 합니다. 서버가 그려 주던 것을 이제 브라우저가 그립니다 |
| **차트 라이브러리 선택이 남았습니다** | **(확인 필요)** — `vendor/` 에 mermaid 11.16.0 은 있으나([CN-069](../00-index/변경이력.md#cn-069)) 차트 라이브러리는 없습니다. Chart.js 를 새로 넣을지, SVG 를 직접 그릴지는 **50-UI 구현 단계에서 정합니다** |
| **한글 폰트 문제가 옮겨갑니다** | 서버의 `configure_matplotlib_korean_font`(3벌, [CN-066](../00-index/변경이력.md#cn-066))가 없어지는 대신, **브라우저 폰트로 넘어갑니다.** 이쪽이 더 쉽습니다 |
| **로컬과 배포본의 동작이 갈라집니다** | 로컬 Docker 에는 matplotlib 이 남으므로 `ml.py` 5곳이 동작하고, 배포본에서는 안 합니다. [CN-064](../00-index/변경이력.md#cn-064) 의 "배포용/로컬용 `requirements.txt` 분리" 와 짝입니다 |

> **마지막 줄이 이 결정의 가장 큰 위험입니다.** "Docker 는 되는데 Vercel 은 안 된다" 가
> [CN-064](../00-index/변경이력.md#cn-064) 가 이미 지목한 전형적 사고 지점입니다.
> [테스트-계획](../60-운영/테스트-계획.md)이 **배포용 의존성으로도 스모크 테스트를
> 돌리도록** 잡아야 합니다.
