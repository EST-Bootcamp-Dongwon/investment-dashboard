"""관리자 명단 조회 — Repository.

`app_admin` 테이블(마이그레이션 20260814120000) 한 곳만 읽는다.

**이 파일에는 판정이 없다.** "이 사람이 명단에 있는가" 만 답하고, 그래서 무엇을
허가할지는 `routers/owner.require_admin` 이 정한다. repo 가 `bool` 을 주는 것이
도메인 판단처럼 보일 수 있지만, 여기서 하는 일은 *행이 있는가* 이지 *권한이 있는가*
가 아니다 — 명단에 있다는 사실과 그것이 권한을 뜻한다는 해석은 다른 층의 일이다.
"""

from __future__ import annotations

try:
    from . import supabase_client
except ImportError:  # `uvicorn main:app` 를 app/backend 에서 실행하는 경우
    import clients.supabase_client as supabase_client  # type: ignore


def is_listed(user_id: str) -> bool:
    """`app_admin` 에 이 사용자 행이 있는지.

    `select=user_id` 로 최소 컬럼만 읽는다. `note` 는 사람이 읽을 메모라 판정에
    필요 없고, 응답에 실어 나를 이유도 없다.

    `app_admin` 에는 RLS 정책이 하나도 없으므로 이 조회는 **service_role 로만**
    성공한다. anon 키로는 0행이 온다 — 명단 자체가 밖으로 새지 않는다.
    """
    rows = supabase_client.select(
        "app_admin",
        {"select": "user_id", "user_id": f"eq.{user_id}", "limit": "1"},
    )
    return bool(rows)
