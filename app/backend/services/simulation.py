"""F05 포트폴리오 시뮬레이션 — 도메인 계층.

docs/spec/60-운영/아키텍처.md 2.1절의 `services/` 계층이다.
몬테카를로 계산과 프로필 가정만 들고 있으며, HTTP 도 DB 도 모른다.
`HTTPException` 을 던지지 않는다 — 도메인 예외를 올리고 라우터가 번역한다.

**상수와 계산 절차의 출처는 `app/backend/routers/quant.py:59~105` 이고 값을 바꾸지
않았다.** 기대수익·변동성·시드·경로 수·백분위·설명 문구가 전부 같다. F03 이
`portfolioGuide.js` 를 옮길 때와 같은 원칙이다 — 옮기면서 계산까지 손대면 저장된 값이
기존 화면과 왜 다른지 가려낼 수 없다.

**`quant.py` 의 엔드포인트는 그대로 둔다.** 이 모듈은 그것을 대체하지 않고 저장 경로를
새로 낸다. `scripts/verify_simulation_api.py` 가 두 경로의 출력을 대조해 값이 갈라지지
않았음을 확인한다.

**딕셔너리 키 하나만 이름이 다르다.** `quant.py:68` 의 `"return"` 을 `annual_return`
으로 바꿨다. `return` 은 파이썬 예약어라 `TypedDict` 의 클래스 문법으로 선언할 수 없다.
값(0.045 · 0.065 · 0.085)은 그대로다.
"""

from __future__ import annotations

from typing import Literal, TypedDict

Profile = Literal["stable", "balanced", "growth"]


class SimulationDataError(Exception):
    """계산 결과가 도메인 불변식을 깼다. 라우터가 500 으로 번역한다."""


class ProfileConfig(TypedDict):
    label: str
    annual_return: float
    volatility: float


class Point(TypedDict):
    year: int
    cautious: int
    middle: int
    positive: int


# ─── 프로필 가정 — quant.py:66~70 의 값 그대로 ────────────────────────────────
#
# 예시용 가정이지 전망이나 기대수익 약속이 아니다 (quant.py:65 의 주석과 같은 취지).
PROFILES: dict[Profile, ProfileConfig] = {
    "stable":   {"label": "안정 중심", "annual_return": 0.045, "volatility": 0.07},
    "balanced": {"label": "균형 중심", "annual_return": 0.065, "volatility": 0.12},
    "growth":   {"label": "성장 중심", "annual_return": 0.085, "volatility": 0.18},
}

# ─── 재현의 전제 — quant.py:72~73 ─────────────────────────────────────────────
#
# 이 둘이 바뀌면 같은 입력이 다른 결과를 낸다. 그래서 simulation_run 이 결과와 함께
# 컬럼으로 저장하고(테이블-정의서 4.5절), 응답에도 실어 보낸다 — 저장된 값과 지금
# 값을 밖에서 대조할 수 있어야 "재현된다" 는 주장이 검사 가능해진다.
RNG_SEED = 20260806
PATHS = 5_000

# 보수·중간·긍정의 정의. quant.py:83 의 [10, 50, 90] 이다.
PERCENTILES = (10, 50, 90)

# quant.py:105 의 고정 문구. R-07(개인별 투자 조언이 아님)을 만족시키는 문장이라
# 서버 응답에 함께 실어 보낸다.
EXPLANATION = "같은 구성이라도 시장 흐름에 따라 결과가 달라질 수 있음을 보여주는 학습용 가상 시나리오입니다."


