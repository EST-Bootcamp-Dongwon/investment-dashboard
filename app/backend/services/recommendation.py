"""F03 포트폴리오 추천 — 도메인 계층.

docs/spec/60-운영/아키텍처.md 2.1절의 `services/` 계층이다.
판정 규칙과 프로필 상수만 들고 있으며, HTTP 도 DB 도 모른다.
`HTTPException` 을 던지지 않는다 — 도메인 예외를 올리고 라우터가 번역한다.

**상수의 출처는 `app/frontend/js/views/portfolioGuide.js:1~37` 이고 값을 바꾸지 않았다.**
자산명·비중·설명·문구가 프론트와 글자 단위로 같다. 이 이관이 F03 을 백엔드화하는
목적(저장·재현·검증) 자체이므로, 옮기면서 배분표까지 손대면 무엇이 달라졌는지
가려낼 수 없다.

**판정 규칙만은 바꾼다 — CN-029 결정.** 현행 프론트 규칙(`js:39~43,133`)은 27조합 중
19칸(70.4%)이 `stable` 이고 `growth` 는 3칸뿐이라, R-01 이 요구한 "안정/균형/성장 세
갈래" 가 사실상 한 갈래로 무너져 있다. 세 축을 점수화하고 안전 가드를 붙인 새 규칙은
docs/spec/20-기능명세/02-포트폴리오.md 1.4절에 전수표까지 확정돼 있다.
"""

from __future__ import annotations

from typing import Literal, TypedDict

Profile = Literal["stable", "balanced", "growth"]


class RecommendationDataError(Exception):
    """서버 상수가 손상됐다 (배분 합계가 100 이 아님). 라우터가 500 으로 번역한다."""


class AssetItem(TypedDict):
    sort_order: int
    asset_name: str
    weight_pct: int
    explanation: str


class ProfileConfig(TypedDict):
    label: str
    badge: str
    intro: str
    note: str
    items: list[AssetItem]


# ─── 프로필 상수 — portfolioGuide.js:1~37 의 값 그대로 ─────────────────────────
#
# 색상(#22c55e 등)은 옮기지 않는다. UI 테마의 관심사이고, 자산명 → 색상이 세 프로필에
# 걸쳐 모순 없는 함수라 프론트가 asset_name 으로 되찾을 수 있다 (테이블-정의서 4.3절).
# 반대로 explanation 은 같은 자산도 프로필마다 문구가 달라 반드시 여기 있어야 한다
# (현금성 자산 js:6 / js:20 / js:33 셋 다 다름).

PROFILES: dict[Profile, ProfileConfig] = {
    "stable": {
        "label": "안정 중심 구성",
        "badge": "안정형",
        "intro": "큰 흔들림을 줄이는 데 우선순위를 둔 예시입니다. 수익 기회도 중요하지만, 예상보다 큰 변동을 견디기 어렵다면 이런 출발점이 편할 수 있습니다.",
        "note": "주가가 빠르게 오를 때에는 성장형 구성보다 수익이 더디게 느껴질 수 있습니다.",
        "items": [
            {"sort_order": 0, "asset_name": "현금성 자산", "weight_pct": 35, "explanation": "급한 상황이나 기회를 위한 여유 자금"},
            {"sort_order": 1, "asset_name": "채권·안정형 자산", "weight_pct": 35, "explanation": "포트폴리오의 흔들림을 완화하는 역할"},
            {"sort_order": 2, "asset_name": "글로벌 주식", "weight_pct": 20, "explanation": "장기 성장 기회를 위한 부분"},
            {"sort_order": 3, "asset_name": "배당·방어형 주식", "weight_pct": 10, "explanation": "상대적으로 안정적인 현금흐름을 기대하는 부분"},
        ],
    },
    "balanced": {
        "label": "균형 중심 구성",
        "badge": "균형형",
        "intro": "성장 기회와 안정성을 함께 고려한 예시입니다. 한 가지 자산에 집중하기보다 서로 다른 역할을 가진 자산을 나누어 담는 데 초점을 둡니다.",
        "note": "시장 상황에 따라 주식과 안정형 자산이 모두 기대만큼 움직이지 않을 수 있습니다.",
        "items": [
            {"sort_order": 0, "asset_name": "글로벌 주식", "weight_pct": 45, "explanation": "여러 국가와 업종의 성장 기회"},
            {"sort_order": 1, "asset_name": "채권·안정형 자산", "weight_pct": 25, "explanation": "시장 변동을 완화하는 완충 역할"},
            {"sort_order": 2, "asset_name": "국내 주식", "weight_pct": 15, "explanation": "익숙한 시장의 성장 기회"},
            {"sort_order": 3, "asset_name": "현금성 자산", "weight_pct": 10, "explanation": "예상치 못한 지출과 추가 투자 여유"},
            {"sort_order": 4, "asset_name": "대체 자산", "weight_pct": 5, "explanation": "금 등 다른 성격의 자산을 소량 활용"},
        ],
    },
    "growth": {
        "label": "성장 중심 구성",
        "badge": "성장형",
        "intro": "장기 성장 가능성에 더 무게를 둔 예시입니다. 단기적인 등락을 감수할 수 있고, 투자 기간이 충분히 길 때 검토해 볼 수 있습니다.",
        "note": "짧은 기간에도 큰 손실이 발생할 수 있습니다. 생활에 필요한 돈은 별도로 두는 것이 좋습니다.",
        "items": [
            {"sort_order": 0, "asset_name": "글로벌 주식", "weight_pct": 60, "explanation": "폭넓은 성장 기회를 중심으로 구성"},
            {"sort_order": 1, "asset_name": "국내 주식", "weight_pct": 20, "explanation": "국내 시장과 관심 산업에 참여하는 부분"},
            {"sort_order": 2, "asset_name": "테마·성장 자산", "weight_pct": 10, "explanation": "높은 변동성을 감수하는 작은 비중"},
            {"sort_order": 3, "asset_name": "채권·안정형 자산", "weight_pct": 5, "explanation": "급격한 변동에 대비하는 완충 역할"},
            {"sort_order": 4, "asset_name": "현금성 자산", "weight_pct": 5, "explanation": "기본적인 유동성 확보"},
        ],
    },
}

