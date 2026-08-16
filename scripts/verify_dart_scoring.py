#!/usr/bin/env python3
"""B · DART 재무 비율·점수 계산 검사 — `_calc_dart_ratios` · `_score_financial_health`.

[테스트-계획 5.1절] 최소셋 7종 중 **B**. 문서가 적은 이유는
*"순수 계산. CN-046 결측 처리 변경의 회귀 방지"* 다.

## `main.py` 안의 함수를 어떻게 부르는가 — 옮기지 않고 떼어 온다

두 함수는 `main.py:2341` · `:2376` 에 있고, `main.py` 는 import 하면
`torch`·`diffusers`·`matplotlib` 를 끌고 온다(1.6GB). 앞선 세션들이 세 가지 방법을
썼다 — 상수만 AST 로 비교(CN-106) · 힙독을 텍스트로 떼어 컴파일(CN-119) ·
바뀌는 부분을 `services/` 로 꺼내기(CN-123).

여기서는 **네 번째**를 쓴다. `ast` 로 두 함수의 정의 노드만 떼어 내 컴파일하고,
**전역이 비어 있는 이름공간에서 실행**한다. 셋과 다른 점:

- CN-123 처럼 코드를 옮기지 않는다. 이번엔 **바뀌는 것이 없다** — 검사를 붙이려고
  운영 코드를 움직이면 그 움직임 자체가 회귀 위험이다.
- CN-106 처럼 상수만 보지 않는다. **함수를 진짜로 부른다.**
- 전역을 비워 두는 것이 그 자체로 검사다. 두 함수가 모듈 전역에 손을 뻗는 순간
  `NameError` 로 죽는다 — "순수 계산" 이라는 전제가 깨지면 즉시 드러난다.

검사하는 것은 **`main.py` 안의 바로 그 바이트**다. 사본이 아니다.

## 무엇을 고정하는가

`_score_financial_health` 의 결측 규칙(값이 없으면 만점의 50%)은 CN-046 이
*"바꾸지 않고 그대로 뒀다"* 고 명시한 것이다. 그 결정이 살아 있는지가 이 검사의
1순위이고, 그 규칙 때문에 `services/dart_outlook.assess` 가 결측 2개부터 등급을
보류한다 — **두 계층의 접점까지 함께 밟는다**(섹션 ⑥).

라벨 6개도 고정한다. `verify_r07_expressions.py:122~129` 의 `FULL` 이 그 이름과
배점을 **손으로 적어** 두고 있는데, 지금까지 그것이 실제 값과 같은지는 아무도
검사하지 않았다. 어긋나면 F23 화면이 조용히 깨진다.

## 실행

    .venv/bin/python scripts/verify_dart_scoring.py

네트워크도 자격증명도 DART 키도 필요 없다.
"""

from __future__ import annotations

import ast
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
sys.path.insert(0, str(ROOT / "app" / "backend"))

from services import dart_outlook  # noqa: E402
from sourcetext import code_only  # noqa: E402

MAIN = ROOT / "app" / "backend" / "main.py"
WANTED = ("_calc_dart_ratios", "_score_financial_health")

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
# ① 떼어 오기 — main.py 를 import 하지 않고 두 함수만 컴파일한다
# ─────────────────────────────────────────────────────────────────────────────

def extract() -> dict[str, object]:
    """`main.py` 에서 두 함수의 정의만 떼어 내 **빈 전역**에서 실행한다."""
    tree = ast.parse(MAIN.read_text(encoding="utf-8"))
    picked = [
        node for node in tree.body
        if isinstance(node, ast.FunctionDef) and node.name in WANTED
    ]
    module = ast.Module(body=picked, type_ignores=[])
    namespace: dict[str, object] = {}
    # `__builtins__` 만 있고 `main.py` 의 전역은 하나도 없다. 두 함수가 바깥을
    # 참조하면 여기서가 아니라 **호출할 때** NameError 로 죽는다 — 섹션 ②가 부른다.
    exec(compile(ast.fix_missing_locations(module), str(MAIN), "exec"), namespace)
    return namespace


NS = extract()
calc = NS.get("_calc_dart_ratios")
score = NS.get("_score_financial_health")


def _fin(**amounts: tuple[float, float]) -> dict[str, dict[str, float]]:
    """`_parse_dart_amounts` 가 주는 모양. `키=(당기, 전기)`."""
    return {key: {"current": cur, "prior": prior} for key, (cur, prior) in amounts.items()}


