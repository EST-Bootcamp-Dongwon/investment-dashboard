"""F03 추천 저장·조회 — Repository.

API-상세명세 2.7절이 요구한 3계층의 맨 아래다.
Controller(`routers/recommendation.py`) → Service(`services/recommendation.py`) →
**Repository(여기)** → 전송(`clients/supabase_client.py`).

아키텍처 2.2절의 폴더 배치에 Repository 라는 폴더가 따로 없어 `clients/` 에 둔다.
그 계층의 정의가 "외부 API 호출·응답 파싱·**DB 접근**" 이라 자리가 맞는다.
도메인 판단은 하지 않는다 — 소유자 비교나 판정은 전부 위 계층의 일이다.
"""

from __future__ import annotations

from typing import Any

try:
    from . import supabase_client
except ImportError:  # `uvicorn main:app` 를 app/backend 에서 실행하는 경우
    import clients.supabase_client as supabase_client  # type: ignore

# 목록·상세에서 읽는 컬럼. `*` 를 쓰지 않는 것은 나중에 컬럼이 늘어도 응답이
# 조용히 커지지 않게 하기 위해서다.
_DETAIL_COLUMNS = (
    "id,user_id,anon_id,goal,horizon,risk,profile,profile_label,created_at,"
    "recommendation_item(sort_order,asset_name,weight_pct,explanation)"
)


def insert_recommendation(
    *,
    user_id: str | None,
    anon_id: str | None,
    goal: str,
    horizon: str,
    risk: str,
    profile: str,
    profile_label: str,
    items: list[dict[str, Any]],
) -> dict[str, Any]:
    """추천 1행과 배분 라인을 한 트랜잭션으로 넣고 `{id, created_at}` 을 돌려준다."""
    rows = supabase_client.rpc(
        "create_recommendation",
        {
            "p_user_id": user_id,
            "p_anon_id": anon_id,
            "p_goal": goal,
            "p_horizon": horizon,
            "p_risk": risk,
            "p_profile": profile,
            "p_profile_label": profile_label,
            "p_items": items,
        },
    )
    row = rows[0] if isinstance(rows, list) and rows else None
    if not row or row.get("recommendation_id") is None:
        raise supabase_client.SupabaseError("추천을 저장했으나 식별자를 돌려받지 못했습니다.")
    return {"id": int(row["recommendation_id"]), "created_at": row["created_at"]}


def list_recommendations(
    *, user_id: str | None, anon_id: str | None, limit: int
) -> list[dict[str, Any]]:
    """이력 목록을 `created_at desc` 로 돌려준다. 배분 상세는 담지 않는다."""
    rows = supabase_client.rpc(
        "list_recommendation",
        {"p_user_id": user_id, "p_anon_id": anon_id, "p_limit": limit},
    )
    return rows if isinstance(rows, list) else []


def fetch_recommendation(recommendation_id: int) -> dict[str, Any] | None:
    """단건을 배분 라인까지 함께 읽는다. 없으면 `None`.

    소유자 컬럼(`user_id`·`anon_id`)을 함께 읽어 올린다. 조회 조건에 소유자를 섞지
    않는 이유는 라우터가 403(남의 행)과 404(없는 행)를 구분해야 하기 때문이다 —
    조건으로 걸러 버리면 둘 다 빈 결과가 되어 구분할 근거가 사라진다.
    """
    rows = supabase_client.select(
        "recommendation",
        {
            "select": _DETAIL_COLUMNS,
            "id": f"eq.{recommendation_id}",
            "limit": "1",
            # 자식 정렬은 임베디드 리소스에 직접 건다.
            "recommendation_item.order": "sort_order.asc",
        },
    )
    return rows[0] if rows else None
