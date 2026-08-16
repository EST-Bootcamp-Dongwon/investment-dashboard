#!/usr/bin/env python3
"""F04 조합 API 4개를 **원격 Supabase 에 대고** 왕복 검증한다.

`scripts/verify_simulation_api.py`(F05 · 47건)와 같은 틀이다. 다른 점은 **무엇을
대조하느냐** 하나이고, 그것이 이 세션이 먼저 결정해야 했던 것이다.

## F05 는 출력을 비교했다. F04 는 그럴 수 없다

F05 는 시드가 고정 상수라 두 경로에 같은 입력을 넣고 **정수 곡선을 그대로 비교**할
수 있었다. F04 는 불가능하다 — yfinance 가 매일 다른 시세를 주고, `auto_adjust=True`
라 배당·분할이 생기면 **과거 구간 값까지 소급해서 바뀐다.** 어제 통과한 기대값이
오늘 실패한다.

그래서 세 가지로 나눠 대조한다.

    ① 규칙의 상수  — **원본 라우트를 AST 로 파싱**해 임계값·문장·라벨·정규식·
                     하한·응답 키를 뽑아 `services/combination.py` 와 비교한다.
                     "값을 바꾸지 않았다" 는 주장이 여기서 검사 가능해진다.
    ② 규칙의 동작  — **고정 시계열**을 넣어 판정이 결정적으로 나오는지 본다.
                     경계값(0.30 · 0.70)을 양쪽에서 밟는다.
    ③ 왕복        — 시세 경계(`clients/yahoo_prices.download_closes`)를 가짜로
                     바꿔 **원격 왕복 자체를 결정적으로** 만든다.

**③ 이 가능한 것이 계층 분리가 사 준 것이다.** 라우트 핸들러가 `yf.download` 를
직접 부르면 꽂을 자리가 없어, 원격 왕복 검증이 매번 다른 시세 위에서 돌아 재실행할
때마다 기대값이 달라진다.

검사 71건 = 원문 대조 21 + 규칙 동작 11 + preview 8 + create 8 + history 6
           + detail 10 + 감사 컬럼 3 + DB 백스톱 4.

## 앱을 띄우지 않는다 — 그런데 읽기는 한다

`app/backend/main.py` 는 `torch`·`diffusers`·`matplotlib` 를 import 시점에 끌어와,
이 검증만을 위해 1.6GB 를 설치해야 한다. 그래서 **라우터만 빈 FastAPI 에 마운트**한다
(`verify_simulation_api.py` 와 같은 이유).

①이 읽는 원본은 `services/market.py` 의 `portfolio_combination` 이다. 2026-08-16
[CN-065](docs/spec/00-index/변경이력.md#cn-065) 분해 전에는 `main.py:1194` 에 있어
**import 하지 않고 소스만 읽는 것 말고 방법이 없었다.** 지금은 그 모듈이 가벼워져
import 해도 되지만 AST 방식을 그대로 둔다 — 이 검사가 보려는 것은 함수 안에 박힌
**상수**이고, import 하면 상수가 아니라 실행 결과를 보게 되기 때문이다.

## 실행

    python3 -m venv .venv && .venv/bin/pip install fastapi httpx numpy pandas
    .venv/bin/python scripts/verify_combination_api.py

`yfinance` 는 필요 없다 — 시세 경계를 가짜로 바꾸므로 네트워크로 시세를 받지 않는다.
저장소 루트의 `.env` 에서 `SUPABASE_URL`·`SUPABASE_SERVICE_ROLE_KEY` 를 읽는다.
**만든 행은 끝에서 전부 지운다** — 검증이 프로젝트 DB 에 잔여물을 남기지 않는다.
"""

from __future__ import annotations

import ast
import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone
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

import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402
from fastapi import FastAPI  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from clients import supabase_client, yahoo_prices  # noqa: E402
from routers.combination import router as combination_router  # noqa: E402
from services import combination as service  # noqa: E402

app = FastAPI()
app.include_router(combination_router)
client = TestClient(app, raise_server_exceptions=False)

# 검증 전용 소유자 2명. 접두사로 정리 대상을 정확히 특정한다 (16~64자 · ^[A-Za-z0-9_-]+$).
ANON_A = "verify16combowneraAAAAAAAAAAAAAA"
ANON_B = "verify16combownerbBBBBBBBBBBBBBB"
BAD_TOKEN = "not-a-real-access-token"

