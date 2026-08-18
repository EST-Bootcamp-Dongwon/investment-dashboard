/**
 * 백테스트 엔진 (F08) — MA 크로스오버.
 *
 * ## 서버 PNG 한 장에서 ApexCharts 세 장으로 (2026-08-17)
 *
 * 이 화면은 `<img src="${data.image}">` 한 줄로 260KB짜리 matplotlib PNG 를 받아
 * 그렸다. 바뀐 이유는 둘이다.
 *
 *  1. **배포본에 matplotlib 이 없다.** 500MB 한도 안에 들어가려면 빼야 하고
 *     (`requirements.txt` 머리말), 빼면 이 화면이 503 이 됐다.
 *  2. 계약 §8.6 의 판정 기준 — *"사용자가 상호작용해야 하는가"*. 에쿼티 커브를
 *     구간별로 확대해 보는 것은 그림으로 안 된다.
 *
 * 서버는 이제 숫자만 준다(`services/quant_charts.backtest`). 계산은 한 줄도 바뀌지
 * 않았고 `metrics` 값도 그대로다 — 옮긴 것은 **그리는 위치**뿐이다.
 *
 * ## 곁다리로 고친 것 ★
 *
 * 이 화면은 `short_ma`·`long_ma`·`initial_capital`·`volatility` 를 보내고 있었는데
 * **백엔드가 받는 이름은 `fast_ma`·`slow_ma`·`n_days` 셋뿐이다**
 * (`routers/quant.py:20~23`). Pydantic 은 모르는 필드를 조용히 버리므로, **MA 입력
 * 두 칸이 아무 일도 하지 않고 있었다** — 무엇을 넣든 서버는 기본값 20/60 으로 돌렸다.
 * 화면을 다시 쓰는 김에 이름을 맞췄고, 서버가 안 받는 두 칸(초기자본·변동성)은 지웠다.
 * 있지도 않은 손잡이를 남겨 두면 다음 사람이 또 속는다.
 */
import { api } from '../api.js';
import { cloudResourceCard } from './cloudAiResources.js';

const FONT = 'Pretendard, -apple-system, "Malgun Gothic", sans-serif';
// 서버 차트(`services/quant_charts.py:70~73`)가 쓰던 값 그대로다. 색이 달라지면
// "옮겼다" 가 아니라 "바꿨다" 가 된다.
const PANEL = '#1e293b';
const TEXT = '#e2e8f0';
const MUTED = '#94a3b8';
const GRID = '#334155';

function baseOptions(height) {
  return {
    chart: {
      // ⚠️ `'transparent'` 를 쓰면 안 된다. ApexCharts 3.54 는 그 값을 넘겨도
      // `.apexcharts-canvas` 를 흰색으로 칠해, 어두운 패널 안에 흰 블록이 남는다
      // (2026-08-17 브라우저 실측). 원본 matplotlib 의 어두운 배경을 지키려면
      // 패널과 같은 색을 **명시**해야 한다.
      height, background: PANEL, fontFamily: FONT,
      // 줌·팬이 이번 이전의 목적이다. 끄면 PNG 와 다를 것이 없다.
      toolbar: { show: true, tools: { download: false, pan: true, reset: true } },
      zoom: { enabled: true, type: 'x', autoScaleYaxis: true },
      animations: { enabled: false },
    },
    theme: { mode: 'dark' },
    grid: { borderColor: GRID, strokeDashArray: 3 },
    dataLabels: { enabled: false },
    stroke: { curve: 'straight' },
    legend: { labels: { colors: TEXT }, fontSize: '12px' },
    xaxis: {
      type: 'datetime',
      labels: { style: { colors: MUTED, fontSize: '11px' } },
      axisBorder: { color: GRID }, axisTicks: { color: GRID },
    },
    tooltip: { theme: 'dark', x: { format: 'yyyy-MM-dd' } },
  };
}

/** `[날짜]` 와 `[값]` 두 배열을 ApexCharts 의 `{x, y}` 로 짝짓는다. */
function pair(dates, values) {
  return dates.map((date, i) => ({ x: date, y: values[i] }));
}

