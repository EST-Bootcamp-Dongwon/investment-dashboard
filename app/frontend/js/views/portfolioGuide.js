import { api } from '../api.js';
import { visitorId } from '../utils/localState.js';

// 자산 배분표와 판정 규칙은 서버로 옮겼다 (app/backend/services/recommendation.py).
// 브라우저 안에만 있던 탓에 저장·재현·검증이 불가능했던 것이 F03 의 문제였다.
//
// 색상만 여기 남는다. UI 테마의 관심사라 이력에 저장하지 않기로 했고(테이블-정의서 4.3절),
// 자산명 → 색상이 세 프로필에 걸쳐 모순 없는 함수라 자산명으로 되찾을 수 있다.
const ASSET_COLORS = {
  '현금성 자산': '#38bdf8',
  '채권·안정형 자산': '#818cf8',
  '글로벌 주식': '#22c55e',
  '배당·방어형 주식': '#f59e0b',
  '국내 주식': '#0078d4',
  '대체 자산': '#f59e0b',
  '테마·성장 자산': '#a855f7',
};

const PROFILE_COLORS = {
  stable: '#059669',
  balanced: '#0078d4',
  growth: '#7c3aed',
};

// 배분표에 새 자산이 생겨도 화면이 깨지지 않게 기본값을 준다.
function assetColor(name) {
  return ASSET_COLORS[name] ?? '#94a3b8';
}

function renderProfile(result) {
  const items = result.items ?? [];
  const accent = PROFILE_COLORS[result.profile] ?? '#0078d4';
  const blocks = items.map((item) => {
    const color = assetColor(item.asset_name);
    return `<span style="width:${item.weight_pct}%;background:${color}" title="${item.asset_name} ${item.weight_pct}%"></span>`;
  }).join('');
  const rows = items.map((item) => `
    <li><span class="guide-dot" style="background:${assetColor(item.asset_name)}"></span><div><b>${item.asset_name}</b><small>${item.explanation}</small></div><strong>${item.weight_pct}%</strong></li>`).join('');
  return `
    <section class="portfolio-guide-result">
      <div class="portfolio-guide-result-head">
        <div><p>추천 구성 예시</p><h2>${result.profile_label} <span style="color:${accent}">${result.badge}</span></h2></div>
        <i class="fa-solid fa-compass" style="color:${accent}"></i>
      </div>
      <p class="portfolio-guide-intro">${result.intro}</p>
      <div class="guide-allocation-bar" aria-label="자산 구성 비중">${blocks}</div>
      <ul class="guide-allocation-list">${rows}</ul>
      <div class="portfolio-guide-note"><i class="fa-solid fa-circle-info"></i><span><b>미리 알아둘 점:</b> ${result.note}</span></div>
      ${renderSaveState(result)}
    </section>`;
}

// 저장 여부를 화면에 드러낸다. 저장에 실패했는데 결과만 보여주면 사용자는 이력에
// 남았다고 믿는다. 서버가 503 을 주면 preview 로 폴백하되 그 사실을 반드시 적는다.
function renderSaveState(result) {
  if (result.recommendation_id) {
    const at = new Date(result.created_at).toLocaleString('ko-KR');
    return `<p class="portfolio-guide-saved"><i class="fa-solid fa-clock-rotate-left"></i> ${at} 이력에 저장했습니다 (번호 ${result.recommendation_id}).</p>`;
  }
  if (result.saveFailed) {
    return `<p class="portfolio-guide-saved" data-state="failed"><i class="fa-solid fa-triangle-exclamation"></i> 결과는 보여드리지만 <b>이력에 저장되지 않았습니다.</b> ${result.saveFailed}</p>`;
  }
  return '';
}

