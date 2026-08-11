"""F04 조합 조회 이력 저장·조회 — Repository.

Controller(`routers/combination.py`) → Service(`services/combination.py`) →
**Repository(여기)** → 전송(`clients/supabase_client.py`).

`recommendation_repo.py` · `simulation_repo.py` 와 같은 자리·같은 규칙이다.
도메인 판단은 하지 않는다 — 소유자 비교나 검증은 전부 위 계층의 일이다.

## 앞의 둘과 다른 점 — **RPC 를 만들지 않았다**

F03 과 F05 는 저장 RPC 를 하나씩 뒀다(`create_recommendation` · `create_simulation`).
부모 1행과 자식 N행을 넣어야 하는데 PostgREST 는 요청 하나가 트랜잭션 하나라,
따로 넣으면 자식이 실패했을 때 **고아 부모 행**이 남기 때문이다.

`combination_query` 는 **단일 테이블**이다. 넣을 행이 하나뿐이라 요청 하나가 이미
원자적이고, 함수를 만들면 마이그레이션과 유지 대상만 늘어난다.
**"세 번째니까 앞의 둘을 따라 한다" 가 아니라, 앞의 둘이 RPC 를 쓴 이유를 보고
그 이유가 여기 없음을 확인한 것이다.**

`user_id` 가 있을 때만 `app_user` 를 먼저 만드는 요청이 하나 더 붙는다. 그 둘은
트랜잭션이 갈라지는데, 그래도 괜찮은 이유는 `insert_combination` 안에 적었다.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

try:
    from . import supabase_client
except ImportError:  # `uvicorn main:app` 를 app/backend 에서 실행하는 경우
    import clients.supabase_client as supabase_client  # type: ignore

# 목록에서 읽는 컬럼. `*` 를 쓰지 않는 것은 나중에 컬럼이 늘어도 응답이 조용히
# 커지지 않게 하기 위해서다 (`recommendation_repo.py:23` 과 같은 이유).
#
# 감사 컬럼 3종(relationship · observed_from · observation_count)은 **일부러 읽지
# 않는다.** 응답에 나가지 않기로 한 값이라(마이그레이션 20260811130000 말미),
# 읽어 놓고 버리면 언젠가 누가 응답에 얹는다.
_LIST_COLUMNS = (
    "id,ticker_a,ticker_b,period,signal,summary,portfolio_hint,latest_data_at,created_at"
)

# 상세는 소유자 컬럼을 더 읽는다. 이유는 `fetch_combination` 의 docstring 참고.
_DETAIL_COLUMNS = f"{_LIST_COLUMNS},user_id,anon_id"


def _naive_utc_iso(value: str | None) -> str | None:
    """PostgREST 의 `timestamptz` 문자열을 **저장할 때 보낸 형태로** 되돌린다.

    이 함수가 필요한 이유는 왕복이 문자열을 바꾸기 때문이다. 보낼 때는
    `'2026-08-10T00:00:00'`(pandas 의 `Timestamp.isoformat()` · `main.py:1229`)인데,
    `timestamptz` 컬럼을 거쳐 나오면 `'2026-08-10T00:00:00+00:00'` 이 된다.
    **같은 시각이지만 다른 문자열**이라, 그대로 두면 `create` 와 `detail` 의 응답이
    갈라지고 프런트가 두 형태를 다 다뤄야 한다.

    일봉의 거래일이라 시각 성분은 자정이고, 실제로 필요한 정보는 날짜다.
    이 정규화가 실제로 필요하다는 것(=원격이 오프셋을 붙여 준다는 것)은
    `scripts/verify_combination_api.py` 가 원본 문자열을 그대로 찍어 실측으로 남긴다.
    """
    if not value:
        return None
    parsed = datetime.fromisoformat(value)
    if parsed.tzinfo is not None:
        parsed = parsed.astimezone(timezone.utc).replace(tzinfo=None)
    return parsed.isoformat()


def _normalize(row: dict[str, Any]) -> dict[str, Any]:
    """읽어 온 행에서 시각 컬럼만 정규화한다. 나머지는 손대지 않는다."""
    return {**row, "latest_data_at": _naive_utc_iso(row.get("latest_data_at"))}


def insert_combination(
    *,
    user_id: str | None,
    anon_id: str | None,
    ticker_a: str,
    ticker_b: str,
    period: str,
    signal: str,
    summary: str,
    portfolio_hint: str | None,
    latest_data_at: str,
    relationship: float,
    observed_from: str,
    observation_count: int,
) -> dict[str, Any]:
    """조합 판정 1행을 넣고 `{id, created_at}` 을 돌려준다."""
    if user_id is not None:
        # 로그인 사용자인데 `app_user` 행이 아직 없으면 FK 가 터진다. 토큰 검증으로
        # `auth.users` 행의 존재는 이미 확인된 상태이므로 1:1 행을 만들어 준다
        # (`create_simulation` 함수 안에서 하던 일과 같다).
        #
        # **여기서는 트랜잭션이 갈라진다.** 그래도 괜찮은 이유는 남는 것이
        # *빈 사용자 프로필 행* 이기 때문이다. 실재하는 인증 사용자의 1:1 행이라
        # 그 자체로 올바른 데이터이고, 다음 저장이 그대로 재사용한다.
        # F05 에서 트랜잭션을 갈랐다면 **곡선 없는 시뮬레이션 실행** 이 남았을 것이다 —
        # 화면에 "결과 없음" 으로 보이면서 이력에는 남는, 아무도 원하지 않는 행이다.
        # 둘의 차이는 요청 수가 아니라 **실패했을 때 남는 것이 유효한가** 다.
        supabase_client.insert("app_user", {"id": user_id}, ignore_duplicates=True)

    rows = supabase_client.insert(
        "combination_query",
        {
            "user_id": user_id,
            "anon_id": anon_id,
            "ticker_a": ticker_a,
            "ticker_b": ticker_b,
            "period": period,
            "signal": signal,
            "summary": summary,
            "portfolio_hint": portfolio_hint,
            "latest_data_at": latest_data_at,
            "relationship": relationship,
            "observed_from": observed_from,
            "observation_count": observation_count,
        },
        returning=True,
    )
    row = rows[0] if rows else None
    if not row or row.get("id") is None:
        raise supabase_client.SupabaseError(
            "조합 판정을 저장했으나 식별자를 돌려받지 못했습니다."
        )
    return {"id": int(row["id"]), "created_at": row["created_at"]}


def list_combinations(
    *, user_id: str | None, anon_id: str | None, limit: int
) -> list[dict[str, Any]]:
    """이력 목록을 `created_at desc` 로 돌려준다.

    **RPC 가 아니라 PostgREST 질의다.** F05 의 `list_simulation` 은 자식 행 수를
    세야 해서 함수가 필요했지만, 여기에는 셀 자식이 없다.

    소유자 조건을 OR 로 합치지 않는다 — 토큰이 있으면 `user_id`, 없으면 `anon_id`
    하나만 건다(`list_simulation` 과 같은 판단). 비로그인 이력이 로그인 계정에
    자동 병합되면 소유 관계가 흐려진다.
    """
    params = {
        "select": _LIST_COLUMNS,
        "order": "created_at.desc",
        "limit": str(limit),
    }
    if user_id is not None:
        params["user_id"] = f"eq.{user_id}"
    else:
        params["anon_id"] = f"eq.{anon_id}"

    return [_normalize(row) for row in supabase_client.select("combination_query", params)]


def fetch_combination(combination_id: int) -> dict[str, Any] | None:
    """단건을 읽는다. 없으면 `None`.

    소유자 컬럼(`user_id`·`anon_id`)을 함께 읽어 올린다. 조회 조건에 소유자를 섞지
    않는 이유는 라우터가 403(남의 행)과 404(없는 행)를 구분해야 하기 때문이다 —
    조건으로 걸러 버리면 둘 다 빈 결과가 되어 구분할 근거가 사라진다.
    """
    rows = supabase_client.select(
        "combination_query",
        {
            "select": _DETAIL_COLUMNS,
            "id": f"eq.{combination_id}",
            "limit": "1",
        },
    )
    return _normalize(rows[0]) if rows else None
