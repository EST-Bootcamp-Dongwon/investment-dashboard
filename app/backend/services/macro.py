"""거시 지표·지수 — 도메인 계층.

[CN-065](../../../docs/spec/00-index/변경이력.md#cn-065) 분해 순서 ⑤~⑦.
`main.py` 에 있던 4개 라우트의 본문과 그것이 쓰던 헬퍼·상수를 그대로 옮겼다.
HTTP 를 모른다 — 실패는 `services/errors.DomainError` 로 올리고, 상태 코드로
번역하는 일은 `main.py` 의 예외 처리기 한 곳이 맡는다.

옮기면서 계산과 문구는 건드리지 않았다. 바뀐 것은 ⓐ 요청 모델 대신 키워드 인자를
받는 것과 ⓑ `HTTPException` → `DomainError` 둘뿐이다.
"""

from __future__ import annotations

from datetime import datetime, timezone
import base64
import io

try:
    from .errors import DomainError
except ImportError:  # `uvicorn main:app` 를 app/backend 에서 실행하는 경우
    from services.errors import DomainError  # type: ignore

try:
    from .. import charting
except ImportError:  # `uvicorn main:app` 를 app/backend 에서 실행하는 경우
    import charting  # type: ignore

try:
    from ..clients.yahoo_prices import close_series
except ImportError:  # `uvicorn main:app` 를 app/backend 에서 실행하는 경우
    from clients.yahoo_prices import close_series  # type: ignore


TICKER_LABELS = {
    "^TNX":     "미국 10년물 금리",
    "CL=F":     "WTI 유가",
    "^GSPC":    "S&P 500",
    "^KS11":    "KOSPI",
    "GC=F":     "금 (Gold)",
    "EURUSD=X": "EUR/USD",
    "BTC-USD":  "Bitcoin",
    "^IRX":     "미국 단기금리(3M)",
    "^VIX":     "VIX 공포지수",
    "DX-Y.NYB": "달러 인덱스",
}

KOSPI_COMPONENTS = [
    {"ticker": "005930.KS", "name": "삼성전자",        "sector": "반도체",    "weight": 0.210},
    {"ticker": "000660.KS", "name": "SK하이닉스",      "sector": "반도체",    "weight": 0.075},
    {"ticker": "373220.KS", "name": "LG에너지솔루션",  "sector": "배터리",    "weight": 0.035},
    {"ticker": "207940.KS", "name": "삼성바이오로직스", "sector": "바이오",    "weight": 0.028},
    {"ticker": "005380.KS", "name": "현대차",          "sector": "자동차",    "weight": 0.025},
    {"ticker": "000270.KS", "name": "기아",            "sector": "자동차",    "weight": 0.022},
    {"ticker": "105560.KS", "name": "KB금융",          "sector": "금융",      "weight": 0.018},
    {"ticker": "035420.KS", "name": "NAVER",           "sector": "IT/플랫폼", "weight": 0.013},
    {"ticker": "055550.KS", "name": "신한지주",        "sector": "금융",      "weight": 0.015},
    {"ticker": "006400.KS", "name": "삼성SDI",         "sector": "배터리",    "weight": 0.012},
    {"ticker": "086790.KS", "name": "하나금융지주",    "sector": "금융",      "weight": 0.012},
    {"ticker": "012330.KS", "name": "현대모비스",      "sector": "자동차",    "weight": 0.009},
    {"ticker": "051910.KS", "name": "LG화학",          "sector": "화학",      "weight": 0.010},
    {"ticker": "032830.KS", "name": "삼성생명",        "sector": "금융",      "weight": 0.008},
    {"ticker": "035720.KS", "name": "카카오",          "sector": "IT/플랫폼", "weight": 0.008},
    {"ticker": "316140.KS", "name": "우리금융지주",    "sector": "금융",      "weight": 0.007},
    {"ticker": "068270.KS", "name": "셀트리온",        "sector": "바이오",    "weight": 0.010},
    {"ticker": "005490.KS", "name": "POSCO홀딩스",     "sector": "철강",      "weight": 0.015},
    {"ticker": "017670.KS", "name": "SK텔레콤",        "sector": "통신",      "weight": 0.010},
    {"ticker": "030200.KS", "name": "KT",              "sector": "통신",      "weight": 0.008},
    {"ticker": "018260.KS", "name": "삼성SDS",         "sector": "IT/플랫폼", "weight": 0.005},
    {"ticker": "096770.KS", "name": "SK이노베이션",    "sector": "에너지",    "weight": 0.006},
    {"ticker": "034730.KS", "name": "SK",              "sector": "에너지",    "weight": 0.006},
    {"ticker": "003550.KS", "name": "LG",              "sector": "지주회사",  "weight": 0.005},
    {"ticker": "090430.KS", "name": "아모레퍼시픽",    "sector": "소비재",    "weight": 0.004},
    {"ticker": "034220.KS", "name": "LG디스플레이",    "sector": "디스플레이","weight": 0.004},
    {"ticker": "011170.KS", "name": "롯데케미칼",      "sector": "화학",      "weight": 0.003},
    {"ticker": "000120.KS", "name": "CJ대한통운",      "sector": "물류",      "weight": 0.003},
]


