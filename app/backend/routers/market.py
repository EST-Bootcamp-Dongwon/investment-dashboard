"""시장 지표·조합 — Controller.

[CN-065](../../../docs/spec/00-index/변경이력.md#cn-065) 분해 순서 ⑤~⑦. `main.py` 에서
갈라져 나온 라우터다. 경로 선언과 요청 검증만 하고, 판정·계산·그림은
`services/market.py` 가 맡는다.

**경로 문자열은 옮기기 전과 한 글자도 다르지 않다.** 화면(`app/frontend/js/api.js`)이
그 경로를 부르고 있어서, 여기서 접두사를 붙이면 그대로 404 가 된다. 그래서
`APIRouter(prefix=...)` 를 쓰지 않고 절대 경로를 그대로 적는다 —
`routers/combination.py` 같은 신설 라우터와 다른 점이다.
"""

from __future__ import annotations

from fastapi import APIRouter
from pydantic import BaseModel, Field

try:
    from ..services import market as service
except ImportError:  # `uvicorn main:app` 를 app/backend 에서 실행하는 경우
    from services import market as service  # type: ignore

router = APIRouter()

class MarketSnapshotRequest(BaseModel):
    tickers: list[str] = ["^KS11", "^IXIC", "KRW=X"]


class PortfolioCombinationRequest(BaseModel):
    ticker_a: str = Field(default="AAPL", min_length=1, max_length=20)
    ticker_b: str = Field(default="JNJ", min_length=1, max_length=20)
    period: str = Field(default="1y", pattern=r"^(3mo|6mo|1y|2y)$")


@router.post("/api/market/portfolio-combination")
def portfolio_combination(req: PortfolioCombinationRequest) -> dict[str, object]:
    """Compare two real tickers and return a plain-language diversification signal."""
    return service.portfolio_combination(ticker_a=req.ticker_a, ticker_b=req.ticker_b, period=req.period)


@router.post("/api/market/snapshot")
def market_snapshot(req: MarketSnapshotRequest) -> dict[str, object]:
    return service.market_snapshot(tickers=req.tickers)


@router.get("/api/market/volume-cloud")
def market_volume_cloud(market: str='us') -> dict[str, object]:
    """Return recent volume and price changes for a compact market bubble cloud."""
    return service.market_volume_cloud(market=market)
