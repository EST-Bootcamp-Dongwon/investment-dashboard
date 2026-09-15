# bi — BI 도구 산출물

> ⚠️ **이건 서비스가 아니다.** Docker에도 Vercel에도 들어가지 않는다.
> CSV 한 장을 읽는 별도 산출물이다.

## 계약

**공급원이 없어졌다 (2026-09-15).** CSV 를 내보내기로 했던 `factor-service`·
`backtest-service` 는 저장소를 만들지 않고 개발하지 않기로 하면서 제거됐다.

```
(폐기된 계획)
factor-service    GET /factors/eval/export?format=csv   → data/exports/factor_eval_*.csv
backtest-service  GET /backtests/{run_id}/export        → data/exports/backtest_*.csv
```

**입력 공급원 미정.** 이 저장소(`investment-dashboard`) 자체에는 현재 CSV 를
내보내는 기능이 없다 — `POST /api/backtest-lab/report`(`app/backend/routers/backtest_lab.py:302`)는
HTML 리포트를 반환할 뿐이다. BI 대시보드를 실제로 만들 때 CSV 내보내기를 이 저장소에
새로 둘지 함께 정한다.

BI 도구가 죽어도 서비스는 살아 있어야 한다. CI 독립성 원칙과 같은 논리다.

## 만들 대시보드

| # | 화면 | 원천 | 슬라이서 |
|---|---|---|---|
| 1 | **팩터 평가** — Rank IC 시계열 · ICIR · 분위별 누적수익 · 턴오버 · 팩터 상관 히트맵 | `factor_eval` | `factor_name` · `generator_id` · 기간 |
| 2 | **백테스트 성과** — 에쿼티 커브 · 드로다운 · 롤링 샤프 · 월별 수익 히트맵 | `backtest_*` | `run_id` · `strategy` |
| 3 | **거래비용 분해** — 연도별 세율 변화 × 회전율 × 성과 영향 | `backtest_*` | 기간 · 시장 |

**1번이 가장 중요하다.** Alphalens 티어시트는 업계 리서치 리포트의 표준 포맷이고,
`factor_name`을 슬라이서로 두면 **팀원이 generator를 추가해도 BI를 안 건드린다.**

## 도구 선택 (🔍 미확정)

| 도구 | 상태 |
|---|---|
| Power BI Desktop | 🔍 웹 게시에 유료 라이선스·조직 계정이 필요한지 확인 필요 |
| Tableau Public | 🔍 저장 시 데이터가 공개됨. KRX·DART 재배포 조건 확인 전 업로드 금지 |

**결정 전 반드시 확인할 것**: `프롬프트/08-bi-시각화.md`의 A·B 항목.

## 파일 배치 (예정)

```
bi/
├── README.md
├── powerbi/       *.pbix (용량 확인 후 커밋 여부 결정)
├── tableau/       *.twbx
├── screenshots/   README·포트폴리오용 이미지 ← 이건 반드시 커밋
└── how-to-reproduce.md   CSV 생성 → 데이터 소스 연결 → 측정값 정의
```
