/**
 * 거시경제 시뮬레이션 대시보드 — 서버 렌더 PNG 에서 ApexCharts 로 (2026-08-17).
 *
 * 서버 `macro.macro_simulation()` 이 `image` 대신 `series` 를 준다. 여기서 지표
 * 여섯을 각각 한 장씩, 3×2 그리드로 그린다(원본 `gridspec.GridSpec(3, 2)`).
 *
 * **색은 화면이 고른다.** 계열 팔레트와 국면 색은 UI 의 관심사라 응답에 싣지
 * 않는다(D-11). 응답의 지표 배열 **순서가 곧 색**이므로 순서를 바꾸지 마라.
 */
import { api } from '../api.js';

const FONT = 'Pretendard, -apple-system, "Malgun Gothic", sans-serif';
const PANEL = '#1e293b';
const TEXT = '#e2e8f0';
const MUTED = '#94a3b8';
const GRID = '#334155';

/** 원본 `macro.py` 의 `COLORS` 그대로. 순서가 곧 지표다. */
const COLORS = ['#3b82f6', '#f59e0b', '#ef4444', '#22c55e', '#a855f7', '#06b6d4'];

/** 원본 `axvspan` 의 `bg` 판정을 색으로 되돌린다 (`#22c55e22` 등). */
const PHASE_FILL = { up: '#22c55e', warm: '#f59e0b', down: '#ef4444' };

function chartOptions(ind, phases, points, color) {
  const fix = (v) => Number(v).toFixed(ind.decimals);
  const sign = ind.chg_pct >= 0 ? '+' : '';
  return {
    chart: {
      // ⚠️ `'transparent'` 금지 — ApexCharts 3.54 는 캔버스를 흰색으로 칠한다.
      type: 'area', height: 240, background: PANEL, fontFamily: FONT,
      toolbar: { show: true, tools: { download: false, pan: true, reset: true } },
      zoom: { enabled: true, type: 'x' },
      animations: { enabled: false },
      group: 'macro-sim',
    },
    theme: { mode: 'dark' },
    title: {
      // 원본 `ax.set_title(f"{name}  현재: {cur}  ({sign}{chg}%)")` 그대로.
      text: `${ind.name}  현재: ${fix(ind.end)}  (${sign}${ind.chg_pct.toFixed(1)}%)`,
      style: { color: TEXT, fontSize: '12px', fontWeight: 700 },
    },
    series: [{ name: ind.name, data: ind.values }],
    colors: [color],
    stroke: { curve: 'straight', width: 1.5 },   // 원본 lw=1.5
    fill: { type: 'solid', opacity: 0.12 },      // 원본 fill_between alpha=0.12
    dataLabels: { enabled: false },
    grid: { borderColor: GRID, strokeDashArray: 3 },
    xaxis: {
      type: 'numeric', tickAmount: 6, max: points,   // 축 상한도 points 하나로 통일
      labels: { formatter: (v) => Number(v).toFixed(0), style: { colors: MUTED, fontSize: '10px' } },
      axisBorder: { color: GRID }, axisTicks: { color: GRID },
    },
    yaxis: { labels: { formatter: fix, style: { colors: MUTED, fontSize: '10px' } } },
    legend: { show: false },
    tooltip: { theme: 'dark', x: { formatter: (v) => `${Number(v).toFixed(0)}거래일` },
               y: { formatter: fix } },
    annotations: {
      xaxis: [
        // 경기국면 배경. 원본은 `alpha=0.4` 를 `#rrggbb22` 위에 겹쳐 칠했다 —
        // 실효 불투명도가 낮아 여기서는 0.13 으로 맞췄다(선보다 옅어야 한다).
        ...phases.map((ph) => ({
          x: ph.x0, x2: ph.x1, fillColor: PHASE_FILL[ph.tone], opacity: 0.13,
          // 원본은 `va="bottom"` 이라 축선 **위**에 앉는다. `offsetY` 가 없으면
          // 축선에 걸쳐 y축 눈금과 겹친다("3.30상승기").
          label: { text: ph.name, position: 'bottom', orientation: 'horizontal',
                   offsetY: -6, borderWidth: 0,
                   style: { background: 'transparent', color: MUTED, fontSize: '9px' } },
        })),
      ],
      points: [
        // 원본 `ax.annotate("고: ...")` / `("저: ...")`
        { x: ind.high.index, y: ind.high.value, marker: { size: 3, fillColor: '#22c55e', strokeWidth: 0 },
          label: { text: `고: ${fix(ind.high.value)}`, offsetY: -4, borderWidth: 0,
                   style: { background: 'transparent', color: '#22c55e', fontSize: '9px' } } },
        { x: ind.low.index, y: ind.low.value, marker: { size: 3, fillColor: '#ef4444', strokeWidth: 0 },
          label: { text: `저: ${fix(ind.low.value)}`, offsetY: 14, borderWidth: 0,
                   style: { background: 'transparent', color: '#ef4444', fontSize: '9px' } } },
      ],
    },
  };
}


