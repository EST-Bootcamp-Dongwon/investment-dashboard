"""기업 재무제표 — 도메인 계층.

[CN-065](../../../docs/spec/00-index/변경이력.md#cn-065) 분해 순서 ⑤~⑦.
`main.py` 에 있던 1개 라우트의 본문과 그것이 쓰던 헬퍼·상수를 그대로 옮겼다.
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


def company_financials(*, ticker: str, period: str) -> dict[str, object]:
    """Return structured financial data for a ticker using yfinance."""
    import math
    import yfinance as yf
    import pandas as pd

    def safe_float(v) -> float | None:
        if v is None:
            return None
        try:
            f = float(v)
            return None if (math.isnan(f) or math.isinf(f)) else f
        except (TypeError, ValueError):
            return None

    def row(df: "pd.DataFrame", *keys: str) -> "pd.Series":
        for key in keys:
            if key in df.index:
                return df.loc[key]
        return pd.Series(dtype=float)

    def series_to_list(series: "pd.Series") -> list[dict]:
        result = []
        for idx, val in series.items():
            label = str(idx)[:7] if hasattr(idx, "strftime") else str(idx)[:10]
            result.append({"period": label, "value": safe_float(val)})
        return list(reversed(result))

    ticker_sym = ticker.strip().upper()
    try:
        tk = yf.Ticker(ticker_sym)
    except Exception as exc:
        raise DomainError(400, f"티커 오류: {exc}") from exc

    # Select annual vs quarterly statements
    if period == "annual":
        income  = tk.income_stmt
        balance = tk.balance_sheet
        cashflow = tk.cashflow
    else:
        income  = tk.quarterly_income_stmt
        balance = tk.quarterly_balance_sheet
        cashflow = tk.quarterly_cashflow

    if income is None or income.empty:
        raise DomainError(404, f"'{ticker_sym}' 재무데이터를 찾을 수 없습니다.")

    # ── Income statement rows ──────────────────────────────────────────────────
    revenue       = row(income, "Total Revenue")
    cogs          = row(income, "Cost Of Revenue")
    gross_profit  = row(income, "Gross Profit")
    op_expense    = row(income, "Operating Expense")
    op_income     = row(income, "Operating Income", "EBIT")
    other_income  = row(income, "Other Income Expense",
                        "Other Non Operating Income Expense",
                        "Non Operating Income")
    pretax        = row(income, "Pretax Income")
    tax           = row(income, "Tax Provision")
    net_income    = row(income, "Net Income")

    # ── Balance sheet rows ────────────────────────────────────────────────────
    total_debt = row(balance, "Total Debt", "Long Term Debt")
    cash       = row(balance,
                     "Cash And Cash Equivalents",
                     "Cash Cash Equivalents And Short Term Investments")

    # ── Cash flow rows ─────────────────────────────────────────────────────────
    op_cf  = row(cashflow, "Operating Cash Flow",
                 "Cash Flow From Continuing Operating Activities")
    capex  = row(cashflow, "Capital Expenditure")

    # Free Cash Flow = Operating CF + Capex (capex stored as negative)
    if not op_cf.empty and not capex.empty:
        shared_idx = op_cf.index.intersection(capex.index)
        fcf = op_cf.loc[shared_idx] + capex.loc[shared_idx]
    elif not op_cf.empty:
        fcf = op_cf
    else:
        fcf = pd.Series(dtype=float)

    # Net margin %
    margin_data: list[dict] = []
    for idx in revenue.index:
        r = safe_float(revenue.get(idx))
        n = safe_float(net_income.get(idx))
        label = str(idx)[:7]
        if r and n and r != 0:
            margin_data.append({"period": label, "value": round(n / r * 100, 2)})
    margin_data = list(reversed(margin_data))

    # ── Waterfall (most recent period) ────────────────────────────────────────
    def wf(series: "pd.Series") -> float | None:
        return safe_float(series.iloc[0]) if not series.empty else None

    waterfall = {
        "revenue":          wf(revenue),
        "cogs":             wf(cogs),
        "gross_profit":     wf(gross_profit),
        "operating_expense": wf(op_expense),
        "operating_income": wf(op_income),
        "other_income":     wf(other_income),
        "tax":              wf(tax),
        "net_income":       wf(net_income),
    }

    # ── Earnings history ──────────────────────────────────────────────────────
    earnings_data: list[dict] = []
    try:
        ed = tk.earnings_dates
        if ed is not None and not ed.empty:
            for idx, erow in list(ed.iterrows())[:20]:
                earnings_data.append({
                    "date":         str(idx)[:10],
                    "eps_estimate": safe_float(erow.get("EPS Estimate")),
                    "eps_actual":   safe_float(erow.get("Reported EPS")),
                    "surprise_pct": safe_float(erow.get("Surprise(%)")),
                })
            earnings_data.sort(key=lambda x: x["date"])
    except Exception:
        pass

    # ── Company info ─────────────────────────────────────────────────────────
    company_name = ticker_sym
    currency = "USD"
    try:
        info = tk.info or {}
        company_name = info.get("longName") or info.get("shortName") or ticker_sym
        currency = info.get("currency", "USD")
    except Exception:
        pass

    return {
        "ticker":   ticker_sym,
        "name":     company_name,
        "currency": currency,
        "period":   period,
        "performance": {
            "revenue":        series_to_list(revenue),
            "net_income":     series_to_list(net_income),
            "net_margin_pct": margin_data,
        },
        "waterfall": waterfall,
        "debt": {
            "total_debt": series_to_list(total_debt),
            "fcf":        series_to_list(fcf),
            "cash":       series_to_list(cash),
        },
        "earnings": earnings_data,
    }
