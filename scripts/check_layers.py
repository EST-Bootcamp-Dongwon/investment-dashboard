#!/usr/bin/env python3
"""F · 계층 규칙 검사 — 아키텍처 5절의 판정 명령 6개를 실행 가능한 판정으로 옮긴다.

[테스트-계획 5.1절] 최소셋 7종 중 **F**. 아키텍처 5절은 이렇게 적었다 —
*"6개 명령이 전부 통과하면 이 축은 ✅ 입니다. 하나라도 실패하면 ❌ 입니다.
'대체로 나눠져 있다' 같은 판정을 하지 않기 위해 이렇게 적습니다."*

이 파일이 그 문장을 명령으로 만든다. R-08 8축 중 "계층 분리" 축의 판정이
사람 손을 떠난다.

## 처음엔 통과하지 않는 검사였다 — 지금은 통과한다

만들던 날(2026-08-16 오전) 실측은 6개 중 **3개 미달**이었다 — `main.py` 2,693줄 ·
라우터 차트 20건 · 중복 정의 3벌. 미달인 채로 두는 것이 그때의 목적이었다.
대조표가 이 축을 🔶 로 적어 둔 근거가 지금까지 문장이었고, 이제 숫자였기 때문이다.

같은 날 [CN-065](docs/spec/00-index/변경이력.md#cn-065) 분해 순서 ⑤~⑦ 이 셋을 모두
치웠다. 그래서 이 검사의 성격이 바뀌었다 — 목표를 가리키던 검사에서 **지켜 낸 것을
지키는 검사**로.

## 6개에서 7개가 됐다 (2026-08-16 오후)

아키텍처 5절 표는 명령을 **6개**로 적었고 여섯 모두 `app/backend/` 를 본다.
**7번만 `app/frontend/js/` 를 본다** — *"`api.js` 외 파일이 `fetch` 를 직접 부르지
않음"*. 축을 넓힌 것이 아니라, 같은 축의 프론트 쪽 절반이 그때까지 비어 있었다.

근거는 이 저장소 문서 두 곳이다.

* `docs/spec/40-API/공통-응답과-에러.md` §9 조치 9번 — *"`api.js` 를 단일 창구로"* 를
  **축: 계층 분리** 로 이미 분류해 두었다.
* `quant-contract/docs/contracts/api-contract.md` §8.1 — API 계약의 **선행 조건**으로
  이 검사를 지목했다. 받는 쪽이 8곳이면 계약이 강제되지 않기 때문이다.

7번은 만들자마자 통과했다. 같은 날 오후에 회수를 먼저 끝냈기 때문이다
(7파일 10건 → 0건). **그래서 이 규칙은 처음부터 "지켜 낸 것을 지키는" 쪽이다.**

종료 코드는 셋 그대로다 (`verify_rag_api.py` 가 세운 관례 — 1은 검사 실패,
2는 자격증명 없음).

    0  7개 전부 통과 → 축이 ✅ 로 올라간다
    1  **기준선보다 나빠졌다** — 회귀다. 고쳐야 한다
    2  기준선 그대로이고 목표에 미달 — 아직 분해가 안 끝났다

1과 2를 가르지 않으면 이 검사는 **언제나 실패하는 검사**가 되고, 언제나 실패하는
검사는 아무도 보지 않는다(테스트-계획 4.1절이 오탐에 대해 한 말과 같다).
지금은 7개가 다 통과하므로 실질적으로 0 과 1 만 나온다.

## 기준선을 왜 파일에 적는가

`BASELINE` 은 **실측이고 목표가 아니다.** 분해가 진행되면 내려 적어야 하고, 내려
적지 않으면 다시 나빠져도 통과한다. 실제로 그럴 뻔했다 — 분해 직후 `main.py` 가
185줄이 됐는데 기준선이 2,693 인 채였다면, 나중에 1,000 줄로 되돌아가도 검사는
"기준선보다 좋아졌다(개선)" 로 읽는다. **회귀가 개선으로 보이는 것**이다.

그래서 통과한 날 곧바로 실측으로 내려 적었다(아래 `RULES`). 검사는 반대 방향도
알려 준다 — 실측이 기준선보다 좋으면 "기준선이 느슨해졌다" 고 보고한다.

## 주석을 걷어내고 본다

아키텍처 5절의 4번 명령을 그대로 돌리면 **7건이 잡히는데 7건 전부가 오탐이다.**

    $ grep -rn "HTTPException\\|fastapi" app/backend/services/     # 2026-08-16
    services/rag.py:6         … `HTTPException` 을 던지지 않고
    services/simulation.py:5  `HTTPException` 을 던지지 않는다 — 도메인 예외를 …
                                                                        (7건)

**규칙을 지켰다고 적어 둔 문장이 그 규칙의 검사에 걸린다.** `scripts/sourcetext.py`
가 주석과 독스트링을 걷어낸 뒤에 센다. 걷어낸 뒤 실측은 0건이다.

## 실행

    .venv/bin/python scripts/check_layers.py

네트워크도 자격증명도 필요 없다.
"""

