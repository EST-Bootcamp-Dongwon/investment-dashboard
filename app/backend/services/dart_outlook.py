"""F23 재무 상태 표기 — CN-046 적용본.

## 무엇을 바꿨는가

`main.py:2552~2576` 은 종합점수로 **투자의견**을 냈다.

    if score >= 75:   outlook = "매수(Buy)";       outlook_eng = "BUY"
    elif score >= 55: outlook = "중립(Hold)";      outlook_eng = "HOLD"
    else:             outlook = "관망(Sell/Wait)"; outlook_eng = "SELL"

강사님 요구 R-07 이 "확정적 표현 금지 · 개인별 투자 조언이 아님을 유지" 인데,
"매수/관망" 은 재무 요약이 아니라 **행동 지시**다. 게다가 근거가 재무비율 6개뿐이라
**주가·밸류에이션·산업 국면이 하나도 없다** — 재무가 좋아도 주가가 이미 반영했으면
매수가 아니므로 방법론적으로도 성립하지 않는다. 같은 프로젝트의 F19(밸류에이션)가
바로 그 이야기를 한다.

그래서 **의견이 아니라 상태로** 바꾼다. 문구와 배지 색은
`docs/spec/50-UI/화면-상세.md` 4.2절 표가 정본이고, 이 파일이 그대로 옮겨 왔다.

## 왜 `services/` 로 꺼냈는가

바뀐 것이 **판정 규칙**이라 판정을 직접 넣고 확인할 수 있어야 한다. 그런데
`main.py` 는 import 하면 라우터가 딸려 와 무겁다 (`services/combination.py` 가 같은
이유로 AST 대조를 쓴다). 판정만 순수 함수로 꺼내면 `scripts/verify_dart_outlook.py`
가 **가짜 breakdown 을 꽂아 결정적으로** 검사할 수 있다.

꺼낸 것은 **판정뿐이다.** `analysis.paragraphs` 의 재무 서술(부채비율·수익성·성장률
문단, `main.py:2462~2550`)은 건드리지 않았다 — CN-046 이 "사실 서술이라 R-07 위반이
아니다" 라고 명시했다.

## 결측을 점수가 아니라 경고로

`_score_financial_health` 는 값이 없으면 **만점의 50%** 를 준다
(`main.py:2380~2381`). 재무제표 파싱이 실패한 회사가 그 규칙 때문에 "보통" 으로
보인다. 화면-상세.md 4.2절이 정한 대로 **결측 2개 이상이면 등급 대신 `판정 보류`** 를
낸다.

**50% 규칙 자체는 그대로 뒀다.** 그것을 바꾸면 결측이 없는 회사의 점수까지 전부
움직이는데, 그건 R-07 이 요구한 범위가 아니다. 미결 항목으로 남긴다.
"""

from __future__ import annotations

try:
    from .rag import DISCLAIMER
except ImportError:  # `uvicorn main:app` 을 app/backend 에서 띄우는 경로 (CN-102)
    from rag import DISCLAIMER  # type: ignore

# ── 면책 (R-07 · CN-060) ─────────────────────────────────────────────────────
#
# `DISCLAIMER` 는 새로 짓지 않고 `services/rag.py` 것을 **그대로 가져다 쓴다.** 파이썬
# 쪽 사본을 둘로 늘리면 갈라진다. F27 이 먼저 그 자리에 뒀을 뿐, 문장은 화면 공통이다
# (`50-UI/화면-상세.md` 3.2절 strong).
#
# `DISCLAIMER_CONTEXT` 는 같은 절 3.2절 표의 **F23 행**이고, 프런트에도 같은 문장이
# `components/disclaimer.js` 의 `DISCLAIMER_CONTEXT.F23` 으로 있다. 두 사본이 갈라지는지는
# `scripts/verify_dart_outlook.py` 가 `==` 로 대조한다 — F27 이 세운 방식 그대로다.
DISCLAIMER_CONTEXT = (
    "재무비율만 본 결과이며 주가·밸류에이션은 반영하지 않았습니다."
)

# 화면-상세.md 4.2절 표. 색 이름은 프런트의 토큰 계열(ok · muted · warn)과 맞췄다 —
# 기존 green/yellow/red 는 신호등이라 그 자체가 매매 지시로 읽힌다.
STATUS_GOOD = "재무 양호"
STATUS_FAIR = "보통"
STATUS_WEAK = "재무 취약 — 확인 필요 항목 있음"
STATUS_WITHHELD = "판정 보류 — 재무 자료 부족"

