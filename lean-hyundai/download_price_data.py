"""Yahoo Finance 일봉 OHLCV를 LEAN Custom Data용 CSV로 내려받습니다.

lean-samsung/download_samsung_data.py 를 티커 인자를 받도록 일반화한 판본입니다.
표준 라이브러리만 사용하므로 어느 환경에서나 실행됩니다.
"""

from __future__ import annotations

import argparse
import csv
import json
from datetime import date, datetime, time, timezone
from pathlib import Path
from urllib.parse import urlencode
from urllib.request import Request, urlopen

# Yahoo Finance 차트 API. 비공식 엔드포인트라 언제든 막히거나 형식이 바뀔 수 있습니다.
CHART_URL = "https://query1.finance.yahoo.com/v8/finance/chart/{ticker}"


def unix_timestamp(value: str) -> int:
    parsed = date.fromisoformat(value)
    return int(datetime.combine(parsed, time.min, tzinfo=timezone.utc).timestamp())


def download(ticker: str, start: str, end: str) -> list[list[object]]:
    query = urlencode(
        {
            "period1": unix_timestamp(start),
            "period2": unix_timestamp(end),
            "interval": "1d",
            "events": "history",
        }
    )
    request = Request(
        f"{CHART_URL.format(ticker=ticker)}?{query}",
        headers={"User-Agent": "Mozilla/5.0"},
    )
    with urlopen(request, timeout=30) as response:
        payload = json.load(response)

    result = payload["chart"]["result"][0]
    quote = result["indicators"]["quote"][0]

    rows: list[list[object]] = []
    for timestamp, open_, high, low, close, volume in zip(
        result["timestamp"],
        quote["open"],
        quote["high"],
        quote["low"],
        quote["close"],
        quote["volume"],
    ):
        # 휴장일·거래정지일은 값이 null 로 오므로 버립니다.
        if None in (open_, high, low, close, volume):
            continue
        day = datetime.fromtimestamp(timestamp, timezone.utc).date().isoformat()
        rows.append([day, open_, high, low, close, volume])
    return rows


def main() -> None:
    parser = argparse.ArgumentParser(description="Yahoo Finance 일봉 다운로더")
    parser.add_argument("--ticker", default="005380.KS", help="Yahoo 티커 (기본: 현대차)")
    parser.add_argument("--output", required=True)
    parser.add_argument("--start", required=True)
    parser.add_argument("--end", required=True)
    args = parser.parse_args()

    rows = download(args.ticker, args.start, args.end)
    if not rows:
        raise RuntimeError(
            f"{args.ticker} 의 {args.start}~{args.end} 구간에서 받은 유효한 일봉이 0건입니다."
        )

    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("w", newline="") as file:
        writer = csv.writer(file)
        writer.writerow(["Date", "Open", "High", "Low", "Close", "Volume"])
        writer.writerows(rows)

    print(f"{args.ticker}: {len(rows)}건 저장 ({rows[0][0]} ~ {rows[-1][0]}) → {output}")


if __name__ == "__main__":
    main()
