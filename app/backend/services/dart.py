"""DART 공시 기업 정보 — 도메인 계층.

[CN-065](../../../docs/spec/00-index/변경이력.md#cn-065) 분해 순서 ⑤~⑦.
`main.py` 에 있던 4개 라우트의 본문과 그것이 쓰던 헬퍼·상수를 그대로 옮겼다.
HTTP 를 모른다 — 실패는 `services/errors.DomainError` 로 올리고, 상태 코드로
번역하는 일은 `main.py` 의 예외 처리기 한 곳이 맡는다.

옮기면서 계산과 문구는 건드리지 않았다. 바뀐 것은 ⓐ 요청 모델 대신 키워드 인자를
받는 것과 ⓑ `HTTPException` → `DomainError` 둘뿐이다.
"""

from __future__ import annotations

import io
import json
import os
import urllib.error
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
import zipfile

try:
    from . import dart_outlook
    from .errors import DomainError
except ImportError:  # `uvicorn main:app` 를 app/backend 에서 실행하는 경우
    from services import dart_outlook  # type: ignore
    from services.errors import DomainError  # type: ignore


def _dart_api_key() -> str:
    key = os.getenv("DART_API_KEY") or os.getenv("OPENDART_API_KEY")
    if not key:
        raise DomainError(
            503,
            "DART_API_KEY 또는 OPENDART_API_KEY 환경변수를 설정하세요.",
        )
    return key


def _load_dart_corp_codes() -> list[dict[str, str]]:
    key = _dart_api_key()
    url = "https://opendart.fss.or.kr/api/corpCode.xml?" + urllib.parse.urlencode({"crtfc_key": key})
    try:
        with urllib.request.urlopen(url, timeout=20) as response:
            payload = response.read()
    except Exception as exc:
        raise DomainError(502, f"DART 회사코드 목록 수신 실패: {exc}") from exc

    try:
        with zipfile.ZipFile(io.BytesIO(payload)) as zf:
            xml_name = zf.namelist()[0]
            xml_bytes = zf.read(xml_name)
    except zipfile.BadZipFile as exc:
        message = payload[:200].decode("utf-8", errors="ignore")
        raise DomainError(502, f"DART 응답을 해석할 수 없습니다: {message}") from exc

    root = ET.fromstring(xml_bytes)
    rows: list[dict[str, str]] = []
    for item in root.findall("list"):
        corp_code = (item.findtext("corp_code") or "").strip()
        corp_name = (item.findtext("corp_name") or "").strip()
        stock_code = (item.findtext("stock_code") or "").strip()
        modify_date = (item.findtext("modify_date") or "").strip()
        if corp_code and corp_name:
            rows.append({
                "corp_code": corp_code,
                "corp_name": corp_name,
                "stock_code": stock_code,
                "modify_date": modify_date,
            })
    return rows


def _resolve_krx_yahoo_ticker(stock_code: str) -> dict[str, object]:
    if not stock_code:
        return {"ticker": None, "candidates": []}

    candidates = [f"{stock_code}.KS", f"{stock_code}.KQ"]
    found: list[str] = []
    for ticker in candidates:
        chart_url = (
            "https://query1.finance.yahoo.com/v8/finance/chart/"
            + urllib.parse.quote(ticker)
            + "?range=5d&interval=1d"
        )
        try:
            with urllib.request.urlopen(chart_url, timeout=4) as response:
                text = response.read(5000).decode("utf-8", errors="ignore")
            if '"regularMarketPrice"' in text or '"timestamp"' in text:
                found.append(ticker)
        except Exception:
            continue

    return {"ticker": found[0] if found else f"{stock_code}.KS", "candidates": found or candidates}


def _pykrx_market_data(ref_date: str) -> dict[str, dict]:
    """Return {stock_code: {market, market_cap, close}} using pykrx.

    ref_date is "YYYYMMDD" and acts as the LRU cache key so that data is
    refreshed automatically each new trading day.  Failures are silently
    swallowed so that group-network still returns results even when pykrx
    cannot reach KRX servers.
    """
    try:
        from pykrx import stock as krx

        result: dict[str, dict] = {}

        for mkt in ("KOSPI", "KOSDAQ"):
            try:
                cap_df = krx.get_market_cap_by_ticker(ref_date, market=mkt)
                for ticker, row in cap_df.iterrows():
                    result[ticker] = {
                        "market":     mkt,
                        "market_cap": int(row.get("시가총액", 0)),
                        "close":      int(row.get("종가", 0)),
                    }
            except Exception:
                pass

        return result
    except Exception:
        return {}


