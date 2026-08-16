#!/usr/bin/env python3
"""E · 금지 표현 검사 — 테스트-계획 3.4절 4-1 · 4-2 를 저장소 전역에 건다.

[테스트-계획 5.1절] 최소셋 7종 중 **E**. 5.3절은 `bash scripts/check_forbidden_terms.sh`
라고 적었지만 `grep` 몇 줄로는 성립하지 않는다 — 근거는 아래 "왜 셸이 아닌가".

## `verify_r07_expressions.py` 와 무엇이 다른가

세션 19가 만든 그것은 **아는 화면 6개**를 이름으로 찍어 검사한다. 지운 상품 14개가
`investmentTree.js` 에 되살아났는지, `main.py` 에서 옛 분기가 사라졌는지를 본다.
**새 파일에 새로 들어온 위반은 그 방식으로 잡히지 않는다.**

이 검사는 반대다. **`app/frontend/` · `app/backend/` 전부를 훑고** 패턴으로 잡는다.
파일 목록을 손으로 들고 있지 않으므로 어제 만든 화면도 오늘 걸린다.
두 검사는 겹치는 게 아니라 축이 다르다 — 하나는 *"그것이 돌아왔는가"*,
하나는 *"새것이 들어왔는가"* 다.

지운 상품 14개 목록(`BANNED_PRODUCTS`)은 **복사하지 않고 import 한다.**
`verify_r07_expressions.py:63` 이 *"여기가 목록의 정본이다"* 라고 적었고, 사본을
만들면 그 문장이 거짓이 된다.

## 왜 셸이 아닌가 — grep 만으로는 오탐이 남는다 (2026-08-16 실측)

테스트-계획 4.1절이 제시한 필터를 그대로 걸어도 2건이 남는다.

    $ grep -rnE "매수\\(Buy\\)|무조건 (수익|매수하)|반드시 매수" app/frontend/ app/backend/ \\
        | grep -vE "아닙니다|마세요|않습니다"
    app/backend/main.py:2556               # 여기 있던 "매수(Buy)/중립(Hold)/…" 은 …
    app/backend/services/dart_outlook.py:7     if score >= 75: outlook = "매수(Buy)" …

앞은 CN-046 이 무엇을 지웠는지 적어 둔 **주석**이고, 뒤는 옛 코드를 인용한
**독스트링**이다. 뒤엣것은 들여쓰기까지 코드와 똑같아 어떤 정규식으로도 갈라지지
않는다. 4-2 도 같다 — `services/rag.py:320` 의 `KODEX`·`TIGER` 는 R-07 **금칙어
목록 그 자체**이고, 그것은 주석이 아니라 진짜 코드다.

그래서 두 층으로 나눈다.
  ① 주석·독스트링을 걷어낸다 → `scripts/sourcetext.py` (파이썬 `ast`+`tokenize` 가 필요)
  ② 남은 진짜 코드 중 **검사 도구 자신**만 이름으로 면제한다 → `EXEMPTIONS`

면제는 파일 단위가 아니라 **변수 이름 단위**다. `services/rag.py` 를 통째로 빼면
그 파일에 진짜 위반이 생겨도 못 잡는데, F27 응답을 만드는 곳이라 위반 가능성이
가장 높은 자리 중 하나다.

## 실행

    .venv/bin/python scripts/check_forbidden_terms.py

종료 코드 — 0 통과 · 1 위반 · 2 검사 자체가 성립하지 않음(면제가 죽었다).
네트워크도 자격증명도 필요 없다.
"""

from __future__ import annotations

import ast
import re
import sys
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
sys.path.insert(0, str(ROOT / "app" / "backend"))

from sourcetext import code_only, numbered  # noqa: E402
from verify_r07_expressions import BANNED_BRANDS, BANNED_PRODUCTS  # noqa: E402