def verify_extraction() -> None:
    names = sorted(n for n in NS if not n.startswith("__"))
    check("① 두 함수를 떼어 왔다", "main.py", sorted(WANTED), names)
    check("① main.py 가 실제로 그 둘을 부른다", "main.py", (True, True),
          ("_calc_dart_ratios(fin)" in code_only(MAIN),
           "_score_financial_health(ratios)" in code_only(MAIN)))


# ─────────────────────────────────────────────────────────────────────────────
# ② 비율 10개 — 손계산과 대조
# ─────────────────────────────────────────────────────────────────────────────

# 딱 떨어지는 수로 골랐다. 부동소수 반올림을 검사가 흡수하지 않게 하기 위해서다.
SAMPLE = _fin(
    revenue=(1_000.0, 800.0),
    op_income=(150.0, 0.0),
    net_income=(100.0, 0.0),
    total_assets=(2_000.0, 0.0),
    total_liabilities=(800.0, 0.0),
    total_equity=(1_200.0, 1_000.0),
    current_assets=(600.0, 0.0),
    current_liabilities=(300.0, 0.0),
    retained_earnings=(900.0, 0.0),
)

EXPECTED_RATIOS = {
    "debt_equity_ratio": 800 / 1200 * 100,      # 부채 / 자본
    "op_margin":         150 / 1000 * 100,
    "net_margin":        100 / 1000 * 100,
    "roe":               100 / 1200 * 100,
    "roa":               100 / 2000 * 100,
    "current_ratio":     600 / 300 * 100,
    "revenue_growth":    (1000 - 800) / 800 * 100,
    "equity_growth":     (1200 - 1000) / 1000 * 100,
    "retained_ratio":    900 / 1200 * 100,
    "debt_ratio":        800 / 2000 * 100,
}


def verify_ratios() -> None:
    got = calc(SAMPLE)  # type: ignore[operator]
    check("② 비율 10개 값", "_calc_dart_ratios", EXPECTED_RATIOS, got)

    # 분모가 0 이면 None 이다. 0 이 아니라 None 이어야 채점이 결측으로 읽는다.
    zeros = calc(_fin(  # type: ignore[operator]
        revenue=(0.0, 0.0), op_income=(10.0, 0.0), net_income=(10.0, 0.0),
        total_assets=(0.0, 0.0), total_liabilities=(10.0, 0.0),
        total_equity=(0.0, 0.0), current_assets=(10.0, 0.0),
        current_liabilities=(0.0, 0.0), retained_earnings=(10.0, 0.0),
    ))
    check("② 분모 0 은 전부 None", "_calc_dart_ratios",
          [None] * 10, list(zeros.values()))

    # 전기 매출이 0 이면 성장률을 만들지 않는다 (첫 공시 회사).
    first = calc(_fin(  # type: ignore[operator]
        revenue=(1_000.0, 0.0), op_income=(0.0, 0.0), net_income=(0.0, 0.0),
        total_assets=(1.0, 0.0), total_liabilities=(0.0, 0.0),
        total_equity=(1.0, 0.0), current_assets=(0.0, 0.0),
        current_liabilities=(1.0, 0.0), retained_earnings=(0.0, 0.0),
    ))
    check("② 전기 값이 0 이면 성장률은 None", "_calc_dart_ratios",
          (None, None), (first["revenue_growth"], first["equity_growth"]))

    # 계산은 10개인데 채점은 6개다. 넷(net_margin·roa·equity_growth·debt_ratio)은
    # 화면 표시용이다. 이 차이를 적어 두지 않으면 "점수에 반영된다" 고 오해한다.
    scored = {"debt_equity_ratio", "op_margin", "roe",
              "current_ratio", "revenue_growth", "retained_ratio"}
    check("② 계산 10개 중 채점은 6개", "_calc_dart_ratios/_score",
          (10, 6), (len(EXPECTED_RATIOS), len(scored & set(EXPECTED_RATIOS))))


# ─────────────────────────────────────────────────────────────────────────────
# ③ 배점과 라벨 — dart_outlook · verify_r07_expressions 가 기대하는 그대로인가
# ─────────────────────────────────────────────────────────────────────────────

