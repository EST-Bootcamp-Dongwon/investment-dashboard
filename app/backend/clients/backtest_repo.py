"""F28 백테스트 요약 저장·조회 — Repository.

Controller(`routers/backtest_lab.py`) → Service(`services/backtest.py`) →
**Repository(여기)** → 전송(`clients/supabase_client.py`).

`recommendation_repo.py` · `simulation_repo.py` · `combination_repo.py` 와 같은
자리·같은 규칙이다. 도메인 판단은 하지 않는다 — 무엇을 저장할지 정하는 것은
`services/backtest.to_row` 이고, 소유자 비교는 라우터의 일이다.

## RPC 를 만들지 않았다 — F04 와 같은 이유

`backtest_summary` 는 **단일 테이블**이다. 넣을 행이 하나뿐이라 PostgREST 요청 하나가
이미 트랜잭션 하나이고, 함수를 만들면 마이그레이션과 유지 대상만 늘어난다(CN-104).
F03·F05 가 RPC 를 쓴 것은 부모 1행 + 자식 N행이라 따로 넣으면 **고아 부모 행**이
남기 때문인데, 여기에는 자식이 없다.

## 읽을 때 숫자를 한 번 손본다

`numeric` 컬럼이 PostgREST 를 지나 무엇으로 돌아오는지에 **기대지 않는다.** 문자열로
와도 숫자로 와도 같은 값이 되게 `_to_float` 를 지난다.

실제로 무엇이 오는지는 재 두었다. 원격 프로젝트에 한 행을 넣었다 빼서 형을 찍은 것이다.

    # 2026-08-11 · GET /rest/v1/backtest_summary?id=eq.<id>&select=*
    initial_cash               100000000                            int
    commission_rate            0.00015                              float
    strategy_total_return_pct  18.331820983355485                   float
    train_start                '2025-01-01'                         str
    created_at                 '2026-08-11T02:18:20.253094+00:00'   str

즉 지금 버전은 `numeric` 을 **JSON 수**로 준다. 그래서 `_to_float` 는 이 버전에서
사실상 항등이고, **버전이 바뀌어 문자열로 오는 경우를 위한 방어**다. 값 자체는
`jsonb → numeric → JSON` 을 지나도 보존된다(위 `18.331820983355485` 가 넣은 값과
`==` 로 같다 — `scripts/verify_backtest_api.py` 의 "history 생성컬럼" 검사).
"""

from __future__ import annotations

from typing import Any

try:
    from . import supabase_client
except ImportError:  # `uvicorn main:app` 를 app/backend 에서 실행하는 경우
    import clients.supabase_client as supabase_client  # type: ignore

# 목록에서 읽는 컬럼. `*` 를 쓰지 않는 것은 나중에 컬럼이 늘어도 응답이 조용히
# 커지지 않게 하기 위해서다 (`recommendation_repo.py:23` 과 같은 이유).
#
# **jsonb 3개를 일부러 읽지 않는다.** 목록에 싣지 않기로 했으므로(`to_list_item`),
# 읽어 놓고 버리면 전송량만 늘고 언젠가 누가 응답에 얹는다 (CN-108 과 같은 판단).
# 대신 생성 컬럼 2개를 읽는다 — 그러라고 만들어 둔 컬럼이다.
_LIST_COLUMNS = (
    "id,ticker,name,train_start,train_end,test_start,test_end,model_name,price_rows,"
    "strategy_total_return_pct,strategy_max_drawdown_pct,created_at"
)

# 상세는 입력 4개 · 지표 3덩이 · 시세 창 3개 · 소유자 2개를 더 읽는다.
_DETAIL_COLUMNS = (
    f"{_LIST_COLUMNS},user_id,anon_id,initial_cash,commission_rate,sell_tax_rate,"
    "slippage_rate,warmup_days,strategy_stats,benchmark_stats,prediction_metrics,"
    "price_first,price_last,engine_note"
)

