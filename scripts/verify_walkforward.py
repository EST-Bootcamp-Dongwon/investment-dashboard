#!/usr/bin/env python3
"""C · `hd_core` 워크포워드 검사 — 학습/검증 분리가 깨지지 않았는지.

[테스트-계획 5.1절] 최소셋 7종 중 **C**. 문서가 적은 이유는
*"학습/검증 구간 분리가 깨지면 **성과가 조용히 부풀려집니다**"* 다.
조용하다는 것이 문제의 전부다 — 깨져도 화면은 멀쩡하고, 오히려 **더 좋아 보인다.**

## 무엇을 지키는가

`hd_core.train_and_predict:246~250` 에 가드가 셋 있다.

    train_mask = (Date >= train_start) & (Date <= train_end)
                 & (next_date < test_start)      ← 이 줄이 누출 가드다

셋째 줄이 없으면 **학습 마지막 행의 타깃이 검증 첫날 수익률**이 된다. 모델이
정답을 하나 보고 시험을 치는 것이고, 표본이 적을수록 그 하나가 성적을 흔든다.

이 검사는 그 줄이 **무엇을 잘라내는지 데이터로 보인다**(섹션 ④) — 잘려 나간 행의
타깃 날짜가 실제로 검증 구간 안에 있음을 확인한다. 모델을 학습시켜 성적을
비교하는 방식이 아니다. 그쪽은 표본에 따라 결과가 흔들려 **검사가 가끔 실패**한다.

`build_features` 쪽 선견은 **절단 불변성**으로 잡는다(섹션 ②) — 시세를 뒤에서
잘라내도 앞쪽 행의 피처가 그대로여야 한다. 미래를 조금이라도 보면 값이 바뀐다.

## 시세를 어디서 얻는가

만들어 쓴다. `yfinance` 를 부르면 **남의 쿼터를 쓰고 결과가 매일 달라진다**
(테스트-계획 5.2절). 난수는 씨앗을 고정해 매 실행 같은 값이 나오게 한다.

## 실행

    .venv/bin/python scripts/verify_walkforward.py

네트워크도 자격증명도 필요 없다. `pandas`·`numpy`·`scikit-learn` 이 필요하고,
셋 다 `requirements.txt` 에 있다. 없으면 종료 코드 2 로 알린다.
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "lean-hyundai"))
sys.path.insert(0, str(ROOT / "app" / "backend"))

try:
    import numpy as np
    import pandas as pd
    import hd_core
    from services import backtest as backtest_service
except ImportError as exc:  # 자격증명이 아니라 계산 라이브러리가 없는 경우
    print(f"\n건너뜁니다 — {exc}")
    print("  .venv/bin/pip install pandas numpy scikit-learn")
    raise SystemExit(2) from exc

results: list[tuple[str, str, str, str, bool]] = []


def brief(value) -> str:
    text = str(value)
    return text if len(text) <= 100 else text[:97] + "…"


def check(name: str, where: str, expected, got, extra: str = "") -> bool:
    """비교는 `==` 로 한다 (CN-098)."""
    ok = expected == got
    results.append((name, where, brief(expected), f"{brief(got)}{extra}", ok))
    return ok


# ─────────────────────────────────────────────────────────────────────────────
# 시세 — 씨앗을 고정한 랜덤워크
# ─────────────────────────────────────────────────────────────────────────────

SEED = 20260816
N_DAYS = 420
START = "2024-01-01"


def make_prices(n: int = N_DAYS) -> pd.DataFrame:
    """영업일 `n` 개짜리 일봉. 값이 아니라 **구조**를 검사하므로 분포는 중요하지 않다."""
    rng = np.random.default_rng(SEED)
    dates = pd.bdate_range(START, periods=n)
    step = rng.normal(0.0004, 0.015, size=n)
    close = 70_000 * np.exp(np.cumsum(step))
    spread = np.abs(rng.normal(0.008, 0.004, size=n)) * close
    return pd.DataFrame({
        "Date": dates,
        "Open": close - spread * 0.3,
        "High": close + spread,
        "Low": close - spread,
        "Close": close,
        "Volume": rng.integers(500_000, 3_000_000, size=n).astype(float),
    })


PRICES = make_prices()
FEATURED = hd_core.build_features(PRICES)

# 학습 종료 바로 다음 영업일이 검증 시작이다 — 누출 가드가 **가장 크게 걸리는** 배치다.
# 하루라도 띄우면 잘려 나가는 행이 0개가 되어 섹션 ④ 가 공허해진다.
READY = FEATURED.dropna(subset=hd_core.FEATURE_COLUMNS + ["target_ret"]).reset_index(drop=True)
SPLIT = int(len(READY) * 0.75)
TRAIN_START = READY["Date"].iloc[0].date().isoformat()
TRAIN_END = READY["Date"].iloc[SPLIT].date().isoformat()
TEST_START = READY["Date"].iloc[SPLIT + 1].date().isoformat()
TEST_END = READY["Date"].iloc[-1].date().isoformat()


# ─────────────────────────────────────────────────────────────────────────────
# ① 엔진 — 부를 수 있는가, 상수가 사본과 갈라지지 않았는가
# ─────────────────────────────────────────────────────────────────────────────

def verify_engine() -> None:
    check("① 피처 12개", "hd_core.FEATURE_COLUMNS", 12, len(hd_core.FEATURE_COLUMNS))
    check("① 피처 이름에 중복이 없다", "hd_core.FEATURE_COLUMNS",
          len(hd_core.FEATURE_COLUMNS), len(set(hd_core.FEATURE_COLUMNS)))

    # `services/backtest.py:78~80` 이 hd_core 를 못 불러온 환경용으로 같은 값을 손으로
    # 복제해 뒀다. 둘이 갈라지면 폴백 환경만 다른 비용으로 계산한다.
    check("① 비용 상수 3개가 services 폴백과 같다", "services/backtest.py",
          (hd_core.DEFAULT_COMMISSION_RATE, hd_core.DEFAULT_SELL_TAX_RATE,
           hd_core.DEFAULT_SLIPPAGE_RATE),
          (backtest_service.DEFAULT_COMMISSION_RATE,
           backtest_service.DEFAULT_SELL_TAX_RATE,
           backtest_service.DEFAULT_SLIPPAGE_RATE))

    check("① 검증용 시세를 만들었다", "make_prices",
          (N_DAYS, True), (len(PRICES), len(READY) > 200), f"  (피처 완비 {len(READY)}행)")


# ─────────────────────────────────────────────────────────────────────────────
# ② 선견 금지 — 뒤를 잘라내도 앞쪽 피처가 그대로여야 한다
# ─────────────────────────────────────────────────────────────────────────────

def verify_no_lookahead() -> None:
    """`build_features` 가 t 시점 정보만 쓰는지.

    시세를 뒤에서 60행 잘라내고 다시 피처를 만든다. 미래를 조금이라도 보는 열이
    있으면 **잘라낸 것만으로 앞쪽 값이 달라진다.** 롤링 창이 아무리 길어도
    뒤를 보지 않으면 값이 움직일 이유가 없다.
    """
    cut = len(PRICES) - 60
    short = hd_core.build_features(PRICES.iloc[:cut].reset_index(drop=True))

    mismatched = [
        column for column in hd_core.FEATURE_COLUMNS
        if not FEATURED[column].iloc[:cut].reset_index(drop=True)
        .equals(short[column].reset_index(drop=True))
    ]
    check("② 피처 12개가 절단에 불변", "build_features", [], mismatched,
          f"  (뒤 60행 절단 · 앞 {cut}행 대조)")

    # 타깃만은 달라져야 한다. 잘린 마지막 행은 다음 날이 없으므로 NaN 이다.
    # 이 검사가 없으면 위 검사는 "타깃도 과거만 본다"는 정반대 결함을 통과시킨다.
    check("② 타깃은 마지막 행에서만 달라진다", "build_features",
          (True, True),
          (bool(pd.isna(short["target_ret"].iloc[-1])),
           FEATURED["target_ret"].iloc[:cut - 1].reset_index(drop=True)
           .equals(short["target_ret"].iloc[:cut - 1].reset_index(drop=True))))


def verify_target_is_next_day() -> None:
    """타깃이 t+1 인가. `next_date`·`next_close`·`target_ret` 셋이 같은 행을 가리켜야 한다."""
    frame = FEATURED
    shifted_date = frame["Date"].shift(-1)
    shifted_close = frame["Close"].shift(-1)

    check("③ next_date 가 다음 행의 날짜", "build_features", True,
          frame["next_date"].equals(shifted_date))
    check("③ next_close 가 다음 행의 종가", "build_features", True,
          frame["next_close"].equals(shifted_close))

    expected = (shifted_close / frame["Close"] - 1)
    check("③ target_ret = next_close/close - 1", "build_features", True,
          frame["target_ret"].equals(expected))

    check("③ 마지막 행은 타깃이 없다", "build_features", True,
          bool(pd.isna(frame["target_ret"].iloc[-1])))


# ─────────────────────────────────────────────────────────────────────────────
# ④ 누출 가드 — 무엇이 잘려 나가는가
# ─────────────────────────────────────────────────────────────────────────────

def verify_leak_guard() -> None:
    in_train = (READY["Date"] >= pd.Timestamp(TRAIN_START)) & (
        READY["Date"] <= pd.Timestamp(TRAIN_END)
    )
    guarded = in_train & (READY["next_date"] < pd.Timestamp(TEST_START))

    naive_size = int(in_train.sum())
    guarded_size = int(guarded.sum())
    leaked = READY[in_train & ~(READY["next_date"] < pd.Timestamp(TEST_START))]

    check("④ 가드가 학습 표본을 줄인다", "train_and_predict",
          True, naive_size > guarded_size,
          f"  (가드 없음 {naive_size} → 가드 {guarded_size})")

    # 잘려 나간 행이 0개면 아래 검사가 `[] == []` 로 **공허하게 통과한다.**
    # 구간 배치가 바뀌어 그렇게 되는 순간 여기서 먼저 걸리게 한다 (CN-128 의 교훈).
    check("④ 잘려 나간 행이 있다 — 아래 검사가 공허하지 않다", "train_and_predict",
          True, len(leaked) > 0, f"  ({len(leaked)}행)")

    # **핵심.** 잘려 나간 행의 타깃 날짜가 검증 구간 안에 있다. 그래서 남겨 두면
    # 검증 구간의 정답을 학습하게 된다 — 이것이 "조용히 부풀려진다"의 기전이다.
    inside = [
        pd.Timestamp(TEST_START) <= d <= pd.Timestamp(TEST_END)
        for d in leaked["next_date"]
    ]
    check("④ 잘려 나간 행의 타깃이 검증 구간 안에 있다", "train_and_predict",
          [True] * len(leaked), inside, f"  ({len(leaked)}행)")

    # 학습 마지막 행의 타깃은 **검증 첫날** 이다. 가드가 막는 것이 정확히 그것이다.
    check("④ 잘린 행의 타깃이 검증 첫날", "train_and_predict",
          [pd.Timestamp(TEST_START)], list(leaked["next_date"]))

    # 실제 함수가 그 수만큼만 학습했는가. 여기서 처음으로 모델을 돌린다.
    run = hd_core.train_and_predict(FEATURED, TRAIN_START, TRAIN_END, TEST_START, TEST_END)
    check("④ train_size 가 가드 적용 수와 같다", "train_and_predict",
          guarded_size, run.train_size)

    check("④ 예측 행 수가 검증 표본 수와 같다", "train_and_predict",
          int(((READY["Date"] >= pd.Timestamp(TEST_START))
               & (READY["Date"] <= pd.Timestamp(TEST_END))).sum()),
          len(run.rows))
    return run


# ─────────────────────────────────────────────────────────────────────────────
# ⑤ 구간 분리 — 예측이 검증 구간 밖으로 나가지 않는가
# ─────────────────────────────────────────────────────────────────────────────

def verify_split(run) -> None:
    signal = [row["signal_date"] for row in run.rows]
    outside = [d for d in signal if not (TEST_START <= d <= TEST_END)]
    check("⑤ 예측이 전부 검증 구간 안", "train_and_predict", [], outside)

    overlapping = [d for d in signal if d <= TRAIN_END]
    check("⑤ 학습 구간과 겹치는 예측이 없다", "train_and_predict", [], overlapping)

    wrong_order = [r for r in run.rows if r["target_date"] <= r["signal_date"]]
    check("⑤ 타깃 날짜가 신호 날짜보다 뒤", "train_and_predict", [], wrong_order)

    # `direction_hit` 정의가 뒤집히면 방향 정확도가 통째로 거짓이 된다.
    wrong_hit = [
        r for r in run.rows
        if r["direction_hit"] != ((r["pred_ret"] > 0) == (r["actual_ret"] > 0))
    ]
    check("⑤ direction_hit 정의", "train_and_predict", [], wrong_hit)

    wrong_signal = [r for r in run.rows if r["signal"] != int(r["pred_ret"] > 0)]
    check("⑤ signal 은 예측 부호", "train_and_predict", [], wrong_signal)


# ─────────────────────────────────────────────────────────────────────────────
# ⑥ 재현성 — 같은 입력이면 같은 예측
# ─────────────────────────────────────────────────────────────────────────────

def verify_reproducible(run) -> None:
    again = hd_core.train_and_predict(FEATURED, TRAIN_START, TRAIN_END, TEST_START, TEST_END)
    check("⑥ 두 번 돌려도 예측이 같다", "train_and_predict",
          [r["pred_ret"] for r in run.rows], [r["pred_ret"] for r in again.rows])
    check("⑥ 두 번 돌려도 학습 표본 수가 같다", "train_and_predict",
          run.train_size, again.train_size)


# ─────────────────────────────────────────────────────────────────────────────
# ⑦ 빈 구간 — 거절하고 이유를 말하는가
# ─────────────────────────────────────────────────────────────────────────────

def verify_empty_windows() -> None:
    for label, args in (
        ("학습", ("1999-01-01", "1999-12-31", TEST_START, TEST_END)),
        ("검증", (TRAIN_START, TRAIN_END, "2099-01-01", "2099-12-31")),
    ):
        try:
            hd_core.train_and_predict(FEATURED, *args)
            check(f"⑦ 빈 {label} 구간을 거절한다", "train_and_predict", "ValueError", "없음")
        except ValueError as exc:
            check(f"⑦ 빈 {label} 구간을 거절한다", "train_and_predict",
                  (True, True), (f"{label} 구간" in str(exc), "표본이 없습니다" in str(exc)),
                  f"  ({exc})")


def _params(train_start: str, train_end: str, test_start: str, test_end: str):
    """`normalized` 가 유일한 생성 경로다 (`services/backtest.py:188`).

    구간 넷 말고는 `check_period` 가 보지 않으므로 나머지는 화면 기본값으로 채운다.
    """
    return backtest_service.RunParams.normalized(
        ticker="005380.KS", name="현대차",
        train_start=train_start, train_end=train_end,
        test_start=test_start, test_end=test_end,
        initial_cash=10_000_000,
        commission_rate=hd_core.DEFAULT_COMMISSION_RATE,
        sell_tax_rate=hd_core.DEFAULT_SELL_TAX_RATE,
        slippage_rate=hd_core.DEFAULT_SLIPPAGE_RATE,
        warmup_days=120,
    )


def verify_check_period() -> None:
    """테스트-계획 2-7 — 겹침 거절. 판정은 `services/backtest.check_period` 에 있다."""
    params = _params("2024-01-01", "2025-12-31", "2025-06-01", "2026-01-31")
    try:
        backtest_service.check_period(params)
        check("⑦ 겹치는 구간을 거절한다", "check_period", "BacktestInputError", "없음")
    except backtest_service.BacktestInputError as exc:
        message = str(exc)
        check("⑦ 겹치는 구간을 거절한다", "check_period", True, "겹칩니다" in message)
        # R-06 이 요구한 "이해하기 쉬운 안내" — 무엇이·왜·어떻게가 한 문장에 있어야 한다
        # (테스트-계획 3.2절이 이 문구를 모범으로 지목했다).
        check("⑦ 거절 문구가 무엇·왜·어떻게를 말한다", "check_period",
              (True, True, True),
              ("겹칩니다" in message,
               "out-of-sample" in message,
               "학습 종료일 뒤로" in message))

    ok_params = _params("2024-01-01", "2025-05-31", "2025-06-01", "2025-12-31")
    try:
        backtest_service.check_period(ok_params)
        check("⑦ 겹치지 않으면 통과한다", "check_period", True, True)
    except backtest_service.BacktestInputError as exc:
        check("⑦ 겹치지 않으면 통과한다", "check_period", True, False, f"  ({exc})")


# ─────────────────────────────────────────────────────────────────────────────
# ⑧ 평가 — naive 기준선이 실제로 기준선인가
# ─────────────────────────────────────────────────────────────────────────────

def verify_metrics(run) -> None:
    metrics = run.metrics
    check("⑧ 표본 수가 예측 행 수와 같다", "evaluate_predictions",
          len(run.rows), metrics.n_samples)

    actual = np.array([r["actual_ret"] for r in run.rows])
    predicted = np.array([r["pred_ret"] for r in run.rows])

    check("⑧ naive MAE 는 '수익률 0' 가정", "evaluate_predictions",
          float(np.mean(np.abs(actual))), metrics.naive_mae_return)
    check("⑧ beats_naive_mae 는 두 값의 대소", "evaluate_predictions",
          metrics.mae_return < metrics.naive_mae_return, metrics.beats_naive_mae)

    hits = float(np.mean((actual > 0) == (predicted > 0)) * 100)
    check("⑧ 방향 정확도", "evaluate_predictions", hits, metrics.direction_accuracy)

    # naive 방향 기준선은 "항상 상승" 다수결이라 **50% 아래로 내려갈 수 없다.**
    check("⑧ naive 방향 기준선이 50% 이상", "evaluate_predictions", True,
          metrics.naive_direction_accuracy >= 50.0,
          f"  ({metrics.naive_direction_accuracy:.1f}%)")

    empty = hd_core.evaluate_predictions(np.array([]), np.array([]), np.array([]))
    check("⑧ 빈 입력은 0 으로 돌려준다", "evaluate_predictions", 0, empty.n_samples)


def main() -> int:
    verify_engine()
    verify_no_lookahead()
    verify_target_is_next_day()
    run = verify_leak_guard()
    verify_split(run)
    verify_reproducible(run)
    verify_empty_windows()
    verify_check_period()
    verify_metrics(run)

    width = max(len(name) for name, *_ in results)
    print()
    print(f"구간 — 학습 {TRAIN_START}~{TRAIN_END} · 검증 {TEST_START}~{TEST_END}")
    print(f"표본 — 피처 완비 {len(READY)}행 · 학습 {run.train_size} · 검증 {len(run.rows)}")
    for name, where, expected, got, ok in results:
        print(f"[{'OK ' if ok else 'FAIL'}] {name:<{width}}  {where}")
        if not ok:
            print(f"        기대: {expected}")
            print(f"        실측: {got}")

    passed = sum(1 for *_, ok in results if ok)
    print(f"\n{passed} / {len(results)} 통과")
    return 0 if passed == len(results) else 1


if __name__ == "__main__":
    raise SystemExit(main())
