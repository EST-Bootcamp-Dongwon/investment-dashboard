"""거시 지표·지수 — Controller.

[CN-065](../../../docs/spec/00-index/변경이력.md#cn-065) 분해 순서 ⑤~⑦. `main.py` 에서
갈라져 나온 라우터다. 경로 선언과 요청 검증만 하고, 판정·계산·그림은
`services/macro.py` 가 맡는다.

**경로 문자열은 옮기기 전과 한 글자도 다르지 않다.** 화면(`app/frontend/js/api.js`)이
그 경로를 부르고 있어서, 여기서 접두사를 붙이면 그대로 404 가 된다. 그래서
`APIRouter(prefix=...)` 를 쓰지 않고 절대 경로를 그대로 적는다 —
`routers/combination.py` 같은 신설 라우터와 다른 점이다.
"""

from __future__ import annotations

from fastapi import APIRouter
from pydantic import BaseModel, Field

try:
    from ..services import macro as service
except ImportError:  # `uvicorn main:app` 를 app/backend 에서 실행하는 경우
    from services import macro as service  # type: ignore

router = APIRouter()

class MacroRealtimeRequest(BaseModel):
    tickers: list[str] = ["^TNX", "CL=F", "^GSPC", "^KS11", "GC=F", "EURUSD=X"]
    period:  str       = "1y"   # 1mo 3mo 6mo 1y 2y 5y


class MacroKospiExRequest(BaseModel):
    exclude_tickers: list[str] = []
    exclude_sectors: list[str] = []
    period: str = "1y"


class MacroSimRequest(BaseModel):
    # `seed` 는 하한이 없으면 음수가 들어와 `np.random.default_rng` 가 500 을 낸다.
    # 422 가 사실에 맞는 응답이다 (2026-08-17).
    n_days:    int   = Field(252, ge=60, le=1260)
    seed:      int   = Field(42, ge=0)


@router.post("/api/macro/realtime")
def macro_realtime(req: MacroRealtimeRequest) -> dict[str, object]:
    return service.macro_realtime(tickers=req.tickers, period=req.period)


@router.post("/api/macro/kospi-ex")
def macro_kospi_ex(req: MacroKospiExRequest) -> dict[str, object]:
    return service.macro_kospi_ex(exclude_tickers=req.exclude_tickers, exclude_sectors=req.exclude_sectors, period=req.period)


@router.get("/api/macro/kospi-ex/meta")
def macro_kospi_ex_meta() -> dict[str, object]:
    return service.macro_kospi_ex_meta()


@router.post("/api/macro/simulation")
def macro_simulation(req: MacroSimRequest) -> dict[str, object]:
    return service.macro_simulation(n_days=req.n_days, seed=req.seed)