def _fetch_company_detail(corp_code: str) -> dict:
    """Fetch company overview (address, bizr_no) from DART company.json."""
    key = _dart_api_key()
    url = ("https://opendart.fss.or.kr/api/company.json?"
           + urllib.parse.urlencode({"crtfc_key": key, "corp_code": corp_code}))
    try:
        with urllib.request.urlopen(url, timeout=8) as response:
            data = json.loads(response.read())
        return data if data.get("status") == "000" else {}
    except Exception:
        return {}


def _load_all_listed_details() -> list[dict]:
    """Batch-fetch company detail for all listed companies. Cached in-process.

    First call may take ~30 s; subsequent calls are instant.
    """
    from concurrent.futures import ThreadPoolExecutor, as_completed

    rows = _load_dart_corp_codes()
    listed = [r for r in rows if r["stock_code"]]

    results: list[dict] = []
    with ThreadPoolExecutor(max_workers=30) as executor:
        future_to_row = {
            executor.submit(_fetch_company_detail, r["corp_code"]): r
            for r in listed
        }
        for future in as_completed(future_to_row):
            row = future_to_row[future]
            detail = future.result()
            if detail:
                results.append({
                    "corp_code":   row["corp_code"],
                    "corp_name":   detail.get("corp_name") or row["corp_name"],
                    "stock_code":  row["stock_code"],
                    "modify_date": row["modify_date"],
                    "bizr_no":     detail.get("bizr_no", ""),
                    "jurir_no":    detail.get("jurir_no", ""),
                    "adres":       detail.get("adres", ""),
                    "ceo_nm":      detail.get("ceo_nm", ""),
                    "corp_cls":    detail.get("corp_cls", ""),
                    "est_dt":      detail.get("est_dt", ""),
                })
    return results


def _fetch_emp_count(corp_code: str, bsns_year: str) -> int:
    """Return total employee count from DART empSttus.json. Returns -1 on failure."""
    key = _dart_api_key()
    url = ("https://opendart.fss.or.kr/api/empSttus.json?"
           + urllib.parse.urlencode({
               "crtfc_key":  key,
               "corp_code":  corp_code,
               "bsns_year":  bsns_year,
               "reprt_code": "11011",  # 사업보고서
           }))
    try:
        with urllib.request.urlopen(url, timeout=8) as response:
            data = json.loads(response.read())
        if data.get("status") != "000":
            return -1

        def to_int(v: object) -> int:
            try:
                return int(str(v).replace(",", "").strip() or "0")
            except (ValueError, TypeError):
                return 0

        items = data.get("list", [])
        if not items:
            return -1

        total_rows = [x for x in items if "합계" in str(x.get("nm", ""))]
        target = total_rows or items[:1]
        total = sum(to_int(x.get("rgllbr_co", 0)) + to_int(x.get("cnttk_co", 0)) for x in target)
        if total > 0:
            return total
        return to_int(items[0].get("jan_blyy_empcnt", -1)) or -1
    except Exception:
        return -1


def _parse_dart_amounts(items: list[dict]) -> dict[str, dict[str, float]]:
    """Extract key financial line items from DART fnlttSinglAcnt response.

    Returns a dict mapping account_nm → {current, prior}.
    """
    ACCT_MAP: dict[str, list[str]] = {
        "current_assets":       ["유동자산"],
        "noncurrent_assets":    ["비유동자산"],
        "total_assets":         ["자산총계"],
        "current_liabilities":  ["유동부채"],
        "noncurrent_liabilities": ["비유동부채"],
        "total_liabilities":    ["부채총계"],
        "paid_in_capital":      ["자본금"],
        "retained_earnings":    ["이익잉여금"],
        "total_equity":         ["자본총계"],
        "revenue":              ["매출액", "영업수익", "수익(매출액)"],
        "op_income":            ["영업이익", "영업손익"],
        "pretax_income":        ["법인세차감전", "법인세비용차감전"],
        "net_income":           ["당기순이익(손실)", "당기순이익"],
        "comprehensive_income": ["총포괄손익"],
    }

    def _num(val: object) -> float:
        try:
            s = str(val or "").replace(",", "").strip()
            return float(s) if s and s not in ("-", "") else 0.0
        except (ValueError, TypeError):
            return 0.0

    result: dict[str, dict[str, float]] = {}
    for key, kws in ACCT_MAP.items():
        for item in items:
            nm = (item.get("account_nm") or "").strip()
            if any(kw in nm for kw in kws):
                result[key] = {
                    "current": _num(item.get("thstrm_amount")),
                    "prior":   _num(item.get("frmtrm_amount")),
                }
                break
        if key not in result:
            result[key] = {"current": 0.0, "prior": 0.0}
    return result


