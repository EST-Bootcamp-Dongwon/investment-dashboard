"""예측 모델·평가·간이 백테스트 공용 모듈.

LEAN 컨테이너(sklearn 1.6.1)와 웹앱 백엔드 컨테이너(scikit-learn) 양쪽에서
**같은 코드**가 돌도록 sklearn 만 사용합니다. LightGBM 을 쓰지 않는 이유가 이것입니다 —
두 환경에 공통으로 설치된 부스팅 구현이 sklearn 의 HistGradientBoosting 뿐입니다.

역할 분담:
  - 이 모듈       : 피처 → 모델 학습 → 예측 → 예측 정확도 평가 → 간이(벡터화) 백테스트
  - LEAN 알고리즘 : 이 모듈이 만든 신호로 **실제 주문을 집행** (체결·수수료·세금 반영)

간이 백테스트는 탐색용 근사치이고, 최종 성과의 정본은 LEAN 실행 결과입니다.
둘의 수치가 조금 다를 수 있으며 리포트에서 나란히 보여줍니다.
"""

from __future__ import annotations

import csv
import math
from dataclasses import dataclass, field, asdict
from datetime import date
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.ensemble import HistGradientBoostingRegressor

# ---------------------------------------------------------------------------
# 비용 가정 — 전부 "가정"이며 실제 계좌 조건에 맞게 바꿔야 합니다.
# ---------------------------------------------------------------------------

#: 위탁수수료율(편도). 증권사·계좌 등급에 따라 다릅니다.
DEFAULT_COMMISSION_RATE = 0.00015  # 0.015%
#: 매도 시에만 붙는 세금. 2025년 이후 코스피는 증권거래세 0% + 농어촌특별세 0.15% 구조입니다.
#: 세율은 정책에 따라 바뀌므로 실행 전 반드시 확인하세요.
DEFAULT_SELL_TAX_RATE = 0.0015  # 0.15%
#: 체결 슬리피지 가정(편도). 종가 동시호가 체결을 가정한 보수적 값입니다.
DEFAULT_SLIPPAGE_RATE = 0.0005  # 0.05%

TRADING_DAYS_PER_YEAR = 252

FEATURE_COLUMNS = [
    "ret_1",
    "ret_2",
    "ret_3",
    "ret_5",
    "ret_10",
    "sma5_gap",
    "sma20_gap",
    "rsi14",
    "vol20",
    "volume_ratio",
    "hl_range",
    "range_position",
]


# ---------------------------------------------------------------------------
# 데이터 적재와 피처
# ---------------------------------------------------------------------------


def load_prices(csv_path: str | Path) -> pd.DataFrame:
    """다운로더가 만든 CSV를 읽어 날짜 오름차순 DataFrame으로 돌려줍니다."""
    frame = pd.read_csv(csv_path)
    frame["Date"] = pd.to_datetime(frame["Date"])
    frame = frame.sort_values("Date").drop_duplicates("Date").reset_index(drop=True)
    for column in ("Open", "High", "Low", "Close", "Volume"):
        frame[column] = pd.to_numeric(frame[column], errors="coerce")
    return frame.dropna(subset=["Open", "High", "Low", "Close"]).reset_index(drop=True)


def _rsi(close: pd.Series, period: int = 14) -> pd.Series:
    """RSI — 단순이동평균(Cutler) 방식.

    Wilder 원형은 `ewm` 이라 **첫 행부터 재귀적**입니다. 그러면 시세를 며칠 전부터
    받았느냐에 따라 RSI 가 통째로 달라지고, 같은 종목·같은 구간을 돌려도 결과가
    재현되지 않습니다(워밍업 시작일만 바꿔도 성과가 몇 %p 씩 움직였습니다).

    여기서는 rolling 평균을 써서 **모든 피처의 참조 범위를 최근 20봉 이내로 한정**합니다.
    워밍업을 얼마나 넉넉히 잡든 학습 구간의 피처 값이 동일해집니다.
    """
    delta = close.diff()
    gain = delta.clip(lower=0.0)
    loss = -delta.clip(upper=0.0)
    avg_gain = gain.rolling(period).mean()
    avg_loss = loss.rolling(period).mean()
    rs = avg_gain / avg_loss.replace(0.0, np.nan)
    return (100 - 100 / (1 + rs)).fillna(50.0)


