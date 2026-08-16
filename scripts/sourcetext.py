"""주석과 독스트링을 걷어낸 **실행되는 코드**만 돌려준다.

## 왜 이 파일이 따로 있는가

[테스트-계획 4.1절]은 금지 표현 grep 의 오탐 2건을 이미 지목하면서
*"자동 판정을 만들 때 오탐을 남겨 두면 아무도 그 검사를 믿지 않게 됩니다"* 라고
적었다. **같은 부류가 계층 규칙 grep 에도 있다.** 2026-08-16 실측:

    $ grep -rn "HTTPException\\|fastapi" app/backend/services/
    services/rag.py:6         아키텍처 2.1절대로 … `HTTPException` 을 던지지 않고
    services/simulation.py:5  `HTTPException` 을 던지지 않는다 — 도메인 예외를 …
    …                                                              (7건)

**7건 전부가 그 규칙을 설명하는 문장이다.** 아키텍처 5절이 정한 판정 명령이
*"서비스는 HTTP 를 모른다"* 를 검사하는데, 그렇게 적어 둔 주석에 걸린다.

허용 목록으로 덮으면 안 된다. 그 파일에서 **진짜 위반이 생겨도 못 잡게** 되고,
`services/` 는 위반이 생길 가능성이 가장 높은 자리다. 그래서 문장 자체를 걷어낸다.

E(금지 표현)와 F(계층 규칙) 두 검사가 같은 전처리를 필요로 하고, 전처리가 틀리면
**두 검사가 함께 조용히 통과한다.** 사본을 두지 않는 이유가 그것이다.

## 줄 번호를 보존한다

걷어낸 자리를 빈 줄로 바꾼다. 위반을 찾았을 때 `파일:줄` 로 짚을 수 있어야
고칠 수 있고, `ast.unparse` 는 그것을 잃는다.
"""

from __future__ import annotations

import ast
import io
import re
import tokenize
from pathlib import Path

#: `//` 를 주석 시작으로 인정하는 조건 — **줄머리이거나 앞에 공백이 있을 때만.**
#:
#: `https://` 만 예외로 두면 부족하다. 2026-08-16 실측으로 확인했다 —
#: `'https://example.com//KODEX'` 에서 두 번째 `//` 앞은 `m` 이라 예외에 걸리지 않고,
#: 그 줄의 뒷부분이 통째로 사라져 `KODEX` 를 놓쳤다.
#:
#: 사람이 쓰는 주석은 줄머리이거나 코드 뒤에 공백을 두고 붙는다. 그 형태만 인정하면
#: URL 은 경로 중간의 `//` 까지 전부 살아남는다. 대가는 `a=1;// 메모` 처럼 공백 없이
#: 붙인 주석을 코드로 읽는 것인데, 그쪽은 **오탐이라 눈에 띄고** 반대는 조용히 놓친다.
_JS_LINE_COMMENT = re.compile(r"(?:(?<=^)|(?<=\s))//.*$", re.M)


def python_code_only(source: str) -> str:
    """`.py` 에서 주석과 독스트링을 걷어낸다. 줄 수는 그대로다.

    독스트링은 *"값으로 쓰이지 않는 문자열 문장"* 전부를 뜻한다 — 모듈·함수·클래스
    머리뿐 아니라 중간에 홀로 놓인 삼중따옴표 블록도 포함한다. 파이썬에서 그것은
    실행되지만 아무 효과가 없어, 실무에서 **블록 주석으로 쓰인다.**

    구문 오류가 있으면 원문을 그대로 돌려준다. 검사가 파싱 실패를 조용히
    "위반 0건" 으로 바꾸면 안 되므로, 오히려 원문을 보게 해 걸리게 둔다.
    """
    lines = source.splitlines()

    try:
        tree = ast.parse(source)
    except SyntaxError:
        return source

    # ── ① 문자열 문장(독스트링·블록 주석) 자리를 표시한다 ────────────────────────
    blanked: set[int] = set()  # 1-기반 줄 번호
    for node in ast.walk(tree):
        if (
            isinstance(node, ast.Expr)
            and isinstance(node.value, ast.Constant)
            and isinstance(node.value.value, str)
        ):
            end = node.end_lineno or node.lineno
            blanked.update(range(node.lineno, end + 1))

    # ── ② 주석 토큰을 잘라낸다 ──────────────────────────────────────────────────
    # tokenize 는 주석의 시작 열을 정확히 준다. 문자열 안의 `#` 은 COMMENT 가 아니라
    # STRING 토큰이므로 잘못 자를 일이 없다 — 정규식으로 하면 그 구분이 없다.
    cuts: dict[int, int] = {}  # 줄 번호 → 자를 열
    try:
        for token in tokenize.generate_tokens(io.StringIO(source).readline):
            if token.type == tokenize.COMMENT:
                row, col = token.start
                cuts[row] = min(cuts.get(row, col), col)
    except (tokenize.TokenError, IndentationError):
        pass  # ①만으로도 독스트링은 걷힌다. 주석이 남는 쪽이 놓치는 쪽보다 안전하다.

    out: list[str] = []
    for index, line in enumerate(lines, start=1):
        if index in blanked:
            out.append("")  # 줄 자체는 남겨 뒤쪽 줄 번호를 지킨다
        elif index in cuts:
            out.append(line[: cuts[index]])
        else:
            out.append(line)
    return "\n".join(out)


def js_code_only(source: str) -> str:
    """`.js` 에서 주석을 걷어낸다. 줄 수는 그대로다.

    `verify_r07_expressions.py:81~82` 가 쓰던 방식에 두 가지를 더했다.
    ① 블록 주석을 통째로 지우지 않고 **줄바꿈만 남겨** 줄 번호를 지킨다.
    ② `//` 를 줄머리·공백 뒤일 때만 주석으로 본다 (`_JS_LINE_COMMENT`).

    문자열 리터럴 안의 `/*` 까지 가려내지는 않는다. 자바스크립트를 제대로 토큰화하는
    일이고 파이썬 표준 라이브러리에 그런 도구가 없다. **남은 한계는 이 방향뿐이다** —
    문자열에 `/*` 가 들어오면 그 뒤가 지워져 위반을 놓칠 수 있다.

    2026-08-16 실측: `app/` 아래 `.js` 52개에서 따옴표 안에 `/*`·`*/` 가 든 줄은
    1건이고(`views/adminRagIndex.js:4`), 그것도 블록 주석 **안**의 경로 표기라
    어차피 걷힌다. 진짜 코드에서는 0건이다.
    """

    def keep_newlines(match: re.Match[str]) -> str:
        return "\n" * match.group(0).count("\n")

    without_block = re.sub(r"/\*.*?\*/", keep_newlines, source, flags=re.S)
    return _JS_LINE_COMMENT.sub("", without_block)


def code_only(path: Path) -> str:
    """확장자를 보고 알맞은 전처리를 고른다. 모르는 확장자는 원문 그대로."""
    source = path.read_text(encoding="utf-8")
    if path.suffix == ".py":
        return python_code_only(source)
    if path.suffix in (".js", ".mjs"):
        return js_code_only(source)
    return source


def numbered(text: str) -> list[tuple[int, str]]:
    """`(줄 번호, 내용)` 목록. 빈 줄은 뺀다 — 걷어낸 자리라 볼 것이 없다."""
    return [(i, line) for i, line in enumerate(text.splitlines(), start=1) if line.strip()]
