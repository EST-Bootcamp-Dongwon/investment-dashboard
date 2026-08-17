# ADR-DB-0002: 차트 라이브러리를 ApexCharts 하나로 유지하고, 캔들 성능 실측에서만 예외를 둔다

## 상태

채택됨 (2026-08-16)

## 맥락

**이 레포는 이미 ApexCharts 를 쓰고 있다.** 05 리서치는 이 사실을 모른 채 다섯 개
후보(Lightweight Charts · ECharts · uPlot · Plotly.js · Chart.js)를 비교하고
Lightweight Charts 를 권장했다. 비교표에 **현행 채택본이 없다**
(`research/05-dashboard-검증완료.md` P0-5).

```html
<!-- app/frontend/index.html:151 -->
<script src="https://cdn.jsdelivr.net/npm/apexcharts@3.54.0/dist/apexcharts.min.js"></script>
```

### 실측 — 차트 경로가 넷이다

05 검증본은 3종 병존이라고 적었다. **넷이다.** 이번 세션에서 네 번째를 찾았다.

| # | 경로 | 무엇 | 위치 | 소비자 |
|---|---|---|---|---|
| 1 | **ApexCharts 3.54.0 (CDN)** | 인터랙티브 차트 | `index.html:151` | `js/app.js` · `views/home.js` · `views/serverResources.js` · `views/volumeCloud.js` · `views/technicalChart.js` · `views/worldMarkets.js` |
| 2 | Canvas 2D 수제 | 재무 차트 | `js/utils/financialCharts.js` | `views/companyFinancial.js` · `views/dartCompanySearch.js` |
| 3 | **인라인 SVG 수제** ★신규 발견 | 백테스트 실험실 라인차트 | `js/pages/backtest-lab.js:34~83` (`lineChart()`) | 같은 파일 |
| 4 | matplotlib PNG | 서버사이드 정적 | `app/backend/charting.py` | 라우터 |

**3번이 결정적이다.** `pages/backtest-lab.html` 은 ApexCharts CDN 을 **로드하지 않는다**
(`grep` 실측: 해당 파일에 apexcharts 0건). 그래서 백테스트 화면은 `polyline` 을 문자열로
조립한 정적 SVG 를 쓴다 — 다중 시리즈는 되지만(`series[].name/color/dashed`)
**줌·팬·툴팁이 없다.**

그런데 그 화면이 **대시보드의 1순위 화면**이다. `api-contract.md` §10 이
`GET /api/v1/backtests?run_ids=A,B,C` 다중 비교를 "★대시보드 1순위" 로 못 박았고,
05 검증본 §5.4 가 그 화면에 필요한 것을 "다중 시리즈 라인 + **줌**" 으로 적었다.
**지금 그 요구를 못 채우는 유일한 경로가 3번이다.**

### 배포가 이 결정을 좁힌다

`docs/spec/60-운영/배포-전략.md` §3.4 는 Vercel 500MB 함수 상한 때문에
**matplotlib 을 배포본에서 뺀다**고 확정했다(시나리오 ③, 429.8MB). 서버 렌더 차트
실질 10곳이 프런트 렌더로 이전된다. 즉 **4번 경로는 배포본에서 사라지고 로컬·배치
전용으로 남는다.** 프런트 차트 라이브러리 선택이 그만큼 더 무거워졌다.

### ADR-DB-0001 이 후보를 미리 걸러 놓았다

[ADR-DB-0001](0001-vanilla-js-and-no-typescript.md) 결정 3번: *"CDN `<script>` 한 줄로
붙는가"* 가 탈락 조건이다. Recharts 등 React 전용은 이 조건에서 자동 탈락한다.
ApexCharts 는 이미 그 조건을 만족한 채 붙어 있다.

## 결정

**라이브러리 순위표를 만들지 않는다. 화면 단위로 판정한다.**
질문은 하나다 — *"이 화면을 빼면 무엇을 설명할 수 없는가."*

| 화면 | 무엇을 설명하는가 | 필요한 것 | 판정 |
|---|---|---|---|
| 에쿼티 커브 `run_id` 다중 비교 | "전략 A 가 B 보다 낫다" | 다중 시리즈 라인 + 줌 | **ApexCharts 로 옮긴다** (결정 2) |
| 드로다운 / 롤링 샤프 | "언제 얼마나 아팠나" | 영역 + 라인 | ApexCharts 로 된다 |
| 캔들 + 거래 마커 | "이 신호가 어디서 났나" | 캔들 + 마커 + 대용량 팬/줌 | **실측 후 결정** (결정 3) |
| 팩터 IC 히트맵 | "팩터가 언제 죽었나" | 히트맵 | ApexCharts 로 된다 |
| 정적 리포트 PNG | 발표자료·README 썸네일 | matplotlib | 로컬 전용으로 유지 (결정 5) |

1. **기본은 현행 ApexCharts 3.54.0 유지다.** 이미 CDN 한 줄로 붙어 있고 6개 뷰가
   쓰고 있다. **교체에는 근거가 필요하고, 유지에는 필요 없다.**
2. **`pages/backtest-lab.html` 에 ApexCharts CDN 한 줄을 추가하고, `lineChart()`
   수제 SVG 를 ApexCharts 로 흡수한다.** 다섯 번째 라이브러리를 들이지 않는다.
   흡수 전까지 수제 SVG 는 그대로 둔다 — 지금 동작하고 있다.
