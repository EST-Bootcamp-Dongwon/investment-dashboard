"""산업 경쟁력 분석 — 도메인 계층.

[CN-065](../../../docs/spec/00-index/변경이력.md#cn-065) 분해 순서 ⑤~⑦.
`main.py` 에 있던 4개 라우트의 본문과 그것이 쓰던 헬퍼·상수를 그대로 옮겼다.
HTTP 를 모른다 — 실패는 `services/errors.DomainError` 로 올리고, 상태 코드로
번역하는 일은 `main.py` 의 예외 처리기 한 곳이 맡는다.

옮기면서 계산과 문구는 건드리지 않았다. 바뀐 것은 ⓐ 요청 모델 대신 키워드 인자를
받는 것과 ⓑ `HTTPException` → `DomainError` 둘뿐이다.
"""

from __future__ import annotations

import base64
import io

try:
    from .errors import DomainError
except ImportError:  # `uvicorn main:app` 를 app/backend 에서 실행하는 경우
    from services.errors import DomainError  # type: ignore

try:
    from ..charting import configure_matplotlib_korean_font
except ImportError:  # `uvicorn main:app` 를 app/backend 에서 실행하는 경우
    from charting import configure_matplotlib_korean_font  # type: ignore


SECTOR_LABELS = {
    "SOXX": "반도체 (SOXX)", "XLE": "에너지 (XLE)", "XLF": "금융 (XLF)",
    "XLV":  "헬스케어 (XLV)", "XLK": "기술 (XLK)",  "XLI": "산업재 (XLI)",
    "XLY":  "소비재경기 (XLY)","XLP": "소비재필수 (XLP)","XLB": "소재 (XLB)",
    "XLRE": "부동산 (XLRE)",  "XLU": "유틸리티 (XLU)","IBB": "바이오 (IBB)",
}


LIFECYCLE_DATA = {
    "도입기": {
        "idx": 0, "color": "#3b82f6",
        "chars": ["매출 낮음·손실 가능", "높은 R&D 비용", "선도자 이점 확보 기회"],
        "strategy": ["성장주 투자", "VC/초기 투자", "기술 모멘텀 추종"],
        "examples": ["양자컴퓨터", "뇌-컴퓨터 인터페이스", "핵융합"],
    },
    "성장기": {
        "idx": 1, "color": "#22c55e",
        "chars": ["매출 급증", "경쟁자 진입 시작", "규모의 경제 달성"],
        "strategy": ["성장주 비중 확대", "시장점유율 1위 기업 주목", "PEG 지표 활용"],
        "examples": ["AI 반도체", "전기차", "클라우드"],
    },
    "성숙기": {
        "idx": 2, "color": "#f59e0b",
        "chars": ["성장 둔화", "가격경쟁 심화", "배당·자사주 매입 증가"],
        "strategy": ["가치주·배당주 투자", "PER·PBR 저평가 선별", "FCF 중심 분석"],
        "examples": ["스마트폰", "자동차", "은행"],
    },
    "쇠퇴기": {
        "idx": 3, "color": "#ef4444",
        "chars": ["매출 감소", "구조조정·M&A", "대체재에 시장 잠식"],
        "strategy": ["Short 전략 고려", "방어주 비중 축소", "Exit 타이밍 관리"],
        "examples": ["인쇄매체", "유선전화", "DVD 렌탈"],
    },
}


