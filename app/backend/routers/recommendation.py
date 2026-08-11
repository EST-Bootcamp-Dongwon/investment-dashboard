"""F03 포트폴리오 추천 API — Controller.

R-01 이 요구한 A등급 기능인데 백엔드가 없어 추천 로직이 브라우저 안에만 있었고,
그래서 저장·재현·검증이 불가능했다 (CN-011). 이 라우터가 그것을 해소한다.

**3계층의 첫 적용 대상이다** (아키텍처 3절 ④ · CN-039 · CN-065).
이 파일은 경로 선언 · 요청 검증 · **도메인 예외를 HTTP 코드로 번역**하는 일만 한다.
판정과 상수는 `services/recommendation.py`, DB 접근은 `clients/recommendation_repo.py`
에 있다. 계산도 외부 호출도 여기서 하지 않는다.

설계 정본: docs/spec/40-API/API-상세명세.md 2절.
"""

from __future__ import annotations

from fastapi import APIRouter, Header, HTTPException, Query
from pydantic import BaseModel, Field

try:
    from ..clients import recommendation_repo, supabase_client
    from ..services import recommendation as service
    from . import owner
except ImportError:  # `uvicorn main:app` 를 app/backend 에서 실행하는 경우
    from clients import recommendation_repo, supabase_client  # type: ignore
    from routers import owner  # type: ignore
    from services import recommendation as service  # type: ignore

router = APIRouter(prefix="/api/recommendation", tags=["추천"])

# 소유자 판별과 anon_id 제약은 `routers/owner.py` 로 옮겼다. F05 가 같은 것을 쓰게 되어
# 사본이 둘이 되는 시점에 뽑은 것이고, 이 파일의 동작은 달라지지 않았다.
_ANON_ID = owner.ANON_ID

_SAVE_FAILED = "추천 결과를 저장할 수 없습니다. 잠시 후 다시 시도해 주세요."
_READ_FAILED = "추천 이력을 불러올 수 없습니다. 잠시 후 다시 시도해 주세요."
_CONSTANT_BROKEN = "자산 배분 구성이 올바르지 않습니다."


class PreviewRequest(BaseModel):
    """설문 3문항. 셋 다 기본값을 주지 않고 필수로 둔다.

    설문 답을 서버가 임의로 채우면 판정 근거가 흐려진다.
    (`PortfolioScenarioRequest` 가 `profile` 에 기본값을 준 것은 판정 *결과*를
    직접 받는 경우라 성격이 다르다.)
    """

    goal: str = Field(pattern="^(growth|balance|protect)$")
    horizon: str = Field(pattern="^(short|medium|long)$")
    risk: str = Field(pattern="^(low|medium|high)$")


class CreateRequest(PreviewRequest):
    anon_id: str | None = Field(default=None, **_ANON_ID)  # type: ignore[arg-type]


def _resolve_owner(authorization: str | None, anon_id: str | None) -> tuple[str | None, str | None]:
    """`owner.resolve_owner` 에 이 기능의 503 문구만 얹는다."""
    return owner.resolve_owner(authorization, anon_id, unavailable_detail=_READ_FAILED)


def _build(goal: str, horizon: str, risk: str) -> dict:
    try:
        return service.build_recommendation(goal, horizon, risk)
    except service.RecommendationDataError as exc:
        # 사용자 입력이 아니라 서버 상수가 깨진 경우다. 사용자가 고칠 수 없으므로 500.
        raise HTTPException(status_code=500, detail=_CONSTANT_BROKEN) from exc


@router.post("/preview")
def preview_recommendation(req: PreviewRequest) -> dict:
    """판정만 하고 저장하지 않는다. DB 를 전혀 건드리지 않는 순수 함수다.

    따로 두는 이유 셋. ⓐ 진입 시 하드코딩된 `renderProfile('balanced')` 의 우연한
    일치에 의존하지 않게 된다. ⓑ 방문만 해도 행이 쌓이는 것을 막는다.
    ⓒ **Supabase 가 죽어도 화면이 동작한다** — 백엔드화 때문에 오늘보다 나빠지면 안 된다.
    """
    return _build(req.goal, req.horizon, req.risk)


