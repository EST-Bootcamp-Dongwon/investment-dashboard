/**
 * F07 리스크 분석 (VaR / CVaR) — 서버 렌더 PNG 에서 ApexCharts 로.
 *
 * ## 서버 PNG 에서 시리즈로 (2026-08-17)
 *
 * `backtest.js` 에 이어 두 번째다. 서버 `quant_charts.risk()` 가 `image` 대신
 * `series` 를 주고, 여기서 두 장을 그린다. 계산은 서버에서 한 줄도 바뀌지 않았다.
 *
 * ## 곁다리로 고친 것 — 입력 칸 두 개가 아무 일도 하지 않았다
 *
 * 이 화면은 `volatility`·`n_days` 를 보내고 있었는데 **서버가 받는 이름은
 * `confidence`·`n_scenarios`·`portfolio_value` 셋뿐이다**(`routers/quant.py:31~34`).
 * Pydantic 이 모르는 필드를 조용히 버리므로 "연간 변동성"·"시뮬레이션 일수" 두 칸은
 * 지금까지 화면에만 있었다 — σ 는 서비스에 `0.012` 로 박혀 있다. `backtest.js` 의
 * `short_ma`/`long_ma` 와 정확히 같은 함정이다.
 *
 * 정작 그림을 좌우하는 `n_scenarios` 는 손잡이가 없어 늘 기본값 10,000 이었다.
 * 그래서 죽은 칸 하나를 지우고 하나를 `시나리오 수` 로 바꿨다.
 *
 * `포트폴리오 가치` 의 `min` 도 1,000 이었는데 서버는 `ge=1_000_000` 이라
 * 100만 미만을 넣으면 422 가 났다. 그리고 라벨이 `$` 인데 서버 축은 `백만원` 이고
 * 기본값이 1억이었다 — **한 화면에 두 통화가 있었다.** 서버에 맞춰 원화로 통일했다.
 */
import { api } from '../api.js';

// `backtest.js:29~35` 와 같은 값이다. 색이 갈라지면 두 화면이 다른 제품처럼 보인다.
const FONT = 'Pretendard, -apple-system, "Malgun Gothic", sans-serif';
const PANEL = '#1e293b';
const TEXT = '#e2e8f0';
const MUTED = '#94a3b8';
const GRID = '#334155';

/** 원본 `quant_charts.risk()` 가 쓰던 색. 한 글자도 바꾸지 않는다. */
const HIST = '#3b82f6';   // ax.hist(color=...)
const VAR_C = '#f97316';  // axvline VaR
const CVAR_C = '#ef4444'; // axvline CVaR · fill_betweenx
const PV_C = '#22c55e';   // barh 포트폴리오 가치

