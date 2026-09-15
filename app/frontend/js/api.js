/**
 * api.js — 브라우저에서 나가는 **모든 네트워크 요청의 단일 진입점**.
 *
 * ## 왜 단일 진입점이어야 하는가
 *
 * 2026-08-16 실측으로 이 파일 **밖에서 `fetch()` 를 부르는 곳이 7개 파일 10건**이었다
 * (`quant-contract/research/05-dashboard-검증완료.md` P0-3). 그 상태에서는 API 계약을
 * 아무리 잘 써도 **받는 쪽이 8곳이라 계약이 강제되지 않는다.** 팀원이 백엔드를 붙일 때
 * 어느 파일이 어디를 부르는지 매번 추적해야 한다.
 *
 * 그래서 전부 여기로 회수했다. 회수를 **지키는 장치**는 `scripts/check_layers.py` 의
 * 규칙 7번이다 — 이 파일 외의 `js/**` 에서 `fetch(` 가 하나라도 나오면 검사가 실패한다.
 * 규칙은 강제되지 않으면 지켜지지 않는다.
 *
 * ## 두 갈래로 나뉜다 — 이것이 이 파일의 핵심 설계다
 *
 *     apiFetch(path)     → BASE + path.  백엔드 API 를 부른다
 *     fetchAsset(path)   → path 그대로.  **같은 출처의 정적 파일**을 읽는다
 *
 * 05 검증본 §5.2 는 10건을 전부 `apiFetch` 로 옮기라고 적었지만, 그중 2건은
 * **정적 자산이고 상대경로다.**
 *
 *     includeSidebar.js  'partials/sidebar-nav.html'      → /pages/partials/…
 *     pages/youtube.js   '../js/data/youtubeVideos.json'  → /js/data/…
 *
 * `apiFetch` 는 `BASE + path` **문자열 단순 연결**이다. `BASE` 가 빈 문자열인 지금은
 * 우연히 맞지만, `<meta name="api-base">` 가 `https://팀원백엔드` 로 바뀌는 순간
 * `https://팀원백엔드../js/data/youtubeVideos.json` 이 된다. 사이드바와 영상 목록이
 * 조용히 404 가 되고, 원인이 API 설정이라는 걸 아무도 짐작하지 못한다.
 *
 * **정적 자산은 프론트와 언제나 같은 출처다.** 그래서 갈랐다. 지금은 두 함수의 동작이
 * 완전히 같지만(`BASE === ''`), 가르는 비용이 지금 5줄이고 나중엔 디버깅 반나절이다.
 *
 * ## 계약과의 관계
 *
 * 원래 `quant-contract/docs/contracts/api-contract.md` §8 이 이 파일의 규약이었다.
 * 그 저장소는 2026-09-15 제거돼 원문이 없다 — **이제 이 주석과 `toError()` 가 규약 정본이다.**
 * §8.4 가 정한 `new Error(err.detail || …)` 를 그대로 지키되 **두 가지를 더했다** —
 * 아래 `toError()` 의 주석에 이유가 있다.
 */

// ── 기준 URL ────────────────────────────────────────────────────────────────
//
// 빌드 단계를 만들지 않는 주입이다 (ADR-DB-0001 결정 4 · 절대 제약 7 · 계약 §8.2).
// 번들러·환경변수 치환을 쓰지 않으므로 팀원은 **HTML 한 줄**만 바꾼다.
//
//     <meta name="api-base" content="">                      동일 출처 (기본)
//     <meta name="api-base" content="http://localhost:8000">  분리 배포·팀 통합
//
// **기본값이 빈 문자열인 것이 중요하다.** 개인 배포본은 아무것도 바꾸지 않아도
// 지금까지와 똑같이 돈다 — `docs/spec/60-운영/배포-전략.md` §4.2 가 확정한
// "Vercel 은 정적과 함수를 한 도메인에 얹으므로 BASE 를 그대로 두면 된다" 가
// 그대로 유효하다. 이 승격은 그 결정을 **뒤집는 게 아니라 설정 지점을 만드는 것**이다.
//
// `??` 는 null·undefined 에서만 넘어간다. `content=""` 인 meta 가 있으면 빈 문자열이
// 그대로 채택되고(= 명시적 동일 출처), meta 가 아예 없을 때만 다음 후보로 간다.
const BASE = (
  document.querySelector('meta[name="api-base"]')?.content
  ?? window.__API_BASE__
  ?? ''
).replace(/\/+$/, '');   // 끝 슬래시를 걷는다. 'http://x:8000/' + '/api/…' = '//api/…'

