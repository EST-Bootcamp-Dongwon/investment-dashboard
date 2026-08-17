#!/usr/bin/env python3
"""프런트 JS 가 ESM 으로 파싱되는지 검사한다.

## 왜 있는가 (2026-08-17)

**2026-08-14 커밋 `31d649f` 부터 사흘 동안 SPA 전체가 죽어 있었다.**
`js/views/dartFinancialAnalysis.js` 의 **템플릿 리터럴 안** HTML 주석에 백틱이 두 곳
들어갔고, 백틱이 템플릿을 그 자리에서 닫아 뒤가 코드로 파싱됐다. 브라우저는
`Unexpected identifier 'analysis'` 만 던지고 **스택도 남기지 않는다.** `app.js` 의
import 사슬이 끊겨 `window.navigate` 조차 정의되지 않았고, 화면이 하나도 뜨지 않았다.

**그런데 검사 15벌이 전부 통과했다.** 전부 파이썬·HTTP 쪽이라 프런트 번들을
아무도 파싱해 보지 않았기 때문이다. `verify_*.py` 는 API 를 부르지 화면을 열지 않는다.

그래서 이 검사를 뒀다. 규칙은 강제되지 않으면 지켜지지 않는다.

## 무엇을 하는가

`app/frontend/js/**/*.js` 를 전부 `node --input-type=module --check` 에 흘린다.
번들러가 아니다 — **파싱만** 한다. 산출물이 없으므로 절대 제약 7(빌드 단계 금지)에
걸리지 않는다.

`vendor/` 는 제외한다. 서드파티 배포본이고 우리가 고칠 대상이 아니다.

## node 가 없으면

**막다른 길로 만들지 않는다.** 무엇을 해야 하는지까지 출력하고 실패로 센다.
이 검사를 조용히 건너뛰면 이번 사고가 그대로 재발한다.
"""

from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
JS_DIR = ROOT / "app" / "frontend" / "js"
EXCLUDE_DIRS = {"vendor"}


def find_node() -> str | None:
  """`node` 실행 파일을 찾는다."""
  return shutil.which("node")


def js_files() -> list[Path]:
  """검사 대상 JS 를 모은다. `vendor/` 는 뺀다."""
  return sorted(
    path
    for path in JS_DIR.rglob("*.js")
    if not EXCLUDE_DIRS & set(path.relative_to(JS_DIR).parts)
  )


def check_one(node: str, path: Path) -> str | None:
  """한 파일을 ESM 으로 파싱한다. 통과하면 `None`, 아니면 오류 요약."""
  # `node --check <파일>` 은 확장자·package.json 으로 모듈 종류를 정하는데,
  # 이 레포에는 package.json 이 없어 CommonJS 로 읽힌다. 브라우저는 이 파일들을
  # `<script type="module">` 로 읽으므로 **ESM 으로 검사해야** 실제와 같다.
  result = subprocess.run(
    [node, "--input-type=module", "--check"],
    input=path.read_bytes(),
    capture_output=True,
  )
  if result.returncode == 0:
    return None
  text = result.stderr.decode("utf-8", errors="replace")
  for line in text.splitlines():
    if "Error" in line:
      return line.strip()
  return text.splitlines()[0].strip() if text.strip() else "알 수 없는 파싱 실패"


def main() -> int:
  node = find_node()
  if node is None:
    print("[FAIL] node 를 찾지 못했다 — 프런트 구문 검사를 돌릴 수 없다.")
    print()
    print("  이 검사는 번들러가 아니라 파서다. 산출물을 만들지 않는다.")
    print("  설치: https://nodejs.org  (또는 nvm install --lts)")
    print("  확인: node --version")
    print()
    print("  건너뛰지 마라 — 2026-08-14~17 에 SPA 가 사흘 동안 죽어 있었고")
    print("  파이썬 검사 15벌은 전부 통과했다.")
    return 1

  files = js_files()
  if not files:
    print(f"[FAIL] {JS_DIR} 아래에 검사할 JS 가 없다. 경로가 바뀌었는가?")
    return 1

  failures: list[tuple[Path, str]] = []
  for path in files:
    problem = check_one(node, path)
    if problem is not None:
      failures.append((path, problem))

  width = 72
  print("프런트 JS ESM 파싱 검사")
  print("─" * width)

  for path, problem in failures:
    print(f"[FAIL] {path.relative_to(ROOT)}")
    print(f"       {problem}")

  print("─" * width)
  passed = len(files) - len(failures)
  print(f"{passed} / {len(files)} 통과")

  if failures:
    print()
    print("가장 흔한 원인: **템플릿 리터럴 안에 백틱**.")
    print("  HTML 주석(<!-- -->)도 템플릿 안이면 코드다. 백틱이 템플릿을 닫는다.")
    print("  주석에서 코드를 인용할 때는 백틱 대신 따옴표를 써라.")
    return 1

  print("아키텍처: 프런트 번들이 브라우저에서 파싱된다 ✅")
  return 0


if __name__ == "__main__":
  sys.exit(main())
