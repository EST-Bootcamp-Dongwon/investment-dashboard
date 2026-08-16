"""FastAPI 앱 조립부.

[CN-065](../../docs/spec/00-index/변경이력.md#cn-065) 분해 순서 ⑦. **이 파일은 앱을 만들고,
미들웨어를 걸고, 라우터를 붙이는 일만 한다.** 라우트도 계산도 여기 없다.

## 2,693줄에서 여기까지

2026-08-10 AST 해부(CN-065)가 센 것은 라우트 핸들러 22개 1,710줄 · 헬퍼 17개 525줄 ·
Pydantic 모델 15개 60줄이었고, 그것이 백엔드 전체의 **49.7 %** 였다. 분해 순서
①~④ 는 중복 제거 · 이중 import 정리 · `clients/` 신설 · F03 신설로 본보기를
만드는 데까지였고, ⑤~⑦ 이 남아 있었다. 이 파일이 그 ⑦ 이다.

라우트 22개는 주제별로 일곱 갈래로 갈라졌다 — `routers/system.py` ·`dart.py` ·
`industry.py` ·`market.py` ·`macro.py` ·`finance.py` ·`home.py`. 각 라우터는 경로
선언과 요청 검증만 하고, 본문은 같은 이름의 `services/` 모듈에 있다.

## 조립부에 남긴 것과 그 이유

- **미들웨어 셋** — GZip · CORS · `no_cache_static_assets`. 앱 전체에 걸리는
  것이라 특정 라우터에 속하지 않는다.
- **`DomainError` 번역기** — 서비스 계층은 HTTP 를 모르므로
  (`services/errors.py`) 상태 코드로 옮기는 일을 **여기 한 곳**에서 한다.
  라우터마다 `try/except` 를 두면 빠뜨린 곳이 500 으로 샌다.
- **정적 파일 mount** — `"/"` 에 걸리므로 **반드시 맨 마지막**이어야 한다.
  위로 올리면 모든 API 경로를 정적 파일 처리기가 먼저 먹는다.

## 여기서 사라진 것

`DOCS_DIR` 은 아무도 읽지 않아 지웠다(`routers/admin.py:60` 이 자기 몫을 따로
계산한다). `GENERATED_DIR` 과 그 `mkdir` 도 지웠다 — 쓰는 쪽인 `routers/ml.py:18~20`
과 `routers/backtest_lab.py:55` 가 각자 정의하고 있어서 여기 것은 죽은 코드였다.
[CN-068](../../docs/spec/00-index/변경이력.md#cn-068) 이 콜드 스타트 위험으로 지목한
`main.py:54` 는 그래서 이 파일에서 없어졌다. **`ml.py:20` 쪽은 그대로 남아 있다** —
그쪽은 CN-068 의 조치(`/tmp` 이동) 대상이고 이번 작업 범위가 아니다.
"""

from __future__ import annotations

from pathlib import Path

from dotenv import load_dotenv

load_dotenv(Path(__file__).parent / ".env")

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.responses import JSONResponse, Response
from fastapi.staticfiles import StaticFiles

try:
    from .openapi_docs import install_openapi
    from .services.errors import DomainError
except ImportError:  # `uvicorn main:app` 를 app/backend 에서 실행하는 경우
    from openapi_docs import install_openapi  # type: ignore
    from services.errors import DomainError  # type: ignore

try:
    import orjson
except ImportError:
    DEFAULT_RESPONSE_CLASS = JSONResponse
else:
    class FastORJSONResponse(Response):
        media_type = "application/json"

        def render(self, content: object) -> bytes:
            return orjson.dumps(content)

    DEFAULT_RESPONSE_CLASS = FastORJSONResponse

ROOT_DIR = Path(__file__).resolve().parents[2]
FRONTEND_DIR = ROOT_DIR / "app" / "frontend"


app = FastAPI(
    title="Python Education Cloud API",
    version="2.0.0",
    description=(
        "주식 투자 입문 가이드"
    ),
    default_response_class=DEFAULT_RESPONSE_CLASS,
)

