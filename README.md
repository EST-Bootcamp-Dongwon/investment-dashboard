# investment-dashboard

**포트폴리오 분석·추천·시뮬레이션 웹앱** — 개인 프로젝트입니다.

강사님의 [edumgt/investment-analysis](https://github.com/edumgt/investment-analysis)를
기반으로 가져와, 학습·퀴즈 기능을 걷어내고 **포트폴리오 도메인 중심으로 다시 설계**하는
것이 목표입니다.

> **출처와 라이선스는 [NOTICE.md](NOTICE.md)를 반드시 먼저 읽으세요.**
> 원본에 LICENSE 파일이 없어 제3자 재사용에는 원저작자 허가가 필요합니다.

---

## 1. 지금 상태

| 단계 | 내용 | 상태 |
| --- | --- | --- |
| v1.0 | 강사님 원본을 가져와 제외 기능 정리 (= 기획서 v1.0 기준선) | ✅ 완료 (2026-08-07) |
| v2.0 | 기획서·설계서 재작성, 기능별 명세 분리, 버전 관리 체계 수립 | ⏳ 진행 예정 |

**v1.0 코드는 강사님 원본 그대로입니다.** 제외 기능을 걷어낸 것 외에는 손대지 않았고,
이는 v2.0 설계 변경분을 diff 로 명확히 구분하기 위한 의도입니다.

## 2. 기술 스택

| 계층 | 사용 기술 |
| --- | --- |
| 백엔드 | Python 3.12, FastAPI, Uvicorn |
| 프런트엔드 | 바닐라 JS ES Modules (빌드 도구 없음), ApexCharts, Mermaid, Font Awesome |
| 데이터 | yfinance, pykrx, OpenDART, pandas / numpy |
| 분석 | scikit-learn, PyTorch, Diffusers, OpenCV, matplotlib |
| 검색 | Qdrant (문서 검색 RAG, 의존성 없는 해시 임베딩 384차원) |
| 백테스트 | QuantConnect LEAN (별도 Compose 구성) |
| 실행 | Docker Compose |

프런트엔드에 번들러·프레임워크가 없습니다. `index.html`이 `js/app.js`를 ES Module 로
직접 불러오고, `app.js`의 `routes` 객체가 해시 없는 쿼리스트링(`?view=...`) 라우터 역할을 합니다.

## 3. 화면 구성

사이드바에 노출되는 메뉴입니다.

| 메뉴 | 뷰 ID | 호출 API |
| --- | --- | --- |
| 대시보드 | `home` | `/api/home/market-candle`, `/api/home/kospi-candle`, `/api/home/box-range` |
| 데이터 시각화 › 서버 리소스 | `server-resources` | `/api/system/resources` |
| 데이터 시각화 › 세계증시현황 | `world-markets` | `/api/market/snapshot` |
| 데이터 시각화 › 거래량 클라우드 | `volume-cloud` | `/api/market/volume-cloud` |
| **포트폴리오 조합** | `portfolio-combination` | `/api/market/portfolio-combination` |
| **포트폴리오 추천** | `portfolio-guide` | (없음 · 프런트엔드 전용) |
| **포트폴리오 시뮬레이션** | `portfolio-simulation` | `/api/quant/portfolio-scenario` |
| 문서 검색 채팅 | `rag-chat` | `/api/rag/search`, `/api/rag/ask`, `/api/rag/status` |

> **사이드바에 없는 라우트가 30여 개 더 있습니다.** 밸류에이션·기술적 분석·DART 재무 AI 분석·
> 산업 경쟁력 분석·세무 시뮬레이션·ML/DL 실습 등이 `app.js`의 `routes`에 등록되어 있고
> `?view=<id>`로 직접 접근하면 동작합니다. 원본에서 메뉴만 정리된 상태이며, v2.0 에서
> 어떤 것을 살리고 버릴지 결정합니다. 전체 목록은 `app/frontend/js/app.js`의 `routes` 를 보세요.

## 4. 실행하기

### 4.1 Docker Compose (권장)

준비물: Docker Desktop(Windows·macOS) 또는 Docker Engine + Compose 플러그인(Linux).
사용 포트: `8000`, `6333`, `6334`.

```bash
docker compose up --build -d
```

<http://localhost:8000> 을 엽니다. 상태 확인은 <http://localhost:8000/api/health>,
API 명세는 <http://localhost:8000/docs> 입니다.

포트가 겹치면 저장소 루트에 `.env` 를 만들어 바꿉니다.

```dotenv
APP_PORT=8080
QDRANT_PORT=6335
QDRANT_GRPC_PORT=6336

# 선택 사항: 공시·재무 분석 기능
DART_API_KEY=
```

문서 검색을 쓰려면 `docs/` 를 Qdrant 에 색인합니다. `docs/*.md` 를 수정한 뒤에도 다시 실행합니다.

```bash
docker compose --profile tools run --rm docs-index
```

종료합니다.

```bash
docker compose down       # 데이터 유지
docker compose down -v    # Qdrant 색인까지 삭제
```

### 4.2 Python 으로 직접 실행

```bash
python3 -m venv .venv
source .venv/bin/activate          # Windows PowerShell: .venv\Scripts\Activate.ps1
pip install -r requirements.txt

cp app/backend/.env.example app/backend/.env   # PowerShell: Copy-Item ...
uvicorn app.backend.main:app --host 0.0.0.0 --port 8000 --reload
```

Qdrant 만 컨테이너로 띄우고 백엔드는 로컬에서 돌릴 수도 있습니다.

```bash
docker compose up -d qdrant
QDRANT_URL=http://localhost:6333 ./scripts/upload_docs_to_qdrant.sh
```

`requirements.txt` 에 PyTorch·Diffusers·OpenCV 가 포함되어 설치가 오래 걸리고 용량도 큽니다.
ML/DL 실습 화면을 쓰지 않는다면 해당 줄을 지우고 설치해도 나머지 화면은 동작합니다.

### 4.3 환경 변수

`app/backend/.env` 를 읽습니다. **`.env` 는 절대 커밋하지 마세요. 이 저장소는 Public 입니다.**

| 변수 | 필요한 기능 | 없으면 |
| --- | --- | --- |
| `QDRANT_URL` | 문서 검색 | RAG API 가 `503` |
| `QDRANT_COLLECTION` | 문서 검색 | 색인 명령과 같은 값을 유지해야 합니다 |
| `DART_API_KEY` | 기업·공시 분석 | DART 관련 API 가 `503` |
| `DIFFUSERS_MODEL_ID` | 텍스트-이미지 생성 | 기본 모델을 사용합니다 |

## 5. LEAN 백테스트 (별도 구성)

웹앱과 독립적으로 QuantConnect LEAN 기반 삼성전자(`005930.KS`) 일봉 예제를 실행합니다.
웹앱 Compose 를 띄우지 않아도 됩니다.

```bash
docker compose -f docker-compose.lean.yml run --build --rm samsung-backtest
```

결과는 `lean-results/` 에 생성됩니다(`.gitignore` 대상 — 재실행으로 언제든 다시 만듭니다).
기간을 바꾸려면 다음처럼 실행합니다.

```bash
SAMSUNG_START_DATE=2023-01-01 SAMSUNG_END_DATE=2024-01-01 \
  docker compose -f docker-compose.lean.yml run --rm samsung-backtest
```

첫 실행은 `quantconnect/lean` 베이스 이미지(10GB 이상)를 받아야 하므로 오래 걸립니다.
Custom Data 기반 동작 예제이므로 **KRX 수수료·세금·호가단위·배당·환율 모델이 없습니다.**
숫자를 실투자 수익률로 해석하면 안 됩니다.

## 6. 저장소 구조

```text
app/
  backend/
    main.py            # 2,700줄 단일 모듈 — DART·산업·시장·거시 API 가 모두 여기 있다
    openapi_docs.py    # Swagger 에 노출할 경로 화이트리스트 + 한국어 설명
    routers/
      quant.py         # 백테스트·포트폴리오·리스크·파이프라인
      ml.py            # ML/DL·NLP·CV 실습
      tax.py           # 세무·회계 시뮬레이션
      rag.py           # Qdrant 문서 검색
  frontend/
    index.html         # SPA 셸 + 사이드바 원본
    js/
      app.js           # 라우터 + 화면 전환 (routes 객체가 진입점)
      api.js           # fetch 래퍼 + 엔드포인트 목록
      views/*.js       # 화면 1개 = 모듈 1개 (47개)
      utils/           # 차트 헬퍼, localStorage 폼 상태
    pages/partials/    # 정적 페이지용 사이드바 (build_sidebar_partial.py 가 생성)
  src/                 # 참고용 파이썬 클래스 (Backtest·PortfolioOptimizer·RiskManager)
docs/                  # 학습 문서 Markdown — 화면에서 읽지 않고 RAG 색인 원본으로만 쓴다
lean-samsung/          # LEAN 백테스트 이미지·전략·설정
scripts/               # 사이드바 생성, RAG 색인, 크롤러
test/                  # 강사님 실습 스크립트 (앱과 무관)
```

`app/frontend/pages/partials/sidebar-nav.html` 은 **직접 고치지 않습니다.**
`index.html` 의 `<nav class="sidebar-nav">` 를 고친 뒤 아래를 실행해 재생성합니다.

```bash
python3 scripts/build_sidebar_partial.py
```

## 7. 주의 사항

- 이 앱은 **교육·학습 목적**입니다. 투자 권유가 아니며 실제 주문 기능도 없습니다.
- 시세·공시 데이터는 외부 공급자 상태에 따라 지연되거나 달라질 수 있습니다.
- 세무 시뮬레이션은 단순화된 교육용 계산입니다. 실제 신고에 사용하면 안 됩니다.
- 저장소가 **Public** 이므로 API 키·개인정보·데이터 원본을 커밋하지 않습니다.
