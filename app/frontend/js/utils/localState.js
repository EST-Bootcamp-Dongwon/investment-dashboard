const PREFIX = 'investment-analysis:';

function keyFor(view, suffix) {
  return `${PREFIX}${suffix}:${view}`;
}

function safely(fn, fallback = null) {
  try {
    return fn();
  } catch (error) {
    // 저장 공간이 부족하거나 브라우저 정책으로 막힌 경우에도 화면 기능은 유지한다.
    console.warn('로컬 저장소 처리 실패:', error);
    return fallback;
  }
}

function controlKey(control) {
  return control.id || control.name || null;
}

function storableControls(root) {
  return [...root.querySelectorAll('input, select, textarea')].filter((control) => {
    const type = (control.type || '').toLowerCase();
    return controlKey(control)
      && !control.disabled
      && !control.closest('[data-local-state="off"]')
      && !['button', 'submit', 'reset', 'file', 'hidden', 'password'].includes(type);
  });
}

export function saveFormState(view, root = document) {
  if (!view) return;
  const values = {};
  for (const control of storableControls(root)) {
    const key = controlKey(control);
    const type = (control.type || '').toLowerCase();
    if (type === 'radio') {
      if (control.checked) values[key] = { type, value: control.value };
    } else if (type === 'checkbox') {
      values[key] = { type, checked: control.checked };
    } else {
      values[key] = { type, value: control.value };
    }
  }
  safely(() => localStorage.setItem(keyFor(view, 'form'), JSON.stringify(values)));
}

export function restoreFormState(view, root = document) {
  if (!view) return;
  const values = safely(() => JSON.parse(localStorage.getItem(keyFor(view, 'form')) || '{}'), {});
  for (const control of storableControls(root)) {
    const saved = values[controlKey(control)];
    if (!saved) continue;
    const type = (control.type || '').toLowerCase();
    if (type === 'radio') {
      control.checked = saved.value === control.value;
    } else if (type === 'checkbox') {
      control.checked = Boolean(saved.checked);
    } else {
      control.value = saved.value ?? control.value;
    }
  }
}

const VISITOR_ID_KEY = 'investment_analysis_visitor_id';

// 서버가 요구하는 형식: 16~64자, [A-Za-z0-9_-] 만.
// recommendation.anon_id 의 DB 상한이 64자라 heartbeat(80자)보다 좁은 쪽에 맞춘다.
const VISITOR_ID_MIN = 16;
const VISITOR_ID_MAX = 64;

function createVisitorId() {
  if (globalThis.crypto?.randomUUID) return globalThis.crypto.randomUUID().replaceAll('-', '');
  // 폴백. Math.random().toString(36).slice(2) 는 길이가 들쭉날쭉하고 이론상 빈 문자열도
  // 나오므로, 16자에 못 미치면 채워서 서버 검증(min_length=16)에 걸리지 않게 한다.
  let id = `${Date.now().toString(36)}${Math.random().toString(36).slice(2)}${Math.random().toString(36).slice(2)}`;
  while (id.length < VISITOR_ID_MIN) id += Math.random().toString(36).slice(2) || '0';
  return id.slice(0, VISITOR_ID_MAX);
}

/**
 * 비로그인 브라우저 식별자. 방문자 수 집계(F01)와 추천 이력 소유자(F03)가 같은 값을 쓴다.
 * 두 기능이 각자 만들면 같은 브라우저가 서로 다른 신원으로 갈라진다.
 */
export function visitorId() {
  try {
    const saved = localStorage.getItem(VISITOR_ID_KEY);
    if (saved) return saved;
    const id = createVisitorId();
    localStorage.setItem(VISITOR_ID_KEY, id);
    return id;
  } catch {
    // 저장소가 막힌 브라우저에서도 화면은 동작해야 한다. 이력은 남지 않는다.
    return createVisitorId();
  }
}

export function saveViewPayload(view, payload) {
  safely(() => localStorage.setItem(keyFor(view, 'payload'), JSON.stringify(payload)));
}

export function loadViewPayload(view) {
  return safely(() => JSON.parse(localStorage.getItem(keyFor(view, 'payload')) || 'null'));
}
