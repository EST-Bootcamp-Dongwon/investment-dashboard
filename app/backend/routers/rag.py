"""F27 문서 검색 챗 API — Controller.

**F03·F04·F05·F28 에 이어 3계층을 다섯 번째로 적용한 대상이다.** 이 파일은 경로 선언 ·
요청 검증 · 도메인 예외를 HTTP 코드로 번역 · 응답 조립만 한다. 청킹·임베딩·답변 조립은
`services/rag.py`, DB 접근은 `clients/doc_chunk_repo.py` 에 있다.

**외부 모델 호출 계층(`clients/rag_llm.py`)은 2026-08-16 에 없앴다.** 절대 제약 1이
"LLM 유료 API 비용 0원" 이고, compose 기본값이 `https://api.openai.com/v1` 이라
키만 꽂으면 과금이 시작되는 배선이었다. 답변은 이제 검색된 원문만 조립해 만든다.

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

## 후속 질문 (R-04 · CN-128)

`/ask` 응답에 `followups` · `followups_head` 를 싣는다. **답변 문자열에 섞지 않는
이유**는 `answer` 가 "원문에서 온 것" 이라는 보증을 지키기 위해서다 — 섞으면 어느
문장이 원문에서 왔는지 사용자도 검증 스크립트도 가를 수 없다. 필드를 나누면
`answer` 는 원문 전용, `followups` 는 규칙 전용이 되어 경계가 스키마에서 강제된다.

계산은 `services/rag.build_followups` 이고 **DB 왕복이 늘지 않는다** — `_search` 가
이미 받아 둔 풀을 그대로 본다. 늘어나는 것은 그 한 번의 요청이 가져오는 행 수다.

설계 정본: docs/spec/30-데이터/테이블-정의서.md 4.7절 · docs/spec/20-기능명세/06-학습과-AI.md 4절.
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

try:
    from ..clients import doc_chunk_repo, supabase_client
    from ..services import rag as service
except ImportError:  # `uvicorn main:app` 를 app/backend 에서 실행하는 경우
    from clients import doc_chunk_repo, supabase_client  # type: ignore
    from services import rag as service  # type: ignore

router = APIRouter()

_STORE_FAILED = "문서 저장소를 읽을 수 없습니다. 잠시 후 다시 시도해 주세요."
_NOT_INDEXED = (
    "학습 문서가 아직 색인되지 않았습니다. "
    "`python3 scripts/index_docs_to_supabase.py` 로 문서를 먼저 색인하세요."
)


class RagAskRequest(BaseModel):
    """옛 `RagSearchRequest` 다. **제약값을 그대로 옮겼다.**

    `/search` 를 지우면서 상속 관계가 없어졌을 뿐, 필드와 상·하한은 바뀌지 않았다
    (`query` 1~2000 · `top_k` 1~20 기본 5 · `score_threshold` 0~1 기본 0).

    2026-08-16 에 `provider` 만 빠졌다 — 아래 주석 참고.
    """

    query: str = Field(min_length=1, max_length=2000, description="검색 질문")
    top_k: int = Field(default=5, ge=1, le=20, description="반환할 최대 청크 수")
    score_threshold: float = Field(default=0.0, ge=0.0, le=1.0, description="최소 유사도 점수")
    # `provider` 필드를 없앴습니다 (2026-08-16). 값이 `rag|openai_compatible` 둘이었고
    # 후자가 외부 유료 API 를 부르는 경로였습니다 — 절대 제약 1 위반이라 폐기했습니다.
    #
    # **호환을 위해 남기지 않았습니다.** pydantic 은 모르는 필드를 조용히 무시하므로,
    # 옛 화면이 `provider: "openai_compatible"` 을 계속 보내도 422 가 아니라 그냥
    # RAG 답변이 나갑니다. 필드를 남겨 두면 "선택할 수 있다" 는 신호가 스키마에
    # 남아 다음 사람이 배선을 되살립니다.


def _search(req: RagAskRequest) -> tuple[list[dict], list[dict]]:
    """검색만 한다. 저장소 실패는 503 으로 번역한다.

    **왕복은 여전히 1회다.** `match_count` 만 `FOLLOWUP_POOL` 까지 키워, 화면에 싣는
    상위 `top_k` 와 후속 질문이 뒤질 넓은 풀을 한 요청으로 함께 받는다.

    풀을 키우는 이유는 해시 검색이 관련 청크를 상위로 못 올리기 때문이다(CN-015 ·
    CN-129). 후속 질문은 **질의와 어간이 겹치는 후보만** 고르므로(`build_followups`
    의 관문), 좁은 풀에서는 겹치는 것이 아예 안 잡힌다.

    **풀 크기별 커버리지 표와 60 을 고른 근거는 변경노트 CN-128 에 한 벌만 있다.**
    여기에 복제하지 않는다 — 같은 표를 두 곳에 적었더니 값이 갈렸다(CN-121 과 같은 부류).
    요지만 적으면: 풀을 안 키우면 커버리지가 3분의 1로 떨어지고, 전체(178행)를 받으면
    payload 가 353KB 가 된다. 60 은 그 사이의 절충이고 **검색이 고장 나 있는 동안의
    보상값**이라, CN-021 로 의미 검색이 들어오면 낮춰야 한다.

    `RagAskRequest.top_k` 의 상한(`le=20`)은 *응답에 싣는 개수* 제한이라 그대로 두고
    풀만 서비스 상수로 분리했다. 돌려주는 것은 `(응답용 top_k, 후속질문용 풀)` 이다.
    """
    try:
        rows = doc_chunk_repo.search(
            service.hash_embed(req.query),
            match_count=max(req.top_k, service.FOLLOWUP_POOL),
            score_threshold=req.score_threshold,
        )
    except supabase_client.SupabaseError as exc:
        raise HTTPException(status_code=503, detail=_STORE_FAILED) from exc
    pool = [service.to_source(row) for row in rows]
    return pool[: req.top_k], pool


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
    """학습 문서에서 근거를 찾아, **검색된 원문만 조립해** 답합니다."""
    sources, pool = _search(req)
    if not sources:
        _assert_indexed()

    # **답변은 검색된 원문만 조립해 만듭니다.** 외부 모델 분기가 여기 있었고
    # 2026-08-16 에 걷어냈습니다(절대 제약 1). 걷어내면서 R-07 이 강해졌습니다 —
    # 옛 분기는 "근거가 0건이면 외부 모델을 부르지 않는다" 는 **조건**으로 환각을
    # 막았는데, 이제는 부를 모델 자체가 없어 조건이 필요 없습니다.
    answer = service.compose_answer(sources)

    return {
        "query": req.query,
        "answer": answer,
        # 하드코딩이 아니라 서비스 상수를 읽는다. 옛 구현은 문자열 'hash' 를 세 곳에
        # 박아 두어(`rag.py:168,181,206`) 임베딩을 바꾸면 응답이 거짓이 됐다.
        "embed_method": service.EMBED_METHOD,
        "sources": sources,
        "source_count": len(sources),
        "disclaimer": service.DISCLAIMER,
        "disclaimer_context": service.DISCLAIMER_CONTEXT,
        # 후속 질문은 **답변이 아니라 메타데이터**다. `answer` 는 원문 전용으로 두고
        # 규칙 계산 결과를 별개 필드로 내보내면, "이 문장은 원문에서 왔는가" 의 경계가
        # 타입 수준에서 갈린다. 옛 `provider` 분기 **밖**에서 계산하도록 짜 두었기에,
        # 그 분기를 걷어낸 지금도 이 자리가 그대로다 (R-04 · CN-128).
        #
        # 넘기는 것은 `sources`(top_k) 가 아니라 `pool`(최대 FOLLOWUP_POOL) 이다 —
        # 좁은 쪽을 주면 관문을 통과하는 후보가 크게 줄어든다 (CN-128 의 표).
        "followups": service.build_followups(req.query, pool),
        "followups_head": service.FOLLOWUP_HEAD,
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
        "embed_method": service.EMBED_METHOD,
        "disclaimer": service.DISCLAIMER,
        "disclaimer_context": service.DISCLAIMER_CONTEXT,
    }