def industry_porter(*, industry: str, scores: dict[str, float]) -> dict[str, object]:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    import matplotlib.gridspec as gridspec
    import numpy as np
    import io, base64
    configure_matplotlib_korean_font(plt)

    DARK, SURF, BORDER, TEXT, MUTED = "#0f172a","#1e293b","#334155","#e2e8f0","#64748b"
    ACCENT = "#3b82f6"
    C_HIGH  = "#ef4444"   # 위협 강함
    C_MED   = "#f59e0b"
    C_LOW   = "#22c55e"   # 위협 약함

    forces = list(scores.keys())
    values = [max(0.0, min(10.0, float(v))) for v in scores.values()]
    N = len(forces)

    def force_color(v):
        if v >= 7: return C_HIGH
        if v >= 4: return C_MED
        return C_LOW

    fig = plt.figure(figsize=(14, 8), facecolor=DARK)
    gs  = gridspec.GridSpec(1, 2, figure=fig, wspace=0.35,
                            left=0.05, right=0.97, top=0.88, bottom=0.1)

    # ── Panel 1: Radar (polar) ──────────────────────────────────────────────
    ax_r = fig.add_subplot(gs[0, 0], polar=True, facecolor=SURF)
    angles = [n / N * 2 * np.pi for n in range(N)]
    angles += angles[:1]
    vals_plot = values + values[:1]

    ax_r.set_theta_offset(np.pi / 2)
    ax_r.set_theta_direction(-1)
    ax_r.set_ylim(0, 10)
    ax_r.set_yticks([2, 4, 6, 8, 10])
    ax_r.set_yticklabels(["2","4","6","8","10"], color=MUTED, fontsize=7)
    ax_r.set_xticks(angles[:-1])
    ax_r.set_xticklabels(forces, color=TEXT, fontsize=9)
    ax_r.spines["polar"].set_color(BORDER)
    ax_r.tick_params(colors=MUTED)
    ax_r.grid(color=BORDER, linewidth=0.8)

    # 배경 zone 색칠 (위험 등급)
    for thresh, col in [(10, "#ef444411"), (7, "#f59e0b11"), (4, "#22c55e11")]:
        zone = [thresh] * N + [thresh]
        ax_r.fill(angles, zone, color=col)

    ax_r.plot(angles, vals_plot, color=ACCENT, lw=2.2, zorder=3)
    ax_r.fill(angles, vals_plot, color=ACCENT, alpha=0.25, zorder=2)
    for a, v in zip(angles[:-1], values):
        ax_r.plot(a, v, "o", color=force_color(v), ms=8, zorder=4)
        ax_r.text(a, v + 0.8, f"{v:.1f}", ha="center", va="center",
                  fontsize=8, color=TEXT, fontweight="bold")

    ax_r.set_title(f"Porter 5 Forces\n{industry} 산업",
                   color=TEXT, fontsize=11, fontweight="bold", pad=18)

    # ── Panel 2: 수평 바 + 해석 ─────────────────────────────────────────────
    ax_b = fig.add_subplot(gs[0, 1], facecolor=SURF)
    bars = ax_b.barh(forces, values, color=[force_color(v) for v in values],
                     height=0.5, zorder=2)
    ax_b.set_xlim(0, 10)
    ax_b.axvline(4, color=MUTED, lw=0.8, ls="--", alpha=0.5)
    ax_b.axvline(7, color=MUTED, lw=0.8, ls="--", alpha=0.5)
    ax_b.text(2, -0.8, "약함", ha="center", color=C_LOW, fontsize=8)
    ax_b.text(5.5, -0.8, "보통", ha="center", color=C_MED, fontsize=8)
    ax_b.text(8.5, -0.8, "강함", ha="center", color=C_HIGH, fontsize=8)

    INTERP = {
        "경쟁강도":      {(7,10):"경쟁사 많음 → 가격경쟁↑·수익성↓", (4,7):"과점 구조 → 안정적", (0,4):"독점적 지위"},
        "신규진입 위협": {(7,10):"진입장벽 낮음 → 점유율 위협", (4,7):"중간 진입장벽", (0,4):"특허·규제·규모 장벽↑"},
        "대체재 위협":   {(7,10):"대체재 다수 → 가격결정력↓", (4,7):"부분 대체 가능", (0,4):"대체재 없음"},
        "구매자 교섭력": {(7,10):"구매자 협상력↑ → 마진압박", (4,7):"균형 협상", (0,4):"공급자 우위"},
        "공급자 교섭력": {(7,10):"원재료 공급 불안정·비용↑", (4,7):"복수 공급선 확보", (0,4):"공급 안정"},
    }

    for i, (bar, force, val) in enumerate(zip(bars, forces, values)):
        ax_b.text(val + 0.15, bar.get_y() + bar.get_height()/2,
                  f"{val:.1f}", va="center", fontsize=9,
                  color=TEXT, fontweight="bold")
        for (lo, hi), msg in INTERP.get(force, {}).items():
            if lo <= val <= hi:
                ax_b.text(10.2, bar.get_y() + bar.get_height()/2,
                          msg, va="center", fontsize=7, color=MUTED)
                break

    ax_b.set_xlabel("위협 강도 (0 = 낮음, 10 = 높음)", color=MUTED, fontsize=8)
    ax_b.tick_params(colors=TEXT, labelsize=9)
    ax_b.spines[:].set_color(BORDER)
    ax_b.set_title("5 Forces 위협 강도 분석", color=TEXT, fontsize=11,
                   fontweight="bold", pad=10)
    ax_b.set_xlim(0, 16)   # 오른쪽 텍스트 공간

    # 종합 점수
    avg = sum(values) / N
    grade = "고위험" if avg >= 7 else "중위험" if avg >= 4 else "저위험"
    grade_col = C_HIGH if avg >= 7 else C_MED if avg >= 4 else C_LOW
    fig.suptitle(
        f"산업 경쟁력 분석  |  {industry}  |  종합 위협 지수: {avg:.1f}/10  [{grade}]",
        color=TEXT, fontsize=12, fontweight="bold", y=0.97)
    fig.text(0.5, 0.01,
             "■ 녹색: 약함(0-4)  ■ 주황: 보통(4-7)  ■ 빨강: 강함(7-10)",
             ha="center", fontsize=8, color=MUTED)

    buf = io.BytesIO()
    fig.savefig(buf, format="png", dpi=130, facecolor=DARK, bbox_inches="tight")
    plt.close(fig)
    buf.seek(0)
    img = "data:image/png;base64," + base64.b64encode(buf.read()).decode()

    result = {f: {"score": v, "level": "강함" if v>=7 else "보통" if v>=4 else "약함"}
              for f, v in zip(forces, values)}
    return {"image": img, "industry": industry,
            "avg_score": round(avg, 2), "grade": grade, "forces": result}