def _calc_dart_ratios(fin: dict[str, dict[str, float]]) -> dict[str, float | None]:
    """Compute financial ratios from parsed DART data."""

    def g(k: str, period: str = "current") -> float:
        return fin.get(k, {}).get(period, 0.0)

    def safe_r(a: float, b: float, mult: float = 100.0) -> float | None:
        return (a / b * mult) if b != 0 else None

    rev     = g("revenue")
    prev_rev = g("revenue", "prior")
    op_inc  = g("op_income")
    net_inc = g("net_income")
    assets  = g("total_assets")
    liab    = g("total_liabilities")
    equity  = g("total_equity")
    cur_a   = g("current_assets")
    cur_l   = g("current_liabilities")
    ret_e   = g("retained_earnings")
    prev_eq = g("total_equity", "prior")

    return {
        "debt_equity_ratio": safe_r(liab, equity),
        "op_margin":         safe_r(op_inc, rev),
        "net_margin":        safe_r(net_inc, rev),
        "roe":               safe_r(net_inc, equity),
        "roa":               safe_r(net_inc, assets),
        "current_ratio":     safe_r(cur_a, cur_l),
        "revenue_growth":    safe_r(rev - prev_rev, prev_rev) if prev_rev else None,
        "equity_growth":     safe_r(equity - prev_eq, prev_eq) if prev_eq else None,
        "retained_ratio":    safe_r(ret_e, equity),
        "debt_ratio":        safe_r(liab, assets),
    }


def _score_financial_health(ratios: dict) -> tuple[float, dict]:
    """Score financial health on 0-100 scale with breakdown."""
    breakdown: dict[str, dict] = {}
    total = 0.0

    def score_item(key: str, label: str, max_score: float,
                   thresholds: list[tuple[float, float]], value: float | None) -> float:
        if value is None:
            s = max_score * 0.5
        else:
            s = 0.0
            for limit, pts in thresholds:
                if value >= limit:
                    s = pts
                    break
        breakdown[label] = {"score": round(s, 1), "max": max_score, "value": value}
        return s

    # 부채비율 (20점) — 낮을수록 좋음 (역방향)
    dr = ratios.get("debt_equity_ratio")
    dr_inv = -dr if dr is not None else None  # invert so higher=better
    total += score_item("debt_equity_ratio", "부채비율", 20,
                        [(-50, 20), (-100, 16), (-200, 10), (-300, 5), (-1e9, 0)], dr_inv)

    # 영업이익률 (20점)
    total += score_item("op_margin", "영업이익률", 20,
                        [(20, 20), (10, 16), (5, 10), (0, 5), (-1e9, 0)],
                        ratios.get("op_margin"))

    # ROE (15점)
    total += score_item("roe", "자기자본이익률(ROE)", 15,
                        [(20, 15), (10, 12), (5, 8), (0, 4), (-1e9, 0)],
                        ratios.get("roe"))

    # 유동비율 (15점)
    total += score_item("current_ratio", "유동비율", 15,
                        [(200, 15), (150, 12), (100, 8), (50, 4), (-1e9, 0)],
                        ratios.get("current_ratio"))

    # 매출 성장률 (15점)
    total += score_item("revenue_growth", "매출 성장률", 15,
                        [(15, 15), (5, 12), (0, 7), (-10, 3), (-1e9, 0)],
                        ratios.get("revenue_growth"))

    # 이익잉여금 비율 (15점)
    total += score_item("retained_ratio", "이익잉여금 비율", 15,
                        [(70, 15), (50, 12), (30, 8), (10, 4), (-1e9, 0)],
                        ratios.get("retained_ratio"))

    return round(total, 1), breakdown


