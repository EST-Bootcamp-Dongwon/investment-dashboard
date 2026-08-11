"""LEAN 백테스트용 일봉 조회 — 연동 계층.

docs/spec/60-운영/아키텍처.md 2.1절의 `clients/` 계층이다. `yahoo_prices.py` 와
나란한 자리지만 **부르는 대상이 다르다** — 저쪽은 `yfinance` 패키지이고, 이쪽은
`lean-hyundai/download_price_data.py` 다. 둘을 합치지 않은 이유는 아래에 적었다.

**도메인 판단을 하지 않는다.** 몇 행이면 충분한지 · 구간이 겹치는지는 전부
`services/backtest.py` 가 정한다. 여기서 하는 일은 부르고 · 캐시하고 ·
**실패를 도메인 예외로 올리는** 것까지다.

## 이 파일이 따로 있어야 하는 이유

F28 의 계산은 매일 다른 값을 낸다. 비결정성의 출처가 **이 함수 하나**라서, 검증에서
`lean_prices.download` 만 가짜로 바꾸면 나머지 전부가 결정적이 된다
(CN-106 ② · `scripts/verify_backtest_api.py`). 리팩터 전 `backtest_lab.py:144` 는
`download_price_data.download(...)` 를 라우트 핸들러 안에서 직접 불렀는데, 그러면
치환 지점이 **라우터의 내부 이름**이라 계층 밖에서 갈아끼우는 모양이 된다.

## `yahoo_prices.py` 와 합치지 않은 이유

같은 Yahoo 를 두 방식으로 부른다. `yahoo_prices` 는 `yfinance` 패키지를 쓰고
(`auto_adjust=True` — 배당·분할이 **과거 값까지 소급 수정**한다), 이쪽은
`download_price_data.py` 가 표준 라이브러리 `urllib` 로 차트 엔드포인트를 직접 친다.
**둘은 같은 티커·같은 구간에도 다른 숫자를 줄 수 있다.**

합쳐서 한쪽으로 통일하면 LEAN 컨테이너가 쓰는 시세와 웹앱이 쓰는 시세가 갈라진다.
`routers/backtest_lab.py` 머리말이 *"LEAN 컨테이너가 쓰는 것과 같은 모듈이라 신호가
갈라지지 않는다"* 고 적은 그 전제가 깨지는 것이다. 그래서 **부르는 경로를 그대로 두고
자리만 옮겼다.**
"""

from __future__ import annotations

import sys
from pathlib import Path
from threading import Lock
from time import monotonic

# lean-hyundai 는 패키지가 아니라 스크립트 폴더라 경로를 직접 얹는다.
# 리팩터 전 `backtest_lab.py:26~28` 이 하던 일을 그대로 가져왔다.
ROOT = Path(__file__).resolve().parents[3]
LEAN_HD = ROOT / "lean-hyundai"


def ensure_path() -> None:
    """`lean-hyundai/` 를 `sys.path` 에 얹는다. 여러 번 불러도 안전하다.

    `services/backtest.py` 도 `hd_core` 를 import 하려면 이 경로가 필요해서 함수로
    빼 두었다. **호출 순서에 기대지 않기 위해서다** — 이 모듈을 import 하는 것만으로
    경로가 붙게 해 두면, import 순서가 바뀌는 날 조용히 깨진다.
    """
    if str(LEAN_HD) not in sys.path:
        sys.path.insert(0, str(LEAN_HD))


ensure_path()

try:
    import download_price_data  # type: ignore

    IMPORT_ERROR = ""
except Exception as exc:  # pragma: no cover - 환경 문제를 화면에 그대로 알린다.
    download_price_data = None  # type: ignore
    IMPORT_ERROR = f"{type(exc).__name__}: {exc}"


class PriceDownloadError(Exception):
    """시세를 받지 못했다. 라우터가 502 로 번역한다."""


class PriceEmptyError(Exception):
    """받았는데 유효한 일봉이 0건이다. 라우터가 404 로 번역한다.

    `PriceDownloadError` 와 나누는 이유는 사용자가 할 일이 다르기 때문이다 —
    앞은 "잠시 후 다시", 뒤는 "티커·기간을 고쳐라" 다. 리팩터 전
    `backtest_lab.py:145~159` 도 502 와 404 로 나눠 냈다.
    """


# 시세 캐시. 같은 조건을 반복 실행할 때 Yahoo 를 매번 두드리지 않기 위한 것으로,
# 요청 제한(429)에 걸리는 것도 막아준다. 리팩터 전 `backtest_lab.py:57~59` 그대로다.
CACHE_TTL_SECONDS = 900
_cache: dict[tuple[str, str, str], tuple[float, list]] = {}
_cache_lock = Lock()


def clear_cache() -> None:
    """캐시를 비운다. 검증이 같은 조건을 여러 번 다른 시세로 돌릴 때 쓴다."""
    with _cache_lock:
        _cache.clear()


def download(ticker: str, start: str, end: str) -> list:
    """일봉 `[[날짜, 시, 고, 저, 종, 거래량], …]` 를 돌려준다. TTL 캐시가 앞에 붙는다.

    `except Exception` 으로 넓게 잡는 것은 리팩터 전 `backtest_lab.py:145` 와 같다.
    비공식 엔드포인트라 네트워크 오류·파싱 오류·429 가 각기 다른 타입으로 오고,
    호출자 입장에서는 전부 "이 티커는 못 받았다" 하나로 같다.
    """
    if download_price_data is None:
        raise PriceDownloadError(IMPORT_ERROR or "시세 모듈을 찾지 못했습니다.")

    key = (ticker, start, end)
    now = monotonic()
    with _cache_lock:
        hit = _cache.get(key)
        if hit and now - hit[0] < CACHE_TTL_SECONDS:
            return hit[1]

    try:
        rows = download_price_data.download(ticker, start, end)
    except Exception as exc:  # noqa: BLE001 - 위 docstring 참고
        raise PriceDownloadError(f"{type(exc).__name__}: {exc}") from exc

    if not rows:
        # **캐시에 넣지 않는다.** 빈 결과를 15분 동안 들고 있으면, 티커를 고쳐 다시
        # 물어도 같은 404 가 돌아온다. 리팩터 전에도 404 는 캐시 저장 앞에서 났다.
        raise PriceEmptyError(f"{ticker} 의 {start}~{end} 구간에서 받은 유효한 일봉이 0건입니다.")

    with _cache_lock:
        _cache[key] = (now, rows)
        # 캐시가 무한정 자라지 않게 오래된 항목을 정리한다.
        for stale in [k for k, (ts, _) in _cache.items() if now - ts > CACHE_TTL_SECONDS]:
            _cache.pop(stale, None)
    return rows
