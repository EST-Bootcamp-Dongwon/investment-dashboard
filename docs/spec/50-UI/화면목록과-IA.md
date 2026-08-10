# 화면 목록과 정보구조 (IA)

> - **버전**: v2.0
> - **최종 수정**: 2026-08-10 (KST)
> - **상태**: 초안
> - **기준 코드**: `main` @ `d4c2fdc`
> - **관련**: [기능ID-대장](../00-index/기능ID-대장.md) ·
>   [CN-018](../00-index/변경이력.md#cn-018) · [CN-012](../00-index/변경이력.md#cn-012) ·
>   [CN-026](../00-index/변경이력.md#cn-026)

---

## 0. 이 문서가 답하는 것

| 질문 | 절 |
| --- | --- |
| 화면이 몇 개이고 어디로 가야 나오는가 | [1절](#1-화면-전수--37개) |
| 왜 32개가 링크 없이 방치돼 있는가 | [2절](#2-지금-문제--링크가-없는-라우트-32개) |
| v2.0 사이드바는 어떻게 생겼는가 | [3절](#3-v20-사이드바-ia--확정) |
| 고아 라우트 2개를 어떻게 할 것인가 | [4절](#4-cn-026-결정--kospi-candle-삭제--box-range-홈에-연결) |
| 화면마다 데이터 출처를 어떻게 밝히는가 | [5절](#5-데이터-출처-배지--신설) |
| 라우터·진입 경로가 실제로 어떻게 동작하는가 | [6절](#6-라우팅-구조) |

**화면 구성 요소·상태·에러 화면은 [화면-상세.md](화면-상세.md)** 가 맡습니다.
여기서는 **"무엇이 있고 어떻게 도달하는가"** 만 다룹니다.

---

## 1. 화면 전수 — 37개

`app.js:51~92` 의 `routes` 객체 **40개** + 별도 페이지 **2개**(F28·F29)가 전부입니다.
그중 5개(X01~X05)는 [폐기](../20-기능명세/99-폐기-기능.md) 대상이므로 v2.0 화면은 **37개**입니다.

```
$ grep -cE "^\s+'[a-z-]+':" app/frontend/js/app.js   # routes 블록만          실측 2026-08-10
40
```

| 구분 | 개수 | 근거 |
| --- | ---: | --- |
| SPA 라우트 | 40 | `app.js:51~92` |
| ─ 제품 기능 (F) | 27 | 40 − 8(A) − 5(X) |
| ─ 아카이브 (A01~A08) | 8 | [기능ID-대장 2절](../00-index/기능ID-대장.md#2-아카이브-a01--a08--sklearn-수업-실습) |
| ─ **폐기 (X01~X05)** | **5** | v2.0 에서 라우트째 제거 |
| 별도 페이지 | 2 | `pages/backtest-lab.html`(F28) · `pages/youtube.html`(F29) |
| **v2.0 화면 합계** | **37** | 27 + 8 + 2 |

### 1.1 전수 목록

`진입` 열은 **지금** 어떻게 도달하는지입니다. `v2.0 위치`는 [3절](#3-v20-사이드바-ia--확정)의 개편안입니다.

| ID | 화면 | 라우트 / 경로 | 등급 | 진입 (현행) | v2.0 위치 |
| --- | --- | --- | :---: | --- | --- |
| F01 | 대시보드 | `home` | B | **사이드바** | 대시보드 |
| F02 | 서버 리소스 모니터 | `server-resources` | C | **사이드바** | 시스템 |
| **F03** | **포트폴리오 추천** | `portfolio-guide` | **A** | **사이드바** | 포트폴리오 |
| **F04** | **포트폴리오 조합** | `portfolio-combination` | **A** | **사이드바** | 포트폴리오 |
| **F05** | **포트폴리오 시뮬레이션** | `portfolio-simulation` | **A** | **사이드바** | 포트폴리오 |
| F06 | 포트폴리오 최적화 (MPT) | `portfolio` | B | ❌ 주소 직접 입력 | 포트폴리오 |
| F07 | 리스크 분석 (VaR) | `risk` | B | ❌ 주소 직접 입력 | 포트폴리오 |
| F08 | 백테스트 엔진 | `backtest` | B | ❌ 주소 직접 입력 | 포트폴리오 |
| F09 | 퀀트 파이프라인 | `pipeline` | B | ❌ 주소 직접 입력 | 포트폴리오 |
| F10 | 거래량 클라우드 | `volume-cloud` | C | **사이드바** | 시장과 시세 |
| F11 | 세계 증시 현황 | `world-markets` | B | **사이드바** | 시장과 시세 |
| F12 | 기술적 분석 실습 | `technical-chart` | B | ❌ 주소 직접 입력 | 시장과 시세 |
| F13 | 거시경제 현황 (실시간) | `macro-realtime` | B | ❌ 주소 직접 입력 | 거시경제 |
| F14 | 거시경제 시뮬레이션 | `macro-simulation` | B | ❌ 주소 직접 입력 | 거시경제 |
| F15 | KOSPI 제외 지수 분석 | `kospi-excluded` | B | ❌ 주소 직접 입력 | 거시경제 |
| F16 | 산업 경쟁력 분석 | `industry-analysis` | B | ❌ 주소 직접 입력 | 산업과 기업 |
| F17 | 기업 파이낸셜 분석 | `company-financial` | B | ❌ 주소 직접 입력 | 산업과 기업 |
| F18 | 재무제표 분석 | `financial-statement` | B | ❌ 주소 직접 입력 | 산업과 기업 |
| F19 | 밸류에이션 실습 | `valuation` | C | ❌ 주소 직접 입력 | 산업과 기업 |
| F20 | DART 상장기업 검색 | `dart-company-search` | B | ❌ 주소 직접 입력 | 산업과 기업 |
| F21 | DART 지역·종사자수 조회 | `dart-region-search` | C | ❌ 주소 직접 입력 | 산업과 기업 |
| F22 | 그룹사 계열사 네트워크 | `group-network` | C | ❌ 주소 직접 입력 | 산업과 기업 |
| F23 | DART 재무 AI 분석 | `dart-financial-analysis` | B | ❌ 주소 직접 입력 | 산업과 기업 |
| F24 | 금융상품·자산배분 학습 | `financial-knowledge` | C | ❌ 주소 직접 입력 | 학습 |
| F25 | 투자 성향 분석 | `investment-tree` | B | ❌ 주소 직접 입력 | 학습 |
| F26 | 세무·회계 시뮬레이션 | `tax-accounting` | C | ❌ 주소 직접 입력 | 학습 |
| **F27** | **AI 투자 도우미 (RAG 챗)** | `rag-chat` | **A** | **사이드바** | AI 도우미 |
| F28 | 백테스트 실험실 (LEAN) | `pages/backtest-lab.html` | B | **사이드바** (`index.html:130`) | 학습 |
| **F29** | **유튜브 학습 자료실** | `pages/youtube.html` | C | ❌ **링크 없음** | **학습** ← [CN-051](../00-index/변경이력.md#cn-051) |
| A01~A08 | sklearn 실습 8종 | `cross-validation` 외 7 | 아카이브 | ❌ 주소 직접 입력 | **실습** |

> **X01~X05 는 이 표에 없습니다.** v2.0 에서 라우트·view 파일·의존성을 함께
> 제거합니다 → [99-폐기-기능.md](../20-기능명세/99-폐기-기능.md).

---

## 2. 지금 문제 — 링크가 없는 라우트 32개

```
$ grep -o 'data-view="[^"]*"' app/frontend/index.html | sort -u | wc -l   # 실측 2026-08-10
8
```

| 항목 | 값 |
| --- | ---: |
| SPA 라우트 | 40 |
| `index.html` 의 `data-view` (클릭 가능) | **8** |
| 정적 페이지 링크 (`pages/backtest-lab.html`, `index.html:130`) | 1 |
| **주소를 직접 쳐야 열리는 라우트** | **32** |

사이드바 8개: `home` · `server-resources` · `world-markets` · `volume-cloud` ·
`portfolio-combination` · `portfolio-guide` · `portfolio-simulation` · `rag-chat`
(`index.html:100~126`).

**요구 4화면(F03·F04·F05·F27)은 전부 사이드바에 있습니다.** IA 의 방향 자체는 맞습니다.
문제는 **그 뒤에 붙어 있어야 할 나머지 24개 제품 기능이 통째로 보이지 않는다**는 것입니다.

### 2.1 코드가 예전 IA 를 기억하고 있습니다 — 새 실측

`app.js:237~245` 는 화면이 속한 사이드바 섹션을 펼치는 로직인데,
**존재하지 않는 섹션 두 개를 참조합니다.**

```javascript
// app/frontend/js/app.js:244~245
if (_practiceViews.includes(view)) activeSections.push('practice');
if (_aiViews.includes(view))       activeSections.push('aitools');
```

```
$ grep -rn "nav-practice\|nav-aitools" app/frontend/          # 실측 2026-08-10
(0건)
$ grep -n "chev-" app/frontend/index.html
107:  <i class="fa-solid fa-chevron-down nav-chev" id="chev-visualization"></i>
```

`sidebarUI.js:6` 의 `MENU_SECTION_ORDER` 도 `['visualization']` 하나뿐입니다.
즉 `_setActiveNavSections(['practice'])` 는 **아무 일도 하지 않고 조용히 끝납니다.**

> **이것을 IA 개편의 근거로 씁니다.** 사이드바에 `practice`(실습)와 `aitools`(AI 도구)
> 섹션이 **있었고**, 그 섹션이 지워지면서 24개 화면이 링크를 잃은 것으로 보는 게
> 자연스럽습니다. `_practiceViews` 배열(`app.js:237~240`)에는 지금도 **27개 라우트**가
> 나열돼 있습니다. **되살릴 대상 목록이 코드 안에 이미 있습니다.**

---

## 3. v2.0 사이드바 IA — 확정

**원칙 3가지.**

1. **제품 · 학습 · 실습을 섞지 않는다.** 수업 실습(A01~A08)이 제품 기능과 같은 층에
   있으면 심사자가 무엇이 결과물인지 판단할 수 없습니다.
2. **[20-기능명세](../20-기능명세/) 의 도메인 구분을 그대로 쓴다.** 문서와 화면의 분류가
   다르면 둘 다 신뢰를 잃습니다.
3. **링크 없는 라우트를 0으로 만든다.** [CN-018](../00-index/변경이력.md#cn-018) 의 해소 조건입니다.

### 3.1 구조

```
대시보드                                          F01

━━ 제품 ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
▾ 포트폴리오                                    7개
    포트폴리오 추천            ★ 필수          F03
    포트폴리오 조합            ★ 필수          F04
    포트폴리오 시뮬레이션      ★ 필수          F05
    ─────────────────────────
    포트폴리오 최적화 (MPT)                     F06
    리스크 분석 (VaR)                           F07
    백테스트 엔진                               F08
    퀀트 파이프라인                             F09
▾ 시장과 시세                                   3개
    세계 증시 현황                              F11
    거래량 클라우드                             F10
    기술적 분석                                 F12
▾ 거시경제                                      3개
    거시경제 현황 (실시간)                      F13
    거시경제 시뮬레이션                         F14
    KOSPI 제외 지수 분석                        F15
▾ 산업과 기업                                   8개
    산업 경쟁력 분석                            F16
    기업 파이낸셜 분석                          F17
    재무제표 분석                               F18
    밸류에이션                                  F19
    DART 상장기업 검색                          F20
    DART 지역·종사자수 조회                     F21
    그룹사 계열사 네트워크                      F22
    DART 재무 분석                              F23
  AI 투자 도우미               ★ 필수          F27

━━ 학습 ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    유튜브 학습 자료실                          F29   ← CN-012 해소
    금융상품·자산배분                           F24
    투자 성향 분석                              F25
    세무·회계 시뮬레이션                        F26
    백테스트 실험실 (LEAN)                      F28

━━ 실습 (수업 잔재) ━━━━━━━━━━━━━━━━━━━━━━━━━
▾ 머신러닝 실습                                 8개
    Cross Validation · Decision Boundary ·
    Random Forest · KMeans · SVM · MLP ·
    선형 회귀 · 텍스트 분류                A01~A08

━━ 시스템 ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    서버 리소스                                 F02
```

### 3.2 검산

| 그룹 | 항목 수 |
| --- | ---: |
| 대시보드 | 1 |
| 제품 — 포트폴리오 | 7 |
| 제품 — 시장과 시세 | 3 |
| 제품 — 거시경제 | 3 |
| 제품 — 산업과 기업 | 8 |
| 제품 — AI 도우미 | 1 |
| 학습 | 5 |
| 실습 | 8 |
| 시스템 | 1 |
| **합계** | **37** |

**37 = 제품 기능 29(F01~F29) + 아카이브 8.** [1절](#1-화면-전수--37개)의 화면 수와 일치합니다.
**링크 없는 라우트 0개** → [CN-018](../00-index/변경이력.md#cn-018) 해소.

### 3.3 결정의 근거

| 결정 | 근거 |
| --- | --- |
| **아카이브 8개를 "실습" 으로 분리** | 사용자 지시 (2026-08-10). [기능ID-대장 2절](../00-index/기능ID-대장.md#2-아카이브-a01--a08--sklearn-수업-실습) 이 이미 "사이드바에서는 실습 섹션으로 분리" 라고 적어 둔 방침 |
| **F03·F04·F05 를 포트폴리오 그룹 맨 위 + 구분선** | 강사님 요구 4화면 중 3개. 구분선 아래(F06~F09)는 [CN-042](../00-index/변경이력.md#cn-042)·[CN-043](../00-index/변경이력.md#cn-043) 때문에 **입력이 서버에 안 닿는 상태**라 같은 신뢰도로 나란히 두면 안 됨 |
| **F27 을 그룹에 넣지 않고 단독** | A등급이고 다른 화면과 성격이 다름(대화형). 현행 사이드바에서도 단독(`index.html:124`) |
| **F29 를 "학습" 맨 위** | [CN-051](../00-index/변경이력.md#cn-051) 에서 살리기로 결정. **10주제·영상 30개**로 학습 그룹에서 콘텐츠 양이 가장 많음 |
| **F28 을 "학습"** | 제품 기능이 아니라 **로컬 전용 실험 도구**([CN-019](../00-index/변경이력.md#cn-019) — Vercel 에 올릴 수 없음). 제품 그룹에 두면 배포본에서 죽은 링크가 됨 |
| **F12 를 "시장과 시세" 에 유지하되 배지 부착** | [CN-047](../00-index/변경이력.md#cn-047) 이 백엔드화를 안 하기로 했으나 계산 대상이 난수. [5절](#5-데이터-출처-배지--신설) 배지로 표시 |
| **F02 를 "시스템" 으로 격리** | 제품 기능이 아니라 운영 화면. 현행은 "데이터 시각화" 섹션에 있어 분류가 틀림(`index.html:110`) |

### 3.4 F29 링크 — 세 번째 결정

**"학습" 그룹의 첫 항목**으로 넣습니다. 근거:

- F28 이 `index.html:130` 과 `sidebar-nav.html:34` **양쪽**에 링크를 갖습니다.
  F29 는 **같은 정적 페이지 구조인데 링크만 없습니다** → [CN-051](../00-index/변경이력.md#cn-051)
- `pages/youtube.html` 은 이미 `#sidebar-nav-slot`(`youtube.html:42`)과
  `includeSidebar.js`(`youtube.html:57`)를 갖추고 있어 **페이지 쪽 준비는 끝나 있습니다.**
- 필요한 변경은 `index.html` 에 `<a class="nav-item" href="pages/youtube.html">` 한 줄과
  `scripts/build_sidebar_partial.py` 의 `EXTERNAL_PAGES` 등록입니다
  (`index.html:127~129` 주석이 그 절차를 설명합니다).

### 3.5 함께 고쳐야 하는 것

| # | 대상 | 조치 |
| --- | --- | --- |
| 1 | `app.js:237~245` `_practiceViews` · `_aiViews` | 새 섹션 ID(`portfolio`·`market`·`macro`·`industry`·`learn`·`lab`)로 재작성 |
| 2 | `sidebarUI.js:6` `MENU_SECTION_ORDER` | `['visualization']` → 새 섹션 순서 |
| 3 | `scripts/build_sidebar_partial.py` | `EXTERNAL_PAGES` 에 `youtube.html` 추가 후 partial 재생성 |
| 4 | `pages/partials/sidebar-nav.html` | **직접 수정 금지.** 3번으로 재생성 (`includeSidebar.js:3~5` 경고) |

---

## 4. CN-026 결정 — `kospi-candle` 삭제 · `box-range` 홈에 연결

[CN-026](../00-index/변경이력.md#cn-026) 이 남긴 마지막 미결입니다. **둘을 나눠서 판단합니다.**

### 4.1 `GET /api/home/kospi-candle` → **삭제**

```python
# app/backend/main.py:2181~2184
@app.get("/api/home/kospi-candle")
def home_kospi_candle(period: str = "3mo") -> dict[str, object]:
    """Backward-compatible KOSPI endpoint for older clients."""
    return home_market_candle("kospi", period)
```

**본문이 `home_market_candle("kospi", period)` 위임 한 줄입니다. 추가로 주는 정보가 0입니다.**

| 확인 | 결과 |
| --- | --- |
| docstring 의 "older clients" 가 실재하는가 | **아니오.** 프런트가 같은 저장소에 있고 단일 배포입니다 |
| 프런트 참조 | **0건** (`grep -rn "kospi-candle" app/frontend/`) |
| `market-candle` 로 대체 가능한가 | **예.** `?market=kospi` 로 같은 응답 |

[CN-028](../00-index/변경이력.md#cn-028) 이 `POST /api/rag/search` 를 지운 것과 **같은 논리**입니다 —
"추가로 주는 정보가 0인데 Swagger·에러 규약·테스트 대상만 늘린다."
`OPERATION_DOCS` 항목(`openapi_docs.py`)도 함께 지웁니다.

### 4.2 `GET /api/home/box-range` → **홈에 연결**

**이쪽은 성격이 다릅니다. 홈이 지금 주지 못하는 정보를 줍니다.**

```python
# app/backend/main.py:2256~2271
box_high = max(bar["h"] for bar in ohlcv)
box_low  = min(bar["l"] for bar in ohlcv)
upper_pct    = round((box_high - last_close) / last_close * 100, 2)
lower_pct    = round((last_close - box_low)  / last_close * 100, 2)
position_pct = round((last_close - box_low)  / box_range   * 100, 2)
```

| 판단 기준 | 결과 |
| --- | --- |
| 홈의 기존 화면과 중복되는가 | ❌ 아니오. 홈은 캔들·MA20·거래량만 그림 (`home.js:158~173`) |
| 비전공자에게 읽히는가 | ✅ **"최근 3개월 범위의 어디쯤"** 은 지수 절대값보다 직관적 |
| 붙이는 비용 | 백엔드 **0** (이미 동작). `HOME_MARKETS` 설정을 그대로 씀 |
| 지금 그대로 붙여도 되는가 | ❌ **아니오.** [4.3](#43-연결-전에-반드시-고칠-것) 참고 |

**결정.** 홈의 시장 카드 4개(`home.js:30~54` `chartCard`) 하단에
**박스권 위치 막대**를 한 줄 추가합니다. 화면 사양은
[화면-상세 1절](화면-상세.md#1-f01--대시보드-홈)에 있습니다.

### 4.3 연결 전에 반드시 고칠 것

```python
# app/backend/main.py:2207   ← 실패해도 200 + 난수
is_simulated = True
...
# main.py:2229~2251           ← LCG 난수로 OHLCV 를 만들어 반환
```

`box-range` 는 [CN-035](../00-index/변경이력.md#cn-035) 가 지목한 **난수 폴백 4곳 중 네 번째**입니다.
[CN-041](../00-index/변경이력.md#cn-041) 이 "표시할 화면 자체가 없다" 고 적었는데,
**연결하는 순간 화면이 생기므로 이 면제가 사라집니다.**

| # | 조치 | 이유 |
| --- | --- | --- |
| 1 | 실패 시 난수 폴백 대신 **502 반환** | [CN-036](../00-index/변경이력.md#cn-036) 코드 정책("외부 실패 → 502/503 통일") |
| 2 | 폴백을 남긴다면 **배너로 승격** | [화면-상세 2절](화면-상세.md#2-is_simulated-배너--f01-1순위)의 공통 배너 사용 |
| 3 | 데이터 출처를 **KRX 로 이관** | [CN-045](../00-index/변경이력.md#cn-045) — yfinance 429 가 폴백의 원인 |
| 4 | `openapi_docs.py` 화이트리스트에 등록 | [CN-025](../00-index/변경이력.md#cn-025) 의 누락 8건 중 하나 |

**1번을 채택합니다.** 폴백을 남기는 것보다 지우는 쪽이 싸고, R-07 과도 어긋나지 않습니다.

### 4.4 라우트 수 변화

| 시점 | 라우트 | 근거 |
| --- | ---: | --- |
| 현행 | 51 | [마스터인덱스 4.2절](../00-index/마스터인덱스.md#4-코드-실측치-2026-08-07-기준) |
| [CN-028](../00-index/변경이력.md#cn-028) 반영 후 | 49 | `rag/search` · `quant/financial-knowledge` 삭제 |
| **CN-026 결정 반영 후** | **48** | `home/kospi-candle` 삭제 |
| [CN-039](../00-index/변경이력.md#cn-039) F03 신설 4개 반영 후 | **52** | `recommendation/*` |

> **기능ID-대장 1.1절을 고쳐야 합니다.** F01 의 백엔드가 `market-candle` + `snapshot` +
> **`box-range`** 3개가 됩니다. `kospi-candle` 은 목록에서 사라집니다.

---

## 5. 데이터 출처 배지 — 신설

### 5.1 왜 필요한가

이 프로젝트에서 **화면이 보여주는 숫자의 출처는 세 갈래**인데, 지금은 화면마다
표기 방식이 제각각입니다.

| 사례 | 지금 표기 | 문제 |
| --- | --- | --- |
| F08 백테스트 | "GBM으로 시뮬레이션된 가격" (`backtest.js:9`) | ✅ 밝힘 |
| F09 파이프라인 | "1. 데이터 생성 (GBM 시뮬레이션)" (`pipeline.js:15`) | ✅ 밝힘 |
| **F07 리스크 분석** | "정규분포 및 **역사적 시뮬레이션**을 통해" (`risk.js:8`) | ❌ **실제 이력처럼 읽힘** → [CN-042](../00-index/변경이력.md#cn-042) |
| **F12 기술적 분석** | "삼성전자 / 005930.KS / 71,000" (`technicalChart.js:642`) | ❌ **난수에 실존 이름표** → [CN-047](../00-index/변경이력.md#cn-047) |
| **F16 산업 분석** | 없음 | ❌ **8탭 중 4탭이 상수인데 구분 없음** |

**F16 실측** (2026-08-10):

```
$ grep -n "api\." app/frontend/js/views/industryAnalysis.js
126:  api.industryPorter     ①
291:  api.industryPeer       ③
514:  api.industrySector     ⑥
602:  api.industryLifecycle  ⑦
```

탭 8개(`industryAnalysis.js:48~57`) 중 **API 를 부르는 것은 4개**입니다.
나머지 4개는 화면 안 상수입니다 — `KPI_DATA`(`:158`) ② ·
`renderNewsMemo`(`:347`) ④ · `PEST_DEFAULTS`(`:397`) ⑤ · `SWOT_DEFAULTS`(`:630`) ⑧.

### 5.2 배지 3종 — 확정

| 배지 | 뜻 | 색 토큰 | 표시 조건 |
| --- | --- | --- | --- |
| **실시간** | 외부 API 에서 이번 요청에 받아온 값 | `--badge-live` | 응답 `is_simulated !== true` |
| **학습용 상수** | 코드에 고정된 값 또는 시드 고정 난수 | `--badge-static` | 서버 호출이 없거나 시드 고정 |
| **직접 입력** | 사용자가 넣은 가정값 | `--badge-input` | 계산 입력이 전부 화면 입력 |

색 정의는 [디자인-토큰 4.3절](디자인-토큰.md#43-데이터-출처-배지)에 있습니다.

**표시 위치**: 화면 제목(`h1`) 오른쪽. 탭이 있는 화면(F16·F12)은 **탭마다** 붙입니다.
한 화면에 성격이 섞이면 화면 단위 배지가 거짓말이 되기 때문입니다.

### 5.3 화면별 배지 배정

| ID | 화면 | 배지 | 근거 |
| --- | --- | --- | --- |
| F01 | 대시보드 | 실시간 | `market-candle`·`snapshot` (`home.js:130,204`) |
| F02 | 서버 리소스 | 실시간 | `/api/system/resources` |
| **F03** | 포트폴리오 추천 | **학습용 상수 + 직접 입력** | 프론트 상수 (`portfolioGuide.js:1~40`) |
| **F04** | 포트폴리오 조합 | **실시간** | yfinance 실가격 |
| **F05** | 포트폴리오 시뮬레이션 | **학습용 상수 + 직접 입력** | 수익·변동성 가정 상수 |
| F06 | 포트폴리오 최적화 | 학습용 상수 | `quant.py:240~250` 하드코딩 |
| F07 | 리스크 분석 | **학습용 상수** | `rng.normal(...)` 시드 42 (`quant.py:551~553`) |
| F08 | 백테스트 엔진 | 학습용 상수 | GBM 시드 42 (`quant.py:117~125`) |
| F09 | 퀀트 파이프라인 | 학습용 상수 | 시드 42 (`quant.py:619~625`) |
| F10 | 거래량 클라우드 | 실시간 | `/api/market/volume-cloud` |
| F11 | 세계 증시 현황 | 실시간 | `/api/market/snapshot` |
| **F12** | 기술적 분석 | **학습용 상수** | 시나리오 난수 (`technicalChart.js:642`) |
| F13 | 거시경제 현황 | 실시간 | `/api/macro/realtime` |
| F14 | 거시경제 시뮬레이션 | 학습용 상수 | GBM |
| F15 | KOSPI 제외 지수 | **실시간 + 학습용 상수** | 시세는 실시간, 가중치 28종 하드코딩([CN-045](../00-index/변경이력.md#cn-045)) |
| **F16** | 산업 경쟁력 분석 | **탭별** ①③⑥⑦ 실시간 / ②④⑤⑧ 학습용 상수 | [5.1](#51-왜-필요한가) 실측 |
| F17 | 기업 파이낸셜 분석 | 실시간 | DART |
| F18 | 재무제표 분석 | 학습용 상수 | 상수 배열 (`financialStatement.js:1~193`) |
| F19 | 밸류에이션 | 직접 입력 | 전부 사용자 가정 |
| F20~F23 | DART 4종 | 실시간 | DART API |
| F24 | 금융상품·자산배분 | 학습용 상수 + 직접 입력 | 프론트 계산기 |
| F25 | 투자 성향 분석 | 학습용 상수 | 트리 상수 (`investmentTree.js`) |
| F26 | 세무·회계 | 직접 입력 | 엑셀 업로드 |
| F27 | AI 투자 도우미 | 실시간 | 문서 색인 검색 |
| F28 | 백테스트 실험실 | 실시간 | LEAN 실데이터 |
| F29 | 유튜브 자료실 | 학습용 상수 | 정적 JSON (2026-08-03 크롤링) |
| A01~A08 | 실습 8종 | 학습용 상수 | 실습 더미 |

**집계**: 실시간 11 · 학습용 상수 12(+아카이브 8) · 직접 입력 2 · 혼합 5.
**즉 제품 화면 29개 중 12개가 상수인데 지금은 그중 2개만 밝힙니다.**

---

## 6. 라우팅 구조

### 6.1 SPA — 해시가 아니라 클릭 핸들러

```javascript
// app/frontend/js/app.js:264~269
document.querySelectorAll('.nav-item[data-view], .sidebar-link[data-view]').forEach(a => {
  a.addEventListener('click', (e) => { e.preventDefault(); navigate(a.dataset.view); });
});
// app.js:395~396
const requestedView = new URLSearchParams(window.location.search).get('view');
navigate(requestedView && routes[requestedView] ? requestedView : 'home');
```

| 특성 | 값 | 영향 |
| --- | --- | --- |
| 주소 형식 | `?view=<라우트>` (쿼리스트링) | 링크 공유 가능 |
| **화면 전환 시 주소 갱신** | **하지 않음** (`history.pushState` 0건) | **뒤로가기가 홈으로 나감** · 새로고침하면 홈 |
| 없는 `view` 값 | `routes['home']` 폴백 (`app.js:215,396`) | 404 화면 없음 |

> **`pushState` 미사용은 v2.0 에서 고칩니다.** 심사자가 화면을 옮겨 다니다
> 뒤로가기를 누르면 작업이 통째로 날아갑니다. 조치는
> [화면-상세 8.2절](화면-상세.md#82-라우팅-보완)에 있습니다.

### 6.2 정적 페이지(MPA) — 사이드바를 fetch 로 주입

`pages/*.html` 은 SPA 밖이라 사이드바를 `partials/sidebar-nav.html` 에서 받아옵니다
(`includeSidebar.js:8~20`). 실패하면 "메뉴를 불러오지 못했습니다 + 대시보드로 이동"
링크를 대신 넣습니다(`includeSidebar.js:16~19`) — **이 저장소에서 유일한 명시적 폴백 UI 입니다.**

| 페이지 | `data-page` | 스타일 |
| --- | --- | --- |
| `pages/backtest-lab.html` | `backtest-lab` (`:14`) | `../styles.css?v=10` (`:10`) |
| `pages/youtube.html` | `youtube` (`:13`) | `../styles.css?v=10` (`:10`) |
| `index.html` | — | `styles.css?v=13` (`:10`) |

> ⚠ **캐시 버스터가 어긋나 있습니다** — SPA 는 `v=13`, 정적 페이지 둘은 `v=10`.
> 같은 파일을 서로 다른 키로 캐시하므로 **스타일 수정이 정적 페이지에 안 먹는 시간**이
> 생깁니다 → [CN-062](../00-index/변경이력.md#cn-062).

### 6.3 전역 UI 부품 3개

사이드바와 함께 **모든 페이지에 주입**되는 요소입니다. 어느 기능 ID 에도 속하지 않습니다.

| 부품 | 위치 | 역할 | 판단 |
| --- | --- | --- | --- |
| 상단 티커 (KOSPI·NASDAQ·USD/KRW) | `index.html:62~73` · `app.js:312~352` | 30초마다 `POST /api/market/snapshot` | 유지 |
| 방문자 수 배지 | `index.html:75~77` · `app.js:370~380` | 30초마다 heartbeat | 유지 |
| **플로팅 챗봇** | `sidebarUI.js:28~80` | **질문하면 "Enterprise 버전입니다." 만 답함** | **[7절](#7-정리해야-할-ui-잔재) 참고** |

---

## 7. 정리해야 할 UI 잔재

IA 를 확정하면서 **동작하지 않거나 오해를 부르는 UI** 를 함께 실측했습니다.

| # | 잔재 | 근거 | 조치 |
| --- | --- | --- | --- |
| 1 | **플로팅 챗봇이 가짜** | `sidebarUI.js:70~78` — 어떤 질문에도 `'Enterprise 버전입니다.'` 를 반환 | **제거하고 F27 로 보내는 버튼으로 교체** → [CN-059](../00-index/변경이력.md#cn-059) |
| 2 | **`vendor/mermaid.min.js` 가 없는 파일** | `index.html:152` 가 로드하는데 `app/frontend/vendor/` **폴더 자체가 없음**. git 추적 0건 | 개념 모달에 mermaid 를 쓸 것이므로 **파일을 넣는다** → [개념설명-모달-사양 6절](개념설명-모달-사양.md#6-mermaid-도입) |
| 3 | **`#breadcrumb` 엘리먼트 없음** | `app.js:45,234` 가 참조하나 `index.html` 에 없음 (`grep` 실측) | 새 IA 는 2단(그룹 > 화면)이라 **빵부스러기를 실제로 넣는다** |
| 4 | **`.mermaid-*` CSS 15개 규칙이 미사용** | `styles.css:591~634`. JS 참조 0건 | 2번과 함께 되살림 |
| 5 | **엔터프라이즈 로그인 게이트** | `index.html:18~28` — "회원가입/로그인은 엔터프라이즈 요금제 가입 고객에게 제공" | **[D-05](../00-index/마스터인덱스.md#2-지금-확정된-설계-결정) Supabase 인증과 충돌.** 인증 도입 시 제거 |

> 1·5 는 **같은 성격의 문제**입니다 — 있지도 않은 상용 서비스의 흔적이
> 제품 UI 에 남아 있습니다. 심사에서 "이건 왜 눌러도 안 되나요" 로 바로 드러납니다.

---

## 8. 남은 확인 사항

| # | 확인할 것 | 상태 |
| --- | --- | --- |
| U-01 | `scripts/build_sidebar_partial.py` 의 `EXTERNAL_PAGES` 형식 | ✅ **해소** → [8.1](#81-u-01-해소--partial-생성-스크립트-실측) |
| U-02 | 새 IA 의 섹션 5개를 전부 펼쳤을 때 사이드바 세로 길이가 1080p 에 들어가는가 | **(확인 필요)** — 실기기 확인 |
| U-03 | `?view=` 를 `pushState` 로 바꿀 때 정적 페이지 왕복(`../index.html?view=...`)이 깨지지 않는가 | **(확인 필요)** |

### 8.1 U-01 해소 — partial 생성 스크립트 실측

```python
# scripts/build_sidebar_partial.py:19~22                        확인 2026-08-10
EXTERNAL_PAGES: dict[str, str] = {
    "backtest-lab.html": "backtest-lab",
}
```

F29 를 넣으려면 **`"youtube.html": "youtube"` 한 줄**을 추가하고
`python3 scripts/build_sidebar_partial.py` 를 실행하면 됩니다.
`pages/youtube.html:13` 이 이미 `data-page="youtube"` 를 갖고 있어 활성 표시도 바로 맞습니다
(`includeSidebar.js:27~33`).

> ⚠ **새 섹션을 만들 때의 제약.** 스크립트는 `<a class="nav-item …" data-view="…">`
> 패턴에만 `href` 를 보강합니다(`build_sidebar_partial.py:40`).
> `class` 속성이 `nav-item` 으로 **시작하지 않으면 정적 페이지에서 링크가 죽습니다.**
> 3절의 새 사이드바를 작성할 때 이 순서를 지켜야 합니다.
