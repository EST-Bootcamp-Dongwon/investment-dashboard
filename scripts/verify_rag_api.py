#!/usr/bin/env python3
"""F27 문서 검색 API 와 관리자 색인 경로를 **원격 Supabase 에 대고** 왕복 검증한다.

`verify_combination_api.py`(F04 · 71건) · `verify_backtest_api.py`(F28 · 79건)와 같은
틀이다. 다른 점은 **무엇을 대조하느냐** 이고, 이번에는 대조 대상이 넷이다.

    ① 원문 대조   — 옛 색인 스크립트(`scripts/upload_docs_to_qdrant.sh`) 안에 있는
                    `chunk_text` · `hash_embed` 를 **소스에서 뽑아 실제로 실행**해
                    `services/rag.py` 의 것과 같은 값을 내는지 본다.
    ② 면책 대조   — `services/rag.py` 의 문구와 `components/disclaimer.js` 의 문구가
                    같은 문자열인지 본다. 두 사본이 갈라지면 화면과 API 가 다른 말을 한다.
    ③ 왕복        — 색인 → 검색 → 응답까지 원격을 거쳐 돌아온 값이 넣은 값과 같은지.
    ④ 권한        — 관리자 경로가 401 · 403 · 200 을 실제로 갈라 내는지.
                    **검증 전용 계정을 만들어 진짜 토큰으로 두드린다.**

## ① 이 F04 의 AST 우회보다 강하다

[CN-106] 은 `main.py` 가 `torch` 를 끌고 와 import 할 수 없어 **상수 21개만** AST 로
비교했다. 여기서는 원본이 bash 힙독 안의 python 이라 import 자체가 불가능한데,
대신 **그 힙독을 텍스트로 떼어 내 함수 정의만 컴파일**할 수 있다. 상수가 아니라
**함수의 출력 전체**를 비교하게 되고, 입력은 실제 말뭉치 `docs/*.md` 8개다.

## ④ 가 만드는 부수효과와 정리

Auth 사용자 2명(관리자 1 · 비관리자 1)을 만들고 끝에서 지운다. `app_admin` 행과
검증용 `doc_chunk` 행도 마찬가지다. **`docs/*.md` 178행은 건드리지 않는다** —
검증 전용 `source_doc` 접두사(`__verify__`)를 써서 정리 대상을 정확히 특정한다.

## 실행

    .venv/bin/python scripts/verify_rag_api.py

저장소 루트의 `.env` 에서 `SUPABASE_URL`·`SUPABASE_SERVICE_ROLE_KEY` 를 읽는다.
외부 AI 는 **더 이상 존재하지 않는다.** 2026-08-16 에 `clients/rag_llm.py` 와
`provider` 필드를 걷어냈다(절대 제약 1 — LLM 유료 API 비용 0원). 그래서 이 검사에서
경계를 치환하던 절(`rag_llm.complete` 를 가짜로 바꾸던 자리)도 함께 없앴고, 대신
**되살아나지 않는지를 보는 검사 3건**을 넣었다 — 아래 ③ 절 끝.
"""

from __future__ import annotations

import ast
import json
import os
import re
import sys
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "app" / "backend"))


def load_dotenv(path: Path) -> None:
    """`.env` 를 읽어 환경변수에 넣는다. 검증 스크립트 4벌과 같은 함수다."""
    if not path.exists():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


load_dotenv(ROOT / ".env")

from fastapi import FastAPI  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from clients import doc_chunk_repo, supabase_client  # noqa: E402
from routers.admin import router as admin_router  # noqa: E402
from routers.rag import router as rag_router  # noqa: E402
from services import rag as service  # noqa: E402

app = FastAPI()
app.include_router(rag_router)
app.include_router(admin_router)
client = TestClient(app, raise_server_exceptions=False)

# 검증 전용 접두사. 정리할 때 이 접두사로만 지운다 — 실제 말뭉치 178행을 건드리지 않는다.
VERIFY_DOC = "__verify__rag.md"
VERIFY_ORPHAN = "__verify__orphan.md"


def _corpus_paths() -> list[Path]:
    """말뭉치 파일 목록. 판정은 `services/rag.is_corpus_doc` 이 한다.

    **이 스크립트가 자기 규칙을 갖지 않는 것이 요점이다.** 검증하는 쪽이 판정
    규칙을 따로 들고 있으면, 색인 쪽 규칙이 바뀌어도 검증은 옛 규칙으로 통과한다 —
    검증이 아니라 자기 자신과의 대조가 된다.
    """
    return sorted(
        path for path in (ROOT / "docs").glob("*.md") if service.is_corpus_doc(path.name)
    )

# 연결이 즉시 거부되는 주소. 타임아웃 10초를 기다리지 않고 503 경로를 밟는다.
DEAD_URL = "http://127.0.0.1:1"
BAD_TOKEN = "not-a-real-access-token"

results: list[tuple[str, str, str, str, bool]] = []
created_users: list[str] = []


def brief(value) -> str:
    """표에 넣을 짧은 표현. dict·list 는 키 순서 차이로 같은 값이 달라 보이므로
    정규화해서 보여 준다. 비교는 `==`(순서 무관)로 한다 — CN-098."""
    if isinstance(value, (dict, list)):
        text = json.dumps(value, ensure_ascii=False, sort_keys=True)
    else:
        text = str(value)
    return text if len(text) <= 88 else text[:85] + "…"


def check(name: str, endpoint: str, expected, got, extra: str = "") -> bool:
    ok = expected == got
    results.append((name, endpoint, brief(expected), f"{brief(got)}{extra}", ok))
    return ok


# ─────────────────────────────────────────────────────────────────────────────
# Auth 관리 — 검증 전용 계정
# ─────────────────────────────────────────────────────────────────────────────
def _auth_request(method: str, path: str, body=None, token: str | None = None) -> dict:
    key = os.environ["SUPABASE_SERVICE_ROLE_KEY"]
    url = f"{os.environ['SUPABASE_URL'].rstrip('/')}{path}"
    data = json.dumps(body).encode("utf-8") if body is not None else None
    headers = {
        "apikey": key,
        "Authorization": f"Bearer {token or key}",
        "Content-Type": "application/json",
        "Accept": "application/json",
    }
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=20) as res:
            raw = res.read()
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", "replace")[:300]
        raise RuntimeError(f"Auth {method} {path} → {exc.code}: {detail}") from exc
    return json.loads(raw) if raw else {}