def industry_sector(*, tickers: list[str], period: str) -> dict[str, object]:
    import yfinance as yf
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    import matplotlib.gridspec as gridspec
    import numpy as np
    import pandas as pd
    import io, base64
    configure_matplotlib_korean_font(plt)

    DARK, SURF, BORDER, TEXT, MUTED = "#0f172a","#1e293b","#334155","#e2e8f0","#64748b"
    COLORS = ["#3b82f6","#22c55e","#f59e0b","#ef4444","#a855f7",
              "#06b6d4","#f97316","#84cc16","#ec4899","#14b8a6","#8b5cf6","#fb923c"]

    raw: dict[str, pd.Series] = {}
    for t in tickers:
        try:
            df = yf.download(t, period=period, progress=False, auto_adjust=True)
            if df.empty: continue
            s = df["Close"]
            if isinstance(s, pd.DataFrame): s = s.iloc[:, 0]
            s = s.dropna()
            if len(s) > 5: raw[t] = s
        except Exception:
            pass

    if not raw:
        raise DomainError(503, "데이터를 가져올 수 없습니다.")

    fig = plt.figure(figsize=(14, 10), facecolor=DARK)
    gs  = gridspec.GridSpec(2, 2, figure=fig, hspace=0.42, wspace=0.32,
                            left=0.07, right=0.97, top=0.92, bottom=0.07)

    # Panel 1: 정규화 수익률
    ax1 = fig.add_subplot(gs[0, :], facecolor=SURF)
    for i, (t, s) in enumerate(raw.items()):
        norm = (s / s.iloc[0] - 1) * 100
        ax1.plot(norm.index, norm.values, color=COLORS[i % len(COLORS)],
                 lw=1.8, label=SECTOR_LABELS.get(t, t))
    ax1.axhline(0, color=MUTED, lw=0.8, ls="--")
    ax1.set_title("섹터 ETF 정규화 누적 수익률 (%)", color=TEXT, fontsize=10, pad=6)
    ax1.tick_params(colors=TEXT, labelsize=7)
    ax1.spines[:].set_color(BORDER)
    ax1.legend(fontsize=7, facecolor=SURF, labelcolor=TEXT,
               ncol=4, loc="upper left", framealpha=0.7)
    ax1.tick_params(axis="x", rotation=30)
    for lbl in ax1.get_xticklabels(): lbl.set_fontsize(6)

    # Panel 2: 기간 수익률 바
    ax2 = fig.add_subplot(gs[1, 0], facecolor=SURF)
    names, returns, cols = [], [], []
    for i, (t, s) in enumerate(raw.items()):
        r = (s.iloc[-1] / s.iloc[0] - 1) * 100
        names.append(SECTOR_LABELS.get(t, t))
        returns.append(r)
        cols.append(COLORS[i % len(COLORS)])
    order = sorted(range(len(returns)), key=lambda x: returns[x], reverse=True)
    names_s  = [names[i] for i in order]
    returns_s = [returns[i] for i in order]
    cols_s   = [cols[i] for i in order]
    bars = ax2.barh(names_s, returns_s, color=cols_s, height=0.6)
    ax2.axvline(0, color=MUTED, lw=0.8)
    for bar, v in zip(bars, returns_s):
        ax2.text(v + (0.3 if v >= 0 else -0.3), bar.get_y() + bar.get_height()/2,
                 f"{v:+.1f}%", va="center", ha="left" if v >= 0 else "right",
                 fontsize=7, color=TEXT)
    ax2.set_title(f"기간 수익률 순위 ({period})", color=TEXT, fontsize=10, pad=6)
    ax2.tick_params(colors=TEXT, labelsize=7)
    ax2.spines[:].set_color(BORDER)

    # Panel 3: 변동성 vs 수익률 (리스크-리턴 산점도)
    ax3 = fig.add_subplot(gs[1, 1], facecolor=SURF)
    for i, (t, s) in enumerate(raw.items()):
        ret  = (s.iloc[-1] / s.iloc[0] - 1) * 100
        vol  = s.pct_change().std() * (252**0.5) * 100
        ax3.scatter(vol, ret, color=COLORS[i % len(COLORS)], s=100, zorder=3)
        ax3.text(vol + 0.3, ret, SECTOR_LABELS.get(t, t).split("(")[0].strip(),
                 fontsize=6.5, color=TEXT)
    ax3.axhline(0, color=MUTED, lw=0.8, ls="--")
    ax3.set_xlabel("연환산 변동성 (%)", color=MUTED, fontsize=8)
    ax3.set_ylabel(f"수익률 ({period}) %", color=MUTED, fontsize=8)
    ax3.set_title("리스크-리턴 산점도", color=TEXT, fontsize=10, pad=6)
    ax3.tick_params(colors=TEXT, labelsize=7)
    ax3.spines[:].set_color(BORDER)
    ax3.grid(color=BORDER, lw=0.5, alpha=0.5)

    fig.suptitle(f"섹터 주가 비교 분석  |  {period}",
                 color=TEXT, fontsize=12, fontweight="bold", y=0.97)

    buf = io.BytesIO()
    fig.savefig(buf, format="png", dpi=130, facecolor=DARK, bbox_inches="tight")
    plt.close(fig)
    buf.seek(0)
    img = "data:image/png;base64," + base64.b64encode(buf.read()).decode()

    summary = {}
    for t, s in raw.items():
        summary[SECTOR_LABELS.get(t, t)] = {
            "return_pct": round((s.iloc[-1]/s.iloc[0]-1)*100, 2),
            "annual_vol":  round(s.pct_change().std()*(252**0.5)*100, 2),
        }
    return {"image": img, "summary": summary}


