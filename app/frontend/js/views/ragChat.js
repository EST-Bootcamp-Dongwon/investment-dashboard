import { api } from '../api.js';
import { disclaimer, DISCLAIMER_CONTEXT } from '../components/disclaimer.js';

const EXAMPLES = ['PER과 PBR의 차이를 알려줘', 'ETF 괴리율은 왜 생기나요?', '지정가 주문과 시장가 주문의 차이는?', '분산투자의 목적은 무엇인가요?'];

function escapeHtml(value) {
  return String(value).replace(/[&<>'"]/g, (char) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', "'": '&#39;', '"': '&quot;' }[char]));
}

function formatText(value) {
  return escapeHtml(value).replace(/\n/g, '<br>');
}

export function ragChatView(app) {
  const messages = [];
  let sources = [];
  let followups = [];
  let followupsHead = '';

  function renderSources() {
    if (!sources.length) {
      return '<div class="rag-source-empty"><i class="fa-solid fa-file-lines"></i><p>질문을 보내면 RAG가 찾은 원문 문서 조각이 여기에 표시됩니다.</p></div>';
    }
    return sources.map((source, index) => `
      <article class="rag-source-card">
        <div class="rag-source-head"><strong>출처 ${index + 1}</strong><span>유사도 ${Number(source.score).toFixed(3)}</span></div>
        <p class="rag-source-name">${escapeHtml(source.source_doc)} · 문서 조각 ${Number(source.chunk_index) + 1}</p>
        <p class="rag-source-text">${formatText(source.text)}</p>
      </article>`).join('');
  }

  // 후속 질문 (R-04 · CN-128). 서버가 검색된 원문에서 규칙으로 뽑아 준 문자열이다.
  // 버튼 텍스트와 data-query 양쪽에 escapeHtml 을 건다 — .rag-example 버튼이 이미
  // 쓰는 것과 정확히 같은 이중 이스케이프다. formatText 는 쓰지 않는다: 한 줄 질문이라
  // <br> 변환이 필요 없고, HTML 을 만드는 경로를 하나 줄인다.
  //
  // 후보가 없으면 빈 문자열이다 — 껍데기만 있는 블록을 그리지 않는다. 서버가 질의와
  // 어휘가 겹치는 것만 고르므로(services/rag.build_followups 의 관문) 빈 경우가 실제로 있다.
  function renderFollowups() {
    if (!followups.length) return '';
    return `
      <div class="rag-followups" aria-label="${escapeHtml(followupsHead)}">
        <span class="rag-followups-label">${escapeHtml(followupsHead)}</span>
        ${followups.map((question) => `<button type="button" class="btn btn-secondary btn-sm rag-followup" data-query="${escapeHtml(question)}">${escapeHtml(question)}</button>`).join('')}
      </div>`;
  }

  function render() {
    app.innerHTML = `
      <section class="card rag-chat-heading">
        <div class="rag-chat-heading-copy">
          <h2><i class="fa-solid fa-comments"></i>문서 검색 채팅</h2>
          <p>RAG가 학습 문서에서 관련 조각을 찾습니다. 답변은 검색된 원문만 정리하며, 원문은 오른쪽에서 확인할 수 있습니다.</p>
          <!-- R-07 · CN-060 1순위 적용 대상. 질문을 던지기 *전에도* 보이도록 헤딩 바로 아래에 둔다 —
               답변 말풍선에 붙이면 첫 화면에는 아무 문구도 없다.
               문장은 components/disclaimer.js 가 정본이고, 같은 문장이 서버 응답의
               disclaimer 필드로도 나간다(services/rag.py). 두 사본이 같은지는
               scripts/verify_rag_api.py 가 대조한다. -->
          ${disclaimer('strong', { context: DISCLAIMER_CONTEXT.F27 })}
        </div>
        <div class="rag-chat-controls">
          <!-- 2026-08-16: "답변 다듬기" 선택(RAG만 / 외부 AI · OpenAI 호환)을 없앴습니다.
               외부 AI 경로가 유료 API 호출이었고, 절대 제약 1이 "LLM 유료 API 비용 0원"
               입니다. 고를 것이 하나뿐인 셀렉트는 선택지가 아니라 거짓말이라 통째로
               걷고 무엇으로 답하는지를 문장으로 적습니다. -->
          <small id="rag-provider-note">답변은 검색된 학습 문서 원문만 조립해 만듭니다. 외부 AI를 부르지 않습니다.</small>
          <span id="rag-status" class="badge badge-gray">연결 확인 중</span>
        </div>
      </section>
      <section class="rag-chat-layout">
        <section class="card rag-chat-panel">
          <div id="rag-messages" class="rag-messages" aria-live="polite">
            ${messages.length ? messages.map((message) => `<div class="rag-message is-${message.role}">${formatText(message.text)}</div>`).join('') : '<div class="rag-welcome"><strong>무엇이 궁금한가요?</strong><br>예: “ETF 괴리율은 왜 생기나요?”</div>'}
            ${renderFollowups()}
          </div>
          <div class="rag-chat-compose">
            <div class="rag-examples">${EXAMPLES.map((example) => `<button type="button" class="btn btn-secondary btn-sm rag-example" data-query="${escapeHtml(example)}">${escapeHtml(example)}</button>`).join('')}</div>
            <form id="rag-form" class="rag-form">
              <input id="rag-input" maxlength="500" placeholder="문서에서 찾을 질문을 입력하세요" aria-label="문서 검색 질문" />
              <button class="btn btn-primary" type="submit"><i class="fa-solid fa-paper-plane"></i> 질문</button>
            </form>
          </div>
        </section>
        <aside class="card rag-source-panel" aria-label="RAG 검색 원문">
          <div class="rag-source-title"><div><h3><i class="fa-solid fa-book-open"></i>RAG 검색 원문</h3><p>채팅 답변의 근거가 된 문서 조각입니다.</p></div><span>${sources.length ? `${sources.length}개` : '대기 중'}</span></div>
          <div id="rag-sources" class="rag-sources">${renderSources()}</div>
        </aside>
      </section>`;

    const messagesEl = app.querySelector('#rag-messages');
    messagesEl.scrollTop = messagesEl.scrollHeight;
    app.querySelectorAll('.rag-example').forEach((button) => button.addEventListener('click', () => ask(button.dataset.query)));
    app.querySelectorAll('.rag-followup').forEach((button) => button.addEventListener('click', () => ask(button.dataset.query)));
    app.querySelector('#rag-form').addEventListener('submit', (event) => {
      event.preventDefault();
      const input = app.querySelector('#rag-input');
      ask(input.value.trim());
    });
    updateStatus();
  }

  async function updateStatus() {
    try {
      // 옛 코드는 `res.ok` 를 안 보고 본문만 읽어서, 비-2xx 여도 아래 갱신이 돌았다.
      // `apiFetch` 는 비-2xx 에서 던지므로 그때는 catch 의 'RAG 상태 확인 실패' 로 간다.
      // `rag_status` 는 예외를 던지지 않게 짜여 있어(`routers/rag.py`) 정상 경로에서
      // 이 차이는 드러나지 않는다 — 프록시·게이트웨이 오류일 때만 갈린다.
      const data = await api.ragStatus();
      const status = app.querySelector('#rag-status');
      const providerNote = app.querySelector('#rag-provider-note');
      if (!status || !providerNote) return;
      // 저장소가 Qdrant → Supabase pgvector 로 바뀌면서 응답 키가 `qdrant` 에서
      // `vector_store` 가 됐다(D-08 · CN-021). 저장소 이름을 스키마에 박아 두면
      // 옮길 때마다 화면이 거짓말을 한다. `collection_available` → `indexed`,
      // `points_count` → `total_chunks` 도 같은 이유로 이름이 바뀌었다.
      const store = data.vector_store;
      if (store?.indexed) {
        status.className = 'badge badge-green';
        status.textContent = `문서 ${Number(store.total_chunks || 0).toLocaleString()}개 청크 연결됨`;
      } else if (store?.available) {
        status.className = 'badge badge-gray';
        status.textContent = '문서 색인 필요';
        providerNote.textContent = '학습 문서가 아직 색인되지 않았습니다. 관리자에게 문서 색인을 요청하세요.';
      } else status.textContent = '벡터 DB 연결 안 됨';
    } catch {
      const status = app.querySelector('#rag-status');
      if (status) status.textContent = 'RAG 상태 확인 실패';
    }
  }

  async function ask(query) {
    if (!query) return;
    // 로딩 렌더와 에러 경로 양쪽에서 직전 질의의 제안이 남지 않게 **fetch 전에** 비운다.
    // 후속 질문은 답변 말풍선 바로 아래라 "이 답변의 후속" 으로 읽히므로, 남으면
    // 화면이 거짓말을 한다.
    followups = [];
    followupsHead = '';
    messages.push({ role: 'user', text: query }, { role: 'assistant loading', text: '문서에서 찾는 중…' });
    render();
    try {
      // 변수명을 `data` 로 유지해야 한다 — `scripts/verify_rag_api.py` 가 이 파일 원문에서
      // 문자열 `data.followups` · `data.followups_head` 를 grep 해 R-04 이행을 판정한다.
      // 구조분해로 바꾸면 검증이 깨진다.
      const data = await api.ragAsk({ query, top_k: 5 });
      messages.pop();
      sources = data.sources || [];
      followups = Array.isArray(data.followups) ? data.followups : [];
      followupsHead = data.followups_head || '';
      messages.push({ role: 'assistant', text: data.answer || '관련 문서를 찾지 못했습니다.' });
    } catch (error) {
      // 실패 시 `messages.pop()` 은 **여기 한 번만** 돈다. 옛 코드는 본문을 먼저 읽고
      // pop 한 뒤 던져서 catch 에서 또 pop 했고, 그래서 사용자 질문 말풍선까지 지워졌다.
      // 이제 로딩 말풍선만 지워지고 질문이 남는다 — 회귀가 아니라 그 결함이 사라진 것이다.
      messages.pop();
      messages.push({ role: 'error', text: error.message || '문서 검색에 실패했습니다.' });
    }
    render();
  }

  render();
}