// ── 요청 조립 ───────────────────────────────────────────────────────────────

/**
 * `fetch` 의 두 번째 인자를 만든다. 옛 구현의 **버그 두 개**를 여기서 고친다.
 *
 * 옛 구현은 `{ headers: {…}, ...options }` 였다. 즉 `options.headers` 가 있으면
 * 기본 헤더를 **통째로 대체**했다. 그래서 두 곳이 위험했다.
 *
 * ① `views/adminRagIndex.js` 는 `Authorization` 을 넘긴다 → `Content-Type` 이 사라져
 *    `POST /api/admin/rag/reindex` 가 422 가 된다. **그래서 병합한다.**
 * ② `views/taxAccounting.js` 는 `FormData` 를 보내는데 헤더를 **하나도 안 넘긴다**
 *    → 기본 `Content-Type: application/json` 이 그대로 붙는다 → 브라우저가 multipart
 *    boundary 를 만들지 않아 `file: UploadFile = File(...)` 이 본문을 못 읽는다.
 *    **그래서 FormData 면 Content-Type 을 넣지 않는다.**
 *
 * ②는 회수하는 순간 업로드가 통째로 죽는 자리였다. 옛 코드가 `fetch` 를 직접 부른 덕에
 * 우연히 피해 가고 있었을 뿐이다.
 */
function buildInit(options = {}, { defaultJsonHeader = true } = {}) {
  const { headers, ...rest } = options;
  const merged = { ...headers };

  const isFormData = typeof FormData !== 'undefined' && rest.body instanceof FormData;
  const hasContentType = Object.keys(merged).some((k) => k.toLowerCase() === 'content-type');

  if (defaultJsonHeader && !isFormData && !hasContentType) {
    merged['Content-Type'] = 'application/json';
  }
  return { ...rest, headers: merged };
}

/**
 * 실패 응답을 `Error` 로 바꾼다.
 *
 * 계약 §8.4 의 기준 형태는 이렇다.
 *
 *     const err = await res.json().catch(() => ({ detail: res.statusText }));
 *     const e = new Error(err.detail || res.statusText);
 *     e.code = err.code ?? 'UNKNOWN'; e.status = res.status; e.traceId = err.trace_id;
 *
 * **`e.message` 가 `detail` 문자열 그대로여야 한다는 규약을 지킨다.** 화면 코드가
 * `e.message` 를 그대로 보여 주고 있기 때문이다. 다만 두 가지를 더했고, 둘 다
 * **`detail` 이 문자열일 때는 동작이 한 글자도 다르지 않다.**
 *
 * ① **배열 detail 평탄화.** FastAPI 의 422 검증 오류는 `detail` 이 **배열**이다.
 *    배열을 그대로 넣으면 화면에 `[object Object]` 가 뜬다. `pages/backtest-lab.js`
 *    가 이 평탄화를 갖고 있었고(옛 `post()` 의 238~241줄), 회수하면서 잃으면
 *    "날짜 형식이 올바르지 않습니다…" 같은 문구가 사라진다. 계약 §2-6 이
 *    `/api/v1/*` 의 `detail` 을 문자열로 못 박았지만 **구 표면 `/api/*` 는 여전히
 *    배열을 낸다** — 그 둘을 같은 함수가 받는다.
 * ② **HTTP/2 에서 `statusText` 는 빈 문자열이다.** 폴백이 `''` 면 `new Error('')` 가
 *    되어 화면에 "오류: " 만 뜬다. 상태 코드를 폴백에 남긴다.
 */
