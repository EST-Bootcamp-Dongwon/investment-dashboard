#!/usr/bin/env python3
"""F28 백테스트 API 6개를 **원격 Supabase 에 대고** 왕복 검증한다.

`scripts/verify_combination_api.py`(F04 · 77건)와 같은 틀이다. 다른 점은 **원본을
무엇으로 잡느냐** 하나이고, 그것이 이 세션이 먼저 결정해야 했던 것이다.

## F04 는 `main.py` 원문을 AST 로 읽었다. F28 은 그럴 필요가 없다

F04 의 원본은 `torch` 를 끌고 오는 `main.py` 안에 있어 import 할 수 없었고, 그래서
소스를 파싱해 **상수만** 대조했다(CN-106 ①). F28 의 원본은 이미
`routers/backtest_lab.py` 안의 함수였다 — import 할 수 있으니 상수가 아니라
**출력 전체**를 대조할 수 있다. 더 강한 대조다.

그래서 리팩터 **전** 출력을 `test/fixtures/backtest_run_golden.json` 에 떠 두고
지금 출력과 `==` 로 비교한다. 상수 하나가 아니라 `meta`·`regime`·지표 16개·
피처 중요도·성과 12개 × 2 와 일별 표 2개(해시)가 통째로 걸린다.

## 무엇을 세 갈래로 나눠 대조하는가

    ① 계산      — 골든과 `==`. 계층을 옮겨도 숫자가 그대로인가.
    ② 정규화    — 저장 컬럼보다 정밀한 입력을 **굴리기 전에** 깎는가.
                  안 깎으면 저장된 입력으로 다시 돌려도 저장된 결과가 안 나온다.
    ③ 왕복      — 시세 경계(`clients/lean_prices.download`)를 가짜로 바꿔
                  **원격 왕복 자체를 결정적으로** 만든다 (CN-106 ②).

**③ 이 가능한 것이 이번 계층 분리가 사 준 것이다.** 리팩터 전
`backtest_lab.py:144` 처럼 라우트 핸들러가 `download_price_data.download` 를 직접
부르면 치환 지점이 라우터 내부 이름이라, 계층 밖에서 갈아끼우는 모양이 된다.

## main.py 를 띄우지 않는다

`app/backend/main.py` 는 `torch`·`diffusers`·`matplotlib` 를 import 시점에 끌어와,
이 검증만을 위해 1.6GB 를 설치해야 한다. 그래서 **라우터만 빈 FastAPI 에 마운트**한다
(`verify_combination_api.py` 와 같은 이유). F28 은 원본도 라우터라 AST 우회조차 필요 없다.

## 실행

    python3 -m venv .venv && .venv/bin/pip install fastapi httpx numpy pandas scikit-learn
    .venv/bin/python scripts/verify_backtest_api.py

`yfinance` 는 필요 없다 — 시세 경계를 가짜로 바꾸므로 네트워크로 시세를 받지 않는다.
`scikit-learn` 은 필요하다(`hd_core` 가 `HistGradientBoostingRegressor` 를 쓴다).
저장소 루트의 `.env` 에서 `SUPABASE_URL`·`SUPABASE_SERVICE_ROLE_KEY` 를 읽는다.
**만든 행은 끝에서 전부 지운다** — 검증이 프로젝트 DB 에 잔여물을 남기지 않는다.
"""

from __future__ import annotations

import hashlib
import json
import math
import os
import sys
import urllib.error
import urllib.parse
import urllib.request
from datetime import date, timedelta
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

from clients import backtest_repo, lean_prices, supabase_client  # noqa: E402
from routers.backtest_lab import router as backtest_router  # noqa: E402
from services import backtest as service  # noqa: E402

results: list[tuple[str, str, str, str, bool]] = []
created_ids: list[int] = []

ANON_A = "verifybt-owner-a-0123456789"
ANON_B = "verifybt-owner-b-0123456789"
DEAD_URL = "http://127.0.0.1:9"


def brief(value) -> str:
    """표에 넣을 짧은 표현. dict·list 는 원문을 그대로 자르면 **키 순서 차이 때문에
    같은 값이 달라 보인다** — PostgREST 가 키 순서를 보장하지 않는다 (CN-098).
    값 비교는 `==`(순서 무관)로 하고, 표시는 정규화해서 오해를 없앤다."""
    if isinstance(value, set):
        # 집합은 순서가 없으니 정렬해 찍는다. 튜플은 순서가 뜻을 가지므로 건드리지 않는다.
        value = sorted(value, key=str)
    if isinstance(value, (dict, list, tuple)):
        return json.dumps(value, ensure_ascii=False, sort_keys=True)
    return str(value)


