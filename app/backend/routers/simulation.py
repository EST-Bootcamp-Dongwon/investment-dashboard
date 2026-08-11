"""F05 포트폴리오 시뮬레이션 API — Controller.

`POST /api/quant/portfolio-scenario`(`quant.py:60`)는 A등급 기능인데 **결과가 저장되지
않아** 같은 조건을 다시 보려면 매번 다시 계산해야 했다. 이 라우터가 그 저장 경로를 낸다.

**F03 에 이어 3계층을 두 번째로 적용한 대상이다** (아키텍처 3절 ④ · CN-039).
이 파일은 경로 선언 · 요청 검증 · **도메인 예외를 HTTP 코드로 번역**하는 일만 한다.
계산과 상수는 `services/simulation.py`, DB 접근은 `clients/simulation_repo.py` 에 있다.

**기존 `quant.py` 엔드포인트를 대체하지 않는다.** 화면(`portfolioSimulation.js:56`)이
지금 그것을 부르고 있고, 저장 기능을 붙이면서 동작하던 화면이 나빠질 이유가 없다.
두 경로가 같은 값을 내는지는 `scripts/verify_simulation_api.py` 가 대조한다.

설계 정본: docs/spec/40-API/API-상세명세.md 1.2절 · 테이블-정의서 4.5절.
"""

from __future__ import annotations

from fastapi import APIRouter, Header, HTTPException, Query
from pydantic import BaseModel, Field

try:
    from ..clients import simulation_repo, supabase_client
    from ..services import simulation as service
    from . import owner
except ImportError:  # `uvicorn main:app` 를 app/backend 에서 실행하는 경우
    from clients import simulation_repo, supabase_client  # type: ignore
    from routers import owner  # type: ignore
    from services import simulation as service  # type: ignore

router = APIRouter(prefix="/api/simulation", tags=["시뮬레이션"])

_SAVE_FAILED = "시뮬레이션 결과를 저장할 수 없습니다. 잠시 후 다시 시도해 주세요."
_READ_FAILED = "시뮬레이션 이력을 불러올 수 없습니다. 잠시 후 다시 시도해 주세요."
_CALC_BROKEN = "시뮬레이션 결과가 올바르지 않습니다."


class PreviewRequest(BaseModel):
    """제약은 `PortfolioScenarioRequest`(`quant.py:50~55`)와 같은 값이다.

    기본값까지 같게 둔다. 두 경로가 같은 요청을 같은 뜻으로 읽어야 값 대조가 성립한다.
    """

    profile: str = Field(default="balanced", pattern="^(stable|balanced|growth)$")
    initial_amount: int = Field(default=10_000_000, ge=0, le=1_000_000_000)
    monthly_amount: int = Field(default=500_000, ge=0, le=100_000_000)
    years: int = Field(default=10, ge=1, le=30)


class CreateRequest(PreviewRequest):
    anon_id: str | None = Field(default=None, **owner.ANON_ID)  # type: ignore[arg-type]


def _build(req: PreviewRequest) -> dict:
    try:
        return service.build_simulation(
            req.profile,  # type: ignore[arg-type]
            req.initial_amount,
            req.monthly_amount,
            req.years,
        )
    except service.SimulationDataError as exc:
        # 사용자 입력이 아니라 계산이 깨진 경우다. 사용자가 고칠 수 없으므로 500 이고,
        # 503 이면 안 된다 — 다시 시도해도 같은 값이 나온다.
        raise HTTPException(status_code=500, detail=_CALC_BROKEN) from exc


@router.post("/preview")
def preview_simulation(req: PreviewRequest) -> dict:
    """계산만 하고 저장하지 않는다. DB 를 전혀 건드리지 않는다.

    따로 두는 이유는 F03 `preview` 와 같다 — ⓐ 화면을 열어 보기만 해도 행이 쌓이는 것을
    막고, ⓑ **Supabase 가 죽어도 시뮬레이션 화면은 동작한다.**
    """
    return _build(req)


@router.post("/create")
def create_simulation(
    req: CreateRequest,
    authorization: str | None = Header(default=None),
) -> dict:
    """계산하고 저장한다. 실행 1행과 곡선 `years + 1` 행이 한 트랜잭션으로 들어간다."""
    user_id, anon_id = owner.resolve_owner(
        authorization, req.anon_id, unavailable_detail=_READ_FAILED
    )
    payload = _build(req)

    try:
        saved = simulation_repo.insert_simulation(
            user_id=user_id,
            anon_id=anon_id,
            profile=payload["profile"],
            profile_label=payload["profile_label"],
            initial_amount=payload["initial_amount"],
            monthly_amount=payload["monthly_amount"],
            years=payload["years"],
            total_paid=payload["total_paid"],
            final_cautious=payload["summary"]["cautious"],
            final_middle=payload["summary"]["middle"],
            final_positive=payload["summary"]["positive"],
            rng_seed=payload["rng_seed"],
            paths=payload["paths"],
            points=payload["points"],
        )
    except supabase_client.SupabaseError as exc:
        # 저장 실패를 200 으로 눙치지 않는다. 이 엔드포인트가 존재하는 이유가 저장이라,
        # 저장이 실패했는데 200 을 주면 사용자는 이력에 남았다고 믿는다.
        # 프런트는 이 503 을 받으면 preview 로 폴백하고 "저장되지 않았음" 을 표시한다.
        raise HTTPException(status_code=503, detail=_SAVE_FAILED) from exc

    return {**payload, "simulation_id": saved["id"], "created_at": saved["created_at"]}