from __future__ import annotations

import re
import sys
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

from sourcetext import code_only, numbered  # noqa: E402

BACKEND = ROOT / "app" / "backend"
FRONTEND_JS = ROOT / "app" / "frontend" / "js"
API_MODULE = FRONTEND_JS / "api.js"


@dataclass(frozen=True)
class Rule:
    """아키텍처 5절 표의 한 행."""

    number: int
    condition: str          # 합격 조건 (문서 문구 그대로)
    command: str            # 문서가 적은 판정 명령
    target: int             # 통과 기준값
    compare: str            # "<" 또는 "=="
    baseline: int           # 2026-08-16 실측. 이보다 나빠지면 회귀다


# 아키텍처 5절 표 그대로다. `baseline` 만 이 파일이 더한 것이고, **CN-065 분해를
# 마친 뒤(2026-08-16 오후)의 실측값**이다. 셋(1·3·6)은 그날 오전만 해도 각각
# 2693 · 20 · 3 이었다 — 분해가 그것을 185 · 0 · 1 로 만들었고, 여기에 내려 적음으로써
# **되돌아가는 것이 회귀로 잡힌다.**
RULES = (
    Rule(1, "main.py 200줄 미만", "wc -l app/backend/main.py", 200, "<", 185),
    Rule(2, "라우터가 외부 API 를 직접 부르지 않음",
         'grep -rn "yf\\.|krx\\.|urlopen" app/backend/routers/', 0, "==", 0),
    Rule(3, "라우터가 차트를 직접 그리지 않음",
         'grep -rn "savefig|b64encode" app/backend/routers/', 0, "==", 0),
    Rule(4, "서비스가 HTTP 를 모름",
         'grep -rn "HTTPException|fastapi" app/backend/services/', 0, "==", 0),
    Rule(5, "역방향 의존 없음",
         'grep -rn "from ..routers|from ..services" app/backend/clients/', 0, "==", 0),
    Rule(6, "중복 정의 없음",
         'grep -rn "^def configure_matplotlib_korean_font" app/backend/', 1, "==", 1),
    # ── 7번은 아키텍처 5절 표에 없던 규칙이다 ─────────────────────────────
    #
    # 앞의 여섯은 전부 `app/backend/` 를 본다. 이것만 `app/frontend/js/` 를 본다.
    # 넣은 근거는 두 곳이다.
    #
    # ① `docs/spec/40-API/공통-응답과-에러.md` §9 조치 9번이 *"`api.js` 를 단일
    #    창구로"* 를 **축: 계층 분리 · 크기: 소** 로 이미 분류해 두었다. 축이 같다.
    # ② `quant-contract/docs/contracts/api-contract.md` §8.1 이 계약의 선행 조건으로
    #    *"강제 장치는 `check_layers.py` 에 「api.js 외 파일의 `fetch(` 금지」 검사를
    #    추가한다"* 를 지목했다.
    #
    # **왜 계약이 이걸 요구하는가.** 2026-08-16 오전 실측으로 `api.js` 밖에서
    # `fetch()` 를 부르는 곳이 **7개 파일 10건**이었다. 그 상태에서는 API 계약을
    # 아무리 잘 써도 받는 쪽이 8곳이라 강제되지 않는다. 같은 날 회수해 0건이 됐고,
    # 이 규칙이 **되돌아가는 것을 회귀로 잡는다.**
    #
    # 기준선을 0 으로 적은 이유: 규칙 2~5 와 같다. 회수가 이미 끝났으므로 기준선이
    # 곧 목표다. 하나라도 늘면 `value > baseline` 이라 종료 코드 1(회귀)이 난다.
    Rule(7, "api.js 외 프론트 파일이 fetch 를 직접 부르지 않음",
         'grep -rn "fetch(" app/frontend/js/ --include=*.js  # api.js 제외', 0, "==", 0),
)