# portfolioGuide.js:103 의 고정 문구. R-07(개인별 투자 조언이 아님)을 만족하는
# 3개 화면 중 하나이므로 서버 응답에도 함께 실어 보낸다.
DISCLAIMER = "이 내용은 금융 교육을 위한 일반적인 구성 예시이며, 개인별 투자 조언이나 수익을 보장하는 추천이 아닙니다."


# ─── 판정 규칙 — CN-029 점수제 ────────────────────────────────────────────────
#
# ① 세 축을 각각 0·1·2 점으로 환산해 더한다 (0~6점).
_GOAL_SCORE = {"protect": 0, "balance": 1, "growth": 2}
_HORIZON_SCORE = {"short": 0, "medium": 1, "long": 2}
_RISK_SCORE = {"low": 0, "medium": 1, "high": 2}

# ③ 안전 가드. 셋 중 하나라도 해당하면 growth 를 주지 않고 balanced 로 내린다.
#    점수만 쓰면 "원금 보호가 목적인데 기간이 길고 하락에 버틸 수 있는" 사람에게
#    성장형이 나가고, 그것은 R-07 과 정면으로 어긋난다.
_GUARD_GOAL = "protect"
_GUARD_HORIZON = "short"
_GUARD_RISK = "low"


def decide_profile(goal: str, horizon: str, risk: str) -> Profile:
    """설문 3문항으로 프로필을 판정한다.

    docs/spec/20-기능명세/02-포트폴리오.md 1.4절의 ①②③ 을 그대로 옮긴 것이고,
    같은 문서의 27조합 전수표가 이 함수의 기대 출력이다.
    `scripts/verify_recommendation_rule.py` 가 전수 대조한다.
    """
    score = _GOAL_SCORE[goal] + _HORIZON_SCORE[horizon] + _RISK_SCORE[risk]

    # ② 점수로 1차 판정
    if score <= 2:
        profile: Profile = "stable"
    elif score == 3:
        profile = "balanced"
    else:
        profile = "growth"

    # ③ 안전 가드
    if profile == "growth" and (
        goal == _GUARD_GOAL or horizon == _GUARD_HORIZON or risk == _GUARD_RISK
    ):
        profile = "balanced"

    return profile


def build_recommendation(goal: str, horizon: str, risk: str) -> dict:
    """판정하고 응답 본문을 만든다. 저장은 하지 않는다.

    `preview` 와 `create` 가 같은 함수를 쓰므로 둘의 결과가 갈라질 수 없다.
    """
    profile = decide_profile(goal, horizon, risk)
    config = PROFILES[profile]
    items = [dict(item) for item in config["items"]]
    total = sum(item["weight_pct"] for item in items)

    # 비중 합계 100 은 행 단위 CHECK 로 보장할 수 없어 이 계층에서 검증한다
    # (테이블-정의서 4.3절이 채택한 방법). 배분표가 서버 상수이므로 입력원은 하나뿐이고,
    # 여기서 걸린다면 사용자 입력이 아니라 상수가 손상된 것이다.
    if total != 100:
        raise RecommendationDataError(
            f"프로필 '{profile}' 의 비중 합계가 {total} 입니다 (100 이어야 합니다)."
        )

    return {
        "goal": goal,
        "horizon": horizon,
        "risk": risk,
        "profile": profile,
        "profile_label": config["label"],
        "badge": config["badge"],
        "intro": config["intro"],
        "note": config["note"],
        "items": items,
        "total_weight_pct": total,
        "disclaimer": DISCLAIMER,
    }


def profile_display(profile: str) -> dict:
    """저장돼 있지 않은 표시 문구를 현재 상수에서 되찾는다.

    `recommendation` 이 저장하는 표시 문구는 `profile_label` 하나뿐이라,
    `detail` 로 과거 추천을 재현할 때 badge·intro·note 는 저장값이 아니라
    **지금의 서버 상수**에서 나온다. 즉 한 화면 안에 시점이 다른 두 종류의 문구가
    섞인다 — `items[].explanation` 은 스냅샷이고 이 셋은 현재값이다.
    확정 스키마 안에서는 이것이 유일한 방법이다 (API-상세명세 2.8절 · CN-031).
    """
    config = PROFILES.get(profile)  # type: ignore[arg-type]
    if config is None:
        return {"badge": "", "intro": "", "note": ""}
    return {"badge": config["badge"], "intro": config["intro"], "note": config["note"]}
