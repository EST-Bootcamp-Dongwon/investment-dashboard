/**
 * backtest-lab.js — 백테스트 실험실 화면.
 *
 * /api/backtest-lab/run 을 호출해 예측 정확도와 간이 매매 성과를 받아 그립니다.
 * 차트는 외부 라이브러리 없이 인라인 SVG 로 직접 그립니다(리포트 생성기와 같은 방식).
 */

const COLOR = {
  actual: '#0f766e',
  pred: '#c2410c',
  strategy: '#1d4ed8',
  bench: '#94a3b8',
};

const $ = (id) => document.getElementById(id);
const statusEl = () => $('lab-status');

/** 화면의 % 입력(0.015)을 API 가 쓰는 비율(0.00015)로 바꿉니다. */
const toRate = (percentValue) => Number(percentValue) / 100;

const fmtWon = (v, digits = 0) =>
  `${Number(v).toLocaleString('ko-KR', { minimumFractionDigits: digits, maximumFractionDigits: digits })}원`;
const fmtPct = (v, digits = 2, sign = false) =>
  `${sign && v > 0 ? '+' : ''}${Number(v).toFixed(digits)}%`;
const esc = (s) => String(s).replace(/[&<>"']/g, (c) =>
  ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));

let lastPayload = null;

// ---------------------------------------------------------------------------
// SVG 차트
// ---------------------------------------------------------------------------

function lineChart(labels, series, { height = 280, width = 940, yFormat = 'number' } = {}) {
  if (!labels.length || !series.length) return '<p class="lab-note">표시할 데이터가 없습니다.</p>';

  const padL = 76, padR = 16, padT = 14, padB = 30;
  const plotW = width - padL - padR;
  const plotH = height - padT - padB;

  const flat = series.flatMap((s) => s.values).filter((v) => v != null && Number.isFinite(v));
  if (!flat.length) return '<p class="lab-note">표시할 데이터가 없습니다.</p>';
  let lo = Math.min(...flat), hi = Math.max(...flat);
  const pad = (hi - lo) * 0.08 || Math.abs(lo) * 0.05 || 1;
  lo -= pad; hi += pad;
  const span = hi - lo || 1;

  const xOf = (i) => padL + (plotW * i) / Math.max(labels.length - 1, 1);
  const yOf = (v) => padT + plotH * (1 - (v - lo) / span);

  const fmtY = (v) => {
    if (yFormat === 'won') return Math.round(v).toLocaleString('ko-KR');
    if (yFormat === 'eok') return `${(v / 1e8).toFixed(3)}억`;
    return v.toFixed(2);
  };

  let svg = `<svg viewBox="0 0 ${width} ${height}" role="img" preserveAspectRatio="xMidYMid meet">`;
  for (let i = 0; i < 5; i++) {
    const v = lo + (span * i) / 4;
    const y = yOf(v);
    svg += `<line class="grid" x1="${padL}" y1="${y.toFixed(1)}" x2="${width - padR}" y2="${y.toFixed(1)}"/>`;
    svg += `<text class="tick" x="${padL - 8}" y="${(y + 4).toFixed(1)}" text-anchor="end">${esc(fmtY(v))}</text>`;
  }
  const ticks = Math.min(6, labels.length);
  for (let i = 0; i < ticks; i++) {
    const idx = Math.round(((labels.length - 1) * i) / Math.max(ticks - 1, 1));
    svg += `<text class="tick" x="${xOf(idx).toFixed(1)}" y="${height - 10}" text-anchor="middle">${esc(labels[idx])}</text>`;
  }
  for (const s of series) {
    const pts = s.values
      .map((v, i) => (v == null || !Number.isFinite(v) ? null : `${xOf(i).toFixed(1)},${yOf(v).toFixed(1)}`))
      .filter(Boolean)
      .join(' ');
    const dash = s.dashed ? ' stroke-dasharray="5 4"' : '';
    svg += `<polyline fill="none" stroke="${s.color}" stroke-width="2" stroke-linejoin="round" stroke-linecap="round"${dash} points="${pts}"/>`;
  }
  svg += '</svg>';

  const legend = series
    .map((s) => `<span><i style="background:${s.color}"></i>${esc(s.name)}</span>`)
    .join('');
  return `<div class="lab-legend">${legend}</div><div class="lab-chart">${svg}</div>`;
}

// ---------------------------------------------------------------------------
// 조각 렌더러
// ---------------------------------------------------------------------------