def build_features(prices: pd.DataFrame) -> pd.DataFrame:
    """t일 종가까지의 정보만으로 피처를 만들고, 타깃은 t+1일 수익률로 둡니다.

    **선견(lookahead) 금지가 이 함수의 전부입니다.** 모든 피처는 t 시점에 확정된
    값만 쓰고, 미래를 보는 유일한 열은 타깃(`target_ret`)입니다.
    """
    frame = prices.copy()
    close = frame["Close"]

    ret_1 = close.pct_change()
    frame["ret_1"] = ret_1
    frame["ret_2"] = close.pct_change(2)
    frame["ret_3"] = close.pct_change(3)
    frame["ret_5"] = close.pct_change(5)
    frame["ret_10"] = close.pct_change(10)

    frame["sma5_gap"] = close / close.rolling(5).mean() - 1
    frame["sma20_gap"] = close / close.rolling(20).mean() - 1
    frame["rsi14"] = _rsi(close, 14)
    frame["vol20"] = ret_1.rolling(20).std()

    volume_mean = frame["Volume"].rolling(20).mean()
    frame["volume_ratio"] = frame["Volume"] / volume_mean.replace(0.0, np.nan)
    frame["hl_range"] = (frame["High"] - frame["Low"]) / close

    low20 = frame["Low"].rolling(20).min()
    high20 = frame["High"].rolling(20).max()
    span = (high20 - low20).replace(0.0, np.nan)
    frame["range_position"] = (close - low20) / span

    # 타깃: t+1일 종가 수익률. 마지막 행은 타깃이 없어 NaN 이 됩니다.
    frame["target_ret"] = close.shift(-1) / close - 1
    frame["next_close"] = close.shift(-1)
    frame["next_date"] = frame["Date"].shift(-1)

    return frame


# ---------------------------------------------------------------------------
# 학습과 예측
# ---------------------------------------------------------------------------


@dataclass
class PredictionMetrics:
    """예측 정확도 지표. 모두 out-of-sample 구간에서 계산합니다."""

    n_samples: int = 0
    # 수익률 기준
    mae_return: float = 0.0
    rmse_return: float = 0.0
    # 가격 기준(원). pred_price = close_t * (1 + pred_ret)
    mae_price: float = 0.0
    rmse_price: float = 0.0
    mape_price: float = 0.0
    # 방향
    direction_accuracy: float = 0.0
    up_ratio_actual: float = 0.0
    up_ratio_predicted: float = 0.0
    # 기준선(naive) — "내일도 오늘과 같다"는 랜덤워크 가정
    naive_mae_return: float = 0.0
    naive_rmse_return: float = 0.0
    naive_mae_price: float = 0.0
    naive_direction_accuracy: float = 0.0
    # 상대 평가
    beats_naive_mae: bool = False
    beats_naive_direction: bool = False
    r2_vs_naive: float = 0.0

    def to_dict(self) -> dict:
        return asdict(self)


def _safe_div(numerator: float, denominator: float) -> float:
    return float(numerator / denominator) if denominator else 0.0


