#!/usr/bin/env python3
"""H · 라우트 보존 검사 — 분해하는 동안 엔드포인트가 사라지지 않았는가.

[CN-065](docs/spec/00-index/변경이력.md#cn-065) 분해 순서 ⑤~⑦ 을 위해 만든 **안전망**이다.
`main.py` 2,693줄에서 라우트 22개를 들어내 `routers/` 로 옮기는 작업은, 옮기다
하나를 빠뜨려도 **아무것도 실패하지 않는다** — 앱은 그대로 뜨고, 남은 67개는
정상이며, 사라진 하나는 그 화면을 누를 때까지 아무도 모른다.

`check_layers.py` 는 이것을 잡지 못한다. 라우트를 통째로 지우면 `main.py` 가
200줄 밑으로 내려가 **오히려 통과한다.** 계층 검사와 이 검사는 서로 반대
방향으로 당기고, 그래서 둘이 함께 있어야 분해가 안전하다.

## 무엇을 기준으로 하는가

**분해 직전(2026-08-16 · `0688f0a`)의 실측 68개다.** 목표가 아니라 사실이고,
그래서 `check_layers.py` 의 `BASELINE` 과 성격이 다르다 — 저쪽은 나아지면 내려
적지만, 이쪽은 **바뀌면 안 되는 값**이다.

    $ .venv/bin/python scripts/check_routes.py     # 실측 2026-08-16
    68 개 — 전부 제자리

라우트를 **의도적으로** 더하거나 뺐다면 `EXPECTED` 를 고치고, 무엇을 왜 바꿨는지
변경노트에 적는다. 고치지 않으면 이 검사가 막는다. 그것이 목적이다.

## 왜 `ast` 인가 — 띄워서 세지 않는다

`main.py` 는 import 시점에 `torch`·`diffusers` 를 끌어와 1.6GB 가 필요하고
(`verify_smoke.py` 와 같은 사정), `routers/ml.py` 도 마찬가지다. 그래서 **소스만
읽는다.** 대신 띄웠다면 알 수 있었을 것 하나를 잃는다 — *"파일에는 있는데 앱에
붙지 않은 라우터"* 다. 그 구멍을 ② 가 따로 막는다.

## 두 가지를 본다

    ① 경로 집합    — (메서드, 경로) 68개가 그대로인가
    ② 마운트       — 라우트를 가진 `routers/` 모듈이 전부 `include_router` 되는가

②가 없으면 분해가 **조용히 실패한다.** 새 라우터 파일을 만들고 `main.py` 에
`include_router` 를 빠뜨리는 것이 이 작업에서 가장 하기 쉬운 실수이고, ① 만으로는
잡히지 않는다 — 경로는 소스에 멀쩡히 있기 때문이다.

## 실행

    .venv/bin/python scripts/check_routes.py

네트워크도 자격증명도 필요 없다. 종료 코드 — 0 통과 · 1 어긋남.
"""

from __future__ import annotations

import ast
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
BACKEND = ROOT / "app" / "backend"

HTTP_METHODS = frozenset({"get", "post", "put", "patch", "delete", "head", "options"})