#: 훑는 범위. 테스트-계획 3.4절 4-1·4-2 가 적은 그대로다.
SCAN_ROOTS = ("app/frontend", "app/backend")
SCAN_SUFFIXES = (".py", ".js", ".mjs")
SKIP_PARTS = ("__pycache__", "node_modules")


@dataclass(frozen=True)
class Exemption:
    """이름으로 지목한 면제. 파일 단위 면제를 쓰지 않는 이유는 위 독스트링에 있다."""

    path: str
    name: str
    why: str


EXEMPTIONS = (
    Exemption(
        path="app/backend/services/rag.py",
        name="FOLLOWUP_BANNED_TERMS",
        why="R-07 금칙어 목록 그 자체다. 검사 대상이 아니라 검사 도구다 (CN-128).",
    ),
)


# ── 4-1 확정적 표현 ───────────────────────────────────────────────────────────
#
# 테스트-계획 3.4절 4.1 의 패턴 그대로다. 넓히지 않았다 — `services/rag.py` 의
# `FOLLOWUP_BANNED_TERMS` 는 '오른다'·'반드시'·'항상' 까지 막지만, 그것은 **버튼으로
# 만들 후보**를 고르는 기준이라 훨씬 좁아도 된다. 같은 잣대를 교육 본문 전체에 대면
# "주가는 반드시 오르지 않습니다" 같은 **옳은 문장**이 전부 걸린다.
ASSERTIVE = re.compile(r"매수\(Buy\)|무조건 (수익|매수하)|반드시 매수")

#: 부정어와 함께 쓰인 경고문은 R-06 4단계가 요구하는 태도 그 자체다 (4.1절 오탐 2건).
#: 주석·독스트링을 걷어낸 **뒤에도** 이 필터가 필요하다 — 그 둘은 진짜 코드 안의
#: 사용자 문구다 (`financialStatement.js:96` · `valuation.js:685`).
ASSERTIVE_OK = re.compile(r"아닙니다|마세요|않습니다|않으면|아니라")

#: CN-046 이 F23 에서 걷어낸 투자의견 배지. 저장소 어디에도 되살아나면 안 된다.
#: `verify_r07_expressions.py` ⑤ 는 `main.py` 만 보므로 여기서 범위를 넓힌다.
OPINION_BADGE = re.compile(r"매수\(Buy\)|중립\(Hold\)|관망\(Sell/Wait\)|outlook_eng")

# ── 4-2 실명 금융상품 ─────────────────────────────────────────────────────────
#
# 운용사 접두는 `verify_r07_expressions.BANNED_BRANDS` 를 그대로 쓴다. `ACE ` 처럼
# 뒤에 공백이 붙은 항목이 있어 정규식으로 만들 때 escape 가 필요하다.
BRAND = re.compile("|".join(re.escape(b) for b in BANNED_BRANDS))
PRODUCT = re.compile("|".join(re.escape(p) for p in BANNED_PRODUCTS))

results: list[tuple[str, str, str, str, bool]] = []


def check(name: str, where: str, expected, got, extra: str = "") -> bool:
    """`verify_r07_expressions.py:53` 과 같은 함수다. 비교는 `==` 로 한다 (CN-098)."""
    ok = expected == got
    results.append((name, where, brief(expected), f"{brief(got)}{extra}", ok))
    return ok


def brief(value) -> str:
    text = str(value)
    return text if len(text) <= 100 else text[:97] + "…"


def targets() -> list[Path]:
    """훑을 파일. 목록을 손으로 들지 않는다 — 새 파일이 저절로 들어온다."""
    found: list[Path] = []
    for root in SCAN_ROOTS:
        for path in sorted((ROOT / root).rglob("*")):
            if path.suffix not in SCAN_SUFFIXES or not path.is_file():
                continue
            if any(part in SKIP_PARTS for part in path.parts):
                continue
            found.append(path)
    return found


