"""Supabase(PostgREST · Auth) 연동 계층.

docs/spec/60-운영/아키텍처.md 2.1절의 `clients/` 계층이다. 외부 호출과 응답 파싱만
하고 도메인 판단은 하지 않으며, `HTTPException` 을 던지지 않는다.

**표준 라이브러리 `urllib` 로 부른다.** `supabase-py` 를 쓰지 않는 이유는 번들 크기다.
Vercel Python 함수의 상한이 500MB 인데 현재 의존성만으로 이미 429.8MB 이고(D-10),
`supabase-py` 는 `httpx`·`gotrue`·`postgrest`·`realtime`·`storage3` 를 함께 끌고 온다.
쓰는 기능이 REST 호출 세 종류뿐이라 표준 라이브러리로 충분하다.
같은 이유로 `main.py:264~296` 의 DART 호출도 `urlopen` 을 쓴다.

**service_role 키로 부른다.** 비로그인 이력은 RLS 로 막을 수 없어(테이블-정의서 6.2절)
서버가 대신 조회하는 구조이고, 그 전제가 service_role 이다.
이 키는 서버 환경변수로만 두며 프론트에 내려가면 RLS 가 전부 무력화된다.
"""

from __future__ import annotations

import json
import os
import urllib.error
import urllib.parse
import urllib.request
from typing import Any

# 서버리스 콜드 스타트에서 무한정 매달리지 않게 한다. Supabase 무료 플랜은
# 일정 시간 요청이 없으면 프로젝트가 쉬었다 깨어나므로 첫 요청이 느릴 수 있다.
_TIMEOUT_SECONDS = 10


class SupabaseError(Exception):
    """Supabase 연결·질의 실패. 라우터가 503 으로 번역한다."""


class SupabaseAuthError(Exception):
    """액세스 토큰 검증 실패. 라우터가 401 로 번역한다."""


class SupabaseNotConfigured(SupabaseError):
    """SUPABASE_URL·SUPABASE_SERVICE_ROLE_KEY 가 없다.

    `SupabaseError` 를 상속하므로 라우터는 따로 다루지 않아도 503 이 된다.
    미설정과 장애를 사용자 입장에서 구분할 이유가 없다 — 둘 다 "지금은 저장할 수 없다" 다.
    """


def _base_url() -> str:
    return (os.getenv("SUPABASE_URL") or "").rstrip("/")


def _service_key() -> str:
    return os.getenv("SUPABASE_SERVICE_ROLE_KEY") or ""


def is_configured() -> bool:
    """두 환경변수가 모두 있는지. 화면이 저장 기능을 켤지 결정하는 데 쓴다."""
    return bool(_base_url() and _service_key())


def _request(
    method: str,
    url: str,
    *,
    headers: dict[str, str],
    body: dict[str, Any] | None = None,
) -> Any:
    payload = json.dumps(body).encode("utf-8") if body is not None else None
    req = urllib.request.Request(url, data=payload, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=_TIMEOUT_SECONDS) as res:
            raw = res.read()
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", "replace")[:500]
        raise SupabaseError(f"Supabase {method} {exc.code}: {detail}") from exc
    except urllib.error.URLError as exc:
        raise SupabaseError(f"Supabase 연결 실패: {exc.reason}") from exc
    except OSError as exc:  # 타임아웃은 socket.timeout(OSError) 로 온다
        raise SupabaseError(f"Supabase 응답 지연: {exc}") from exc

    if not raw:
        return None
    try:
        return json.loads(raw)
    except json.JSONDecodeError as exc:
        raise SupabaseError("Supabase 응답을 JSON 으로 읽을 수 없습니다.") from exc


def _rest_headers() -> dict[str, str]:
    key = _service_key()
    if not (_base_url() and key):
        raise SupabaseNotConfigured(
            "SUPABASE_URL 과 SUPABASE_SERVICE_ROLE_KEY 가 설정되지 않았습니다."
        )
    return {
        "apikey": key,
        "Authorization": f"Bearer {key}",
        "Content-Type": "application/json",
        "Accept": "application/json",
    }


def rpc(function_name: str, params: dict[str, Any]) -> Any:
    """Postgres 함수를 호출한다.

    여러 테이블에 걸친 삽입을 한 트랜잭션으로 묶는 유일한 방법이다.
    PostgREST 의 테이블 삽입은 요청 하나가 트랜잭션 하나라, 부모와 자식을 따로
    넣으면 자식이 실패했을 때 고아 부모 행이 남는다.
    """
    url = f"{_base_url()}/rest/v1/rpc/{urllib.parse.quote(function_name)}"
    return _request("POST", url, headers=_rest_headers(), body=params)


def select(table: str, params: dict[str, str]) -> list[dict[str, Any]]:
    """PostgREST 조회. `params` 는 PostgREST 질의 문법 그대로다."""
    query = urllib.parse.urlencode(params, quote_via=urllib.parse.quote)
    url = f"{_base_url()}/rest/v1/{urllib.parse.quote(table)}?{query}"
    rows = _request("GET", url, headers=_rest_headers())
    return rows if isinstance(rows, list) else []


def auth_user_id(access_token: str) -> str:
    """액세스 토큰을 검증하고 사용자 id(`sub`)를 돌려준다.

    서명을 직접 검증하지 않고 Auth 서버에 되묻는다. 직접 검증하려면 JWT 라이브러리와
    JWT 시크릿(또는 JWKS 캐시)이 필요한데, 지금 인증 코드가 0건이라 그 기반이 없다.
    토큰이 실제로 있을 때만 한 번 더 부르는 비용이고, 취소된 토큰까지 걸러낸다.
    """
    key = _service_key()
    if not (_base_url() and key):
        raise SupabaseNotConfigured(
            "SUPABASE_URL 과 SUPABASE_SERVICE_ROLE_KEY 가 설정되지 않았습니다."
        )
    url = f"{_base_url()}/auth/v1/user"
    headers = {
        "apikey": key,
        "Authorization": f"Bearer {access_token}",
        "Accept": "application/json",
    }
    try:
        data = _request("GET", url, headers=headers)
    except SupabaseError as exc:
        # 401·403 은 토큰 문제이고, 그 밖(5xx·연결 실패)은 Supabase 장애다.
        # 둘을 같은 코드로 뭉뚱그리면 사용자가 재로그인해야 하는지 알 수 없다.
        message = str(exc)
        if "Supabase GET 401" in message or "Supabase GET 403" in message:
            raise SupabaseAuthError("액세스 토큰이 유효하지 않습니다.") from exc
        raise

    user_id = (data or {}).get("id")
    if not user_id:
        raise SupabaseAuthError("액세스 토큰에서 사용자를 확인할 수 없습니다.")
    return str(user_id)
