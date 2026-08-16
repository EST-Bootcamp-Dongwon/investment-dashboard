"""홈 화면 시세 — Controller.

[CN-065](../../../docs/spec/00-index/변경이력.md#cn-065) 분해 순서 ⑤~⑦. `main.py` 에서
갈라져 나온 라우터다. 경로 선언과 요청 검증만 하고, 판정·계산·그림은
`services/home.py` 가 맡는다.

**경로 문자열은 옮기기 전과 한 글자도 다르지 않다.** 화면(`app/frontend/js/api.js`)이
그 경로를 부르고 있어서, 여기서 접두사를 붙이면 그대로 404 가 된다. 그래서
`APIRouter(prefix=...)` 를 쓰지 않고 절대 경로를 그대로 적는다 —
`routers/combination.py` 같은 신설 라우터와 다른 점이다.
"""

from __future__ import annotations

from fastapi import APIRouter

try:
    from ..services import home as service
except ImportError:  # `uvicorn main:app` 를 app/backend 에서 실행하는 경우
    from services import home as service  # type: ignore

router = APIRouter()

@router.get("/api/home/market-candle")
def home_market_candle(market: str='kospi', period: str='3mo') -> dict[str, object]:
    return service.home_market_candle(market=market, period=period)


@router.get("/api/home/kospi-candle")
def home_kospi_candle(period: str='3mo') -> dict[str, object]:
    """Backward-compatible KOSPI endpoint for older clients."""
    return service.home_kospi_candle(period=period)


@router.get("/api/home/box-range")
def home_box_range(market: str='kospi', start: str='', end: str='') -> dict[str, object]:
    """지정한 from~to 기간의 박스권(최고가·최저가) 상단/하단 퍼센티지를 계산한다."""
    return service.home_box_range(market=market, start=start, end=end)
