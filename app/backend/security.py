"""CORS 화이트리스트와 보안 응답 헤더.

[보안과-시크릿 2절·3절](../../docs/spec/60-운영/보안과-시크릿.md)을 코드로 옮긴 것이다.
`main.py` 에 두지 않은 이유는 하나뿐이다 — 그 파일은 **200줄 미만**이어야 하고
(`scripts/check_layers.py` 규칙 1), 지금 190줄이다.

## 1. CORS — 지금 상태가 왜 나쁜가

`main.py` 는 `allow_origins=["*"]` 와 `allow_credentials=True` 를 함께 하드코딩하고
있었다. 보안과-시크릿 3.2절이 실제 응답으로 확인한 결과는 나쁜 쪽이다.

    $ curl -H "Origin: https://evil.example.com" .../api/health
    access-control-allow-origin: https://evil.example.com   ← * 가 아니라 에코
    access-control-allow-credentials: true

Starlette 는 `*` 를 그대로 보내지 않고 **요청한 오리진을 되돌려준다.** 브라우저는
`*` + credentials 조합은 거부하지만 **구체적 오리진 + credentials 는 허용한다.**
즉 "임의의 사이트가 자격증명을 실어 이 API 를 부를 수 있는" 구조가 이미 완성돼 있다.
훔칠 것이 아직 없을 뿐이다(인증 코드 0건).

**화이트리스트가 비면 아무 오리진도 허용하지 않는 것이 기본값이다.** 동일 출처
배포에서는 브라우저가 CORS 를 태우지 않으므로 이 기본값으로 아무것도 깨지지 않는다.

## 2. 헤더 5종 중 4종

보안과-시크릿 2.2절의 표 그대로다. **`Strict-Transport-Security` 는 넣지 않는다** —
같은 절이 명시적으로 뺐다. Vercel 이 HTTPS 를 종단하며 자체로 붙이고, 애플리케이션이
중복 선언하면 로컬 HTTP 개발이 깨진다.

## 3. CSP 는 단계로 간다 — 그리고 2단계 값에 구멍이 넷이었다

보안과-시크릿 2.3절이 적은 2단계 값은 이랬다.

    default-src 'self'; img-src 'self' data:;
    frame-src https://www.youtube.com; style-src 'self' 'unsafe-inline'

**이대로 켜면 화면이 깨진다.** `index.html:10~12,154` 를 실측하면 외부 출처가 셋이다.

| 무엇 | 어디서 | 없으면 |
| --- | --- | --- |
| ApexCharts | `cdn.jsdelivr.net` | **차트가 하나도 안 그려진다** (ADR-DB-0002 의 목적지) |
| Pretendard 웹폰트 | `cdn.jsdelivr.net` | 서체가 폴백으로 떨어진다 |
| Font Awesome | `cdnjs.cloudflare.com` | 아이콘이 전부 □ 가 된다 |

지시어로 옮기면 **`script-src`·`style-src`(호스트)·`font-src`·`connect-src` 넷**이
빠져 있었다. 넷 다 `default-src 'self'` 로 떨어져 차단된다. `connect-src` 가 없다는
지적은 이 중 하나였을 뿐이고, 나머지 셋도 같은 이유로 빠져 있었다.

`connect-src` 에는 **`CORS_ORIGINS` 를 그대로 얹는다.** 교차 출처로 가는 순간
서버가 허용하는 오리진과 브라우저가 허용하는 오리진이 같아야 하는데, 두 곳에 따로
적으면 반드시 갈라진다. 한 환경변수에서 둘을 만든다.

## 4. 켜고 끄기

    CSP_MODE=report-only   기본. `Content-Security-Policy-Report-Only` 로 관찰만 (1단계)
    CSP_MODE=enforce       실제로 막는다 (2단계)
    CSP_MODE=off           헤더를 붙이지 않는다

기본을 `report-only` 로 둔 것은 2.3절이 *"1단계: v2.0 배포와 동시"* 로 정했기
때문이다. 위반 목록을 본 뒤 `enforce` 로 올린다.
"""

from __future__ import annotations

import os

from fastapi.middleware.cors import CORSMiddleware

# 라우트 51개가 전부 GET·POST 다(API-목록). DELETE·PATCH·PUT 을 허용할 이유가 없다.
ALLOWED_METHODS = ["GET", "POST"]
ALLOWED_HEADERS = ["Content-Type"]

# 실측 출처(`index.html:10~12,154`). 여기에 없는 호스트를 HTML 에 더하면 CSP 를
# `enforce` 로 올린 날 그것만 조용히 막힌다 — 더할 때 이 목록도 함께 고친다.
_CDN_SCRIPT = ("https://cdn.jsdelivr.net",)
_CDN_STYLE = ("https://cdn.jsdelivr.net", "https://cdnjs.cloudflare.com")
_CDN_FONT = ("https://cdn.jsdelivr.net", "https://cdnjs.cloudflare.com")

SECURITY_HEADERS = {
    "X-Content-Type-Options": "nosniff",
    "X-Frame-Options": "DENY",
    "Referrer-Policy": "strict-origin-when-cross-origin",
    "Permissions-Policy": "geolocation=(), microphone=(), camera=()",
}


def cors_origins() -> list[str]:
    """`CORS_ORIGINS` 를 목록으로. 비어 있으면 **빈 목록**이다(= 아무 오리진도 불가).

    로컬 `.env` 나 compose 에서 `http://localhost:8000` 처럼 준다. 콤마로 여럿.
    """
    raw = os.getenv("CORS_ORIGINS", "")
    return [origin.strip() for origin in raw.split(",") if origin.strip()]


def csp_policy(extra_connect: list[str] | None = None) -> str:
    """2단계 CSP 문자열. `connect-src` 에 교차 출처 백엔드를 얹는다."""
    connect = ["'self'", *(extra_connect or [])]
    return "; ".join(
        (
            "default-src 'self'",
            "base-uri 'self'",
            "object-src 'none'",
            "frame-ancestors 'none'",
            "img-src 'self' data:",
            # base64 차트 16곳이 `data:` 를 쓴다(CN-033). 프런트 렌더로 옮기면 줄어든다.
            f"script-src 'self' {' '.join(_CDN_SCRIPT)}",
            # 인라인 `style=` 1,126개(CN-056)를 정리하기 전에는 뺄 수 없다 → 3단계 과제.
            f"style-src 'self' 'unsafe-inline' {' '.join(_CDN_STYLE)}",
            f"font-src 'self' data: {' '.join(_CDN_FONT)}",
            f"connect-src {' '.join(connect)}",
            "frame-src https://www.youtube.com",
        )
    )


def install(app) -> None:
    """CORS 미들웨어와 보안 헤더 미들웨어를 건다. `main.py` 가 한 번 부른다."""
    origins = cors_origins()

    app.add_middleware(
        CORSMiddleware,
        allow_origins=origins,
        allow_credentials=True,
        allow_methods=ALLOWED_METHODS,
        allow_headers=ALLOWED_HEADERS,
    )

    mode = os.getenv("CSP_MODE", "report-only").strip().lower()
    policy = csp_policy(origins)
    csp_header = {
        "enforce": "Content-Security-Policy",
        "report-only": "Content-Security-Policy-Report-Only",
    }.get(mode)

    @app.middleware("http")
    async def _security_headers(request, call_next):
        response = await call_next(request)
        for key, value in SECURITY_HEADERS.items():
            response.headers[key] = value
        if csp_header:
            response.headers[csp_header] = policy
        return response