async function toError(res) {
  const body = await res.json().catch(() => ({}));
  const detail = Array.isArray(body.detail)
    ? body.detail.map((d) => d?.msg || JSON.stringify(d)).join(' / ')
    : body.detail;

  const error = new Error(detail || res.statusText || `HTTP ${res.status}`);
  error.code = body.code ?? 'UNKNOWN';   // 계약 §7 의 기계 판독용 상수
  error.status = res.status;
  error.traceId = body.trace_id;
  // 서버가 `detail` 을 줬는지 자체를 남긴다. `message` 만 보면 "detail 이 'Not Found'
  // 였다" 와 "detail 이 없어 statusText 로 떨어졌다" 를 구분할 수 없는데,
  // `views/adminRagIndex.js` 는 후자일 때만 자기 한국어 문구를 쓴다.
  error.detail = detail;
  return error;
}

async function request(url, options, initOpts) {
  const res = await fetch(url, buildInit(options, initOpts));
  if (!res.ok) throw await toError(res);
  return res;
}

// ── 진입점 ①: 백엔드 API ────────────────────────────────────────────────────

/** 백엔드 API 를 부른다. `BASE`(= `<meta name="api-base">`)가 앞에 붙는다. */
export async function apiFetch(path, options = {}) {
  const res = await request(BASE + path, options);
  return res.json();
}

// ── 진입점 ②: 같은 출처의 정적 파일 ────────────────────────────────────────
//
// **`BASE` 를 붙이지 않는다.** 파일 머리말의 이유 그대로 — 이 자산들은 프론트와
// 언제나 같은 출처에 있고, 경로가 문서 기준 상대경로다.

/** 같은 출처의 정적 JSON 을 읽는다. */
export async function fetchAsset(path, options = {}) {
  const res = await request(path, options, { defaultJsonHeader: false });
  return res.json();
}

/** 같은 출처의 정적 텍스트(HTML 조각 등)를 읽는다. */
export async function fetchAssetText(path, options = {}) {
  const res = await request(path, options, { defaultJsonHeader: false });
  return res.text();
}

// ── 구 표면 헬퍼 (그대로 유지) ──────────────────────────────────────────────
// 계약 §8.3: "기존 `api` 객체는 그대로 둔다. `/api/*` 구 표면을 부르는 화면이 계속
// 동작해야 한다 — 개인 완결성이 기본이다."

export async function apiGet(path) { return apiFetch(path); }
export async function apiPost(path, body) { return apiFetch(path, { method: 'POST', body: JSON.stringify(body) }); }
export async function withLoading(btn, fn) {
  btn.disabled = true;
  const orig = btn.textContent;
  btn.textContent = '실행 중...';
  try { return await fn(); } finally { btn.disabled = false; btn.textContent = orig; }
}
export function renderError(msg) { return `<p style="color:#ef4444; margin-top:12px;">오류: ${msg}</p>`; }
export function renderImage(src) { return src ? `<img src="${src}" style="width:100%; border-radius:8px; margin-top:16px;"/>` : ''; }
export function renderMetrics(m) {
  if (!m) return '';
  return `<div style="display:flex; flex-wrap:wrap; gap:12px; margin-top:16px;">
    ${Object.entries(m).map(([k, v]) => `
      <div class="metric-box">
        <div style="font-size:0.7rem; color:#64748b; text-transform:uppercase; margin-bottom:4px;">${k.replace(/_/g,' ')}</div>
        <div style="font-size:1rem; font-weight:700; color:#3b82f6;">${typeof v === 'number' ? v.toFixed(4) : v}</div>
      </div>`).join('')}
  </div>`;
}

/**
 * `POST + JSON 바디` 래퍼를 만든다. 옛 코드가 40줄에 걸쳐 손으로 반복하던 형태
 * (`(body) => apiFetch(path, { method:'POST', body: JSON.stringify(body) })`)와
 * **인자 하나로 부를 때 동작이 완전히 같다.**
 *
 * 두 번째 인자 `options` 를 더한 이유가 있다 — `views/home.js` 가 시세 새로고침에
 * `AbortSignal` 을 쓴다. 연타하면 이전 요청을 취소해야 늦게 도착한 응답이 최신 화면을
 * 덮어쓰지 않는다. **옵션 자리가 없으면 그 화면은 `fetch` 를 직접 부를 수밖에 없고,
 * 그러면 회수가 무너진다.** 진입점을 하나로 만들려면 진입점이 필요한 것을 받아야 한다.
 */
const post = (path) => (body, options = {}) =>
  apiFetch(path, { method: 'POST', body: JSON.stringify(body), ...options });

