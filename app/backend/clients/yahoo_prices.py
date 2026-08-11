"""Yahoo Finance 종가 조회 — 연동 계층.

docs/spec/60-운영/아키텍처.md 2.1절의 `clients/` 계층이고, 2.2절이 예고한
`clients/yfinance_client.py` 자리의 **첫 조각**이다. 지금 담은 것은 F04 가 쓰는
"종가 시리즈 받아오기" 하나뿐이라 이름을 좁게 붙였다. 나머지 라우트 9개
(아키텍처 1.3절의 yfinance ✅ 10개 중 F04 를 뺀 수)가 옮겨 올 때 함께 넓히면 된다.

**도메인 판단을 하지 않는다.** 몇 행부터 충분한지, 짧으면 어떻게 할지는 전부
`services/combination.py` 가 정한다. 여기서 하는 일은 부르고 · 파싱하고 ·
**실패한 티커가 무엇인지 알려 주는** 것까지다.

## 이 파일이 따로 있어야 하는 이유

F04 의 계산은 매일 다른 값을 낸다. 비결정성의 출처가 이 파일 하나라서, 검증에서
**이 함수만 가짜로 바꾸면 나머지 전부가 결정적**이 된다
(`scripts/verify_combination_api.py`). `main.py:1194` 처럼 라우트 핸들러 안에서
`yf.download` 를 직접 부르면 그 자리가 없다 — 계층 분리가 사 준 것이 그것이다.
"""

from __future__ import annotations

from typing import Any

# 지연 import 는 의도된 것이다(`main.py:1177` · `indicators.py:20~22` 와 같은 관례).
# yfinance 는 requests·lxml 을 끌고 오므로 모듈 최상단에 두면 이 모듈을 import 하는
# 것만으로 콜드 스타트가 늘어난다. 여기서는 **검증에서 이 함수를 통째로 갈아끼우기
# 쉽다** 는 이유가 하나 더 있다.

# 일봉 · 배당·분할 조정 후 가격 · 스레드 없음. `main.py:1194~1195` 그대로다.
INTERVAL = "1d"
AUTO_ADJUST = True
THREADS = False


def _close_series(frame: Any) -> Any:
    """일봉 프레임에서 종가 열만 뽑아 결측을 지운다. `main.py:1166~1170` 그대로다.

    `hasattr(close, "columns")` 를 보는 것은 yfinance 가 티커 수에 따라 열 구조를
    바꾸기 때문이다 — 단일 티커인데도 MultiIndex 로 오는 경우가 있어 그때는 첫 열을
    쓴다. 조건 없이 `iloc[:, 0]` 을 쓰면 Series 인 경우에 첫 *행* 이 잡힌다.
    """
    close = frame["Close"]
    if hasattr(close, "columns"):
        close = close.iloc[:, 0]
    return close.dropna()


def download_closes(
    tickers: tuple[str, ...], period: str
) -> tuple[dict[str, Any], list[str]]:
    """`({티커: 종가 시리즈}, 못 받은 티커 목록)` 을 돌려준다.

    **예외를 올리지 않고 목록으로 돌려준다.** 티커 하나가 실패해도 나머지는 받아야
    하고, "무엇이 실패했는지" 를 문장으로 만드는 일은 도메인 계층 몫이기 때문이다
    (`main.py:1204~1206` 의 문장을 `services/combination.py` 가 만든다).

    `except Exception` 으로 넓게 잡는 것은 `main.py:1201` 과 같다. yfinance 는
    비공식 엔드포인트라 네트워크 오류 · 파싱 오류 · 429 가 각기 다른 타입으로 오고,
    호출자 입장에서는 전부 "이 티커는 못 받았다" 하나로 같다.

    **다만 없는 티커는 이 목록에 담기지 않는다.** 실측하면 이렇다.

        # 2026-08-11 · yfinance 1.5.2 · download_closes(("ZZZZNOSUCH",), "1y")
        unavailable : []                    ← 예외가 나지 않는다
        closes      : {"ZZZZNOSUCH": len=0} ← 빈 Series 로 온다

    yfinance 는 stderr 에 경고만 찍고 **빈 프레임을 돌려준다.** `Close` 열은 있으므로
    `_close_series` 도 통과한다. 그래서 없는 티커를 걸러내는 것은 이 함수가 아니라
    `services/combination.MIN_HISTORY` 의 길이 검사이고, 사용자에게 나가는 문장은
    `main.py` 와 같다("…의 충분한 가격 데이터를 찾지 못했습니다"). 위 예외 분기는
    네트워크·파싱 실패용으로 남는다.
    """
    import yfinance as yf

    closes: dict[str, Any] = {}
    unavailable: list[str] = []
    for ticker in tickers:
        try:
            frame = yf.download(
                ticker,
                period=period,
                interval=INTERVAL,
                progress=False,
                auto_adjust=AUTO_ADJUST,
                threads=THREADS,
            )
            closes[ticker] = _close_series(frame)
        except Exception:  # noqa: BLE001 — 위 docstring 참고
            unavailable.append(ticker)
    return closes, unavailable