export function macroSimulationView(container) {
  container.innerHTML = `
    <div style="margin-bottom:24px;">
      <h1 style="font-size:1.25rem; font-weight:700; color:#131722; margin-bottom:6px;"><i class="fa-solid fa-chart-area"></i> 거시경제현황 2 — 시뮬레이션 대시보드</h1>
      <p style="font-size:0.875rem; color:#6b7280; line-height:1.6;">
        GBM(기하브라운운동)으로 기준금리·CPI·유가·환율·KOSPI·S&amp;P 500을 시뮬레이션하고
        경기사이클(상승기→과열기→침체기→회복기) 국면을 함께 표시합니다.
      </p>
    </div>

    <!-- 경기사이클 설명 -->
    <div style="background:#1e293b; border-radius:12px; padding:16px 20px; border:1px solid #334155; margin-bottom:16px;">
      <div style="font-size:0.75rem; font-weight:600; color:#64748b; text-transform:uppercase; letter-spacing:0.08em; margin-bottom:12px;">경기사이클 4단계</div>
      <div style="display:grid; grid-template-columns:repeat(4,1fr); gap:10px;">
        ${[
          { name: '상승기', color: '#22c55e', desc: '성장률↑ 금리 안정 주가↑' },
          { name: '과열기', color: '#f59e0b', desc: '물가↑ 금리↑ 긴축 시작' },
          { name: '침체기', color: '#ef4444', desc: '성장 둔화 실업↑ 주가↓' },
          { name: '회복기', color: '#3b82f6', desc: '금리↓ 완화 소비 회복' },
        ].map(p => `
          <div style="text-align:center; padding:10px 8px; background:#0f172a; border-radius:8px;
               border-top:3px solid ${p.color};">
            <div style="font-size:0.875rem; font-weight:700; color:${p.color}; margin-bottom:4px;">${p.name}</div>
            <div style="font-size:0.7rem; color:#64748b; line-height:1.5;">${p.desc}</div>
          </div>`).join('')}
      </div>
    </div>

    <div style="background:#1e293b; border-radius:12px; padding:24px; border:1px solid #334155;">
      <div style="display:grid; grid-template-columns:repeat(auto-fill,minmax(180px,1fr)); gap:16px; margin-bottom:20px;">
        <div>
          <label class="param-label">시뮬레이션 기간 (거래일)</label>
          <input id="sim-days" type="number" value="252" min="60" max="1260" class="param-input"/>
          <div style="font-size:0.7rem; color:#64748b; margin-top:4px;">252일 = 1년, 1260일 = 5년</div>
        </div>
        <div>
          <label class="param-label">랜덤 시드 (재현성)</label>
          <input id="sim-seed" type="number" value="42" min="0" max="9999" class="param-input"/>
        </div>
      </div>
      <button class="run-btn" id="sim-run">▶ 시뮬레이션 실행</button>
      <div id="sim-result" style="margin-top:24px;"></div>
    </div>`;

  // ApexCharts 인스턴스 여섯이 window resize 리스너를 문다. 화면을 떠날 때
  // 정리하지 않으면 떨어져 나간 컨테이너에 대고 NaN 오류가 난다(app.js:265~273).
  let charts = [];
  const destroy = () => { charts.forEach((c) => { try { c.destroy(); } catch (e) { /* noop */ } }); charts = []; };
  window._viewCleanup = destroy;

  container.querySelector('#sim-run').addEventListener('click', async () => {
    const btn    = container.querySelector('#sim-run');
    const result = container.querySelector('#sim-result');
    destroy();
    btn.disabled = true; btn.textContent = '시뮬레이션 중...';
    result.innerHTML = '<p style="color:#94a3b8;">GBM 시뮬레이션 실행 중...</p>';
    try {
      const data = await api.macroSimulation({
        n_days: +container.querySelector('#sim-days').value,
        seed:   +container.querySelector('#sim-seed').value,
      });

      const { series } = data;
      let html = `<div style="font-size:0.8rem; color:${MUTED}; margin-bottom:12px;">
        ${series.points.toLocaleString('ko-KR')}거래일 GBM 시뮬레이션 · 구간을 끌어 확대할 수 있습니다
      </div>
      <div id="sim-grid" style="display:grid; grid-template-columns:repeat(auto-fit,minmax(360px,1fr)); gap:12px; margin-bottom:20px;">
        ${series.indicators.map((_, i) => `<div id="sim-c${i}" style="background:${PANEL}; border:1px solid ${GRID}; border-radius:10px; padding:8px;"></div>`).join('')}
      </div>`;

      if (data.summary) {
        html += `
          <div style="font-size:0.75rem; font-weight:600; color:#64748b; text-transform:uppercase;
               letter-spacing:0.08em; margin-bottom:12px;">시뮬레이션 결과 요약</div>
          <div style="overflow-x:auto;">
            <table style="width:100%; border-collapse:collapse; font-size:0.825rem;">
              <thead>
                <tr style="background:#0f172a;">
                  <th style="padding:10px 12px; text-align:left; color:#64748b; font-size:0.7rem; text-transform:uppercase; white-space:nowrap;">지표</th>
                  <th style="padding:10px 12px; text-align:right; color:#64748b; font-size:0.7rem; text-transform:uppercase;">시작값</th>
                  <th style="padding:10px 12px; text-align:right; color:#64748b; font-size:0.7rem; text-transform:uppercase;">종료값</th>
                  <th style="padding:10px 12px; text-align:right; color:#64748b; font-size:0.7rem; text-transform:uppercase;">변화율</th>
                </tr>
              </thead>
              <tbody>
                ${Object.entries(data.summary).map(([name, s]) => {
                  const isPos = s.chg_pct >= 0;
                  return `
                    <tr style="border-bottom:1px solid #334155;">
                      <td style="padding:10px 12px; color:#e2e8f0; font-weight:500;">${name}</td>
                      <td style="padding:10px 12px; text-align:right; color:#94a3b8;">${s.start.toLocaleString()}</td>
                      <td style="padding:10px 12px; text-align:right; color:#e2e8f0; font-weight:600;">${s.end.toLocaleString()}</td>
                      <td style="padding:10px 12px; text-align:right; font-weight:700;
                           color:${isPos ? '#22c55e' : '#ef4444'};">
                        ${isPos ? '▲' : '▼'} ${Math.abs(s.chg_pct).toFixed(2)}%
                      </td>
                    </tr>`;
                }).join('')}
              </tbody>
            </table>
          </div>`;
      }
      result.innerHTML = html;

      // 컨테이너가 DOM 에 들어간 **뒤에** 그린다.
      charts = series.indicators.map((ind, i) => new ApexCharts(
        result.querySelector(`#sim-c${i}`),
        chartOptions(ind, series.phases, series.points, COLORS[i % COLORS.length])));
      charts.forEach((c) => c.render());
    } catch (e) {
      result.innerHTML = `<p style="color:#ef4444;">오류: ${e.message}</p>`;
    } finally {
      btn.disabled = false; btn.textContent = '▶ 시뮬레이션 실행';
    }
  });
}
