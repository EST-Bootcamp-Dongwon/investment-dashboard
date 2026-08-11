"""F28 워크포워드 백테스트 — 도메인 계층.

docs/spec/60-운영/아키텍처.md 2.1절의 `services/` 계층이다. 계산 절차와 저장 규칙만
들고 있으며, HTTP 도 DB 도 모른다. `HTTPException` 을 던지지 않는다 — 도메인 예외를
올리고 라우터가 번역한다.

**계산 절차의 출처는 `app/backend/routers/backtest_lab.py:168~225`(리팩터 전
`_run_pipeline`)이고 값을 바꾸지 않았다.** 그 주장은 문서가 아니라 실측으로 고정한다 —
`scripts/verify_backtest_api.py` 가 리팩터 **전** 출력을 골든으로 들고 있다가 지금
출력과 `==` 로 비교한다.

## F03 · F04 · F05 와 다른 점 — **원본이 이미 라우터였다**

F03 은 프런트 JS 에서, F04 는 `main.py` 에서, F05 는 `routers/quant.py` 에서 도메인을
꺼내 왔다. F28 의 원본은 **이미 `routers/backtest_lab.py` 안의 함수**다. 그래서
CN-106 ①(`main.py` 원문 AST 대조)이 필요 없다 — 원본을 그냥 부를 수 있고, 더 강한
대조인 **출력 전체 비교**가 가능하다.

## `hd_core` 를 여기서 import 하는 이유

`clients/` 가 아니라 여기다. `hd_core` 는 바깥 세상을 부르지 않는 **순수 계산
모듈**이라(입력은 DataFrame, 출력은 dict) `numpy`·`pandas` 와 같은 자리다.
아키텍처 2.1절이 `clients/` 에 두라고 한 것은 *"바깥 세상을 아는"* 코드이고,
F28 에서 그것은 시세 하나뿐이라 `clients/lean_prices.py` 로 갈랐다.

## 저장할 때 입력을 먼저 깎는다 — 이 파일에서 가장 중요한 결정

`backtest_summary` 의 컬럼이 요청보다 **정밀도가 낮다.**

    initial_cash    bigint        ← 요청은 float (`RunRequest.initial_cash`)
    commission_rate numeric(6,5)  ← 요청은 float, 소수 6자리 이상이 올 수 있다
    sell_tax_rate   numeric(6,5)  ← 〃
    slippage_rate   numeric(6,5)  ← 〃

계산을 먼저 하고 저장할 때 깎으면, **저장된 입력으로 다시 돌려도 저장된 결과가 나오지
않는다.** 마이그레이션 20260809120500 말미가 *"입력 11개가 남아 있으므로 재실행으로
복원한다"* 고 적은 그 전제가 깨진다. 비용률은 성과 계산에서 누적 곱셈에 들어가므로
6자리째 차이가 수익률 끝자리에 남는다.

그래서 **깎은 다음에 계산한다**(`RunParams.normalized`). 그러면 굴린 값과 저장한 값이
같은 값이 되고, 재실행이 실제로 같은 결과를 낸다.

`/run` 도 같은 정규화를 지난다. 두 경로가 다르게 깎으면 같은 요청이 저장 여부에 따라
다른 숫자를 내기 때문이다 — 저장 기능을 붙이면서 생길 이유가 없는 차이다.

**Postgres 가 어떻게 반올림하는지에 기대지 않는다.** 여기서 5자리로 깎아 보내므로
원격은 반올림할 일이 없다. `float` 은 0.00015 를 정확히 담지 못하지만, JSON 직렬화가
왕복하는 최단 표기를 쓰므로 원격에 도착하는 문자열은 `"0.00015"` 다. 이 왕복이 실제로
값을 보존한다는 것은 `verify_backtest_api.py` 가 원격에 넣었다 빼서 `==` 로 확인한다.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta
from decimal import ROUND_HALF_UP, Decimal
from typing import Any

try:
    from ..clients import lean_prices
except ImportError:  # `uvicorn main:app` 를 app/backend 에서 실행하는 경우
    from clients import lean_prices  # type: ignore

# `lean-hyundai/` 를 sys.path 에 얹은 뒤에 `hd_core` 를 부른다.
lean_prices.ensure_path()

try:
    import hd_core  # type: ignore

    IMPORT_ERROR = ""
except Exception as exc:  # pragma: no cover - 환경 문제를 화면에 그대로 알린다.
    hd_core = None  # type: ignore
    IMPORT_ERROR = f"{type(exc).__name__}: {exc}"


# 기본 비용 가정. `hd_core` 를 못 불러온 환경에서도 화면이 뜨도록 폴백을 둔다.
# 값은 `hd_core.py:32~37` 과 같다. 리팩터 전 `backtest_lab.py:69~71` 이 하던 일이다.
DEFAULT_COMMISSION_RATE = hd_core.DEFAULT_COMMISSION_RATE if hd_core else 0.00015
DEFAULT_SELL_TAX_RATE = hd_core.DEFAULT_SELL_TAX_RATE if hd_core else 0.0015
DEFAULT_SLIPPAGE_RATE = hd_core.DEFAULT_SLIPPAGE_RATE if hd_core else 0.0005

#: 비용률 컬럼의 소수 자릿수. `numeric(6,5)` 의 5 다.
RATE_DECIMALS = 5

#: 프리셋. 사용자가 티커를 몰라도 바로 눌러볼 수 있게 한다.
#: 리팩터 전 `backtest_lab.py:43~51` 그대로다.
PRESETS = [
    {"ticker": "005380.KS", "name": "현대차"},
    {"ticker": "005930.KS", "name": "삼성전자"},
    {"ticker": "000660.KS", "name": "SK하이닉스"},
    {"ticker": "035420.KS", "name": "NAVER"},
    {"ticker": "051910.KS", "name": "LG화학"},
    {"ticker": "207940.KS", "name": "삼성바이오로직스"},
    {"ticker": "^KS11", "name": "코스피 지수"},
]

# ── 되살릴 수 없는 값 — 저장하지 않기로 한 것들 (제약 C-04) ──────────────────
#
# 목록으로 **이름을 박아 두는 이유**는 F04 에서 배운 것이다(CN-108). 무엇이 빠지는지
# 문서에만 적으면 나중에 하나 더 빠져도 아무도 모른다. 검증이 이 상수를 읽어
# `save` 와 `detail` 의 키 차집합과 대조하므로, 목록과 실제가 어긋나면 검사가 깨진다.

#: `/run` 의 최상위 키 중 저장하지 않는 것. 일별 자산곡선·예측표·국면 요약이다.
UNSAVED_TOP = ("rows", "regime", "feature_importance")
#: `meta` 중 저장하지 않는 것. 표본 수 둘은 `rows` 없이 의미가 없고, 피처 목록은
#: `hd_core.FEATURE_COLUMNS` 라 지금 값을 그대로 쓰면 **옛 행에 새 목록**이 붙는다.
UNSAVED_META = ("train_samples", "test_samples", "features")
#: `simple_backtest` 중 저장하지 않는 것. 일별 곡선이라 행 수가 구간 길이만큼 늘어난다.
UNSAVED_BACKTEST = ("curve",)


class BacktestUnavailable(Exception):
    """예측 모듈을 불러오지 못했다. 라우터가 503 으로 번역한다."""


class BacktestInputError(Exception):
    """사용자가 고칠 수 있는 문제. 라우터가 400 으로 번역한다.

    리팩터 전 `_check_period` 4건과 `train_and_predict` 의 `ValueError` 가 전부
    400 이었다(`backtest_lab.py:113~133,193`). 그 하나를 유지하려고 예외도 하나만 둔다.
    문구는 호출자가 그대로 쓴다.
    """


def engine_available() -> bool:
    """예측 모듈과 시세 모듈이 모두 import 됐는지. `/config` 가 화면에 알려 준다."""
    return hd_core is not None and not lean_prices.IMPORT_ERROR


def import_error() -> str:
    """못 불러왔다면 그 원인. 둘 다 실패했으면 둘 다 알려 준다."""
    return " / ".join(m for m in (IMPORT_ERROR, lean_prices.IMPORT_ERROR) if m)


def _quantize_rate(value: float) -> float:
    """비용률을 `numeric(6,5)` 가 담을 수 있는 5자리로 깎는다. 이유는 모듈 머리말."""
    quantized = Decimal(str(value)).quantize(
        Decimal(1).scaleb(-RATE_DECIMALS), rounding=ROUND_HALF_UP
    )
    return float(quantized)


def _quantize_cash(value: float) -> int:
    """초기 자본을 `bigint` 가 담을 수 있는 정수로 깎는다.

    반올림이 범위를 벗어나게 하지 않는다 — 제약이 `between 1000000 and 1000000000000`
    으로 **정수 경계**라, 그 안의 값을 반올림해도 안에 남는다.
    """
    return int(Decimal(str(value)).quantize(Decimal(1), rounding=ROUND_HALF_UP))


@dataclass(frozen=True)
class RunParams:
    """백테스트 입력 11개. **항상 정규화된 값**이다.

    `frozen=True` 는 굴린 값과 저장한 값이 같은 값임을 보장하려는 것이다. 중간에
    누가 바꿔 쓰면 모듈 머리말의 전제가 조용히 깨진다.
    """

    ticker: str
    name: str
    train_start: str
    train_end: str
    test_start: str
    test_end: str
    initial_cash: int
    commission_rate: float
    sell_tax_rate: float
    slippage_rate: float
    warmup_days: int

    @classmethod
    def normalized(
        cls,
        *,
        ticker: str,
        name: str,
        train_start: str,
        train_end: str,
        test_start: str,
        test_end: str,
        initial_cash: float,
        commission_rate: float,
        sell_tax_rate: float,
        slippage_rate: float,
        warmup_days: int,
    ) -> "RunParams":
        """저장 컬럼의 정밀도에 맞춰 깎은 입력을 만든다. 유일한 생성 경로다."""
        return cls(
            ticker=ticker,
            # `name` 이 비면 티커로 채운다. `name` 은 NOT NULL 이고, 리팩터 전
            # `meta` 도 `payload.name or payload.ticker` 였다(`backtest_lab.py:210`).
            name=name or ticker,
            train_start=train_start,
            train_end=train_end,
            test_start=test_start,
            test_end=test_end,
            initial_cash=_quantize_cash(initial_cash),
            commission_rate=_quantize_rate(commission_rate),
            sell_tax_rate=_quantize_rate(sell_tax_rate),
            slippage_rate=_quantize_rate(slippage_rate),
            warmup_days=warmup_days,
        )

    def as_inputs(self) -> dict[str, Any]:
        """재실행에 필요한 입력 11개를 그대로 돌려준다.

        **응답에 싣는 이유**는 정규화가 값을 바꿀 수 있기 때문이다. 사용자가
        `0.000123456` 을 보냈는데 `0.00012` 로 굴렸다면, 그 사실이 응답에 보여야 한다.
        저장 컬럼과 1:1 이라 이 블록만 있으면 같은 결과를 다시 만들 수 있다.
        """
        return {
            "ticker": self.ticker,
            "name": self.name,
            "train_start": self.train_start,
            "train_end": self.train_end,
            "test_start": self.test_start,
            "test_end": self.test_end,
            "initial_cash": self.initial_cash,
            "commission_rate": self.commission_rate,
            "sell_tax_rate": self.sell_tax_rate,
            "slippage_rate": self.slippage_rate,
            "warmup_days": self.warmup_days,
        }


def _require_engine() -> None:
    if not engine_available():
        raise BacktestUnavailable(import_error() or "경로에서 모듈을 찾지 못함")


def check_period(params: RunParams) -> None:
    """구간 4개의 순서와 겹침을 본다. 문구는 리팩터 전 `backtest_lab.py:113~133` 그대로다."""
    train_start = date.fromisoformat(params.train_start)
    train_end = date.fromisoformat(params.train_end)
    test_start = date.fromisoformat(params.test_start)
    test_end = date.fromisoformat(params.test_end)

    if train_start >= train_end:
        raise BacktestInputError("학습 시작일이 학습 종료일보다 빠릅니다.")
    if test_start >= test_end:
        raise BacktestInputError("검증 시작일이 검증 종료일보다 빠릅니다.")
    if test_start <= train_end:
        raise BacktestInputError(
            "검증 구간이 학습 구간과 겹칩니다. 겹치면 out-of-sample 검증이 아니라 "
            "그냥 학습 데이터를 다시 맞히는 것이 됩니다. 검증 시작일을 학습 종료일 뒤로 두세요."
        )
    if test_end > date.today():
        raise BacktestInputError(
            f"검증 종료일({params.test_end})이 오늘({date.today().isoformat()})보다 뒤입니다. "
            "아직 오지 않은 날은 실제값이 없어 비교할 수 없습니다."
        )


def run(params: RunParams) -> dict:
    """시세 수집 → 피처 → 학습·예측 → 평가 → 간이 백테스트.

    리팩터 전 `_run_pipeline` 과 **같은 dict 를 돌려준다.** 다른 점은 `HTTPException`
    대신 도메인 예외를 올린다는 것 하나이고, 시세는 `clients/lean_prices` 를 거친다.
    """
    import pandas as pd

    _require_engine()
    check_period(params)

    data_start = (
        date.fromisoformat(params.train_start) - timedelta(days=params.warmup_days)
    ).isoformat()
    # 시세 실패(502·404)는 `lean_prices` 의 예외가 그대로 라우터까지 올라간다.
    rows = lean_prices.download(params.ticker, data_start, params.test_end)

    prices = pd.DataFrame(rows, columns=["Date", "Open", "High", "Low", "Close", "Volume"])
    prices["Date"] = pd.to_datetime(prices["Date"])
    prices = prices.sort_values("Date").drop_duplicates("Date").reset_index(drop=True)

    featured = hd_core.build_features(prices)
    try:
        prediction = hd_core.train_and_predict(
            featured,
            params.train_start,
            params.train_end,
            params.test_start,
            params.test_end,
        )
    except ValueError as exc:
        # 학습·검증 구간에 표본이 모자란 경우다. 사용자가 구간을 넓히면 풀린다.
        raise BacktestInputError(str(exc)) from exc

    backtest = hd_core.simple_backtest(
        prediction.rows,
        initial_cash=params.initial_cash,
        commission_rate=params.commission_rate,
        sell_tax_rate=params.sell_tax_rate,
        slippage_rate=params.slippage_rate,
    )

    return {
        "meta": {
            "ticker": params.ticker,
            "name": params.name,
            "train_start": params.train_start,
            "train_end": params.train_end,
            "test_start": params.test_start,
            "test_end": params.test_end,
            "train_samples": prediction.train_size,
            "test_samples": len(prediction.rows),
            "model": "sklearn HistGradientBoostingRegressor",
            "features": hd_core.FEATURE_COLUMNS,
            "price_rows": int(len(prices)),
            "price_first": prices["Date"].iloc[0].date().isoformat(),
            "price_last": prices["Date"].iloc[-1].date().isoformat(),
            "engine": "간이(벡터화) 계산 — 정본은 LEAN 엔진 실행 결과입니다.",
        },
        "regime": hd_core.regime_summary(
            featured, params.train_start, params.train_end, params.test_start, params.test_end
        ),
        "prediction_metrics": prediction.metrics.to_dict(),
        "feature_importance": prediction.feature_importance,
        "rows": prediction.rows,
        "simple_backtest": backtest,
    }


def to_row(params: RunParams, result: dict, *, user_id: str | None, anon_id: str | None) -> dict:
    """실행 결과를 `backtest_summary` 한 행으로 옮긴다. DB 를 부르지 않는다.

    저장하는 것은 **입력 11개 + 지표 3덩이 + 시세 창 3개**다. 무엇을 빼는지는
    `UNSAVED_*` 상수에 있다.
    """
    meta = result["meta"]
    backtest = result["simple_backtest"]
    return {
        "user_id": user_id,
        "anon_id": anon_id,
        "ticker": params.ticker,
        "name": params.name,
        "train_start": params.train_start,
        "train_end": params.train_end,
        "test_start": params.test_start,
        "test_end": params.test_end,
        "initial_cash": params.initial_cash,
        "commission_rate": params.commission_rate,
        "sell_tax_rate": params.sell_tax_rate,
        "slippage_rate": params.slippage_rate,
        "warmup_days": params.warmup_days,
        "model_name": meta["model"],
        "strategy_stats": backtest["strategy"],
        "benchmark_stats": backtest["benchmark"],
        "prediction_metrics": result["prediction_metrics"],
        "price_rows": meta["price_rows"],
        "price_first": meta["price_first"],
        "price_last": meta["price_last"],
        "engine_note": meta["engine"],
    }


def to_detail(row: dict) -> dict:
    """저장된 행 하나를 `/save` 응답과 **같은 모양**으로 되살린다.

    `cost_assumptions` 와 `excess_return_pct` 는 컬럼이 없지만 **되살릴 수 있다** —
    앞은 저장한 입력 4개 그대로이고, 뒤는 저장한 두 수익률의 차다. 컬럼을 만들지 않은
    것은 저장된 값에서 유도되는 값이라 따로 두면 어긋날 자리가 생기기 때문이다.

    **`hd_core.simple_backtest` 와 같은 식으로 뺀다**(`hd_core.py:494~495`). 다시
    계산하는 쪽이 저장하는 쪽보다 나은 이유는, 지표 정의가 바뀌면 옛 행도 같이
    새 정의로 보이기 때문이다 — 유도값은 원본과 어긋나 있으면 안 된다.
    """
    strategy = row["strategy_stats"]
    benchmark = row["benchmark_stats"]
    return {
        "meta": {
            "ticker": row["ticker"],
            "name": row["name"],
            "train_start": row["train_start"],
            "train_end": row["train_end"],
            "test_start": row["test_start"],
            "test_end": row["test_end"],
            "model": row["model_name"],
            "price_rows": row["price_rows"],
            "price_first": row["price_first"],
            "price_last": row["price_last"],
            "engine": row["engine_note"],
        },
        "prediction_metrics": row["prediction_metrics"],
        "simple_backtest": {
            "strategy": strategy,
            "benchmark": benchmark,
            "excess_return_pct": strategy["total_return_pct"] - benchmark["total_return_pct"],
            "cost_assumptions": {
                "commission_rate": row["commission_rate"],
                "sell_tax_rate": row["sell_tax_rate"],
                "slippage_rate": row["slippage_rate"],
                "initial_cash": row["initial_cash"],
            },
        },
        "inputs": {
            "ticker": row["ticker"],
            "name": row["name"],
            "train_start": row["train_start"],
            "train_end": row["train_end"],
            "test_start": row["test_start"],
            "test_end": row["test_end"],
            "initial_cash": row["initial_cash"],
            "commission_rate": row["commission_rate"],
            "sell_tax_rate": row["sell_tax_rate"],
            "slippage_rate": row["slippage_rate"],
            "warmup_days": row["warmup_days"],
        },
        "backtest_id": row["id"],
        "created_at": row["created_at"],
    }


def to_list_item(row: dict) -> dict:
    """목록 한 줄. **지표 3덩이(jsonb)를 담지 않는다.**

    F05 의 `history` 가 곡선을 뺀 것과 같은 판단이다. 목록에서 필요한 것은 "언제 ·
    무엇을 · 얼마나 벌었나" 뿐인데, `prediction_metrics` 16필드 × `strategy`·
    `benchmark` 12필드씩을 N행 실으면 목록 응답이 상세보다 무거워진다.

    대신 **생성 컬럼 2개**를 읽는다. 마이그레이션 20260809120500 이
    *"자주 정렬·필터할 지표만 생성 컬럼으로 승격한다"* 며 만들어 둔 그 둘이고,
    여기가 그 컬럼이 쓰이는 자리다.
    """
    return {
        "backtest_id": row["id"],
        "ticker": row["ticker"],
        "name": row["name"],
        "train_start": row["train_start"],
        "train_end": row["train_end"],
        "test_start": row["test_start"],
        "test_end": row["test_end"],
        "model": row["model_name"],
        "price_rows": row["price_rows"],
        "total_return_pct": row["strategy_total_return_pct"],
        "max_drawdown_pct": row["strategy_max_drawdown_pct"],
        "created_at": row["created_at"],
    }
