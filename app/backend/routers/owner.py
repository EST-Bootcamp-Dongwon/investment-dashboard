"""요청 주체 판별 — Controller 계층 공용 헬퍼.

두 가지를 답한다. **`resolve_owner` 는 "이 요청은 누구 것인가"**(F03·F04·F05·F28 의
이력 저장), **`require_admin` 은 "이 사람이 색인을 고쳐도 되는가"**(F27 관리자 경로).

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
    from ..clients import admin_repo, supabase_client
except ImportError:  # `uvicorn main:app` 를 app/backend 에서 실행하는 경우
    from clients import admin_repo, supabase_client  # type: ignore

# anon_id 검증 상한이 /api/visitors/heartbeat(main.py:228, 16~80)와 다르다.
# recommendation·simulation_run 의 anon_id 는 DB 에서 64자 상한이라(테이블-정의서
# 4.2 · 4.5절), 80 으로 맞추면 pydantic 을 통과한 값이 DB 에서 터져 500 이 된다.
# 좁은 쪽에 맞춘다.
ANON_ID = {"min_length": 16, "max_length": 64, "pattern": r"^[A-Za-z0-9_-]+$"}

OWNER_REQUIRED = "로그인하거나 브라우저 식별자를 함께 보내 주세요."
TOKEN_INVALID = "로그인 정보가 유효하지 않습니다. 다시 로그인해 주세요."

ADMIN_REQUIRED = "관리자 로그인이 필요합니다."
ADMIN_FORBIDDEN = "관리자만 사용할 수 있는 기능입니다."


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


def require_admin(authorization: str | None, *, unavailable_detail: str) -> str:
    """관리자면 `user_id` 를 돌려주고, 아니면 막는다.

    `resolve_owner` 와 **형태가 다르다.** 그쪽은 `(user_id, anon_id)` 를 돌려주고 그
    값이 행에 저장되지만, 이쪽이 돌려주는 `user_id` 는 저장되는 곳이 없다 — `doc_chunk`
    에는 소유자 컬럼이 없기 때문이다. 돌려주는 이유는 **누가 색인을 고쳤는지 로그에
    남기기 위해서**이고, 그 로그가 지금은 서버 표준출력뿐이다.

    ## 비로그인은 관리자가 될 수 없다

    `anon_id` 를 아예 받지 않는다. 그 값은 브라우저가 스스로 만들어 보내는 문자열이라
    (테이블-정의서 6.2절이 인정한 한계) 권한 판정에 쓰면 아무나 관리자가 된다.
    토큰이 없으면 400(`OWNER_REQUIRED`)이 아니라 **401** 이다 — 익명 식별자를 더
    보낸다고 될 일이 아니라 로그인을 해야 하는 상황이라, 안내 문구가 달라야 한다.

    ## 코드 세 개를 구분한다

    | 코드 | 뜻 |
    | --- | --- |
    | 401 | 토큰이 없거나 유효하지 않다 → 로그인하면 된다 |
    | 403 | 로그인은 했는데 `app_admin` 에 없다 → 로그인해도 안 된다 |
    | 503 | 명단을 확인할 수 없다 (Supabase 장애·미설정) |

    **503 일 때 통과시키지 않는다.** 명단 조회가 실패했다는 것은 관리자인지 아닌지
    모른다는 뜻이고, 모를 때 여는 쪽으로 기울면 Supabase 를 끊는 것이 곧 권한 우회가
    된다. `SupabaseNotConfigured` 도 `SupabaseError` 라 같은 가지로 막힌다 — 환경변수를
    지우는 것으로 관리자 화면이 열리지 않는다.
    """
    if not (authorization and authorization.lower().startswith("bearer ") and authorization[7:].strip()):
        raise HTTPException(status_code=401, detail=ADMIN_REQUIRED)

    # 토큰 검증 실패(401)·Auth 장애(503)는 `resolve_owner` 가 이미 갈라 준다.
    user_id, _ = resolve_owner(authorization, None, unavailable_detail=unavailable_detail)
    if not user_id:
        raise HTTPException(status_code=401, detail=ADMIN_REQUIRED)

    try:
        listed = admin_repo.is_listed(user_id)
    except supabase_client.SupabaseError as exc:
        raise HTTPException(status_code=503, detail=unavailable_detail) from exc

    if not listed:
        raise HTTPException(status_code=403, detail=ADMIN_FORBIDDEN)
    return user_id