def create_user(email: str, password: str) -> str:
    """검증 전용 계정을 만들고 `user_id` 를 돌려준다. 메일 확인은 건너뛴다."""
    created = _auth_request(
        "POST",
        "/auth/v1/admin/users",
        {"email": email, "password": password, "email_confirm": True},
    )
    user_id = created["id"]
    created_users.append(user_id)
    return user_id


def sign_in(email: str, password: str) -> str:
    """비밀번호로 로그인해 **진짜 액세스 토큰**을 받는다."""
    signed = _auth_request(
        "POST", "/auth/v1/token?grant_type=password", {"email": email, "password": password}
    )
    return signed["access_token"]


# ─────────────────────────────────────────────────────────────────────────────
# ① 원문 대조 — 옛 색인 스크립트의 함수를 실제로 실행해 비교
# ─────────────────────────────────────────────────────────────────────────────
def load_legacy_functions() -> dict:
    """`upload_docs_to_qdrant.sh` 힙독에서 `chunk_text`·`hash_embed` 만 떼어 컴파일한다.

    스크립트 전체를 돌리면 Qdrant 에 접속하려 든다. 힙독을 텍스트로 잘라 `ast` 로 파싱한
    뒤 **함수 정의 두 개만** 새 모듈에 넣어 컴파일하면 부작용 없이 원본 코드를 부를 수 있다.
    """
    source = (ROOT / "scripts" / "upload_docs_to_qdrant.sh").read_text(encoding="utf-8")
    match = re.search(r"<<'PY'\n(.*?)\nPY\n", source, re.DOTALL)
    if not match:
        raise RuntimeError("upload_docs_to_qdrant.sh 에서 python 힙독을 찾지 못했습니다.")

    tree = ast.parse(match.group(1))
    wanted = {"chunk_text", "hash_embed"}
    picked = [node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name in wanted]
    if {node.name for node in picked} != wanted:
        raise RuntimeError(f"원본 함수를 찾지 못했습니다: {wanted - {n.name for n in picked}}")

    namespace: dict = {}
    exec(compile(ast.Module(body=picked, type_ignores=[]), "<legacy>", "exec"), namespace)
    # 힙독 상단의 import(hashlib·math·re)를 함수가 전역에서 찾는다.
    import hashlib as _hashlib
    import math as _math
    import re as _re

    namespace.update({"hashlib": _hashlib, "math": _math, "re": _re})
    namespace["TOKEN_PATTERN"] = _re.compile(r"[0-9A-Za-z가-힣_]+")
    return namespace


def verify_port() -> None:
    legacy = load_legacy_functions()
    docs = _corpus_paths()

    total_chunks = 0
    chunk_mismatch = 0
    embed_mismatch = 0
    for path in docs:
        text = path.read_text(encoding="utf-8")
        old_chunks = legacy["chunk_text"](text, 1200, 200)
        new_chunks = service.chunk_text(text)
        if old_chunks != new_chunks:
            chunk_mismatch += 1
        total_chunks += len(new_chunks)
        for chunk in new_chunks:
            if legacy["hash_embed"](chunk) != service.hash_embed(chunk):
                embed_mismatch += 1

    check("① 청킹 — 문서별 조각이 원본과 동일", "chunk_text", 0, chunk_mismatch,
          f"  (문서 {len(docs)}개 · 총 {total_chunks}청크)")
    check("① 임베딩 — 청크별 384차원 벡터가 원본과 동일", "hash_embed", 0, embed_mismatch,
          f"  ({total_chunks}청크 전수)")
    check("① 말뭉치 총 청크 수", "docs/*.md", 178, total_chunks)

    # 질의 쪽 옛 사본(`routers/rag.py:52~59`)도 같은 값이었는지 — 이것이 사본 두 벌이
    # 갈라져 있었는가에 대한 답이다. 옛 라우터는 이미 새 코드로 덮였으므로, 그때
    # 위험이었던 것은 **차원을 저장소가 정했다는 점**이다. 지금은 고정이다.
    check("① 임베딩 차원이 고정", "services.rag.EMBED_DIM", 384, len(service.hash_embed("차원")))
    check("① 빈 문자열은 영벡터", "hash_embed('')", [0.0] * 384, service.hash_embed(""))


# ─────────────────────────────────────────────────────────────────────────────
# ② 면책 대조 — 서버 상수 ↔ 프런트 컴포넌트
# ─────────────────────────────────────────────────────────────────────────────
def verify_disclaimer() -> None:
    js = (ROOT / "app" / "frontend" / "js" / "components" / "disclaimer.js").read_text(encoding="utf-8")

    strong = re.search(r"strong:\s*\n?\s*'([^']*)'", js)
    context = re.search(r"F27:\s*'([^']*)'", js)
    check("② 프런트에 strong 문구가 있다", "disclaimer.js", True, strong is not None)
    check("② 프런트에 F27 context 가 있다", "disclaimer.js", True, context is not None)
    if not (strong and context):
        return

    check("② 면책 본문이 서버·프런트에서 같다", "DISCLAIMER", service.DISCLAIMER, strong.group(1))
    check("② F27 context 가 서버·프런트에서 같다", "DISCLAIMER_CONTEXT",
          service.DISCLAIMER_CONTEXT, context.group(1))

    # R-07 이 요구하는 낱말이 실제로 들어 있는지. 문구가 나중에 바뀌어도 요구의
    # 핵심("교육"·"투자 조언이 아님"·"본인 책임")이 빠지면 여기서 걸린다.
    for word in ("교육", "투자 조언", "책임"):
        check(f"② 면책에 '{word}' 가 있다", "DISCLAIMER", True, word in service.DISCLAIMER)

    # 화면에도 실제로 붙었는가 — 테스트-계획 4-4 가 세던 그 grep 이다.
    rag_chat = (ROOT / "app" / "frontend" / "js" / "views" / "ragChat.js").read_text(encoding="utf-8")
    check("② ragChat.js 가 면책 컴포넌트를 부른다", "ragChat.js", True,
          "disclaimer('strong'" in rag_chat)

    # 후속 질문이 화면까지 갔는지 (R-04 · CN-128). 서버가 필드를 실어도 화면이 읽지
    # 않으면 요구는 충족되지 않는다.
    check("② ragChat.js 가 data.followups 를 읽는다", "ragChat.js", True,
          "data.followups" in rag_chat)
    check("② ragChat.js 가 followups_head 를 읽는다", "ragChat.js", True,
          "data.followups_head" in rag_chat)
    # 제안 문자열은 색인 원문에서 왔다. 버튼 텍스트와 data-query 양쪽을 이스케이프하는지.
    followup_button = re.search(r"rag-followup\"[^`]*?</button>", rag_chat)
    check("② 후속 질문 버튼이 escapeHtml 을 쓴다", "ragChat.js", 2,
          len(re.findall(r"escapeHtml\(question\)", followup_button.group(0) if followup_button else "")))