def industry_peer(*, tickers: dict[str, str]) -> dict[str, object]:
    import math

    import yfinance as yf

    if not tickers:
        raise DomainError(400, "비교할 종목을 1개 이상 입력하세요.")
    if len(tickers) > 12:
        raise DomainError(400, "Peer Comparison은 최대 12개 종목까지 지원합니다.")

    def as_float(value):
        if value is None:
            return None
        try:
            number = float(value)
        except (TypeError, ValueError):
            return None
        if math.isnan(number) or math.isinf(number):
            return None
        return number

    rows: list[dict[str, object]] = []
    for name, ticker in tickers.items():
        label = (name or ticker).strip()[:40]
        symbol = (ticker or "").strip().upper()
        if not symbol:
            continue
        try:
            info = yf.Ticker(symbol).info
        except Exception as exc:
            rows.append({
                "company": label,
                "ticker": symbol,
                "error": f"데이터 수신 실패: {exc}",
            })
            continue

        market_cap = as_float(info.get("marketCap"))
        revenue_growth = as_float(info.get("revenueGrowth"))
        operating_margin = as_float(info.get("operatingMargins"))
        debt_to_equity = as_float(info.get("debtToEquity"))
        roe = as_float(info.get("returnOnEquity"))
        per = as_float(info.get("trailingPE"))
        pbr = as_float(info.get("priceToBook"))

        rows.append({
            "company": label,
            "ticker": symbol,
            "market_cap_krw_100m": round(market_cap / 1e8, 0) if market_cap is not None else None,
            "revenue_growth_pct": round(revenue_growth * 100, 1) if revenue_growth is not None else None,
            "operating_margin_pct": round(operating_margin * 100, 1) if operating_margin is not None else None,
            "per": round(per, 1) if per is not None else None,
            "pbr": round(pbr, 2) if pbr is not None else None,
            "debt_to_equity_pct": round(debt_to_equity, 1) if debt_to_equity is not None else None,
            "roe_pct": round(roe * 100, 1) if roe is not None else None,
            "currency": info.get("currency"),
            "sector": info.get("sector"),
        })

    if not rows:
        raise DomainError(400, "유효한 종목 코드가 없습니다.")

    valid_rows = [r for r in rows if not r.get("error")]
    leader = None
    if valid_rows:
        leader = max(
            valid_rows,
            key=lambda r: (
                r.get("operating_margin_pct") if r.get("operating_margin_pct") is not None else -999,
                r.get("roe_pct") if r.get("roe_pct") is not None else -999,
            ),
        ).get("company")

    return {
        "rows": rows,
        "leader": leader,
        "notes": [
            "동종 기업 여부를 먼저 확인한 뒤 멀티플 차이를 해석하세요.",
            "PER/PBR은 성장률, 수익성, 재무건전성과 함께 봐야 합니다.",
            "Yahoo Finance 항목 누락 시 일부 값은 빈칸으로 표시됩니다.",
        ],
    }


