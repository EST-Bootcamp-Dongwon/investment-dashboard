#!/usr/bin/env python3
"""F05 시뮬레이션 API 4개를 **원격 Supabase 에 대고** 왕복 검증한다.

`scripts/verify_recommendation_api.py`(F03 · 34건)와 같은 틀이다. 다른 점은 하나 —
**F05 는 기존 구현이 이미 있다.** `POST /api/quant/portfolio-scenario`(`quant.py:60`)가
같은 계산을 하고 있고, 이 세션이 한 일은 그 계산을 `services/simulation.py` 로 옮겨
저장 경로를 붙인 것이다. 그래서 이 스크립트는 상태 코드 계약뿐 아니라
**두 경로가 같은 값을 내는지**를 먼저 확인한다 (검사 10~13번).

검사 42건 = 두 경로 대조 4 + 응답 계약 15 + 에러표 15 + 왕복 대조 8.

## main.py 를 띄우지 않는다

`app/backend/main.py` 는 `torch`·`diffusers`·`matplotlib` 를 import 시점에 끌어와,
이 검증만을 위해 1.6GB 를 설치해야 한다. 대신 **라우터만 빈 FastAPI 에 마운트**한다.
경로 선언·요청 검증·예외 번역이 전부 `routers/simulation.py` 안에 있고, `main.py` 에는
`@app.exception_handler` 가 **0건**이라(2026-08-11 grep) 상태 코드 계약은 보존된다.

`routers/quant.py` 는 그대로 import 된다 — `charting.py`·`indicators.py` 에 최상단
무거운 import 가 없고 matplotlib 은 함수 안에서 부르기 때문이다 (2026-08-11 실측).

## 실행

    python3 -m venv .venv && .venv/bin/pip install fastapi httpx numpy
    .venv/bin/python scripts/verify_simulation_api.py

저장소 루트의 `.env` 에서 `SUPABASE_URL`·`SUPABASE_SERVICE_ROLE_KEY` 를 읽는다.
**만든 행은 끝에서 전부 지운다** — 검증이 프로젝트 DB 에 잔여물을 남기지 않는다.
"""

from __future__ import annotations

import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "app" / "backend"))


def load_dotenv(path: Path) -> None:
    """`.env` 를 읽어 환경변수에 넣는다. python-dotenv 를 쓰지 않는 것은 의존성 하나를
    검증 전용으로 늘리지 않기 위해서다 — 형식이 `KEY=VALUE` 한 줄뿐이다."""
    if not path.exists():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


load_dotenv(ROOT / ".env")

from fastapi import FastAPI  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from clients import supabase_client  # noqa: E402  (라우터와 같은 폴백 경로로 import)
from routers.quant import PortfolioScenarioRequest, portfolio_scenario  # noqa: E402
from routers.simulation import router as simulation_router  # noqa: E402
from services import simulation as service  # noqa: E402

app = FastAPI()
app.include_router(simulation_router)
client = TestClient(app, raise_server_exceptions=False)

# 검증 전용 소유자 2명. 접두사로 정리 대상을 정확히 특정한다 (16~64자 · ^[A-Za-z0-9_-]+$).
ANON_A = "verify15simowneraAAAAAAAAAAAAAAA"
ANON_B = "verify15simownerbBBBBBBBBBBBBBBB"
BAD_TOKEN = "not-a-real-access-token"

# 연결이 즉시 거부되는 주소. 타임아웃 10초를 기다리지 않고 503 경로를 밟는다.
DEAD_URL = "http://127.0.0.1:1"

# A: 화면 기본값과 같은 조건. B: 곡선이 가장 긴 경계(30년 → 31행)를 밟는다.
CASE_A = {"profile": "balanced", "initial_amount": 10_000_000, "monthly_amount": 500_000, "years": 10}
CASE_B = {"profile": "growth", "initial_amount": 0, "monthly_amount": 300_000, "years": 30}

results: list[tuple[str, str, str, str, bool]] = []
created_ids: list[int] = []


def brief(value) -> str:
    """표에 넣을 짧은 표현. dict·list 는 원문을 그대로 자르면 **키 순서 차이 때문에
    같은 값이 달라 보인다** — PostgREST 가 임베디드 리소스의 키 순서를 보장하지 않는다
    (CN-098). 값 비교는 `==`(순서 무관)로 하고, 표시는 정규화해서 오해를 없앤다."""
    if isinstance(value, (dict, list)):
        return json.dumps(value, ensure_ascii=False, sort_keys=True)
    return str(value)


