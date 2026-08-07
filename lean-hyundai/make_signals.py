"""2025년으로 학습해 2026년 상반기를 예측하고, 신호 CSV와 평가 지표를 씁니다.

LEAN 백테스트가 시작되기 **전에** 실행됩니다. 산출물:

  signals.csv          LEAN Custom Data 입력 (Date · Close · PredReturn · Signal)
  prediction.json      예측 정확도 지표 + 일자별 예측/실제 + 간이 백테스트 결과
"""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path

import hd_core


def main() -> None:
    parser = argparse.ArgumentParser(description="예측 신호 생성기")
    parser.add_argument("--prices", required=True, help="일봉 CSV 경로")
    parser.add_argument("--signals-out", required=True)
    parser.add_argument("--json-out", required=True)
    parser.add_argument("--train-start", default=os.getenv("HD_TRAIN_START", "2025-01-01"))
    parser.add_argument("--train-end", default=os.getenv("HD_TRAIN_END", "2025-12-31"))
    parser.add_argument("--test-start", default=os.getenv("HD_TEST_START", "2026-01-01"))
    parser.add_argument("--test-end", default=os.getenv("HD_TEST_END", "2026-06-30"))
    parser.add_argument("--ticker", default=os.getenv("HD_TICKER", "005380.KS"))
    parser.add_argument("--name", default=os.getenv("HD_NAME", "현대차"))
    parser.add_argument(
        "--initial-cash", type=float, default=float(os.getenv("HD_INITIAL_CASH", "100000000"))
    )
    args = parser.parse_args()

    prices = hd_core.load_prices(args.prices)
    featured = hd_core.build_features(prices)
    run = hd_core.train_and_predict(
        featured,
        args.train_start,
        args.train_end,
        args.test_start,
        args.test_end,
    )

    signals_path = hd_core.write_signals_csv(run.rows, args.signals_out)
    backtest = hd_core.simple_backtest(run.rows, initial_cash=args.initial_cash)

    payload = {
        "meta": {
            "ticker": args.ticker,
            "name": args.name,
            "train_start": args.train_start,
            "train_end": args.train_end,
            "test_start": args.test_start,
            "test_end": args.test_end,
            "train_samples": run.train_size,
            "test_samples": len(run.rows),
            "model": "sklearn HistGradientBoostingRegressor",
            "features": hd_core.FEATURE_COLUMNS,
            "price_rows": int(len(prices)),
            "price_first": prices["Date"].iloc[0].date().isoformat(),
            "price_last": prices["Date"].iloc[-1].date().isoformat(),
        },
        "regime": hd_core.regime_summary(
            featured, args.train_start, args.train_end, args.test_start, args.test_end
        ),
        "prediction_metrics": run.metrics.to_dict(),
        "feature_importance": run.feature_importance,
        "rows": run.rows,
        "simple_backtest": backtest,
    }

    json_path = Path(args.json_out)
    json_path.parent.mkdir(parents=True, exist_ok=True)
    json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    metrics = run.metrics
    print(f"[신호 생성] 학습 {run.train_size}건 → 검증 {len(run.rows)}건")
    print(f"  방향 적중률 {metrics.direction_accuracy:.2f}% (기준선 {metrics.naive_direction_accuracy:.2f}%)")
    print(f"  수익률 MAE {metrics.mae_return:.5f} (기준선 {metrics.naive_mae_return:.5f})")
    print(f"  naive 대비 R² {metrics.r2_vs_naive:+.4f}")
    print(f"  간이 백테스트 전략 {backtest['strategy']['total_return_pct']:+.2f}% / "
          f"매수보유 {backtest['benchmark']['total_return_pct']:+.2f}%")
    print(f"  → {signals_path}, {json_path}")


if __name__ == "__main__":
    main()