def industry_lifecycle(*, stage: str, industry: str) -> dict[str, object]:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    import matplotlib.patches as mpatches
    import numpy as np
    import io, base64
    configure_matplotlib_korean_font(plt)

    DARK, SURF, BORDER, TEXT, MUTED = "#0f172a","#1e293b","#334155","#e2e8f0","#64748b"

    stage_info = LIFECYCLE_DATA.get(stage, LIFECYCLE_DATA["성장기"])
    cur_idx    = stage_info["idx"]

    # S-curve (logistic)
    x = np.linspace(-6, 10, 400)
    y = 100 / (1 + np.exp(-x * 0.9))          # 도입~성숙
    decline = np.linspace(0, 1, 100)
    x_full  = np.concatenate([x, x[-1] + decline * 4])
    y_full  = np.concatenate([y, y[-1] - decline * 35])  # 쇠퇴

    # 각 단계 x 범위
    stage_x = [(-6, -1.5), (-1.5, 3), (3, 7), (7, x_full[-1])]
    stage_colors = [d["color"] for d in LIFECYCLE_DATA.values()]
    stage_names  = list(LIFECYCLE_DATA.keys())

    fig, (ax_main, ax_info) = plt.subplots(1, 2, figsize=(14, 7),
                                           gridspec_kw={"width_ratios": [3, 2]},
                                           facecolor=DARK)

    # ── 메인: S-curve ────────────────────────────────────────────────────────
    ax_main.set_facecolor(SURF)
    for i, ((x0, x1), col, name) in enumerate(zip(stage_x, stage_colors, stage_names)):
        mask = (x_full >= x0) & (x_full <= x1)
        alpha = 0.9 if i == cur_idx else 0.35
        lw    = 3.5 if i == cur_idx else 1.5
        ax_main.plot(x_full[mask], y_full[mask], color=col, lw=lw, alpha=alpha, zorder=3)
        mid_x = (x0 + x1) / 2
        mid_y = np.interp(mid_x, x_full, y_full)
        ax_main.text(mid_x, mid_y + (8 if i != 3 else -8), name,
                     ha="center", fontsize=10, color=col,
                     fontweight="bold" if i == cur_idx else "normal",
                     bbox=dict(boxstyle="round,pad=0.3",
                               facecolor=SURF if i != cur_idx else col + "33",
                               edgecolor=col, linewidth=1.5 if i == cur_idx else 0.8))
        # 단계 구분선
        if i < 3:
            ax_main.axvline(x1, color=BORDER, lw=1, ls=":", alpha=0.7)

    # 현재 위치 표시
    cur_x0, cur_x1 = stage_x[cur_idx]
    cur_mid = (cur_x0 + cur_x1) / 2
    cur_y   = np.interp(cur_mid, x_full, y_full)
    ax_main.scatter([cur_mid], [cur_y], color=stage_info["color"],
                    s=200, zorder=5, edgecolors=TEXT, linewidths=1.5)
    ax_main.annotate(f"▶ {industry}\n({stage})",
                     xy=(cur_mid, cur_y), xytext=(cur_mid + 0.5, cur_y - 18),
                     fontsize=9, color=stage_info["color"], fontweight="bold",
                     arrowprops=dict(arrowstyle="->", color=stage_info["color"], lw=1.5))

    ax_main.set_xlabel("시간 →", color=MUTED, fontsize=10)
    ax_main.set_ylabel("시장 규모 / 매출", color=MUTED, fontsize=10)
    ax_main.set_title("산업 생애주기 (Industry Life Cycle)", color=TEXT,
                      fontsize=11, fontweight="bold", pad=10)
    ax_main.tick_params(colors=MUTED, labelsize=7)
    ax_main.set_xticklabels([])
    ax_main.spines[:].set_color(BORDER)
    ax_main.set_ylim(-5, 115)

    # ── 사이드: 단계별 특성표 ────────────────────────────────────────────────
    ax_info.set_facecolor(DARK)
    ax_info.axis("off")

    y_pos = 0.97
    ax_info.text(0.5, y_pos, f"{industry}  |  {stage}", ha="center",
                 fontsize=12, fontweight="bold", color=stage_info["color"],
                 transform=ax_info.transAxes)
    y_pos -= 0.08

    sections = [
        ("특징", stage_info["chars"], "#e2e8f0"),
        ("투자 전략", stage_info["strategy"], "#3b82f6"),
        ("예시 산업", stage_info["examples"], "#a855f7"),
    ]
    for title, items, col in sections:
        ax_info.text(0.05, y_pos, title, fontsize=9, fontweight="bold",
                     color=col, transform=ax_info.transAxes)
        y_pos -= 0.06
        for item in items:
            ax_info.text(0.08, y_pos, f"• {item}", fontsize=8.5, color=TEXT,
                         transform=ax_info.transAxes)
            y_pos -= 0.065
        y_pos -= 0.02

    # 4단계 요약 타임라인
    y_pos -= 0.02
    ax_info.text(0.5, y_pos, "── 4단계 흐름 ──", ha="center",
                 fontsize=8, color=MUTED, transform=ax_info.transAxes)
    y_pos -= 0.065
    for i, (name, data) in enumerate(LIFECYCLE_DATA.items()):
        marker = "●" if i == cur_idx else "○"
        weight = "bold" if i == cur_idx else "normal"
        ax_info.text(0.1 + i * 0.22, y_pos, f"{marker}\n{name}", ha="center",
                     fontsize=8, color=data["color"], fontweight=weight,
                     transform=ax_info.transAxes)

    fig.suptitle("산업 생애주기 분석  |  단계별 투자 전략",
                 color=TEXT, fontsize=12, fontweight="bold", y=0.99)

    buf = io.BytesIO()
    fig.savefig(buf, format="png", dpi=130, facecolor=DARK, bbox_inches="tight")
    plt.close(fig)
    buf.seek(0)
    img = "data:image/png;base64," + base64.b64encode(buf.read()).decode()

    return {"image": img, "stage": stage, "industry": industry,
            "characteristics": stage_info["chars"],
            "strategies": stage_info["strategy"]}