def check(name: str, endpoint: str, expected, got, extra: str = "") -> bool:
    """기대와 실측을 대조해 기록한다. 통과 여부를 돌려준다."""
    ok = expected == got
    results.append((name, endpoint, brief(expected), f"{brief(got)}{extra}", ok))
    return ok


def with_dead_supabase(fn):
    """SUPABASE_URL 만 죽은 주소로 바꿔 503 경로를 밟게 한다. 원격 DB 는 건드리지 않는다."""
    saved = os.environ.get("SUPABASE_URL", "")
    os.environ["SUPABASE_URL"] = DEAD_URL
    try:
        return fn()
    finally:
        os.environ["SUPABASE_URL"] = saved


def with_broken_percentiles(fn):
    """백분위 순서를 뒤집어 500 경로를 밟게 한다 (cautious > positive → 불변식 위반).

    DB 의 `ck_simulation_run_percentile` 이 아니라 `services._validate` 가 먼저 잡아야
    한다. DB 에서 잡히면 503("잠시 후 다시") 이 되어, 다시 시도해도 같은 값이 나오는
    결함을 사용자가 장애로 읽는다.
    """
    saved = service.PERCENTILES
    service.PERCENTILES = (90, 50, 10)
    try:
        return fn()
    finally:
        service.PERCENTILES = saved