app.add_middleware(GZipMiddleware, minimum_size=1024)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def no_cache_static_assets(request, call_next):
    """Always fetch the latest local HTML, JavaScript, and CSS on page load.

    StaticFiles normally uses ETag/Last-Modified revalidation. The learning
    app is deployed as a single image, so an old shell or module can otherwise
    survive a deployment in a browser cache. ``no-store`` plus legacy
    revalidation headers makes local frontend assets non-cacheable for both
    browsers and intermediary proxies.
    """
    response = await call_next(request)
    path = request.url.path
    if path == "/" or path.endswith((".html", ".js", ".css")):
        response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
        response.headers["Pragma"] = "no-cache"
        response.headers["Expires"] = "0"
    return response


@app.exception_handler(DomainError)
async def domain_error_handler(request, exc: DomainError) -> JSONResponse:
    """도메인 실패를 HTTP 응답으로 옮긴다.

    본문 모양(`{"detail": ...}`)은 FastAPI 가 `HTTPException` 에 쓰는 것과 같다.
    분해 전 이 앱이 내보내던 응답과 **한 글자도 다르지 않아야** 화면
    (`app/frontend/js/api.js`)의 오류 처리가 그대로 동작한다.
    """
    return JSONResponse(status_code=exc.status_code, content={"detail": exc.detail})


try:
    from .routers.admin import router as admin_router
    from .routers.backtest_lab import router as backtest_lab_router
    from .routers.combination import router as combination_router
    from .routers.dart import router as dart_router
    from .routers.finance import router as finance_router
    from .routers.home import router as home_router
    from .routers.industry import router as industry_router
    from .routers.macro import router as macro_router
    from .routers.market import router as market_router
    from .routers.ml import router as ml_router
    from .routers.quant import router as quant_router
    from .routers.rag import router as rag_router
    from .routers.recommendation import router as recommendation_router
    from .routers.simulation import router as simulation_router
    from .routers.system import router as system_router
    from .routers.tax import router as tax_router
except ImportError:  # Allows `uvicorn main:app` from app/backend.
    from routers.admin import router as admin_router  # type: ignore
    from routers.backtest_lab import router as backtest_lab_router  # type: ignore
    from routers.combination import router as combination_router  # type: ignore
    from routers.dart import router as dart_router  # type: ignore
    from routers.finance import router as finance_router  # type: ignore
    from routers.home import router as home_router  # type: ignore
    from routers.industry import router as industry_router  # type: ignore
    from routers.macro import router as macro_router  # type: ignore
    from routers.market import router as market_router  # type: ignore
    from routers.ml import router as ml_router  # type: ignore
    from routers.quant import router as quant_router  # type: ignore
    from routers.rag import router as rag_router  # type: ignore
    from routers.recommendation import router as recommendation_router  # type: ignore
    from routers.simulation import router as simulation_router  # type: ignore
    from routers.system import router as system_router  # type: ignore
    from routers.tax import router as tax_router  # type: ignore

# 분해로 새로 생긴 일곱. 경로는 옮기기 전과 같다(`scripts/check_routes.py` 가 68개를 지킨다).
app.include_router(system_router)
app.include_router(dart_router)
app.include_router(industry_router)
app.include_router(market_router)
app.include_router(macro_router)
app.include_router(finance_router)
app.include_router(home_router)

# 분해 전부터 있던 아홉.
app.include_router(ml_router)
app.include_router(quant_router)
app.include_router(backtest_lab_router)
app.include_router(recommendation_router)
app.include_router(simulation_router)
app.include_router(combination_router)
app.include_router(tax_router)
app.include_router(rag_router)
app.include_router(admin_router)

install_openapi(app)

# ─────────────────────────────────────────────────────────────────────────────
# 반드시 맨 마지막이다. `"/"` 에 걸리므로 위로 올리면 API 경로를 먼저 가로챈다.

app.mount("/", StaticFiles(directory=FRONTEND_DIR, html=True), name="frontend")