# ─────────────────────────────────────────────────────────────────────────────
# ③ 왕복 — status · ask · DB 백스톱
# ─────────────────────────────────────────────────────────────────────────────
def postgrest(path: str, params: dict[str, str]) -> list[dict]:
    """PostgREST 를 **라우터를 거치지 않고** 직접 두드리는 백스톱.

    라우터가 준 값이 정말 DB 에 있는 값인지 확인하려면, 그 값을 만들어 준 코드와
    다른 경로로 읽어야 한다. F04·F28 이 쓴 방식과 같다.
    """
    key = os.environ["SUPABASE_SERVICE_ROLE_KEY"]
    query = urllib.parse.urlencode(params, quote_via=urllib.parse.quote)
    url = f"{os.environ['SUPABASE_URL'].rstrip('/')}/rest/v1/{path}?{query}"
    req = urllib.request.Request(
        url, headers={"apikey": key, "Authorization": f"Bearer {key}", "Accept": "application/json"}
    )
    with urllib.request.urlopen(req, timeout=20) as res:
        return json.loads(res.read())


def verify_runtime() -> None:
    # ── status ───────────────────────────────────────────────────────────────
    response = client.get("/api/rag/status")
    body = response.json()
    check("③ status 200", "GET /api/rag/status", 200, response.status_code)
    check("③ 저장소 이름이 pgvector", "status.vector_store.store", "supabase-pgvector",
          body["vector_store"]["store"])
    check("③ 저장소에 붙는다", "status.vector_store.available", True, body["vector_store"]["available"])
    check("③ 색인돼 있다", "status.vector_store.indexed", True, body["vector_store"]["indexed"])
    check("③ 응답에 옛 qdrant 키가 없다", "status", False, "qdrant" in body)
    check("③ status 에도 면책이 실린다", "status.disclaimer", service.DISCLAIMER, body["disclaimer"])

    db_total = sum(int(row["chunk_count"]) for row in doc_chunk_repo.stats())
    check("③ 청크 총수가 DB 와 일치", "status.total_chunks", db_total,
          body["vector_store"]["total_chunks"])
    check("③ 말뭉치 문서 8개가 색인돼 있다", "status.document_count", 8,
          len([d for d in body["vector_store"]["documents"] if not str(d["source_doc"]).startswith("__verify__")]))

    # ── ask ──────────────────────────────────────────────────────────────────
    response = client.post("/api/rag/ask", json={"query": "분산투자", "top_k": 3})
    body = response.json()
    check("③ ask 200", "POST /api/rag/ask", 200, response.status_code)
    # `provider` 가 2026-08-16 에 빠졌다 — 외부 AI 폐기(절대 제약 1). 응답에 되돌아오면
    # 이 집합 비교가 곧바로 걸린다. **키 집합을 통째로 비교하는 이유가 이것이다** —
    # 개별 키를 하나씩 보면 새로 *생긴* 키를 아무도 못 잡는다.
    check("③ 응답 키 집합", "ask", {
        "query", "answer", "embed_method", "sources", "source_count",
        "disclaimer", "disclaimer_context", "followups", "followups_head",
    }, set(body))
    check("③ embed_method 가 하드코딩이 아니다", "ask.embed_method", service.EMBED_METHOD,
          body["embed_method"])
    check("③ source_count 가 sources 길이와 같다", "ask.source_count", len(body["sources"]),
          body["source_count"])
    check("③ top_k 를 지킨다", "ask.sources", True, len(body["sources"]) <= 3)
    check("③ 답변에 면책이 동봉된다", "ask.disclaimer", service.DISCLAIMER, body["disclaimer"])
    check("③ 답변에 context 가 동봉된다", "ask.disclaimer_context", service.DISCLAIMER_CONTEXT,
          body["disclaimer_context"])

    # ── 후속 질문 (R-04 · CN-128) — 원격을 거쳐 돌아온 값으로 확인한다 ────────
    check("③ followups 가 전부 물음표로 끝난다", "ask.followups", [],
          [q for q in body["followups"] if not str(q).endswith("?")])
    check("③ followups 가 상한 이하", "ask.followups", True,
          len(body["followups"]) <= service.FOLLOWUP_MAX)
    check("③ followups 에 금칙어가 없다", "ask.followups", [],
          [q for q in body["followups"] if service.followup_banned_hit(str(q))])
    check("③ followups_head 가 서비스 상수와 같다", "ask.followups_head", service.FOLLOWUP_HEAD,
          body["followups_head"])

    # ── 배선을 실제로 고정한다 ────────────────────────────────────────────────
    #
    # 위 검사들은 `followups` 가 **빈 배열이어도 전부 통과한다** — "물음표로 끝난다"
    # 도 "금칙어가 없다" 도 빈 목록에서 참이다. 실제로 질의 `분산투자` 는 관문을 통과하는
    # 후보가 없어 `[]` 다. 그래서 제안이 실제로 나오는 질의로 한 번 더 두드려
    # **비어 있지 않은 경로**를 고정한다. 이것이 없으면 `build_followups` 를 통째로
    # 지워도 ③ 이 초록으로 뜬다.
    질의 = "배당은 언제 받나요?"
    rich = client.post("/api/rag/ask", json={"query": 질의, "top_k": 5}).json()
    check("③ 제안이 나오는 질의는 실제로 나온다", "ask.followups", True,
          len(rich["followups"]) >= 1, extra=f" ({len(rich['followups'])}개)")
    check("③ 그 제안도 전부 물음표로 끝난다", "ask.followups", [],
          [q for q in rich["followups"] if not str(q).endswith("?")])

    # `match_count = max(top_k, FOLLOWUP_POOL)` 이 정말 도는가. top_k=1 이면 응답의
    # `sources` 는 1개인데, 계산이 `sources` 가 아니라 `pool` 을 보므로 제안은 그대로
    # 나와야 한다. `pool` → `sources` 로 되돌리는 회귀가 여기서 잡힌다.
    narrow = client.post("/api/rag/ask", json={"query": 질의, "top_k": 1}).json()
    check("③ top_k=1 이어도 sources 는 1개", "ask.source_count", 1, narrow["source_count"])
    check("③ top_k=1 이어도 제안은 풀에서 나온다", "ask.followups", rich["followups"],
          narrow["followups"])

    # ── DB 백스톱 — 라우터가 준 원문이 진짜 그 행인가 ─────────────────────────
    if body["sources"]:
        top = body["sources"][0]
        rows = postgrest("doc_chunk", {
            "select": "content,source_doc,chunk_index",
            "source_doc": f"eq.{top['source_doc']}",
            "chunk_index": f"eq.{top['chunk_index']}",
            "limit": "1",
        })
        check("③ 백스톱 — 응답 원문이 DB 행과 같다", "doc_chunk", top["text"],
              rows[0]["content"] if rows else None)
        check("③ 점수가 0~1 범위", "ask.sources[0].score", True, 0.0 <= top["score"] <= 1.0)

    # ── score_threshold 가 실제로 걸린다 ─────────────────────────────────────
    high = client.post("/api/rag/ask", json={"query": "분산투자", "top_k": 5, "score_threshold": 0.99})
    check("③ 임계값 0.99 면 0건", "ask.score_threshold", 0, high.json()["source_count"])
    check("③ 0건이어도 200", "POST /api/rag/ask", 200, high.status_code)
    check("③ 0건이면 안내 문장", "ask.answer", service.ANSWER_EMPTY, high.json()["answer"])
    # 근거가 0건이면 제안도 0개다. 근거 없이 질문을 붙이면 ANSWER_EMPTY 와 모순된다.
    check("③ 근거 0건이면 followups 도 0개", "ask.followups", [], high.json()["followups"])

    # ── 외부 AI 가 되살아나지 않는지 ─────────────────────────────────────────
    #
    # 여기에 "외부 AI 경로" 검사 8건이 있었다. `clients/rag_llm.complete` 를 가짜로
    # 바꿔 `provider='openai_compatible'` 을 네트워크 없이 밟는 방식이었다.
    # **그 경로를 2026-08-16 에 폐기했다** — compose 기본값이 `https://api.openai.com/v1`
    # 이라 키만 꽂으면 과금이 시작되는 배선이었고, 절대 제약 1 이 그것을 금지한다.
    #
    # 지운 자리를 비워 두지 않는다. 폐기는 **한 번 지우는 일이 아니라 계속 지워져
    # 있어야 하는 상태**이고, 지켜지는지 보는 것이 이 파일의 일이다.
    # (05 검증본 P0-7: *"파일만 지우면 안 된다. 다음 사람이 키를 꽂는 순간 되살아난다."*)
    check("③ 외부 AI 모듈이 없다", "clients/rag_llm.py", False,
          (ROOT / "app" / "backend" / "clients" / "rag_llm.py").exists())
    check("③ 응답에 external_ai 가 없다", "GET /api/rag/status", False,
          "external_ai" in client.get("/api/rag/status").json())
    # `provider` 를 보내도 **422 가 아니라 무시**된다. pydantic 이 모르는 필드를
    # 조용히 버리기 때문이다. 옛 화면이 남아 있어도 RAG 답변이 그대로 나간다.
    revived = client.post("/api/rag/ask", json={"query": "분산투자", "top_k": 2,
                                                "provider": "openai_compatible"})
    check("③ 옛 provider 를 보내도 200", "POST /api/rag/ask", 200, revived.status_code)
    check("③ 옛 provider 를 보내도 RAG 답변", "ask.answer",
          client.post("/api/rag/ask", json={"query": "분산투자", "top_k": 2}).json()["answer"],
          revived.json()["answer"])

    # ── 입력 검증 ────────────────────────────────────────────────────────────
    check("③ 빈 질문은 422", "POST /api/rag/ask", 422, client.post("/api/rag/ask", json={"query": ""}).status_code)
    check("③ top_k 상한 초과는 422", "POST /api/rag/ask", 422,
          client.post("/api/rag/ask", json={"query": "x", "top_k": 21}).status_code)
    check("③ 삭제된 /search 는 404", "POST /api/rag/search", 404,
          client.post("/api/rag/search", json={"query": "x"}).status_code)