# 분해 직전 실측 68개(`0688f0a` · 2026-08-16). 정렬해 둔 것은 diff 를 읽기 쉽게 하려는 것뿐이다.
EXPECTED: frozenset[tuple[str, str]] = frozenset({
    ("DELETE", "/api/admin/rag/documents/{source_doc}"),
    ("GET", "/api/admin/rag/documents"),
    ("GET", "/api/backtest-lab/config"),
    ("GET", "/api/backtest-lab/detail"),
    ("GET", "/api/backtest-lab/history"),
    ("GET", "/api/combination/detail"),
    ("GET", "/api/combination/history"),
    ("GET", "/api/health"),
    ("GET", "/api/home/box-range"),
    ("GET", "/api/home/kospi-candle"),
    ("GET", "/api/home/market-candle"),
    ("GET", "/api/macro/kospi-ex/meta"),
    ("GET", "/api/market/volume-cloud"),
    ("GET", "/api/ml/decision-boundary"),
    ("GET", "/api/rag/status"),
    ("GET", "/api/recommendation/detail"),
    ("GET", "/api/recommendation/history"),
    ("GET", "/api/simulation/detail"),
    ("GET", "/api/simulation/history"),
    ("GET", "/api/system/resources"),
    ("GET", "/api/tax/sample"),
    ("GET", "/files/{file_name}"),
    ("POST", "/api/admin/rag/reindex"),
    ("POST", "/api/backtest-lab/report"),
    ("POST", "/api/backtest-lab/run"),
    ("POST", "/api/backtest-lab/save"),
    ("POST", "/api/combination/create"),
    ("POST", "/api/combination/preview"),
    ("POST", "/api/cv/circle-animation"),
    ("POST", "/api/dart/company-list"),
    ("POST", "/api/dart/company-search"),
    ("POST", "/api/dart/financial-analysis"),
    ("POST", "/api/dart/group-network"),
    ("POST", "/api/dl/cnn-timeseries"),
    ("POST", "/api/dl/lstm-predictor"),
    ("POST", "/api/dl/transformer-timeseries"),
    ("POST", "/api/finance/company-financials"),
    ("POST", "/api/genai/text-to-image"),
    ("POST", "/api/industry/lifecycle"),
    ("POST", "/api/industry/peer"),
    ("POST", "/api/industry/porter"),
    ("POST", "/api/industry/sector"),
    ("POST", "/api/macro/kospi-ex"),
    ("POST", "/api/macro/realtime"),
    ("POST", "/api/macro/simulation"),
    ("POST", "/api/market/portfolio-combination"),
    ("POST", "/api/market/snapshot"),
    ("POST", "/api/ml/cross-validation"),
    ("POST", "/api/ml/kmeans"),
    ("POST", "/api/ml/linear-regression"),
    ("POST", "/api/ml/mlp"),
    ("POST", "/api/ml/random-forest"),
    ("POST", "/api/ml/svm"),
    ("POST", "/api/nlp/text-classify"),
    ("POST", "/api/quant/backtest"),
    ("POST", "/api/quant/financial-knowledge"),
    ("POST", "/api/quant/pipeline"),
    ("POST", "/api/quant/portfolio"),
    ("POST", "/api/quant/portfolio-scenario"),
    ("POST", "/api/quant/risk"),
    ("POST", "/api/rag/ask"),
    ("POST", "/api/recommendation/create"),
    ("POST", "/api/recommendation/preview"),
    ("POST", "/api/simulation/create"),
    ("POST", "/api/simulation/preview"),
    ("POST", "/api/tax/simulate"),
    ("POST", "/api/tax/upload"),
    ("POST", "/api/visitors/heartbeat"),
})


def _router_prefix(tree: ast.Module) -> str:
    """`APIRouter(prefix=...)` 의 접두사. 없으면 빈 문자열이다."""
    for node in ast.walk(tree):
        if not (isinstance(node, ast.Assign) and isinstance(node.value, ast.Call)):
            continue
        func = node.value.func
        name = getattr(func, "id", None) or getattr(func, "attr", None)
        if name != "APIRouter":
            continue
        for keyword in node.value.keywords:
            if keyword.arg == "prefix":
                try:
                    return ast.literal_eval(keyword.value)
                except ValueError:
                    return ""
    return ""


