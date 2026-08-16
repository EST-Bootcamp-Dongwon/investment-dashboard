"""홈 화면 시세 — 도메인 계층.

[CN-065](../../../docs/spec/00-index/변경이력.md#cn-065) 분해 순서 ⑤~⑦.
`main.py` 에 있던 3개 라우트의 본문과 그것이 쓰던 헬퍼·상수를 그대로 옮겼다.
HTTP 를 모른다 — 실패는 `services/errors.DomainError` 로 올리고, 상태 코드로
번역하는 일은 `main.py` 의 예외 처리기 한 곳이 맡는다.

옮기면서 계산과 문구는 건드리지 않았다. 바뀐 것은 ⓐ 요청 모델 대신 키워드 인자를
받는 것과 ⓑ `HTTPException` → `DomainError` 둘뿐이다.
"""

from __future__ import annotations


try:
    from .errors import DomainError
except ImportError:  # `uvicorn main:app` 를 app/backend 에서 실행하는 경우
    from services.errors import DomainError  # type: ignore


PERIOD_DAYS = {"1mo": 30, "3mo": 90, "6mo": 180, "1y": 365}


HOME_MARKETS = {
    "kospi":  {"ticker": "^KS11", "name": "KOSPI", "base_price": 2650.0, "seed": 42},
    "kosdaq": {"ticker": "^KQ11", "name": "KOSDAQ", "base_price": 850.0, "seed": 73},
    "nasdaq": {"ticker": "^IXIC", "name": "NASDAQ", "base_price": 18000.0, "seed": 109},
    "sp500":  {"ticker": "^GSPC", "name": "S&P 500", "base_price": 5200.0, "seed": 151},
}


def home_market_candle(*, market: str, period: str) -> dict[str, object]:
    if period not in PERIOD_DAYS:
        period = "3mo"
    config = HOME_MARKETS.get(market, HOME_MARKETS["kospi"])
    import pandas as pd
    try:
        import yfinance as yf
        df = yf.download(config["ticker"], period=period, interval="1d", progress=False,
                         auto_adjust=True, threads=False)
        if df.empty:
            raise ValueError("empty")
        ohlcv = []
        for idx, row in df.iterrows():
            def _f(col):
                v = row.get(col)
                if v is None:
                    return None
                if hasattr(v, '__iter__') and not isinstance(v, (str, float, int)):
                    v = list(v)[0]
                return round(float(v), 2)
            ohlcv.append({
                "date": str(idx)[:10],
                "o": _f("Open"), "h": _f("High"),
                "l": _f("Low"),  "c": _f("Close"),
                "v": int(_f("Volume") or 0),
            })
        return {"market": market, "name": config["name"], "ticker": config["ticker"], "ohlcv": ohlcv, "is_simulated": False}
    except Exception:
        import numpy as np, math
        rng_state = config["seed"]
        def _rand():
            nonlocal rng_state
            rng_state = (rng_state * 1664525 + 1013904223) % 2**32
            return rng_state / 2**32
        def _randn():
            u, v = max(_rand(), 1e-10), _rand()
            return math.sqrt(-2 * math.log(u)) * math.cos(2 * math.pi * v)
        price = config["base_price"]
        ohlcv = []
        days = PERIOD_DAYS[period]
        n_bars = int(days * 0.72)
        base = pd.Timestamp("today") - pd.Timedelta(days=days)
        for i in range(n_bars):
            date = (base + pd.Timedelta(days=i + 1)).strftime("%Y-%m-%d")
            chg = _randn() * price * 0.012
            o = price
            c = max(o * 0.9, o + chg)
            h = max(o, c) * (1 + _rand() * 0.008)
            l = min(o, c) * (1 - _rand() * 0.008)
            ohlcv.append({"date": date, "o": round(o, 2), "h": round(h, 2),
                          "l": round(l, 2), "c": round(c, 2), "v": int(_rand() * 1e8)})
            price = c
        return {"market": market, "name": config["name"], "ticker": config["ticker"], "ohlcv": ohlcv, "is_simulated": True}