def with_dead_supabase(fn):
    """`SUPABASE_URL` 만 죽은 주소로 바꿔 503 경로를 밟는다.

    `supabase_client` 가 환경변수를 **호출 시점에** 읽기 때문에 성립한다
    (`_base_url()` — 모듈 수준 상수였다면 못 했다).
    """
    original = os.environ["SUPABASE_URL"]
    os.environ["SUPABASE_URL"] = DEAD_URL
    try:
        return fn()
    finally:
        os.environ["SUPABASE_URL"] = original


def verify_store_failure() -> None:
    def probe():
        ask = client.post("/api/rag/ask", json={"query": "분산투자"})
        status = client.get("/api/rag/status")
        return ask, status

    ask, status = with_dead_supabase(probe)
    check("③ 저장소가 죽으면 ask 는 503", "POST /api/rag/ask", 503, ask.status_code)
    check("③ 저장소가 죽어도 status 는 200", "GET /api/rag/status", 200, status.status_code)
    check("③ status 가 available:false 로 알린다", "status.vector_store.available", False,
          status.json()["vector_store"]["available"])
    check("③ 저장소가 죽어도 면책은 나온다", "status.disclaimer", service.DISCLAIMER,
          status.json()["disclaimer"])


# ─────────────────────────────────────────────────────────────────────────────
# ④ 권한 — 진짜 토큰으로 401 · 403 · 200 을 가른다
# ─────────────────────────────────────────────────────────────────────────────
def verify_admin() -> None:
    admin_email = "verify-admin@example.invalid"
    plain_email = "verify-plain@example.invalid"
    password = "verify-Password-2026!"

    admin_id = create_user(admin_email, password)
    plain_id = create_user(plain_email, password)
    admin_token = sign_in(admin_email, password)
    plain_token = sign_in(plain_email, password)
    supabase_client.insert("app_admin", {"user_id": admin_id, "note": "검증 전용"}, ignore_duplicates=True)

    def head(token: str | None) -> dict:
        return {"Authorization": f"Bearer {token}"} if token else {}

    # ── 401 · 403 ────────────────────────────────────────────────────────────
    check("④ 토큰이 없으면 401", "GET /documents", 401,
          client.get("/api/admin/rag/documents").status_code)
    check("④ Bearer 가 아니면 401", "GET /documents", 401,
          client.get("/api/admin/rag/documents", headers={"Authorization": "Token abc"}).status_code)
    check("④ 빈 Bearer 는 401", "GET /documents", 401,
          client.get("/api/admin/rag/documents", headers={"Authorization": "Bearer "}).status_code)
    check("④ 가짜 토큰은 401", "GET /documents", 401,
          client.get("/api/admin/rag/documents", headers=head(BAD_TOKEN)).status_code)
    check("④ 로그인해도 명단에 없으면 403", "GET /documents", 403,
          client.get("/api/admin/rag/documents", headers=head(plain_token)).status_code)
    check("④ 쓰기도 비관리자는 403", "POST /reindex", 403,
          client.post("/api/admin/rag/reindex", json={}, headers=head(plain_token)).status_code)
    check("④ 삭제도 비관리자는 403", "DELETE /documents", 403,
          client.delete(f"/api/admin/rag/documents/{VERIFY_DOC}", headers=head(plain_token)).status_code)

    # 명단을 못 읽으면 **열지 않는다.** 여는 쪽으로 기울면 Supabase 를 끊는 것이
    # 곧 권한 우회가 된다.
    dead = with_dead_supabase(
        lambda: client.get("/api/admin/rag/documents", headers=head(admin_token))
    )
    check("④ 명단을 못 읽으면 통과가 아니라 503", "GET /documents", 503, dead.status_code)

    # ── 200 — 관리자 ─────────────────────────────────────────────────────────
    response = client.get("/api/admin/rag/documents", headers=head(admin_token))
    body = response.json()
    check("④ 관리자는 200", "GET /documents", 200, response.status_code)
    states = {doc["source_doc"]: doc for doc in body["documents"]}
    check("④ 말뭉치 8개가 indexed 로 보인다", "documents[].state", 8,
          len([d for d in body["documents"] if d["state"] == "indexed" and not d["source_doc"].startswith("__verify__")]))
    check("④ 총 청크가 178 이상", "documents.total_chunks", True, body["total_chunks"] >= 178)
    check("④ 07.md 가 28청크", "documents['07.md']", 28,
          states.get("07.md", {}).get("chunk_count"))

    # ── 재색인 왕복 ──────────────────────────────────────────────────────────
    before = states.get("10.md", {}).get("chunk_count")
    response = client.post("/api/admin/rag/reindex", json={"source_doc": "10.md"}, headers=head(admin_token))
    body = response.json()
    check("④ 문서 1개 재색인 200", "POST /reindex", 200, response.status_code)
    check("④ 재색인이 같은 청크 수를 낸다", "reindex.total_chunks", before, body["total_chunks"])
    check("④ 재색인 대상이 1개", "reindex.reindexed", 1, body["reindexed"])

    rows = postgrest("doc_chunk", {"select": "chunk_index", "source_doc": "eq.10.md"})
    check("④ 백스톱 — 재색인 뒤 DB 행 수", "doc_chunk", before, len(rows))
    check("④ chunk_index 가 0..N-1 로 연속", "doc_chunk", list(range(len(rows))),
          sorted(int(r["chunk_index"]) for r in rows))

    check("④ 없는 문서 재색인은 404", "POST /reindex", 404,
          client.post("/api/admin/rag/reindex", json={"source_doc": "nope.md"}, headers=head(admin_token)).status_code)
    check("④ 경로 탈출 시도는 422", "POST /reindex", 422,
          client.post("/api/admin/rag/reindex", json={"source_doc": "../.env"}, headers=head(admin_token)).status_code)

    # ── orphan — 파일 없는 색인이 보이고, 지울 수 있다 ───────────────────────
    orphan_rows = service.build_chunks(VERIFY_ORPHAN, "고아 청크입니다. 파일은 저장소에 없습니다.")
    doc_chunk_repo.replace_document(VERIFY_ORPHAN, orphan_rows)
    body = client.get("/api/admin/rag/documents", headers=head(admin_token)).json()
    orphan = next((d for d in body["documents"] if d["source_doc"] == VERIFY_ORPHAN), None)
    check("④ 파일 없는 색인이 orphan 으로 보인다", "documents[].state", "orphan",
          orphan["state"] if orphan else None)
    check("④ orphan 은 on_disk 가 false", "documents[].on_disk", False,
          orphan["on_disk"] if orphan else None)

    response = client.delete(f"/api/admin/rag/documents/{VERIFY_ORPHAN}", headers=head(admin_token))
    check("④ orphan 삭제 200", "DELETE /documents", 200, response.status_code)
    check("④ 삭제 뒤 DB 에 남지 않는다", "doc_chunk", 0,
          len(postgrest("doc_chunk", {"select": "id", "source_doc": f"eq.{VERIFY_ORPHAN}"})))

    # ── replace_document 가 꼬리를 남기지 않는다 ─────────────────────────────
    long_rows = service.build_chunks(VERIFY_DOC, "가" * 5000)
    doc_chunk_repo.replace_document(VERIFY_DOC, long_rows)
    short_rows = service.build_chunks(VERIFY_DOC, "짧은 문서입니다.")
    doc_chunk_repo.replace_document(VERIFY_DOC, short_rows)
    remaining = postgrest("doc_chunk", {"select": "chunk_index", "source_doc": f"eq.{VERIFY_DOC}"})
    check("④ 문서가 짧아지면 옛 꼬리가 사라진다", "replace_document", len(short_rows), len(remaining),
          f"  (긴 판 {len(long_rows)}청크 → 짧은 판 {len(short_rows)}청크)")

    # ── 조건 없는 DELETE 는 거부 ─────────────────────────────────────────────
    try:
        supabase_client.delete("doc_chunk", {})
        refused = False
    except supabase_client.SupabaseError:
        refused = True
    check("④ 조건 없는 DELETE 는 거부된다", "supabase_client.delete", True, refused)