function priceOptions(series, params) {
  const { dates } = series;
  return {
    ...baseOptions(320),
    series: [
      { name: '주가', data: pair(dates, series.close) },
      { name: `MA${params.fast_ma}`, data: pair(dates, series.ma_fast) },
      { name: `MA${params.slow_ma}`, data: pair(dates, series.ma_slow) },
    ],
    colors: ['#64748b', '#3b82f6', '#f97316'],
    stroke: { curve: 'straight', width: [1, 1.8, 1.8] },
    yaxis: { labels: { style: { colors: MUTED, fontSize: '11px' }, formatter: (v) => v?.toFixed(0) } },
    // 매수·매도 시점. 원본 차트의 ▲▼ scatter 두 줄에 대응한다.
    annotations: {
      points: [
        ...series.buy_points.map((p) => marker(p, '#22c55e', '매수')),
        ...series.sell_points.map((p) => marker(p, '#ef4444', '매도')),
      ],
    },
  };
}

function marker(point, color, label) {
  return {
    x: new Date(point.date).getTime(), y: point.price,
    marker: { size: 5, fillColor: color, strokeColor: color },
    label: { text: label, borderColor: color, offsetY: 0,
             style: { background: color, color: '#0f172a', fontSize: '10px', fontWeight: 700 } },
  };
}

function cumulativeOptions(series, metrics) {
  const pct = (v) => `${v >= 0 ? '+' : ''}${(v * 100).toFixed(1)}%`;
  return {
    ...baseOptions(300),
    series: [
      { name: `전략 (${pct(metrics.total_return)})`, data: pair(series.dates, series.strategy_cum) },
      { name: `Buy & Hold (${pct(metrics.bh_return)})`, data: pair(series.dates, series.buyhold_cum) },
    ],
    colors: ['#3b82f6', '#94a3b8'],
    stroke: { curve: 'straight', width: 2, dashArray: [0, 5] },
    yaxis: { labels: { style: { colors: MUTED, fontSize: '11px' }, formatter: (v) => v?.toFixed(2) } },
    // 원본의 `axhline(1.0)` — 원금 회수선이다.
    annotations: { yaxis: [{ y: 1, borderColor: '#475569', strokeDashArray: 0 }] },
  };
}

function drawdownOptions(series) {
  return {
    ...baseOptions(240),
    chart: { ...baseOptions(240).chart, type: 'area' },
    series: [{ name: '낙폭', data: pair(series.dates, series.drawdown_pct) }],
    colors: ['#ef4444'],
    fill: { type: 'solid', opacity: 0.45 },
    stroke: { curve: 'straight', width: 1 },
    yaxis: { labels: { style: { colors: MUTED, fontSize: '11px' }, formatter: (v) => `${v?.toFixed(0)}%` } },
    legend: { show: false },
  };
}

// 원본 차트 오른쪽 아래의 표(`ax4.table`)다. 그림 안의 글자였던 것이 DOM 이 되면서
// 복사·확대·스크린리더가 전부 가능해진다.
const METRIC_ROWS = [
  ['전략 총수익률', (m) => `${m.total_return >= 0 ? '+' : ''}${(m.total_return * 100).toFixed(1)}%`, (m) => m.total_return],
  ['B&H 수익률', (m) => `${m.bh_return >= 0 ? '+' : ''}${(m.bh_return * 100).toFixed(1)}%`, (m) => m.bh_return],
  ['CAGR', (m) => `${m.cagr >= 0 ? '+' : ''}${(m.cagr * 100).toFixed(2)}%`, (m) => m.cagr],
  ['Sharpe', (m) => m.sharpe.toFixed(2), (m) => m.sharpe],
  ['MDD', (m) => `${(m.mdd * 100).toFixed(1)}%`, (m) => m.mdd],
  ['승률', (m) => `${(m.win_rate * 100).toFixed(1)}%`, () => 0],
  ['손익비', (m) => m.profit_factor.toFixed(2), (m) => m.profit_factor - 1],
  ['거래횟수', (m) => `${m.n_trades}회`, () => 0],
];

function metricsMarkup(metrics) {
  return `<div style="display:grid; grid-template-columns:repeat(auto-fill,minmax(140px,1fr)); gap:12px; margin-top:16px;">
    ${METRIC_ROWS.map(([label, format, sign]) => {
      const value = sign(metrics);
      const color = value > 0 ? '#22c55e' : value < 0 ? '#ef4444' : TEXT;
      return `<div class="metric-box">
        <div style="font-size:0.7rem; color:#64748b; text-transform:uppercase; margin-bottom:4px;">${label}</div>
        <div style="font-size:1rem; font-weight:700; color:${color};">${format(metrics)}</div>
      </div>`;
    }).join('')}
  </div>`;
}

