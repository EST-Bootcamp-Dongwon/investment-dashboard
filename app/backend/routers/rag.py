"""F27 문서 검색 챗 API — Controller.

**F03·F04·F05·F28 에 이어 3계층을 다섯 번째로 적용한 대상이다.** 이 파일은 경로 선언 ·
요청 검증 · 도메인 예외를 HTTP 코드로 번역 · 응답 조립만 한다. 청킹·임베딩·답변 조립은
`services/rag.py`, DB 접근은 `clients/doc_chunk_repo.py`, 외부 모델 호출은
`clients/rag_llm.py` 에 있다.

## 앞의 넷과 다른 점 — **"저장 경로" 의 모양이 다르다**

F03·F04·F05·F28 은 전부 *사용자가 한 일을 이력으로 남기는* 경로였다. 셋 다 `create` ·
`history` · `detail` 3종에 소유자가 붙었다. **F27 에는 남길 사용자 이력이 없다.**
`doc_chunk` 는 질문·답변이 아니라 *색인*이고, 누구의 것도 아닌 참조 데이터다
(ERD 5.4절 "배치가 채우고 화면이 읽기만").

그래서 이 라우터는 **읽기만 한다.** 쓰기는 두 곳에 있다 —
`scripts/index_docs_to_supabase.py`(배치, 정본)와 `routers/admin.py`(관리자 화면).
`owner.resolve_owner` 가 걸릴 자리는 없고, 대신 관리자 경로에 `owner.require_admin`
이 걸린다.

## Qdrant 를 떠난다 (D-08 · CN-021)

옛 구현은 `QDRANT_URL` 의 컬렉션을 직접 두드렸다. 이제 Supabase pgvector 를 본다.
그에 따라 두 가지가 바뀌었고 둘 다 화면에 영향이 있다.

① `GET /api/rag/status` 의 `qdrant` 키가 **`vector_store`** 가 됐다. 저장소 이름을
   응답 스키마에 박아 두면 옮길 때마다 프런트가 거짓말을 하게 된다.
② `POST /api/rag/search` 를 **삭제했다.** 응답이 `/ask` 의 `sources` 와 같아 추가로
   주는 정보가 0 이라는 것이 이미 확인돼 삭제가 확정돼 있었다(CN-028 · 기능ID-대장).
   화면은 이 경로를 부르지 않는다 — `ragChat.js` 는 `/ask` 와 `/status` 만 쓴다.

## 면책 (R-07)

`/ask` 응답에 `disclaimer` · `disclaimer_context` 를 싣는다. 요구 원문이
*"**AI 답변에는** 교육용 정보이며 개인별 투자 조언이 아니라는 문구를 유지합니다"*
(`docs/07.md:197`)로 **답변 자체**를 지목하기 때문이다. 화면을 거치지 않고 이 API 를
직접 부르는 경로에서도 문구가 답변에 붙어 나간다.

문장은 `services/rag.DISCLAIMER` 하나이고, 화면 쪽 사본과 같은지는
`scripts/verify_rag_api.py` 가 대조한다.

설계 정본: docs/spec/30-데이터/테이블-정의서.md 4.7절 · docs/spec/20-기능명세/06-학습과-AI.md 4절.
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

try:
    from ..clients import doc_chunk_repo, rag_llm, supabase_client
    from ..services import rag as service
except ImportError:  # `uvicorn main:app` 를 app/backend 에서 실행하는 경우
    from clients import doc_chunk_repo, rag_llm, supabase_client  # type: ignore
    from services import rag as service  # type: ignore

router = APIRouter()

_STORE_FAILED = "문서 저장소를 읽을 수 없습니다. 잠시 후 다시 시도해 주세요."
_NOT_INDEXED = (
    "학습 문서가 아직 색인되지 않았습니다. "
    "`python3 scripts/index_docs_to_supabase.py` 로 문서를 먼저 색인하세요."
)


class RagAskRequest(BaseModel):
    """옛 `RagSearchRequest` + `provider` 다. **제약값을 그대로 옮겼다.**

    `/search` 를 지우면서 상속 관계가 없어졌을 뿐, 필드와 상·하한은 바뀌지 않았다
    (`query` 1~2000 · `top_k` 1~20 기본 5 · `score_threshold` 0~1 기본 0).
    """

    query: str = Field(min_length=1, max_length=2000, description="검색 질문")
    top_k: int = Field(default=5, ge=1, le=20, description="반환할 최대 청크 수")
    score_threshold: float = Field(default=0.0, ge=0.0, le=1.0, description="최소 유사도 점수")
    provider: str = Field(
        default="rag",
        pattern="^(rag|openai_compatible)$",
        description="답변 다듬기에 사용할 외부 AI 모듈",
    )


def _search(req: RagAskRequest) -> list[dict]:
    """검색만 한다. 저장소 실패는 503 으로 번역한다."""
    try:
        rows = doc_chunk_repo.search(
            service.hash_embed(req.query),
            match_count=req.top_k,
            score_threshold=req.score_threshold,
        )
    except supabase_client.SupabaseError as exc:
        raise HTTPException(status_code=503, detail=_STORE_FAILED) from exc
    return [service.to_source(row) for row in rows]


def _assert_indexed() -> None:
    """검색이 0건일 때만 부른다 — **"색인이 없다" 와 "안 걸렸다" 를 가른다.**

    둘은 사용자가 할 일이 완전히 다르다. 색인이 없으면 관리자에게 말해야 하고, 그냥
    안 걸린 것이면 질문을 바꿔 보면 된다. 옛 구현은 요청마다 컬렉션 존재를 먼저 물어
    이 둘을 갈랐는데(`_require_qdrant`), 그러면 **모든 질문이 왕복을 하나 더 한다.**
    0건일 때만 확인하면 평상시 비용이 0 이다.
    """
    try:
        total = doc_chunk_repo.total_chunks()
    except supabase_client.SupabaseError as exc:
        raise HTTPException(status_code=503, detail=_STORE_FAILED) from exc
    if total == 0:
        raise HTTPException(status_code=503, detail=_NOT_INDEXED)


@router.post("/api/rag/ask")
def rag_ask(req: RagAskRequest) -> dict[str, object]:
    """학습 문서에서 근거를 찾아 답하고, 선택 시 외부 AI 로 문장만 다듬습니다."""
    sources = _search(req)
    if not sources:
        _assert_indexed()

    if req.provider == "rag" or not sources:
        # 근거가 0건이면 외부 모델을 부르지 않는다. 다듬을 원문이 없는데 부르면
        # 모델이 자기 지식으로 투자 이야기를 지어내고, 그것이 R-07 이 막으려는 바로
        # 그 상황이다 — 옛 구현은 빈 컨텍스트로도 호출했다.
        answer = service.compose_answer(sources)
    else:
        try:
            answer = rag_llm.complete(service.build_llm_prompt(req.query, sources))
        except rag_llm.RagLlmNotConfigured as exc:
            raise HTTPException(status_code=503, detail=str(exc)) from exc
        except rag_llm.RagLlmError as exc:
            raise HTTPException(status_code=502, detail=str(exc)) from exc

    return {
        "query": req.query,
        "answer": answer,
        "provider": req.provider,
        # 하드코딩이 아니라 서비스 상수를 읽는다. 옛 구현은 문자열 'hash' 를 세 곳에
        # 박아 두어(`rag.py:168,181,206`) 임베딩을 바꾸면 응답이 거짓이 됐다.
        "embed_method": service.EMBED_METHOD,
        "sources": sources,
        "source_count": len(sources),
        "disclaimer": service.DISCLAIMER,
        "disclaimer_context": service.DISCLAIMER_CONTEXT,
    }


@router.get("/api/rag/status")
def rag_status() -> dict[str, object]:
    """문서 저장소 연결과 색인 현황을 반환합니다.

    **여기서는 예외를 던지지 않는다.** 화면이 배지를 그리려고 부르는 경로라, 저장소가
    죽었을 때 503 을 주면 화면이 상태를 표시할 방법 자체를 잃는다. 실패는 `available:
    false` 라는 *상태*로 돌려준다 — 이것이 옛 구현의 판단이었고(`_qdrant_available`
    이 예외를 삼켰다) 그대로 유지한다.
    """
    documents: list[dict[str, object]] = []
    available = True
    try:
        documents = [
            {
                "source_doc": row.get("source_doc"),
                "chunk_count": int(row.get("chunk_count") or 0),
                "embed_method": row.get("embed_method"),
                "indexed_at": row.get("indexed_at"),
            }
            for row in doc_chunk_repo.stats()
        ]
    except supabase_client.SupabaseError:
        available = False

    total = sum(int(row["chunk_count"]) for row in documents)  # type: ignore[arg-type]
    return {
        "vector_store": {
            "store": "supabase-pgvector",
            "available": available,
            # `indexed` 를 따로 두는 이유는 "붙었는데 비어 있다" 가 별개 상태이기
            # 때문이다. 옛 `collection_available` 이 하던 구분과 같은 자리다.
            "indexed": available and total > 0,
            "total_chunks": total,
            "document_count": len(documents),
            "documents": documents,
        },
        "external_ai": {"openai_compatible_available": rag_llm.is_configured()},
        "embed_method": service.EMBED_METHOD,
        "disclaimer": service.DISCLAIMER,
        "disclaimer_context": service.DISCLAIMER_CONTEXT,
    }