# ─────────────────────────────────────────────────────────────────────────────
# 정리
# ─────────────────────────────────────────────────────────────────────────────
def cleanup() -> None:
    for source_doc in (VERIFY_DOC, VERIFY_ORPHAN):
        try:
            doc_chunk_repo.delete_document(source_doc)
        except Exception as exc:  # noqa: BLE001 — 정리는 최선 노력이다
            print(f"[WARN] {source_doc} 정리 실패: {exc}")
    for user_id in created_users:
        try:
            supabase_client.delete("app_admin", {"user_id": f"eq.{user_id}"})
            _auth_request("DELETE", f"/auth/v1/admin/users/{user_id}")
        except Exception as exc:  # noqa: BLE001
            print(f"[WARN] 계정 {user_id} 정리 실패: {exc}")


# ─────────────────────────────────────────────────────────────────────────────
# ⑤ 후속 질문 (R-04 · CN-128) — 네트워크 0 · 결정적
#
# 섹션 ① 에 얹지 않는다. ① 은 "옛 색인 스크립트와 값이 같은가" 로 뜻이 확정돼 있어
# 성격이 다른 검사를 넣으면 섹션 이름이 거짓이 된다.
#
# 전수 입력은 `docs/*.md` 를 `service.chunk_text` 로 다시 잘라 만든다 — ① 의
# `verify_port()` 가 이미 쓰는 방식이라 새 기법이 아니고 `.env` 도 필요 없다.
# ─────────────────────────────────────────────────────────────────────────────
def _corpus_sources() -> list[dict]:
    """말뭉치 전체를 `to_source()` 모양의 청크 리스트로 만든다."""
    out: list[dict] = []
    for path in _corpus_paths():
        for index, chunk in enumerate(service.chunk_text(path.read_text(encoding="utf-8"))):
            out.append({
                "score": 0.0, "source_doc": path.name, "chunk_index": index, "text": chunk,
            })
    return out