#: 읽어 온 뒤 `float` 로 맞출 컬럼. `numeric` 이라 전송 형태가 보장되지 않는다.
_FLOAT_COLUMNS = (
    "commission_rate",
    "sell_tax_rate",
    "slippage_rate",
    "strategy_total_return_pct",
    "strategy_max_drawdown_pct",
)


def _to_float(value: Any) -> Any:
    """`numeric` 을 float 로 맞춘다. `None` 은 그대로 둔다.

    생성 컬럼 2개는 `strategy_stats->>'…'` 가 없으면 `None` 이 될 수 있어
    (`jsonb` 에 키가 빠진 경우) `None` 을 숫자로 바꾸지 않는다 — 없는 값을 0 으로
    보이게 하면 "손실 0%" 로 읽힌다.
    """
    return None if value is None else float(value)


def _normalize(row: dict[str, Any]) -> dict[str, Any]:
    """읽어 온 행에서 숫자 컬럼만 맞춘다. 나머지는 손대지 않는다.

    `date` 컬럼(train_start 등)은 보낸 것과 같은 `'YYYY-MM-DD'` 로 돌아오므로
    F04 의 `_naive_utc_iso` 같은 정규화가 필요 없다. `timestamptz` 였다면 오프셋이
    붙어 돌아왔겠지만(CN-097), 여기 4개는 `date` 다.
    """
    return {**row, **{c: _to_float(row[c]) for c in _FLOAT_COLUMNS if c in row}}


def insert_backtest_summary(row: dict[str, Any]) -> dict[str, Any]:
    """백테스트 요약 1행을 넣고 `{id, created_at}` 을 돌려준다.

    `row` 는 `services/backtest.to_row` 가 만든 그대로다. 여기서 컬럼을 다시 나열하지
    않는 이유는 20개라 두 곳에 적으면 갈라지기 때문이다 — F04 는 12개라 인자로 풀어
    받았지만, 그 방식이 여기서는 실수를 부른다.
    """
    user_id = row.get("user_id")
    if user_id is not None:
        # 로그인 사용자인데 `app_user` 행이 아직 없으면 FK 가 터진다. 토큰 검증으로
        # `auth.users` 행의 존재는 이미 확인된 상태이므로 1:1 행을 만들어 준다.
        #
        # 트랜잭션이 갈라지지만 남는 것이 *빈 사용자 프로필 행* 이라 괜찮다는 판단은
        # `combination_repo.insert_combination` 에 적은 것과 같다.
        supabase_client.insert("app_user", {"id": user_id}, ignore_duplicates=True)

    rows = supabase_client.insert("backtest_summary", row, returning=True)
    saved = rows[0] if rows else None
    if not saved or saved.get("id") is None:
        raise supabase_client.SupabaseError(
            "백테스트 결과를 저장했으나 식별자를 돌려받지 못했습니다."
        )
    return {"id": int(saved["id"]), "created_at": saved["created_at"]}


def list_backtest_summaries(
    *, user_id: str | None, anon_id: str | None, limit: int
) -> list[dict[str, Any]]:
    """이력 목록을 `created_at desc` 로 돌려준다.

    소유자 조건을 OR 로 합치지 않는다 — 토큰이 있으면 `user_id`, 없으면 `anon_id`
    하나만 건다(`list_combinations` 와 같은 판단). 비로그인 이력이 로그인 계정에
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

    return [_normalize(row) for row in supabase_client.select("backtest_summary", params)]


def fetch_backtest_summary(backtest_id: int) -> dict[str, Any] | None:
    """단건을 읽는다. 없으면 `None`.

    소유자 컬럼(`user_id`·`anon_id`)을 함께 읽어 올린다. 조회 조건에 소유자를 섞지
    않는 이유는 라우터가 403(남의 행)과 404(없는 행)를 구분해야 하기 때문이다 —
    조건으로 걸러 버리면 둘 다 빈 결과가 되어 구분할 근거가 사라진다.
    """
    rows = supabase_client.select(
        "backtest_summary",
        {
            "select": _DETAIL_COLUMNS,
            "id": f"eq.{backtest_id}",
            "limit": "1",
        },
    )
    return _normalize(rows[0]) if rows else None
