/**
 * 관리자 · F27 문서 색인 운영 화면.
 *
 * 백엔드: app/backend/routers/admin.py (`/api/admin/rag/*`)
 *
 * ## 왜 토큰을 붙여 넣게 하는가
 *
 * 이 저장소의 프런트에는 **인증 코드가 0건이다** (2026-08-14 실측:
 *   grep -rn "supabase|access_token|Authorization|Bearer" app/frontend/js/  → 0건).
 * 로그인 화면도 세션 보관도 없다. 그래서 지금 토큰을 얻을 방법은 사람이 Supabase
 * 에서 복사해 오는 것뿐이다.
 *
 * 로그인 화면을 여기서 만들지 않은 것은 그것이 F27 색인 운영이 아니라 **인증 기능
 * 자체**라서다. 저장 기능 4벌(F03·F04·F05·F28)도 전부 토큰 없이 anon_id 로 돌고 있고,
 * 로그인을 붙이는 순간 그 넷의 소유자 판별이 전부 영향을 받는다. 한 세션에 한 작업이다.
 *
 * 토큰은 `sessionStorage` 에 둔다 — `localStorage` 는 탭을 닫아도 남는다.
 * 공용 PC 에서 관리자 토큰이 디스크에 남는 쪽을 고르지 않는다.
 *
 * ## 이 화면이 존재하는 이유는 `orphan` 이다
 *
 * 문서를 지우거나 이름을 바꾸면 옛 청크가 DB 에 그대로 남고, 검색은 지금 저장소에
 * 없는 문장을 근거라고 내놓는다. DB 만 보거나 파일만 봐서는 안 보이고 둘을 맞대야
 * 드러난다 — 서버의 `GET /documents` 가 그 대조를 하고 여기서 색으로 보여 준다.
 */

const TOKEN_KEY = 'adminAccessToken';

const STATE_BADGE = {
  indexed: { className: 'badge badge-green', label: '색인됨' },
  missing: { className: 'badge badge-yellow', label: '색인 없음' },
  orphan: { className: 'badge badge-red', label: '파일 없음' },
};

function escapeHtml(value) {
  return String(value).replace(/[&<>'"]/g, (char) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', "'": '&#39;', '"': '&quot;' }[char]));
}

function formatTime(value) {
  if (!value) return '—';
  const parsed = new Date(value);
  return Number.isNaN(parsed.getTime()) ? '—' : parsed.toLocaleString('ko-KR');
}

