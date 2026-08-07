"""예측 결과 + LEAN 백테스트 결과 → 자체완결 HTML 리포트.

표준 라이브러리만 씁니다. 차트는 인라인 SVG 로 직접 그리므로 matplotlib 도,
CDN 도 필요 없습니다. 만들어진 HTML 파일 하나만 있으면 어디서든 열립니다.
"""

from __future__ import annotations

import argparse
import csv
import html
import json
import math
from datetime import datetime, timezone, timedelta
from pathlib import Path

KST = timezone(timedelta(hours=9))

# 계열 색. 라이트/다크 양쪽에서 읽히는 값으로 골랐습니다.
COLOR_ACTUAL = "#0f766e"
COLOR_PRED = "#c2410c"
COLOR_STRATEGY = "#1d4ed8"
COLOR_BENCH = "#94a3b8"
COLOR_POS = "#059669"
COLOR_NEG = "#dc2626"


# ---------------------------------------------------------------------------
# 포맷 도우미
# ---------------------------------------------------------------------------


def won(value: float, digits: int = 0) -> str:
    return f"{value:,.{digits}f}원"


def pct(value: float, digits: int = 2, sign: bool = False) -> str:
    return f"{value:+.{digits}f}%" if sign else f"{value:.{digits}f}%"


def esc(value: object) -> str:
    return html.escape(str(value))


def verdict_class(good: bool) -> str:
    return "good" if good else "bad"


# ---------------------------------------------------------------------------
# SVG 차트
# ---------------------------------------------------------------------------


def _nice_bounds(low: float, high: float) -> tuple[float, float]:
    if math.isclose(low, high):
        pad = abs(low) * 0.05 or 1.0
        return low - pad, high + pad
    pad = (high - low) * 0.08
    return low - pad, high + pad


def line_chart(
    labels: list[str],
    series: list[dict],
    *,
    height: int = 300,
    width: int = 960,
    y_format: str = "number",
    title: str = "",
) -> str:
    """여러 계열을 겹쳐 그리는 라인 차트.

    series 원소: {"name": 표시명, "color": 색, "values": [float, ...]}
    values 길이는 labels 와 같아야 합니다.
    """
    if not labels or not series:
        return '<p class="empty">표시할 데이터가 없습니다.</p>'

    pad_left, pad_right, pad_top, pad_bottom = 78, 18, 16, 34
    plot_w = width - pad_left - pad_right
    plot_h = height - pad_top - pad_bottom

    flat = [v for s in series for v in s["values"] if v is not None]
    if not flat:
        return '<p class="empty">표시할 데이터가 없습니다.</p>'
    low, high = _nice_bounds(min(flat), max(flat))
    span = high - low or 1.0
    count = len(labels)

    def x_of(index: int) -> float:
        return pad_left + (plot_w * index / max(count - 1, 1))

    def y_of(value: float) -> float:
        return pad_top + plot_h * (1 - (value - low) / span)

    parts: list[str] = [
        f'<svg class="chart" viewBox="0 0 {width} {height}" role="img" '
        f'preserveAspectRatio="xMidYMid meet" aria-label="{esc(title or "차트")}">'
    ]

    # 가로 눈금선 5개와 y축 라벨
    for step in range(5):
        value = low + span * step / 4
        y = y_of(value)
        parts.append(f'<line class="grid" x1="{pad_left}" y1="{y:.1f}" x2="{width - pad_right}" y2="{y:.1f}"/>')
        if y_format == "won":
            text = f"{value:,.0f}"
        elif y_format == "pct":
            text = f"{value:.1f}%"
        elif y_format == "eok":
            text = f"{value / 100_000_000:.3f}억"
        else:
            text = f"{value:,.3f}"
        parts.append(
            f'<text class="tick" x="{pad_left - 8}" y="{y + 4:.1f}" text-anchor="end">{esc(text)}</text>'
        )

    # x축 날짜 라벨 (최대 7개)
    tick_count = min(7, count)
    for step in range(tick_count):
        index = round((count - 1) * step / max(tick_count - 1, 1))
        x = x_of(index)
        parts.append(
            f'<text class="tick" x="{x:.1f}" y="{height - 12}" text-anchor="middle">{esc(labels[index])}</text>'
        )

    for entry in series:
        points = " ".join(
            f"{x_of(index):.1f},{y_of(value):.1f}"
            for index, value in enumerate(entry["values"])
            if value is not None
        )
        dash = ' stroke-dasharray="5 4"' if entry.get("dashed") else ""
        parts.append(
            f'<polyline fill="none" stroke="{entry["color"]}" stroke-width="2" '
            f'stroke-linejoin="round" stroke-linecap="round"{dash} points="{points}"/>'
        )

    parts.append("</svg>")

    legend = " ".join(
        f'<span class="legend-item"><i style="background:{entry["color"]}"></i>{esc(entry["name"])}</span>'
        for entry in series
    )
    return f'<div class="chart-wrap">{"".join(parts)}</div><div class="legend">{legend}</div>'