KOSPI_SECTORS = sorted({c["sector"] for c in KOSPI_COMPONENTS})


def _build_excl_label(excluded: list, excl_sectors: set, total_weight: float) -> str:
    if not excluded:
        return "없음"
    sector_names = sorted(excl_sectors) if excl_sectors else []
    stock_names  = [c["name"] for c in excluded if c["sector"] not in excl_sectors]
    parts = sector_names + stock_names
    label = ", ".join(parts[:3])
    if len(parts) > 3:
        label += f" 외 {len(parts)-3}개"
    return label


def macro_realtime(*, tickers: list[str], period: str) -> dict[str, object]:
    import yfinance as yf
    plt = charting.require_matplotlib()
    import matplotlib.gridspec as gridspec
    import numpy as np
    import pandas as pd
    import io, base64

    DARK   = "#0f172a"
    SURF   = "#1e293b"
    BORDER = "#334155"
    TEXT   = "#e2e8f0"
    MUTED  = "#64748b"
    COLORS = ["#3b82f6","#22c55e","#f59e0b","#ef4444","#a855f7","#06b6d4","#f97316","#84cc16"]

    if not tickers:
        raise DomainError(400, "최소 1개 종목을 선택하세요.")

    # ── 데이터 fetch ──────────────────────────────────────────────────────────
    raw: dict[str, pd.Series] = {}
    fetch_error: str | None = None
    fetched_at = pd.Timestamp.utcnow()

    for t in tickers:
        try:
            df = yf.download(t, period=period, progress=False, auto_adjust=True)
            if df.empty:
                continue
            close = close_series(df)
            if len(close) > 0:
                raw[t] = close
        except Exception as e:
            fetch_error = str(e)

    # ── 실시간 데이터 없을 때 GBM 시뮬레이션으로 폴백 ──────────────────────────
    is_simulated = False
    if not raw:
        is_simulated = True
        rng_fb = np.random.default_rng(42)
        n_days = {"1mo": 22, "3mo": 66, "6mo": 132, "1y": 252,
                  "2y": 504, "5y": 1260}.get(period, 252)
        BASE = {
            "^TNX": (4.20, 0.0, 0.40), "CL=F": (78.0, 0.03, 0.35),
            "^GSPC": (4800, 0.08, 0.17), "^KS11": (2650, 0.06, 0.18),
            "GC=F": (2000, 0.05, 0.14), "EURUSD=X": (1.08, -0.01, 0.07),
            "BTC-USD": (45000, 0.20, 0.70), "^IRX": (5.25, 0.0, 0.15),
            "^VIX": (18.0, 0.0, 0.80), "DX-Y.NYB": (104.0, 0.01, 0.06),
        }
        dt = 1 / 252
        for t in tickers:
            s0, mu, sigma = BASE.get(t, (100, 0.05, 0.20))
            shocks = rng_fb.standard_normal(n_days)
            log_r  = (mu - 0.5 * sigma**2) * dt + sigma * np.sqrt(dt) * shocks
            vals   = s0 * np.exp(np.cumsum(log_r))
            idx    = pd.date_range(end=pd.Timestamp.today(), periods=n_days, freq="B")
            raw[t] = pd.Series(vals, index=idx)

    labels_used = [TICKER_LABELS.get(t, t) for t in raw]

    # ── 정규화 수익률 ─────────────────────────────────────────────────────────
    norm: dict[str, pd.Series] = {}
    for t, s in raw.items():
        norm[t] = (s / s.iloc[0] - 1) * 100

    # ── 공통 날짜로 상관관계 DataFrame ────────────────────────────────────────
    combined = pd.DataFrame({TICKER_LABELS.get(t, t): s for t, s in raw.items()})
    combined = combined.dropna()
    corr = combined.pct_change().dropna().corr()

    # ── Figure ────────────────────────────────────────────────────────────────
    n = len(raw)
    fig = plt.figure(figsize=(14, 11), facecolor=DARK)
    gs  = gridspec.GridSpec(2, 2, figure=fig, hspace=0.4, wspace=0.35,
                            left=0.07, right=0.97, top=0.93, bottom=0.07)

    # Panel 1: 원시 가격 추세
    ax1 = fig.add_subplot(gs[0, 0])
    ax1.set_facecolor(SURF)
    for i, (t, s) in enumerate(raw.items()):
        ax2_ = ax1.twinx() if i > 0 else ax1
        col  = COLORS[i % len(COLORS)]
        lbl  = TICKER_LABELS.get(t, t)
        if i == 0:
            ax1.plot(s.index, s.values, color=col, lw=1.5, label=lbl)
        # 정규화 차트가 더 유용하므로 여기선 첫 종목만 왼쪽 축에 표시
    ax1.tick_params(colors=TEXT, labelsize=7)
    ax1.set_title("가격 추이 (첫 번째 종목 기준)", color=TEXT, fontsize=9, pad=6)
    ax1.spines[:].set_color(BORDER)
    ax1.set_xlabel("")
    ax1.tick_params(axis='x', rotation=30)
    for label in ax1.get_xticklabels(): label.set_fontsize(6)

    # Panel 2: 정규화 수익률 (누적 %)
    ax2 = fig.add_subplot(gs[0, 1])
    ax2.set_facecolor(SURF)
    for i, (t, s) in enumerate(norm.items()):
        ax2.plot(s.index, s.values, color=COLORS[i % len(COLORS)],
                 lw=1.5, label=TICKER_LABELS.get(t, t))
    ax2.axhline(0, color=MUTED, lw=0.8, ls="--")
    ax2.set_title("정규화 누적 수익률 (%)", color=TEXT, fontsize=9, pad=6)
    ax2.tick_params(colors=TEXT, labelsize=7)
    ax2.spines[:].set_color(BORDER)
    ax2.legend(fontsize=6, facecolor=SURF, labelcolor=TEXT,
               loc="upper left", framealpha=0.7)
    ax2.tick_params(axis='x', rotation=30)
    for label in ax2.get_xticklabels(): label.set_fontsize(6)

    # Panel 3: 상관관계 히트맵
    ax3 = fig.add_subplot(gs[1, 0])
    ax3.set_facecolor(SURF)
    if len(corr) > 1:
        cmat = corr.values
        im = ax3.imshow(cmat, cmap="RdYlGn", vmin=-1, vmax=1, aspect="auto")
        ax3.set_xticks(range(len(corr.columns)))
        ax3.set_yticks(range(len(corr.columns)))
        ax3.set_xticklabels(corr.columns, rotation=45, ha="right",
                            fontsize=7, color=TEXT)
        ax3.set_yticklabels(corr.columns, fontsize=7, color=TEXT)
        for ii in range(len(cmat)):
            for jj in range(len(cmat)):
                v = cmat[ii, jj]
                ax3.text(jj, ii, f"{v:.2f}", ha="center", va="center",
                         fontsize=7, color="white" if abs(v) > 0.5 else TEXT)
        plt.colorbar(im, ax=ax3, fraction=0.04, pad=0.02).ax.tick_params(
            labelcolor=TEXT, labelsize=7)
    else:
        ax3.text(0.5, 0.5, "2개 이상 선택 시\n상관관계 표시", ha="center",
                 va="center", color=MUTED, transform=ax3.transAxes, fontsize=9)
    ax3.set_title("수익률 상관관계 히트맵", color=TEXT, fontsize=9, pad=6)
    ax3.spines[:].set_color(BORDER)

    # Panel 4: 최근 수익률 바 차트 (1M / 3M / 기간 전체)
    ax4 = fig.add_subplot(gs[1, 1])
    ax4.set_facecolor(SURF)
    period_returns = {}
    for t, s in raw.items():
        lbl = TICKER_LABELS.get(t, t)
        period_returns[lbl] = (s.iloc[-1] / s.iloc[0] - 1) * 100
    names  = list(period_returns.keys())
    values = list(period_returns.values())
    bar_colors = [COLORS[i % len(COLORS)] for i in range(len(names))]
    bars = ax4.barh(names, values, color=bar_colors, height=0.55)
    ax4.axvline(0, color=MUTED, lw=0.8)
    for bar, v in zip(bars, values):
        ax4.text(v + (0.5 if v >= 0 else -0.5), bar.get_y() + bar.get_height()/2,
                 f"{v:+.1f}%", va="center", ha="left" if v >= 0 else "right",
                 fontsize=7, color=TEXT)
    ax4.set_title(f"기간 전체 수익률 ({period})", color=TEXT, fontsize=9, pad=6)
    ax4.tick_params(colors=TEXT, labelsize=7)
    ax4.spines[:].set_color(BORDER)

    title_suffix = "  [시뮬레이션 — 실시간 연결 불가]" if is_simulated else "  (Yahoo Finance)"
    fig.suptitle(f"거시경제현황 — 실시간 데이터{title_suffix}", color=TEXT,
                 fontsize=12, fontweight="bold", y=0.97)

    buf = io.BytesIO()
    fig.savefig(buf, format="png", dpi=130, facecolor=DARK)
    plt.close(fig)
    buf.seek(0)
    img_b64 = "data:image/png;base64," + base64.b64encode(buf.read()).decode()

    # ── 요약 통계 ─────────────────────────────────────────────────────────────
    summary = {}
    for t, s in raw.items():
        lbl = TICKER_LABELS.get(t, t)
        ret  = (s.iloc[-1] / s.iloc[0] - 1) * 100
        vol  = s.pct_change().std() * (252 ** 0.5) * 100
        summary[lbl] = {
            "current": round(float(s.iloc[-1]), 4),
            "return_pct": round(ret, 2),
            "annual_vol_pct": round(vol, 2),
            "latest_data_at": pd.Timestamp(s.index[-1]).isoformat(),
        }

    return {"image": img_b64, "summary": summary, "period": period,
            "n_tickers": len(raw),
            "is_simulated": is_simulated,
            "fetched_at": fetched_at.isoformat(),
            "warning": "Yahoo Finance 요청 한도 초과로 시뮬레이션 데이터를 표시합니다. 잠시 후 다시 시도하세요." if is_simulated else None}