@router.post("/create")
def create_recommendation(
    req: CreateRequest,
    authorization: str | None = Header(default=None),
) -> dict:
    """판정하고 저장한다. 추천 1행과 배분 3~5행이 한 트랜잭션으로 들어간다."""
    user_id, anon_id = _resolve_owner(authorization, req.anon_id)
    payload = _build(req.goal, req.horizon, req.risk)

    try:
        saved = recommendation_repo.insert_recommendation(
            user_id=user_id,
            anon_id=anon_id,
            goal=req.goal,
            horizon=req.horizon,
            risk=req.risk,
            profile=payload["profile"],
            profile_label=payload["profile_label"],
            items=payload["items"],
        )
    except supabase_client.SupabaseError as exc:
        # 저장 실패를 200 으로 눙치지 않는다. F03 백엔드화의 목적 자체가 저장·재현이라,
        # 저장이 실패했는데 200 을 주면 사용자는 이력에 남았다고 믿는다.
        # 프런트는 이 503 을 받으면 preview 로 폴백하고 "저장되지 않았음" 을 표시한다.
        raise HTTPException(status_code=503, detail=_SAVE_FAILED) from exc

    return {**payload, "recommendation_id": saved["id"], "created_at": saved["created_at"]}


@router.get("/history")
def recommendation_history(
    anon_id: str | None = Query(default=None, **_ANON_ID),  # type: ignore[arg-type]
    limit: int = Query(default=20, ge=1, le=100),
    authorization: str | None = Header(default=None),
) -> dict:
    """내 추천 이력 목록. 배분 상세는 담지 않는다 — 상세는 `detail` 이 담당한다."""
    user_id, owner_anon = _resolve_owner(authorization, anon_id)

    try:
        rows = recommendation_repo.list_recommendations(
            user_id=user_id, anon_id=owner_anon, limit=limit
        )
    except supabase_client.SupabaseError as exc:
        raise HTTPException(status_code=503, detail=_READ_FAILED) from exc

    items = [
        {
            "recommendation_id": row["recommendation_id"],
            "goal": row["goal"],
            "horizon": row["horizon"],
            "risk": row["risk"],
            "profile": row["profile"],
            "profile_label": row["profile_label"],
            "item_count": row["item_count"],
            "created_at": row["created_at"],
        }
        for row in rows
    ]
    # 결과 0건은 에러가 아니다. total 0 · items [] 로 200 을 준다.
    return {
        "total": len(items),
        "limit": limit,
        "owner_type": "user" if user_id else "anon",
        "items": items,
    }


@router.get("/detail")
def recommendation_detail(
    id: int = Query(ge=1),
    anon_id: str | None = Query(default=None, **_ANON_ID),  # type: ignore[arg-type]
    authorization: str | None = Header(default=None),
) -> dict:
    """저장된 스냅샷을 그대로 되살린다. 응답 형태는 `create` 와 완전히 같다.

    프런트가 렌더 함수 하나를 그대로 재사용할 수 있게 맞춘 것이다.
    """
    user_id, owner_anon = _resolve_owner(authorization, anon_id)

    try:
        row = recommendation_repo.fetch_recommendation(id)
    except supabase_client.SupabaseError as exc:
        raise HTTPException(status_code=503, detail=_READ_FAILED) from exc

    if row is None:
        raise HTTPException(status_code=404, detail="해당 추천 결과를 찾을 수 없습니다.")

    # 403 과 404 를 분리한다. 분리하면 "그 id 는 존재한다" 가 새어 나가고 id 가 순번
    # 정수라 열거가 쉽지만, 학습용 데이터라 민감도가 낮다 (API-상세명세 2.6절).
    owned = (row.get("user_id") == user_id) if user_id else (row.get("anon_id") == owner_anon)
    if not owned:
        raise HTTPException(status_code=403, detail="다른 사용자의 추천 결과입니다.")

    items = sorted(row.get("recommendation_item") or [], key=lambda i: i["sort_order"])
    display = service.profile_display(row["profile"])

    return {
        "goal": row["goal"],
        "horizon": row["horizon"],
        "risk": row["risk"],
        "profile": row["profile"],
        "profile_label": row["profile_label"],
        **display,
        "items": items,
        # 저장된 행들의 실제 합이라 100 이 아닐 수 있다. 감시용 뷰
        # v_recommendation_weight_check 와 같은 값이므로 그대로 노출한다.
        "total_weight_pct": sum(item["weight_pct"] for item in items),
        "disclaimer": service.DISCLAIMER,
        "recommendation_id": row["id"],
        "created_at": row["created_at"],
    }