def check(name: str, endpoint: str, expected, got, extra: str = "") -> bool:
    """기대와 실측을 대조해 기록한다. 통과 여부를 돌려준다."""
    ok = expected == got
    results.append((name, endpoint, brief(expected), f"{brief(got)}{extra}", ok))
    return ok


def digest(value) -> str:
    """골든 픽스처와 같은 방식으로 해시한다 (정렬 직렬화 · CN-098)."""
    return hashlib.sha256(
        json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()


def with_dead_supabase(fn):
    """SUPABASE_URL 만 죽은 주소로 바꿔 503 경로를 밟게 한다. 원격 DB 는 건드리지 않는다."""
    saved = os.environ.get("SUPABASE_URL", "")
    os.environ["SUPABASE_URL"] = DEAD_URL
    try:
        return fn()
    finally:
        os.environ["SUPABASE_URL"] = saved


# ─── 시세 경계 치환 — 여기서부터 전부 결정적이다 (CN-106 ②) ──────────────────

def fake_rows(start: str, end: str) -> list[list]:
    """합성 일봉. **난수를 쓰지 않아** 매 실행 같은 값이 나온다.

    골든을 뜰 때 쓴 것과 같은 식이다(`test/fixtures/backtest_run_golden.json`).
    주말을 빼는 것은 `hd_core.build_features` 가 거래일 연속을 가정하기 때문이다.
    """
    d0, d1 = date.fromisoformat(start), date.fromisoformat(end)
    rows, day, i = [], d0, 0
    while day <= d1:
        if day.weekday() < 5:
            base = 70000 + 3000 * math.sin(i / 9.0) + 40 * i
            open_ = round(base, 1)
            close = round(base * (1 + 0.004 * math.cos(i / 4.0)), 1)
            rows.append([day.isoformat(), open_, round(max(open_, close) * 1.006, 1),
                         round(min(open_, close) * 0.994, 1), close, 1_000_000 + 5000 * (i % 37)])
            i += 1
        day += timedelta(days=1)
    return rows


REAL_DOWNLOAD = lean_prices.download
lean_prices.download = lambda ticker, start, end: fake_rows(start, end)

app = FastAPI()
app.include_router(backtest_router)
client = TestClient(app)


def post(path: str, body: dict, headers: dict | None = None):
    return client.post(f"/api/backtest-lab/{path}", json=body, headers=headers or {})


def get(path: str, params: dict, headers: dict | None = None):
    return client.get(f"/api/backtest-lab/{path}", params=params, headers=headers or {})


# ─── 0. 전제 ────────────────────────────────────────────────────────────────

print("=" * 78)
print("F28 백테스트 API — 골든 대조 + 원격 Supabase 왕복 검증")
print("=" * 78)

if not supabase_client.is_configured():
    print("\n⛔ SUPABASE_URL·SUPABASE_SERVICE_ROLE_KEY 가 없습니다.")
    print("   저장소 루트 .env 에 두 값을 넣고 다시 실행하세요 (.env.example 참고).")
    raise SystemExit(2)

if not service.engine_available():
    print(f"\n⛔ 예측 모듈을 불러오지 못했습니다: {service.import_error()}")
    print("   .venv/bin/pip install scikit-learn numpy pandas 를 먼저 실행하세요.")
    raise SystemExit(2)

host = urllib.parse.urlparse(os.environ["SUPABASE_URL"]).hostname or "?"
print(f"\n대상   : {host[:8]}….supabase.co  (원격)")
print(f"소유자 : A={ANON_A[:16]}…  B={ANON_B[:16]}…")
print(f"원본   : test/fixtures/backtest_run_golden.json (리팩터 전 /run 출력)")
print(f"시세   : fake_rows — 합성 일봉, 난수 없음")


# ─── 1. 골든 대조 — 계층을 옮겨도 숫자가 그대로인가 ─────────────────────────
#
# 이 세션의 주장("계산을 services/ 로 옮겼고 값을 바꾸지 않았다")을 고정하는 자리다.

GOLDEN = json.loads((ROOT / "test" / "fixtures" / "backtest_run_golden.json").read_text("utf-8"))

for label, case in sorted(GOLDEN["cases"].items()):
    lean_prices.clear_cache()
    res = post("run", case["request"])
    if res.status_code != 200:
        check(f"골든 {label} 실행", "/run", 200, res.status_code, f"  {res.text[:120]}")
        continue
    got = json.loads(json.dumps(res.json(), ensure_ascii=False))  # 골든과 같은 JSON 왕복본으로
    want = case["expected"]

    check(f"골든 {label} meta", "/run", want["meta"], got["meta"])
    check(f"골든 {label} 국면", "/run", want["regime"], got["regime"])
    check(f"골든 {label} 예측지표", "/run", want["prediction_metrics"], got["prediction_metrics"])
    check(f"골든 {label} 피처중요도", "/run", want["feature_importance"], got["feature_importance"])
    check(f"골든 {label} 성과", "/run", want["simple_backtest"],
          {k: v for k, v in got["simple_backtest"].items() if k != "curve"})

    for key, path in (("rows", ("rows",)), ("simple_backtest.curve", ("simple_backtest", "curve"))):
        actual = got
        for part in path:
            actual = actual[part]
        want_long = case["long_arrays"][key]
        check(f"골든 {label} {key}", "/run",
              (want_long["length"], want_long["sha256"]), (len(actual), digest(actual)))


# ─── 2. 정규화 — 굴리기 전에 깎는가 ─────────────────────────────────────────
#
# 저장 컬럼이 요청보다 정밀도가 낮다(bigint · numeric(6,5)). 굴린 뒤에 깎으면
# 저장된 입력으로 다시 돌려도 저장된 결과가 나오지 않는다.

COARSE = {
    "initial_cash": 100_000_000.4,   # bigint  → 100000000
    "commission_rate": 0.000123456,  # (6,5)   → 0.00012
    "sell_tax_rate": 0.0015004,      # (6,5)   → 0.0015
    "slippage_rate": 0.00049999,     # (6,5)   → 0.0005
}
QUANTIZED = {
    "initial_cash": 100_000_000,
    "commission_rate": 0.00012,
    "sell_tax_rate": 0.0015,
    "slippage_rate": 0.0005,
}

params_coarse = service.RunParams.normalized(
    ticker="005380.KS", name="현대차", train_start="2025-01-01", train_end="2025-12-31",
    test_start="2026-01-01", test_end="2026-06-30", warmup_days=120, **COARSE,
)
check("정규화 4개 값", "service", QUANTIZED,
      {k: getattr(params_coarse, k) for k in QUANTIZED})
check("정규화 initial_cash 형", "service", int, type(params_coarse.initial_cash))

# 깎은 값이 실제로 계산에 들어갔는가 — 응답의 cost_assumptions 가 증거다.
lean_prices.clear_cache()
coarse_run = post("run", COARSE).json()
check("정규화 후 계산 반영", "/run",
      {**{k: QUANTIZED[k] for k in ("commission_rate", "sell_tax_rate", "slippage_rate")},
       "initial_cash": QUANTIZED["initial_cash"]},
      coarse_run["simple_backtest"]["cost_assumptions"])

# 이미 5자리인 기본값은 깎여도 그대로여야 한다 — 정규화가 값을 흔들면 안 된다.
params_default = service.RunParams.normalized(
    ticker="005380.KS", name="현대차", train_start="2025-01-01", train_end="2025-12-31",
    test_start="2026-01-01", test_end="2026-06-30", warmup_days=120,
    initial_cash=100_000_000, commission_rate=service.DEFAULT_COMMISSION_RATE,
    sell_tax_rate=service.DEFAULT_SELL_TAX_RATE, slippage_rate=service.DEFAULT_SLIPPAGE_RATE,
)
check("정규화 기본값 불변", "service",
      (0.00015, 0.0015, 0.0005),
      (params_default.commission_rate, params_default.sell_tax_rate, params_default.slippage_rate))


# ─── 3. /config ─────────────────────────────────────────────────────────────

config = get("config", {}).json()
check("config 사용가능", "/config", True, config["available"])
check("config 프리셋 수", "/config", 7, len(config["presets"]))
check("config 기본값 키", "/config", 11, len(config["defaults"]))
check("config 피처 수", "/config", 12, len(config["features"]))
# 기본값이 pydantic 제약을 스스로 통과하는가 — 화면이 그대로 보내면 돌아야 한다.
check("config 기본값 유효", "/run", 200, post("run", config["defaults"]).status_code)


# ─── 4. /save — 원격 왕복 ───────────────────────────────────────────────────

check("save 소유자 없음", "/save", 400, post("save", {}).status_code)
check("save anon 짧음", "/save", 422, post("save", {"anon_id": "short"}).status_code)

lean_prices.clear_cache()
save_res = post("save", {"anon_id": ANON_A})
check("save 상태", "/save", 200, save_res.status_code, f"  {save_res.text[:150]}")
saved = save_res.json()
id_a = saved.get("backtest_id")
if isinstance(id_a, int):
    created_ids.append(id_a)
check("save id 정수", "/save", True, isinstance(id_a, int))
check("save 저장시각 있음", "/save", True, bool(saved.get("created_at")))
check("save inputs 11개", "/save", 11, len(saved.get("inputs", {})))

# 저장 경로와 실행 경로가 같은 숫자를 내는가. 저장 여부로 결과가 달라지면 안 된다.
lean_prices.clear_cache()
run_only = post("run", {}).json()
check("save == run 성과", "두 경로",
      run_only["simple_backtest"]["strategy"], saved["simple_backtest"]["strategy"])
check("save == run 지표", "두 경로", run_only["prediction_metrics"], saved["prediction_metrics"])


# ─── 5. /detail — 되살아나는가, 무엇이 빠지는가 ─────────────────────────────

detail = get("detail", {"id": id_a, "anon_id": ANON_A}).json()

check("detail 성과 왕복", "/detail", saved["simple_backtest"]["strategy"],
      detail["simple_backtest"]["strategy"])
check("detail 벤치 왕복", "/detail", saved["simple_backtest"]["benchmark"],
      detail["simple_backtest"]["benchmark"])
check("detail 예측지표 왕복", "/detail", saved["prediction_metrics"], detail["prediction_metrics"])
check("detail 비용 왕복", "/detail", saved["simple_backtest"]["cost_assumptions"],
      detail["simple_backtest"]["cost_assumptions"])
check("detail 초과수익 왕복", "/detail", saved["simple_backtest"]["excess_return_pct"],
      detail["simple_backtest"]["excess_return_pct"])
check("detail inputs 왕복", "/detail", saved["inputs"], detail["inputs"])
check("detail id 왕복", "/detail", saved["backtest_id"], detail["backtest_id"])
check("detail 시각 왕복", "/detail", saved["created_at"], detail["created_at"])

# **무엇이 빠지는가** — 서비스 계층의 상수와 실제 차집합을 대조한다.
# 목록과 실제가 어긋나면 여기서 깨진다 (CN-108 에서 온 방식).
check("빠지는 최상위 키", "/detail", set(service.UNSAVED_TOP), set(saved) - set(detail) - {"inputs"})
check("빠지는 meta 키", "/detail", set(service.UNSAVED_META),
      set(saved["meta"]) - set(detail["meta"]))
check("빠지는 성과 키", "/detail", set(service.UNSAVED_BACKTEST),
      set(saved["simple_backtest"]) - set(detail["simple_backtest"]))
check("detail 에만 있는 키", "/detail", set(), set(detail) - set(saved))
check("detail meta 값 왕복", "/detail",
      {k: v for k, v in saved["meta"].items() if k not in service.UNSAVED_META}, detail["meta"])


# ─── 6. /history ────────────────────────────────────────────────────────────

history = get("history", {"anon_id": ANON_A}).json()
check("history 소유자형", "/history", "anon", history["owner_type"])
check("history 건수", "/history", 1, history["total"])
item = history["items"][0]
check("history 항목 키 수", "/history", 12, len(item))
check("history id", "/history", id_a, item["backtest_id"])
# **jsonb 3덩이가 목록에 없어야 한다.** 있으면 목록이 상세보다 무거워진다.
check("history jsonb 없음", "/history", set(),
      {"strategy_stats", "benchmark_stats", "prediction_metrics"} & set(item))
# 생성 컬럼 — 원격 Postgres 가 jsonb 에서 뽑아 계산한 값이다. 로컬 값과 같아야 한다.
check("history 생성컬럼 수익률", "/history",
      saved["simple_backtest"]["strategy"]["total_return_pct"], item["total_return_pct"])
check("history 생성컬럼 낙폭", "/history",
      saved["simple_backtest"]["strategy"]["max_drawdown_pct"], item["max_drawdown_pct"])

# 두 번째 행을 넣어 정렬을 본다.
lean_prices.clear_cache()
second = post("save", {"anon_id": ANON_A, "ticker": "005930.KS", "name": "삼성전자",
                       "test_end": "2026-05-31"})
id_a2 = second.json().get("backtest_id")
if isinstance(id_a2, int):
    created_ids.append(id_a2)
history2 = get("history", {"anon_id": ANON_A}).json()
check("history 정렬 최신우선", "/history", [id_a2, id_a],
      [i["backtest_id"] for i in history2["items"]])
check("history limit", "/history", 1, len(get("history", {"anon_id": ANON_A, "limit": 1}).json()["items"]))


# ─── 7. 소유자 격리 ─────────────────────────────────────────────────────────

check("남의 상세 403", "/detail", 403, get("detail", {"id": id_a, "anon_id": ANON_B}).status_code)
check("없는 id 404", "/detail", 404, get("detail", {"id": 999_999_999, "anon_id": ANON_A}).status_code)
check("B 이력 비어있음", "/history", 0, get("history", {"anon_id": ANON_B}).json()["total"])
check("잘못된 토큰 401", "/history", 401,
      get("history", {}, {"Authorization": "Bearer not-a-real-token"}).status_code)


# ─── 8. 오류 경로 — 코드가 갈라지는가 ───────────────────────────────────────

check("구간 겹침 400", "/run", 400, post("run", {"test_start": "2025-06-01"}).status_code)
check("미래 구간 400", "/run", 400, post("run", {"test_end": "2099-01-01"}).status_code)
check("시작>종료 400", "/run", 400,
      post("run", {"train_start": "2025-12-31", "train_end": "2025-01-01"}).status_code)
check("티커 문자 422", "/run", 422, post("run", {"ticker": "AA;rm -rf"}).status_code)
check("자본 하한 422", "/run", 422, post("run", {"initial_cash": 1000}).status_code)

# 시세 경계를 **진짜 래퍼로 되돌려** 502·404 를 밟는다. 도메인이 아니라 clients 가
# 내는 예외라, 가짜 함수로 바꿔치기하면 래퍼 자체는 검사되지 않는다.
lean_prices.download = REAL_DOWNLOAD
lean_prices.clear_cache()
_real_dl = lean_prices.download_price_data.download
try:
    lean_prices.download_price_data.download = lambda t, s, e: (_ for _ in ()).throw(TimeoutError("느림"))
    check("시세 실패 502", "/run", 502, post("run", {}).status_code)
    lean_prices.clear_cache()
    lean_prices.download_price_data.download = lambda t, s, e: []
    check("시세 0건 404", "/run", 404, post("run", {}).status_code)
    # 빈 결과를 캐시에 넣지 않았는지 — 넣었다면 티커를 고쳐도 15분간 404 가 이어진다.
    lean_prices.download_price_data.download = lambda t, s, e: fake_rows(s, e)
    check("빈 결과 캐시 안함", "/run", 200, post("run", {}).status_code)
finally:
    lean_prices.download_price_data.download = _real_dl
    lean_prices.download = lambda ticker, start, end: fake_rows(start, end)
    lean_prices.clear_cache()

# Supabase 가 죽으면 저장은 503 이고, **실행은 그대로 200 이어야 한다.**
check("죽은 DB 저장 503", "/save", 503,
      with_dead_supabase(lambda: post("save", {"anon_id": ANON_A}).status_code))
lean_prices.clear_cache()
check("죽은 DB 이력 503", "/history", 503,
      with_dead_supabase(lambda: get("history", {"anon_id": ANON_A}).status_code))
lean_prices.clear_cache()
check("죽은 DB 실행 200", "/run", 200, with_dead_supabase(lambda: post("run", {}).status_code))


# ─── 9. 원격 원문 확인 + DB 백스톱 ──────────────────────────────────────────

BASE = (os.getenv("SUPABASE_URL") or "").rstrip("/")
KEY = os.getenv("SUPABASE_SERVICE_ROLE_KEY") or ""
REST_HEADERS = {"apikey": KEY, "Authorization": f"Bearer {KEY}", "Accept": "application/json"}


def rest(method: str, path: str, body=None, extra_headers=None):
    """PostgREST 직접 호출. 상태 코드와 본문을 함께 돌려준다."""
    payload = json.dumps(body).encode("utf-8") if body is not None else None
    headers = {**REST_HEADERS, "Content-Type": "application/json", **(extra_headers or {})}
    req = urllib.request.Request(f"{BASE}/rest/v1/{path}", data=payload,
                                 headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=20) as res_:
            raw = res_.read()
            return res_.status, (json.loads(raw) if raw else None)
    except urllib.error.HTTPError as exc:
        return exc.code, exc.read().decode("utf-8", "replace")[:300]


status, raw_rows = rest("GET", f"backtest_summary?id=eq.{id_a}&select=*")
raw = (raw_rows or [{}])[0] if isinstance(raw_rows, list) else {}

# `numeric` 이 무엇으로 돌아오는지는 **추측하지 않고 찍는다.** `backtest_repo._to_float`
# 가 왜 필요한지의 실측이다.
print(f"\n  실측 — commission_rate 원문 : {raw.get('commission_rate')!r}")
print(f"  실측 — initial_cash 원문    : {raw.get('initial_cash')!r}")
print(f"  실측 — 생성컬럼 수익률 원문  : {raw.get('strategy_total_return_pct')!r}")
print(f"  실측 — train_start 원문     : {raw.get('train_start')!r}")

check("원격 비용률 값", "원격", saved["inputs"]["commission_rate"],
      float(raw.get("commission_rate")))
check("원격 자본 값", "원격", saved["inputs"]["initial_cash"], int(raw.get("initial_cash")))
check("원격 날짜 값", "원격",
      [saved["inputs"][k] for k in ("train_start", "train_end", "test_start", "test_end")],
      [raw.get(k) for k in ("train_start", "train_end", "test_start", "test_end")])
check("원격 jsonb 성과", "원격", saved["simple_backtest"]["strategy"], raw.get("strategy_stats"))
check("원격 엔진 문구", "원격", saved["meta"]["engine"], raw.get("engine_note"))

# 제약이 실제로 동작하는가. services 가 먼저 걸러 여기 도달할 일은 없어야 하지만,
# "없어야 한다" 와 "막혀 있다" 는 다르다.
BAD_BASE = {
    "anon_id": ANON_A, "ticker": "FIX.KS", "name": "백스톱",
    "train_start": "2025-01-01", "train_end": "2025-12-31",
    "test_start": "2026-01-01", "test_end": "2026-06-30",
    "initial_cash": 100_000_000, "commission_rate": 0.00015, "sell_tax_rate": 0.0015,
    "slippage_rate": 0.0005, "warmup_days": 120, "model_name": "m",
    "strategy_stats": {}, "benchmark_stats": {}, "prediction_metrics": {},
    "price_rows": 10, "price_first": "2024-09-03", "price_last": "2026-06-30",
    "engine_note": "e",
}
for label, bad in (
    ("자본 하한", {"initial_cash": 999}),
    ("수수료 상한", {"commission_rate": 0.5}),
    ("워밍업 하한", {"warmup_days": 10}),
    ("종목명 길이", {"name": "가" * 41}),
    ("소유자 없음", {"anon_id": None}),
    ("행 수 음수", {"price_rows": -1}),
):
    status_, _ = rest("POST", "backtest_summary", {**BAD_BASE, **bad})
    check(f"제약 {label}", "원격", 400, status_)


# ─── 10. 결과 ───────────────────────────────────────────────────────────────

print()
print(f"{'검사':<26} {'대상':<8} {'기대':<11} {'실측':<11} 판정")
print("-" * 80)
for name, endpoint, expected, got, ok in results:
    print(f"{name:<26} {endpoint:<8} {expected[:10]:<11} {got[:10]:<11} {'✅' if ok else '❌'}")

passed = sum(1 for *_, ok in results if ok)
print("-" * 80)
print(f"{passed} / {len(results)} 통과")

if passed != len(results):
    print("\n실패한 검사:")
    for name, endpoint, expected, got, ok in results:
        if not ok:
            print(f"  ❌ {name} ({endpoint})\n     기대: {expected[:400]}\n     실측: {got[:400]}")


def delete_created() -> int:
    """검증이 만든 행을 지운다. 백스톱 검사는 전부 거부되므로 남는 것이 없다."""
    if not (BASE and KEY and created_ids):
        return 0
    ids = ",".join(str(i) for i in created_ids)
    status_, rows = rest("DELETE", f"backtest_summary?id=in.({urllib.parse.quote(ids)})",
                         extra_headers={"Prefer": "return=representation"})
    if status_ >= 400:
        print(f"  ⚠ 정리 실패 — 남은 id: {ids} ({rows})")
        return -1
    return len(rows) if isinstance(rows, list) else 0


print(f"\n정리 — 검증이 만든 행 {len(created_ids)}개 삭제…")
print(f"  삭제된 backtest_summary: {delete_created()}행")

raise SystemExit(0 if passed == len(results) else 1)