def macro_kospi_ex(*, exclude_tickers: list[str], exclude_sectors: list[str], period: str) -> dict[str, object]:
    import yfinance as yf
    plt = charting.require_matplotlib()
    import matplotlib.gridspec as gridspec
    import numpy as np
    import pandas as pd
    import io, base64
    from datetime import datetime, timezone

    # 제외 대상 결정
    excl_ticker_codes = {t.replace(".KS", "").replace(".KQ", "") for t in exclude_tickers}
    excl_sectors      = set(exclude_sectors)

    excluded: list[dict] = []
    included: list[dict] = []
    for comp in KOSPI_COMPONENTS:
        code = comp["ticker"].replace(".KS", "").replace(".KQ", "")
        if code in excl_ticker_codes or comp["sector"] in excl_sectors:
            excluded.append(comp)
        else:
            included.append(comp)

    total_excl_weight = sum(c["weight"] for c in excluded)
    if total_excl_weight >= 0.95:
        raise DomainError(400, "제외 비중이 너무 커서 지수를 계산할 수 없습니다.")

    # 다운로드
    tickers_needed = ["^KS11"] + [c["ticker"] for c in excluded]
    raw: dict[str, pd.Series] = {}
    is_simulated = False
    fetched_at = datetime.now(timezone.utc)

    for t in tickers_needed:
        try:
            df = yf.download(t, period=period, progress=False, auto_adjust=True)
            if df.empty:
                raise ValueError("empty")
            s = df["Close"]
            if isinstance(s, pd.DataFrame):
                s = s.iloc[:, 0]
            s = s.dropna()
            if len(s) > 5:
                raw[t] = s
        except Exception:
            is_simulated = True

    if "^KS11" not in raw or is_simulated:
        # 시뮬레이션 대체 데이터
        import math
        rng = 12345
        def _rnd():
            nonlocal rng
            rng = (rng * 1664525 + 1013904223) % 2**32
            return rng / 2**32
        def _randn():
            u, v = max(_rnd(), 1e-10), _rnd()
            return math.sqrt(-2*math.log(u)) * math.cos(2*math.pi*v)
        period_days = {"1mo":30,"3mo":90,"6mo":180,"1y":365,"2y":730,"3y":1095}
        days = period_days.get(period, 365)
        n_bars = int(days * 0.72)
        base_date = pd.Timestamp("today") - pd.Timedelta(days=days)
        dates = [base_date + pd.Timedelta(days=i+1) for i in range(n_bars)]
        price = 2650.0
        prices = []
        for _ in range(n_bars):
            price = max(price * (1 + _randn() * 0.012), 100)
            prices.append(price)
        raw["^KS11"] = pd.Series(prices, index=dates)
        # 시뮬레이션된 종목 데이터
        for comp in excluded:
            price2 = 50000.0
            p2 = []
            for _ in range(n_bars):
                price2 = max(price2 * (1 + _randn() * 0.015), 100)
                p2.append(price2)
            raw[comp["ticker"]] = pd.Series(p2, index=dates)
        is_simulated = True

    kospi_s = raw["^KS11"]
    # 공통 날짜 인덱스 정렬
    common_idx = kospi_s.index
    for comp in excluded:
        if comp["ticker"] in raw:
            common_idx = common_idx.intersection(raw[comp["ticker"]].index)
    kospi_s = kospi_s.loc[common_idx]

    # 일별 수익률
    kospi_ret = kospi_s.pct_change().fillna(0)

    # 제외 종목 기여도 계산
    contrib = pd.Series(0.0, index=common_idx)
    for comp in excluded:
        if comp["ticker"] in raw:
            s = raw[comp["ticker"]].reindex(common_idx).ffill()
            ret = s.pct_change().fillna(0)
            contrib += comp["weight"] * ret

    # 조정 수익률: r_adj = (r_KOSPI - contrib_excl) / (1 - total_excl_weight)
    adj_ret = (kospi_ret - contrib) / (1 - total_excl_weight)

    # 누적 가격 지수 (100 기준)
    kospi_norm  = (1 + kospi_ret).cumprod() * 100
    adj_norm    = (1 + adj_ret).cumprod() * 100
    kospi_norm.iloc[0] = 100.0
    adj_norm.iloc[0]   = 100.0

    # 통계
    def _stats(s: pd.Series) -> dict:
        ret_pct = float((s.iloc[-1] / s.iloc[0] - 1) * 100)
        vol_pct = float(s.pct_change().std() * (252**0.5) * 100)
        return {"return_pct": round(ret_pct, 2), "annual_vol_pct": round(vol_pct, 2)}

    stats = {
        "kospi":    _stats(kospi_s),
        "adjusted": _stats(adj_norm),
        "total_excl_weight": round(total_excl_weight * 100, 1),
    }

    # 차트 그리기 (화이트 테마)
    BG    = "#ffffff"
    SURF  = "#f8f9fa"
    GRID  = "#e8e8e8"
    TEXT  = "#1a1a1a"
    MUTED = "#666666"
    C1    = "#0078d4"   # KOSPI
    C2    = "#e63946"   # 제외 후

    fig = plt.figure(figsize=(13, 8), facecolor=BG)
    gs  = gridspec.GridSpec(2, 2, figure=fig, hspace=0.44, wspace=0.30,
                            left=0.07, right=0.97, top=0.90, bottom=0.08)

    # Panel 1: 누적 수익률 비교 (상단 전체)
    ax1 = fig.add_subplot(gs[0, :], facecolor=SURF)
    excl_label = _build_excl_label(excluded, excl_sectors, total_excl_weight)
    ax1.plot(kospi_norm.index, kospi_norm.values, color=C1, lw=2.0,
             label="KOSPI (실제)", zorder=3)
    ax1.plot(adj_norm.index, adj_norm.values, color=C2, lw=2.0, ls="--",
             label=f"KOSPI 제외 후 ({excl_label})", zorder=3)
    ax1.axhline(100, color=MUTED, lw=0.8, ls=":")
    ax1.fill_between(adj_norm.index, kospi_norm.values, adj_norm.values,
                     where=(adj_norm.values > kospi_norm.values),
                     alpha=0.12, color=C2, label="제외 후 > KOSPI")
    ax1.fill_between(adj_norm.index, kospi_norm.values, adj_norm.values,
                     where=(adj_norm.values <= kospi_norm.values),
                     alpha=0.12, color=C1, label="KOSPI > 제외 후")
    ax1.set_title(f"KOSPI vs KOSPI 제외 후 비교  |  {period}", color=TEXT, fontsize=11, pad=8, fontweight="bold")
    ax1.tick_params(colors=MUTED, labelsize=7)
    for sp in ax1.spines.values(): sp.set_color(GRID)
    ax1.grid(color=GRID, lw=0.6, alpha=0.8)
    ax1.tick_params(axis="x", rotation=20)
    ax1.legend(fontsize=8, facecolor=BG, labelcolor=TEXT, framealpha=0.9, loc="upper left")
    ax1.set_facecolor(BG)

    # Panel 2: 수익률 차이 (하단 좌)
    ax2 = fig.add_subplot(gs[1, 0], facecolor=BG)
    diff = adj_norm.values - kospi_norm.values
    colors_diff = [C2 if d > 0 else C1 for d in diff]
    ax2.bar(range(len(diff)), diff, color=colors_diff, alpha=0.7, width=1.0)
    ax2.axhline(0, color=MUTED, lw=0.8)
    ax2.set_title("KOSPI 대비 초과 성과 (제외 후 - 실제)", color=TEXT, fontsize=9, pad=6)
    ax2.tick_params(colors=MUTED, labelsize=7)
    for sp in ax2.spines.values(): sp.set_color(GRID)
    ax2.grid(color=GRID, lw=0.6, axis="y", alpha=0.8)
    ax2.set_xticks([])
    ax2.set_facecolor(BG)

    # Panel 3: 제외 종목 기여 비중 파이 (하단 우)
    ax3 = fig.add_subplot(gs[1, 1], facecolor=BG)
    if excluded:
        pie_labels = [c["name"] for c in excluded]
        pie_sizes  = [c["weight"] for c in excluded]
        SECTOR_COLORS = ["#0078d4","#e63946","#2dc653","#f59e0b","#a855f7",
                         "#06b6d4","#f97316","#ec4899","#14b8a6","#8b5cf6"]
        wedge_colors = [SECTOR_COLORS[i % len(SECTOR_COLORS)] for i in range(len(pie_sizes))]
        wedges, texts, autotexts = ax3.pie(
            pie_sizes, labels=pie_labels, colors=wedge_colors,
            autopct=lambda p: f"{p:.1f}%" if p > 3 else "",
            pctdistance=0.78, startangle=90,
            wedgeprops={"edgecolor": BG, "linewidth": 1.5},
            textprops={"fontsize": 7, "color": TEXT},
        )
        for at in autotexts: at.set_fontsize(6.5)
        ax3.set_title(f"제외 종목 구성  (총 비중 {total_excl_weight*100:.1f}%)", color=TEXT, fontsize=9, pad=6)
    else:
        ax3.text(0.5, 0.5, "제외 종목 없음", ha="center", va="center", color=MUTED, fontsize=10)
        ax3.set_title("제외 종목 구성", color=TEXT, fontsize=9, pad=6)
    ax3.set_facecolor(BG)

    title_excl = excl_label if excl_label else "없음"
    fig.suptitle(f"KOSPI 제외 지수 분석  |  제외: {title_excl}",
                 color=TEXT, fontsize=12, fontweight="bold", y=0.96)

    buf = io.BytesIO()
    fig.savefig(buf, format="png", dpi=130, facecolor=BG, bbox_inches="tight")
    plt.close(fig)
    img_b64 = "data:image/png;base64," + base64.b64encode(buf.getvalue()).decode()

    return {
        "image": img_b64,
        "stats": stats,
        "excluded": [{"name": c["name"], "ticker": c["ticker"].replace(".KS","").replace(".KQ",""),
                      "sector": c["sector"], "weight_pct": round(c["weight"]*100,1)} for c in excluded],
        "period": period,
        "is_simulated": is_simulated,
        "fetched_at": fetched_at.isoformat(),
        "warning": "Yahoo Finance 데이터 수신 실패로 시뮬레이션 데이터를 표시합니다." if is_simulated else None,
    }