def _generate_dart_analysis(
    company: dict, market: str, ratios: dict,
    score: float, grade: str, bsns_year: str, breakdown: dict,
) -> dict:
    """Generate rule-based AI financial analysis narrative."""
    corp_name = company.get("corp_name", "동 기업")

    market_ctx = {
        "KOSPI":  "유가증권시장(KOSPI)에 상장된",
        "KOSDAQ": "코스닥(KOSDAQ)에 상장된",
        "KONEX":  "코넥스(KONEX)에 상장된",
    }.get(market, "상장된")

    paragraphs: list[str] = []

    # Overall verdict
    if score >= 85:
        paragraphs.append(
            f"{corp_name}의 {bsns_year}년 재무제표는 전반적으로 매우 우수한 건전성을 보입니다. "
            f"{market_ctx} 기업으로, 재무 안정성과 수익성 모두 업계 상위 수준입니다."
        )
    elif score >= 70:
        paragraphs.append(
            f"{corp_name}의 {bsns_year}년 재무 상태는 양호한 수준입니다. "
            f"{market_ctx} 기업으로, 핵심 재무지표들이 안정적으로 관리되고 있습니다."
        )
    elif score >= 55:
        paragraphs.append(
            f"{corp_name}의 {bsns_year}년 재무 상태는 보통 수준이며, 일부 지표에서 개선이 필요합니다. "
            f"{market_ctx} 기업으로, 선별적 모니터링이 권고됩니다."
        )
    else:
        paragraphs.append(
            f"{corp_name}의 {bsns_year}년 재무 상태는 취약한 것으로 분석됩니다. "
            f"{market_ctx} 기업이나, 재무 리스크가 높아 투자에 각별한 주의가 필요합니다."
        )

    # Debt structure
    dr = ratios.get("debt_equity_ratio")
    if dr is not None:
        if dr < 50:
            paragraphs.append(
                f"부채비율 {dr:.1f}%는 매우 낮은 수준으로, 무차입 또는 보수적 재무 구조를 유지하고 있습니다. "
                "금리 상승기에도 재무적 부담이 경미합니다."
            )
        elif dr < 100:
            paragraphs.append(
                f"부채비율 {dr:.1f}%는 안정적 수준으로, 재무 레버리지가 건전하게 관리되고 있습니다."
            )
        elif dr < 200:
            paragraphs.append(
                f"부채비율 {dr:.1f}%는 업계 평균 수준(100~200%)에 해당하며, 레버리지 관리가 중요합니다."
            )
        else:
            paragraphs.append(
                f"부채비율 {dr:.1f}%는 높은 편입니다. 이자 부담 및 유동성 리스크를 면밀히 점검해야 합니다."
            )

    # Profitability
    om = ratios.get("op_margin")
    nm = ratios.get("net_margin")
    if om is not None:
        if om > 20:
            paragraphs.append(
                f"영업이익률 {om:.1f}%는 매우 높은 수익성을 입증합니다. "
                "강력한 가격 결정력 또는 원가 경쟁력을 보유한 것으로 판단됩니다."
            )
        elif om > 10:
            paragraphs.append(
                f"영업이익률 {om:.1f}%는 안정적 수익성을 나타냅니다."
                + (f" 순이익률 {nm:.1f}%까지 고려할 때 전반적 수익 구조가 건전합니다." if nm and nm > 5 else "")
            )
        elif om > 0:
            paragraphs.append(
                f"영업이익률 {om:.1f}%는 낮은 편으로, 수익성 개선이 향후 핵심 과제입니다."
            )
        else:
            paragraphs.append(
                f"영업이익 적자(영업이익률 {om:.1f}%)는 핵심 영업 활동에서의 손실을 의미합니다. "
                "사업 구조 재편 또는 비용 절감이 시급합니다."
            )

    # Capital efficiency
    roe = ratios.get("roe")
    roa = ratios.get("roa")
    if roe is not None:
        if roe > 15:
            paragraphs.append(
                f"ROE {roe:.1f}%는 자본 효율성이 탁월함을 보여줍니다."
                + (f" ROA {roa:.1f}%도 양호해 자산 운용 효율이 높습니다." if roa and roa > 5 else "")
            )
        elif roe > 5:
            paragraphs.append(f"ROE {roe:.1f}%는 적정 수준의 자본 수익성을 나타냅니다.")
        else:
            paragraphs.append(
                f"ROE {roe:.1f}%는 낮은 자본 효율성을 시사합니다. "
                "수익 모델 개선 또는 자본 재구조화 여지를 검토할 필요가 있습니다."
            )

    # Growth
    rg = ratios.get("revenue_growth")
    if rg is not None:
        if rg > 20:
            paragraphs.append(f"전년 대비 매출이 {rg:.1f}% 급성장하며 강한 성장 모멘텀을 보여줍니다.")
        elif rg > 5:
            paragraphs.append(f"매출 성장률 {rg:.1f}%는 안정적 성장세를 나타냅니다.")
        elif rg >= 0:
            paragraphs.append(f"매출 성장률 {rg:.1f}%로 소폭 성장에 그쳤습니다. 성장 동력 강화가 필요합니다.")
        else:
            paragraphs.append(
                f"매출이 전년 대비 {abs(rg):.1f}% 감소했습니다. "
                "수요 약화 또는 경쟁 심화 여부를 면밀히 파악해야 합니다."
            )

    # Liquidity
    cr = ratios.get("current_ratio")
    if cr is not None:
        if cr > 200:
            paragraphs.append(f"유동비율 {cr:.0f}%는 단기 채무 상환 능력이 매우 충분함을 나타냅니다.")
        elif cr > 100:
            paragraphs.append(f"유동비율 {cr:.0f}%는 단기 유동성이 적정 수준입니다.")
        else:
            paragraphs.append(
                f"유동비율 {cr:.0f}%는 단기 유동성이 다소 취약합니다. "
                "단기 차입 의존도를 낮추는 전략이 필요합니다."
            )

    # ── 재무 상태 표기 (CN-046) ──────────────────────────────────────────────
    # 여기 있던 "매수(Buy)/중립(Hold)/관망(Sell/Wait)" 은 재무 요약이 아니라 행동
    # 지시라서 R-07 과 정면으로 부딪쳤다. 판정을 services/dart_outlook.py 로 꺼내
    # **의견이 아니라 상태**를 내게 했다. 꺼낸 이유는 그 파일 docstring 에 있다 —
    # 요약하면 판정을 직접 넣고 검사할 수 있어야 해서다.
    status = dart_outlook.assess(score, grade, breakdown)

    return {
        "paragraphs":     paragraphs,
        # outlook_eng 는 없앴다. `BUY`/`SELL` 은 매매 지시 그 자체다
        # (50-UI/화면-상세.md 4.2절 1번). 쓰던 곳은 화면 한 곳뿐이었다.
        "outlook":        status["outlook"],
        "outlook_color":  status["outlook_color"],
        "outlook_reason": status["outlook_reason"],
        # 파싱이 실패한 항목을 화면이 `— 자료 없음` 으로 표시할 수 있게 이름을 넘긴다.
        "missing":        status["missing"],
        "withheld":       status["withheld"],
        # 여기 있던 문장("자동화 AI 분석이며, 투자 권유가 아닙니다…")은 이 화면만의
        # 것이었다. CN-060 이 확정한 공통 문구로 갈아끼운다 — 화면마다 다른 면책이
        # 붙어 있으면 무엇이 정본인지 알 수 없다.
        "disclaimer":         dart_outlook.DISCLAIMER,
        "disclaimer_context": dart_outlook.DISCLAIMER_CONTEXT,
    }


