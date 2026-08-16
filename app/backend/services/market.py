"""시장 지표·조합 — 도메인 계층.

[CN-065](../../../docs/spec/00-index/변경이력.md#cn-065) 분해 순서 ⑤~⑦.
`main.py` 에 있던 3개 라우트의 본문과 그것이 쓰던 헬퍼·상수를 그대로 옮겼다.
HTTP 를 모른다 — 실패는 `services/errors.DomainError` 로 올리고, 상태 코드로
번역하는 일은 `main.py` 의 예외 처리기 한 곳이 맡는다.

옮기면서 계산과 문구는 건드리지 않았다. 바뀐 것은 ⓐ 요청 모델 대신 키워드 인자를
받는 것과 ⓑ `HTTPException` → `DomainError` 둘뿐이다.
"""

from __future__ import annotations

import re

try:
    from .errors import DomainError
except ImportError:  # `uvicorn main:app` 를 app/backend 에서 실행하는 경우
    from services.errors import DomainError  # type: ignore

try:
    from ..clients.yahoo_prices import close_series
except ImportError:  # `uvicorn main:app` 를 app/backend 에서 실행하는 경우
    from clients.yahoo_prices import close_series  # type: ignore


MARKET_SNAPSHOT_LABELS = {
    "^KS11": "KOSPI",
    "^IXIC": "NASDAQ",
    "KRW=X": "USD/KRW",
}




VOLUME_CLOUD_MARKETS = {
    "us": [
        {"ticker": "AAPL", "name": "Apple"}, {"ticker": "MSFT", "name": "Microsoft"},
        {"ticker": "GOOGL", "name": "Alphabet"}, {"ticker": "AMZN", "name": "Amazon"},
        {"ticker": "NVDA", "name": "NVIDIA"}, {"ticker": "META", "name": "Meta"},
        {"ticker": "TSLA", "name": "Tesla"},
    ],
    "kr": [
        {"ticker": "005930.KS", "name": "삼성전자"},
        {"ticker": "000660.KS", "name": "SK하이닉스"},
        {"ticker": "373220.KS", "name": "LG에너지솔루션"},
        {"ticker": "207940.KS", "name": "삼성바이오로직스"},
        {"ticker": "005380.KS", "name": "현대차"},
        {"ticker": "000270.KS", "name": "기아"},
        {"ticker": "068270.KS", "name": "셀트리온"},
        {"ticker": "105560.KS", "name": "KB금융"},
        {"ticker": "055550.KS", "name": "신한지주"},
        {"ticker": "012330.KS", "name": "현대모비스"},
        {"ticker": "035420.KS", "name": "NAVER"},
        {"ticker": "028260.KS", "name": "삼성물산"},
        {"ticker": "006400.KS", "name": "삼성SDI"},
        {"ticker": "051910.KS", "name": "LG화학"},
        {"ticker": "003670.KS", "name": "포스코홀딩스"},
        {"ticker": "035720.KS", "name": "카카오"},
        {"ticker": "096770.KS", "name": "SK이노베이션"},
        {"ticker": "034730.KS", "name": "SK"},
        {"ticker": "086790.KS", "name": "하나금융지주"},
        {"ticker": "032830.KS", "name": "삼성생명"},
    ],
}


def portfolio_combination(*, ticker_a: str, ticker_b: str, period: str) -> dict[str, object]:
    """Compare two real tickers and return a plain-language diversification signal."""
    import pandas as pd
    import yfinance as yf

    def clean_ticker(raw: str) -> str:
        ticker = raw.strip().upper()
        if not re.fullmatch(r"[A-Z0-9.^=\-]{1,20}", ticker):
            raise DomainError(422, "올바른 종목 코드를 입력해 주세요.")
        return ticker

    ticker_a = clean_ticker(ticker_a)
    ticker_b = clean_ticker(ticker_b)
    if ticker_a == ticker_b:
        raise DomainError(422, "서로 다른 두 종목을 선택해 주세요.")

    prices: dict[str, pd.Series] = {}
    unavailable: list[str] = []
    for ticker in (ticker_a, ticker_b):
        try:
            frame = yf.download(ticker, period=period, interval="1d", progress=False,
                                auto_adjust=True, threads=False)
            close = close_series(frame)
            if len(close) < 21:
                unavailable.append(ticker)
            else:
                prices[ticker] = close
        except Exception:
            unavailable.append(ticker)

    if unavailable:
        names = ", ".join(unavailable)
        raise DomainError(422, f"{names}의 충분한 가격 데이터를 찾지 못했습니다.")

    # 거래일이 겹치는 구간의 일간 변화만 이용한다. 화면에는 수식 대신 신호와 문장만 노출한다.
    aligned_prices = pd.concat(prices, axis=1, join="inner").dropna()
    daily_moves = aligned_prices.pct_change(fill_method=None).dropna()
    if len(daily_moves) < 20:
        raise DomainError(422, "두 종목의 함께 비교할 수 있는 거래일이 부족합니다.")
    relationship = float(daily_moves.corr().iloc[0, 1])

    if relationship < 0.30:
        signal = "green"
        summary = "최근 흐름이 비교적 다르게 나타났습니다. 함께 담을 때 한 종목에만 의존하는 정도를 낮추는 데 도움이 될 수 있습니다."
        hint = "두 종목의 움직임이 겹치는 정도가 낮은 편입니다. 업종과 보유 비중도 함께 확인해 보세요."
    elif relationship < 0.70:
        signal = "yellow"
        summary = "최근에는 일부 구간에서 함께 움직였습니다. 분산 효과는 기대할 수 있지만 크기는 제한적일 수 있습니다."
        hint = "조합의 균형은 보통 수준입니다. 다른 업종이나 자산을 더하면 포트폴리오 폭을 넓힐 수 있습니다."
    else:
        signal = "red"
        summary = "최근 가격 흐름이 자주 같은 방향으로 움직였습니다. 두 종목을 함께 담아도 분산 효과가 작을 수 있습니다."
        hint = "한 종목의 영향이 다른 종목에도 이어질 수 있습니다. 업종이 다른 종목이나 다른 자산을 함께 검토해 보세요."

    period_labels = {"3mo": "최근 3개월", "6mo": "최근 6개월", "1y": "최근 1년", "2y": "최근 2년"}
    latest_data_at = pd.Timestamp(daily_moves.index[-1]).isoformat()
    # 두 종목의 가격 단위가 달라도 흐름을 한 차트에서 비교할 수 있도록 출발선을 맞춘다.
    chart_base = aligned_prices / aligned_prices.iloc[0] * 100
    chart_points = [
        {
            "date": pd.Timestamp(index).date().isoformat(),
            "a": round(float(row[ticker_a]), 4),
            "b": round(float(row[ticker_b]), 4),
        }
        for index, row in chart_base.iterrows()
    ]
    return {
        "ticker_a": ticker_a,
        "ticker_b": ticker_b,
        "period_label": period_labels[period],
        "signal": signal,
        "summary": summary,
        "portfolio_hint": hint,
        "latest_data_at": latest_data_at,
        "chart_points": chart_points,
    }


