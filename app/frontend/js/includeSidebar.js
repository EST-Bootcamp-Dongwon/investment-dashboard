/**
 * includeSidebar.js — 정적 MPA 페이지(pages/*.html)에서 공통 사이드바 내비게이션을
 * partials/sidebar-nav.html로부터 fetch 하여 주입한다. 해당 파일은 index.html(SPA)
 * 쪽 사이드바를 생성할 때 자동으로 만들어지므로 직접 수정하지 말 것
 * (readme.md 참고 / scripts/build-sidebar-partial.py 로 재생성).
 *
 * ## 이 파일이 `type="module"` 이 된 이유 (2026-08-16)
 *
 * 원래는 평범한 `<script>` 였다. 그러면 `js/api.js` 에서 `import` 를 못 하고,
 * `fetch` 를 직접 부를 수밖에 없다 — `js/api.js` 단일 진입점 회수의 마지막 걸림돌이
 * 이것이었다. 그래서 두 페이지의 `<script>` 에 `type="module"` 을 붙였다.
 *
 * **`js/sidebarUI.js` 는 일부러 그대로 뒀다.** 그쪽은 `toggleSidebar()` 같은 함수를
 * 전역에 두고 HTML 의 인라인 `onclick=` 이 그걸 부른다. 모듈로 바꾸면 스코프가 갈려
 * 버튼이 전부 죽는다. 이 파일은 전역을 **읽기만** 하므로(아래 23~24줄) 안전하다.
 *
 * 모듈은 defer 처럼 늦게 돈다. `sidebarUI.js` 는 평범한 스크립트라 파싱 중에 먼저
 * 실행되므로, 이 파일이 돌 때 `window._orderSidebarSections` 는 이미 있다.
 *
 * **정적 파일이므로 `apiFetch` 가 아니라 `fetchAssetText` 다.** 경로가 문서 기준
 * 상대경로(`/pages/partials/sidebar-nav.html`)이고 본문이 JSON 이 아니라 HTML 이다.
 * `apiFetch` 로 옮기면 (a) `<meta name="api-base">` 가 앞에 붙어 경로가 깨지고
 * (b) `res.json()` 이 HTML 에서 SyntaxError 를 던져 사이드바가 **항상** 실패한다.
 */
import { fetchAssetText } from './api.js';

(async function includeSidebar() {
  const slot = document.getElementById('sidebar-nav-slot');
  if (!slot) return;

  try {
    slot.outerHTML = await fetchAssetText('partials/sidebar-nav.html');
  } catch (err) {
    slot.innerHTML = `<p style="padding:16px;color:var(--text-muted);font-size:.82rem;">
      메뉴를 불러오지 못했습니다. <a href="../index.html">대시보드로 이동</a>
    </p>`;
    console.error('사이드바 로드 실패:', err);
    return;
  }

  if (typeof window._orderSidebarSections === 'function') window._orderSidebarSections();
  if (typeof window._ensureSidebarChatbot === 'function') window._ensureSidebarChatbot();

  // 현재 정적 페이지에 해당하는 메뉴 링크를 활성 표시
  const page = document.body.dataset.page;
  if (page) {
    const link = document.querySelector(`.nav-item[data-page="${page}"]`);
    if (link) {
      link.classList.add('active');
    }
  }
})();