def _validate(points: list[Point], years: int) -> None:
    """DB 제약과 같은 불변식을 저장 전에 확인한다.

    `ck_simulation_point_year`·`ck_simulation_run_percentile` 이 DB 에 이미 있는데도
    여기서 한 번 더 보는 이유는 **오류가 도착하는 방식** 때문이다. DB 에서 걸리면
    `SupabaseError` 가 되고 라우터는 그것을 503("잠시 후 다시 시도해 주세요")으로
    번역한다. 계산이 틀린 것을 사용자가 장애로 읽게 되고, 다시 시도해도 같은 값이 나온다.
    계산 계층에서 걸러야 500(서버 결함)으로 정직하게 나간다.

    백분위는 정의상 단조증가라 지금 코드로는 깨지지 않는다. 이 검사는 나중에
    `PERCENTILES` 순서나 계산 절차가 바뀔 때를 위한 것이다.
    """
    if len(points) != years + 1:
        raise SimulationDataError(
            f"{years}년 시뮬레이션의 곡선이 {len(points)}개입니다 ({years + 1}개여야 합니다)."
        )
    for point in points:
        if not (point["cautious"] <= point["middle"] <= point["positive"]):
            raise SimulationDataError(
                f"{point['year']}년 백분위 순서가 어긋났습니다: "
                f"{point['cautious']} / {point['middle']} / {point['positive']}"
            )


def build_simulation(
    profile: Profile,
    initial_amount: int,
    monthly_amount: int,
    years: int,
) -> dict:
    """몬테카를로 5,000경로를 돌려 연 단위 곡선과 요약을 만든다. 저장은 하지 않는다.

    `preview` 와 `create` 가 같은 함수를 쓰므로 둘의 결과가 갈라질 수 없다.

    numpy 를 함수 안에서 import 하는 것은 `quant.py:61` 과 같은 관례다. 모듈 최상단에
    두면 라우터를 import 하는 것만으로 numpy 가 딸려 와 콜드 스타트가 그만큼 늘어난다.
    """
    import numpy as np

    config = PROFILES[profile]
    rng = np.random.default_rng(RNG_SEED)
    balances = np.full(PATHS, float(initial_amount))

    # 연 기대수익을 월 복리로 환산한다. 연 변동성은 √12 로 나눠 월 변동성으로 본다
    # (quant.py:75~76).
    monthly_return = (1 + config["annual_return"]) ** (1 / 12) - 1
    monthly_volatility = config["volatility"] / np.sqrt(12)

    # 0년 = 시작 시점. 아직 아무 등락도 겪지 않아 세 값이 모두 원금이다 (quant.py:77).
    points: list[Point] = [{
        "year": 0,
        "cautious": int(initial_amount),
        "middle": int(initial_amount),
        "positive": int(initial_amount),
    }]

    for month in range(1, years * 12 + 1):
        changes = rng.normal(monthly_return, monthly_volatility, PATHS)
        # 당월 납입액을 먼저 더하고 등락을 적용한다 — 당월 납입액도 그 달의 등락을
        # 함께 겪는다 (quant.py:81 · API-상세명세 1.2절 "월 적립 순서").
        # 0 으로 자르는 것은 잔고가 음수가 되지 않게 하기 위해서다.
        balances = np.maximum(0, (balances + monthly_amount) * (1 + changes))
        if month % 12 == 0:
            cautious, middle, positive = np.percentile(balances, list(PERCENTILES))
            points.append({
                "year": month // 12,
                "cautious": int(round(cautious)),
                "middle": int(round(middle)),
                "positive": int(round(positive)),
            })

    _validate(points, years)

    # 원금 합계다. 수익률이 반영되지 않은 값이다 (quant.py:91).
    total_paid = initial_amount + monthly_amount * years * 12
    final = points[-1]

    return {
        "profile": profile,
        "profile_label": config["label"],
        "initial_amount": initial_amount,
        "monthly_amount": monthly_amount,
        "years": years,
        "total_paid": int(total_paid),
        "points": points,
        "summary": {
            "cautious": final["cautious"],
            "middle": final["middle"],
            "positive": final["positive"],
        },
        "rng_seed": RNG_SEED,
        "paths": PATHS,
        "explanation": EXPLANATION,
    }