3. **캔들 화면에서 실측으로 막히면 그때만 Lightweight Charts 를 *추가*한다 (교체
   아님).** 판정 기준은 하나다 — **`2,460일 × 1종목` 렌더 + 팬/줌이 체감 가능한가.**
   (2,460 은 10년 일봉 1종목의 행 수다 — api-contract §4.4 의 근거값.)
   이 실측을 하기 전에는 어느 쪽도 채택하지 않는다.
4. **Plotly.js · ECharts · uPlot · Chart.js 는 후보에서 뺀다.** 셋째 라이브러리를
   더하면 브라우저 다운로드가 늘고, 유지 논거를 이길 근거가 "범용성" 뿐이다.
5. **`js/utils/financialCharts.js`(Canvas 수제)는 소비자 2곳을 ApexCharts 로 흡수한 뒤
   삭제를 목표로 둔다. 지금 지우지 않는다.**
6. **matplotlib(`app/backend/charting.py`)은 삭제하지 않고 로컬·배치 전용으로 남긴다.**
   `lean-hyundai/make_report.py` 와 아카이브 A01~A08 이 로컬에서 계속 쓴다
   (배포-전략 §3.5 주석). 한글 폰트(`Dockerfile:7` `fonts-nanum`)를 **빼지 않는다** —
   빼면 빌드도 되고 컨테이너도 뜨고 차트도 그려지는데 한글 라벨만 □ 가 된다.

## 근거

| # | 근거 | 출처 유형 | 위치 |
|---|---|---|---|
| 1 | ApexCharts 3.54.0 이 CDN 한 줄로 이미 붙어 있고 6개 뷰가 쓴다 | 레포 실측 | `index.html:151` · `grep -rl ApexCharts js/` |
| 2 | 백테스트 화면은 ApexCharts 를 로드하지 않고 수제 SVG 를 쓴다 (줌·팬 없음) | 레포 실측 | `pages/backtest-lab.html` · `js/pages/backtest-lab.js:34~83` |
| 3 | `run_id` 다중 비교가 대시보드 1순위 화면이다 | 계약 | `quant-contract/docs/contracts/api-contract.md` §10 |
| 4 | 10년 일봉 1종목 = 약 2,460행 → 캔들 성능 판정 기준값 | 계약 | 같은 문서 §4.4 |
| 5 | CDN 한 줄이 아니면 탈락 | 확정 결정 | [ADR-DB-0001](0001-vanilla-js-and-no-typescript.md) 결정 3 |
| 6 | matplotlib 은 배포본에서 빠지고 로컬 전용으로 남는다 | 실측 설계문서 | `docs/spec/60-운영/배포-전략.md` §3.4·§3.5 |

**🔍 이 ADR 이 근거로 쓰지 않은 것.** ApexCharts 3.54.0 의 라이선스 원문과
대용량 캔들 성능은 **직접 확인하지 않았다.** 05 검증본이 웹 조회 없이 작성됐고
(`research/05-dashboard-검증완료.md` 머리말), 이번 세션도 마찬가지다.
결정 3번의 실측이 그 확인을 겸한다. **그 전에 캔들 화면을 확정 처리하지 말 것.**

05 원본의 5종 비교표는 이 ADR 의 근거가 아니다 — 현행 채택본이 빠져 있어
"왜 ApexCharts 를 버리는가" 를 설명하지 못하기 때문이다(P0-5). Lightweight Charts 의
로고·워터마크 표시 의무 조항도 미확인으로 남아 있다(05 검증본 §9).

## 결과

**쉬워지는 것**

- 차트 코드가 한 곳으로 모인다. 지금은 같은 "라인 차트" 가 세 벌(ApexCharts · Canvas ·
  수제 SVG)이라 스타일·툴팁·색상 규칙이 셋 다 다르다.
- 브라우저 다운로드가 안 늘어난다. ApexCharts 는 이미 받고 있다.
- 백테스트 화면에 줌·팬이 생긴다 — 1순위 화면의 실제 요구.

**어려워지는 것**

- **`lineChart()` 흡수가 공짜가 아니다.** 수제 SVG 는 `viewBox` 기반이라 인쇄·캡처에서
  깨지지 않는다. ApexCharts 는 렌더 후 DOM 이므로 리포트 캡처 경로를 다시 봐야 한다.
- **캔들 성능이 미확인인 채로 남는다.** 결정 3번은 판단을 미루는 조치다. 실측 전까지
  캔들 화면의 완료를 선언할 수 없다.
- **다섯 번째 라이브러리를 못 들인다는 뜻이 아니다.** 결정 3번이 예외 경로다. 다만
  그 예외는 *추가*이고 *교체*가 아니므로, 두 라이브러리를 동시에 유지하는 비용을
  그때 받아들여야 한다.

## 참고

- 05 원본의 ADR-004 제목은 "왜 TradingView Lightweight Charts 를 선택했는가" 였다.
  현행 채택본을 몰랐기 때문이고, 검증에서 제목을 교체했다(05 검증본 §5.4).
- BI 도구 선택(Power BI vs Tableau)은 ADR-DB-0003 이며 08 리서치 이후다. 이 ADR 의
  범위가 아니다.