def market_snapshot(*, tickers: list[str]) -> dict[str, object]:
    import pandas as pd
    import yfinance as yf

    if not tickers:
        raise DomainError(400, "최소 1개 종목을 선택하세요.")

    fetched_at = pd.Timestamp.utcnow()
    items: list[dict[str, object]] = []

    for ticker in tickers:
        label = MARKET_SNAPSHOT_LABELS.get(ticker, ticker)
        try:
            tk = yf.Ticker(ticker)
            fi = tk.fast_info

            # fast_info provides near-realtime last_price (15-min delayed for most exchanges)
            current  = float(fi.last_price)
            previous = float(fi.previous_close) if fi.previous_close else current
            change_pct = ((current / previous) - 1) * 100 if previous else 0.0

            items.append({
                "ticker": ticker,
                "label": label,
                "value": round(current, 4),
                "change_pct": round(change_pct, 2),
                "latest_data_at": fetched_at.isoformat(),
                "status": "ok",
            })
        except Exception as exc:
            # fallback: last daily close
            try:
                df = yf.download(ticker, period="5d", interval="1d",
                                 progress=False, auto_adjust=False, threads=False)
                close = close_series(df)
                current  = float(close.iloc[-1])
                previous = float(close.iloc[-2]) if len(close) > 1 else current
                change_pct = ((current / previous) - 1) * 100 if previous else 0.0
                items.append({
                    "ticker": ticker, "label": label,
                    "value": round(current, 4),
                    "change_pct": round(change_pct, 2),
                    "latest_data_at": pd.Timestamp(close.index[-1]).isoformat(),
                    "status": "ok",
                })
            except Exception as exc2:
                items.append({"ticker": ticker, "label": label,
                              "status": "error", "error": str(exc2)})

    return {
        "items": items,
        "fetched_at": fetched_at.isoformat(),
    }


def market_volume_cloud(*, market: str) -> dict[str, object]:
    """Return recent volume and price changes for a compact market bubble cloud."""
    import pandas as pd
    import yfinance as yf

    market_key = market.lower()
    companies = VOLUME_CLOUD_MARKETS.get(market_key)
    if not companies:
        raise DomainError(400, "market은 us 또는 kr만 선택할 수 있습니다.")

    tickers = [company["ticker"] for company in companies]
    try:
        data = yf.download(tickers, period="2mo", interval="1d", group_by="ticker",
                           progress=False, auto_adjust=False, threads=True)
    except Exception as exc:
        raise DomainError(502, f"거래량 데이터를 가져오지 못했습니다: {exc}") from exc

    items: list[dict[str, object]] = []
    latest_dates: list[pd.Timestamp] = []
    for company in companies:
        ticker = company["ticker"]
        try:
            frame = data[ticker] if len(tickers) > 1 else data
            close = close_series(frame)
            volume = frame["Volume"]
            if hasattr(volume, "columns"):
                volume = volume.iloc[:, 0]
            volume = volume.dropna()
            if len(close) < 2 or volume.empty:
                raise ValueError("가격 또는 거래량 이력이 부족합니다.")

            last_close = float(close.iloc[-1])
            previous_close = float(close.iloc[-2])
            last_volume = float(volume.iloc[-1])
            prior_volume = volume.iloc[-21:-1] if len(volume) > 1 else volume
            average_volume = float(prior_volume.mean()) if not prior_volume.empty else last_volume
            items.append({
                "ticker": ticker,
                "name": company["name"],
                "price": round(last_close, 4),
                "change_pct": round((last_close / previous_close - 1) * 100, 2),
                "volume": int(last_volume),
                "average_volume_20d": int(average_volume),
                "volume_ratio": round(last_volume / average_volume, 2) if average_volume else 0.0,
                "latest_data_at": pd.Timestamp(close.index[-1]).isoformat(),
                "status": "ok",
            })
            latest_dates.append(pd.Timestamp(close.index[-1]))
        except Exception as exc:
            items.append({"ticker": ticker, "name": company["name"], "status": "error", "error": str(exc)})

    return {
        "market": market_key,
        "items": items,
        "fetched_at": pd.Timestamp.utcnow().isoformat(),
        "latest_data_at": max(latest_dates).isoformat() if latest_dates else None,
        "source": "Yahoo Finance",
    }