def _exempt_ranges(path: Path) -> tuple[set[int], list[Exemption]]:
    """이 파일에 걸린 면제의 줄 범위와, 실제로 찾아낸 면제 목록."""
    mine = [e for e in EXEMPTIONS if (ROOT / e.path) == path]
    if not mine:
        return set(), []

    try:
        tree = ast.parse(path.read_text(encoding="utf-8"))
    except SyntaxError:
        return set(), []

    lines: set[int] = set()
    hit: list[Exemption] = []
    for node in ast.walk(tree):
        if not isinstance(node, (ast.Assign, ast.AnnAssign)):
            continue
        names = (
            [t.id for t in node.targets if isinstance(t, ast.Name)]
            if isinstance(node, ast.Assign)
            else ([node.target.id] if isinstance(node.target, ast.Name) else [])
        )
        for exemption in mine:
            if exemption.name in names:
                lines.update(range(node.lineno, (node.end_lineno or node.lineno) + 1))
                hit.append(exemption)
    return lines, hit


def scan() -> tuple[list[str], list[str], list[str], list[str], set[Exemption], int]:
    """네 갈래 위반과, 실제로 쓰인 면제, 훑은 파일 수를 돌려준다."""
    assertive: list[str] = []
    badge: list[str] = []
    brand: list[str] = []
    product: list[str] = []
    used: set[Exemption] = set()

    files = targets()
    for path in files:
        skip, hit = _exempt_ranges(path)
        used.update(hit)
        rel = path.relative_to(ROOT).as_posix()

        for line_no, line in numbered(code_only(path)):
            if line_no in skip:
                continue
            body = line.strip()
            if ASSERTIVE.search(body) and not ASSERTIVE_OK.search(body):
                assertive.append(f"{rel}:{line_no}")
            if OPINION_BADGE.search(body):
                badge.append(f"{rel}:{line_no}")
            if BRAND.search(body):
                brand.append(f"{rel}:{line_no}")
            if PRODUCT.search(body):
                product.append(f"{rel}:{line_no}")

    return assertive, badge, brand, product, used, len(files)


def main() -> int:
    assertive, badge, brand, product, used, file_count = scan()

    check("① 4-1 확정적 표현이 없다", f"{file_count}개 파일", [], assertive)
    check("② 투자의견 배지가 없다 (CN-046)", f"{file_count}개 파일", [], badge)
    check("③ 4-2 운용사 이름이 없다", f"{file_count}개 파일", [], brand,
          f"  (접두 {len(BANNED_BRANDS)}개)")
    check("④ 4-2 실명 상품이 없다", f"{file_count}개 파일", [], product,
          f"  (상품 {len(BANNED_PRODUCTS)}개)")

    # 검사가 훑을 것이 있었는가. 경로가 바뀌면 0건 통과가 되어 조용히 무력해진다.
    check("⑤ 훑을 파일이 있었다", " · ".join(SCAN_ROOTS), True, file_count > 0,
          f"  ({file_count}개)")

    # 죽은 면제 — 면제 대상이 사라졌는데 면제만 남으면 검사가 약해진 채 방치된다.
    dead = [f"{e.path}:{e.name}" for e in EXEMPTIONS if e not in used]
    alive = check("⑥ 면제가 전부 살아 있다", "EXEMPTIONS", [], dead,
                  f"  ({len(EXEMPTIONS)}건)")

    width = max(len(name) for name, *_ in results)
    print()
    for name, where, expected, got, ok in results:
        print(f"[{'OK ' if ok else 'FAIL'}] {name:<{width}}  {where}")
        if not ok:
            print(f"        기대: {expected}")
            print(f"        실측: {got}")

    if EXEMPTIONS:
        print("\n면제 (검사 도구 자신):")
        for e in EXEMPTIONS:
            print(f"  · {e.path}:{e.name} — {e.why}")

    passed = sum(1 for *_, ok in results if ok)
    print(f"\n{passed} / {len(results)} 통과")

    if not alive:
        return 2  # 검사 자체가 성립하지 않는다. 위반과 구분한다.
    return 0 if passed == len(results) else 1


if __name__ == "__main__":
    raise SystemExit(main())