def evaluate_predictions(
    actual_ret: np.ndarray,
    pred_ret: np.ndarray,
    base_close: np.ndarray,
) -> PredictionMetrics:
    """예측 수익률을 실제와 비교합니다.

    **naive 기준선을 함께 계산하는 게 핵심입니다.** 주가 일간 수익률 예측은
    "내일도 오늘 종가"라는 랜덤워크 기준선을 넘기가 대단히 어렵습니다.
    기준선을 못 이기면 모델이 사실상 아무것도 학습하지 못한 것입니다.
    """
    metrics = PredictionMetrics()
    if actual_ret.size == 0:
        return metrics

    actual_price = base_close * (1 + actual_ret)
    pred_price = base_close * (1 + pred_ret)

    error = pred_ret - actual_ret
    metrics.n_samples = int(actual_ret.size)
    metrics.mae_return = float(np.mean(np.abs(error)))
    metrics.rmse_return = float(math.sqrt(np.mean(error**2)))
    metrics.mae_price = float(np.mean(np.abs(pred_price - actual_price)))
    metrics.rmse_price = float(math.sqrt(np.mean((pred_price - actual_price) ** 2)))
    metrics.mape_price = float(np.mean(np.abs(pred_price - actual_price) / actual_price) * 100)

    actual_up = actual_ret > 0
    pred_up = pred_ret > 0
    metrics.direction_accuracy = float(np.mean(actual_up == pred_up) * 100)
    metrics.up_ratio_actual = float(np.mean(actual_up) * 100)
    metrics.up_ratio_predicted = float(np.mean(pred_up) * 100)

    # naive: 수익률 0 (= 내일 종가가 오늘 종가와 같다)
    metrics.naive_mae_return = float(np.mean(np.abs(actual_ret)))
    metrics.naive_rmse_return = float(math.sqrt(np.mean(actual_ret**2)))
    metrics.naive_mae_price = float(np.mean(np.abs(base_close - actual_price)))
    # naive 방향 기준선은 "항상 상승"으로 찍는 다수결 전략입니다.
    majority = max(metrics.up_ratio_actual, 100 - metrics.up_ratio_actual)
    metrics.naive_direction_accuracy = float(majority)

    metrics.beats_naive_mae = bool(metrics.mae_return < metrics.naive_mae_return)
    metrics.beats_naive_direction = bool(
        metrics.direction_accuracy > metrics.naive_direction_accuracy
    )
    # naive 대비 R² — 0보다 커야 예측이 기준선보다 나은 것입니다.
    ss_res = float(np.sum(error**2))
    ss_naive = float(np.sum(actual_ret**2))
    metrics.r2_vs_naive = 1 - _safe_div(ss_res, ss_naive) if ss_naive else 0.0
    return metrics


@dataclass
class PredictionRun:
    rows: list[dict] = field(default_factory=list)
    metrics: PredictionMetrics = field(default_factory=PredictionMetrics)
    train_size: int = 0
    feature_importance: dict[str, float] = field(default_factory=dict)


def train_and_predict(
    featured: pd.DataFrame,
    train_start: str,
    train_end: str,
    test_start: str,
    test_end: str,
    *,
    random_state: int = 42,
    max_iter: int = 300,
    learning_rate: float = 0.05,
    max_depth: int = 3,
) -> PredictionRun:
    """학습 구간으로만 모델을 적합하고 검증 구간을 out-of-sample 로 예측합니다.

    학습 표본에서 **타깃 날짜가 검증 시작일 이후인 행을 제외**합니다. 그러지 않으면
    학습 마지막 행의 타깃(= 검증 첫날 수익률)이 새어 들어갑니다.
    """
    frame = featured.dropna(subset=FEATURE_COLUMNS + ["target_ret"]).copy()

    train_mask = (
        (frame["Date"] >= pd.Timestamp(train_start))
        & (frame["Date"] <= pd.Timestamp(train_end))
        & (frame["next_date"] < pd.Timestamp(test_start))
    )
    test_mask = (frame["Date"] >= pd.Timestamp(test_start)) & (
        frame["Date"] <= pd.Timestamp(test_end)
    )

    train = frame[train_mask]
    test = frame[test_mask]
    if train.empty:
        raise ValueError(f"학습 구간 {train_start}~{train_end} 에 사용할 표본이 없습니다.")
    if test.empty:
        raise ValueError(f"검증 구간 {test_start}~{test_end} 에 사용할 표본이 없습니다.")

    model = HistGradientBoostingRegressor(
        max_iter=max_iter,
        learning_rate=learning_rate,
        max_depth=max_depth,
        random_state=random_state,
    )
    model.fit(train[FEATURE_COLUMNS].to_numpy(), train["target_ret"].to_numpy())
    pred = model.predict(test[FEATURE_COLUMNS].to_numpy())

    metrics = evaluate_predictions(
        test["target_ret"].to_numpy(),
        pred,
        test["Close"].to_numpy(),
    )

    rows: list[dict] = []
    for (_, row), predicted in zip(test.iterrows(), pred):
        rows.append(
            {
                # signal_date: 신호가 확정되는 날(= t일 종가 시점)
                "signal_date": row["Date"].date().isoformat(),
                # target_date: 예측 대상이 되는 다음 거래일(t+1)
                "target_date": row["next_date"].date().isoformat(),
                "close": float(row["Close"]),
                "actual_next_close": float(row["next_close"]),
                "actual_ret": float(row["target_ret"]),
                "pred_ret": float(predicted),
                "pred_next_close": float(row["Close"] * (1 + predicted)),
                "signal": 1 if predicted > 0 else 0,
                "direction_hit": bool((predicted > 0) == (row["target_ret"] > 0)),
            }
        )

    run = PredictionRun(rows=rows, metrics=metrics, train_size=int(len(train)))

    # permutation importance 는 비싸므로, 학습 데이터 기준 단순 치환 중요도를 씁니다.
    try:
        from sklearn.inspection import permutation_importance

        result = permutation_importance(
            model,
            test[FEATURE_COLUMNS].to_numpy(),
            test["target_ret"].to_numpy(),
            n_repeats=5,
            random_state=random_state,
        )
        run.feature_importance = {
            name: float(value)
            for name, value in zip(FEATURE_COLUMNS, result.importances_mean)
        }
    except Exception:  # 중요도는 부가 정보라 실패해도 본 흐름을 막지 않습니다.
        run.feature_importance = {}

    return run


