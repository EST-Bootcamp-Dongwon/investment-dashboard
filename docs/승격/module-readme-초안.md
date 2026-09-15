# investment-dashboard — 모듈 README 초안

> ⚠️ 이 파일은 **초안**이다. 레포 루트의 `README.md`는 아직
> `investment-portfolio-site` 시절 내용이라 덮어쓰지 않았다.
> 승격이 확정되면 이 내용을 루트 `README.md`로 올리고 기존 내용을 흡수하세요.

> ①을 **개명 승격**한 포트폴리오·리스크 분석 대시보드 + BI 산출물 (2026-08-16, `git mv`).
> 복사본이 아니라 같은 저장소이고 히스토리가 이어진다.
> 신규 개발이 아니라 **데이터 계층 교체**가 핵심이다.

## 🔒 프론트 스택 확정 — vanilla JS 유지

강사님 방침: **프론트는 가볍게. HTML 수준으로 가거나, 파이썬으로 백엔드를 잘.**

| 항목 | 결정 |
|---|---|
| 프레임워크 | **vanilla JS 유지.** Next.js·React 전환 안 함 |
| 타입 | 필요하면 JSDoc + `checkJs`. TypeScript 도입 안 함(빌드 단계가 생김) |
| 서버 렌더링 | 필요하면 **FastAPI + Jinja2까지**. Django 신규 도입 안 함(③이 이미 Django) |
| 차트 라이브러리 | **CDN `<script>` 한 줄로 붙는 것만** 후보 |

①은 `app/frontend/index.html` + `styles.css` + `js/{components,views,pages,utils,data}`
구조이고 **빌드 단계가 없다.** 이 상태를 유지하는 것이 CI 비의존 원칙(팀원이 클론 후
5분 안에 실행)과도 맞는다.

## 세 갈래 시각화

| 갈래 | 무엇 | 위치 | 배포 |
|---|---|---|---|
| ① 제품 화면 | FastAPI + Jinja2 + vanilla JS | `app/` `static/` | ✅ Vercel |
| ② 분석 리포트 | matplotlib·plotly 정적 산출 | `reports/figures/` | README·발표자료 |
| ③ BI 도구 | Power BI / Tableau | `bi/` | ❌ 서비스 아님 |

③은 **CSV 파일 한 장으로만** 서비스와 연결된다. 아키텍처 안에 넣지 않는다.

## 왜 이게 팀 구성 협상 카드인가

팀 프로젝트에서 프론트를 새로 만들면 3~4일이 날아간다. 이미 있다.
**"제가 프론트 준비했으니 여기에 붙이세요"** 가 되면 협상력이 생긴다.
그러려면 **팀원 누구의 백엔드에도 꽂히는** 구조여야 하고, 그게 목서버 + OpenAPI 계약이다.

## 승격 시 정리할 것

> ⚠️ **2026-09-15 갱신** — `quant-core`·`backtest-service` 는 개발하지 않기로 해
> 제거됐다. 아래 이관 계획은 폐기됐고 코드는 이 저장소에 남는다.

이 레포는 세 모듈로 갈라진다. **지금 지우지 말고, 각 모듈 착수 시 복사한 뒤 정리한다.**

| 현재 위치 | 갈 곳 | 시점 |
|---|---|---|
| `app/frontend/*` | **여기 남는다** | — |
| `app/backend/main.py` · `charting.py` · `routers/` · `openapi_docs.py` | **여기 남는다** | — |
| `app/backend/indicators.py` | `quant-core/indicators/` | 2차 |
| `app/backend/services/backtest.py` · `combination.py` · `recommendation.py` | `backtest-service/` | 2차 |
| `app/backend/services/simulation.py` | **여기 남는다** | — |
| `app/src/PortfolioOptimizer.py` · `RiskManager.py` | **여기 남는다** | — |
| `app/src/Backtest.py` | `backtest-service/` | 2차 |
| `app/src/OpenCVCPU.py` | **폐기** | 지금 |
| `app/backend/services/rag.py`(해시 임베딩) · `clients/rag_llm.py`(유료 LLM) | **폐기** | 지금 |

- [ ] 루트 `README.md`를 `docs/승격/module-readme-초안.md`로 교체
- [ ] `NOTICE.md`에 `docs/승격/notice-추가분.md` 내용 병합
- [ ] `requirements.txt`에서 **torch · diffusers · opencv-python-headless 제거**
- [ ] `lean-*` 폴더 5개(`lean-cli` · `lean-results` · `lean-hyundai` 등) — 유지 여부 결정
- [ ] `docs/` 하위 강의 자료(`03.md`~`11.md` · `spec/` · `voca.md` · xlsx) Diátaxis 재배치
- [ ] `.env` 커밋 여부 확인 (Public 저장소)