const stat = (k, v, f = '', tone = '') =>
  `<div class="stat"><span class="k">${esc(k)}</span>
   <div class="v ${tone}">${esc(v)}</div>${f ? `<div class="f">${esc(f)}</div>` : ''}</div>`;

const tableHtml = (headers, rows) =>
  `<div class="lab-table-wrap"><table class="lab-table">
    <thead><tr>${headers.map((h) => `<th>${esc(h)}</th>`).join('')}</tr></thead>
    <tbody>${rows.map((r) => `<tr>${r.map((c) => (typeof c === 'object' ? `<td class="${c.tone || ''}">${esc(c.text)}</td>` : `<td>${esc(c)}</td>`)).join('')}</tr>`).join('')}</tbody>
  </table></div>`;

function renderResult(data) {
  const { meta, prediction_metrics: pm, simple_backtest: bt, regime } = data;
  const st = bt.strategy, bm = bt.benchmark;

  const beatsDir = pm.beats_naive_direction;
  const beatsMae = pm.beats_naive_mae;
  const tone = beatsDir && beatsMae ? 'good' : beatsDir || beatsMae ? 'warn' : 'bad';
  const head =
    tone === 'good' ? '모델이 기준선을 양쪽 지표에서 앞섰습니다'
    : tone === 'warn' ? '모델이 기준선을 한쪽 지표에서만 앞섰습니다'
    : '모델이 기준선을 이기지 못했습니다';

  const dates = data.rows.map((r) => r.target_date);
  const curve = bt.curve;

  let html = `
  <div class="lab-banner ${tone}">
    <strong>${esc(head)}</strong>
    <div class="detail">
      방향 적중률 ${fmtPct(pm.direction_accuracy)} vs 기준선 ${fmtPct(pm.naive_direction_accuracy)} ·
      수익률 MAE ${pm.mae_return.toFixed(5)} vs 기준선 ${pm.naive_mae_return.toFixed(5)} ·
      naive 대비 R² ${pm.r2_vs_naive >= 0 ? '+' : ''}${pm.r2_vs_naive.toFixed(4)}
    </div>
  </div>

  <p class="lab-note">
    <strong>${esc(meta.name)} (${esc(meta.ticker)})</strong> ·
    학습 ${esc(meta.train_start)}~${esc(meta.train_end)} (${meta.train_samples}일) →
    검증 ${esc(meta.test_start)}~${esc(meta.test_end)} (${meta.test_samples}일, out-of-sample) ·
    ${esc(meta.model)}
  </p>`;

  // 국면 비교
  if (regime && regime.train && regime.test && regime.train.days) {
    const ratio = regime.volatility_ratio || 0;
    const shifted = ratio >= 1.5 || ratio <= 0.67;
    html += `<h2>학습 구간 vs 검증 구간의 성격</h2>
    ${tableHtml(
      ['구간', '기간', '거래일', '일평균 절대등락', '연환산 변동성', '구간 수익률'],
      [
        ['학습', `${regime.train.start} ~ ${regime.train.end}`, `${regime.train.days}일`,
          fmtPct(regime.train.mean_abs_move_pct), fmtPct(regime.train.annual_volatility_pct),
          fmtPct(regime.train.period_return_pct, 2, true)],
        ['검증', `${regime.test.start} ~ ${regime.test.end}`, `${regime.test.days}일`,
          fmtPct(regime.test.mean_abs_move_pct), fmtPct(regime.test.annual_volatility_pct),
          fmtPct(regime.test.period_return_pct, 2, true)],
      ]
    )}
    <p class="lab-note">검증 구간의 일평균 등락이 학습 구간의 <strong>${ratio.toFixed(2)}배</strong>입니다.
    ${shifted
      ? '<strong>국면이 바뀌었습니다.</strong> 조용한 장에서 배운 패턴을 다른 변동성의 장에 적용하고 있어, 모델 구조를 바꿔도 잘 해결되지 않습니다.'
      : '두 구간의 변동성이 비슷해 학습한 패턴이 적용될 여지가 있습니다.'}</p>`;
  }

  // 1부 예측
  html += `<h2>1부 · 예측이 맞았는가</h2>
  <div class="stat-grid">
    ${stat('방향 적중률', fmtPct(pm.direction_accuracy), `기준선 ${fmtPct(pm.naive_direction_accuracy)}`, beatsDir ? 'good' : 'bad')}
    ${stat('가격 MAE', fmtWon(pm.mae_price), `기준선 ${fmtWon(pm.naive_mae_price)}`, pm.mae_price < pm.naive_mae_price ? 'good' : 'bad')}
    ${stat('가격 MAPE', fmtPct(pm.mape_price), '실제 종가 대비 평균 오차율')}
    ${stat('naive 대비 R²', `${pm.r2_vs_naive >= 0 ? '+' : ''}${pm.r2_vs_naive.toFixed(4)}`, '0보다 커야 기준선보다 나음', pm.r2_vs_naive > 0 ? 'good' : 'bad')}
    ${stat('검증 표본', `${pm.n_samples}일`, `학습 ${meta.train_samples}일`)}
  </div>

  <h3>예측 종가 vs 실제 종가</h3>
  ${lineChart(dates, [
    { name: '실제 종가', color: COLOR.actual, values: data.rows.map((r) => r.actual_next_close) },
    { name: '예측 종가', color: COLOR.pred, values: data.rows.map((r) => r.pred_next_close), dashed: true },
  ], { yFormat: 'won' })}
  <p class="lab-note">두 선이 겹쳐 보이는 건 정확해서가 아닙니다. 예측 종가 = 오늘 종가 × (1 + 예측 수익률)이라
  아무 예측이나 해도 전날 종가를 따라갑니다. 판정은 위 카드의 기준선 비교로 하세요.</p>

  <h2>2부 · 그래서 돈이 되는가</h2>
  <div class="stat-grid">
    ${stat('전략 누적수익', fmtPct(st.total_return_pct, 2, true), fmtWon(st.end_equity), st.total_return_pct > 0 ? 'good' : 'bad')}
    ${stat('매수·보유', fmtPct(bm.total_return_pct, 2, true), fmtWon(bm.end_equity), bm.total_return_pct > 0 ? 'good' : 'bad')}
    ${stat('초과수익', fmtPct(bt.excess_return_pct, 2, true), '전략 − 매수·보유', bt.excess_return_pct > 0 ? 'good' : 'bad')}
    ${stat('전략 MDD', fmtPct(st.max_drawdown_pct), `매수·보유 ${fmtPct(bm.max_drawdown_pct)}`)}
    ${stat('전략 샤프', st.sharpe.toFixed(3), `매수·보유 ${bm.sharpe.toFixed(3)}`)}
    ${stat('진입 횟수', `${st.trades}회`, `승률 ${fmtPct(st.win_rate_pct, 1)} · 보유일 ${fmtPct(st.days_in_market_pct, 1)}`)}
  </div>

  <h3>자산 곡선</h3>
  ${lineChart(curve.map((p) => p.date), [
    { name: '예측 신호 전략', color: COLOR.strategy, values: curve.map((p) => p.strategy) },
    { name: '매수·보유', color: COLOR.bench, values: curve.map((p) => p.benchmark) },
  ], { yFormat: 'eok' })}

  <h3>성과 비교</h3>
  ${tableHtml(['지표', '예측 신호 전략', '매수·보유'], [
    ['시작 자산', fmtWon(st.start_equity), fmtWon(bm.start_equity)],
    ['종료 자산', fmtWon(st.end_equity), fmtWon(bm.end_equity)],
    ['누적 수익률',
      { text: fmtPct(st.total_return_pct, 2, true), tone: st.total_return_pct > 0 ? 'good' : 'bad' },
      { text: fmtPct(bm.total_return_pct, 2, true), tone: bm.total_return_pct > 0 ? 'good' : 'bad' }],
    ['연환산 수익률', fmtPct(st.cagr_pct, 2, true), fmtPct(bm.cagr_pct, 2, true)],
    ['최대 낙폭(MDD)', fmtPct(st.max_drawdown_pct), fmtPct(bm.max_drawdown_pct)],
    ['연환산 변동성', fmtPct(st.volatility_pct), fmtPct(bm.volatility_pct)],
    ['샤프 지수', st.sharpe.toFixed(3), bm.sharpe.toFixed(3)],
    ['진입 횟수', `${st.trades}회`, `${bm.trades}회`],
    ['추정 거래비용', fmtWon(st.total_cost), fmtWon(bm.total_cost)],
  ])}

  <p class="lab-note">
    이 성과는 <strong>벡터화 근사치</strong>입니다. 정수 주 단위 체결·주문별 비용까지 반영한 정본이 필요하면
    <code>docker compose -f docker-compose.hd.yaml run --rm hd-backtest</code> 로 LEAN 엔진을 돌리세요.
    체결가는 신호 확정일 종가로 가정하며, 실제로는 그 가격에 살 수 없습니다.
  </p>`;

  return html;
}

