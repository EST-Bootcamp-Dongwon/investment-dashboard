# ADR-DB-0003: 포트폴리오 최적화·리스크는 이 레포 안에서 완성한다

## 상태

채택됨 (2026-08-17) — `ADR-PF-*` 스코프를 흡수한다

> ⚠️ **2026-09-15 갱신** — `backtest-service`·`quant-core` 는 개발하지 않기로 해
> 제거됐다. 이 ADR 이 이관 대상·역할 수행처로 지목한 부분(결정 3번,
> "결과" 절의 `quant-core` 언급)은 폐기됐고, `Backtest.py`·`indicators.py` 는
> 이 저장소에 남는다. 나머지 결정(1·2·4·5번)은 그대로 유효하다.

## 맥락

CONTEXT rev.6 까지의 계획은 **`portfolio-service` 를 별도 레포로 신설**하고,
이 레포의 `app/src/PortfolioOptimizer.py`(MVO · Risk Parity)와
`app/src/RiskManager.py`(VaR · CVaR)를 그쪽으로 옮기는 것이었다.

**그 계획은 이 레포에 무엇이 있는지 모르고 세워졌다.** 실측하면 포트폴리오 기능이
계산부터 화면까지 **이미 다 있다.**

| 있는 것 | 경로 |
|---|---|
| 포트폴리오 화면 4종 | `app/frontend/js/views/portfolio.js` · `portfolioCombination.js` · `portfolioGuide.js` · `portfolioSimulation.js` |
| 리스크 화면 | `app/frontend/js/views/risk.js` |
| 최적화 계산 | `app/src/PortfolioOptimizer.py` (MVO · Risk Parity) |
| 리스크 계산 | `app/src/RiskManager.py` (VaR · CVaR) |
| 백엔드 라우터 | `app/backend/routers/quant.py` · `simulation.py` · `combination.py` · `recommendation.py` |

`portfolio-service` 계획은 이 중 **계산 코드 두 개만 뽑아** FastAPI 로 감싸는
것이었다. 그러면 남은 화면 다섯 개가 **자기 계산을 잃고 다른 서비스를 HTTP 로
호출해야 한다.** 돌아가는 완성품 하나가 반쪽 둘이 된다.

### 왜 그런 계획이 나왔는가

분할 기준이 **"9월 팀 프로젝트에 조립하기 좋게"** 였기 때문이다. 그 전제 자체가
사실과 달랐다 — 팀 프로젝트는 2주짜리 하나가 아니라 **2주 × 3개 = 6주 점진 확장**이고,
강사님 방침은 *"완성품을 가져오는 게 아니라 각자 만든 것을 융합"* 이다.

즉 **개인 프로젝트의 완성도를 낮추는 방향의 분할이었다.**

## 결정

1. **`portfolio-service` 를 폐기한다.** 저장소를 만들지 않고 폴더도 두지 않는다.
2. `PortfolioOptimizer.py` · `RiskManager.py` 는 **이 레포에 남는다.** 최적화와
   리스크는 여기서 완성한다.
3. 이 레포에서 **다른 모듈로 나가는 것은 둘뿐이다** — `app/src/Backtest.py` →
   `backtest-service`, `app/backend/indicators.py` → `quant-core`.
4. `ADR-PF-*` 스코프는 폐기하고 그 결정들을 `ADR-DB-*` 가 흡수한다.
5. 분할 기준을 **"AI 퀀트 모델 개발의 기능 단위"** 로 바꾼다. "팀원이 붙으면"·
   "융합 요건"은 **기능을 더하거나 빼는 근거가 되지 않는다.**

## 근거

- **레포 실측 (2026-08-17).** 위 표의 아홉 경로가 전부 실재한다.
- **`research/06-프로젝트-구조-재설계.md` §1.3** — 같은 결론을 독립적으로 냈다.
- **CONTEXT rev.7 §3 · §10** — `portfolio-service` 를 폐기 항목으로 확정했다.
- 강사님 방침(CONTEXT §1) — 완성품 이식이 아니라 각자 만든 것의 융합이다.

## 결과

**쉬워지는 것.** 포트폴리오 화면 다섯 개가 자기 계산을 그대로 쓴다. HTTP 왕복도,
두 레포 사이의 스키마 동기화도 없다. `docker compose up` 한 번으로 끝까지 돈다 —
그게 이 프로젝트의 완료 조건이다.

**어려워지는 것.** 팀이 최적화 로직만 따로 쓰고 싶어지면 그때 꺼내야 한다.
다만 그건 **꺼낼 수 있는 상태로 두면 되는 일**이고, 미리 쪼개 둘 이유가 아니다.
`quant-core` 가 이미 그 역할(pip 라이브러리)을 맡고 있다.

**남는 숙제.** 같은 계산이 `app/src/*.py` 와 `app/backend/services/*.py` 두 곳에
있는지 정리해야 한다 — **같은 계산이 두 곳에 있으면 반드시 갈라진다.**