# `_score_financial_health` 안의 순서·배점 그대로. 라벨은 `verify_r07_expressions.FULL`
# 이 손으로 들고 있는 것과 같아야 한다.
EXPECTED_ITEMS = [
    ("부채비율", 20),
    ("영업이익률", 20),
    ("자기자본이익률(ROE)", 15),
    ("유동비율", 15),
    ("매출 성장률", 15),
    ("이익잉여금 비율", 15),
]

ALL_NONE = dict.fromkeys(EXPECTED_RATIOS, None)


def verify_items() -> None:
    total, breakdown = score(ALL_NONE)  # type: ignore[operator]

    check("③ 항목 이름과 배점", "_score_financial_health", EXPECTED_ITEMS,
          [(label, item["max"]) for label, item in breakdown.items()])
    check("③ 배점 합이 100", "_score_financial_health", 100,
          sum(m for _, m in EXPECTED_ITEMS))

    # verify_r07_expressions.py 의 FULL 이 손으로 적어 둔 값. 어긋나면 그 검사가
    # 존재하지 않는 항목을 꽂아 검사하게 된다 — 통과하지만 아무것도 안 본다.
    from verify_r07_expressions import FULL  # noqa: PLC0415

    check("③ verify_r07_expressions.FULL 과 이름·배점이 같다", "FULL",
          EXPECTED_ITEMS, [(label, mx) for label, _, mx, _ in FULL])


# ─────────────────────────────────────────────────────────────────────────────
# ④ 결측 규칙 — CN-046 이 "그대로 뒀다" 고 적은 그것
# ─────────────────────────────────────────────────────────────────────────────

def verify_missing_rule() -> None:
    total, breakdown = score(ALL_NONE)  # type: ignore[operator]

    check("④ 전 항목 결측이면 만점의 절반", "_score_financial_health", 50.0, total)
    check("④ 항목마다 배점의 50%", "_score_financial_health",
          [m * 0.5 for _, m in EXPECTED_ITEMS],
          [item["score"] for item in breakdown.values()])
    check("④ 결측은 value 가 None 으로 남는다", "_score_financial_health",
          [None] * 6, [item["value"] for item in breakdown.values()])

    # 결측이 점수를 **올린다.** 실제로 나쁜 회사가 결측 덕에 나아 보이는 경로다 —
    # dart_outlook 이 등급을 보류하는 이유가 이것이고, 그 이유를 수치로 남긴다.
    worst = {"debt_equity_ratio": 100_000.0, "op_margin": -100.0, "roe": -100.0,
             "current_ratio": 0.0, "revenue_growth": -100.0, "retained_ratio": -100.0}
    floor, _ = score(worst)  # type: ignore[operator]
    check("④ 전 항목 최저는 0점", "_score_financial_health", 0.0, floor)

    half_missing = dict(worst, revenue_growth=None, retained_ratio=None)
    lifted, _ = score(half_missing)  # type: ignore[operator]
    check("④ 결측 2개가 0점을 15점으로 올린다", "_score_financial_health",
          15.0, lifted, "  (최저 0.0 → 결측 2개 15.0)")


# ─────────────────────────────────────────────────────────────────────────────
# ⑤ 임계값 경계 — `>=` 이므로 경계값 자체는 위 등급이다
# ─────────────────────────────────────────────────────────────────────────────

BEST = {"debt_equity_ratio": 0.0, "op_margin": 100.0, "roe": 100.0,
        "current_ratio": 1_000.0, "revenue_growth": 100.0, "retained_ratio": 100.0}

# (비율 이름, 라벨, [(값, 기대 점수)]). 각 구간의 **경계와 경계 바로 아래**를 밟는다.
BOUNDARIES = [
    ("debt_equity_ratio", "부채비율",
     [(50.0, 20.0), (50.1, 16.0), (100.0, 16.0), (100.1, 10.0),
      (200.0, 10.0), (200.1, 5.0), (300.0, 5.0), (300.1, 0.0)]),
    ("op_margin", "영업이익률",
     [(20.0, 20.0), (19.9, 16.0), (10.0, 16.0), (9.9, 10.0),
      (5.0, 10.0), (4.9, 5.0), (0.0, 5.0), (-0.1, 0.0)]),
    ("roe", "자기자본이익률(ROE)",
     [(20.0, 15.0), (19.9, 12.0), (10.0, 12.0), (9.9, 8.0),
      (5.0, 8.0), (4.9, 4.0), (0.0, 4.0), (-0.1, 0.0)]),
    ("current_ratio", "유동비율",
     [(200.0, 15.0), (199.9, 12.0), (150.0, 12.0), (149.9, 8.0),
      (100.0, 8.0), (99.9, 4.0), (50.0, 4.0), (49.9, 0.0)]),
    ("revenue_growth", "매출 성장률",
     [(15.0, 15.0), (14.9, 12.0), (5.0, 12.0), (4.9, 7.0),
      (0.0, 7.0), (-0.1, 3.0), (-10.0, 3.0), (-10.1, 0.0)]),
    ("retained_ratio", "이익잉여금 비율",
     [(70.0, 15.0), (69.9, 12.0), (50.0, 12.0), (49.9, 8.0),
      (30.0, 8.0), (29.9, 4.0), (10.0, 4.0), (9.9, 0.0)]),
]