// ---------------------------------------------------------------------------
// 폼 → API
// ---------------------------------------------------------------------------

function collect() {
  return {
    ticker: $('ticker').value.trim(),
    name: $('name').value.trim() || $('ticker').value.trim(),
    train_start: $('train_start').value,
    train_end: $('train_end').value,
    test_start: $('test_start').value,
    test_end: $('test_end').value,
    initial_cash: Number($('initial_cash').value),
    commission_rate: toRate($('commission_rate').value),
    sell_tax_rate: toRate($('sell_tax_rate').value),
    slippage_rate: toRate($('slippage_rate').value),
  };
}

async function post(path, body) {
  const res = await fetch(path, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  });
  const json = await res.json().catch(() => ({ detail: res.statusText }));
  if (!res.ok) {
    // FastAPI 검증 오류는 detail 이 배열로 옵니다.
    const detail = Array.isArray(json.detail)
      ? json.detail.map((d) => d.msg || JSON.stringify(d)).join(' / ')
      : json.detail || res.statusText;
    throw new Error(detail);
  }
  return json;
}

async function loadConfig() {
  try {
    const cfg = await fetch('/api/backtest-lab/config').then((r) => r.json());
    const select = $('preset');
    for (const p of cfg.presets || []) {
      const option = document.createElement('option');
      option.value = p.ticker;
      option.textContent = `${p.name} (${p.ticker})`;
      select.appendChild(option);
    }
    select.value = '005380.KS';
    // 검증 종료일이 미래가 되지 않도록 상한을 오늘로 막습니다.
    if (cfg.today) {
      $('test_end').max = cfg.today;
      $('test_start').max = cfg.today;
    }
    if (!cfg.available) {
      statusEl().textContent = `예측 모듈을 불러오지 못했습니다: ${cfg.import_error || '원인 불명'}`;
      statusEl().className = 'lab-status error';
      $('run-btn').disabled = true;
    }
  } catch (err) {
    console.error('설정 로드 실패:', err);
  }
}

