# ADR-DB-0004: skfolio 는 교차검증 기준선이고, 이 레포의 구현이 정본이다

## 상태

채택됨 (2026-08-17)

## 맥락

`skfolio`(BSD-3, arXiv:2507.04176)는 `MeanRisk`(MVO) · `HierarchicalRiskParity` ·
CVaR · `CombinatorialPurgedCV` 를 한꺼번에 제공한다. 이 레포의
`PortfolioOptimizer.py`(MVO · Risk Parity)와 `RiskManager.py`(VaR · CVaR)가
하는 일과 **겹친다.**

그래서 "직접 구현을 걷어내고 skfolio 로 갈아탄다" 는 선택지가 자연스럽게 보인다.
CONTEXT rev.6 까지는 이 판단이 열려 있었다.

**갈아타면 안 된다.** 이 프로젝트에서 최적화·리스크 구현은 **산출물 그 자체**다.
1차 팀 프로젝트 주제가 *"나만의 투자 전략 기반 종목 선정·비중 결정·리밸런싱"* 이고,
면접에서 설명해야 하는 것도 라이브러리 호출이 아니라 그 계산이다. 라이브러리로
대체하면 남는 것이 `import` 한 줄이다.

동시에, **직접 구현이 맞는지는 따로 확인해야 한다.** 검증 없는 자작 구현은
자작이라서 좋은 게 아니라 그냥 틀릴 수 있는 것이다.

## 결정

1. **`PortfolioOptimizer.py` · `RiskManager.py` 의 구현이 정본이다.** skfolio 로
   대체하지 않는다.
2. **`skfolio` 는 교차검증 기준선으로만 쓴다.** 같은 입력으로 `MeanRisk` ·
   `HierarchicalRiskParity` 를 돌려 이 레포의 결과와 대조한다.
3. **결과를 `docs/explanation/cross-validation-with-skfolio.md` 에 남긴다 —
   일치든 불일치든 남긴다.** 불일치가 나오면 그 원인을 적는다. 대조를 돌리고
   결과를 안 적으면 대조를 안 한 것과 같다.
4. skfolio 는 **개발·검증 의존성**이다. 배포 번들(`requirements.txt`)에 넣지 않는다
   (배포-전략 §3.4 — 번들 432MB / 한도의 86.4%).

## 근거

- **강사님 방침(CONTEXT §1)** — 만든 것을 융합한다. 가져다 쓰는 게 아니다.
- **`research/06-프로젝트-구조-재설계.md` §1.3** — skfolio 교차검증 계획의 이 판단을
  `investment-dashboard` 소관으로 옮겼다.
- **CONTEXT §4** — skfolio 는 BSD-3 라 라이선스 부담이 없다. 쓰지 못할 이유는
  라이선스가 아니라 **산출물의 정체성**이다.
- CONTEXT §9 미해결 항목 *"이 레포의 MVO/Risk Parity 결과 vs skfolio `MeanRisk`
  교차검증"* 이 이 ADR 로 닫힌다.

## 결과

**쉬워지는 것.** 직접 구현이 맞다는 근거가 문서로 남는다. 면접에서 "왜 직접
구현했나" 와 "그게 맞다는 걸 어떻게 아나" 에 둘 다 답할 수 있다.

**어려워지는 것.** 대조 코드를 따로 써야 하고, 두 구현의 전제(공분산 추정 방식·
제약 조건·리밸런싱 주기)를 맞추는 데 시간이 든다. **전제가 다르면 결과가 달라도
버그가 아니므로**, 대조 문서에 전제를 먼저 적어야 한다.

**함정.** skfolio 를 배포 번들에 넣으면 500MB 한도를 건드린다. 개발 의존성으로만
둔다(`requirements-dev.txt`).