# 원문 임계값을 바꾸지 않았다 (`main.py:2553` · `:2561`).
SCORE_GOOD = 75.0
SCORE_FAIR = 55.0

# 결측 몇 개부터 판정을 보류하는가. 화면-상세.md 4.2절 "2개 이상이면".
MISSING_LIMIT = 2

# 달성률이 이 이상이면 "점수를 끌어올린 항목", 이하면 "끌어내린 항목" 으로 센다.
# breakdown 의 score/max 비율이라 항목별 배점(20 · 15)이 달라도 비교가 된다.
LIFT_RATIO = 0.8
DRAG_RATIO = 0.4

# 이유 문장에 이름을 몇 개까지 넣는가. 6개를 다 늘어놓으면 읽히지 않는다.
NAME_LIMIT = 3


def _ratio(item: dict) -> float:
    """달성률. `max` 가 0 이면 비교할 수 없으므로 0 으로 본다."""
    top = item.get("max") or 0
    return (item.get("score", 0) / top) if top else 0.0


def _names(items: list[tuple[str, float]]) -> list[str]:
    """달성률 순으로 정렬한 뒤 이름만 `NAME_LIMIT` 개까지."""
    return [label for label, _ in items[:NAME_LIMIT]]


def assess(score: float, grade: str, breakdown: dict) -> dict:
    """재무 상태 표기를 만든다.

    `breakdown` 은 `_score_financial_health` 가 준 그대로다 —
    `{항목명: {"score": float, "max": float, "value": float | None}}`.
    `value is None` 이 파싱 실패를 뜻한다.

    반환에 `outlook_eng` 가 없다. `BUY`/`SELL` 은 매매 지시 그 자체라
    화면-상세.md 4.2절 1번이 제거를 지시했다.
    """
    scored = sorted(
        ((label, _ratio(item)) for label, item in breakdown.items()),
        key=lambda pair: pair[1],
        reverse=True,
    )
    missing = [label for label, item in breakdown.items() if item.get("value") is None]

    # ── 결측이 많으면 등급을 내지 않는다 ──────────────────────────────────────
    # 점수는 그대로 돌려준다. 화면이 점수 게이지를 이미 그리고 있고, 숨기면
    # "왜 안 보이는가" 를 설명할 방법이 없다. 대신 무엇이 비었는지를 말한다.
    if len(missing) >= MISSING_LIMIT:
        return {
            "outlook": STATUS_WITHHELD,
            "outlook_color": "muted",
            "outlook_reason": (
                f"재무 건전성 종합점수 {score:.0f}점(등급: {grade}). "
                f"다만 평가 항목 {len(breakdown)}개 중 {len(missing)}개가 공시에서 "
                f"확인되지 않았습니다 — {' · '.join(missing)}. "
                "결측 항목은 만점의 절반으로 계산되므로 점수가 실제보다 높게 보일 수 "
                "있어 등급 표기를 보류합니다."
            ),
            "missing": missing,
            "withheld": True,
        }

    lifted = _names([pair for pair in scored if pair[1] >= LIFT_RATIO])
    dragged = _names([pair for pair in reversed(scored) if pair[1] <= DRAG_RATIO])

    if score >= SCORE_GOOD:
        outlook, color = STATUS_GOOD, "ok"
    elif score >= SCORE_FAIR:
        outlook, color = STATUS_FAIR, "muted"
    else:
        outlook, color = STATUS_WEAK, "warn"

    # 이유는 "중장기 투자 매력이 높습니다" 같은 전망이 아니라 **어느 항목이 점수를
    # 움직였는가** 다. breakdown 에 항목별 점수가 이미 있어 추가 계산이 없다.
    parts = [f"재무 건전성 종합점수 {score:.0f}점(등급: {grade})."]
    if lifted:
        parts.append(f"점수를 끌어올린 항목은 {' · '.join(lifted)} 입니다.")
    if dragged:
        parts.append(f"끌어내린 항목은 {' · '.join(dragged)} 입니다.")
    if missing:
        parts.append(f"{' · '.join(missing)} 은(는) 공시에서 확인되지 않았습니다.")

    return {
        "outlook": outlook,
        "outlook_color": color,
        "outlook_reason": " ".join(parts),
        "missing": missing,
        "withheld": False,
    }