export function adminRagIndexView(app) {
  let token = sessionStorage.getItem(TOKEN_KEY) || '';
  let payload = null;
  let message = '';
  let busy = false;

  async function callAdmin(path, options = {}) {
    if (!token) throw new Error('액세스 토큰을 먼저 입력하세요.');
    const response = await fetch(`/api/admin/rag${path}`, {
      ...options,
      headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${token}` },
    });
    const data = await response.json().catch(() => ({}));
    if (!response.ok) {
      // 401·403·503 을 서버가 이미 갈라 준다(routers/owner.require_admin).
      // 문구를 여기서 다시 짓지 않고 그대로 보여 준다 — 로그인하면 되는 상황과
      // 로그인해도 안 되는 상황을 사용자가 구분할 수 있어야 한다.
      throw new Error(data.detail || `요청이 실패했습니다 (HTTP ${response.status}).`);
    }
    return data;
  }

  async function load() {
    if (!token) { payload = null; render(); return; }
    busy = true; render();
    try {
      payload = await callAdmin('/documents');
      message = '';
    } catch (error) {
      payload = null;
      message = error.message;
    }
    busy = false;
    render();
  }

  async function reindex(sourceDoc) {
    busy = true; message = sourceDoc ? `${sourceDoc} 재색인 중…` : '전체 재색인 중…'; render();
    try {
      const result = await callAdmin('/reindex', {
        method: 'POST',
        body: JSON.stringify(sourceDoc ? { source_doc: sourceDoc } : {}),
      });
      message = `재색인 완료 — 문서 ${result.reindexed}개 · ${result.total_chunks}청크`;
      payload = await callAdmin('/documents');
    } catch (error) {
      message = error.message;
    }
    busy = false;
    render();
  }

  async function removeDocument(sourceDoc) {
    // 되돌릴 수 없는 조작이라 한 번 묻는다. 지우는 것은 색인이고 파일은 그대로다.
    if (!window.confirm(`${sourceDoc} 의 색인을 지웁니다. 문서 파일은 지워지지 않습니다. 계속할까요?`)) return;
    busy = true; render();
    try {
      await callAdmin(`/documents/${encodeURIComponent(sourceDoc)}`, { method: 'DELETE' });
      message = `${sourceDoc} 색인을 삭제했습니다.`;
      payload = await callAdmin('/documents');
    } catch (error) {
      message = error.message;
    }
    busy = false;
    render();
  }

  function renderRows() {
    const documents = payload?.documents || [];
    if (!documents.length) {
      return '<tr><td colspan="6" class="admin-empty">표시할 문서가 없습니다.</td></tr>';
    }
    return documents.map((doc) => {
      const badge = STATE_BADGE[doc.state] || STATE_BADGE.missing;
      return `
        <tr>
          <td><code>${escapeHtml(doc.source_doc)}</code></td>
          <td><span class="${badge.className}">${badge.label}</span></td>
          <td class="admin-num">${Number(doc.chunk_count || 0).toLocaleString()}</td>
          <td>${escapeHtml(doc.embed_method || '—')}</td>
          <td>${escapeHtml(formatTime(doc.indexed_at))}</td>
          <td class="admin-actions">
            ${doc.on_disk ? `<button type="button" class="btn btn-secondary btn-sm js-reindex" data-doc="${escapeHtml(doc.source_doc)}">재색인</button>` : ''}
            ${doc.chunk_count ? `<button type="button" class="btn btn-secondary btn-sm js-delete" data-doc="${escapeHtml(doc.source_doc)}">색인 삭제</button>` : ''}
          </td>
        </tr>`;
    }).join('');
  }

  function render() {
    app.innerHTML = `
      <section class="card">
        <h2><i class="fa-solid fa-database"></i> 관리자 · 문서 색인</h2>
        <p class="admin-lead">
          F27 문서 검색이 쓰는 <code>doc_chunk</code> 색인을 관리합니다.
          저장소의 <code>docs/*.md</code> 와 DB 를 대조해 어긋난 것을 보여 줍니다.
        </p>

        <div class="admin-token">
          <label for="admin-token">Supabase 액세스 토큰</label>
          <input id="admin-token" type="password" class="param-input" autocomplete="off"
                 placeholder="Bearer 없이 토큰만 붙여 넣으세요" value="${escapeHtml(token)}" />
          <button type="button" id="admin-token-save" class="btn btn-primary btn-sm">확인</button>
          <small>
            <code>app_admin</code> 에 등록된 계정만 사용할 수 있습니다.
            토큰은 이 탭에서만 보관되며 새로고침해도 남지만 탭을 닫으면 사라집니다.
          </small>
        </div>

        ${message ? `<p class="admin-message">${escapeHtml(message)}</p>` : ''}

        ${payload ? `
          <div class="admin-summary">
            <span>문서 <strong>${(payload.documents || []).length}</strong></span>
            <span>청크 <strong>${Number(payload.total_chunks || 0).toLocaleString()}</strong></span>
            <span>임베딩 <strong>${escapeHtml(payload.embed_method || '—')}</strong></span>
            <span class="admin-path"><code>${escapeHtml(payload.docs_dir || '')}</code></span>
          </div>
          <div class="admin-toolbar">
            <button type="button" id="admin-reindex-all" class="btn btn-primary btn-sm" ${busy ? 'disabled' : ''}>전체 재색인</button>
            <button type="button" id="admin-refresh" class="btn btn-secondary btn-sm" ${busy ? 'disabled' : ''}>새로고침</button>
          </div>
          <div class="admin-table-wrap">
            <table class="admin-table">
              <thead><tr><th>문서</th><th>상태</th><th class="admin-num">청크</th><th>임베딩</th><th>색인 시각</th><th>작업</th></tr></thead>
              <tbody>${renderRows()}</tbody>
            </table>
          </div>
        ` : '<p class="admin-lead">토큰을 입력하면 색인 현황을 불러옵니다.</p>'}
      </section>`;

    app.querySelector('#admin-token-save').addEventListener('click', () => {
      token = app.querySelector('#admin-token').value.trim();
      if (token) sessionStorage.setItem(TOKEN_KEY, token);
      else sessionStorage.removeItem(TOKEN_KEY);
      load();
    });

    app.querySelector('#admin-refresh')?.addEventListener('click', () => load());
    app.querySelector('#admin-reindex-all')?.addEventListener('click', () => reindex(null));
    app.querySelectorAll('.js-reindex').forEach((button) =>
      button.addEventListener('click', () => reindex(button.dataset.doc)));
    app.querySelectorAll('.js-delete').forEach((button) =>
      button.addEventListener('click', () => removeDocument(button.dataset.doc)));
  }

  render();
  if (token) load();
}