def verify_followups() -> None:
    corpus = _corpus_sources()

    # ── 전수 안전 — 말뭉치가 만들 수 있는 모든 후보를 한 번에 본다 ─────────────
    every: set[str] = set()
    for source in corpus:
        for _tier, _order, text in service.followup_candidates(source):
            every.add(text)
    check("⑤ 말뭉치가 후보를 만든다", "followup_candidates", True, len(every) > 0,
          extra=f" (고유 {len(every)}개)")
    check("⑤ 후보가 전부 물음표로 끝난다", "followup_candidates", [],
          sorted(t for t in every if not t.endswith("?")))
    check("⑤ 후보에 금칙어가 없다", "followup_banned_hit", [],
          sorted(t for t in every if service.followup_banned_hit(t)))
    check("⑤ 후보에 6자리 종목코드가 없다", "followup_candidates", [],
          sorted(t for t in every if re.search(r"(?<!\d)\d{6}(?!\d)", t)))
    check("⑤ 후보에 숫자% 약속이 없다", "followup_candidates", [],
          sorted(t for t in every if re.search(r"\d\s*%", t)))
    check("⑤ 후보가 길이 상한을 지킨다", "FOLLOWUP_MAX_CHARS", [],
          sorted(t for t in every if len(t) > service.FOLLOWUP_MAX_CHARS))
    # 화면이 escapeHtml 을 걸지만, 서버가 애초에 내보내지 않는 것이 이중 방어의 안쪽이다.
    check("⑤ 후보에 HTML 특수문자가 없다", "followup_candidates", [],
          sorted(t for t in every if any(ch in t for ch in '<>&"')))

    # ── 절단 조각 — 청크 경계가 낱말 중간을 자른 것이 버튼이 되면 안 된다 ──────
    #
    # `docs/06.md` 청크 2의 첫 줄은 `가도 버틸 수 있나요?` 인데 원문은
    # `가격이 많이 내려가도 버틸 수 있나요?` 이고 1200자 경계가 `내려|가도` 를 쪼갠 것이다.
    # **뒤가 온전해 물음표로 멀쩡히 끝나므로 다른 어떤 검사에도 안 걸린다** —
    # 그래서 여기서 따로 못박는다. 꼬리 절단은 `?` 로 안 끝나 자동으로 걸러진다.
    머리절단 = [
        text
        for source in corpus
        if int(source["chunk_index"]) > 0
        for _tier, order, text in service.followup_candidates(source)
        if order == 0
    ]
    check("⑤ 첫 청크가 아니면 첫 줄을 후보로 쓰지 않는다", "followup_candidates", [], 머리절단)
    check("⑤ 알려진 절단 조각이 되살아나지 않는다", "followup_candidates", False,
          "가도 버틸 수 있나요?" in every)

    # 전수 후보 수를 여기서 센다 — 코드 주석에 손으로 적지 않기 위해서다(CN-121 · CN-126).
    # 말뭉치나 규칙이 바뀌면 이 값이 움직이고, 그때 CN-128 의 숫자를 함께 고치면 된다.
    check("⑤ 전수 후보 수가 기록과 같다", "followup_candidates 고유", 349, len(every))

    # ── R-07 정본 목록 대조 — 손으로 베끼지 않는다 ────────────────────────────
    #
    # `verify_r07_expressions.py` 의 두 리스트를 `ast` 로 떼어 `followup_banned_hit()`
    # 에 **직접** 먹인다. `build_followups` 를 통해 시험하면 길이·한글 하한이 먼저 걸려
    # 금칙어 목록이 비어도 초록으로 뜬다 — 공허한 검사가 된다.
    r07_source = (ROOT / "scripts" / "verify_r07_expressions.py").read_text(encoding="utf-8")
    r07_lists: dict[str, list[str]] = {}
    for node in ast.walk(ast.parse(r07_source)):
        if isinstance(node, ast.Assign) and isinstance(node.targets[0], ast.Name):
            name = node.targets[0].id
            if name in ("BANNED_PRODUCTS", "BANNED_BRANDS"):
                r07_lists[name] = list(ast.literal_eval(node.value))
    for name in ("BANNED_PRODUCTS", "BANNED_BRANDS"):
        words = r07_lists.get(name, [])
        check(f"⑤ {name} 을 전부 잡는다", "followup_banned_hit", [],
              [w for w in words if not service.followup_banned_hit(w)],
              extra=f" ({len(words)}개 대조)")

    # ── 경계 ─────────────────────────────────────────────────────────────────
    check("⑤ sources 0건이면 빈 목록", "build_followups", [],
          service.build_followups("분산투자", []))
    check("⑤ limit 0 이면 빈 목록", "build_followups", [],
          service.build_followups("분산투자", corpus, limit=0))
    check("⑤ text 가 없으면 빈 목록", "build_followups", [],
          service.build_followups("분산투자", [{"score": 1.0, "source_doc": "a.md",
                                            "chunk_index": 0, "text": ""}]))
    # 한 글자 질의는 어간을 못 만든다. 관문이 통째로 열려 아무거나 나오면 안 된다.
    check("⑤ 어간 없는 질의는 빈 목록", "build_followups", [],
          service.build_followups("요", corpus))
    check("⑤ limit 1 이면 1개 이하", "build_followups", True,
          len(service.build_followups("거래량", corpus, limit=1)) <= 1)

    # 후속 질문은 **부가물**이다. 못 만드는 것은 빈 목록으로 끝나야 하고, 답변까지
    # 500 으로 끌고 내려갈 일이 아니다. 망가진 행을 먹여도 예외가 없어야 한다 —
    # `float("x")` 가 ValueError 를 던지는 것을 실제로 겪어서 넣은 검사다.
    깨진행들 = (
        {"score": "x", "source_doc": "a.md", "chunk_index": 0, "text": "## 배당의 중요한 날짜\n본문"},
        {"score": 1.0, "source_doc": "a.md", "chunk_index": "zz", "text": "## 배당의 중요한 날짜\n본문"},
        {"score": {}, "source_doc": None, "chunk_index": None, "text": "## 배당의 중요한 날짜\n본문"},
        {},
        {"score": 1.0, "source_doc": "a.md", "chunk_index": 0, "text": None},
    )
    던진것 = []
    for row in 깨진행들:
        try:
            service.build_followups("배당의 날짜는", [row])
        except Exception as exc:  # noqa: BLE001 — 예외가 나오면 그것이 실패다
            던진것.append(f"{row.get('score')!r}/{row.get('chunk_index')!r}: {type(exc).__name__}")
    check("⑤ 깨진 행에도 예외를 던지지 않는다", "build_followups", [], 던진것,
          extra=f" ({len(깨진행들)}종 대조)")
    check("⑤ 상한을 넘지 않는다", "FOLLOWUP_MAX", True,
          all(len(service.build_followups(q, corpus)) <= service.FOLLOWUP_MAX
              for q in ("거래량", "공시", "재무제표", "차트", "배당")))

    # ── 관문 — 출력은 정의상 질의와 어간을 공유한다 ───────────────────────────
    질의들 = ("거래량은 왜 보나요?", "공시는 어디서 확인하나요?", "차트는 어떻게 읽나요?",
             "재무제표를 보는 순서", "배당은 언제 받나요?", "환율이 주가에 주는 영향")
    무관 = []
    for q in 질의들:
        stems = service._followup_stems(q)
        for text in service.build_followups(q, corpus):
            if not (stems & service._followup_stems(text)):
                무관.append((q, text))
    check("⑤ 출력이 전부 질의와 어간을 공유한다", "build_followups 관문", [], 무관)

    # ── 결정성 ───────────────────────────────────────────────────────────────
    check("⑤ 같은 입력에 같은 출력", "build_followups", True,
          service.build_followups("거래량", corpus) == service.build_followups("거래량", corpus))
    # 라우터가 준 순서에 의존하면 안 된다 — 함수가 안에서 다시 정렬한다.
    check("⑤ 입력 순서를 뒤집어도 같다", "build_followups",
          service.build_followups("거래량", corpus),
          service.build_followups("거래량", list(reversed(corpus))))

    # ── 골든 거부 — 조사·심사가 원문에서 찾아낸 실제 위험 사례 ────────────────
    #
    # 목록을 여기에 못박는다. 하나라도 통과하게 되면 FAIL 이다. 옛 커밋에서 뽑지
    # 않는 이유는 `verify_r07_expressions.py:11` 과 같다 — 되살아나는 것을 잡으려면
    # 기대값이 코드에 남아 있어야 한다.
    거부해야 = (
        'LEAN은 "삼성전자를 오늘 사야 하나요?',
        "삼성전자에 대입해 보기",
        "「삼성전자에 대입해 보기」 — 문서는 이 부분을 어떻게 설명하나요?",
        "추격매수는 무엇일까요?",
        "지금 바로 사지 않아도 되는 이유와, 사야 하는 이유를 각각 한 문장으로 적을 수 있나요?",
        "산타 랠리: 연말에 오른다는 말은 무엇일까요?",
        "1년 중 언제 투자하면 좋을까요?",
        "각 팀별로 모의 투자 시스템을 구축하여 매매 연습 합니다.",
        "com/store/apps/details?",
        "「내 경우에는 무엇을 확인해 보면 될까요?」",
        "005930은 어떤 회사인가요?",
        "연 3~5% 수익을 기대할 수 있나요?",
        "KODEX 200을 담아도 될까요?",
        "지금이 좋은 시점인가요?",
        "Docker Compose 는 어떻게 설치하나요?",
        "왜 필요한가요?",
        "배당",
    )
    check("⑤ 골든 거부 목록이 전부 막힌다", "followup_rejected", [],
          [t for t in 거부해야 if service.followup_rejected(t) is None],
          extra=f" ({len(거부해야)}건 대조)")

    # ── 골든 통과 — 막아서는 안 되는 것 ──────────────────────────────────────
    #
    # 명세 4.5절이 "좋은 후속 질문" 의 모범으로 든 두 문장(`docs/07.md:181`)과,
    # 화면 예시(`ragChat.js:3`) 중 규칙에 걸릴 소지가 있던 것들이다. 필터를 조이다가
    # 이쪽이 죽는 것이 실제로 일어났으므로(FOLLOWUP_MIN_TOKENS 4→3) 함께 못박는다.
    통과해야 = (
        "빨간 신호는 무엇을 뜻하나요?",
        "보수적 흐름은 손실 확정인가요?",
        "이동평균선은 왜 볼까요?",
        "양봉과 음봉은 무엇일까요?",
        "지정가 주문과 시장가 주문의 차이는?",
        "「현금흐름표의 세 영역」 — 문서는 이 부분을 어떻게 설명하나요?",
    )
    check("⑤ 골든 통과 목록이 전부 살아 있다", "followup_rejected", [],
          [(t, service.followup_rejected(t)) for t in 통과해야
           if service.followup_rejected(t) is not None],
          extra=f" ({len(통과해야)}건 대조)")

    # ── 템플릿 자체가 안전한가 ───────────────────────────────────────────────
    #
    # 이 모듈이 저작하는 문장은 `FOLLOWUP_TEMPLATE` 하나다. 그 하나가 R-07 을 어기면
    # 모든 tier2 출력이 함께 어긴다. 개인화 요청문("내 경우에는…")을 쓰지 않기로 한
    # 결정(CN-128)이 코드에 남아 있는지 본다.
    shaped = service.FOLLOWUP_TEMPLATE.format(heading="배당의 중요한 날짜")
    check("⑤ 템플릿 산출물이 규칙을 통과한다", "FOLLOWUP_TEMPLATE", None,
          service.followup_rejected(shaped))
    check("⑤ 템플릿에 1인칭 개인화가 없다", "FOLLOWUP_TEMPLATE", [],
          [w for w in ("내 경우", "제 경우", "제가", "내가", "저는")
           if w in service.FOLLOWUP_TEMPLATE])
    check("⑤ 템플릿에 금칙어가 없다", "FOLLOWUP_TEMPLATE", [],
          service.followup_banned_hit(service.FOLLOWUP_TEMPLATE))
    # 긴 제목은 템플릿을 씌우면 상한을 넘는다. 그 가드가 실제로 도는지 —
    # 넘치는 제목이 tier2 후보가 되지 않아야 한다. 위 "길이 상한" 검사는 말뭉치가
    # 마침 짧아서 통과할 수도 있으므로, 넘치는 입력을 직접 만들어 확인한다.
    긴제목 = "가" * service.FOLLOWUP_MAX_CHARS
    check("⑤ 템플릿이 상한을 넘기면 후보에서 빠진다", "followup_candidates", [],
          [t for _tier, _order, t in service.followup_candidates(
              {"score": 0.0, "source_doc": "x.md", "chunk_index": 0,
               "text": f"## {긴제목}\n뒤에 본문이 있어야 절단 제목이 아니다."})
           if len(t) > service.FOLLOWUP_MAX_CHARS])