# ---------------------------------------------------------------------------
# 간이(벡터화) 백테스트 — 탐색용 근사치
# ---------------------------------------------------------------------------


@dataclass
class BacktestStats:
    label: str = ""
    start_equity: float = 0.0
    end_equity: float = 0.0
    total_return_pct: float = 0.0
    cagr_pct: float = 0.0
    max_drawdown_pct: float = 0.0
    sharpe: float = 0.0
    volatility_pct: float = 0.0
    trades: int = 0
    win_rate_pct: float = 0.0
    days_in_market_pct: float = 0.0
    total_cost: float = 0.0

    def to_dict(self) -> dict:
        return asdict(self)


def _drawdown(equity: np.ndarray) -> float:
    if equity.size == 0:
        return 0.0
    peak = np.maximum.accumulate(equity)
    return float(np.min(equity / peak - 1) * 100)


def _stats_from_equity(
    label: str,
    equity: np.ndarray,
    daily_returns: np.ndarray,
    *,
    trades: int,
    wins: int,
    days_in_market: int,
    total_cost: float,
) -> BacktestStats:
    """`equity` 는 **시작 자본을 0번 원소로 포함**해야 합니다.

    첫날 수익률이 누락되는 것을 막기 위한 규약입니다. equity[0] 을 첫날 *종료* 자산으로
    두면 총수익률이 하루치만큼 잘못 계산됩니다.
    """
    stats = BacktestStats(label=label, trades=trades, total_cost=float(total_cost))
    if equity.size == 0:
        return stats

    stats.start_equity = float(equity[0])
    stats.end_equity = float(equity[-1])
    stats.total_return_pct = float((equity[-1] / equity[0] - 1) * 100)
    years = len(daily_returns) / TRADING_DAYS_PER_YEAR
    if years > 0 and equity[0] > 0 and equity[-1] > 0:
        stats.cagr_pct = float(((equity[-1] / equity[0]) ** (1 / years) - 1) * 100)
    stats.max_drawdown_pct = _drawdown(equity)

    if daily_returns.size > 1:
        std = float(np.std(daily_returns, ddof=1))
        stats.volatility_pct = std * math.sqrt(TRADING_DAYS_PER_YEAR) * 100
        if std > 0:
            stats.sharpe = float(
                np.mean(daily_returns) / std * math.sqrt(TRADING_DAYS_PER_YEAR)
            )
    stats.win_rate_pct = _safe_div(wins, trades) * 100 if trades else 0.0
    stats.days_in_market_pct = _safe_div(days_in_market, len(daily_returns)) * 100
    return stats


