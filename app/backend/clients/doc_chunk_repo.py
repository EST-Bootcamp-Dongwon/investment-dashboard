"""F27 문서 청크 색인·검색 — Repository.

Controller(`routers/rag.py` · `routers/admin.py`) → Service(`services/rag.py`) →
**Repository(여기)** → 전송(`clients/supabase_client.py`).

`combination_repo.py` 와 같은 자리·같은 규칙이다. 도메인 판단은 하지 않는다.

## 앞의 넷과 다른 점 — **소유자가 없다**

F03·F04·F05·F28 의 repo 는 전부 `user_id`/`anon_id` 를 받아 넣고 그것으로 걸러 읽었다.
`doc_chunk` 에는 그 컬럼이 없다. 색인은 **누구의 것도 아닌 참조 데이터**이고
(ERD 5.4절 "배치가 채우고 화면이 읽기만"), 그래서 이 파일에는 소유자 인자가 없다.

읽기는 아무나 할 수 있고(RLS `문서 청크 공개 조회`), 쓰기는 정책이 아예 없어서
service_role 을 쥔 서버·배치만 할 수 있다. "누가 써도 되는가" 의 판정은 DB 가 아니라
`routers/owner.require_admin` 이 한다.

## RPC 를 쓰는 이유는 앞의 셋과 또 다르다

F03·F05 는 부모·자식을 한 트랜잭션에 넣으려고 RPC 를 만들었고, F04 는 그 이유가 없어
PostgREST 질의로 갔다. 여기서 RPC 를 쓰는 것은 **PostgREST 로 표현할 수 없기 때문**이다 —
벡터 거리 연산자 `<=>` 로 정렬하는 질의를 PostgREST 질의 문법으로 쓸 방법이 없다.
`doc_chunk_stats` 도 같다(`group by`).
"""

from __future__ import annotations

from typing import Any

try:
    from . import supabase_client
except ImportError:  # `uvicorn main:app` 를 app/backend 에서 실행하는 경우
    import clients.supabase_client as supabase_client  # type: ignore

# 색인 한 번에 보내는 행 수. 178행 전체를 한 요청에 넣으면 본문이 대략 6MB 가 되는데
# (384 float × 178행), Vercel 함수의 요청 본문 상한이 4.5MB 다(배포-전략 50~59).
# 색인 스크립트는 서버를 거치지 않아 그 상한과 무관하지만, 관리자 화면의 재색인은
# 서버를 거친다. 두 경로가 같은 repo 를 쓰므로 좁은 쪽에 맞춘다.
#
# 문서 단위로 자르지 않고 행 수로 자르는 이유는 문서 크기가 고르지 않기 때문이다
# (03.md 45청크 · 10.md 6청크).
INSERT_BATCH = 50


def search(
    query_embedding: list[float], *, match_count: int, score_threshold: float
) -> list[dict[str, Any]]:
    """해시 임베딩으로 상위 N개 청크를 찾는다.

    `match_doc_chunk_hash`(마이그레이션 20260814120100)를 부른다. 768 쪽
    `match_doc_chunk` 가 아니다 — 지금 색인이 전부 `embed_method='hash'` 라
    768 함수는 `where c.embedding is not null` 에서 0건을 준다.

    벡터는 float 리스트로 그대로 보낸다. JSON 배열 `[0.1,...]` 이 pgvector 의 텍스트
    입력 형식과 같은 모양이라 캐스팅이 성립한다. 이것이 실제로 되는지는 추정이 아니라
    `scripts/verify_rag_api.py` 가 원격에 대고 확인한다.
    """
    rows = supabase_client.rpc(
        "match_doc_chunk_hash",
        {
            "query_embedding": query_embedding,
            "match_count": match_count,
            "score_threshold": score_threshold,
        },
    )
    return rows if isinstance(rows, list) else []


def stats() -> list[dict[str, Any]]:
    """문서별 색인 현황을 돌려준다. `[{source_doc, chunk_count, embed_method, indexed_at}]`.

    청크 원문을 싣지 않는다. 목록을 다 받아 브라우저에서 세면 353KB 가 통째로 나간다.
    """
    rows = supabase_client.rpc("doc_chunk_stats", {})
    return rows if isinstance(rows, list) else []


def total_chunks() -> int:
    """색인된 청크 총수. `stats()` 를 합산한다.

    PostgREST 의 `count=exact` 헤더를 쓰지 않는 것은 `supabase_client.select` 가 응답
    헤더를 돌려주지 않아서다. 전송 계층에 기능을 하나 더 만드는 것보다 이미 있는 RPC 를
    합산하는 쪽이 싸다 — 문서가 8개라 합산 대상이 8행이다.
    """
    return sum(int(row.get("chunk_count") or 0) for row in stats())


def replace_document(source_doc: str, rows: list[dict[str, Any]]) -> int:
    """문서 한 편의 색인을 통째로 갈아 끼운다. 넣은 청크 수를 돌려준다.

    ## upsert 가 아니라 delete → insert 인 이유

    `uq_doc_chunk(source_doc, chunk_index)` 기준 upsert 로 하면 **문서가 짧아졌을 때
    옛 꼬리가 남는다.** 45청크였던 문서를 30청크로 줄여 다시 색인하면 31~45번 행이
    그대로 살아서, 검색이 지금 문서에 없는 문장을 근거랍시고 내놓는다.

    ## 트랜잭션이 갈라진다는 것을 알고 고른다

    DELETE 요청과 INSERT 요청이 따로라, DELETE 뒤 INSERT 가 실패하면 **그 문서만
    색인에서 빠진 상태**로 남는다. 그래도 괜찮다고 판단한 근거는 셋이다.

    ① 잃는 것이 원본이 아니다. `doc_chunk` 는 `docs/*.md` 에서 파생된 값이고 원본은
       저장소에 그대로 있다. 다시 돌리면 복구된다 — 사용자 데이터였다면 이 판단을
       할 수 없다.
    ② **빠진 것이 보인다.** 관리자 화면이 문서별 청크 수를 보여 주므로 0건이 된 문서가
       눈에 띈다. 조용히 틀린 상태가 아니다.
    ③ 한 트랜잭션으로 묶으려면 384×N 개 float 를 jsonb 로 받는 함수를 새로 만들어야
       하는데, 그 함수는 이 저장소에서 검증된 적 없는 크기의 인자를 받는다.

    `combination_repo.insert_combination:95~100` 이 트랜잭션을 가른 것과 같은 형태의
    판단이고, 기준도 같다 — **실패했을 때 남는 것이 유효한가.**
    """
    supabase_client.delete("doc_chunk", {"source_doc": f"eq.{source_doc}"})

    inserted = 0
    for start in range(0, len(rows), INSERT_BATCH):
        inserted += supabase_client.insert_many("doc_chunk", rows[start : start + INSERT_BATCH])
    return inserted


def delete_document(source_doc: str) -> None:
    """문서 한 편의 색인을 지운다. 없는 문서를 지워도 오류가 아니다(0행 삭제)."""
    supabase_client.delete("doc_chunk", {"source_doc": f"eq.{source_doc}"})
