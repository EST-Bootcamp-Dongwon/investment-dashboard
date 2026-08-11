#!/usr/bin/env python3
"""F03 추천 API 4개를 **원격 Supabase 에 대고** 왕복 검증한다.

세션 11(CN-085)은 같은 코드를 로컬 PostgREST 컨테이너로 확인했다. 이 스크립트는 그
검증을 **실제 원격 프로젝트**에 재실행해, 로컬 대역에서만 통하던 가정이 없는지 본다.
`docs/spec/60-운영/테스트-계획.md` 5.1절 D(에러 코드 정책)의 자동화 대상이다.

검증 범위는 `docs/spec/40-API/API-상세명세.md` 2.3~2.6절 네 개 에러표의 **모든 칸**
(16개) + 정상 응답과 그 내용 대조 18개 = **34건**이다.
세션 11의 12케이스를 포함하는 상위집합이다.

## main.py 를 띄우지 않는다

`app/backend/main.py` 는 `torch`·`diffusers`·`matplotlib` 를 import 시점에 끌어와,
이 검증만을 위해 1.6GB 를 설치해야 한다. 대신 **라우터만 빈 FastAPI 에 마운트**한다.
경로 선언·요청 검증·예외 번역이 전부 `routers/recommendation.py` 안에 있고,
`main.py` 에는 `@app.exception_handler` 가 **0건**이라(2026-08-11 grep) 상태 코드
계약은 그대로 보존된다. 미들웨어 3종(GZip·CORS·no-cache)은 코드를 바꾸지 않는다.

## 실행

    python3 -m venv .venv && .venv/bin/pip install fastapi httpx
    .venv/bin/python scripts/verify_recommendation_api.py

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
from routers.recommendation import router as recommendation_router  # noqa: E402
from services import recommendation as service  # noqa: E402

app = FastAPI()
app.include_router(recommendation_router)
client = TestClient(app, raise_server_exceptions=False)

# 검증 전용 소유자 2명. 접두사로 정리 대상을 정확히 특정한다 (16~64자 · ^[A-Za-z0-9_-]+$).
ANON_A = "verify14ownerAAAAAAAAAAAAAAAAAAAA"
ANON_B = "verify14ownerBBBBBBBBBBBBBBBBBBBB"
BAD_TOKEN = "not-a-real-access-token"

# 연결이 즉시 거부되는 주소. 타임아웃 10초를 기다리지 않고 503 경로를 밟는다.
DEAD_URL = "http://127.0.0.1:1"

results: list[tuple[str, str, str, str, bool]] = []
created_ids: list[int] = []


def brief(value) -> str:
    """표에 넣을 짧은 표현. dict·list 는 원문을 그대로 자르면 **키 순서 차이 때문에
    같은 값이 달라 보인다** — PostgREST 가 임베디드 리소스의 키 순서를 보장하지 않아
    `create` 와 `detail` 의 JSON 키 순서가 실제로 다르다 (2026-08-11 실측).
    값 비교는 `==`(순서 무관)로 하고, 표시는 정규화해서 오해를 없앤다."""
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


def with_broken_profiles(fn):
    """서버 상수를 손상시켜 500 경로를 밟게 한다 (합계 ≠ 100)."""
    saved = {k: v["items"] for k, v in service.PROFILES.items()}
    for config in service.PROFILES.values():
        config["items"] = [dict(config["items"][0], weight_pct=1)]
    try:
        return fn()
    finally:
        for key, items in saved.items():
            service.PROFILES[key]["items"] = items


def delete_created() -> int:
    """검증이 만든 행을 지운다. `recommendation_item` 은 ON DELETE CASCADE 로 함께 간다."""
    base = (os.getenv("SUPABASE_URL") or "").rstrip("/")
    key = os.getenv("SUPABASE_SERVICE_ROLE_KEY") or ""
    if not (base and key and created_ids):
        return 0
    ids = ",".join(str(i) for i in created_ids)
    url = f"{base}/rest/v1/recommendation?id=in.({urllib.parse.quote(ids)})"
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
print("F03 추천 API — 원격 Supabase 왕복 검증")
print("=" * 78)

if not supabase_client.is_configured():
    print("\n⛔ SUPABASE_URL·SUPABASE_SERVICE_ROLE_KEY 가 없습니다.")
    print("   저장소 루트 .env 에 두 값을 넣고 다시 실행하세요 (.env.example 참고).")
    raise SystemExit(2)

host = urllib.parse.urlparse(os.environ["SUPABASE_URL"]).hostname or "?"
print(f"\n대상   : {host[:8]}….supabase.co  (원격)")
print(f"소유자 : A={ANON_A[:14]}…  B={ANON_B[:14]}…")

# ─── 1. preview — DB 를 건드리지 않는다 ──────────────────────────────────────

res = client.post("/api/recommendation/preview", json={"goal": "growth", "horizon": "long", "risk": "high"})
check("1  preview 정상", "preview", 200, res.status_code)
body = res.json() if res.status_code == 200 else {}
check("2  preview 판정", "preview", "growth", body.get("profile"))
check("3  preview 합계 100", "preview", 100, body.get("total_weight_pct"))

res = client.post("/api/recommendation/preview", json={"goal": "없는값", "horizon": "long", "risk": "high"})
check("4  preview enum 위반", "preview", 422, res.status_code)

res = client.post("/api/recommendation/preview", json={"goal": "growth", "horizon": "long"})
check("5  preview 필드 누락", "preview", 422, res.status_code)

# ─── 2. create — 실제로 원격에 넣는다 ───────────────────────────────────────

payload_a = {"goal": "growth", "horizon": "long", "risk": "high", "anon_id": ANON_A}
res = client.post("/api/recommendation/create", json=payload_a)
ok = check("6  create 저장(A)", "create", 200, res.status_code, f" {res.text[:80] if res.status_code != 200 else ''}")
row_a = res.json() if ok else {}
if ok:
    created_ids.append(row_a["recommendation_id"])
check("7  create id 발급", "create", True, isinstance(row_a.get("recommendation_id"), int))
check("8  create 응답=preview 형태", "create", body.get("items"), row_a.get("items"))

payload_b = {"goal": "protect", "horizon": "short", "risk": "low", "anon_id": ANON_B}
res = client.post("/api/recommendation/create", json=payload_b)
ok = check("9  create 저장(B)", "create", 200, res.status_code)
row_b = res.json() if ok else {}
if ok:
    created_ids.append(row_b["recommendation_id"])

res = client.post("/api/recommendation/create", json={"goal": "growth", "horizon": "long", "risk": "high"})
check("10 create 소유자 없음", "create", 400, res.status_code)

res = client.post("/api/recommendation/create", json=payload_a, headers={"Authorization": f"Bearer {BAD_TOKEN}"})
check("11 create 토큰 무효", "create", 401, res.status_code)

res = client.post("/api/recommendation/create", json={**payload_a, "anon_id": "짧음"})
check("12 create anon_id 위반", "create", 422, res.status_code)

res = with_broken_profiles(lambda: client.post("/api/recommendation/create", json=payload_a))
check("13 create 상수 손상", "create", 500, res.status_code)

res = with_dead_supabase(lambda: client.post("/api/recommendation/create", json=payload_a))
check("14 create 저장 실패", "create", 503, res.status_code)

# ─── 3. history ─────────────────────────────────────────────────────────────

res = client.get("/api/recommendation/history", params={"anon_id": ANON_A})
ok = check("15 history 정상(A)", "history", 200, res.status_code)
hist = res.json() if ok else {}
check("16 history A 는 1건", "history", 1, hist.get("total"))
check("17 history owner_type", "history", "anon", hist.get("owner_type"))
first = (hist.get("items") or [{}])[0]
check("18 history item_count", "history", len(row_a.get("items") or []), first.get("item_count"))

res = client.get("/api/recommendation/history")
check("19 history 소유자 없음", "history", 400, res.status_code)

res = client.get("/api/recommendation/history", params={"anon_id": ANON_A}, headers={"Authorization": f"Bearer {BAD_TOKEN}"})
check("20 history 토큰 무효", "history", 401, res.status_code)

res = client.get("/api/recommendation/history", params={"anon_id": ANON_A, "limit": 101})
check("21 history limit 범위", "history", 422, res.status_code)

res = with_dead_supabase(lambda: client.get("/api/recommendation/history", params={"anon_id": ANON_A}))
check("22 history 조회 실패", "history", 503, res.status_code)

# ─── 4. detail — 저장한 것이 그대로 되살아나는지 ────────────────────────────

id_a = row_a.get("recommendation_id", 0)
res = client.get("/api/recommendation/detail", params={"id": id_a, "anon_id": ANON_A})
ok = check("23 detail 정상(A)", "detail", 200, res.status_code)
detail = res.json() if ok else {}
check("24 detail 스냅샷 일치", "detail", row_a.get("items"), detail.get("items"))
# 필드 집합까지 같아야 프런트가 렌더 함수 하나를 재사용할 수 있다 (명세 2.6절).
# 키 *순서* 는 PostgREST 가 보장하지 않으므로 검사하지 않는다 — 집합으로만 본다.
check(
    "25 detail 필드 집합",
    "detail",
    sorted((row_a.get("items") or [{}])[0]),
    sorted((detail.get("items") or [{}])[0]),
)
check("26 detail 합계 100", "detail", 100, detail.get("total_weight_pct"))
check("27 detail 면책 문구", "detail", service.DISCLAIMER, detail.get("disclaimer"))

res = client.get("/api/recommendation/detail", params={"id": id_a, "anon_id": ANON_B})
check("28 detail 남의 행", "detail", 403, res.status_code)

res = client.get("/api/recommendation/detail", params={"id": 999_999_999, "anon_id": ANON_A})
check("29 detail 없는 행", "detail", 404, res.status_code)

res = client.get("/api/recommendation/detail", params={"anon_id": ANON_A})
check("30 detail id 누락", "detail", 422, res.status_code)

res = client.get("/api/recommendation/detail", params={"id": 0, "anon_id": ANON_A})
check("31 detail id 범위", "detail", 422, res.status_code)

res = client.get("/api/recommendation/detail", params={"id": id_a})
check("32 detail 소유자 없음", "detail", 400, res.status_code)

res = client.get("/api/recommendation/detail", params={"id": id_a, "anon_id": ANON_A}, headers={"Authorization": f"Bearer {BAD_TOKEN}"})
check("33 detail 토큰 무효", "detail", 401, res.status_code)

res = with_dead_supabase(lambda: client.get("/api/recommendation/detail", params={"id": id_a, "anon_id": ANON_A}))
check("34 detail 조회 실패", "detail", 503, res.status_code)

# ─── 5. 결과 ────────────────────────────────────────────────────────────────

print()
print(f"{'검사':<24} {'대상':<9} {'기대':<10} {'실측':<10} 판정")
print("-" * 78)
for name, endpoint, expected, got, ok in results:
    print(f"{name:<24} {endpoint:<9} {expected[:9]:<10} {got[:9]:<10} {'✅' if ok else '❌'}")

passed = sum(1 for *_, ok in results if ok)
print("-" * 78)
print(f"{passed} / {len(results)} 통과")

print(f"\n정리 — 검증이 만든 행 {len(created_ids)}개 삭제…")
deleted = delete_created()
print(f"  삭제된 recommendation: {deleted}행 (item 은 CASCADE)")

raise SystemExit(0 if passed == len(results) else 1)