function baseOptions(height) {
  return {
    chart: {
      // ⚠️ `'transparent'` 금지 — ApexCharts 3.54 는 캔버스를 흰색으로 칠한다
      // (2026-08-17 실측, backtest.js 와 같은 이유).
      height, background: PANEL, fontFamily: FONT,
      animations: { enabled: false },
    },
    theme: { mode: 'dark' },
    dataLabels: { enabled: false },
    grid: { borderColor: GRID, strokeDashArray: 3 },
    tooltip: { theme: 'dark' },
  };
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

/**
 * 수익률 분포 + VaR/CVaR 수직선 + 왼쪽 꼬리 음영.
 *
 * `type:'area'` + `curve:'stepline'` 인 이유: 원본은 `bins=80` 에 `edgecolor="none"`
 * 이라 이미 **채워진 실루엣**이다. 그리고 막대 차트는 Apex 가 내부에서 카테고리
 * 스케일로 잡아 수직선 주석이 반 칸 밀린다 — VaR·CVaR 선은 꼬리의 경계라서
 * 반 칸이 밀리면 **틀린 그림**이 된다. 계단 면적은 수치 축이라 정확히 맞는다.
 */
function histOptions(series, params) {
  const { bins, lines } = series;
  const pct = (v) => `${(v * 100).toFixed(0)}%`;
  return {
    ...baseOptions(340),
    chart: { ...baseOptions(340).chart, type: 'area',
      toolbar: { show: true, tools: { download: false, pan: true, reset: true } },
      zoom: { enabled: true, type: 'x' } },
    series: [{ name: '수익률 분포',
               data: bins.centers.map((x, i) => ({ x, y: bins.counts[i] })) }],
    colors: [HIST],
    stroke: { curve: 'stepline', width: 1 },
    fill: { type: 'solid', opacity: 0.75 },  // hist alpha=0.75
    xaxis: {
      type: 'numeric', tickAmount: 8,
      title: { text: '일간 수익률 (%)', style: { color: TEXT, fontSize: '11px' } },
      labels: { formatter: (v) => Number(v).toFixed(2), style: { colors: MUTED, fontSize: '11px' } },
      axisBorder: { color: GRID }, axisTicks: { color: GRID },
    },
    yaxis: {
      title: { text: '빈도', style: { color: TEXT, fontSize: '11px' } },
      labels: { style: { colors: MUTED, fontSize: '11px' }, formatter: (v) => Number(v).toFixed(0) },
    },
    legend: { show: false },  // 원본 범례 3항목 중 둘은 아래 주석 라벨이 들고 간다
    tooltip: { theme: 'dark',
               x: { formatter: (v) => `${Number(v).toFixed(2)}% 구간` },
               y: { formatter: (v) => `${v}건` } },
    annotations: {
      xaxis: [
        // fill_betweenx — 왼쪽 꼬리. x_min 은 edges[0] = daily_ret.min()*100 이다.
        { x: bins.x_min, x2: lines.var_x, fillColor: CVAR_C, opacity: 0.15 },
        // axvline(linestyle="--")
        { x: lines.var_x, borderColor: VAR_C, strokeDashArray: 6, borderWidth: 2,
          // ⚠️ ApexCharts 는 x축 주석 라벨을 **세로로 회전**하는 것이 기본이다.
          // 원본 범례는 가로였으므로 명시해야 한다(2026-08-17 실측).
          label: { text: `VaR (${pct(params.confidence)}): ${lines.var_x.toFixed(2)}%`,
                   borderColor: VAR_C, position: 'top', orientation: 'horizontal',
                   offsetY: -2,
                   style: { background: VAR_C, color: '#0f172a', fontSize: '10px', fontWeight: 700 } } },
        // axvline(linestyle="-")
        { x: lines.cvar_x, borderColor: CVAR_C, strokeDashArray: 0, borderWidth: 2,
          label: { text: `CVaR: ${lines.cvar_x.toFixed(2)}%`,
                   borderColor: CVAR_C, position: 'bottom', orientation: 'horizontal',
                   offsetY: 2,
                   style: { background: CVAR_C, color: '#0f172a', fontSize: '10px', fontWeight: 700 } } },
      ],
    },
  };
}

/**
 * 리스크 금액 수평 막대 3개.
 *
 * ⚠️ matplotlib `barh` 는 첫 항목을 맨 **아래**에, ApexCharts 는 맨 **위**에 그린다.
 * categories·data·colors **세 곳을 모두** 뒤집어야 라벨과 색이 어긋나지 않는다.
 * ⚠️ `distributed:true` 가 없으면 `colors` 가 계열 색으로 먹어 막대 3개가 한 색이 된다.
 */
function amountOptions(series) {
  const rows = [...series.amounts].reverse();
  const max = Math.max(...series.amounts.map((a) => a.value_m));
  return {
    ...baseOptions(260),
    chart: { ...baseOptions(260).chart, type: 'bar', toolbar: { show: false } },
    series: [{ name: '금액(백만원)', data: rows.map((a) => a.value_m) }],
    colors: [PV_C, CVAR_C, VAR_C],  // 원본 ["#f97316","#ef4444","#22c55e"] 의 역순
    // `position:'top'` 이 없으면 긴 막대의 라벨이 **안쪽 가운데**로 들어간다.
    // 원본은 `ax2.text(val + 1%, ...)` 로 셋 다 막대 밖이었다.
    plotOptions: { bar: { horizontal: true, distributed: true, barHeight: '55%',
                         dataLabels: { position: 'top' } } },
    fill: { type: 'solid', opacity: 0.85 },              // alpha=0.85
    stroke: { show: true, width: 1, colors: [PANEL] },   // edgecolor=grid_c(#1e293b)
    dataLabels: { enabled: true, offsetX: 30, textAnchor: 'start',
                  formatter: (v) => `${Number(v).toFixed(1)}M`,   // f"{val:.1f}M"
                  style: { colors: [TEXT], fontSize: '10px', fontWeight: 700 } },
    xaxis: {
      categories: rows.map((a) => a.label),
      max: max * 1.15,  // 가장 긴 막대의 끝 라벨이 잘리지 않게
      title: { text: '금액 (백만원)', style: { color: TEXT, fontSize: '11px' } },
      labels: { style: { colors: MUTED, fontSize: '11px' } },
      axisBorder: { color: GRID }, axisTicks: { color: GRID },
    },
    yaxis: { labels: { style: { colors: TEXT, fontSize: '11px' } } },
    // 원본은 `axis="x"` — 세로 격자만 켠다.
    grid: { borderColor: GRID, xaxis: { lines: { show: true } }, yaxis: { lines: { show: false } } },
    legend: { show: false },
    tooltip: { theme: 'dark', y: { formatter: (v) => `${Number(v).toFixed(1)}M원` } },
  };
}

export function riskView(container) {
  container.innerHTML = `
    <div style="margin-bottom:24px;">
      <h1 style="font-size:1.25rem; font-weight:700; color:var(--text); margin-bottom:6px;"><i class="fa-solid fa-shield-halved"></i> 리스크 분석 (VaR / CVaR)</h1>
      <p style="font-size:0.875rem; color:#94a3b8; line-height:1.6;">
        정규분포 및 역사적 시뮬레이션을 통해 Value at Risk와 Conditional VaR(Expected Shortfall)를 계산합니다.
        차트는 브라우저에서 그리므로 구간을 끌어 확대할 수 있습니다.
      </p>
    </div>
    <div style="background:${PANEL}; border-radius:12px; padding:24px; border:1px solid ${GRID};">
      <div style="display:grid; grid-template-columns:repeat(auto-fill,minmax(180px,1fr)); gap:16px; margin-bottom:20px;">
        <div>
          <label class="param-label">포트폴리오 가치 (원)</label>
          <input id="risk-pv" type="number" value="100000000" min="1000000" step="1000000" class="param-input"/>
        </div>
        <div>
          <label class="param-label">신뢰수준 (%)</label>
          <input id="risk-conf" type="number" value="95" min="90" max="99" class="param-input"/>
        </div>
        <div>
          <label class="param-label">시나리오 수</label>
          <input id="risk-scenarios" type="number" value="10000" min="1000" max="100000" step="1000" class="param-input"/>
        </div>
      </div>
      <button class="run-btn" id="risk-run">▶ VaR 계산</button>
      <div id="risk-result" style="margin-top:20px;"></div>
    </div>`;

  // ApexCharts 인스턴스는 window resize 리스너를 물고 있다. 화면을 떠날 때
  // 정리하지 않으면 떨어져 나간 컨테이너에 대고 NaN 오류가 난다(app.js:265~273).
  let charts = [];
  const destroy = () => { charts.forEach((c) => { try { c.destroy(); } catch (e) { /* noop */ } }); charts = []; };
  window._viewCleanup = destroy;

  container.querySelector('#risk-run').addEventListener('click', async () => {
    const btn = container.querySelector('#risk-run');
    const result = container.querySelector('#risk-result');
    destroy();  // 재실행 때 인스턴스가 쌓이는 것을 막는다
    btn.disabled = true; btn.textContent = '계산 중...';
    result.innerHTML = '<p style="color:#94a3b8;">리스크 분석 중...</p>';
    try {
      const conf = +container.querySelector('#risk-conf').value;
      const data = await api.risk({
        portfolio_value: +container.querySelector('#risk-pv').value,
        confidence:      conf / 100,
        n_scenarios:     +container.querySelector('#risk-scenarios').value,
      });
      const { series, params } = data;

      // 지표 4칸은 응답 **최상위** 키를 읽는다. 서버가 그래서 접지 않았다.
      const won = (v) => `${Math.round(v).toLocaleString('ko-KR')}원`;
      const metrics = [
        { label: `VaR ${conf}%`, value: data.var_pct != null ? `${(data.var_pct * 100).toFixed(2)}%` : '—', color: VAR_C },
        { label: 'CVaR (ES)', value: data.cvar_pct != null ? `${(data.cvar_pct * 100).toFixed(2)}%` : '—', color: CVAR_C },
        { label: 'VaR 금액', value: data.var_amount != null ? won(data.var_amount) : '—', color: VAR_C },
        { label: 'CVaR 금액', value: data.cvar_amount != null ? won(data.cvar_amount) : '—', color: CVAR_C },
      ];

      result.innerHTML = `
        <div style="display:flex; flex-wrap:wrap; gap:12px; margin-bottom:16px;">
          ${metrics.map((m) => `
            <div class="metric-box" style="min-width:130px;">
              <div style="font-size:0.7rem; color:#64748b; text-transform:uppercase; margin-bottom:4px;">${m.label}</div>
              <div style="font-size:1.1rem; font-weight:700; color:${m.color};">${m.value}</div>
            </div>`).join('')}
        </div>
        ${panel(`수익률 분포 & VaR/CVaR (${conf}% 신뢰수준)`,
                `${params.n_scenarios.toLocaleString('ko-KR')} 시나리오 · 주황=VaR, 빨강=CVaR`, 'risk-hist')}
        ${panel('리스크 금액 비교', '단위: 백만원', 'risk-amt')}`;

      // 컨테이너가 DOM 에 들어간 **뒤에** 그린다. 순서가 바뀌면 조용히 안 그려진다.
      charts = [
        new ApexCharts(result.querySelector('#risk-hist'), histOptions(series, params)),
        new ApexCharts(result.querySelector('#risk-amt'), amountOptions(series)),
      ];
      charts.forEach((c) => c.render());
    } catch (e) {
      result.innerHTML = `<p style="color:#ef4444;">오류: ${e.message}</p>`;
    } finally {
      btn.disabled = false; btn.textContent = '▶ VaR 계산';
    }
  });
}
