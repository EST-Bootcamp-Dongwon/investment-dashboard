#!/usr/bin/env python3
"""docs/spec 안의 상대 링크와 앵커를 전수 검사한다.

명세가 서로를 촘촘히 참조하는 구조라, 제목을 한 글자 고치면 다른 문서의 앵커가
조용히 깨진다. 링크는 눌러 보기 전까지 깨진 것이 드러나지 않으므로 기계로 센다.

**앵커 슬러그 규칙** (GitHub 방식). 이 셋을 틀리면 대량 오탐이 난다.

1. 소문자로 바꾼다. 한글은 그대로다.
2. 영숫자·한글·공백·하이픈·**밑줄**만 남긴다. `·` `(` `)` `,` 같은 기호는 **지운다**.
   밑줄은 지우지 않는다 — `invest_goal` 은 앵커에도 `invest_goal` 로 남는다.
3. **공백 1개가 하이픈 1개다.** 여러 칸을 하나로 줄이지 않는다.

**코드블록은 빼고 읽는다.** 펜스 안의 `# 주석` 이 제목으로, SQL 문자열이 링크로
잡히면 없는 앵커를 찾다가 실패한다.

    $ python3 scripts/check_spec_links.py
"""

from __future__ import annotations

import re
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SPEC_DIR = ROOT / "docs" / "spec"

_FENCE = re.compile(r"^\s*(```|~~~)")
_HEADING = re.compile(r"^(#{1,6})\s+(.*?)\s*#*\s*$")
_EXPLICIT_ANCHOR = re.compile(r"""<a\s+id=["']([^"']+)["']""")
# 이미지(![...])는 제외하고 링크만 본다.
_LINK = re.compile(r"(?<!!)\[(?:[^\[\]]|\[[^\[\]]*\])*\]\(([^()\s]*(?:\([^()]*\)[^()\s]*)*)\)")


def strip_code_blocks(text: str) -> str:
    """펜스 코드블록을 빈 줄로 바꾼다. 줄 번호는 유지한다."""
    out, in_fence, fence = [], False, ""
    for line in text.splitlines():
        marker = _FENCE.match(line)
        if marker and not in_fence:
            in_fence, fence = True, marker.group(1)
            out.append("")
            continue
        if in_fence:
            out.append("")
            if line.strip().startswith(fence):
                in_fence = False
            continue
        out.append(line)
    return "\n".join(out)


def slugify(heading: str) -> str:
    text = re.sub(r"`([^`]*)`", r"\1", heading)                 # 인라인 코드
    text = re.sub(r"!?\[([^\]]*)\]\([^)]*\)", r"\1", text)      # 링크는 표시 텍스트만
    text = re.sub(r"\*\*|__|\*|~~", "", text)                   # 강조 표기
    text = text.strip().lower()
    text = re.sub(r"[^\w\s-]", "", text, flags=re.UNICODE)      # \w 가 한글·밑줄을 남긴다
    return text.replace(" ", "-")


def anchors_of(text: str) -> set[str]:
    """제목에서 만들어지는 슬러그 + 문서가 직접 박은 <a id>."""
    found: set[str] = set()
    seen: dict[str, int] = defaultdict(int)
    for line in text.splitlines():
        heading = _HEADING.match(line)
        if heading:
            slug = slugify(heading.group(2))
            if not slug:
                continue
            # 같은 제목이 여러 번이면 GitHub 이 -1, -2 를 붙인다.
            found.add(slug if seen[slug] == 0 else f"{slug}-{seen[slug]}")
            seen[slug] += 1
        found.update(_EXPLICIT_ANCHOR.findall(line))
    return found


def main() -> int:
    if not SPEC_DIR.is_dir():
        print(f"명세 폴더가 없습니다: {SPEC_DIR}")
        return 1

    files = sorted(SPEC_DIR.rglob("*.md"))
    bodies = {f: strip_code_blocks(f.read_text(encoding="utf-8")) for f in files}
    anchors = {f: anchors_of(body) for f, body in bodies.items()}

    total = 0
    problems: list[str] = []

    for path, body in bodies.items():
        for lineno, line in enumerate(body.splitlines(), 1):
            for target in _LINK.findall(line):
                if target.startswith(("http://", "https://", "mailto:", "#!")):
                    continue
                total += 1
                where = f"{path.relative_to(ROOT)}:{lineno}"

                file_part, _, anchor = target.partition("#")
                if not file_part:  # 같은 문서 안의 앵커
                    dest = path
                else:
                    dest = (path.parent / file_part).resolve()
                    if not dest.exists():
                        problems.append(f"{where}  파일 없음 → {target}")
                        continue
                    if dest.suffix != ".md":
                        continue  # 이미지·SQL 등은 존재 확인까지만

                if not anchor:
                    continue
                if dest not in anchors:
                    problems.append(f"{where}  명세 밖 문서의 앵커 → {target}")
                    continue
                if anchor not in anchors[dest]:
                    problems.append(f"{where}  앵커 없음 → {target}")

    print(f"문서 {len(files)}개 · 링크 {total}개 검사")
    if problems:
        print(f"\n깨진 링크 {len(problems)}개:")
        for item in problems:
            print(f"  {item}")
        return 1
    print("전부 통과.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