def verify_boundaries() -> None:
    for key, label, cases in BOUNDARIES:
        got = []
        for value, _ in cases:
            _, breakdown = score(dict(BEST, **{key: value}))  # type: ignore[operator]
            got.append(breakdown[label]["score"])
        check(f"⑤ {label} 구간 경계 {len(cases)}칸", "_score_financial_health",
              [expected for _, expected in cases], got)

    check("⑤ 전 항목 최고는 100점", "_score_financial_health", 100.0,
          score(BEST)[0])  # type: ignore[operator]

    # 부채비율만 역방향이다 (낮을수록 좋다). 부호를 뒤집어 같은 `>=` 표를 쓴다.
    low, _ = score(dict(BEST, debt_equity_ratio=10.0))   # type: ignore[operator]
    high, _ = score(dict(BEST, debt_equity_ratio=400.0))  # type: ignore[operator]
    check("⑤ 부채비율은 낮을수록 높은 점수", "_score_financial_health",
          True, low > high, f"  ({low} > {high})")


# ─────────────────────────────────────────────────────────────────────────────
# ⑥ 접점 — 이 점수를 받은 dart_outlook 이 무엇이라 하는가
# ─────────────────────────────────────────────────────────────────────────────

def verify_handoff() -> None:
    """B(계산) 와 CN-046(표기) 사이를 잇는다. 둘을 따로 검사하면 이 사이가 빈다."""
    _, full = score(BEST)  # type: ignore[operator]
    good = dart_outlook.assess(100.0, "A+", full)
    check("⑥ 만점이면 판정을 낸다", "assess", (False, "재무 양호"),
          (good["withheld"], good["outlook"]))

    _, one = score(dict(BEST, retained_ratio=None))  # type: ignore[operator]
    r1 = dart_outlook.assess(92.5, "A+", one)
    check("⑥ 결측 1개는 판정을 낸다", "assess", (False, ["이익잉여금 비율"]),
          (r1["withheld"], r1["missing"]))

    _, two = score(dict(BEST, retained_ratio=None, revenue_growth=None))  # type: ignore[operator]
    r2 = dart_outlook.assess(85.0, "A", two)
    check("⑥ 결측 2개는 판정을 보류한다", "assess",
          (True, "판정 보류 — 재무 자료 부족"), (r2["withheld"], r2["outlook"]))
    check("⑥ 보류 사유가 결측 항목을 지목한다", "assess", True,
          "매출 성장률" in r2["outlook_reason"] and "이익잉여금 비율" in r2["outlook_reason"])

    # dart_outlook 의 상수와 채점 항목 수가 맞는가. 항목이 6 → 4 로 줄면
    # MISSING_LIMIT 2 의 뜻이 달라진다 (1/3 결측 → 1/2 결측).
    check("⑥ 채점 항목 수와 보류 기준", "dart_outlook",
          (6, 2), (len(full), dart_outlook.MISSING_LIMIT))


def main() -> int:
    verify_extraction()
    verify_ratios()
    verify_items()
    verify_missing_rule()
    verify_boundaries()
    verify_handoff()

    width = max(len(name) for name, *_ in results)
    print()
    for name, where, expected, got, ok in results:
        print(f"[{'OK ' if ok else 'FAIL'}] {name:<{width}}  {where}")
        if not ok:
            print(f"        기대: {expected}")
            print(f"        실측: {got}")

    passed = sum(1 for *_, ok in results if ok)
    print(f"\n{passed} / {len(results)} 통과")
    return 0 if passed == len(results) else 1


if __name__ == "__main__":
    raise SystemExit(main())