def delete_created() -> int:
    """검증이 만든 행을 지운다. `simulation_point` 는 ON DELETE CASCADE 로 함께 간다."""
    base = (os.getenv("SUPABASE_URL") or "").rstrip("/")
    key = os.getenv("SUPABASE_SERVICE_ROLE_KEY") or ""
    if not (base and key and created_ids):
        return 0
    ids = ",".join(str(i) for i in created_ids)
    url = f"{base}/rest/v1/simulation_run?id=in.({urllib.parse.quote(ids)})"
    req = urllib.request.Request(
        url,
        method="DELETE",
        headers={
            "apikey": key,
            "Authorization": f"Bearer {key}",
            "Prefer": "return=representation",
            "Accept": "application/json",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=15) as res:
            rows = json.loads(res.read() or b"[]")
        return len(rows) if isinstance(rows, list) else 0
    except (urllib.error.URLError, OSError, json.JSONDecodeError) as exc:
        print(f"  ⚠ 정리 실패 — 남은 id: {ids} ({exc})")
        return -1


# ─── 0. 전제 ────────────────────────────────────────────────────────────────

print("=" * 78)
print("F05 시뮬레이션 API — 원격 Supabase 왕복 검증")
print("=" * 78)

if not supabase_client.is_configured():
    print("\n⛔ SUPABASE_URL·SUPABASE_SERVICE_ROLE_KEY 가 없습니다.")
    print("   저장소 루트 .env 에 두 값을 넣고 다시 실행하세요 (.env.example 참고).")
    raise SystemExit(2)

host = urllib.parse.urlparse(os.environ["SUPABASE_URL"]).hostname or "?"
print(f"\n대상   : {host[:8]}….supabase.co  (원격)")
print(f"소유자 : A={ANON_A[:14]}…  B={ANON_B[:14]}…")

# ─── 1. preview — DB 를 건드리지 않는다 ──────────────────────────────────────

res = client.post("/api/simulation/preview", json=CASE_A)
check("1  preview 정상", "preview", 200, res.status_code)
prev_a = res.json() if res.status_code == 200 else {}
check("2  preview 곡선 길이", "preview", CASE_A["years"] + 1, len(prev_a.get("points") or []))
check("3  preview 요약=끝점", "preview",
      {k: (prev_a.get("points") or [{}])[-1].get(k) for k in ("cautious", "middle", "positive")},
      prev_a.get("summary"))
check("4  preview 원금 공식", "preview",
      CASE_A["initial_amount"] + CASE_A["monthly_amount"] * CASE_A["years"] * 12,
      prev_a.get("total_paid"))

# 기본값이 quant.py:51~55 와 같아야 두 경로 대조가 성립한다.
res = client.post("/api/simulation/preview", json={})
base = res.json() if res.status_code == 200 else {}
check("5  preview 기본값", "preview",
      {"profile": "balanced", "initial_amount": 10_000_000, "monthly_amount": 500_000, "years": 10},
      {k: base.get(k) for k in ("profile", "initial_amount", "monthly_amount", "years")})

# 시드가 고정 상수이므로 같은 입력은 언제나 같은 곡선이다. 저장의 전제다.
res2 = client.post("/api/simulation/preview", json=CASE_A)
check("6  preview 재현성", "preview", prev_a.get("points"), res2.json().get("points"))

res = client.post("/api/simulation/preview", json={**CASE_A, "profile": "없는값"})
check("7  preview profile 위반", "preview", 422, res.status_code)

res = client.post("/api/simulation/preview", json={**CASE_A, "years": 31})
check("8  preview years 범위", "preview", 422, res.status_code)

res = client.post("/api/simulation/preview", json={**CASE_A, "initial_amount": -1})
check("9  preview 금액 범위", "preview", 422, res.status_code)

# ─── 2. 두 경로 대조 — quant.py 와 값이 갈라지지 않았는가 ────────────────────
#
# 이 세션의 주장("계산을 옮겼고 값을 바꾸지 않았다")을 실측으로 고정하는 자리다.
# 기존 엔드포인트를 직접 호출해 겹치는 필드를 전부 비교한다.

for idx, case in ((10, CASE_A), (11, CASE_B)):
    legacy = portfolio_scenario(PortfolioScenarioRequest(**case))
    fresh = client.post("/api/simulation/preview", json=case).json()
    check(f"{idx} quant 대조 곡선({case['years']}년)", "preview", legacy["points"], fresh.get("points"))

legacy_a = portfolio_scenario(PortfolioScenarioRequest(**CASE_A))
check("12 quant 대조 요약", "preview", legacy_a["summary"], prev_a.get("summary"))
check("13 quant 대조 라벨·원금·문구", "preview",
      [legacy_a["profile_label"], legacy_a["total_paid"], legacy_a["explanation"]],
      [prev_a.get("profile_label"), prev_a.get("total_paid"), prev_a.get("explanation")])

# ─── 3. create — 실제로 원격에 넣는다 ───────────────────────────────────────

res = client.post("/api/simulation/create", json={**CASE_A, "anon_id": ANON_A})
ok = check("14 create 저장(A)", "create", 200, res.status_code,
           f" {res.text[:80] if res.status_code != 200 else ''}")
row_a = res.json() if ok else {}
if ok:
    created_ids.append(row_a["simulation_id"])
check("15 create id 발급", "create", True, isinstance(row_a.get("simulation_id"), int))
check("16 create 응답=preview 곡선", "create", prev_a.get("points"), row_a.get("points"))

res = client.post("/api/simulation/create", json={**CASE_B, "anon_id": ANON_B})
ok = check("17 create 저장(B·30년)", "create", 200, res.status_code,
           f" {res.text[:80] if res.status_code != 200 else ''}")
row_b = res.json() if ok else {}
if ok:
    created_ids.append(row_b["simulation_id"])
check("18 create 30년 곡선 31행", "create", 31, len(row_b.get("points") or []))

res = client.post("/api/simulation/create", json=CASE_A)
check("19 create 소유자 없음", "create", 400, res.status_code)

res = client.post("/api/simulation/create", json={**CASE_A, "anon_id": ANON_A},
                  headers={"Authorization": f"Bearer {BAD_TOKEN}"})
check("20 create 토큰 무효", "create", 401, res.status_code)

res = client.post("/api/simulation/create", json={**CASE_A, "anon_id": "짧음"})
check("21 create anon_id 위반", "create", 422, res.status_code)

res = with_broken_percentiles(
    lambda: client.post("/api/simulation/create", json={**CASE_A, "anon_id": ANON_A}))
check("22 create 불변식 위반", "create", 500, res.status_code)

res = with_dead_supabase(
    lambda: client.post("/api/simulation/create", json={**CASE_A, "anon_id": ANON_A}))
check("23 create 저장 실패", "create", 503, res.status_code)

# ─── 4. history ─────────────────────────────────────────────────────────────

res = client.get("/api/simulation/history", params={"anon_id": ANON_A})
ok = check("24 history 정상(A)", "history", 200, res.status_code)
hist = res.json() if ok else {}
check("25 history A 는 1건", "history", 1, hist.get("total"))
check("26 history owner_type", "history", "anon", hist.get("owner_type"))
first = (hist.get("items") or [{}])[0]
check("27 history point_count", "history", len(row_a.get("points") or []), first.get("point_count"))
check("28 history 요약 일치", "history", row_a.get("summary"), first.get("summary"))
check("29 history 입력 에코", "history",
      {k: CASE_A[k] for k in ("profile", "initial_amount", "monthly_amount", "years")},
      {k: first.get(k) for k in ("profile", "initial_amount", "monthly_amount", "years")})

res = client.get("/api/simulation/history")
check("30 history 소유자 없음", "history", 400, res.status_code)

res = client.get("/api/simulation/history", params={"anon_id": ANON_A},
                 headers={"Authorization": f"Bearer {BAD_TOKEN}"})
check("31 history 토큰 무효", "history", 401, res.status_code)

res = client.get("/api/simulation/history", params={"anon_id": ANON_A, "limit": 101})
check("32 history limit 범위", "history", 422, res.status_code)

res = with_dead_supabase(lambda: client.get("/api/simulation/history", params={"anon_id": ANON_A}))
check("33 history 조회 실패", "history", 503, res.status_code)

# ─── 5. detail — 저장한 것이 그대로 되살아나는지 ────────────────────────────

id_a = row_a.get("simulation_id", 0)
res = client.get("/api/simulation/detail", params={"id": id_a, "anon_id": ANON_A})
ok = check("34 detail 정상(A)", "detail", 200, res.status_code)
detail = res.json() if ok else {}
check("35 detail 곡선 스냅샷", "detail", row_a.get("points"), detail.get("points"))
# 필드 집합까지 같아야 프런트가 렌더 함수 하나를 재사용할 수 있다.
# 키 *순서* 는 PostgREST 가 보장하지 않으므로 검사하지 않는다 — 집합으로만 본다 (CN-098).
check("36 detail 필드 집합", "detail", sorted(row_a), sorted(detail))
# 저장 경로가 둘(final_* 컬럼 · simulation_point 행)이라 둘이 어긋날 수 있다.
# summary 는 컬럼에서, points 는 자식 행에서 오므로 이 비교가 둘의 일치를 증명한다.
check("37 detail 요약=끝점", "detail",
      {k: (detail.get("points") or [{}])[-1].get(k) for k in ("cautious", "middle", "positive")},
      detail.get("summary"))
check("38 detail 재현 전제", "detail",
      [service.RNG_SEED, service.PATHS], [detail.get("rng_seed"), detail.get("paths")])
check("39 detail 설명 문구", "detail", service.EXPLANATION, detail.get("explanation"))

# 저장값만으로 다시 계산해 같은 곡선이 나오는지. "재현된다" 는 주장의 실측이다.
recomputed = service.build_simulation(
    detail.get("profile"), detail.get("initial_amount"),
    detail.get("monthly_amount"), detail.get("years"),
)
check("40 detail 값으로 재계산", "detail", recomputed["points"], detail.get("points"))

res = client.get("/api/simulation/detail", params={"id": id_a, "anon_id": ANON_B})
check("41 detail 남의 행", "detail", 403, res.status_code)

res = client.get("/api/simulation/detail", params={"id": 999_999_999, "anon_id": ANON_A})
check("42 detail 없는 행", "detail", 404, res.status_code)

res = client.get("/api/simulation/detail", params={"anon_id": ANON_A})
check("43 detail id 누락", "detail", 422, res.status_code)

res = client.get("/api/simulation/detail", params={"id": 0, "anon_id": ANON_A})
check("44 detail id 범위", "detail", 422, res.status_code)

res = client.get("/api/simulation/detail", params={"id": id_a})
check("45 detail 소유자 없음", "detail", 400, res.status_code)

res = client.get("/api/simulation/detail", params={"id": id_a, "anon_id": ANON_A},
                 headers={"Authorization": f"Bearer {BAD_TOKEN}"})
check("46 detail 토큰 무효", "detail", 401, res.status_code)

res = with_dead_supabase(
    lambda: client.get("/api/simulation/detail", params={"id": id_a, "anon_id": ANON_A}))
check("47 detail 조회 실패", "detail", 503, res.status_code)

# ─── 6. 결과 ────────────────────────────────────────────────────────────────

print()
print(f"{'검사':<30} {'대상':<9} {'기대':<10} {'실측':<10} 판정")
print("-" * 78)
for name, endpoint, expected, got, ok in results:
    print(f"{name:<30} {endpoint:<9} {expected[:9]:<10} {got[:9]:<10} {'✅' if ok else '❌'}")

passed = sum(1 for *_, ok in results if ok)
print("-" * 78)
print(f"{passed} / {len(results)} 통과")

if passed != len(results):
    print("\n실패한 검사:")
    for name, endpoint, expected, got, ok in results:
        if not ok:
            print(f"  ❌ {name} ({endpoint})\n     기대: {expected[:200]}\n     실측: {got[:200]}")

print(f"\n정리 — 검증이 만든 행 {len(created_ids)}개 삭제…")
deleted = delete_created()
print(f"  삭제된 simulation_run: {deleted}행 (point 는 CASCADE)")

raise SystemExit(0 if passed == len(results) else 1)