def dart_company_search(*, company_name: str, limit: int) -> dict[str, object]:
    query = company_name.strip()
    normalized = query.replace(" ", "").lower()
    if not normalized:
        raise DomainError(400, "회사명을 입력하세요.")

    rows = _load_dart_corp_codes()
    listed = [row for row in rows if row["stock_code"]]
    exact = [row for row in listed if row["corp_name"].replace(" ", "").lower() == normalized]
    partial = [row for row in listed if normalized in row["corp_name"].replace(" ", "").lower()]
    matches = (exact + [row for row in partial if row not in exact])[: limit]

    results = []
    for row in matches:
        ticker_info = _resolve_krx_yahoo_ticker(row["stock_code"])
        results.append({
            **row,
            "ticker": ticker_info["ticker"],
            "ticker_candidates": ticker_info["candidates"],
            "display": f'{ticker_info["ticker"] or row["stock_code"]}, {row["corp_name"]}',
        })

    return {
        "query": query,
        "count": len(results),
        "results": results,
        "source": "OpenDART corpCode.xml",
        "notes": [
            "DART 회사코드 목록에서 상장기업(stock_code 보유 기업)만 검색합니다.",
            "DART는 .KS/.KQ suffix를 제공하지 않아 조회 가능한 Yahoo ticker 후보로 보완 표시합니다.",
        ],
    }


