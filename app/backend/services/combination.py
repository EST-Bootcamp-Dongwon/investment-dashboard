"""F04 포트폴리오 조합 판정 — 도메인 계층.

docs/spec/60-운영/아키텍처.md 2.1절의 `services/` 계층이다.
판정 규칙과 상수만 들고 있으며, HTTP 도 DB 도 yfinance 도 모른다.
`HTTPException` 을 던지지 않는다 — 도메인 예외를 올리고 라우터가 번역한다.

**상수와 계산 절차의 출처는 `app/backend/main.py:1173~1249` 이고 값을 바꾸지 않았다.**
임계값(0.30 · 0.70) · 신호 3종 · 문장 6개 · 기간 라벨 4개 · 하한 2개(21 · 20) ·
정규화 기준선(100) · 반올림 자리(4)가 전부 같다.

**F03 · F05 와 다른 점이 하나 있다 — 원본이 `main.py` 안에 있다.** F03 은 프런트
JS 에서, F05 는 `routers/quant.py` 에서 옮겨 왔다. F04 는 2,694줄짜리 단일 파일에서
꺼내는 **첫 사례**다(아키텍처 1.2절이 말하는 그 파일이다).

**`main.py` 의 엔드포인트는 그대로 둔다.** 화면(`api.js:57`)이 지금 그것을 부르고
있고, 저장 기능을 붙이면서 동작하던 화면이 나빠질 이유가 없다.

## 값 대조를 어떻게 하는가 — F05 와 갈라지는 지점

F05 는 시드가 고정 상수라 두 경로의 **출력을 직접 비교**할 수 있었다. F04 는 그것이
불가능하다. yfinance 가 매일 다른 시세를 주고, `auto_adjust=True` 라 배당·분할이
생기면 **과거 구간의 값까지 소급해서 바뀐다.**

그래서 비결정성이 있는 곳을 잘라냈다. 이 모듈은 **시세를 받지 않고 시계열을 받는다.**
외부 호출은 `clients/yahoo_prices.py` 가 하고, 그 경계 덕분에

- 판정 규칙은 **고정 시계열**을 넣어 결정적으로 검사할 수 있고,
- 원격 왕복 검증도 **가짜 시세를 꽂아** 결정적으로 돌릴 수 있다.

`scripts/verify_combination_api.py` 가 그 둘을 한다. 거기에 더해 이 모듈의 상수를
`main.py` 원문에서 **AST 로 뽑아 대조**한다 — import 하면 `torch` 가 딸려 오므로
소스만 읽는다. "값을 바꾸지 않았다" 는 주장이 그 지점에서 검사 가능해진다.
"""

from __future__ import annotations

from typing import Literal, TypedDict

try:
    from ..clients import yahoo_prices
except ImportError:  # `uvicorn main:app` 를 app/backend 에서 실행하는 경우
    from clients import yahoo_prices  # type: ignore

Period = Literal["3mo", "6mo", "1y", "2y"]
Signal = Literal["green", "yellow", "red"]


class CombinationInputError(Exception):
    """사용자가 고칠 수 있는 문제. 라우터가 422 로 번역한다.

    `main.py` 의 조합 엔드포인트는 종목 형식 · 같은 종목 · 데이터 부족 · 겹치는
    거래일 부족을 **전부 422** 로 낸다(`main.py:1182,1188,1206,1212`). 그 하나를
    유지하려고 예외도 하나만 둔다. 문구는 호출자가 그대로 쓴다.
    """


class CombinationDataError(Exception):
    """계산 결과가 도메인 불변식을 깼다. 라우터가 500 으로 번역한다.

    `services/simulation.py:SimulationDataError` 와 같은 자리·같은 이유다 —
    사용자가 고칠 수 없고 다시 시도해도 같은 값이 나오므로 503 이면 안 된다.
    """


class Verdict(TypedDict):
    signal: Signal
    summary: str
    portfolio_hint: str


class ChartPoint(TypedDict):
    date: str
    a: float
    b: float


# ─── 판정 임계값 — main.py:1215 · 1219 의 값 그대로 ───────────────────────────
#
# 경계는 **미만**이다. 0.30 은 green 이 아니라 yellow 이고, 0.70 은 yellow 가 아니라
# red 다. `<` 를 `<=` 로 바꾸면 경계값 두 개의 판정이 뒤집히므로 그대로 옮겼다.
GREEN_BELOW = 0.30
YELLOW_BELOW = 0.70