def simple_backtest(
    rows: list[dict],
    *,
    initial_cash: float = 100_000_000,
    commission_rate: float = DEFAULT_COMMISSION_RATE,
    sell_tax_rate: float = DEFAULT_SELL_TAX_RATE,
    slippage_rate: float = DEFAULT_SLIPPAGE_RATE,
) -> dict:
    """예측 신호로 전량 매수/전량 청산하는 단순 전략을 벡터화 계산합니다.

    체결 가정: 신호가 확정되는 t일 **종가**에 진입·청산합니다(종가 동시호가 체결 가정).
    이 가정은 낙관적입니다. 실제로는 종가를 확인한 뒤 그 종가로 체결할 수 없습니다.
    """
    if not rows:
        return {"strategy": BacktestStats().to_dict(), "benchmark": BacktestStats().to_dict(), "curve": []}

    actual = np.array([row["actual_ret"] for row in rows], dtype=float)
    signal = np.array([row["signal"] for row in rows], dtype=float)

    # 거래 비용: 포지션이 바뀌는 날에만 발생합니다.
    prev_signal = np.concatenate([[0.0], signal[:-1]])
    entering = (signal > 0) & (prev_signal == 0)
    exiting = (signal == 0) & (prev_signal > 0)
    # 마지막 날까지 보유 중이면 그날 청산한 것으로 봅니다.
    final_exit = np.zeros_like(exiting)
    final_exit[-1] = signal[-1] > 0

    buy_cost = commission_rate + slippage_rate
    sell_cost = commission_rate + sell_tax_rate + slippage_rate

    def _equity_curve(position: np.ndarray, buys: np.ndarray, sells: np.ndarray):
        """비용을 곱셈으로 반영한 자산곡선. 0번 원소가 시작 자본입니다."""
        gross = 1 + position * actual
        cost_factor = (1 - buys * buy_cost) * (1 - sells * sell_cost)
        growth = gross * cost_factor
        equity = initial_cash * np.concatenate([[1.0], np.cumprod(growth)])
        # 비용이 없었다면 얼마였을지와 비교해 총 비용을 역산합니다.
        gross_end = initial_cash * float(np.prod(gross))
        return equity, growth - 1, gross_end - equity[-1]

    strategy_equity, strategy_daily, strategy_cost = _equity_curve(
        signal, entering, exiting | final_exit
    )

    # 벤치마크: 첫날 매수해 끝까지 보유 (매수·매도 각 1회)
    hold = np.ones_like(signal)
    bench_buy = np.zeros_like(signal)
    bench_buy[0] = 1
    bench_sell = np.zeros_like(signal)
    bench_sell[-1] = 1
    benchmark_equity, benchmark_daily, benchmark_cost = _equity_curve(hold, bench_buy, bench_sell)

    # 왕복 거래 단위 손익. 승률은 '거래 건수' 기준이라 100%를 넘을 수 없습니다.
    # (일 단위로 세면 진입 횟수보다 승리일이 많아져 승률이 100%를 넘습니다.)
    trade_pnls: list[float] = []
    index = 0
    while index < len(signal):
        if signal[index] > 0:
            end = index
            while end < len(signal) and signal[end] > 0:
                end += 1
            gross = float(np.prod(1 + actual[index:end]))
            trade_pnls.append(gross * (1 - buy_cost) * (1 - sell_cost) - 1)
            index = end
        else:
            index += 1

    stats_strategy = _stats_from_equity(
        "예측 신호 전략",
        strategy_equity,
        strategy_daily,
        trades=len(trade_pnls),
        wins=sum(1 for pnl in trade_pnls if pnl > 0),
        days_in_market=int((signal > 0).sum()),
        total_cost=float(strategy_cost),
    )
    stats_benchmark = _stats_from_equity(
        "매수·보유",
        benchmark_equity,
        benchmark_daily,
        trades=1,
        wins=1 if benchmark_equity[-1] > initial_cash else 0,
        days_in_market=len(actual),
        total_cost=float(benchmark_cost),
    )

    curve = [
        {
            "date": row["target_date"],
            # equity[0] 은 시작 자본이므로 index+1 이 그날 종료 자산입니다.
            "strategy": float(strategy_equity[index + 1]),
            "benchmark": float(benchmark_equity[index + 1]),
            "close": float(row["actual_next_close"]),
            "signal": int(row["signal"]),
        }
        for index, row in enumerate(rows)
    ]

    return {
        "strategy": stats_strategy.to_dict(),
        "benchmark": stats_benchmark.to_dict(),
        "curve": curve,
        "excess_return_pct": stats_strategy.total_return_pct
        - stats_benchmark.total_return_pct,
        "cost_assumptions": {
            "commission_rate": commission_rate,
            "sell_tax_rate": sell_tax_rate,
            "slippage_rate": slippage_rate,
            "initial_cash": initial_cash,
        },
    }