def report() -> int:
    """모아 둔 결과를 표로 찍고 종료 코드를 돌려준다."""
    width = max(len(name) for name, *_ in results)
    print()
    for name, endpoint, expected, got, ok in results:
        mark = "OK " if ok else "FAIL"
        print(f"[{mark}] {name:<{width}}  {endpoint}")
        if not ok:
            print(f"        기대: {expected}")
            print(f"        실측: {got}")

    passed = sum(1 for *_, ok in results if ok)
    print(f"\n{passed} / {len(results)} 통과")
    return 0 if passed == len(results) else 1


def main() -> int:
    # ⑤ 는 **게이트 앞**이다. 순수 함수 검사라 `.env` 도 네트워크도 필요 없는데
    # 게이트 뒤에 두면 자격증명이 없는 환경에서 R-07 회귀 검사가 0건 실행된다.
    # 자격증명이 없다는 것과 후속 질문 규칙이 안전하다는 것은 아무 관계가 없다.
    verify_followups()

    if not supabase_client.is_configured():
        print(
            "[WARN] SUPABASE_URL · SUPABASE_SERVICE_ROLE_KEY 가 없어 원격 왕복(①②③④)을\n"
            f"       건너뜁니다. 저장소 루트의 .env 에 두 값을 넣으면 전부 돕니다 ({ROOT / '.env'})."
        )
        # 종료 코드로 두 상태를 가른다. 한 코드로 뭉치면 "⑤ 가 깨졌다" 와 "자격증명이
        # 없다" 가 구별되지 않아, ⑤ 를 게이트 앞으로 옮긴 이유가 사라진다.
        #   1 = 검사 실패 (⑤ 가 깨졌다)
        #   2 = 자격증명이 없어 ①②③④ 를 못 돌렸다 (⑤ 는 전부 통과)
        return report() or 2

    try:
        verify_port()
        verify_disclaimer()
        verify_runtime()
        verify_store_failure()
        verify_admin()
    finally:
        cleanup()

    return report()


if __name__ == "__main__":
    raise SystemExit(main())