# ─── 판정 문장 — main.py:1216~1226 ────────────────────────────────────────────
#
# 신호별로 문장 두 개가 짝을 이룬다. `main.py` 는 if/elif/else 세 갈래에 여섯 줄로
# 흩어 두었는데, 여기서는 표로 모은다. 문자열은 한 글자도 바꾸지 않았다.
VERDICTS: dict[Signal, Verdict] = {
    "green": {
        "signal": "green",
        "summary": "최근 흐름이 비교적 다르게 나타났습니다. 함께 담을 때 한 종목에만 의존하는 정도를 낮추는 데 도움이 될 수 있습니다.",
        "portfolio_hint": "두 종목의 움직임이 겹치는 정도가 낮은 편입니다. 업종과 보유 비중도 함께 확인해 보세요.",
    },
    "yellow": {
        "signal": "yellow",
        "summary": "최근에는 일부 구간에서 함께 움직였습니다. 분산 효과는 기대할 수 있지만 크기는 제한적일 수 있습니다.",
        "portfolio_hint": "조합의 균형은 보통 수준입니다. 다른 업종이나 자산을 더하면 포트폴리오 폭을 넓힐 수 있습니다.",
    },
    "red": {
        "signal": "red",
        "summary": "최근 가격 흐름이 자주 같은 방향으로 움직였습니다. 두 종목을 함께 담아도 분산 효과가 작을 수 있습니다.",
        "portfolio_hint": "한 종목의 영향이 다른 종목에도 이어질 수 있습니다. 업종이 다른 종목이나 다른 자산을 함께 검토해 보세요.",
    },
}

# ─── 기간 라벨 — main.py:1228 ─────────────────────────────────────────────────
#
# 키 4개가 `combination_period` enum 과 같아야 한다(`init_types.sql:28`).
# 어긋나면 pydantic 을 통과한 값이 DB 에서 터져 503 이 된다.
PERIOD_LABELS: dict[Period, str] = {
    "3mo": "최근 3개월",
    "6mo": "최근 6개월",
    "1y": "최근 1년",
    "2y": "최근 2년",
}

# ─── 데이터 하한 — main.py:1197 · 1211 ────────────────────────────────────────
#
# 둘이 다른 수인 것은 세는 대상이 다르기 때문이다.
#   MIN_HISTORY : 종목 **하나**의 종가 행 수. 정렬 전에 각각 본다.
#   MIN_OVERLAP : 두 종목이 **겹치는** 날의 일간 변화 수. 정렬 후에 본다.
# 21 과 20 의 차이는 `pct_change` 가 첫 행을 지우기 때문이다 — 종가 21행이 변화
# 20개가 된다. 즉 두 하한은 같은 것을 양쪽에서 말하고 있다.
MIN_HISTORY = 21
MIN_OVERLAP = 20

# 상관계수를 저장할 때의 자리수. `numeric(6,5)`(마이그레이션 20260811130000)와 맞춘다.
# 여기서 미리 반올림해 두는 이유는 **저장한 값과 계산한 값이 갈라지지 않게** 하기
# 위해서다. DB 에 맡기면 응답의 상관계수와 컬럼의 상관계수가 6번째 자리에서 다르다.
RELATIONSHIP_DIGITS = 5

# 차트 정규화 기준선과 반올림 자리 — main.py:1231 · 1235~1236.
CHART_BASE = 100
CHART_DIGITS = 4

# 종목 코드 허용 문자 — main.py:1181 의 정규식 그대로.
TICKER_PATTERN = r"[A-Z0-9.^=\-]{1,20}"

TICKER_INVALID = "올바른 종목 코드를 입력해 주세요."
TICKER_SAME = "서로 다른 두 종목을 선택해 주세요."
OVERLAP_SHORT = "두 종목의 함께 비교할 수 있는 거래일이 부족합니다."


def clean_ticker(raw: str) -> str:
    """공백을 지우고 대문자로 올린 뒤 형식을 본다. `main.py:1179~1183` 그대로다.

    검증을 pydantic 이 아니라 여기서 하는 이유는 **정규화가 먼저** 이기 때문이다.
    `" aapl "` 는 형식이 틀린 값이 아니라 `"AAPL"` 이고, pydantic 의 `pattern` 은
    정규화 전 문자열에 걸리므로 멀쩡한 입력을 422 로 만든다.
    """
    import re

    ticker = raw.strip().upper()
    if not re.fullmatch(TICKER_PATTERN, ticker):
        raise CombinationInputError(TICKER_INVALID)
    return ticker