def macro_kospi_ex_meta() -> dict[str, object]:
    sectors = sorted({c["sector"] for c in KOSPI_COMPONENTS})
    components = [
        {"ticker": c["ticker"].replace(".KS","").replace(".KQ",""),
         "name": c["name"], "sector": c["sector"],
         "weight_pct": round(c["weight"]*100, 1)}
        for c in KOSPI_COMPONENTS
    ]
    return {"sectors": sectors, "components": components}


def macro_simulation(*, n_days: int, seed: int) -> dict[str, object]:
    plt = charting.require_matplotlib()
    import matplotlib.gridspec as gridspec
    import numpy as np
    import io, base64

    DARK   = "#0f172a"
    SURF   = "#1e293b"
    BORDER = "#334155"
    TEXT   = "#e2e8f0"
    MUTED  = "#64748b"
    COLORS = ["#3b82f6","#f59e0b","#ef4444","#22c55e","#a855f7","#06b6d4"]

    rng = np.random.default_rng(seed)
    T   = max(60, min(n_days, 1260))
    dt  = 1 / 252

    def gbm(s0, mu, sigma, n, rng):
        shocks = rng.standard_normal(n)
        log_r  = (mu - 0.5 * sigma**2) * dt + sigma * np.sqrt(dt) * shocks
        return s0 * np.exp(np.cumsum(log_r))

    indicators = {
        "기준금리 (%)" :   {"s0": 3.50,  "mu":  0.05, "sigma": 0.08,  "fmt": ".2f"},
        "CPI (전년비 %)":  {"s0": 3.20,  "mu":  0.02, "sigma": 0.12,  "fmt": ".2f"},
        "WTI 유가 ($)":    {"s0": 78.0,  "mu":  0.03, "sigma": 0.30,  "fmt": ".1f"},
        "USD/KRW":         {"s0": 1320,  "mu": -0.01, "sigma": 0.07,  "fmt": ".0f"},
        "KOSPI":           {"s0": 2650,  "mu":  0.06, "sigma": 0.18,  "fmt": ".0f"},
        "S&P 500":         {"s0": 5200,  "mu":  0.08, "sigma": 0.16,  "fmt": ".0f"},
    }

    # macro regime: 경기 사이클 phase 추가 (상승/둔화/침체/회복)
    phase_len  = T // 4
    phases     = ["상승기", "과열기", "침체기", "회복기"]
    phase_muls = [1.0, 0.5, -0.5, 1.2]

    series_dict = {}
    for name, cfg in indicators.items():
        mu_adj = cfg["mu"]
        vals = []
        for ph_i, mul in enumerate(phase_muls):
            seg = gbm(cfg["s0"] if not vals else vals[-1],
                      mu_adj * mul, cfg["sigma"],
                      min(phase_len, T - len(vals)), rng)
            vals.extend(seg.tolist())
            if len(vals) >= T:
                break
        series_dict[name] = np.array(vals[:T])

    days = np.arange(T)

    # ── Figure ────────────────────────────────────────────────────────────────
    fig = plt.figure(figsize=(14, 12), facecolor=DARK)
    gs  = gridspec.GridSpec(3, 2, figure=fig, hspace=0.45, wspace=0.35,
                            left=0.08, right=0.97, top=0.93, bottom=0.05)

    names_list = list(series_dict.keys())
    for idx, (name, vals) in enumerate(series_dict.items()):
        row, col = divmod(idx, 2)
        ax = fig.add_subplot(gs[row, col])
        ax.set_facecolor(SURF)
        color = COLORS[idx]
        cfg   = indicators[name]

        ax.plot(days, vals, color=color, lw=1.5)
        ax.fill_between(days, vals, vals[0], alpha=0.12, color=color)

        # 경기국면 배경
        for ph_i, (ph_name, mul) in enumerate(zip(phases, phase_muls)):
            x0 = ph_i * phase_len
            x1 = min((ph_i + 1) * phase_len, T)
            bg = "#22c55e22" if mul > 0.8 else "#f59e0b22" if mul > 0 else "#ef444422"
            ax.axvspan(x0, x1, color=bg, alpha=0.4)
            ax.text((x0 + x1) / 2, ax.get_ylim()[0], ph_name,
                    ha="center", va="bottom", fontsize=6, color=MUTED)

        cur  = vals[-1]
        chg  = (cur / vals[0] - 1) * 100
        sign = "+" if chg >= 0 else ""
        ax.set_title(f"{name}  현재: {cur:{cfg['fmt']}}  ({sign}{chg:.1f}%)",
                     color=TEXT, fontsize=8.5, pad=5)
        ax.tick_params(colors=TEXT, labelsize=7)
        ax.spines[:].set_color(BORDER)
        ax.set_xlim(0, T)

        # 최고/최저 표시
        hi, lo = np.argmax(vals), np.argmin(vals)
        ax.annotate(f"고: {vals[hi]:{cfg['fmt']}}",
                    xy=(hi, vals[hi]), xytext=(5, 5), textcoords="offset points",
                    fontsize=6, color="#22c55e", arrowprops=dict(arrowstyle="->", color=MUTED, lw=0.5))
        ax.annotate(f"저: {vals[lo]:{cfg['fmt']}}",
                    xy=(lo, vals[lo]), xytext=(5, -12), textcoords="offset points",
                    fontsize=6, color="#ef4444", arrowprops=dict(arrowstyle="->", color=MUTED, lw=0.5))

    # 경기국면 범례 (우측 상단)
    from matplotlib.patches import Patch
    legend_els = [
        Patch(facecolor="#22c55e44", label="상승기"),
        Patch(facecolor="#f59e0b44", label="과열기"),
        Patch(facecolor="#ef444444", label="침체기"),
        Patch(facecolor="#22c55e44", label="회복기"),
    ]
    fig.legend(handles=legend_els, loc="upper right", fontsize=7,
               facecolor=SURF, labelcolor=TEXT, framealpha=0.8, ncol=4,
               bbox_to_anchor=(0.97, 0.995))

    fig.suptitle(f"거시경제 시뮬레이션 대시보드 — {T}거래일 GBM 시뮬레이션",
                 color=TEXT, fontsize=12, fontweight="bold", y=0.975)

    buf = io.BytesIO()
    fig.savefig(buf, format="png", dpi=130, facecolor=DARK)
    plt.close(fig)
    buf.seek(0)
    img_b64 = "data:image/png;base64," + base64.b64encode(buf.read()).decode()

    summary = {name: {"start": round(float(v[0]), 2),
                      "end":   round(float(v[-1]), 2),
                      "chg_pct": round((v[-1]/v[0]-1)*100, 2)}
               for name, v in series_dict.items()}

    return {"image": img_b64, "summary": summary, "n_days": T}