function panel(title, subtitle, id) {
  return `<section style="background:${PANEL}; border:1px solid ${GRID}; border-radius:12px; padding:16px; margin-bottom:16px;">
    <div style="margin-bottom:8px;">
      <h2 style="font-size:0.95rem; font-weight:700; color:${TEXT};">${title}</h2>
      <p style="font-size:0.75rem; color:#64748b;">${subtitle}</p>
    </div>
    <div id="${id}"></div>
  </section>`;
}

export function backtestView(container) {
  container.innerHTML = `
    <div style="margin-bottom:24px;">
      <h1 style="font-size:1.25rem; font-weight:700; color:var(--text); margin-bottom:6px;"><i class="fa-solid fa-clock-rotate-left"></i> 백테스트 엔진</h1>
      <p style="font-size:0.875rem; color:var(--text-muted); line-height:1.6;">
        GBM으로 시뮬레이션된 가격에 이동평균 크로스오버 전략을 적용하고 성과를 분석합니다.
        차트는 브라우저에서 그리므로 구간을 끌어 확대할 수 있습니다.
      </p>
    </div>
    <div style="background:${PANEL}; border-radius:12px; padding:24px; border:1px solid ${GRID};">
      <div style="display:grid; grid-template-columns:repeat(auto-fill,minmax(160px,1fr)); gap:16px; margin-bottom:20px;">
        <div>
          <label class="param-label">단기 MA</label>
          <input id="bt-fast" type="number" value="20" min="5" max="60" class="param-input"/>
        </div>
        <div>
          <label class="param-label">장기 MA</label>
          <input id="bt-slow" type="number" value="60" min="20" max="200" class="param-input"/>
        </div>
        <div>
          <label class="param-label">거래일 수</label>
          <input id="bt-days" type="number" value="1260" min="252" max="5040" class="param-input"/>
        </div>
      </div>
      <button class="run-btn" id="bt-run">▶ 백테스트 실행</button>
      <div id="bt-result" style="margin-top:20px;"></div>
    </div>
    ${cloudResourceCard('backtest')}`;

  // ApexCharts 인스턴스는 window resize 리스너를 붙든다. 화면을 떠날 때 정리하지
  // 않으면 떨어져 나간 컨테이너에 대고 리사이즈 핸들러가 돌아 NaN 오류를 낸다
  // (`app.js:265~273`).
  let charts = [];
  const destroy = () => { charts.forEach((c) => { try { c.destroy(); } catch (e) { /* noop */ } }); charts = []; };
  window._viewCleanup = destroy;

  container.querySelector('#bt-run').addEventListener('click', async () => {
    const btn = container.querySelector('#bt-run');
    const result = container.querySelector('#bt-result');
    destroy();
    btn.disabled = true; btn.textContent = '실행 중...';
    result.innerHTML = '<p style="color:#94a3b8;">백테스트 실행 중...</p>';
    try {
      const data = await api.backtest({
        fast_ma: +container.querySelector('#bt-fast').value,
        slow_ma: +container.querySelector('#bt-slow').value,
        n_days:  +container.querySelector('#bt-days').value,
      });
      const { series, params, metrics } = data;
      result.innerHTML =
        panel(`MA 크로스오버 전략 (MA${params.fast_ma}/MA${params.slow_ma})`, '주가와 두 이동평균, 매수·매도 시점', 'bt-price')
        + panel('누적 수익률 비교', '전략 대 Buy &amp; Hold. 1.0이 원금입니다', 'bt-cum')
        + panel('낙폭 Drawdown (%)', '고점 대비 얼마나 내려갔는가', 'bt-dd')
        + metricsMarkup(metrics);

      charts = [
        new ApexCharts(result.querySelector('#bt-price'), priceOptions(series, params)),
        new ApexCharts(result.querySelector('#bt-cum'), cumulativeOptions(series, metrics)),
        new ApexCharts(result.querySelector('#bt-dd'), drawdownOptions(series)),
      ];
      charts.forEach((c) => c.render());
    } catch (e) {
      // `e.code` 는 `apiFetch` 가 채운다. 503 은 고장이 아니라 환경이라 문구가 다르다.
      result.innerHTML = `<p style="color:#ef4444;">오류: ${e.message}</p>`;
    } finally {
      btn.disabled = false; btn.textContent = '▶ 백테스트 실행';
    }
  });
}