def classify(relationship: float) -> Verdict:
    """상관계수 하나를 신호등 판정으로 바꾼다. `main.py:1215~1226` 의 분기다.

    **`main.py` 와 한 곳에서 다르게 군다 — NaN 이다.** 두 종목 중 하나의 종가가
    구간 내내 변하지 않으면 상관계수가 NaN 이 되고, `main.py` 에서는
    `nan < 0.30` 도 `nan < 0.70` 도 False 라 **else 로 떨어져 `'red'` 가 나간다.**
    "함께 움직였다" 는 판정을 계산 실패에 붙이는 셈이다.

    여기서는 막는다. 이유가 둘이다.
      ① 저장이 목적인 경로다. NaN 은 `ck_combination_query_relationship`
         (`between -1 and 1`)에 걸려 **503("잠시 후 다시 시도")** 이 되는데,
         다시 시도해도 같은 값이 나온다.
      ② `'red'` 는 *다른* 답이 아니라 *틀린* 답이다. 옮기면서 계산을 손대지 않는다는
         원칙은 옳은 값을 지키기 위한 것이지 틀린 값을 보존하려는 것이 아니다.

    `main.py` 의 현행 동작은 `scripts/verify_combination_api.py` 가 원문에서 뽑은
    임계값으로 재현해 **실측으로 남긴다** — 추정이 아니라 측정으로 적기 위해서다.
    """
    if relationship != relationship:  # NaN 은 자기 자신과도 같지 않다
        raise CombinationDataError(
            "상관계수가 계산되지 않았습니다(NaN). 두 종목 중 한쪽의 가격이 "
            "구간 내내 변하지 않았을 수 있습니다."
        )
    if not (-1 <= relationship <= 1):
        raise CombinationDataError(f"상관계수가 정의역을 벗어났습니다: {relationship}")

    if relationship < GREEN_BELOW:
        return VERDICTS["green"]
    if relationship < YELLOW_BELOW:
        return VERDICTS["yellow"]
    return VERDICTS["red"]


def build_combination(
    ticker_a: str,
    ticker_b: str,
    period: Period,
    closes: dict[str, object],
    unavailable: list[str],
) -> dict:
    """정렬 → 일간 변화 → 상관계수 → 판정까지. 저장도 외부 호출도 하지 않는다.

    `closes` 는 `clients/yahoo_prices.download_closes` 가 돌려준 `{티커: 종가 시리즈}`
    이고, `unavailable` 은 아예 받지 못한 티커들이다. **몇 행부터 충분한가** 는
    도메인 규칙이라 클라이언트가 아니라 여기서 판단한다(`MIN_HISTORY`).

    pandas 를 함수 안에서 import 하는 것은 `main.py:1176` 과 같은 관례다. 모듈
    최상단에 두면 라우터를 import 하는 것만으로 pandas 가 딸려 온다.
    """
    import pandas as pd

    # `main.py:1192~1202` 는 "못 받음" 과 "너무 짧음" 을 같은 목록에 담는다.
    # 두 판단은 계층이 다르지만(전자는 연동, 후자는 도메인) **사용자에게 나가는
    # 문장은 하나** 여야 하므로 여기서 다시 합친다. 순서도 (a, b) 그대로 유지한다 —
    # 목록 순서가 뒤집히면 같은 상황에서 다른 문장이 나간다.
    missing = [
        ticker
        for ticker in (ticker_a, ticker_b)
        if ticker in unavailable or len(closes.get(ticker, ())) < MIN_HISTORY
    ]
    if missing:
        raise CombinationInputError(
            f"{', '.join(missing)}의 충분한 가격 데이터를 찾지 못했습니다."
        )

    # 거래일이 겹치는 구간만 남긴다(`main.py:1209`). 미국장과 한국장처럼 휴일이
    # 다른 조합에서 이 inner join 이 실제로 행을 지운다.
    aligned = pd.concat(
        {ticker_a: closes[ticker_a], ticker_b: closes[ticker_b]}, axis=1, join="inner"
    ).dropna()
    # `fill_method=None` 을 명시한다. pandas 의 기본 채움을 쓰면 결측 다음 날의
    # 변화율이 0 으로 위조된다(`main.py:1210`).
    daily_moves = aligned.pct_change(fill_method=None).dropna()

    if len(daily_moves) < MIN_OVERLAP:
        raise CombinationInputError(OVERLAP_SHORT)

    relationship = round(float(daily_moves.corr().iloc[0, 1]), RELATIONSHIP_DIGITS)
    verdict = classify(relationship)

    # 창의 양 끝은 **일간 변화**의 index 에서 읽는다. `aligned` 가 아니다 —
    # 상관계수에 들어간 것은 변화이지 종가가 아니고, `pct_change` 가 첫 행을 지우므로
    # 두 index 의 시작이 하루 다르다. 되짚을 때 필요한 것은 변화 쪽 창이다.
    observed_from = pd.Timestamp(daily_moves.index[0]).isoformat()
    latest_data_at = pd.Timestamp(daily_moves.index[-1]).isoformat()

    # 두 종목의 가격 단위가 달라도 흐름을 한 차트에서 비교할 수 있도록 출발선을
    # 맞춘다(`main.py:1230~1231`). 기준은 `aligned` 의 첫 행이라 차트 점은 관측 수보다
    # 하나 많다 — 종가 N행이 변화 N-1개를 낳기 때문이고, 어긋난 것이 아니다.
    chart_base = aligned / aligned.iloc[0] * CHART_BASE
    chart_points: list[ChartPoint] = [
        {
            "date": pd.Timestamp(index).date().isoformat(),
            "a": round(float(row[ticker_a]), CHART_DIGITS),
            "b": round(float(row[ticker_b]), CHART_DIGITS),
        }
        for index, row in chart_base.iterrows()
    ]

    return {
        "ticker_a": ticker_a,
        "ticker_b": ticker_b,
        "period": period,
        "period_label": PERIOD_LABELS[period],
        "signal": verdict["signal"],
        "summary": verdict["summary"],
        "portfolio_hint": verdict["portfolio_hint"],
        "latest_data_at": latest_data_at,
        "chart_points": chart_points,
        # 아래 셋은 응답에 나가지 않고 저장에만 쓴다(마이그레이션 20260811130000).
        # 라우터가 응답을 조립할 때 걸러낸다.
        "relationship": relationship,
        "observed_from": observed_from,
        "observation_count": len(daily_moves),
    }


