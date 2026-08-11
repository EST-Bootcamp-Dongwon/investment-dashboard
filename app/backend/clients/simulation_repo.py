"""F05 시뮬레이션 저장·조회 — Repository.

Controller(`routers/simulation.py`) → Service(`services/simulation.py`) →
**Repository(여기)** → 전송(`clients/supabase_client.py`).

`recommendation_repo.py` 와 같은 자리·같은 규칙이다. 도메인 판단은 하지 않는다 —
소유자 비교나 검증은 전부 위 계층의 일이다.
"""

from __future__ import annotations

from typing import Any

try:
    from . import supabase_client
except ImportError:  # `uvicorn main:app` 를 app/backend 에서 실행하는 경우
    import clients.supabase_client as supabase_client  # type: ignore

# 상세에서 읽는 컬럼. `*` 를 쓰지 않는 것은 나중에 컬럼이 늘어도 응답이 조용히
# 커지지 않게 하기 위해서다 (`recommendation_repo.py:23` 과 같은 이유).
_DETAIL_COLUMNS = (
    "id,user_id,anon_id,profile,profile_label,initial_amount,monthly_amount,years,"
    "total_paid,final_cautious,final_middle,final_positive,rng_seed,paths,created_at,"
    "simulation_point(year,cautious,middle,positive)"
)


def insert_simulation(
    *,
    user_id: str | None,
    anon_id: str | None,
    profile: str,
    profile_label: str,
    initial_amount: int,
    monthly_amount: int,
    years: int,
    total_paid: int,
    final_cautious: int,
    final_middle: int,
    final_positive: int,
    rng_seed: int,
    paths: int,
    points: list[dict[str, Any]],
) -> dict[str, Any]:
    """실행 1행과 연 단위 곡선을 한 트랜잭션으로 넣고 `{id, created_at}` 을 돌려준다.

    PostgREST 로 부모와 자식을 따로 넣으면 요청이 둘이라 트랜잭션이 갈라지고, 자식이
    실패하면 곡선 없는 고아 실행 행이 남는다. RPC 한 번이 유일한 방법이다.
    """
    rows = supabase_client.rpc(
        "create_simulation",
        {
            "p_user_id": user_id,
            "p_anon_id": anon_id,
            "p_profile": profile,
            "p_profile_label": profile_label,
            "p_initial_amount": initial_amount,
            "p_monthly_amount": monthly_amount,
            "p_years": years,
            "p_total_paid": total_paid,
            "p_final_cautious": final_cautious,
            "p_final_middle": final_middle,
            "p_final_positive": final_positive,
            "p_rng_seed": rng_seed,
            "p_paths": paths,
            "p_points": points,
        },
    )
    row = rows[0] if isinstance(rows, list) and rows else None
    if not row or row.get("simulation_id") is None:
        raise supabase_client.SupabaseError(
            "시뮬레이션을 저장했으나 식별자를 돌려받지 못했습니다."
        )
    return {"id": int(row["simulation_id"]), "created_at": row["created_at"]}


def list_simulations(
    *, user_id: str | None, anon_id: str | None, limit: int
) -> list[dict[str, Any]]:
    """이력 목록을 `created_at desc` 로 돌려준다. 연 단위 곡선은 담지 않는다."""
    rows = supabase_client.rpc(
        "list_simulation",
        {"p_user_id": user_id, "p_anon_id": anon_id, "p_limit": limit},
    )
    return rows if isinstance(rows, list) else []


def fetch_simulation(simulation_id: int) -> dict[str, Any] | None:
    """단건을 곡선까지 함께 읽는다. 없으면 `None`.

    소유자 컬럼(`user_id`·`anon_id`)을 함께 읽어 올린다. 조회 조건에 소유자를 섞지
    않는 이유는 라우터가 403(남의 행)과 404(없는 행)를 구분해야 하기 때문이다 —
    조건으로 걸러 버리면 둘 다 빈 결과가 되어 구분할 근거가 사라진다.
    """
    rows = supabase_client.select(
        "simulation_run",
        {
            "select": _DETAIL_COLUMNS,
            "id": f"eq.{simulation_id}",
            "limit": "1",
            # 자식 정렬은 임베디드 리소스에 직접 건다.
            "simulation_point.order": "year.asc",
        },
    )
    return rows[0] if rows else None
