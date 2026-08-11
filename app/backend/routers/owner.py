"""소유자 판별 — Controller 계층 공용 헬퍼.

토큰이 있으면 `user_id` 기준, 없으면 `anon_id` 기준으로 이 요청의 소유자를 정한다.
F03(`recommendation.py`)이 처음 쓴 코드를 F05(`simulation.py`)가 두 번째로 쓰게 되어
여기로 뽑았다. **두 번째 사본이 생기는 시점에 뽑는 이유**는 이 판별이 소유권 판정이라,
사본이 갈라지면 한쪽만 고쳐진 채 남의 이력이 보이는 결함이 되기 때문이다.

`services/` 가 아니라 `routers/` 에 두는 것은 이 함수가 `HTTPException` 을 던지기
때문이다. 아키텍처 2.1절이 `services/` 는 HTTP 를 모른다고 못박고 있어 자리가 맞지 않는다.
"""

from __future__ import annotations

from fastapi import HTTPException

try:
    from ..clients import supabase_client
except ImportError:  # `uvicorn main:app` 를 app/backend 에서 실행하는 경우
    from clients import supabase_client  # type: ignore

# anon_id 검증 상한이 /api/visitors/heartbeat(main.py:228, 16~80)와 다르다.
# recommendation·simulation_run 의 anon_id 는 DB 에서 64자 상한이라(테이블-정의서
# 4.2 · 4.5절), 80 으로 맞추면 pydantic 을 통과한 값이 DB 에서 터져 500 이 된다.
# 좁은 쪽에 맞춘다.
ANON_ID = {"min_length": 16, "max_length": 64, "pattern": r"^[A-Za-z0-9_-]+$"}

OWNER_REQUIRED = "로그인하거나 브라우저 식별자를 함께 보내 주세요."
TOKEN_INVALID = "로그인 정보가 유효하지 않습니다. 다시 로그인해 주세요."


def resolve_owner(
    authorization: str | None,
    anon_id: str | None,
    *,
    unavailable_detail: str,
) -> tuple[str | None, str | None]:
    """`(user_id, anon_id)` 를 돌려준다. 둘 중 하나만 채워진다.

    둘을 OR 로 합치지 않는다 — 비로그인 이력이 로그인 계정에 자동 병합되면 소유
    관계가 흐려진다. 병합이 필요하면 별도 기능으로 다룬다.

    `ck_*_owner` 가 둘 중 하나는 NOT NULL 이길 요구하므로, 둘 다 없으면 여기서 400 으로
    막는다. DB 제약 위반을 500 으로 흘리지 않는다.

    `unavailable_detail` 만 호출자가 넘긴다. Auth 서버 장애는 503 인데 그때 보여줄
    문구가 기능마다 다르기 때문이다("추천 이력을…" / "시뮬레이션 결과를…").
    401 문구는 기능과 무관하게 같아서 상수로 둔다.
    """
    token = ""
    if authorization and authorization.lower().startswith("bearer "):
        token = authorization[7:].strip()

    if token:
        try:
            return supabase_client.auth_user_id(token), None
        except supabase_client.SupabaseAuthError as exc:
            raise HTTPException(status_code=401, detail=TOKEN_INVALID) from exc
        except supabase_client.SupabaseError as exc:
            raise HTTPException(status_code=503, detail=unavailable_detail) from exc

    if anon_id:
        return None, anon_id

    raise HTTPException(status_code=400, detail=OWNER_REQUIRED)