def dart_group_network(*, group_name: str, limit: int) -> dict[str, object]:
    """Search DART listed companies by group/conglomerate keyword and enrich
    each match with live market-cap data from pykrx."""
    import datetime

    query = group_name.strip()
    normalized = query.replace(" ", "").lower()
    if not normalized:
        raise DomainError(400, "그룹명을 입력하세요.")

    rows = _load_dart_corp_codes()
    listed = [row for row in rows if row["stock_code"]]

    # Exact name prefix matches first, then partial matches
    exact_codes = {r["corp_code"] for r in listed if r["corp_name"].replace(" ", "").lower().startswith(normalized)}
    exact = [r for r in listed if r["corp_code"] in exact_codes]
    partial = [r for r in listed if normalized in r["corp_name"].replace(" ", "").lower()
               and r["corp_code"] not in exact_codes]
    matches = (exact + partial)[: limit]

    # Try today first; fall back to yesterday for weekends / holidays
    today = datetime.date.today()
    ref_date = today.strftime("%Y%m%d")
    market_data = _pykrx_market_data(ref_date)
    if not market_data:
        yesterday = (today - datetime.timedelta(days=1)).strftime("%Y%m%d")
        market_data = _pykrx_market_data(yesterday)

    results = []
    for row in matches:
        sc = row["stock_code"]
        mkt_info = market_data.get(sc, {})
        market_label = mkt_info.get("market", "기타")
        results.append({
            "corp_code":   row["corp_code"],
            "corp_name":   row["corp_name"],
            "stock_code":  sc,
            "modify_date": row["modify_date"],
            "market":      market_label,
            "market_cap":  mkt_info.get("market_cap", 0),
            "close":       mkt_info.get("close", 0),
            "dart_url":    f"https://dart.fss.or.kr/corp/main.do?corp_code={row['corp_code']}",
        })

    # Sort by market cap descending so flagship companies appear first
    results.sort(key=lambda x: x["market_cap"], reverse=True)

    total_market_cap = sum(r["market_cap"] for r in results)
    kospi_count  = sum(1 for r in results if r["market"] == "KOSPI")
    kosdaq_count = sum(1 for r in results if r["market"] == "KOSDAQ")

    return {
        "query":            query,
        "count":            len(results),
        "total_market_cap": total_market_cap,
        "kospi_count":      kospi_count,
        "kosdaq_count":     kosdaq_count,
        "results":          results,
        "source":           "OpenDART corpCode.xml + pykrx KRX 시장데이터",
    }


def dart_company_list(*, region: str, emp_min: int | None, emp_max: int | None, bsns_year: str, limit: int) -> dict[str, object]:
    """Search listed companies by region (address substring) and/or employee count."""
    from concurrent.futures import ThreadPoolExecutor, as_completed

    region = region.strip()
    use_emp = emp_min is not None or emp_max is not None

    all_companies = _load_all_listed_details()

    candidates = (
        [c for c in all_companies if region in c.get("adres", "")]
        if region else list(all_companies)
    )

    if use_emp:
        with ThreadPoolExecutor(max_workers=20) as executor:
            futures = {
                executor.submit(_fetch_emp_count, c["corp_code"], bsns_year): c
                for c in candidates
            }
            filtered: list[dict] = []
            for future in as_completed(futures):
                company = futures[future]
                emp = future.result()
                if emp < 0:
                    continue
                if emp_min is not None and emp < emp_min:
                    continue
                if emp_max is not None and emp > emp_max:
                    continue
                filtered.append({**company, "emp_count": emp})
    else:
        filtered = [{**c, "emp_count": None} for c in candidates]

    results = sorted(filtered, key=lambda x: x["corp_name"])[: limit]

    return {
        "region":        region or None,
        "emp_min":       emp_min,
        "emp_max":       emp_max,
        "bsns_year":     bsns_year,
        "total_matched": len(filtered),
        "count":         len(results),
        "results":       results,
        "source":        "OpenDART company.json" + (" + empSttus.json" if use_emp else ""),
    }