export const api = {
  health:           ()      => apiFetch('/api/health'),
  systemResources:  ()      => apiFetch('/api/system/resources'),
  visitorHeartbeat: post('/api/visitors/heartbeat'),
  crossValidation:  post('/api/ml/cross-validation'),
  decisionBoundary: ()      => apiFetch('/api/ml/decision-boundary'),
  randomForest:     post('/api/ml/random-forest'),
  kmeans:           post('/api/ml/kmeans'),
  svm:              post('/api/ml/svm'),
  mlp:              post('/api/ml/mlp'),
  linearRegression: post('/api/ml/linear-regression'),
  textClassify:     post('/api/nlp/text-classify'),
  opencv:           post('/api/cv/circle-animation'),
  huggingface:      post('/api/genai/text-to-image'),
  cnnTimeseries:    post('/api/dl/cnn-timeseries'),
  lstm:             post('/api/dl/lstm-predictor'),
  transformer:      post('/api/dl/transformer-timeseries'),
  backtest:         post('/api/quant/backtest'),
  portfolio:        post('/api/quant/portfolio'),
  portfolioScenario:post('/api/quant/portfolio-scenario'),
  portfolioCombination: post('/api/market/portfolio-combination'),
  // F03 포트폴리오 추천. preview 는 저장하지 않으므로 DB 가 죽어도 동작한다.
  recommendationPreview: post('/api/recommendation/preview'),
  recommendationCreate:  post('/api/recommendation/create'),
  recommendationHistory: (anonId, limit = 20) =>
    apiFetch(`/api/recommendation/history?anon_id=${encodeURIComponent(anonId)}&limit=${encodeURIComponent(limit)}`),
  recommendationDetail:  (id, anonId) =>
    apiFetch(`/api/recommendation/detail?id=${encodeURIComponent(id)}&anon_id=${encodeURIComponent(anonId)}`),
  risk:             post('/api/quant/risk'),
  pipeline:         post('/api/quant/pipeline'),
  financialKnowledge: post('/api/quant/financial-knowledge'),
  marketSnapshot:   post('/api/market/snapshot'),   // 2번째 인자로 `{ signal }` 을 받는다
  marketVolumeCloud:(market) => apiFetch(`/api/market/volume-cloud?market=${encodeURIComponent(market)}`),
  macroRealtime:    post('/api/macro/realtime'),
  macroSimulation:  post('/api/macro/simulation'),
  dartCompanySearch:post('/api/dart/company-search'),
  dartCompanyList:  post('/api/dart/company-list'),
  groupNetwork:     post('/api/dart/group-network'),
  industryPorter:   post('/api/industry/porter'),
  industrySector:   post('/api/industry/sector'),
  industryPeer:     post('/api/industry/peer'),
  industryLifecycle:post('/api/industry/lifecycle'),
  companyFinancials:post('/api/finance/company-financials'),
  kospiExMeta:      ()      => apiFetch('/api/macro/kospi-ex/meta'),
  kospiEx:          post('/api/macro/kospi-ex'),
  dartFinancialAnalysis: post('/api/dart/financial-analysis'),
  taxSample:        ()      => apiFetch('/api/tax/sample'),
  taxSimulate:      post('/api/tax/simulate'),

  // ── 회수로 새로 들어온 것 (옛 직접 fetch) ──────────────────────────────
  homeMarketCandle: (market, period) =>
    apiFetch(`/api/home/market-candle?market=${encodeURIComponent(market)}&period=${encodeURIComponent(period)}`),
  taxUpload:        (formData) => apiFetch('/api/tax/upload', { method: 'POST', body: formData }),
  ragStatus:        ()      => apiFetch('/api/rag/status'),
  ragAsk:           post('/api/rag/ask'),
  backtestLabConfig:()      => apiFetch('/api/backtest-lab/config'),
  backtestLabRun:   post('/api/backtest-lab/run'),
  backtestLabReport:post('/api/backtest-lab/report'),
  // 관리자 화면은 요청마다 토큰이 달라 경로·옵션을 그대로 받는다.
  adminRag:         (path, options = {}) => apiFetch(`/api/admin/rag${path}`, options),
};