def _count(
    directory: Path,
    pattern: re.Pattern[str],
    glob: str = "*.py",
    skip: frozenset[Path] = frozenset(),
) -> list[str]:
    """주석·독스트링을 걷어낸 코드에서 패턴이 걸리는 `파일:줄` 목록.

    `code_only` 가 확장자를 보고 `.py`·`.js` 전처리를 고르므로(`sourcetext.py:123`)
    프론트 규칙에도 그대로 쓴다. **주석을 걷는 것이 규칙 7번에서 특히 중요하다** —
    `api.js` 의 머리말이 "밖에서 `fetch()` 를 부르는 곳이 10건이었다" 를 설명하고,
    걷지 않으면 그 설명이 자기 규칙에 걸린다(규칙 4번에서 이미 겪은 일이다).

    `skip` 은 규칙 7번의 `api.js` 처럼 **검사에서 면제되는 파일**이다.
    """
    found: list[str] = []
    for path in sorted(directory.rglob(glob)):
        if "__pycache__" in path.parts or path in skip:
            continue
        for line_no, line in numbered(code_only(path)):
            if pattern.search(line):
                found.append(f"{path.relative_to(ROOT).as_posix()}:{line_no}")
    return found


def measure() -> dict[int, tuple[int, list[str]]]:
    """6개 규칙의 실측값과 근거 목록."""
    main_lines = len((BACKEND / "main.py").read_text(encoding="utf-8").splitlines())

    return {
        1: (main_lines, [f"app/backend/main.py 가 {main_lines}줄"]),
        2: _sized(_count(BACKEND / "routers", re.compile(r"\byf\.|\bkrx\.|urlopen"))),
        3: _sized(_count(BACKEND / "routers", re.compile(r"savefig|b64encode"))),
        4: _sized(_count(BACKEND / "services", re.compile(r"HTTPException|fastapi"))),
        5: _sized(_count(BACKEND / "clients", re.compile(r"from \.\.routers|from \.\.services"))),
        6: _sized(_count(BACKEND, re.compile(r"^def configure_matplotlib_korean_font"))),
        # 회수의 **결과물**은 위반이 아니다. `apiFetch(`·`fetchAssetText(` 는 애초에
        # `fetch(` 와 글자가 다르고, 낱말 경계(`\b`)가 `myfetch(` 처럼 `fetch` 로 끝나는
        # 다른 이름까지 막는다. 반대로 `window.fetch(` 는 `.` 이 경계라 제대로 잡힌다.
        7: _sized(_count(FRONTEND_JS, re.compile(r"\bfetch\("), "*.js", frozenset({API_MODULE}))),
    }


def _sized(found: list[str]) -> tuple[int, list[str]]:
    return len(found), found


def passes(rule: Rule, value: int) -> bool:
    return value < rule.target if rule.compare == "<" else value == rule.target


def main() -> int:
    measured = measure()

    rows: list[tuple[Rule, int, list[str], bool, str]] = []
    for rule in RULES:
        value, evidence = measured[rule.number]
        ok = passes(rule, value)
        if ok:
            verdict = "통과"
        elif value > rule.baseline:
            verdict = "회귀"          # 기준선보다 나빠졌다
        elif value < rule.baseline:
            verdict = "개선"          # 목표엔 못 미치나 기준선보다 좋아졌다
        else:
            verdict = "미달"          # 기준선 그대로
        rows.append((rule, value, evidence, ok, verdict))

    mark = {"통과": "OK  ", "회귀": "REGR", "미달": "미달 ", "개선": "개선 "}
    width = max(len(r.condition) for r in RULES)
    print()
    for rule, value, evidence, ok, verdict in rows:
        target = f"< {rule.target}" if rule.compare == "<" else f"= {rule.target}"
        print(f"[{mark[verdict]}] {rule.number}. {rule.condition:<{width}} "
              f"실측 {value:>4}  기준 {target:>5}  기준선 {rule.baseline}")
        if not ok:
            print(f"        명령: {rule.command}")
            for item in evidence[:6]:
                print(f"        · {item}")
            if len(evidence) > 6:
                print(f"        · … 외 {len(evidence) - 6}건")

    ok_count = sum(1 for *_, ok, _ in rows if ok)
    regressed = [r.number for r, _, _, ok, v in rows if not ok and v == "회귀"]
    improved = [r.number for r, _, _, ok, v in rows if not ok and v == "개선"]

    print(f"\n{ok_count} / {len(RULES)} 통과")

    if improved:
        print(f"기준선이 느슨해졌습니다 — 규칙 {improved} 의 baseline 을 실측으로 내려 적으세요.")

    if ok_count == len(RULES):
        print("아키텍처 5절: 계층 분리 축 ✅")
        return 0
    if regressed:
        print(f"아키텍처 5절: 계층 분리 축 ❌ — **규칙 {regressed} 이 기준선보다 나빠졌습니다.**")
        return 1
    print("아키텍처 5절: 계층 분리 축 ❌ (기준선 그대로 · 회귀 없음)")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
