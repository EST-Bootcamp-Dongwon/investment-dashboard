"""관리자 API — F27 색인 운영.

**이 저장소의 첫 관리자 경로다.** 2026-08-14 실측으로 관리자 개념이 0건이었다:

    grep -rniE "ADMIN_TOKEN|ADMIN_KEY|is_admin|X-Admin|role.*admin" \\
      --include="*.py" --include="*.js" --include="*.sql" app/ supabase/ scripts/   → 0건

## 색인의 정본은 여전히 배치다

`scripts/index_docs_to_supabase.py` 가 정본이고, 이 라우터는 **운영 창구**다.
둘을 나눈 이유는 실패했을 때 할 수 있는 일이 다르기 때문이다 — 배치는 로그를 보고
다시 돌리면 되지만, 화면은 "지금 무엇이 색인돼 있고 무엇이 어긋났는가" 를 사람에게
보여 줘야 한다. 그래서 이 라우터의 중심은 `GET /documents` 이고 쓰기는 그 결과를
고치는 수단이다.

**같은 `services.rag.build_chunks` 를 쓴다.** 두 경로가 따로 자르면 같은 문서가
색인 경로에 따라 다르게 들어가고, `uq_doc_chunk(source_doc, chunk_index)` 는 그것을
막지 못한다 — 제약은 번호의 중복만 보지 내용은 보지 않는다.

## 권한

`owner.require_admin` — 로그인 토큰이 있고 `app_admin` 에 그 `user_id` 가 있어야 한다.
비로그인(`anon_id`)은 관리자가 될 수 없고, 명단 조회가 실패하면 통과가 아니라 503 이다.
근거는 `routers/owner.py` 의 `require_admin` docstring.

## 파일을 읽는다는 것의 전제

서버가 `docs/*.md` 를 파일시스템에서 읽는다. 로컬·Docker 에서는 성립하고, **Vercel
서버리스에서는 배포 번들에 `docs/` 가 포함돼야 성립한다 (확인 필요 — 첫 배포에서 실측).**
포함되지 않으면 이 라우터의 재색인은 404 를 내고, 그때도 배치 경로는 그대로 동작한다.
"""

from __future__ import annotations

import os
from pathlib import Path

from fastapi import APIRouter, Header, HTTPException
from pydantic import BaseModel, Field

try:
    from ..clients import doc_chunk_repo, supabase_client
    from ..services import rag as service
    from . import owner
except ImportError:  # `uvicorn main:app` 를 app/backend 에서 실행하는 경우
    from clients import doc_chunk_repo, supabase_client  # type: ignore
    from routers import owner  # type: ignore
    from services import rag as service  # type: ignore

router = APIRouter(prefix="/api/admin/rag", tags=["관리자"])

_ADMIN_UNAVAILABLE = "관리자 권한을 확인할 수 없습니다. 잠시 후 다시 시도해 주세요."
_STORE_FAILED = "문서 저장소를 읽을 수 없습니다. 잠시 후 다시 시도해 주세요."
_SAVE_FAILED = "색인을 저장하지 못했습니다. 잠시 후 다시 시도해 주세요."

# 색인 대상 폴더. `upload_docs_to_qdrant.sh:7~8` 의 `DOCS_DIR` 과 같은 기본값이고,
# 같은 환경변수 이름으로 바꿀 수 있게 두었다.
#
# `parents[3]` 은 routers → backend → app → 저장소 루트다.
_DEFAULT_DOCS_DIR = Path(__file__).resolve().parents[3] / "docs"

# `glob("*.md")` 는 **비재귀다.** `docs/spec/` 하위 45개 문서는 색인에서 빠진다.
# 의도된 제외다 — 말뭉치는 투자 상식 문서이고 명세서가 아니다 (`docs/spec/README.md`).
_DOC_GLOB = "*.md"


def _docs_dir() -> Path:
    return Path(os.getenv("DOCS_DIR") or _DEFAULT_DOCS_DIR)


def _source_files() -> dict[str, Path]:
    """`{파일명: 경로}`. 파일명이 곧 `doc_chunk.source_doc` 이다(`'07.md'` 등)."""
    directory = _docs_dir()
    if not directory.is_dir():
        return {}
    return {path.name: path for path in sorted(directory.glob(_DOC_GLOB))}


class ReindexRequest(BaseModel):
    """`source_doc` 을 주면 그 문서만, 비우면 전부 다시 색인한다.

    경로 문자열이 아니라 **파일명만** 받는다. `..` 이나 절대경로가 섞이면 서버가
    아무 파일이나 읽어 색인에 넣게 된다. 아래 `_resolve` 가 실재하는 목록과 대조해
    한 번 더 막는다 — 검증 두 겹인 것은 이 값이 파일시스템에 닿기 때문이다.
    """

    source_doc: str | None = Field(
        default=None, max_length=200, pattern=r"^[A-Za-z0-9가-힣._-]+\.md$"
    )


def _resolve(source_doc: str) -> Path:
    """파일명을 실재하는 경로로 바꾼다. 목록에 없으면 404."""
    files = _source_files()
    path = files.get(source_doc)
    if path is None:
        raise HTTPException(
            status_code=404,
            detail=f"색인 대상 문서가 아닙니다: {source_doc}",
        )
    return path