def bar_chart(
    labels: list[str],
    values: list[float],
    *,
    height: int = 260,
    width: int = 960,
    color: str = COLOR_STRATEGY,
    diverging: bool = False,
    value_format: str = "{:.4f}",
) -> str:
    """가로 막대 차트(피처 중요도·오차 분포용)."""
    if not labels:
        return '<p class="empty">표시할 데이터가 없습니다.</p>'

    pad_left, pad_right, pad_top, pad_bottom = 130, 70, 10, 24
    plot_w = width - pad_left - pad_right
    row_h = max(18, (height - pad_top - pad_bottom) / len(labels))
    height = int(pad_top + pad_bottom + row_h * len(labels))

    peak = max(abs(v) for v in values) or 1.0
    parts = [
        f'<svg class="chart" viewBox="0 0 {width} {height}" role="img" '
        f'preserveAspectRatio="xMidYMid meet" aria-label="막대 차트">'
    ]
    for index, (label, value) in enumerate(zip(labels, values)):
        y = pad_top + row_h * index + row_h * 0.15
        bar_h = row_h * 0.7
        length = plot_w * abs(value) / peak
        fill = color
        if diverging:
            fill = COLOR_POS if value >= 0 else COLOR_NEG
        parts.append(
            f'<rect x="{pad_left}" y="{y:.1f}" width="{length:.1f}" height="{bar_h:.1f}" rx="2" fill="{fill}" opacity="0.85"/>'
        )
        parts.append(
            f'<text class="tick" x="{pad_left - 8}" y="{y + bar_h * 0.72:.1f}" text-anchor="end">{esc(label)}</text>'
        )
        parts.append(
            f'<text class="tick" x="{pad_left + length + 6:.1f}" y="{y + bar_h * 0.72:.1f}">'
            f"{esc(value_format.format(value))}</text>"
        )
    parts.append("</svg>")
    return f'<div class="chart-wrap">{"".join(parts)}</div>'


def histogram(values: list[float], *, bins: int = 21, width: int = 960, height: int = 240) -> str:
    """예측 오차 분포. 0 근처에 몰려 있고 좌우 대칭이면 편향이 없다는 뜻입니다."""
    if not values:
        return '<p class="empty">표시할 데이터가 없습니다.</p>'

    low, high = min(values), max(values)
    if math.isclose(low, high):
        low, high = low - 0.01, high + 0.01
    step = (high - low) / bins
    counts = [0] * bins
    for value in values:
        index = min(bins - 1, int((value - low) / step))
        counts[index] += 1

    pad_left, pad_right, pad_top, pad_bottom = 48, 18, 14, 34
    plot_w = width - pad_left - pad_right
    plot_h = height - pad_top - pad_bottom
    peak = max(counts) or 1
    bar_w = plot_w / bins

    parts = [
        f'<svg class="chart" viewBox="0 0 {width} {height}" role="img" '
        f'preserveAspectRatio="xMidYMid meet" aria-label="예측 오차 분포">'
    ]
    for index, count in enumerate(counts):
        bar_h = plot_h * count / peak
        x = pad_left + bar_w * index
        y = pad_top + plot_h - bar_h
        center = low + step * (index + 0.5)
        fill = COLOR_POS if center >= 0 else COLOR_NEG
        parts.append(
            f'<rect x="{x + 1:.1f}" y="{y:.1f}" width="{bar_w - 2:.1f}" height="{bar_h:.1f}" fill="{fill}" opacity="0.7"/>'
        )

    # 0 기준선
    if low < 0 < high:
        zero_x = pad_left + plot_w * (0 - low) / (high - low)
        parts.append(
            f'<line class="zero" x1="{zero_x:.1f}" y1="{pad_top}" x2="{zero_x:.1f}" y2="{pad_top + plot_h}"/>'
        )
        parts.append(
            f'<text class="tick" x="{zero_x:.1f}" y="{height - 12}" text-anchor="middle">0</text>'
        )
    parts.append(
        f'<text class="tick" x="{pad_left}" y="{height - 12}">{low * 100:.2f}%</text>'
        f'<text class="tick" x="{width - pad_right}" y="{height - 12}" text-anchor="end">{high * 100:.2f}%</text>'
    )
    parts.append("</svg>")
    return f'<div class="chart-wrap">{"".join(parts)}</div>'


# ---------------------------------------------------------------------------
# LEAN 결과 읽기
# ---------------------------------------------------------------------------