export function portfolioGuideView(container) {
  container.innerHTML = `
    <section class="portfolio-guide-page">
      <div class="page-heading"><div><h1><i class="fa-solid fa-compass"></i> 포트폴리오 추천</h1><p>몇 가지 질문으로 나에게 맞는 자산 구성의 출발점을 찾아보세요.</p></div></div>
      <aside class="portfolio-guide-explainer"><i class="fa-solid fa-map"></i><div><strong>추천은 ‘정답’보다 ‘출발점’입니다</strong><p>투자 목적, 필요한 시점, 감당할 수 있는 흔들림은 사람마다 다릅니다. 이 메뉴는 그 차이를 반영해 자산을 어떻게 나누어 볼지 쉽게 보여주는 학습용 가이드입니다.</p><button type="button" class="sharpe-help-button" id="sharpe-help" aria-haspopup="dialog" aria-expanded="false"><i class="fa-solid fa-circle-question" aria-hidden="true"></i> 샤프지수(Sharpe Ratio) 알아보기</button></div></aside>
      <div class="sharpe-modal-backdrop" id="sharpe-modal" hidden>
        <section class="sharpe-modal" role="dialog" aria-modal="true" aria-labelledby="sharpe-modal-title" tabindex="-1">
          <header class="sharpe-modal-header"><div><span class="sharpe-modal-icon"><i class="fa-solid fa-scale-balanced"></i></span><div><p class="sharpe-kicker">Sharpe Ratio <span aria-label="샤프 레이시오">(샤프 레이시오)</span></p><h2 id="sharpe-modal-title">샤프지수, 위험 대비 수익의 효율</h2><p>얼마나 많이 벌었는지뿐 아니라, 그 수익을 얻기 위해 얼마나 흔들렸는지도 함께 봅니다.</p></div></div><button type="button" class="sharpe-modal-close" aria-label="샤프지수 설명 닫기"><i class="fa-solid fa-xmark"></i></button></header>
          <div class="sharpe-modal-body">
            <div class="sharpe-plain-language"><span><i class="fa-solid fa-language"></i> 쉽게 말하면</span><p><b>샤프지수</b>는 영어로 <b>Sharpe Ratio</b>, 한국어식으로 <b>샤프 레이시오</b>라고 읽습니다. 위험을 감수하고 얻은 <b>초과수익의 효율</b>을 숫자로 나타낸 지표입니다. 같은 수익이라면 덜 흔들린 투자의 샤프지수가 더 높습니다.</p></div>
            <div class="sharpe-formula" aria-label="샤프지수 수식"><span>Sharpe Ratio</span> = <span>(포트폴리오 수익률 − 무위험수익률)</span> / <span>포트폴리오 변동성</span></div>
            <div class="sharpe-parts"><div><b>초과수익</b><span>예금·국채처럼 위험이 낮은 투자보다 얼마나 더 벌었는지</span></div><div><b>변동성</b><span>수익률이 위아래로 흔들린 정도, 즉 감수한 위험</span></div><div><b>결과</b><span>값이 높을수록 같은 위험 대비 수익의 효율이 높은 편</span></div></div>
            <div class="sharpe-example"><h3><i class="fa-solid fa-calculator"></i> 짧은 예시</h3><p>연 수익률이 10%, 무위험수익률이 3%, 변동성이 14%라면 <b>(10% − 3%) ÷ 14% = 0.50</b>입니다. 수익률이 같아도 변동성이 7%라면 샤프지수는 <b>1.00</b>이 됩니다. 그래서 수익률만 비교할 때 놓치기 쉬운 ‘흔들림’을 함께 고려할 수 있습니다.</p></div>
            <div class="sharpe-caution"><i class="fa-solid fa-triangle-exclamation"></i><p><b>이 추천 화면은 샤프지수를 계산하지 않습니다.</b> 투자 기간·목적·위험 성향에 따라 정해진 학습용 자산배분 예시를 보여줍니다. 샤프지수는 별도의 포트폴리오 최적화 화면에서 여러 조합을 비교할 때 사용합니다.</p></div>
            <div class="sharpe-code-head"><h3><i class="fa-brands fa-python"></i> 이 프로젝트의 최적화 코드</h3><span>app/backend/routers/quant.py 일부</span></div>
            <pre class="sharpe-code"><code># r: 포트폴리오 기대수익률
# v: 공분산을 반영한 포트폴리오 변동성
r = float(w @ mu_ann)
v = float(np.sqrt(w @ cov @ w))

# rf: 무위험수익률 (기본값 3%)
sharpe = (r - rf) / v

# 여러 비중 조합 중 샤프지수가 가장 높은 조합을 선택
best_i = int(np.argmax(port_sharpes))</code></pre>
            <p class="sharpe-note"><i class="fa-solid fa-circle-info"></i> 샤프지수는 과거 데이터와 가정한 수익률·변동성에 따라 달라집니다. 미래 성과나 손실 가능성을 보장하지 않습니다.</p>
          </div>
        </section>
      </div>
      <div class="portfolio-guide-layout">
        <section class="portfolio-guide-form">
          <h2>내 상황에 가까운 선택</h2>
          <label><span>투자 목적</span><select class="param-input" id="guide-goal"><option value="growth">장기적으로 자산을 키우고 싶어요</option><option value="balance">성장과 안정의 균형이 필요해요</option><option value="protect">원금의 큰 흔들림이 걱정돼요</option></select></label>
          <label><span>투자 기간</span><select class="param-input" id="guide-horizon"><option value="short">3년 이내</option><option value="medium" selected>3년 ~ 7년</option><option value="long">7년 이상</option></select></label>
          <label><span>가격이 내려갈 때 내 마음은?</span><select class="param-input" id="guide-risk"><option value="low">불안해서 빠르게 줄이고 싶어요</option><option value="medium" selected>상황을 보며 유지할 수 있어요</option><option value="high">길게 보고 기다릴 수 있어요</option></select></label>
          <button class="run-btn" id="guide-run"><i class="fa-solid fa-wand-magic-sparkles"></i> 구성 예시 보기</button>
        </section>
        <div id="guide-result"><p class="portfolio-guide-loading">추천 구성을 불러오는 중입니다…</p></div>
      </div>
      <section class="portfolio-guide-check"><h2><i class="fa-solid fa-list-check"></i> 구성 전에 확인해 보세요</h2><div><p><b>생활비와 비상금</b><span>가까운 시일에 쓸 돈은 투자금과 분리했나요?</span></p><p><b>한 종목 쏠림</b><span>좋아하는 종목이나 같은 업종에 너무 많이 담기지 않았나요?</span></p><p><b>정기 점검</b><span>정한 목적과 비중이 지금도 내 상황에 맞는지 살펴보세요.</span></p></div></section>
      <p class="portfolio-guide-disclaimer">이 내용은 금융 교육을 위한 일반적인 구성 예시이며, 개인별 투자 조언이나 수익을 보장하는 추천이 아닙니다.</p>
    </section>`;

  const result = container.querySelector('#guide-result');
  const sharpeHelp = container.querySelector('#sharpe-help');
  const sharpeModal = container.querySelector('#sharpe-modal');
  const sharpePanel = sharpeModal.querySelector('.sharpe-modal');

  const closeSharpeModal = () => {
    sharpeModal.hidden = true;
    sharpeHelp.setAttribute('aria-expanded', 'false');
    sharpeHelp.focus();
  };
  sharpeHelp.addEventListener('click', () => {
    sharpeModal.hidden = false;
    sharpeHelp.setAttribute('aria-expanded', 'true');
    sharpePanel.focus();
  });
  sharpeModal.querySelector('.sharpe-modal-close').addEventListener('click', closeSharpeModal);
  sharpeModal.addEventListener('click', (event) => {
    if (event.target === sharpeModal) closeSharpeModal();
  });
  sharpePanel.addEventListener('keydown', (event) => {
    if (event.key === 'Escape') closeSharpeModal();
  });

  const runButton = container.querySelector('#guide-run');

  const answers = () => ({
    goal: container.querySelector('#guide-goal').value,
    horizon: container.querySelector('#guide-horizon').value,
    risk: container.querySelector('#guide-risk').value,
  });

  const showError = (message) => {
    result.innerHTML = `<p class="portfolio-guide-loading" data-state="failed">추천 구성을 불러오지 못했습니다. ${message}</p>`;
  };

  // 진입 시 기본 선택값으로 판정해 보여준다. 예전에는 renderProfile('balanced') 가
  // 하드코딩돼 있었고 기본값의 판정 결과와 우연히 일치했을 뿐이다.
  // preview 는 저장하지 않으므로 방문만으로 이력이 쌓이지 않는다.
  api.recommendationPreview(answers())
    .then((data) => { result.innerHTML = renderProfile(data); })
    .catch((error) => showError(error.message));

  runButton.addEventListener('click', async () => {
    const body = answers();
    runButton.disabled = true;
    try {
      // 버튼을 누른 결과는 이력에 남긴다. 저장이 실패해도 화면은 살아 있어야 하므로
      // preview 로 폴백하되, 저장되지 않았다는 사실을 결과 안에 함께 적는다.
      let data;
      try {
        data = await api.recommendationCreate({ ...body, anon_id: visitorId() });
      } catch (saveError) {
        data = { ...(await api.recommendationPreview(body)), saveFailed: saveError.message };
      }
      result.innerHTML = renderProfile(data);
    } catch (error) {
      showError(error.message);
    } finally {
      runButton.disabled = false;
    }
  });
}
