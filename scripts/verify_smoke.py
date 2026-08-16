#!/usr/bin/env python3
"""G · 스모크 — `/api/health` 와 A등급 4개(F03·F04·F05·F27)가 200 을 내는가.

[테스트-계획 5.1절] 최소셋 7종 중 **G**. 가장 얕은 검사이고, 그래서 가장 먼저
돈다 — *"아무것도 안 뜬다"* 를 30초 안에 알려 주는 것이 목적이다.
응답의 **내용**은 보지 않는다. 그쪽은 기능별 `verify_*_api.py` 여섯 벌이 맡는다.

A등급 4개는 [기능ID-대장 등급 분포](docs/spec/00-index/기능ID-대장.md)의 그것이다 —
F03 포트폴리오 추천 · F04 조합 · F05 시뮬레이션 · F27 RAG 챗.

## 셋으로 나뉜다

    ① /api/health   — 빈 FastAPI 에 마운트해 실제로 200 을 받는다
    ② 라우터 경로    — 같은 방식으로 A등급 4개를 받는다
    ③ DB 가 필요한 것 — 자격증명이 있을 때만. 없으면 종료 코드 2

**`main.py` 를 띄우지 않는다.** import 시점에 `torch`·`diffusers`·`matplotlib` 를
끌어와 1.6GB 가 필요하다(`verify_simulation_api.py` 와 같은 이유). 대신 필요한
**라우터만 골라 빈 앱에 붙인다** — 그래서 검사가 30초 안에 끝난다.

2026-08-16 [CN-065](docs/spec/00-index/변경이력.md#cn-065) 분해 전까지 `/api/health` 는
`main.py:173` 에 있어서 ① 은 `ast` 로 함수만 떼어 내 부르는 우회로였다. 라우트가
`routers/system.py` 로 옮겨진 뒤 그 우회로를 걷고 ② 와 같은 방식으로 통일했다.

## 시세는 대역으로 바꾼다

F04 는 `yfinance` 를 탄다. 테스트-계획 5.2절이 *"외부 API 를 실제로 부르는 테스트는
넣지 않는다"* 고 정했으므로 `clients/yahoo_prices.download_closes` 를 가짜로 바꾼다
(`verify_combination_api.py:376` 과 같은 자리). **그래서 이 검사는 yfinance 연동이
살아 있는지는 말해 주지 않는다** — 라우팅·계산·직렬화까지다.

Supabase 는 반대다. 5.2절이 *"우리 인프라라 예외"* 로 두었고, F27 은 DB 없이는
답을 만들 수 없으므로 ③ 에서 원격을 실제로 부른다. **행을 만들지 않는다** —
읽기만 하므로 지울 잔여물도 없다.

## 실행

    .venv/bin/python scripts/verify_smoke.py

종료 코드 — 0 통과 · 1 실패 · 2 자격증명이 없어 ③ 을 건너뜀(①② 는 돌았다).
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
sys.path.insert(0, str(ROOT / "app" / "backend"))


def load_dotenv(path: Path) -> None:
    """`.env` 를 환경변수로. `verify_simulation_api.py:47` 과 같은 함수다."""
    if not path.exists():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


load_dotenv(ROOT / ".env")

import pandas as pd  # noqa: E402
from fastapi import FastAPI  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from clients import yahoo_prices  # noqa: E402
from routers.combination import router as combination_router  # noqa: E402
from routers.market import router as market_router  # noqa: E402
from routers.quant import router as quant_router  # noqa: E402
from routers.rag import router as rag_router  # noqa: E402
from routers.recommendation import router as recommendation_router  # noqa: E402
from routers.system import router as system_router  # noqa: E402

# `system` 과 `market` 은 CN-065 분해로 `main.py` 에서 갈라져 나온 라우터다.
# 그전에는 `main.py` 안에 있어 마운트할 수 없었고, 그래서 ① 과 ② 일부가 소스를
# 읽는 우회로를 썼다(각 섹션 주석 참고).
MOUNTED = (recommendation_router, combination_router, quant_router, rag_router,
           system_router, market_router)

app = FastAPI()
for router in MOUNTED:
    app.include_router(router)
client = TestClient(app, raise_server_exceptions=False)

results: list[tuple[str, str, str, str, bool]] = []


def brief(value) -> str:
    text = str(value)
    return text if len(text) <= 100 else text[:97] + "…"


def check(name: str, where: str, expected, got, extra: str = "") -> bool:
    """비교는 `==` 로 한다 (CN-098)."""
    ok = expected == got
    results.append((name, where, brief(expected), f"{brief(got)}{extra}", ok))
    return ok


# ─────────────────────────────────────────────────────────────────────────────
# 시세 대역 — F04 가 네트워크를 타지 않게
# ─────────────────────────────────────────────────────────────────────────────

#: `services/combination.MIN_HISTORY`(21) · `MIN_OVERLAP`(20) 을 넉넉히 넘긴다.
#: 값이 아니라 "200 이 나오는가" 를 보는 검사라 시세 모양은 중요하지 않다.
_INDEX = pd.bdate_range("2025-01-01", periods=60)
FIXTURES = {
    "AAPL": pd.Series([100.0 + i * 0.5 for i in range(60)], index=_INDEX),
    "JNJ": pd.Series([80.0 + (i % 7) * 0.4 for i in range(60)], index=_INDEX),
}


def fake_download(tickers, period):
    """`clients/yahoo_prices.download_closes` 와 같은 계약 (`verify_combination_api.py:364`)."""
    closes, unavailable = {}, []
    for ticker in tickers:
        series = FIXTURES.get(ticker)
        if series is None:
            unavailable.append(ticker)
        else:
            closes[ticker] = series
    return closes, unavailable


yahoo_prices.download_closes = fake_download


# ─────────────────────────────────────────────────────────────────────────────
# ① /api/health — 실제로 마운트해 200 을 받는다
# ─────────────────────────────────────────────────────────────────────────────
#
# **2026-08-16 에 이 섹션이 승격됐다.** 그전까지는 `/api/health` 가 `main.py:173` 에
# 있었고, `main.py` 는 import 하면 `torch`·`diffusers` 를 끌어와 1.6GB 가 필요했다.
# 그래서 `ast` 로 함수 정의만 떼어 내 빈 전역에서 부르고, 경로·메서드는 데코레이터
# 소스에서 따로 읽어 대조하는 우회로를 썼다.
#
# [CN-065](docs/spec/00-index/변경이력.md#cn-065) 분해 순서 ⑤~⑦ 이 이 라우트를
# `routers/system.py` 로 옮기면서 **그 우회로가 필요 없어졌다.** 이제 ② 와 똑같이
# 라우터를 빈 FastAPI 에 붙여 실제 요청을 보낸다. 떼어 내 부르던 때보다 검사가
# 강하다 — 경로·메서드·응답을 따로 대조하지 않고 **한 번의 왕복으로 전부 확인**한다.

HEALTH_PATH = "/api/health"


def verify_health() -> None:
    response = client.get(HEALTH_PATH)
    check("① GET /api/health 가 200", "TestClient", 200, response.status_code,
          "" if response.status_code == 200 else f"  {response.text[:120]}")
    if response.status_code != 200:
        return

    check("① /api/health 응답", "TestClient", {"status": "ok"}, response.json())

    # POST 로는 열리지 않아야 한다. GET 으로 선언됐는지를 왕복으로 확인하는 방법이다.
    check("① POST 는 405", "TestClient", 405, client.post(HEALTH_PATH).status_code)


# ─────────────────────────────────────────────────────────────────────────────
# ② 라우터 경로 — 실제로 200 을 받는다
# ─────────────────────────────────────────────────────────────────────────────

#: 화면이 그 기능을 처음 열 때 부르는 경로 하나씩. DB 를 타지 않는 것만 여기 둔다.
OFFLINE_CALLS = (
    ("F03", "POST", "/api/recommendation/preview",
     {"goal": "balance", "horizon": "medium", "risk": "medium"}),
    ("F04", "POST", "/api/combination/preview",
     {"ticker_a": "AAPL", "ticker_b": "JNJ", "period": "1y"}),
    ("F05", "POST", "/api/quant/portfolio-scenario",
     {"profile": "balanced", "initial_amount": 10_000_000,
      "monthly_amount": 500_000, "years": 10}),
)


def call(method: str, path: str, body=None):
    return client.post(path, json=body) if method == "POST" else client.get(path)


def verify_offline_routes() -> None:
    for fid, method, path, body in OFFLINE_CALLS:
        response = call(method, path, body)
        check(f"② {fid} {method} {path}", "TestClient", 200, response.status_code,
              "" if response.status_code == 200 else f"  {response.text[:120]}")

    # 응답이 빈 껍데기면 200 이어도 화면이 아무것도 못 그린다. 얕게 한 겹만 본다.
    empty = [
        f"{fid} {path}"
        for fid, method, path, body in OFFLINE_CALLS
        if not (call(method, path, body).json() or {})
    ]
    check("② 응답이 비어 있지 않다", "TestClient", [], empty)


def verify_declared_routes() -> None:
    """대장이 적은 A등급 경로가 실제로 선언돼 있는가.

    `app.routes` 를 훑지 않는다. fastapi 0.141.1 은 `include_router` 로 붙인 것을
    `_IncludedRouter` 로 감싸 두고 **`path` 도 `methods` 도 주지 않는다**
    (2026-08-16 실측 — `app.routes` 에는 `/docs` 계열 4개와 감싼 것 4개뿐).
    `APIRouter.routes` 쪽은 접두사가 붙은 완전한 경로를 그대로 들고 있다.
    """
    mounted = {
        (method, route.path)
        for router in MOUNTED
        for route in router.routes
        for method in getattr(route, "methods", ())
    }
    expected = {
        ("POST", "/api/recommendation/preview"), ("POST", "/api/recommendation/create"),
        ("GET", "/api/recommendation/history"), ("GET", "/api/recommendation/detail"),
        ("POST", "/api/combination/preview"), ("POST", "/api/combination/create"),
        ("GET", "/api/combination/history"), ("GET", "/api/combination/detail"),
        ("POST", "/api/quant/portfolio-scenario"),
        ("POST", "/api/rag/ask"), ("GET", "/api/rag/status"),
    }
    check("② A등급 라우터 경로 11개가 선언돼 있다", "routers/", [], sorted(expected - mounted))

    # 대장이 F04 로 적어 둔 옛 경로. 2026-08-16 까지는 `main.py` 에 있어 마운트할 수
    # 없었고 소스 문자열로만 확인했는데, CN-065 분해가 `routers/market.py` 로 옮겨
    # **실제 마운트로 확인**할 수 있게 됐다. 사라지면 화면(`api.js:57`)이 404 를 받는다.
    check("② F04 옛 경로가 살아 있다", "routers/market.py", True,
          ("POST", "/api/market/portfolio-combination") in mounted)

    # CN-028 이 삭제를 확정한 경로. 되살아나면 결정이 뒤집힌 것이다.
    check("② 삭제 확정된 /api/rag/search 가 없다", "routers/rag.py", 404,
          client.post("/api/rag/search", json={"query": "PER"}).status_code)


# ─────────────────────────────────────────────────────────────────────────────
# ③ DB 가 필요한 것 — 자격증명이 있을 때만
# ─────────────────────────────────────────────────────────────────────────────

def verify_online_routes() -> None:
    status = client.get("/api/rag/status")
    check("③ F27 GET /api/rag/status", "TestClient", 200, status.status_code)

    store = status.json().get("vector_store", {}) if status.status_code == 200 else {}
    check("③ 벡터 저장소가 붙어 있다", "/api/rag/status", True, store.get("available"))
    check("③ 색인이 비어 있지 않다", "/api/rag/status", True, store.get("indexed"),
          f"  ({store.get('total_chunks')}청크 · 문서 {store.get('document_count')}개)")

    ask = client.post("/api/rag/ask", json={"query": "PER이 무엇인가요?"})
    check("③ F27 POST /api/rag/ask", "TestClient", 200, ask.status_code,
          "" if ask.status_code == 200 else f"  {ask.text[:120]}")
    if ask.status_code == 200:
        body = ask.json()
        check("③ 답변과 근거가 함께 온다", "/api/rag/ask", (True, True),
              (bool(body.get("answer")), len(body.get("sources") or []) > 0))
        # R-07 — 면책은 응답에도 붙는다 (CN-060 · investment-disclaimer-required).
        check("③ 응답에 면책이 있다", "/api/rag/ask", True, bool(body.get("disclaimer")))

    # F03 읽기 경로. 없는 소유자로 물어도 200 + 빈 목록이어야 한다.
    history = client.get("/api/recommendation/history",
                         params={"anon_id": "smokeownerAAAAAAAAAAAAAAAAAAAAAA"})
    check("③ F03 GET /api/recommendation/history", "TestClient", 200, history.status_code,
          "" if history.status_code == 200 else f"  {history.text[:120]}")


def main() -> int:
    verify_health()
    verify_declared_routes()
    verify_offline_routes()

    configured = bool(os.environ.get("SUPABASE_URL")) and bool(
        os.environ.get("SUPABASE_SERVICE_ROLE_KEY")
    )
    if configured:
        verify_online_routes()

    width = max(len(name) for name, *_ in results)
    print()
    for name, where, expected, got, ok in results:
        print(f"[{'OK ' if ok else 'FAIL'}] {name:<{width}}  {where}")
        if not ok:
            print(f"        기대: {expected}")
            print(f"        실측: {got}")

    passed = sum(1 for *_, ok in results if ok)
    print(f"\n{passed} / {len(results)} 통과")

    if not configured:
        print("③ 을 건너뛰었습니다 — .env 에 SUPABASE_URL·SUPABASE_SERVICE_ROLE_KEY 가 필요합니다.")
        return 2 if passed == len(results) else 1
    return 0 if passed == len(results) else 1


if __name__ == "__main__":
    raise SystemExit(main())
