#!/usr/bin/env python3
"""R-07 확정적 표현 2건을 실제로 벗겼는지 검사한다 — F25(CN-048) · F23(CN-046).

`verify_rag_api.py`(F27) 와 같은 틀이고 `check()` 도 같은 함수다. 다른 점은
**네트워크가 필요 없다는 것**이다. 두 조치가 전부 판정 규칙과 화면 문자열이라
원격 DB 도 DART 키도 없이 결정적으로 검사된다.

    ① F25 자산군   — `investmentTree.js` 에 실명 금융상품이 남아 있지 않은지.
                     지운 이름 목록을 **옛 커밋에서 뽑지 않고 여기에 못박아** 둔다.
                     하나라도 되살아나면 FAIL 이다.
    ② F25 면책     — 약한 주의 한 줄이 사라지고 `disclaimer('strong')` 이 붙었는지.
    ③ F23 판정     — `services/dart_outlook.assess` 를 **직접 호출**해 매수/관망이
                     사라지고 결측 규칙이 도는지. 가짜 breakdown 을 꽂는다.
    ④ F23 면책     — 서버 문구와 `components/disclaimer.js` 사본이 같은지 (`==`).
    ⑤ main.py 연결 — 옛 투자의견 분기가 실제로 제거됐는지 소스에서 확인.

## 왜 ③ 만 import 하는가

`main.py` 는 라우터를 다 끌고 와 무거우므로 import 하지 않는다 —
`services/combination.py` 가 같은 이유로 AST 대조를 쓴다(CN-106). 이번에는 판정을
`services/dart_outlook.py` 로 꺼내 뒀기 때문에 **그 모듈만 import 하면 된다.**
`main.py` 쪽은 ⑤ 처럼 소스를 읽어 확인한다.

## 실행

    .venv/bin/python scripts/verify_r07_expressions.py
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "app" / "backend"))

from services import dart_outlook  # noqa: E402

results: list[tuple[str, str, str, str, bool]] = []


def brief(value) -> str:
    """긴 값을 잘라 보여 준다. 비교는 `==` 로 한다 — CN-098."""
    if isinstance(value, (dict, list)):
        text = json.dumps(value, ensure_ascii=False, sort_keys=True)
    else:
        text = str(value)
    return text if len(text) <= 88 else text[:85] + "…"


def check(name: str, where: str, expected, got, extra: str = "") -> bool:
    ok = expected == got
    results.append((name, where, brief(expected), f"{brief(got)}{extra}", ok))
    return ok


# ─────────────────────────────────────────────────────────────────────────────
# ① · ② F25 — 실명 금융상품과 면책
# ─────────────────────────────────────────────────────────────────────────────

# CN-048 이 지목한 실명 상품. **여기가 목록의 정본이다.**
# 옛 커밋에서 뽑으면 커밋이 바뀔 때 검사가 조용히 비어 버린다.
BANNED_PRODUCTS = [
    "KB국민은행 정기예금", "KODEX 단기채권PLUS", "예금보험 적금",
    "KODEX 200", "TIGER 국채3년", "KODEX 골드선물(H)",
    "TIGER 미국S&P500", "KODEX 국고채10년",
    "KODEX 나스닥100", "KODEX 미국나스닥100", "ACE 미국채10년",
    "TIGER 글로벌AI&로보틱스", "KODEX 반도체", "TIGER 인도니프티50",
]

# 운용사 접두사. 위 목록에 없는 새 상품이 들어와도 걸리게 한다.
BANNED_BRANDS = ["KODEX", "TIGER", "ACE", "KBSTAR", "ARIRANG", "HANARO", "SOL "]


def verify_f25() -> None:
    src = (ROOT / "app" / "frontend" / "js" / "views" / "investmentTree.js").read_text(encoding="utf-8")

    # 주석에도 옛 이름이 남아 있으므로(무엇을 왜 바꿨는지 적혀 있다) 주석을 걷어내고 본다.
    code = re.sub(r"/\*.*?\*/", "", src, flags=re.S)
    code = re.sub(r"^\s*//.*$", "", code, flags=re.M)

    survivors = [name for name in BANNED_PRODUCTS if name in code]
    check("① 실명 상품이 코드에 없다", "investmentTree.js", [], survivors,
          f"  (검사 {len(BANNED_PRODUCTS)}개)")

    brands = sorted({b.strip() for b in BANNED_BRANDS if b in code})
    check("① 운용사 이름이 코드에 없다", "investmentTree.js", [], brands)

    check("① products 배열이 assetClasses 로 바뀌었다", "investmentTree.js",
          (False, True), ("products:" in code, "assetClasses:" in code))

    # 자산군은 6전략 × 3개다. 손으로 센 숫자를 적지 않는다 — 파일에서 센다 (CN-121).
    classes = re.findall(r"assetClasses:\s*\[([^\]]*)\]", code)
    per_strategy = [len(re.findall(r"'[^']+'", body)) for body in classes]
    check("① 전략 6개가 각각 자산군 3개를 가진다", "investmentTree.js",
          [3, 3, 3, 3, 3, 3], per_strategy)

    check("② 약한 주의 한 줄이 사라졌다", "investmentTree.js",
          False, "실제 투자 권유가 아닙니다" in code)
    check("② strong 면책이 붙었다", "investmentTree.js",
          True, "disclaimer('strong')" in code)
    check("② 면책 컴포넌트를 import 한다", "investmentTree.js",
          True, "from '../components/disclaimer.js'" in code)

    # 수익률 제시 완화 — '연 N~M%' 꼴이 남아 있으면 안 된다.
    check("② 수익률 숫자 제시가 사라졌다", "investmentTree.js",
          [], re.findall(r"연 \d+~\d+%", code))


# ─────────────────────────────────────────────────────────────────────────────
# ③ F23 — 판정 규칙
# ─────────────────────────────────────────────────────────────────────────────

def _breakdown(pairs: list[tuple[str, float, float, float | None]]) -> dict:
    """`_score_financial_health` 가 주는 모양 그대로 만든다."""
    return {label: {"score": s, "max": m, "value": v} for label, s, m, v in pairs}


# 값이 다 있는 6항목. main.py 의 배점(20 · 20 · 15 · 15 · 15 · 15)과 같다.
FULL = [
    ("부채비율", 20.0, 20, -30.0),
    ("영업이익률", 20.0, 20, 25.0),
    ("자기자본이익률(ROE)", 15.0, 15, 22.0),
    ("유동비율", 12.0, 15, 180.0),
    ("매출 성장률", 7.0, 15, 3.0),
    ("이익잉여금 비율", 4.0, 15, 15.0),
]


def verify_f23_rule() -> None:
    good = dart_outlook.assess(78.0, "B+", _breakdown(FULL))
    check("③ 75점 이상이 '재무 양호'", "assess", "재무 양호", good["outlook"])
    check("③ 색이 신호등이 아니다", "assess", "ok", good["outlook_color"])
    check("③ 점수를 올린 항목을 말한다", "assess", True,
          "점수를 끌어올린 항목" in good["outlook_reason"])
    check("③ 끌어내린 항목도 말한다", "assess", True,
          "끌어내린 항목" in good["outlook_reason"])

    fair = dart_outlook.assess(60.0, "C", _breakdown(FULL))
    check("③ 55~75점이 '보통'", "assess", "보통", fair["outlook"])
    check("③ '보통' 은 중립색", "assess", "muted", fair["outlook_color"])

    weak = dart_outlook.assess(40.0, "F", _breakdown(FULL))
    check("③ 55점 미만이 '재무 취약'", "assess",
          "재무 취약 — 확인 필요 항목 있음", weak["outlook"])
    check("③ '취약' 은 경고색(빨강 아님)", "assess", "warn", weak["outlook_color"])

    # 옛 문구가 어떤 경로로도 나오지 않아야 한다.
    banned = ["매수", "관망", "Buy", "Sell", "Hold", "BUY", "SELL", "HOLD",
              "투자 매력", "분할 접근", "권고"]
    for case, label in ((good, "양호"), (fair, "보통"), (weak, "취약")):
        blob = f"{case['outlook']} {case['outlook_reason']}"
        hit = [w for w in banned if w in blob]
        check(f"③ '{label}' 응답에 투자의견 표현이 없다", "assess", [], hit)

    check("③ outlook_eng 필드가 없다", "assess", False, "outlook_eng" in good)

    # 결측 규칙 — 1개는 통과, 2개부터 보류.
    one_missing = FULL[:5] + [("이익잉여금 비율", 7.5, 15, None)]
    r1 = dart_outlook.assess(70.0, "B", _breakdown(one_missing))
    check("③ 결측 1개는 판정을 낸다", "assess", False, r1["withheld"])
    check("③ 결측 1개를 이름으로 알린다", "assess", ["이익잉여금 비율"], r1["missing"])

    two_missing = FULL[:4] + [("매출 성장률", 7.5, 15, None),
                              ("이익잉여금 비율", 7.5, 15, None)]
    r2 = dart_outlook.assess(70.0, "B", _breakdown(two_missing))
    check("③ 결측 2개는 판정을 보류한다", "assess", True, r2["withheld"])
    check("③ 보류 문구", "assess", "판정 보류 — 재무 자료 부족", r2["outlook"])
    check("③ 보류 사유가 결측을 지목한다", "assess", True,
          "매출 성장률 · 이익잉여금 비율" in r2["outlook_reason"])
    check("③ 보류에도 점수는 남는다", "assess", True, "70점" in r2["outlook_reason"])


# ─────────────────────────────────────────────────────────────────────────────
# ④ F23 — 면책 두 사본 대조
# ─────────────────────────────────────────────────────────────────────────────

def verify_f23_disclaimer() -> None:
    js = (ROOT / "app" / "frontend" / "js" / "components" / "disclaimer.js").read_text(encoding="utf-8")

    strong = re.search(r"strong:\s*\n?\s*'([^']+)'", js)
    context = re.search(r"F23:\s*'([^']+)'", js)
    check("④ 프런트에 F23 context 가 있다", "disclaimer.js", True, context is not None)
    if strong is None or context is None:
        return

    check("④ 면책 본문이 서버·프런트에서 같다", "DISCLAIMER",
          dart_outlook.DISCLAIMER, strong.group(1))
    check("④ F23 context 가 서버·프런트에서 같다", "DISCLAIMER_CONTEXT",
          dart_outlook.DISCLAIMER_CONTEXT, context.group(1))

    view = (ROOT / "app" / "frontend" / "js" / "views" / "dartFinancialAnalysis.js").read_text(encoding="utf-8")
    check("④ 화면이 strong 을 쓴다", "dartFinancialAnalysis.js", True,
          "disclaimer('strong'" in view)
    check("④ 화면이 면책 컴포넌트를 import 한다", "dartFinancialAnalysis.js", True,
          "from '../components/disclaimer.js'" in view)
    check("④ 영문 티커 배지가 사라졌다", "dartFinancialAnalysis.js", False,
          "outlook_eng" in view)
    # 구조 분해에서 `disclaimer` 를 꺼내면 import 한 함수를 가린다. 되살아나면 화면이 깨진다.
    check("④ 응답의 disclaimer 를 구조 분해하지 않는다", "dartFinancialAnalysis.js",
          [], re.findall(r"\{[^}]*\bdisclaimer\b[^}]*\}\s*=\s*analysis", view))


# ─────────────────────────────────────────────────────────────────────────────
# ⑤ main.py — 옛 분기가 남아 있지 않은가
# ─────────────────────────────────────────────────────────────────────────────

def verify_main_source() -> None:
    src = (ROOT / "app" / "backend" / "main.py").read_text(encoding="utf-8")
    code = re.sub(r"^\s*#.*$", "", src, flags=re.M)

    for token in ('"매수(Buy)"', '"중립(Hold)"', '"관망(Sell/Wait)"',
                  'outlook_eng', '"BUY"', '"SELL"', '"HOLD"'):
        check(f"⑤ main.py 에 {token} 이 없다", "main.py", False, token in code)

    check("⑤ main.py 가 dart_outlook 을 쓴다", "main.py", True,
          "dart_outlook.assess(" in code)
    check("⑤ breakdown 을 넘긴다", "main.py", True,
          "breakdown," in code and "_generate_dart_analysis(" in code)


# ─────────────────────────────────────────────────────────────────────────────
# ⑥ strong 화면 — 컴포넌트로 붙었는가
# ─────────────────────────────────────────────────────────────────────────────

# 화면-상세.md 3.3절 strong 행 중 **공통 컴포넌트로 붙인 것들.**
# F03(portfolioGuide) · F05(portfolioSimulation) 은 여기 없다 — 화면 전용 문장을
# 이미 들고 있고 3.3절이 ✅ 로 판정했다. 컴포넌트로 통일하는 것은 별건이다.
STRONG_VIEWS = {
    "F27": "ragChat.js",
    "F25": "investmentTree.js",
    "F23": "dartFinancialAnalysis.js",
    "F04": "portfolioCombination.js",
    "F19": "valuation.js",
    "F24": "financialKnowledge.js",
}

VIEWS_DIR = ROOT / "app" / "frontend" / "js" / "views"


def verify_strong_views() -> None:
    missing_call = []
    missing_import = []
    for fid, filename in STRONG_VIEWS.items():
        src = (VIEWS_DIR / filename).read_text(encoding="utf-8")
        if "disclaimer('strong'" not in src:
            missing_call.append(f"{fid}:{filename}")
        if "from '../components/disclaimer.js'" not in src:
            missing_import.append(f"{fid}:{filename}")

    check("⑥ strong 화면이 전부 컴포넌트를 부른다", "views/", [], missing_call,
          f"  (검사 {len(STRONG_VIEWS)}개)")
    check("⑥ strong 화면이 전부 컴포넌트를 import 한다", "views/", [], missing_import)

    # F03 · F05 는 자체 문장을 그대로 둔 화면이다. 사라지지 않았는지만 본다.
    guide = (VIEWS_DIR / "portfolioGuide.js").read_text(encoding="utf-8")
    sim = (VIEWS_DIR / "portfolioSimulation.js").read_text(encoding="utf-8")
    check("⑥ F03 자체 면책이 남아 있다", "portfolioGuide.js", True,
          "portfolio-guide-disclaimer" in guide)
    check("⑥ F05 자체 면책이 남아 있다", "portfolioSimulation.js", True,
          "simulation-disclaimer" in sim)

    # F19 — 리포트 기본값에 박혀 있던 투자 의견 (화면-상세.md 6절)
    val = (VIEWS_DIR / "valuation.js").read_text(encoding="utf-8")
    check("⑥ F19 기본 투자의견이 사라졌다", "valuation.js", False, "저평가로 판단" in val)
    check("⑥ F19 입력란은 남아 있다", "valuation.js", True, "rpt-opinion" in val)
    check("⑥ F19 기본값이 비었다", "valuation.js", True,
          'id="rpt-opinion" value=""' in val)


# ─────────────────────────────────────────────────────────────────────────────
# ⑦ default 화면 — 라우터 한 곳에서 붙는가
# ─────────────────────────────────────────────────────────────────────────────

# 화면-상세.md 3.3절 default 행을 라우트 이름으로 옮긴 것. F12(technical-chart)는
# 자체 강한 면책이 있어 빠지고, F02(server-resources)는 3.3절이 제외로 적었다.
EXPECTED_DEFAULT_VIEWS = [
    "home",
    "portfolio", "risk", "backtest", "pipeline",
    "volume-cloud", "world-markets",
    "macro-realtime", "macro-simulation", "kospi-excluded",
    "industry-analysis", "company-financial",
    "financial-statement",
    "dart-company-search", "dart-region-search",
    "group-network",
    "tax-accounting",
]


def verify_default_views() -> None:
    app_js = (ROOT / "app" / "frontend" / "js" / "app.js").read_text(encoding="utf-8")

    block = re.search(r"DISCLAIMER_DEFAULT_VIEWS\s*=\s*\[(.*?)\]", app_js, re.S)
    check("⑦ 라우터에 default 명단이 있다", "app.js", True, block is not None)
    if block is None:
        return

    listed = re.findall(r"'([^']+)'", block.group(1))
    # 순서가 아니라 구성을 본다 — 정렬해서 비교한다 (CN-098: == 로).
    check("⑦ default 명단이 3.3절과 같다", "app.js",
          sorted(EXPECTED_DEFAULT_VIEWS), sorted(listed),
          f"  ({len(listed)}개)")

    # 명단의 라우트가 실제로 존재하는가. 오타가 있으면 그 화면만 조용히 빠진다.
    routes_block = re.search(r"const routes\s*=\s*\{(.*?)\n\};", app_js, re.S)
    check("⑦ routes 표를 읽었다", "app.js", True, routes_block is not None)
    if routes_block is not None:
        known = set(re.findall(r"'([^']+)'\s*:", routes_block.group(1)))
        unknown = [v for v in listed if v not in known]
        check("⑦ 명단의 라우트가 전부 실재한다", "app.js", [], unknown)

    check("⑦ 라우터가 default 를 부른다", "app.js", True,
          "disclaimer('default'" in app_js)
    check("⑦ navigate 가 addDisclaimer 를 부른다", "app.js", True,
          "addDisclaimer(view);" in app_js)
    # F02 는 투자 정보가 아니라 제외다. 들어가 있으면 3.3절과 어긋난다.
    check("⑦ F02(서버 리소스)는 제외다", "app.js", False, "'server-resources'" in block.group(1))
    check("⑦ F12(기술적 분석)는 제외다", "app.js", False, "'technical-chart'" in block.group(1))


def main() -> int:
    verify_f25()
    verify_f23_rule()
    verify_f23_disclaimer()
    verify_main_source()
    verify_strong_views()
    verify_default_views()

    width = max(len(name) for name, *_ in results)
    print()
    for name, where, expected, got, ok in results:
        mark = "OK " if ok else "FAIL"
        print(f"[{mark}] {name:<{width}}  {where}")
        if not ok:
            print(f"        기대: {expected}")
            print(f"        실측: {got}")

    passed = sum(1 for *_, ok in results if ok)
    print(f"\n{passed} / {len(results)} 통과")
    return 0 if passed == len(results) else 1


if __name__ == "__main__":
    raise SystemExit(main())