@router.get("/history")
def simulation_history(
    anon_id: str | None = Query(default=None, **owner.ANON_ID),  # type: ignore[arg-type]
    limit: int = Query(default=20, ge=1, le=100),
    authorization: str | None = Header(default=None),
) -> dict:
    """내 시뮬레이션 이력 목록. 연 단위 곡선은 담지 않는다 — 상세는 `detail` 이 담당한다.

    곡선을 빼는 이유는 크기다. 30년 실행 20건이면 곡선만 620행이라, 목록 한 번에
    상세를 다 실으면 응답이 이력 화면에 필요 없는 값으로 채워진다.
    """
    user_id, owner_anon = owner.resolve_owner(
        authorization, anon_id, unavailable_detail=_READ_FAILED
    )

    try:
        rows = simulation_repo.list_simulations(
            user_id=user_id, anon_id=owner_anon, limit=limit
        )
    except supabase_client.SupabaseError as exc:
        raise HTTPException(status_code=503, detail=_READ_FAILED) from exc

    items = [
        {
            "simulation_id": row["simulation_id"],
            "profile": row["profile"],
            "profile_label": row["profile_label"],
            "initial_amount": row["initial_amount"],
            "monthly_amount": row["monthly_amount"],
            "years": row["years"],
            "total_paid": row["total_paid"],
            "summary": {
                "cautious": row["final_cautious"],
                "middle": row["final_middle"],
                "positive": row["final_positive"],
            },
            "point_count": row["point_count"],
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
def simulation_detail(
    id: int = Query(ge=1),
    anon_id: str | None = Query(default=None, **owner.ANON_ID),  # type: ignore[arg-type]
    authorization: str | None = Header(default=None),
) -> dict:
    """저장된 스냅샷을 그대로 되살린다. 응답 형태는 `create` 와 완전히 같다.

    **F03 과 달리 되살릴 수 없는 값이 없다** (CN-031 과 대비된다). F03 은 `badge`·
    `intro`·`note` 를 저장할 자리가 없어 지금 상수에서 되찾아야 했지만, F05 는 입력
    4개 · 결과 요약 3개 · 재현 전제 2개가 전부 컬럼으로 있다. 지금 상수에서 오는 것은
    고정 문구인 `explanation` 하나뿐이다.
    """
    user_id, owner_anon = owner.resolve_owner(
        authorization, anon_id, unavailable_detail=_READ_FAILED
    )

    try:
        row = simulation_repo.fetch_simulation(id)
    except supabase_client.SupabaseError as exc:
        raise HTTPException(status_code=503, detail=_READ_FAILED) from exc

    if row is None:
        raise HTTPException(status_code=404, detail="해당 시뮬레이션 결과를 찾을 수 없습니다.")

    # 403 과 404 를 분리한다. 분리하면 "그 id 는 존재한다" 가 새어 나가고 id 가 순번
    # 정수라 열거가 쉽지만, 학습용 데이터라 민감도가 낮다 (API-상세명세 2.6절과 같은 판단).
    owned = (row.get("user_id") == user_id) if user_id else (row.get("anon_id") == owner_anon)
    if not owned:
        raise HTTPException(status_code=403, detail="다른 사용자의 시뮬레이션 결과입니다.")

    # PostgREST 는 임베디드 리소스의 정렬을 요청대로 주지만, 곡선의 순서는 화면이
    # 그대로 그리는 값이라 여기서 한 번 더 확정한다.
    points = sorted(row.get("simulation_point") or [], key=lambda p: p["year"])

    return {
        "profile": row["profile"],
        "profile_label": row["profile_label"],
        "initial_amount": row["initial_amount"],
        "monthly_amount": row["monthly_amount"],
        "years": row["years"],
        "total_paid": row["total_paid"],
        "points": points,
        # 곡선의 마지막 점이 아니라 저장된 final_* 컬럼을 쓴다. 둘은 같은 값이어야 하고,
        # 어긋난다면 그것 자체가 알아야 할 사실이라 한쪽으로 가려서는 안 된다.
        "summary": {
            "cautious": row["final_cautious"],
            "middle": row["final_middle"],
            "positive": row["final_positive"],
        },
        "rng_seed": row["rng_seed"],
        "paths": row["paths"],
        "explanation": service.EXPLANATION,
        "simulation_id": row["id"],
        "created_at": row["created_at"],
    }
