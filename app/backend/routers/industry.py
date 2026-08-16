"""산업 경쟁력 분석 — Controller.

[CN-065](../../../docs/spec/00-index/변경이력.md#cn-065) 분해 순서 ⑤~⑦. `main.py` 에서
갈라져 나온 라우터다. 경로 선언과 요청 검증만 하고, 판정·계산·그림은
`services/industry.py` 가 맡는다.

**경로 문자열은 옮기기 전과 한 글자도 다르지 않다.** 화면(`app/frontend/js/api.js`)이
그 경로를 부르고 있어서, 여기서 접두사를 붙이면 그대로 404 가 된다. 그래서
`APIRouter(prefix=...)` 를 쓰지 않고 절대 경로를 그대로 적는다 —
`routers/combination.py` 같은 신설 라우터와 다른 점이다.
"""

from __future__ import annotations

from fastapi import APIRouter
from pydantic import BaseModel

try:
    from ..services import industry as service
except ImportError:  # `uvicorn main:app` 를 app/backend 에서 실행하는 경우
    from services import industry as service  # type: ignore

router = APIRouter()

class PorterRequest(BaseModel):
    industry: str = "반도체"
    scores: dict[str, float] = {
        "경쟁강도":       8.0,
        "신규진입 위협":  6.0,
        "대체재 위협":    4.0,
        "구매자 교섭력":  5.0,
        "공급자 교섭력":  7.0,
    }


class SectorRequest(BaseModel):
    tickers: list[str] = ["SOXX", "XLE", "XLF", "XLV", "XLK", "XLI"]
    period:  str       = "1y"


class PeerRequest(BaseModel):
    tickers: dict[str, str] = {
        "삼성전자": "005930.KS",
        "SK하이닉스": "000660.KS",
        "엔비디아": "NVDA",
        "인텔": "INTC",
    }


class LifecycleRequest(BaseModel):
    stage:    str = "성장기"   # 도입기 성장기 성숙기 쇠퇴기
    industry: str = "전기차"


@router.post("/api/industry/porter")
def industry_porter(req: PorterRequest) -> dict[str, object]:
    return service.industry_porter(industry=req.industry, scores=req.scores)


@router.post("/api/industry/sector")
def industry_sector(req: SectorRequest) -> dict[str, object]:
    return service.industry_sector(tickers=req.tickers, period=req.period)


@router.post("/api/industry/peer")
def industry_peer(req: PeerRequest) -> dict[str, object]:
    return service.industry_peer(tickers=req.tickers)


@router.post("/api/industry/lifecycle")
def industry_lifecycle(req: LifecycleRequest) -> dict[str, object]:
    return service.industry_lifecycle(stage=req.stage, industry=req.industry)
