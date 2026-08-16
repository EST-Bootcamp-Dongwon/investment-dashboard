"""서버 상태·접속자 — Controller.

[CN-065](../../../docs/spec/00-index/변경이력.md#cn-065) 분해 순서 ⑤~⑦. `main.py` 에서
갈라져 나온 라우터다. 경로 선언과 요청 검증만 하고, 판정·계산·그림은
`services/system.py` 가 맡는다.

**경로 문자열은 옮기기 전과 한 글자도 다르지 않다.** 화면(`app/frontend/js/api.js`)이
그 경로를 부르고 있어서, 여기서 접두사를 붙이면 그대로 404 가 된다. 그래서
`APIRouter(prefix=...)` 를 쓰지 않고 절대 경로를 그대로 적는다 —
`routers/combination.py` 같은 신설 라우터와 다른 점이다.
"""

from __future__ import annotations

from fastapi import APIRouter
from pydantic import BaseModel, Field

try:
    from ..services import system as service
except ImportError:  # `uvicorn main:app` 를 app/backend 에서 실행하는 경우
    from services import system as service  # type: ignore

router = APIRouter()

class VisitorHeartbeatRequest(BaseModel):
    visitor_id: str = Field(min_length=16, max_length=80, pattern=r"^[A-Za-z0-9_-]+$")


@router.get("/api/health")
def health_check() -> dict[str, str]:
    return service.health_check()


@router.get("/api/system/resources")
def system_resources() -> dict[str, object]:
    """Return host CPU, memory and root-disk utilization for the admin view."""
    return service.system_resources()


@router.post("/api/visitors/heartbeat")
def visitor_heartbeat(payload: VisitorHeartbeatRequest) -> dict[str, int]:
    """Register one browser briefly and return the current active-browser count."""
    return service.visitor_heartbeat(visitor_id=payload.visitor_id)
