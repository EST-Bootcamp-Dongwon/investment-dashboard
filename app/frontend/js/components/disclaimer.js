/**
 * 면책 공통 컴포넌트 — CN-060 확정 사양.
 *
 * 강사님 요구 R-07 원문:
 *   "AI 답변에는 교육용 정보이며 개인별 투자 조언이 아니라는 문구를 유지합니다"
 *   (docs/07.md:197)
 *
 * 사양 정본은 docs/spec/50-UI/화면-상세.md 3.2절이다. 문구를 새로 짓지 않았다 —
 * 세 단계 문장과 F27 의 context 한 줄까지 그 표에 이미 적혀 있던 것을 그대로 옮겼다.
 *
 * ## 서버에도 같은 문장이 있다
 *
 * app/backend/services/rag.py 의 DISCLAIMER · DISCLAIMER_CONTEXT 가 같은 문자열을
 * 들고 있고, POST /api/rag/ask 응답에 실려 나온다. 요구가 "AI 답변에는" 이라고
 * 답변 자체를 지목하기 때문에, 화면을 거치지 않고 API 를 직접 부르는 경로에서도
 * 문구가 붙어야 한다.
 *
 * 사본이 둘인 것은 한쪽이 파이썬이고 한쪽이 브라우저 자바스크립트라 공유할 런타임이
 * 없기 때문이다. **대신 갈라지는지를 자동으로 본다** — scripts/verify_rag_api.py 가
 * 두 파일에서 문자열을 뽑아 == 로 대조한다.
 *
 * ## 이번 세션에서 실제로 쓰는 것은 strong 하나다
 *
 * CN-060 은 화면 29개(strong 8 · default 19 · inline 2)를 지정했지만, 이번에 붙인
 * 곳은 F27(ragChat.js) 한 곳이다. 나머지는 **문구만 붙여서 해결되지 않는 화면이
 * 섞여 있어서** 별도 작업이 필요하다 — F25 는 실명 금융상품 19개 교체(CN-048)가,
 * F23 은 "매수/관망" 배지 교체(CN-046)가 먼저다. 화면-상세.md 3.4절이 그 순서를
 * 못박았다: "문구를 붙인다고 상품 추천이 교육이 되지 않습니다."
 *
 * default·inline 을 지금 정의해 두는 것은 다음 화면이 붙을 때 문구를 다시 정하지
 * 않기 위해서다. 호출처가 아직 없다는 것은 알고 둔다.
 */

/** 단계별 본문. 화면-상세.md 3.2절 표와 같은 문장이다. */
export const DISCLAIMER_TEXT = {
  strong:
    '이 화면의 결과는 금융 교육을 위한 예시이며, 개인별 투자 조언이나 특정 상품 추천이 아닙니다. 투자 판단과 그 결과는 본인의 책임입니다.',
  default:
    '교육용 정보이며 개인별 투자 조언이 아닙니다. 실제 투자 전 원자료와 공시를 직접 확인하세요.',
  inline: '교육용 예시',
};

/** 화면별 한 문장. 확정된 것만 둔다 — 나머지는 그 화면을 손댈 때 추가한다. */
export const DISCLAIMER_CONTEXT = {
  F27: 'AI 답변은 색인된 학습 문서를 근거로 생성되며, 원문에 없는 내용은 확인이 필요합니다.',
  F05: '세금·수수료·물가·예상 밖 시장 충격은 반영하지 않았습니다.',
  F07: '계산에 쓰인 가격은 실제 시세가 아니라 시뮬레이션 값입니다.',
  F23: '재무비율만 본 결과이며 주가·밸류에이션은 반영하지 않았습니다.',
};

function escapeHtml(value) {
  return String(value).replace(/[&<>'"]/g, (char) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', "'": '&#39;', '"': '&quot;' }[char]));
}

/**
 * 면책 마크업을 문자열로 돌려준다. 이 저장소의 뷰가 전부 innerHTML 템플릿이라
 * DOM 노드가 아니라 문자열을 준다.
 *
 * @param {'strong'|'default'|'inline'} level 표시 강도
 * @param {{ context?: string }} [options] context 는 화면별 한 문장
 * @returns {string} HTML
 */
export function disclaimer(level = 'default', { context = '' } = {}) {
  const body = DISCLAIMER_TEXT[level] || DISCLAIMER_TEXT.default;
  // 서버가 내려준 문장을 그대로 받을 수 있게 context 를 인자로 둔다. 응답에
  // disclaimer_context 가 있으면 그것을 넘기면 되고, 없으면 위 상수를 쓰면 된다.
  const tail = context ? ` ${escapeHtml(context)}` : '';

  if (level === 'inline') {
    return `<span class="disclaimer-inline">※ ${escapeHtml(body)}${tail}</span>`;
  }
  if (level === 'strong') {
    return `
      <div class="disclaimer disclaimer-strong" role="note">
        <i class="fa-solid fa-circle-exclamation" aria-hidden="true"></i>
        <p><strong>투자 조언이 아닙니다.</strong> ${escapeHtml(body)}${tail}</p>
      </div>`;
  }
  return `<p class="disclaimer disclaimer-default" role="note">${escapeHtml(body)}${tail}</p>`;
}