def analyze(ticker_a: str, ticker_b: str, period: Period) -> dict:
    """정규화 → 시세 조회 → 판정. **라우터가 부르는 유일한 입구다.**

    시세 조회를 라우터가 아니라 여기서 부르는 이유는 아키텍처 1.3절이 세고 있는
    바로 그 항목 때문이다 — *"라우트 핸들러가 외부 API 를 직접 호출: 22개 중 12개
    → 목표 0개"*. `main.py:1194` 가 그 12개 중 하나이고, 이 함수가 그 한 건을 덜어낸다.

    `yahoo_prices.download_closes` 를 **속성 접근으로** 부른다
    (`from ... import download_closes` 가 아니다). 검증에서 모듈 속성 하나만
    갈아끼우면 이 경로 전체가 결정적이 되기 때문이다 — 그 자리가 없으면 원격 왕복
    검증이 매번 다른 시세 위에서 돌아 재실행할 때마다 기대값이 달라진다.
    """
    a = clean_ticker(ticker_a)
    b = clean_ticker(ticker_b)
    # 같은 종목끼리는 상관계수가 1 이라 판정이 항상 red 다. 계산은 되지만 물어볼
    # 값이 아니므로 막는다 (`main.py:1187~1188`).
    if a == b:
        raise CombinationInputError(TICKER_SAME)

    closes, unavailable = yahoo_prices.download_closes((a, b), period)
    return build_combination(a, b, period, closes, unavailable)


# 응답에 싣지 않는 키. `main.py:1208` 이 "화면에는 수식 대신 신호와 문장만 노출한다"
# 로 정한 것을 저장 경로가 뒤집지 않는다. 되짚기는 DB 를 직접 보는 사람의 몫이다.
AUDIT_ONLY = ("relationship", "observed_from", "observation_count")


def to_response(payload: dict) -> dict:
    """`build_combination` 의 결과에서 감사 전용 키를 걷어낸 응답 본문.

    걸러낼 키를 라우터에 흩어 적지 않고 여기 한 곳에 둔다. `preview` · `create` 가
    같은 함수를 쓰므로 **둘의 필드 집합이 갈라질 수 없다.**
    """
    return {k: v for k, v in payload.items() if k not in AUDIT_ONLY}