def dart_financial_analysis(*, corp_code: str, bsns_year: str, reprt_code: str) -> dict:
    """Fetch DART financial statements and run AI-powered financial health analysis."""
    key = _dart_api_key()

    # ── 1. Company meta-data ─────────────────────────────────────────────────
    company = _fetch_company_detail(corp_code)
    if not company:
        raise DomainError(404, "DART 기업 정보를 조회할 수 없습니다.")

    corp_cls = company.get("corp_cls", "")
    market   = {"Y": "KOSPI", "K": "KOSDAQ", "N": "KONEX"}.get(corp_cls, "비상장/기타")

    # ── 2. Financial statements ──────────────────────────────────────────────
    def _fetch_fin(fs_div: str) -> dict:
        url = ("https://opendart.fss.or.kr/api/fnlttSinglAcnt.json?"
               + urllib.parse.urlencode({
                   "crtfc_key":  key,
                   "corp_code":  corp_code,
                   "bsns_year":  bsns_year,
                   "reprt_code": reprt_code,
                   "fs_div":     fs_div,
               }))
        try:
            with urllib.request.urlopen(url, timeout=15) as resp:
                return json.loads(resp.read())
        except Exception:
            return {}

    fin_data = _fetch_fin("CFS")  # 연결재무제표 우선
    is_consolidated = True
    if fin_data.get("status") != "000" or not fin_data.get("list"):
        fin_data = _fetch_fin("OFS")  # 별도재무제표 fallback
        is_consolidated = False

    if fin_data.get("status") != "000" or not fin_data.get("list"):
        raise DomainError(404, f"{bsns_year}년 재무제표 데이터가 없습니다: {fin_data.get('message', '알 수 없음')}"
        )

    items = fin_data.get("list", [])
    fin   = _parse_dart_amounts(items)

    # ── 3. Ratios & scoring ──────────────────────────────────────────────────
    ratios       = _calc_dart_ratios(fin)
    score, breakdown = _score_financial_health(ratios)
    grade        = (
        "A+" if score >= 90 else "A" if score >= 80 else "B+" if score >= 75
        else "B" if score >= 70 else "C" if score >= 60 else "D" if score >= 50 else "F"
    )
    verdict      = "매우 견실" if score >= 85 else "견실" if score >= 70 else "보통" if score >= 55 else "취약"

    # ── 4. Friendly financial snapshot (unit: 억원) ──────────────────────────
    B = 100_000_000  # 1억

    def to_eok(v: float) -> float | None:
        return round(v / B, 1) if v else None

    snap = {
        "revenue":              to_eok(fin["revenue"]["current"]),
        "prev_revenue":         to_eok(fin["revenue"]["prior"]),
        "op_income":            to_eok(fin["op_income"]["current"]),
        "prev_op_income":       to_eok(fin["op_income"]["prior"]),
        "net_income":           to_eok(fin["net_income"]["current"]),
        "prev_net_income":      to_eok(fin["net_income"]["prior"]),
        "total_assets":         to_eok(fin["total_assets"]["current"]),
        "total_liabilities":    to_eok(fin["total_liabilities"]["current"]),
        "total_equity":         to_eok(fin["total_equity"]["current"]),
        "current_assets":       to_eok(fin["current_assets"]["current"]),
        "current_liabilities":  to_eok(fin["current_liabilities"]["current"]),
        "retained_earnings":    to_eok(fin["retained_earnings"]["current"]),
        "is_consolidated":      is_consolidated,
        "unit":                 "억원",
    }

    # breakdown 을 넘기는 것은 CN-046 때문이다 — 상태 표기의 이유가 "어느 항목이
    # 점수를 움직였는가" 라서 항목별 점수가 필요하다. 추가 계산은 없다.
    analysis = _generate_dart_analysis(
        company, market, ratios, score, grade, bsns_year, breakdown,
    )

    return {
        "company":  {
            "corp_code":  corp_code,
            "corp_name":  company.get("corp_name", ""),
            "ceo_nm":     company.get("ceo_nm", ""),
            "adres":      company.get("adres", ""),
            "est_dt":     company.get("est_dt", ""),
            "stock_code": company.get("stock_code", ""),
            "corp_cls":   corp_cls,
            "market":     market,
        },
        "financials": snap,
        "ratios":     ratios,
        "health":     {
            "score":     score,
            "grade":     grade,
            "verdict":   verdict,
            "breakdown": breakdown,
        },
        "analysis":       analysis,
        "bsns_year":  bsns_year,
    }
