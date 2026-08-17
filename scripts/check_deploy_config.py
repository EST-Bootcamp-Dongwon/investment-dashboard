#!/usr/bin/env python3
"""배포 설정 4종이 서로 어긋나지 않는지 본다 — [배포-전략 7절] 점검표의 자동화.

배포-전략 7절은 배포 전 점검 8개를 **표로** 적어 두었다. 표는 사람이 읽고 사람이
빠뜨린다. 그중 **파일만 보면 판정할 수 있는 것**을 여기서 명령으로 만든다.
나머지(번들 크기·Supabase 정지 여부)는 실제 배포 로그와 대시보드를 봐야 해서 남긴다.

## 왜 필요한가 — 사본이 둘이다

`Content-Security-Policy` 문자열이 **두 곳**에 있다.

    app/backend/security.py    → `/api/*` 응답 (파이썬 함수가 낸다)
    vercel.json                → 정적 페이지 응답 (CDN 이 낸다)

한 벌로 만들 수 없다. 정적 파일은 파이썬을 지나지 않고, `vercel.json` 은 JSON 이라
값을 계산할 수 없기 때문이다. **그래서 대조를 자동화한다** — `services/rag.py` 의
면책 문구가 `components/disclaimer.js` 사본과 갈라지지 않게 하는 것과 같은 이유다
(`verify_rag_api.py` ②).

CSP 가 정적 페이지에서만 강하고 API 에서 약하면(또는 그 반대면) 두 응답이 서로
다른 정책을 말한다. **그 상태는 "CSP 를 켰다" 가 아니다.**

## 실행

    .venv/bin/python scripts/check_deploy_config.py

네트워크도 자격증명도 필요 없다. 종료 코드는 0(전부 통과) · 1(어긋남)이다.
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "app" / "backend"))
sys.path.insert(0, str(ROOT / "scripts"))

import security  # noqa: E402
from sourcetext import code_only, numbered  # noqa: E402

results: list[tuple[str, str, bool, str]] = []


def check(name: str, ok: bool, detail: str = "") -> None:
    results.append((name, "", ok, detail))


# ── vercel.json ──────────────────────────────────────────────────────────────
vercel = json.loads((ROOT / "vercel.json").read_text(encoding="utf-8"))
header_groups = {group["source"]: group["headers"] for group in vercel.get("headers", [])}
catch_all = {h["key"]: h["value"] for h in header_groups.get("/(.*)", [])}

check(
    "① CSP 문자열이 security.py 와 같다",
    catch_all.get("Content-Security-Policy-Report-Only") == security.csp_policy([]),
    f"vercel.json 쪽 {len(catch_all.get('Content-Security-Policy-Report-Only', ''))}자",
)
check(
    "① 보안 헤더 4종이 정적 응답에도 붙는다",
    all(catch_all.get(k) == v for k, v in security.SECURITY_HEADERS.items()),
    f"{sorted(security.SECURITY_HEADERS)}",
)
# 보안과-시크릿 2.2절이 명시적으로 뺐다 — Vercel 이 자체로 붙이고, 중복 선언하면
# 로컬 HTTP 개발이 깨진다.
check(
    "① HSTS 를 선언하지 않는다",
    not any(k.lower() == "strict-transport-security" for k in catch_all),
)
check(
    "① 정적 루트가 app/frontend 다",
    vercel.get("outputDirectory") == "app/frontend",
    vercel.get("outputDirectory", "(없음)"),
)
check(
    "① GENERATED_DIR 이 /tmp 아래다",
    vercel.get("env", {}).get("GENERATED_DIR", "").startswith("/tmp"),
    vercel.get("env", {}).get("GENERATED_DIR", "(없음)"),
)

include_files = vercel["functions"]["api/index.py"]["includeFiles"]
for needed in ("app/backend/**", "lean-hyundai/hd_core.py", "docs/*.md"):
    check(f"① includeFiles 에 {needed}", needed in include_files)

# ── requirements ─────────────────────────────────────────────────────────────
deploy_req = (ROOT / "requirements.txt").read_text(encoding="utf-8")
dev_req = (ROOT / "requirements-dev.txt").read_text(encoding="utf-8")


def _pins(text: str) -> dict[str, str]:
    """주석을 걷어낸 실제 요구사항 줄만 `{이름: 줄}` 로."""
    out: dict[str, str] = {}
    for line in text.splitlines():
        line = line.split("#")[0].strip()
        if not line or line.startswith("-"):
            continue
        out[re.split(r"[=<>!\[]", line)[0].strip().lower()] = line
    return out


deploy_pins = _pins(deploy_req)
dev_pins = _pins(dev_req)

# 배포-전략 7절 점검표 2번. `pykrx` 는 이 표에 없었는데, 그것이 matplotlib 을 하드
# 의존한다는 사실이 2026-08-17 실측으로 드러나 목록에 들어왔다(requirements.txt 머리말).
for banned in ("torch", "diffusers", "opencv-python-headless", "matplotlib", "pykrx"):
    check(f"② 배포용에 {banned} 없음", banned not in deploy_pins)

check(
    "② 배포용 uvicorn 이 [standard] 가 아니다",
    "[standard]" not in deploy_pins.get("uvicorn", ""),
    deploy_pins.get("uvicorn", "(없음)"),
)
check(
    "② 직접 의존이 전부 버전 핀",
    all("==" in line for line in deploy_pins.values()),
    ", ".join(n for n, line in deploy_pins.items() if "==" not in line) or "전부 핀",
)
check("② dev 가 배포용을 -r 로 포함", "-r requirements.txt" in dev_req)
for needed in ("matplotlib", "pykrx"):
    check(f"② dev 에는 {needed} 있음", needed in dev_pins)

# ── .vercelignore 가 필요한 것을 빼지 않는가 ─────────────────────────────────
ignore_lines = [
    line.split("#")[0].strip()
    for line in (ROOT / ".vercelignore").read_text(encoding="utf-8").splitlines()
]
ignore_lines = [line for line in ignore_lines if line]

# `.vercelignore` 가 이긴다 — 여기서 뺀 파일은 업로드되지 않아 includeFiles 가
# 집어넣을 것이 없다. 배포-전략 4.3절과 보안과-시크릿 1.3절이 서로 당기는 자리다.
for fatal in ("lean-hyundai/", "lean-hyundai", "app/frontend/", "app/frontend", "app/backend/"):
    check(f"③ .vercelignore 가 {fatal} 를 통째로 빼지 않는다", fatal not in ignore_lines)
check("③ docs/*.md 를 되살린다", "!docs/*.md" in ignore_lines)
for secret in (".env", "*.env", "*.key", "*.pem"):
    check(f"③ 시크릿 {secret} 제외", secret in ignore_lines)

# ── 콜드 스타트 — import 시점 mkdir 이 없는가 (7절 점검표 3번) ───────────────
backend_files = [
    p for p in (ROOT / "app" / "backend").rglob("*.py") if "__pycache__" not in p.parts
]
import_time_mkdir: list[str] = []
for path in backend_files:
    # 주석·독스트링을 걷어낸 뒤에 센다. 걷지 않으면 **"여기 있던 mkdir 을 없앴다"** 고
    # 적어 둔 주석(`routers/ml.py:19`)이 자기 규칙에 걸린다 — `check_layers.py` 가
    # 규칙 4번에서 겪은 것과 같은 오탐이다.
    for number, line in numbered(code_only(path)):
        # 들여쓰기가 없는 `.mkdir(` = 모듈 최상단 = import 시점에 돈다.
        if re.match(r"^\S.*\.mkdir\(", line):
            import_time_mkdir.append(f"{path.relative_to(ROOT).as_posix()}:{number}")
check(
    "④ 모듈 import 시점에 mkdir 하는 곳이 없다",
    not import_time_mkdir,
    ", ".join(import_time_mkdir) or "0건",
)
check("④ api/index.py 가 있다", (ROOT / "api" / "index.py").is_file())

# ── 출력 ─────────────────────────────────────────────────────────────────────
print()
print(f"{'결과':<5}{'항목':<46}{'비고'}")
print("─" * 92)
passed = 0
for name, _, ok, detail in results:
    print(f"{'[OK ]' if ok else '[FAIL]':<5} {name:<45} {detail}")
    passed += ok
print("─" * 92)
print(f"\n{passed} / {len(results)} 통과")
sys.exit(0 if passed == len(results) else 1)