def read_lean_results(results_dir: Path, algo: str = "HyundaiMLStrategy") -> dict:
    """LEAN 산출물에서 통계 · 자산곡선 · 주문내역을 뽑습니다.

    LEAN 이 아직 안 돌았거나 실패했을 수도 있으므로, 없으면 빈 값을 돌려주고
    리포트는 예측 부분만으로 계속 만듭니다.
    """
    out: dict = {"available": False, "statistics": {}, "equity": [], "orders": [], "runtime": {}}

    summary = results_dir / f"{algo}-summary.json"
    full = results_dir / f"{algo}.json"
    source = full if full.exists() else summary
    if source.exists():
        try:
            payload = json.loads(source.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            payload = {}
        out["statistics"] = payload.get("statistics", {}) or {}
        out["runtime"] = payload.get("runtimeStatistics", {}) or {}

        charts = payload.get("charts", {}) or {}
        equity_series = ((charts.get("Strategy Equity") or {}).get("series") or {}).get("Equity") or {}
        for point in equity_series.get("values", []) or []:
            if not point:
                continue
            timestamp = point[0]
            # 캔들 형식([t,o,h,l,c])이면 종가를, 라인 형식([t,v])이면 그 값을 씁니다.
            value = point[4] if len(point) >= 5 else point[-1]
            if value is None:
                continue
            out["equity"].append(
                (datetime.fromtimestamp(timestamp, timezone.utc).date().isoformat(), float(value))
            )
        out["available"] = bool(out["statistics"])

    orders_csv = results_dir / "orders.csv"
    if orders_csv.exists():
        try:
            with orders_csv.open(newline="", encoding="utf-8") as file:
                for row in csv.reader(file):
                    if len(row) >= 5:
                        out["orders"].append(row)
        except OSError:
            pass

    return out


# ---------------------------------------------------------------------------
# HTML 조립
# ---------------------------------------------------------------------------

STYLE = """
:root{
  --bg:#f8fafc; --panel:#ffffff; --ink:#0f172a; --muted:#64748b; --line:#e2e8f0;
  --good:#047857; --good-bg:#ecfdf5; --bad:#b91c1c; --bad-bg:#fef2f2;
  --warn:#a16207; --warn-bg:#fefce8; --accent:#1d4ed8;
}
@media (prefers-color-scheme: dark){
  :root{
    --bg:#0b1220; --panel:#111a2e; --ink:#e6edf7; --muted:#93a4bd; --line:#22304b;
    --good:#34d399; --good-bg:#052e26; --bad:#f87171; --bad-bg:#3f1414;
    --warn:#fbbf24; --warn-bg:#3a2d05; --accent:#7aa2ff;
  }
}
*{box-sizing:border-box}
body{margin:0;background:var(--bg);color:var(--ink);
  font:15px/1.65 -apple-system,BlinkMacSystemFont,"Pretendard","Malgun Gothic","Apple SD Gothic Neo",sans-serif;}
.page{max-width:1080px;margin:0 auto;padding:32px 20px 80px}
h1{font-size:26px;margin:0 0 6px;letter-spacing:-.02em}
h2{font-size:20px;margin:44px 0 6px;padding-top:20px;border-top:1px solid var(--line);letter-spacing:-.01em}
h3{font-size:16px;margin:26px 0 8px}
p{margin:8px 0}
.sub{color:var(--muted);font-size:14px;margin:0 0 20px}
.panel{background:var(--panel);border:1px solid var(--line);border-radius:12px;padding:18px 20px;margin:14px 0}
.note{font-size:13.5px;color:var(--muted)}
.banner{border-radius:12px;padding:16px 20px;margin:18px 0;border:1px solid transparent}
.banner.good{background:var(--good-bg);border-color:var(--good);color:var(--good)}
.banner.bad{background:var(--bad-bg);border-color:var(--bad);color:var(--bad)}
.banner.warn{background:var(--warn-bg);border-color:var(--warn);color:var(--warn)}
.banner strong{display:block;font-size:17px;margin-bottom:4px}
.banner .detail{color:var(--ink);font-size:14px;opacity:.85}
.cards{display:grid;grid-template-columns:repeat(auto-fit,minmax(178px,1fr));gap:12px;margin:14px 0}
.card{background:var(--panel);border:1px solid var(--line);border-radius:10px;padding:14px 16px}
.card .label{font-size:12.5px;color:var(--muted);display:block;margin-bottom:6px}
.card .value{font-size:23px;font-weight:650;letter-spacing:-.02em;font-variant-numeric:tabular-nums}
.card .foot{font-size:12px;color:var(--muted);margin-top:4px}
.value.good{color:var(--good)} .value.bad{color:var(--bad)}
.table-wrap{overflow-x:auto;margin:12px 0}
table{border-collapse:collapse;width:100%;font-size:14px;min-width:520px}
th,td{padding:9px 12px;border-bottom:1px solid var(--line);text-align:right;font-variant-numeric:tabular-nums;white-space:nowrap}
th:first-child,td:first-child{text-align:left}
thead th{background:color-mix(in srgb,var(--panel) 60%,var(--line));font-weight:600;color:var(--muted);font-size:13px}
tbody tr:hover{background:color-mix(in srgb,var(--panel) 70%,var(--line))}
td.good{color:var(--good)} td.bad{color:var(--bad)}
.chart-wrap{overflow-x:auto;margin:10px 0}
svg.chart{display:block;width:100%;min-width:620px;height:auto}
svg .grid{stroke:var(--line);stroke-width:1}
svg .zero{stroke:var(--muted);stroke-width:1;stroke-dasharray:4 3}
svg .tick{fill:var(--muted);font-size:11px}
.legend{display:flex;gap:16px;flex-wrap:wrap;font-size:13px;color:var(--muted);margin:2px 0 4px}
.legend-item{display:flex;align-items:center;gap:6px}
.legend-item i{width:14px;height:3px;border-radius:2px;display:inline-block}
ul{margin:8px 0;padding-left:20px} li{margin:4px 0}
code{background:color-mix(in srgb,var(--panel) 50%,var(--line));padding:1px 5px;border-radius:4px;font-size:13px}
footer{margin-top:48px;padding-top:16px;border-top:1px solid var(--line);color:var(--muted);font-size:13px}
"""


def card(label: str, value: str, foot: str = "", tone: str = "") -> str:
    tone_class = f" {tone}" if tone else ""
    foot_html = f'<div class="foot">{esc(foot)}</div>' if foot else ""
    return (
        f'<div class="card"><span class="label">{esc(label)}</span>'
        f'<div class="value{tone_class}">{esc(value)}</div>{foot_html}</div>'
    )


def table(headers: list[str], rows: list[list[str]], *, raw_cells: bool = False) -> str:
    head = "".join(f"<th>{esc(h)}</th>" for h in headers)
    body = []
    for row in rows:
        cells = "".join(cell if raw_cells else f"<td>{esc(cell)}</td>" for cell in row)
        body.append(f"<tr>{cells}</tr>")
    return (
        f'<div class="table-wrap"><table><thead><tr>{head}</tr></thead>'
        f'<tbody>{"".join(body)}</tbody></table></div>'
    )


def build_report(prediction: dict, lean: dict) -> str:
    meta = prediction["meta"]
    metrics = prediction["prediction_metrics"]
    rows = prediction["rows"]
    simple = prediction["simple_backtest"]
    strategy = simple["strategy"]
    benchmark = simple["benchmark"]
    costs = simple["cost_assumptions"]

    name = meta["name"]
    ticker = meta["ticker"]
    generated = datetime.now(KST).strftime("%Y-%m-%d %H:%M KST")

    dates = [row["target_date"] for row in rows]
    actual_close = [row["actual_next_close"] for row in rows]
    pred_close = [row["pred_next_close"] for row in rows]
    errors = [row["pred_ret"] - row["actual_ret"] for row in rows]

    beats_dir = metrics["beats_naive_direction"]
    beats_mae = metrics["beats_naive_mae"]
    excess = simple["excess_return_pct"]

    # ---- 판정 배너 -------------------------------------------------------
    if beats_dir and beats_mae:
        banner_tone, banner_head = "good", "모델이 기준선을 양쪽 지표에서 앞섰습니다"
    elif beats_dir or beats_mae:
        banner_tone, banner_head = "warn", "모델이 기준선을 한쪽 지표에서만 앞섰습니다"
    else:
        banner_tone, banner_head = "bad", "모델이 기준선을 이기지 못했습니다"

    banner_detail = (
        f"방향 적중률 {pct(metrics['direction_accuracy'])} vs 기준선 {pct(metrics['naive_direction_accuracy'])} · "
        f"수익률 MAE {metrics['mae_return']:.5f} vs 기준선 {metrics['naive_mae_return']:.5f} · "
        f"naive 대비 R² {metrics['r2_vs_naive']:+.4f}"
    )

    # ---- 국면 변화 -------------------------------------------------------
    regime = prediction.get("regime") or {}
    train_regime, test_regime = regime.get("train") or {}, regime.get("test") or {}
    regime_html = ""
    if train_regime and test_regime:
        ratio = regime.get("volatility_ratio", 0.0)
        shifted = ratio >= 1.5 or ratio <= 0.67
        regime_html = f"""
<div class="panel">
  <h3 style="margin-top:0">학습 구간과 검증 구간의 성격 비교</h3>
  {table(
      ["구간", "기간", "거래일", "일평균 절대등락", "연환산 변동성", "구간 수익률"],
      [
          ["학습 (2025)", f"{train_regime['start']} ~ {train_regime['end']}", f"{train_regime['days']}일",
           pct(train_regime["mean_abs_move_pct"]), pct(train_regime["annual_volatility_pct"]),
           pct(train_regime["period_return_pct"], sign=True)],
          ["검증 (2026 H1)", f"{test_regime['start']} ~ {test_regime['end']}", f"{test_regime['days']}일",
           pct(test_regime["mean_abs_move_pct"]), pct(test_regime["annual_volatility_pct"]),
           pct(test_regime["period_return_pct"], sign=True)],
      ],
  )}
  <p class="note">검증 구간의 일평균 등락이 학습 구간의 <strong>{ratio:.2f}배</strong>입니다.
  {'<strong>국면이 바뀌었습니다.</strong> 모델은 조용한 장에서 배운 패턴을 완전히 다른 변동성의 장에 적용하고 있습니다. 예측이 빗나가는 가장 흔한 원인이 이것이고, 모델 구조를 바꿔서 해결되는 문제가 아닙니다.'
   if shifted else '두 구간의 변동성이 비슷해 학습한 패턴이 적용될 여지가 있습니다.'}</p>
</div>
"""

    # ---- 1부: 예측 정확도 ------------------------------------------------
    accuracy_cards = "".join(
        [
            card(
                "방향 적중률",
                pct(metrics["direction_accuracy"]),
                f"기준선(다수결) {pct(metrics['naive_direction_accuracy'])}",
                verdict_class(beats_dir),
            ),
            card(
                "가격 MAE",
                won(metrics["mae_price"]),
                f"기준선 {won(metrics['naive_mae_price'])}",
                verdict_class(metrics["mae_price"] < metrics["naive_mae_price"]),
            ),
            card("가격 MAPE", pct(metrics["mape_price"]), "실제 종가 대비 평균 오차율"),
            card(
                "naive 대비 R²",
                f"{metrics['r2_vs_naive']:+.4f}",
                "0보다 커야 기준선보다 나음",
                verdict_class(metrics["r2_vs_naive"] > 0),
            ),
            card("검증 표본", f"{metrics['n_samples']}일", f"학습 {meta['train_samples']}일"),
        ]
    )

    accuracy_table = table(
        ["지표", "모델", "기준선(랜덤워크)", "판정"],
        [
            [
                "수익률 MAE",
                f"{metrics['mae_return']:.5f}",
                f"{metrics['naive_mae_return']:.5f}",
                "모델 우세" if beats_mae else "기준선 우세",
            ],
            [
                "수익률 RMSE",
                f"{metrics['rmse_return']:.5f}",
                f"{metrics['naive_rmse_return']:.5f}",
                "모델 우세"
                if metrics["rmse_return"] < metrics["naive_rmse_return"]
                else "기준선 우세",
            ],
            [
                "가격 MAE",
                won(metrics["mae_price"]),
                won(metrics["naive_mae_price"]),
                "모델 우세"
                if metrics["mae_price"] < metrics["naive_mae_price"]
                else "기준선 우세",
            ],
            [
                "방향 적중률",
                pct(metrics["direction_accuracy"]),
                pct(metrics["naive_direction_accuracy"]),
                "모델 우세" if beats_dir else "기준선 우세",
            ],
        ],
    )

    importance = prediction.get("feature_importance") or {}
    if importance:
        ordered = sorted(importance.items(), key=lambda item: abs(item[1]), reverse=True)
        importance_html = (
            "<h3>피처 중요도 (permutation importance, 검증 구간)</h3>"
            + bar_chart(
                [k for k, _ in ordered],
                [v for _, v in ordered],
                diverging=True,
                value_format="{:+.5f}",
            )
            + '<p class="note">값이 0 이하인 피처는 섞어도 성능이 나빠지지 않았다는 뜻 — '
            "즉 모델이 실질적으로 쓰지 않은 피처입니다.</p>"
        )
    else:
        importance_html = ""

    # ---- 2부: 매매 성과 --------------------------------------------------
    simple_curve = simple["curve"]
    equity_series = [
        {"name": "예측 신호 전략 (간이)", "color": COLOR_STRATEGY, "values": [p["strategy"] for p in simple_curve]},
        {"name": "매수·보유", "color": COLOR_BENCH, "values": [p["benchmark"] for p in simple_curve]},
    ]

    lean_stats = lean["statistics"]
    if lean["available"] and lean["equity"]:
        # LEAN 자산곡선을 간이 곡선과 같은 날짜 축에 맞춥니다.
        lean_map = dict(lean["equity"])
        aligned: list[float | None] = []
        last: float | None = None
        for point in simple_curve:
            last = lean_map.get(point["date"], last)
            aligned.append(last)
        if any(value is not None for value in aligned):
            equity_series.insert(
                0,
                {"name": "예측 신호 전략 (LEAN 실행)", "color": COLOR_ACTUAL, "values": aligned},
            )

    performance_cards = "".join(
        [
            card(
                "전략 누적수익 (간이)",
                pct(strategy["total_return_pct"], sign=True),
                won(strategy["end_equity"]),
                verdict_class(strategy["total_return_pct"] > 0),
            ),
            card(
                "매수·보유 누적수익",
                pct(benchmark["total_return_pct"], sign=True),
                won(benchmark["end_equity"]),
                verdict_class(benchmark["total_return_pct"] > 0),
            ),
            card(
                "초과수익",
                pct(excess, sign=True),
                "전략 − 매수·보유",
                verdict_class(excess > 0),
            ),
            card("전략 MDD", pct(strategy["max_drawdown_pct"]), f"매수·보유 {pct(benchmark['max_drawdown_pct'])}"),
            card("전략 샤프", f"{strategy['sharpe']:.3f}", f"매수·보유 {benchmark['sharpe']:.3f}"),
            card("진입 횟수", f"{strategy['trades']}회", f"보유일 비중 {pct(strategy['days_in_market_pct'], 1)}"),
        ]
    )

    performance_table = table(
        ["지표", "예측 신호 전략", "매수·보유"],
        [
            ["시작 자산", won(strategy["start_equity"]), won(benchmark["start_equity"])],
            ["종료 자산", won(strategy["end_equity"]), won(benchmark["end_equity"])],
            [
                "누적 수익률",
                pct(strategy["total_return_pct"], sign=True),
                pct(benchmark["total_return_pct"], sign=True),
            ],
            ["연환산 수익률", pct(strategy["cagr_pct"], sign=True), pct(benchmark["cagr_pct"], sign=True)],
            ["최대 낙폭(MDD)", pct(strategy["max_drawdown_pct"]), pct(benchmark["max_drawdown_pct"])],
            ["연환산 변동성", pct(strategy["volatility_pct"]), pct(benchmark["volatility_pct"])],
            ["샤프 지수", f"{strategy['sharpe']:.3f}", f"{benchmark['sharpe']:.3f}"],
            ["진입 횟수", f"{strategy['trades']}회", f"{benchmark['trades']}회"],
            ["보유일 비중", pct(strategy["days_in_market_pct"], 1), pct(benchmark["days_in_market_pct"], 1)],
            ["추정 거래비용", won(strategy["total_cost"]), won(benchmark["total_cost"])],
        ],
    )

    # ---- LEAN 실행 결과 --------------------------------------------------
    if lean["available"]:
        wanted = [
            "Total Orders", "Start Equity", "End Equity", "Net Profit",
            "Compounding Annual Return", "Drawdown", "Sharpe Ratio", "Sortino Ratio",
            "Win Rate", "Loss Rate", "Total Fees", "Portfolio Turnover",
        ]
        lean_rows = [[key, str(lean_stats[key])] for key in wanted if key in lean_stats]
        lean_html = table(["LEAN 통계", "값"], lean_rows)
        if lean["orders"]:
            header = lean["orders"][0]
            body = lean["orders"][1:]
            preview = body if len(body) <= 60 else body[:60]
            lean_html += "<h3>체결 내역</h3>" + table(header, [list(r) for r in preview])
            if len(body) > len(preview):
                lean_html += f'<p class="note">전체 {len(body)}건 중 앞 {len(preview)}건만 표시했습니다. 전체는 <code>orders.csv</code>에 있습니다.</p>'
        else:
            lean_html += '<p class="note">체결 내역이 비어 있습니다 — 신호가 한 번도 매수를 지시하지 않았을 수 있습니다.</p>'
        lean_html += (
            '<p class="note">LEAN 결과가 위 간이 백테스트와 조금 다를 수 있습니다. 간이 계산은 '
            "자본을 소수점까지 나눠 투입하지만, LEAN 은 <strong>정수 주 단위로만</strong> 체결하고 "
            "수수료·세금·슬리피지를 주문 단위로 계산하기 때문입니다. "
            "<strong>최종 성과의 정본은 LEAN 쪽</strong>입니다.</p>"
        )
    else:
        lean_html = (
            '<div class="banner warn"><strong>LEAN 백테스트 결과가 없습니다</strong>'
            '<div class="detail">예측·간이 백테스트 결과만으로 리포트를 만들었습니다. '
            "엔진 실행은 <code>docker compose -f docker-compose.hd.yaml run --rm hd-backtest</code> 로 수행합니다.</div></div>"
        )

    # ---- 일자별 표(앞 30건) ---------------------------------------------
    daily_rows = []
    for row in rows[:30]:
        hit = row["direction_hit"]
        daily_rows.append(
            [
                f'<td>{esc(row["target_date"])}</td>',
                f'<td>{row["actual_next_close"]:,.0f}</td>',
                f'<td>{row["pred_next_close"]:,.0f}</td>',
                f'<td class="{verdict_class(abs(row["pred_next_close"] - row["actual_next_close"]) < row["actual_next_close"] * 0.01)}">'
                f'{row["pred_next_close"] - row["actual_next_close"]:+,.0f}</td>',
                f'<td>{row["actual_ret"] * 100:+.2f}%</td>',
                f'<td>{row["pred_ret"] * 100:+.2f}%</td>',
                f'<td class="{verdict_class(hit)}">{"적중" if hit else "빗나감"}</td>',
                f'<td>{"보유" if row["signal"] else "현금"}</td>',
            ]
        )
    daily_table = table(
        ["일자", "실제 종가", "예측 종가", "오차", "실제 등락", "예측 등락", "방향", "포지션"],
        daily_rows,
        raw_cells=True,
    )

    return f"""<!doctype html>
<html lang="ko">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{esc(name)} 예측·백테스트 리포트 — {esc(meta['test_start'])}~{esc(meta['test_end'])}</title>
<style>{STYLE}</style>
</head>
<body>
<div class="page">

<h1>{esc(name)} ({esc(ticker)}) 예측 검증 리포트</h1>
<p class="sub">
  학습 {esc(meta['train_start'])} ~ {esc(meta['train_end'])} ({meta['train_samples']}일) &nbsp;→&nbsp;
  검증 {esc(meta['test_start'])} ~ {esc(meta['test_end'])} ({meta['test_samples']}일, out-of-sample) &nbsp;·&nbsp;
  {esc(meta['model'])} &nbsp;·&nbsp; 생성 {esc(generated)}
</p>

<div class="banner {banner_tone}">
  <strong>{esc(banner_head)}</strong>
  <div class="detail">{esc(banner_detail)}</div>
</div>

<div class="panel">
  <p class="note"><strong>이 리포트가 답하는 두 가지 질문</strong></p>
  <ul class="note">
    <li><strong>1부 — 예측이 맞았는가?</strong> 2025년만 보고 학습한 모델이 2026년 상반기 종가를 얼마나 맞혔는지.
        기준선은 "내일도 오늘 종가"라는 랜덤워크입니다.</li>
    <li><strong>2부 — 그래서 돈이 되는가?</strong> 그 예측대로 실제로 사고팔았을 때의 성과를,
        같은 기간 그냥 사서 들고 있었을 때와 비교합니다.</li>
  </ul>
  <p class="note">두 질문의 답은 자주 어긋납니다. 방향을 조금 더 맞혀도 수수료·세금에 먹혀 수익이 안 나거나,
     반대로 적중률이 낮아도 큰 상승 며칠을 잡아 수익이 나기도 합니다.</p>
</div>

{regime_html}

<h2>1부 · 예측이 맞았는가</h2>
<div class="cards">{accuracy_cards}</div>

<h3>예측 종가 vs 실제 종가</h3>
{line_chart(dates, [
    {"name": "실제 종가", "color": COLOR_ACTUAL, "values": actual_close},
    {"name": "예측 종가", "color": COLOR_PRED, "values": pred_close, "dashed": True},
], y_format="won", title="예측 종가 vs 실제 종가")}
<p class="note">두 선이 거의 겹쳐 보이는 것은 모델이 정확해서가 아닙니다.
   예측 종가 = 오늘 종가 × (1 + 예측 수익률) 인데 일간 수익률이 대개 ±2% 안이라,
   <strong>아무 예측이나 해도 전날 종가를 따라가면 겹쳐 보입니다.</strong>
   실제 판정은 위의 기준선 비교 표에서 하세요.</p>

<h3>모델 vs 기준선</h3>
{accuracy_table}

<h3>예측 오차 분포 (예측 수익률 − 실제 수익률)</h3>
{histogram(errors)}
<p class="note">0을 중심으로 좌우 대칭이면 편향이 없다는 뜻입니다.
   한쪽으로 쏠려 있으면 모델이 계속 상승(또는 하락)으로 치우쳐 찍고 있다는 신호입니다.</p>

{importance_html}

<h2>2부 · 그래서 돈이 되는가</h2>
<div class="cards">{performance_cards}</div>

<h3>자산 곡선</h3>
{line_chart(
    [point["date"] for point in simple_curve],
    equity_series,
    y_format="eok",
    title="자산 곡선",
)}

<h3>성과 비교</h3>
{performance_table}

<h3>LEAN 엔진 실행 결과</h3>
{lean_html}

<h2>3부 · 일자별 예측과 실제</h2>
{daily_table}
<p class="note">전체 {len(rows)}일 중 앞 30일만 표시했습니다. 전체 데이터는 <code>prediction.json</code>에 있습니다.</p>

<h2>4부 · 가정과 한계</h2>
<div class="panel">
  <h3 style="margin-top:0">비용 가정</h3>
  <ul>
    <li>위탁수수료 <strong>{costs['commission_rate'] * 100:.4f}%</strong> (편도) — 증권사·계좌 등급에 따라 다릅니다.</li>
    <li>매도세 <strong>{costs['sell_tax_rate'] * 100:.4f}%</strong> — 2025년 이후 코스피 기준(증권거래세 0% + 농어촌특별세 0.15%)으로
        잡은 <em>가정</em>입니다. 세율은 정책에 따라 바뀌므로 실행 전 확인하세요.</li>
    <li>슬리피지 <strong>{costs['slippage_rate'] * 100:.4f}%</strong> (편도) — 종가 체결 가정에 붙인 보수적 값입니다.</li>
    <li>초기 자본 <strong>{won(costs['initial_cash'])}</strong>.</li>
  </ul>

  <h3>구조적 한계 — 결과를 실제 투자 성과로 읽으면 안 되는 이유</h3>
  <ul>
    <li><strong>체결 가정이 낙관적입니다.</strong> 신호는 t일 종가가 확정돼야 나오는데, 체결도 t일 종가로 가정합니다.
        현실에서는 종가를 보고 나서 그 종가에 살 수 없습니다. 종가 동시호가에 걸어도 체결가는 달라집니다.</li>
    <li><strong>KRX 거래 캘린더를 쓰지 않습니다.</strong> 엔진 설정이 <code>force-exchange-always-open: true</code>라
        휴장일·거래정지·상·하한가 제한이 반영되지 않습니다.</li>
    <li><strong>배당이 빠져 있습니다.</strong> Yahoo 종가 기준이라 배당 재투자 수익이 매수·보유 쪽에서 누락됩니다.
        즉 매수·보유의 실제 성과는 여기 표시된 것보다 높습니다.</li>
    <li><strong>단일 종목·단일 구간입니다.</strong> 검증 표본이 {metrics['n_samples']}일뿐이라
        이 결과 하나로 모델의 우열을 결론짓기에는 통계적으로 부족합니다.</li>
    <li><strong>계좌 통화는 LEAN 기본값(USD)입니다.</strong> 환율 변환을 하지 않았으므로
        모든 금액은 <strong>원(KRW)으로 읽으시면 됩니다</strong> — 달러로 환산한 값이 아닙니다.</li>
    <li><strong>데이터 출처는 Yahoo Finance 비공식 엔드포인트</strong>입니다. 수정주가 처리 방식이
        공식 시세와 다를 수 있습니다.</li>
  </ul>

  <h3>선견(lookahead) 차단</h3>
  <ul>
    <li>모든 피처는 t일 종가까지 확정된 값만 씁니다.</li>
    <li>학습 표본에서 <strong>타깃 날짜가 검증 시작일 이후인 행을 제외</strong>했습니다.
        빼지 않으면 학습 마지막 행의 타깃(= 검증 첫날 수익률)이 새어 들어갑니다.</li>
    <li>검증 구간에서 모델을 재학습하지 않습니다 — {esc(meta['train_start'])}~{esc(meta['train_end'])} 로 한 번 적합한
        모델을 고정해 씁니다.</li>
  </ul>
</div>

<footer>
  {esc(name)} ({esc(ticker)}) · 시세 {meta['price_rows']}건 ({esc(meta['price_first'])} ~ {esc(meta['price_last'])}) ·
  생성 {esc(generated)}<br>
  학습·연구 목적 산출물입니다. 투자 판단의 근거로 쓰지 마세요.
</footer>

</div>
</body>
</html>
"""


def main() -> None:
    parser = argparse.ArgumentParser(description="예측·백테스트 HTML 리포트 생성기")
    parser.add_argument("--prediction", required=True, help="make_signals.py 가 만든 JSON")
    parser.add_argument("--lean-results", default="", help="LEAN 결과 폴더 (없으면 예측만으로 생성)")
    parser.add_argument("--algorithm", default="HyundaiMLStrategy")
    parser.add_argument("--output", required=True)
    args = parser.parse_args()

    prediction = json.loads(Path(args.prediction).read_text(encoding="utf-8"))
    lean = (
        read_lean_results(Path(args.lean_results), args.algorithm)
        if args.lean_results
        else {"available": False, "statistics": {}, "equity": [], "orders": [], "runtime": {}}
    )

    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(build_report(prediction, lean), encoding="utf-8")
    size_kb = output.stat().st_size / 1024
    print(f"리포트 생성: {output} ({size_kb:.0f}KB, LEAN 결과 {'포함' if lean['available'] else '없음'})")


if __name__ == "__main__":
    main()