def _reindex_one(source_doc: str, path: Path) -> dict[str, object]:
    rows = service.build_chunks(source_doc, path.read_text(encoding="utf-8"))
    try:
        inserted = doc_chunk_repo.replace_document(source_doc, rows)
    except supabase_client.SupabaseError as exc:
        raise HTTPException(status_code=503, detail=_SAVE_FAILED) from exc
    return {"source_doc": source_doc, "chunk_count": inserted}


@router.get("/documents")
def list_documents(authorization: str | None = Header(default=None)) -> dict[str, object]:
    """색인 현황을 파일시스템과 **대조해서** 돌려준다.

    `GET /api/rag/status` 도 문서별 청크 수를 주지만, 그것은 DB 만 본다. 여기서는
    `docs/*.md` 와 맞춰 세 가지 상태를 가른다.

    | `state` | 뜻 | 관리자가 할 일 |
    | --- | --- | --- |
    | `indexed` | 파일도 있고 색인도 있다 | 없음 |
    | `missing` | 파일은 있는데 색인이 없다 | 재색인 |
    | `orphan` | 색인은 있는데 파일이 없다 | 삭제 |

    **`orphan` 이 이 화면이 존재하는 이유다.** 문서를 지우거나 이름을 바꾸면 옛 청크가
    DB 에 그대로 남고, 검색은 지금 저장소에 없는 문장을 근거라고 내놓는다. DB 만 보거나
    파일만 봐서는 보이지 않고, 둘을 맞대야 드러난다.
    """
    owner.require_admin(authorization, unavailable_detail=_ADMIN_UNAVAILABLE)

    try:
        indexed = {row["source_doc"]: row for row in doc_chunk_repo.stats()}
    except supabase_client.SupabaseError as exc:
        raise HTTPException(status_code=503, detail=_STORE_FAILED) from exc

    files = _source_files()
    documents = []
    for name in sorted(set(files) | set(indexed)):
        row = indexed.get(name)
        documents.append(
            {
                "source_doc": name,
                "on_disk": name in files,
                "chunk_count": int(row["chunk_count"]) if row else 0,
                "embed_method": row.get("embed_method") if row else None,
                "indexed_at": row.get("indexed_at") if row else None,
                "state": "indexed" if (name in files and row) else ("missing" if name in files else "orphan"),
            }
        )

    return {
        "docs_dir": str(_docs_dir()),
        "total_chunks": sum(int(d["chunk_count"]) for d in documents),  # type: ignore[arg-type]
        "documents": documents,
        "embed_method": service.EMBED_METHOD,
    }


@router.post("/reindex")
def reindex(
    req: ReindexRequest,
    authorization: str | None = Header(default=None),
) -> dict[str, object]:
    """문서를 다시 색인한다. 문서 단위로 지우고 다시 넣는다.

    전량(`source_doc` 없음)이라도 **문서 단위로 처리한다.** 한 문서가 실패해도 나머지는
    이미 들어간 상태이고, 어느 문서에서 멈췄는지가 응답에 남는다. 전부를 한 트랜잭션에
    묶지 않는 근거는 `clients/doc_chunk_repo.replace_document` 의 docstring 에 적었다.
    """
    admin_id = owner.require_admin(authorization, unavailable_detail=_ADMIN_UNAVAILABLE)

    if req.source_doc:
        targets = {req.source_doc: _resolve(req.source_doc)}
    else:
        targets = _source_files()
        if not targets:
            raise HTTPException(
                status_code=404,
                detail=f"색인할 문서를 찾지 못했습니다: {_docs_dir()}",
            )

    results = [_reindex_one(name, path) for name, path in targets.items()]

    # 누가 색인을 고쳤는지 남긴다. 지금은 표준출력뿐이다 — 감사 로그 테이블은 없다.
    print(f"[admin] reindex by={admin_id} docs={len(results)} chunks={sum(int(r['chunk_count']) for r in results)}")

    return {
        "reindexed": len(results),
        "total_chunks": sum(int(r["chunk_count"]) for r in results),
        "documents": results,
        "embed_method": service.EMBED_METHOD,
    }


@router.delete("/documents/{source_doc}")
def delete_document(
    source_doc: str,
    authorization: str | None = Header(default=None),
) -> dict[str, object]:
    """색인에서 문서 한 편을 지운다. **파일은 건드리지 않는다.**

    `_resolve` 를 쓰지 않는다 — 지워야 할 대상이 바로 *파일이 없는데 남은 색인*
    (`orphan`)이라, 파일 존재를 요구하면 정작 필요한 경우에 못 지운다.
    대신 파일명 형식은 그대로 검사한다.
    """
    admin_id = owner.require_admin(authorization, unavailable_detail=_ADMIN_UNAVAILABLE)

    if not ReindexRequest(source_doc=source_doc).source_doc:
        raise HTTPException(status_code=422, detail="문서 파일명이 올바르지 않습니다.")

    try:
        doc_chunk_repo.delete_document(source_doc)
    except supabase_client.SupabaseError as exc:
        raise HTTPException(status_code=503, detail=_SAVE_FAILED) from exc

    print(f"[admin] delete by={admin_id} doc={source_doc}")
    return {"deleted": source_doc}