def home_kospi_candle(*, period: str) -> dict[str, object]:
    """Backward-compatible KOSPI endpoint for older clients."""
    return home_market_candle("kospi", period)


def home_box_range(*, market: str, start: str, end: str) -> dict[str, object]:
    """지정한 from~to 기간의 박스권(최고가·최저가) 상단/하단 퍼센티지를 계산한다."""
    import datetime as _dt
    config = HOME_MARKETS.get(market, HOME_MARKETS["kospi"])

    today = _dt.date.today()
    try:
        end_date = _dt.date.fromisoformat(end) if end else today
    except ValueError:
        end_date = today
    try:
        start_date = _dt.date.fromisoformat(start) if start else end_date - _dt.timedelta(days=90)
    except ValueError:
        start_date = end_date - _dt.timedelta(days=90)
    if start_date >= end_date:
        start_date = end_date - _dt.timedelta(days=1)

    import pandas as pd
    ohlcv: list[dict] = []
    is_simulated = True
    try:
        import yfinance as yf
        df = yf.download(config["ticker"], start=start_date.isoformat(),
                         end=(end_date + _dt.timedelta(days=1)).isoformat(),
                         interval="1d", progress=False, auto_adjust=True, threads=False)
        if df.empty:
            raise ValueError("empty")
        for idx, row in df.iterrows():
            def _f(col):
                v = row.get(col)
                if v is None:
                    return None
                if hasattr(v, '__iter__') and not isinstance(v, (str, float, int)):
                    v = list(v)[0]
                return round(float(v), 2)
            ohlcv.append({
                "date": str(idx)[:10],
                "o": _f("Open"), "h": _f("High"),
                "l": _f("Low"),  "c": _f("Close"),
            })
        is_simulated = False
    except Exception:
        import math
        rng_state = config["seed"]
        def _rand():
            nonlocal rng_state
            rng_state = (rng_state * 1664525 + 1013904223) % 2**32
            return rng_state / 2**32
        def _randn():
            u, v = max(_rand(), 1e-10), _rand()
            return math.sqrt(-2 * math.log(u)) * math.cos(2 * math.pi * v)
        price = config["base_price"]
        n_days = max(1, (end_date - start_date).days)
        n_bars = max(1, int(n_days * 0.72))
        for i in range(n_bars):
            date = (start_date + _dt.timedelta(days=int(i / 0.72) + 1)).isoformat()
            chg = _randn() * price * 0.012
            o = price
            c = max(o * 0.9, o + chg)
            h = max(o, c) * (1 + _rand() * 0.008)
            l = min(o, c) * (1 - _rand() * 0.008)
            ohlcv.append({"date": date, "o": round(o, 2), "h": round(h, 2),
                          "l": round(l, 2), "c": round(c, 2)})
            price = c

    if not ohlcv:
        raise DomainError(404, "해당 기간의 시세 데이터를 찾을 수 없습니다.")

    box_high = max(bar["h"] for bar in ohlcv)
    box_low  = min(bar["l"] for bar in ohlcv)
    last_close = ohlcv[-1]["c"]
    box_range = box_high - box_low
    upper_pct    = round((box_high - last_close) / last_close * 100, 2) if last_close else None
    lower_pct    = round((last_close - box_low) / last_close * 100, 2) if last_close else None
    position_pct = round((last_close - box_low) / box_range * 100, 2) if box_range else None

    return {
        "market": market, "name": config["name"], "ticker": config["ticker"],
        "start": start_date.isoformat(), "end": end_date.isoformat(),
        "ohlcv": ohlcv, "is_simulated": is_simulated,
        "box_high": round(box_high, 2), "box_low": round(box_low, 2),
        "last_close": last_close,
        "upper_pct": upper_pct, "lower_pct": lower_pct, "position_pct": position_pct,
    }