def regime_summary(featured: pd.DataFrame, train_start: str, train_end: str,
                   test_start: str, test_end: str) -> dict:
    """학습 구간과 검증 구간의 변동성·추세를 비교합니다.

    두 구간의 성격이 크게 다르면 모델이 배운 패턴이 검증 구간에서 통하지 않습니다.
    예측이 왜 실패했는지를 설명하는 가장 흔한 원인이라 따로 뽑아둡니다.
    """

    def describe(start: str, end: str) -> dict:
        window = featured[
            (featured["Date"] >= pd.Timestamp(start)) & (featured["Date"] <= pd.Timestamp(end))
        ]
        returns = window["ret_1"].dropna()
        if returns.empty:
            return {}
        first, last = float(window["Close"].iloc[0]), float(window["Close"].iloc[-1])
        return {
            "start": window["Date"].iloc[0].date().isoformat(),
            "end": window["Date"].iloc[-1].date().isoformat(),
            "days": int(len(window)),
            "mean_abs_move_pct": float(returns.abs().mean() * 100),
            "annual_volatility_pct": float(
                returns.std(ddof=1) * math.sqrt(TRADING_DAYS_PER_YEAR) * 100
            ),
            "first_close": first,
            "last_close": last,
            "period_return_pct": float((last / first - 1) * 100),
        }

    train = describe(train_start, train_end)
    test = describe(test_start, test_end)
    ratio = 0.0
    if train.get("mean_abs_move_pct"):
        ratio = test.get("mean_abs_move_pct", 0.0) / train["mean_abs_move_pct"]
    return {"train": train, "test": test, "volatility_ratio": ratio}


def write_signals_csv(rows: list[dict], output: str | Path) -> Path:
    """LEAN Custom Data가 읽을 신호 CSV를 씁니다.

    한 행 = 하루이고, 그날 **종가 시점에 확정된** 신호를 함께 싣습니다.

        Date = t (신호 확정일)  ·  Close = close[t]  ·  Signal = t+1일 보유 여부

    LEAN 은 t일 봉을 받는 순간 Signal 을 보고 close[t] 에 체결합니다. 그 포지션이
    t+1일 봉에서 평가되므로, 예측이 겨냥한 구간(close[t] → close[t+1])과 정확히
    일치합니다. 신호가 t+1 행에 붙으면 하루 늦게 들어가 완전히 다른 전략이 됩니다.

    마지막에 검증 구간 최종일 행을 Signal=0 으로 한 줄 더 붙입니다. 그래야 엔진이
    마지막 포지션을 평가하고 청산할 수 있습니다.
    """
    path = Path(output)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="") as file:
        writer = csv.writer(file)
        writer.writerow(["Date", "Close", "PredReturn", "Signal", "NextReturn"])
        for row in rows:
            writer.writerow(
                [
                    row["signal_date"],
                    f"{row['close']:.4f}",
                    f"{row['pred_ret']:.8f}",
                    row["signal"],
                    f"{row['actual_ret']:.8f}",
                ]
            )
        last = rows[-1]
        writer.writerow([last["target_date"], f"{last['actual_next_close']:.4f}", "0", "0", "0"])
    return path