# 연결이 즉시 거부되는 주소. 타임아웃 10초를 기다리지 않고 503 경로를 밟는다.
DEAD_URL = "http://127.0.0.1:1"

results: list[tuple[str, str, str, str, bool]] = []
created_ids: list[int] = []


def brief(value) -> str:
    """표에 넣을 짧은 표현. dict·list 는 원문을 그대로 자르면 **키 순서 차이 때문에
    같은 값이 달라 보인다** — PostgREST 가 키 순서를 보장하지 않는다 (CN-098).
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


# ─── 0. 전제 ────────────────────────────────────────────────────────────────

print("=" * 78)
print("F04 조합 API — 원본 대조 + 원격 Supabase 왕복 검증")
print("=" * 78)

if not supabase_client.is_configured():
    print("\n⛔ SUPABASE_URL·SUPABASE_SERVICE_ROLE_KEY 가 없습니다.")
    print("   저장소 루트 .env 에 두 값을 넣고 다시 실행하세요 (.env.example 참고).")
    raise SystemExit(2)

host = urllib.parse.urlparse(os.environ["SUPABASE_URL"]).hostname or "?"
print(f"\n대상   : {host[:8]}….supabase.co  (원격)")
print(f"소유자 : A={ANON_A[:14]}…  B={ANON_B[:14]}…")


# ─── 1. 원본 대조 — import 하지 않고 AST 로 읽는다 ─────────────────────────
#
# 이 세션의 주장("판정을 옮겼고 값을 바꾸지 않았다")을 고정하는 자리다.
# F05 는 원본을 import 해 출력을 비교했지만, F04 의 원본은 오래 `main.py` 안에 있어
# 그럴 수 없었다(torch 를 끌고 온다). 소스만 읽으면 그 비용이 없다.
#
# **2026-08-16 CN-065 분해로 원본이 `services/market.py` 로 옮겨 갔다.** 이제는
# import 해도 무겁지 않지만 AST 로 읽는 방식을 그대로 둔다 — 검사가 보는 것은
# "그 함수 안의 상수" 이고, import 하면 상수가 아니라 **실행 결과**를 보게 된다.

SOURCE = (ROOT / "app" / "backend" / "services" / "market.py").read_text(encoding="utf-8")
TREE = ast.parse(SOURCE)

ORIGIN = next(
    node
    for node in ast.walk(TREE)
    if isinstance(node, ast.FunctionDef) and node.name == "portfolio_combination"
)
print(f"원본   : services/market.py:{ORIGIN.lineno}~{ORIGIN.end_lineno} "
      f"`{ORIGIN.name}` (AST · import 하지 않음)")


def literal_thresholds(fn: ast.FunctionDef) -> dict[str, float]:
    """함수 안의 `<` 비교를 전부 뽑아 `{비교 대상 표현: 임계값}` 으로 돌려준다.

    왼쪽 표현을 그대로 키로 쓴다(`ast.unparse`). 이렇게 하면 `len(close) < 21` 과
    `relationship < 0.30` 이 **어느 쪽 하한인지 헷갈릴 여지 없이** 구분된다.
    """
    found: dict[str, float] = {}
    for node in ast.walk(fn):
        if (
            isinstance(node, ast.Compare)
            and len(node.ops) == 1
            and isinstance(node.ops[0], ast.Lt)
            and isinstance(node.comparators[0], ast.Constant)
            and isinstance(node.comparators[0].value, (int, float))
        ):
            found[ast.unparse(node.left)] = node.comparators[0].value
    return found


def branch_texts(fn: ast.FunctionDef) -> list[dict[str, str]]:
    """`if relationship < … / elif … / else` 세 갈래가 대입하는 문자열을 순서대로.

    각 갈래에서 `이름 = "문자열"` 형태만 거둔다. 갈래마다
    `{signal, summary, hint}` 셋이 나온다 (`main.py:1215~1226`).
    """
    chain = next(
        node
        for node in ast.walk(fn)
        if isinstance(node, ast.If)
        and isinstance(node.test, ast.Compare)
        and ast.unparse(node.test.left) == "relationship"
    )

    def collect(body) -> dict[str, str]:
        out: dict[str, str] = {}
        for stmt in body:
            if (
                isinstance(stmt, ast.Assign)
                and len(stmt.targets) == 1
                and isinstance(stmt.targets[0], ast.Name)
                and isinstance(stmt.value, ast.Constant)
                and isinstance(stmt.value.value, str)
            ):
                out[stmt.targets[0].id] = stmt.value.value
        return out

    nested = chain.orelse[0]
    assert isinstance(nested, ast.If)
    return [collect(chain.body), collect(nested.body), collect(nested.orelse)]


def named_dict(fn: ast.FunctionDef, name: str) -> dict:
    """함수 안의 `name = {…}` 대입에서 상수 dict 를 꺼낸다."""
    for node in ast.walk(fn):
        if (
            isinstance(node, ast.Assign)
            and len(node.targets) == 1
            and isinstance(node.targets[0], ast.Name)
            and node.targets[0].id == name
            and isinstance(node.value, ast.Dict)
        ):
            return ast.literal_eval(node.value)
    raise AssertionError(f"services/market.py 에서 {name} 대입을 찾지 못했습니다")


def constant_422s(fn: ast.FunctionDef) -> list[str]:
    """`raise DomainError(422, "…")` 의 상수 문구들.

    2026-08-16 [CN-065] 분해 전에는 `raise HTTPException(status_code=422, detail="…")`
    였고, 이 함수도 그 모양(`func.id == "HTTPException"` · 키워드 `detail`)을 읽었다.
    서비스 계층이 HTTP 를 모르게 되면서 예외가 `services/errors.DomainError` 로
    바뀌었고 인자도 **위치 인자 둘**이 됐다. 읽는 모양만 따라 바꾼 것이고,
    **뽑아내는 문구는 같다** — 그래서 아래 18번 검사의 기대값은 손대지 않았다.

    f-string 으로 만드는 문구(종목명이 끼어드는 것)는 상수가 아니라 여기 담기지
    않는다. 이것도 옮기기 전과 같다.
    """
    out: list[str] = []
    for node in ast.walk(fn):
        if not (isinstance(node, ast.Raise) and isinstance(node.exc, ast.Call)):
            continue
        if getattr(node.exc.func, "id", "") != "DomainError":
            continue
        args = node.exc.args
        if (len(args) == 2
                and isinstance(args[0], ast.Constant) and args[0].value == 422
                and isinstance(args[1], ast.Constant)):
            out.append(args[1].value)
    return out


def response_keys(fn: ast.FunctionDef) -> list[str]:
    """함수가 돌려주는 dict 의 키들 (`main.py:1240~1249`)."""
    ret = next(
        node
        for node in ast.walk(fn)
        if isinstance(node, ast.Return) and isinstance(node.value, ast.Dict)
    )
    return [k.value for k in ret.value.keys if isinstance(k, ast.Constant)]


def regex_literal(fn: ast.FunctionDef) -> str:
    """`re.fullmatch("…", …)` 의 패턴 문자열 (`main.py:1181`)."""
    for node in ast.walk(fn):
        if (
            isinstance(node, ast.Call)
            and ast.unparse(node.func) == "re.fullmatch"
            and node.args
            and isinstance(node.args[0], ast.Constant)
        ):
            return node.args[0].value
    raise AssertionError("services/market.py 에서 re.fullmatch 패턴을 찾지 못했습니다")


THRESHOLDS = literal_thresholds(ORIGIN)
BRANCHES = branch_texts(ORIGIN)
ORIGIN_LABELS = named_dict(ORIGIN, "period_labels")
ORIGIN_422 = constant_422s(ORIGIN)
ORIGIN_KEYS = response_keys(ORIGIN)

# `relationship` 을 왼쪽에 둔 `<` 비교는 **두 개**다. dict 로 모으면 뒤엣것이 앞엣것을
# 덮어써 0.70 만 남으므로, 임계값 둘은 dict 가 아니라 분기 자체에서 읽어야 한다.
# 이 검사는 그 사실을 고정한다 — 갈래가 늘거나 줄면 여기서 먼저 걸린다.
check("1  판정 갈래 수", "원문", 2, sum(
    1 for n in ast.walk(ORIGIN)
    if isinstance(n, ast.Compare) and len(n.ops) == 1 and isinstance(n.ops[0], ast.Lt)
    and ast.unparse(n.left) == "relationship"
))
CHAIN = next(
    n for n in ast.walk(ORIGIN)
    if isinstance(n, ast.If) and isinstance(n.test, ast.Compare)
    and ast.unparse(n.test.left) == "relationship"
)
check("2  임계값 green 원문", "원문", service.GREEN_BELOW, CHAIN.test.comparators[0].value)
check("3  임계값 yellow 원문", "원문", service.YELLOW_BELOW,
      CHAIN.orelse[0].test.comparators[0].value)
check("4  하한 MIN_HISTORY", "원문", service.MIN_HISTORY, THRESHOLDS.get("len(close)"))
check("5  하한 MIN_OVERLAP", "원문", service.MIN_OVERLAP, THRESHOLDS.get("len(daily_moves)"))
# 21 과 20 이 서로 다른 것을 세고 있다는 관계까지 고정한다 (pct_change 가 첫 행을 지운다).
check("6  두 하한의 관계", "원문", service.MIN_HISTORY - 1, service.MIN_OVERLAP)

for idx, (num, key) in enumerate(((7, "green"), (8, "yellow"), (9, "red"))):
    check(f"{num}  신호 이름 {key}", "원문", key, BRANCHES[idx].get("signal"))
for idx, (num, key) in enumerate(((10, "green"), (11, "yellow"), (12, "red"))):
    check(f"{num} 요약 문장 {key}", "원문",
          BRANCHES[idx].get("summary"), service.VERDICTS[key]["summary"])
for idx, (num, key) in enumerate(((13, "green"), (14, "yellow"), (15, "red"))):
    check(f"{num} 힌트 문장 {key}", "원문",
          BRANCHES[idx].get("hint"), service.VERDICTS[key]["portfolio_hint"])

check("16 기간 라벨 4종", "원문", ORIGIN_LABELS, dict(service.PERIOD_LABELS))
check("17 종목 정규식", "원문", regex_literal(ORIGIN), service.TICKER_PATTERN)
check("18 422 문구 2종", "원문", sorted(ORIGIN_422),
      sorted([service.TICKER_INVALID, service.TICKER_SAME, service.OVERLAP_SHORT]))

# 응답 키가 하나라도 사라지면 화면이 조용히 깨진다. 새 경로는 원본의 키를 전부 갖는다
# (`period` 는 더 늘어난 것이라 부분집합으로 본다).
check("19 원본 응답 키 포함", "원문", [], sorted(set(ORIGIN_KEYS) - set(service.PERIOD_LABELS) - {
    "ticker_a", "ticker_b", "period_label", "signal", "summary",
    "portfolio_hint", "latest_data_at", "chart_points",
}))

# 차트 정규화 상수. `aligned_prices / aligned_prices.iloc[0] * 100` 와 `round(…, 4)`.
CHART_CONSTS = sorted({
    n.value for n in ast.walk(ORIGIN)
    if isinstance(n, ast.Constant) and isinstance(n.value, int) and n.value in (100, 4)
})
check("20 차트 기준선·자리", "원문", [service.CHART_DIGITS, service.CHART_BASE], CHART_CONSTS)

# NaN 이 원본에서 어떻게 흐르는지를 **추정하지 않고 재현**한다. services.classify 는
# 이것을 막지만, 막았다고 적으려면 무엇을 막았는지가 실측이어야 한다 (CN-103).
nan = float("nan")
origin_nan = ("green" if nan < CHAIN.test.comparators[0].value
              else "yellow" if nan < CHAIN.orelse[0].test.comparators[0].value
              else "red")
check("21 원본의 NaN 처리", "원문", "red", origin_nan, "  ← 계산 실패가 red 로 나간다")


# ─── 2. 고정 시계열 — 판정 규칙이 결정적인지 ────────────────────────────────
#
# 시세를 받지 않고 만든다. 설계한 상관계수가 그대로 나오도록 수익률을 먼저 만들고
# 가격을 누적곱으로 되돌린다 — `pct_change` 가 그 수익률을 그대로 복원한다.

INDEX = pd.bdate_range("2025-01-01", periods=260)
GEN = np.random.default_rng(20260811)
R_BASE = GEN.normal(0, 0.01, len(INDEX))
R_INDEP = GEN.normal(0, 0.01, len(INDEX))


def prices(returns, index=INDEX) -> pd.Series:
    return pd.Series(100.0 * np.cumprod(1 + returns), index=index)


# 0.6·기준 + 0.8·독립 → 기준과의 상관계수가 이론상 0.6 (yellow 한가운데).
FIXTURES: dict[str, pd.Series] = {
    "FIXA": prices(R_BASE),
    "FIXGREEN": prices(R_INDEP),
    "FIXMIX": prices(0.6 * R_BASE + 0.8 * R_INDEP),
    "FIXRED": prices(R_BASE),                      # 같은 수익률 → 상관계수 1
    "FIXFLAT": pd.Series(100.0, index=INDEX),      # 변화 없음 → 상관계수 NaN
    "FIXSHORT": prices(R_BASE[:20], INDEX[:20]),   # 20행 < MIN_HISTORY(21)
    # 각각은 21행을 넘지만 FIXA 와 겹치는 날이 15일뿐 → 변화 14개 < MIN_OVERLAP(20)
    "FIXOFF": prices(
        GEN.normal(0, 0.01, 25),
        INDEX[-15:].append(pd.bdate_range(INDEX[-1] + pd.offsets.BDay(1), periods=10)),
    ),
}


def fake_download(tickers, period):
    """`clients/yahoo_prices.download_closes` 와 같은 계약. 네트워크를 타지 않는다."""
    closes, unavailable = {}, []
    for ticker in tickers:
        series = FIXTURES.get(ticker)
        if series is None:
            unavailable.append(ticker)
        else:
            closes[ticker] = series
    return closes, unavailable


yahoo_prices.download_closes = fake_download


def preview(a: str, b: str, period: str = "1y"):
    return client.post("/api/combination/preview",
                       json={"ticker_a": a, "ticker_b": b, "period": period})


res = preview("FIXA", "FIXGREEN")
ok = check("22 green 판정", "preview", 200, res.status_code, f" {res.text[:70] if res.status_code != 200 else ''}")
green = res.json() if ok else {}
check("23 green 신호", "preview", "green", green.get("signal"))
check("24 yellow 신호", "preview", "yellow", preview("FIXA", "FIXMIX").json().get("signal"))
check("25 red 신호", "preview", "red", preview("FIXA", "FIXRED").json().get("signal"))

# 같은 입력은 같은 판정. 저장의 전제다 — 이 성질이 없으면 이력이 무엇을 말하는지 알 수 없다.
check("26 재현성", "preview", green, preview("FIXA", "FIXGREEN").json())

# 감사 전용 3종은 응답에 나가지 않는다 (`main.py:1208` 의 "수식은 노출하지 않는다").
check("27 감사 키 비노출", "preview", [],
      sorted(set(service.AUDIT_ONLY) & set(green)))
check("28 응답 키 집합", "preview",
      ["chart_points", "latest_data_at", "period", "period_label", "portfolio_hint",
       "signal", "summary", "ticker_a", "ticker_b"], sorted(green))
# 차트 점은 관측 수보다 하나 많다 — 종가 N행이 변화 N-1개를 낳는다.
check("29 차트 점 = 관측+1", "preview", len(INDEX), len(green.get("chart_points") or []))
check("30 차트 출발선 100", "preview", [100.0, 100.0],
      [(green.get("chart_points") or [{}])[0].get("a"),
       (green.get("chart_points") or [{}])[0].get("b")])

check("31 티커 정규화", "preview", ["FIXA", "FIXGREEN"],
      [preview(" fixa ", "fixgreen").json().get(k) for k in ("ticker_a", "ticker_b")])
check("32 같은 종목", "preview", 422, preview("FIXA", "FIXA").status_code)
check("33 종목 형식 위반", "preview", 422, preview("A!B", "FIXA").status_code)
check("34 기간 위반", "preview", 422, preview("FIXA", "FIXGREEN", "5y").status_code)

res = preview("FIXA", "FIXSHORT")
check("35 데이터 부족", "preview", 422, res.status_code)
check("36 부족 문구", "preview", "FIXSHORT의 충분한 가격 데이터를 찾지 못했습니다.",
      res.json().get("detail"))
res = preview("FIXA", "FIXGONE")
check("37 시세 못 받음", "preview", "FIXGONE의 충분한 가격 데이터를 찾지 못했습니다.",
      res.json().get("detail"))
res = preview("FIXA", "FIXOFF")
check("38 겹치는 날 부족", "preview", service.OVERLAP_SHORT, res.json().get("detail"))

# NaN 은 500 이다. 원본(검사 21)이 red 를 내던 자리이고, 503 이어서도 안 된다 —
# 다시 시도해도 같은 값이 나오므로 "잠시 후 다시" 는 거짓말이다.
res = preview("FIXA", "FIXFLAT")
check("39 NaN 은 500", "preview", 500, res.status_code)

check("40 기간 라벨 반영", "preview", "최근 3개월",
      preview("FIXA", "FIXGREEN", "3mo").json().get("period_label"))


# ─── 3. create — 실제로 원격에 넣는다 ───────────────────────────────────────

res = client.post("/api/combination/create",
                  json={"ticker_a": "FIXA", "ticker_b": "FIXGREEN", "period": "1y",
                        "anon_id": ANON_A})
ok = check("41 create 저장(A)", "create", 200, res.status_code,
           f" {res.text[:80] if res.status_code != 200 else ''}")
row_a = res.json() if ok else {}
if ok:
    created_ids.append(row_a["combination_id"])
check("42 create id 발급", "create", True, isinstance(row_a.get("combination_id"), int))
check("43 create=preview 본문", "create", green,
      {k: v for k, v in row_a.items() if k not in ("combination_id", "created_at")})

res = client.post("/api/combination/create",
                  json={"ticker_a": "FIXA", "ticker_b": "FIXRED", "period": "2y",
                        "anon_id": ANON_B})
ok = check("44 create 저장(B·red)", "create", 200, res.status_code,
           f" {res.text[:80] if res.status_code != 200 else ''}")
row_b = res.json() if ok else {}
if ok:
    created_ids.append(row_b["combination_id"])

res = client.post("/api/combination/create",
                  json={"ticker_a": "FIXA", "ticker_b": "FIXGREEN"})
check("45 create 소유자 없음", "create", 400, res.status_code)

res = client.post("/api/combination/create",
                  json={"ticker_a": "FIXA", "ticker_b": "FIXGREEN", "anon_id": ANON_A},
                  headers={"Authorization": f"Bearer {BAD_TOKEN}"})
check("46 create 토큰 무효", "create", 401, res.status_code)

res = client.post("/api/combination/create",
                  json={"ticker_a": "FIXA", "ticker_b": "FIXGREEN", "anon_id": "짧음"})
check("47 create anon_id 위반", "create", 422, res.status_code)

# 판정이 422 면 저장까지 가지 않는다. 실패한 판정이 이력에 남아서는 안 된다.
res = client.post("/api/combination/create",
                  json={"ticker_a": "FIXA", "ticker_b": "FIXA", "anon_id": ANON_A})
check("48 create 판정 실패", "create", 422, res.status_code)

res = with_dead_supabase(lambda: client.post(
    "/api/combination/create",
    json={"ticker_a": "FIXA", "ticker_b": "FIXGREEN", "anon_id": ANON_A}))
check("49 create 저장 실패", "create", 503, res.status_code)


# ─── 4. history ─────────────────────────────────────────────────────────────

res = client.get("/api/combination/history", params={"anon_id": ANON_A})
ok = check("50 history 정상(A)", "history", 200, res.status_code)
hist = res.json() if ok else {}
check("51 history A 는 1건", "history", 1, hist.get("total"))
check("52 history owner_type", "history", "anon", hist.get("owner_type"))
first = (hist.get("items") or [{}])[0]
check("53 history 판정 일치", "history",
      [row_a.get("signal"), row_a.get("summary"), row_a.get("portfolio_hint")],
      [first.get("signal"), first.get("summary"), first.get("portfolio_hint")])

res = client.get("/api/combination/history")
check("54 history 소유자 없음", "history", 400, res.status_code)

res = client.get("/api/combination/history", params={"anon_id": ANON_A},
                 headers={"Authorization": f"Bearer {BAD_TOKEN}"})
check("55 history 토큰 무효", "history", 401, res.status_code)

res = client.get("/api/combination/history", params={"anon_id": ANON_A, "limit": 101})
check("56 history limit 범위", "history", 422, res.status_code)

res = with_dead_supabase(
    lambda: client.get("/api/combination/history", params={"anon_id": ANON_A}))
check("57 history 조회 실패", "history", 503, res.status_code)


# ─── 5. detail — 저장한 것이 그대로 되살아나는지 ────────────────────────────

id_a = row_a.get("combination_id", 0)
res = client.get("/api/combination/detail", params={"id": id_a, "anon_id": ANON_A})
ok = check("58 detail 정상(A)", "detail", 200, res.status_code)
detail = res.json() if ok else {}

# **빠지는 필드가 정확히 chart_points 하나** 임을 고정한다. 문서로 적으면 나중에
# 하나 더 빠져도 아무도 모른다. F05 는 여기서 빠지는 것이 0개였다.
check("59 create−detail 차이", "detail", ["chart_points"],
      sorted(set(row_a) - set(detail)))
check("60 detail−create 차이", "detail", [], sorted(set(detail) - set(row_a)))
check("61 detail 겹치는 값", "detail",
      {k: v for k, v in row_a.items() if k != "chart_points"}, detail)
check("62 detail 라벨 재구성", "detail", service.PERIOD_LABELS["1y"],
      detail.get("period_label"))
# 왕복이 시각 문자열을 바꾸지 않았는지. `_naive_utc_iso` 가 하는 일의 결과다.
check("63 detail 시각 왕복", "detail", green.get("latest_data_at"),
      detail.get("latest_data_at"))

res = client.get("/api/combination/detail", params={"id": id_a, "anon_id": ANON_B})
check("64 detail 남의 행", "detail", 403, res.status_code)

res = client.get("/api/combination/detail", params={"id": 999_999_999, "anon_id": ANON_A})
check("65 detail 없는 행", "detail", 404, res.status_code)

res = client.get("/api/combination/detail", params={"anon_id": ANON_A})
check("66 detail id 누락", "detail", 422, res.status_code)

res = client.get("/api/combination/detail", params={"id": 0, "anon_id": ANON_A})
check("67 detail id 범위", "detail", 422, res.status_code)

res = client.get("/api/combination/detail", params={"id": id_a})
check("68 detail 소유자 없음", "detail", 400, res.status_code)

res = client.get("/api/combination/detail", params={"id": id_a, "anon_id": ANON_A},
                 headers={"Authorization": f"Bearer {BAD_TOKEN}"})
check("69 detail 토큰 무효", "detail", 401, res.status_code)

res = with_dead_supabase(lambda: client.get(
    "/api/combination/detail", params={"id": id_a, "anon_id": ANON_A}))
check("70 detail 조회 실패", "detail", 503, res.status_code)


# ─── 6. 감사 컬럼 — 응답에 없는 값이 실제로 저장됐는가 ──────────────────────
#
# 이 세션이 컬럼 3종을 더한 이유가 "되짚을 수 있게" 인데, 응답에 나오지 않으므로
# API 로는 확인할 수 없다. 원격을 직접 읽는다.

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
        with urllib.request.urlopen(req, timeout=15) as res_:
            raw = res_.read()
            return res_.status, (json.loads(raw) if raw else None)
    except urllib.error.HTTPError as exc:
        return exc.code, exc.read().decode("utf-8", "replace")[:300]


status, raw_rows = rest("GET", f"combination_query?id=eq.{id_a}&select=*")
raw = (raw_rows or [{}])[0] if isinstance(raw_rows, list) else {}

# 응답의 관측 수는 없지만 preview 의 차트 점 수에서 역산된다 (점 N개 = 변화 N-1개).
check("71 감사 관측 수", "원격", len(INDEX) - 1, raw.get("observation_count"))

# 상관계수는 응답에 없으므로 **여기서 다시 계산해** 저장값과 대조한다. 범위 검사로
# 넘기지 않는 이유는 CN-098 과 같다 — 대조한 정밀도만 주장할 수 있고, "−1 과 1 사이"
# 는 아무것도 주장하지 않는다.
local = service.build_combination(
    "FIXA", "FIXGREEN", "1y",
    {"FIXA": FIXTURES["FIXA"], "FIXGREEN": FIXTURES["FIXGREEN"]}, [],
)
check("72 감사 상관계수 값", "원격", local["relationship"], float(raw.get("relationship")),
      f"  ← 원문 {raw.get('relationship')!r}")
# 검사 대상(`combination_repo._naive_utc_iso`)을 쓰지 않고 여기서 따로 판다.
# 같은 함수로 양쪽을 만들면 그 함수가 틀렸을 때 둘 다 같이 틀려 통과한다.
check("73 감사 창 시작 값", "원격", local["observed_from"],
      datetime.fromisoformat(raw.get("observed_from") or "")
      .astimezone(timezone.utc).replace(tzinfo=None).isoformat())

# `_naive_utc_iso` 가 왜 필요한지의 실측. 보낸 문자열과 돌아온 문자열이 다르다.
print(f"\n  실측 — 보낸 latest_data_at : {green.get('latest_data_at')}")
print(f"  실측 — 원격이 돌려준 원문   : {raw.get('latest_data_at')}")
print(f"  실측 — 정규화 후 detail     : {detail.get('latest_data_at')}")


# ─── 7. DB 백스톱 — 도메인 계층이 뚫려도 제약이 잡는가 ──────────────────────
#
# 마이그레이션 20260811130000 이 더한 제약 3종이 실제로 동작하는지 직접 찌른다.
# services 가 먼저 걸러 여기 도달할 일은 없어야 하지만, "없어야 한다" 와
# "막혀 있다" 는 다르다.

BAD_BASE = {
    "anon_id": ANON_A, "ticker_a": "FIXA", "ticker_b": "FIXGREEN", "period": "1y",
    "signal": "green", "summary": "백스톱 검사", "portfolio_hint": None,
    "latest_data_at": "2026-08-10T00:00:00", "observed_from": "2025-08-10T00:00:00",
    "relationship": 0.5, "observation_count": 100,
}
status, _ = rest("POST", "combination_query", {**BAD_BASE, "relationship": 1.5})
check("74 제약 상관계수", "원격", 400, status)
status, _ = rest("POST", "combination_query", {**BAD_BASE, "observation_count": 19})
check("75 제약 관측 하한", "원격", 400, status)
status, _ = rest("POST", "combination_query",
                 {**BAD_BASE, "observed_from": "2026-09-01T00:00:00"})
check("76 제약 창 순서", "원격", 400, status)
status, _ = rest("POST", "combination_query", {**BAD_BASE, "latest_data_at": None})
check("77 제약 시각 NOT NULL", "원격", 400, status)


# ─── 8. 결과 ────────────────────────────────────────────────────────────────

print()
print(f"{'검사':<24} {'대상':<8} {'기대':<11} {'실측':<11} 판정")
print("-" * 78)
for name, endpoint, expected, got, ok in results:
    print(f"{name:<24} {endpoint:<8} {expected[:10]:<11} {got[:10]:<11} {'✅' if ok else '❌'}")

passed = sum(1 for *_, ok in results if ok)
print("-" * 78)
print(f"{passed} / {len(results)} 통과")

if passed != len(results):
    print("\n실패한 검사:")
    for name, endpoint, expected, got, ok in results:
        if not ok:
            print(f"  ❌ {name} ({endpoint})\n     기대: {expected[:300]}\n     실측: {got[:300]}")


def delete_created() -> int:
    """검증이 만든 행을 지운다. 백스톱 검사(74~77)는 전부 거부되므로 남는 것이 없다."""
    if not (BASE and KEY and created_ids):
        return 0
    ids = ",".join(str(i) for i in created_ids)
    status_, rows = rest("DELETE", f"combination_query?id=in.({urllib.parse.quote(ids)})",
                         extra_headers={"Prefer": "return=representation"})
    if status_ >= 400:
        print(f"  ⚠ 정리 실패 — 남은 id: {ids} ({rows})")
        return -1
    return len(rows) if isinstance(rows, list) else 0


print(f"\n정리 — 검증이 만든 행 {len(created_ids)}개 삭제…")
print(f"  삭제된 combination_query: {delete_created()}행")

raise SystemExit(0 if passed == len(results) else 1)
