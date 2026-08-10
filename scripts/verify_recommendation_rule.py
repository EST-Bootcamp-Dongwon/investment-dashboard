#!/usr/bin/env python3
"""F03 판정 규칙이 명세의 27조합 전수표와 일치하는지 대조한다.

명세를 하드코딩해 베끼지 않고 **문서에서 표를 읽어와** 비교한다. 그래야 코드와 문서
어느 쪽이 움직여도 여기서 걸린다. 한쪽을 옮겨 적으면 둘이 갈라져도 조용하다.

정본: docs/spec/20-기능명세/02-포트폴리오.md 1.4절 (CN-029 점수제).
분포 기대값도 같은 절의 표에서 온다 — stable 10 · balanced 10 · growth 7.

    $ python3 scripts/verify_recommendation_rule.py
"""

from __future__ import annotations

import itertools
import re
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.backend.services.recommendation import PROFILES, decide_profile  # noqa: E402

SPEC = ROOT / "docs" / "spec" / "20-기능명세" / "02-포트폴리오.md"

GOALS = ("growth", "balance", "protect")
HORIZONS = ("short", "medium", "long")
RISKS = ("low", "medium", "high")

# 표의 열 머리 `s/low` … `l/high` 순서. 행 머리는 투자 목적이다.
_COLUMN_ORDER = [(h, r) for h in HORIZONS for r in RISKS]


def parse_spec_table(text: str) -> dict[tuple[str, str, str], str]:
    """1.4절 "제안 규칙 전수표" 의 3행을 읽어 27칸을 만든다.

    같은 절에 분포 비교표(`| \\`growth\\` | 3 (11.1 %) | ...`)가 먼저 나오므로,
    전수표 제목 뒤로 범위를 좁힌 다음에 행을 찾는다.
    """
    marker = text.find("제안 규칙 전수표")
    if marker < 0:
        raise SystemExit(f"명세에서 '제안 규칙 전수표' 를 찾지 못했습니다: {SPEC}")
    text = text[marker:]

    expected: dict[tuple[str, str, str], str] = {}
    for goal in GOALS:
        # 행 머리는 `| \`growth\` |` 처럼 백틱으로 감싸여 있다.
        match = re.search(rf"^\|\s*`{goal}`\s*\|(.+)$", text, re.MULTILINE)
        if match is None:
            raise SystemExit(f"명세에서 `{goal}` 행을 찾지 못했습니다: {SPEC}")
        cells = [c.strip().strip("*").strip() for c in match.group(1).split("|")]
        cells = [c for c in cells if c]
        if len(cells) != 9:
            raise SystemExit(f"`{goal}` 행의 칸이 9개가 아닙니다 ({len(cells)}개).")
        for (horizon, risk), profile in zip(_COLUMN_ORDER, cells):
            expected[(goal, horizon, risk)] = profile
    return expected


def main() -> int:
    expected = parse_spec_table(SPEC.read_text(encoding="utf-8"))

    mismatches = []
    actual = Counter()
    for goal, horizon, risk in itertools.product(GOALS, HORIZONS, RISKS):
        got = decide_profile(goal, horizon, risk)
        actual[got] += 1
        want = expected[(goal, horizon, risk)]
        if got != want:
            mismatches.append((goal, horizon, risk, want, got))

    print(f"전수 조합 {len(expected)}칸 대조 — 정본 {SPEC.relative_to(ROOT)} 1.4절")
    for profile in ("stable", "balanced", "growth"):
        share = actual[profile] / len(expected) * 100
        print(f"  {profile:<9} {actual[profile]:>2}칸 ({share:.1f} %)")

    # goal 축이 실제로 결과를 바꾸는 칸 수. CN-029 가 현행 4/9 → 제안 8/9 로 개선한 지표다.
    goal_matters = sum(
        len({decide_profile(g, h, r) for g in GOALS}) > 1
        for h, r in _COLUMN_ORDER
    )
    print(f"  goal 이 결과를 바꾸는 칸: {goal_matters} / 9")

    # 배분표 합계도 함께 본다. 서비스가 요청마다 검증하지만, 상수만 고치고 배포하는
    # 실수를 여기서 미리 잡는다.
    for profile, config in PROFILES.items():
        total = sum(item["weight_pct"] for item in config["items"])
        if total != 100:
            mismatches.append((profile, "-", "-", "합계 100", f"합계 {total}"))

    if mismatches:
        print("\n불일치:")
        for goal, horizon, risk, want, got in mismatches:
            print(f"  {goal}/{horizon}/{risk}: 명세 {want} ≠ 코드 {got}")
        return 1

    print("\n전 칸 일치 · 세 프로필 배분 합계 모두 100.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