def collect_routes() -> dict[tuple[str, str], str]:
    """`{(메서드, 경로): 파일:줄}`. `app.get(...)` 과 `router.get(...)` 을 모두 본다."""
    found: dict[tuple[str, str], str] = {}
    for path in sorted(BACKEND.rglob("*.py")):
        if "__pycache__" in path.parts:
            continue
        tree = ast.parse(path.read_text(encoding="utf-8"))
        prefix = _router_prefix(tree)
        for node in ast.walk(tree):
            if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            for deco in node.decorator_list:
                if not (isinstance(deco, ast.Call) and isinstance(deco.func, ast.Attribute)):
                    continue
                method = deco.func.attr
                if method not in HTTP_METHODS or not deco.args:
                    continue
                try:
                    route = ast.literal_eval(deco.args[0])
                except ValueError:
                    continue
                # `app.get` 은 절대 경로, `router.get` 은 접두사가 붙는다.
                base = getattr(deco.func.value, "id", "")
                full = route if base == "app" else prefix + route
                found[(method.upper(), full)] = (
                    f"{path.relative_to(ROOT).as_posix()}:{node.lineno}"
                )
    return found


def _include_names(tree: ast.Module) -> set[str]:
    """`main.py` 가 `app.include_router(X)` 로 붙인 이름들."""
    names: set[str] = set()
    for node in ast.walk(tree):
        if not (isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)):
            continue
        if node.func.attr != "include_router" or not node.args:
            continue
        arg = node.args[0]
        if isinstance(arg, ast.Name):
            names.add(arg.id)
    return names


def _imported_routers(tree: ast.Module) -> dict[str, str]:
    """`from .routers.X import router as Y` → `{Y: X}`. try/except 양쪽 다 잡힌다."""
    mapping: dict[str, str] = {}
    for node in ast.walk(tree):
        if not isinstance(node, ast.ImportFrom) or not node.module:
            continue
        parts = node.module.split(".")
        if "routers" not in parts:
            continue
        for alias in node.names:
            if alias.name == "router" and alias.asname:
                mapping[alias.asname] = parts[-1]
            elif alias.name != "router":
                # `from .routers import a, b` 형태 — 모듈을 직접 가져온 경우다.
                mapping.setdefault(alias.asname or alias.name, alias.name)
    return mapping


def check_mounted() -> list[str]:
    """라우트를 가진 `routers/` 모듈 중 `main.py` 가 붙이지 않은 것."""
    main_tree = ast.parse((BACKEND / "main.py").read_text(encoding="utf-8"))
    mounted_modules = {
        module
        for name, module in _imported_routers(main_tree).items()
        if name in _include_names(main_tree)
    }

    orphans: list[str] = []
    for path in sorted((BACKEND / "routers").glob("*.py")):
        if path.stem in {"__init__"}:
            continue
        tree = ast.parse(path.read_text(encoding="utf-8"))
        has_route = any(
            isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
            and any(
                isinstance(d, ast.Call)
                and isinstance(d.func, ast.Attribute)
                and d.func.attr in HTTP_METHODS
                for d in node.decorator_list
            )
            for node in ast.walk(tree)
        )
        if has_route and path.stem not in mounted_modules:
            orphans.append(path.relative_to(ROOT).as_posix())
    return orphans


def main() -> int:
    found = collect_routes()
    actual = frozenset(found)

    missing = sorted(EXPECTED - actual)
    added = sorted(actual - EXPECTED)
    orphans = check_mounted()

    print()
    if missing:
        print(f"사라진 라우트 {len(missing)}개 — 옮기다 빠뜨렸습니다")
        for method, route in missing:
            print(f"        · {method:6} {route}")
    if added:
        print(f"기준에 없는 라우트 {len(added)}개 — 의도한 것이면 EXPECTED 에 더하세요")
        for method, route in added:
            print(f"        · {method:6} {route}    {found[(method, route)]}")
    if orphans:
        print(f"앱에 붙지 않은 라우터 {len(orphans)}개 — main.py 의 include_router 가 빠졌습니다")
        for path in orphans:
            print(f"        · {path}")

    if missing or added or orphans:
        print(f"\n{len(actual)} 개 실측 / {len(EXPECTED)} 개 기준 — **어긋납니다**")
        return 1

    print(f"{len(actual)} 개 — 전부 제자리")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