function bind() {
  $('preset').addEventListener('change', (event) => {
    const value = event.target.value;
    if (!value) return;
    const label = event.target.selectedOptions[0].textContent;
    $('ticker').value = value;
    $('name').value = label.replace(/\s*\(.+\)$/, '');
  });

  $('lab-form').addEventListener('submit', async (event) => {
    event.preventDefault();
    const button = $('run-btn');
    button.disabled = true;
    statusEl().className = 'lab-status';
    statusEl().textContent = '시세를 받고 모델을 학습하는 중… (10초 정도 걸립니다)';

    try {
      const data = await post('/api/backtest-lab/run', collect());
      lastPayload = collect();
      const box = $('lab-result');
      box.innerHTML = renderResult(data);
      box.hidden = false;
      statusEl().className = 'lab-status ok';
      statusEl().textContent = `완료 · 검증 ${data.meta.test_samples}일`;
      $('report-btn').disabled = false;
      box.scrollIntoView({ behavior: 'smooth', block: 'start' });
    } catch (err) {
      statusEl().className = 'lab-status error';
      statusEl().textContent = `오류: ${err.message}`;
    } finally {
      button.disabled = false;
    }
  });

  $('report-btn').addEventListener('click', async () => {
    const button = $('report-btn');
    button.disabled = true;
    statusEl().className = 'lab-status';
    statusEl().textContent = '리포트를 만드는 중…';
    try {
      const result = await post('/api/backtest-lab/report', lastPayload || collect());
      // 자체완결 HTML 이라 Blob 으로 바로 내려받게 합니다.
      const blob = new Blob([result.html], { type: 'text/html;charset=utf-8' });
      const url = URL.createObjectURL(blob);
      const link = document.createElement('a');
      link.href = url;
      link.download = result.filename;
      link.click();
      setTimeout(() => URL.revokeObjectURL(url), 10_000);
      statusEl().className = 'lab-status ok';
      statusEl().textContent = `리포트 저장: ${result.filename} (${Math.round(result.bytes / 1024)}KB)`;
    } catch (err) {
      statusEl().className = 'lab-status error';
      statusEl().textContent = `오류: ${err.message}`;
    } finally {
      button.disabled = false;
    }
  });
}

loadConfig();
bind();
