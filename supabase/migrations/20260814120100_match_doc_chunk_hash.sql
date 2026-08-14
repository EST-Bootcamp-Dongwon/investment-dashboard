-- match_doc_chunk_hash — 해시 임베딩(384) 검색 경로.
-- 정본: docs/spec/30-데이터/테이블-정의서.md 4.7절 (버전업 때 이 함수를 추가 기술).
--
-- ## 왜 필요한가 — 약속된 폴백이 스키마에서 동작하지 않았다
--
-- 문서 두 곳이 해시 폴백을 약속한다:
--   ERD.md 4.3절        "API 키가 없거나 호출이 실패하면 `_hash_embed` 로 되돌아가
--                        검색이 죽지 않게 합니다"
--   외부-데이터소스.md   "429 응답 시 해시 임베딩으로 폴백하는 경로를 반드시 남깁니다"
--
-- 그런데 20260809120600_init_doc_chunk.sql 의 match_doc_chunk 는
--   :38  query_embedding extensions.vector(768)
--   :49  where c.embedding is not null
-- 이라 embedding_hash 를 아예 읽지 않고, hnsw 인덱스도 embedding 컬럼 하나뿐이다(:32~33).
-- **폴백해도 결과가 0건이다.** 스키마는 embedding_hash 컬럼과
-- ck_doc_chunk_embedding 의 'hash' 분기까지 미리 마련해 두고 검색만 빠져 있었다.
-- 이 파일은 그 구멍을 메운다 — 새 설계가 아니라 예비된 컬럼에 조회 경로를 붙이는 것이다.
--
-- ## 왜 지금 이것이 주 경로인가
--
-- gemini-embedding-001 을 쓰려면 GEMINI_API_KEY 가 필요한데 저장소 어디에도 없고
-- (2026-08-14 실측 — .env · .key · app/backend/.env.example 셋 다 키 이름 없음),
-- **사용자가 Gemini 키를 쓰지 않기로 결정했다** (2026-08-14).
-- 따라서 embed_method 는 당분간 'hash' 하나이고, 검색은 이 함수를 탄다.
-- match_doc_chunk(768) 은 지우지 않는다 — 키가 생기는 날 그대로 켜진다.
--
-- ## 이 검색이 무엇인지 정확히 말해 둔다
--
-- _hash_embed(app/backend/services/rag.py)는 토큰을 sha256 해시로 384칸에 흩뿌리는
-- 해싱 트릭이다. **의미 검색이 아니라 어휘 일치**이고, "분산투자" 와 "나누어 담는다"
-- 를 잇지 못한다. CN-015 가 이미 지적한 한계이며, 여기서 바뀌지 않는다.
-- 응답의 embed_method 가 'hash' 라는 것이 그 사실을 화면까지 전달하는 통로다.

-- 코사인 거리 기준 근사 최근접 탐색. 768 쪽과 같은 연산자 클래스를 쓴다.
-- pgvector 인덱스 상한은 2,000 차원이라 384 는 여유가 있다.
create index idx_doc_chunk_embedding_hash on doc_chunk
  using hnsw (embedding_hash extensions.vector_cosine_ops);

-- match_doc_chunk(768) 과 **이름만 다르고 형태는 같다.** 반환 컬럼·정렬·임계값 처리를
-- 일부러 그대로 뒀다 — 두 경로가 다르게 굴면 키가 생겨 768 로 옮기는 날 결과가
-- 조용히 바뀐다. 벡터 연산자(<=>)가 extensions 스키마에 있으므로 search_path 에 넣는다.
create or replace function match_doc_chunk_hash(
  query_embedding extensions.vector(384),
  match_count int default 5,
  score_threshold float default 0.0
)
returns table (id bigint, source_doc text, chunk_index int, content text, score float)
language sql stable
set search_path = public, extensions
as $$
  select c.id, c.source_doc, c.chunk_index, c.content,
         1 - (c.embedding_hash <=> query_embedding) as score
  from doc_chunk c
  where c.embedding_hash is not null
    and 1 - (c.embedding_hash <=> query_embedding) >= score_threshold
  order by c.embedding_hash <=> query_embedding
  limit match_count;
$$;

comment on function match_doc_chunk_hash is 'F27 해시 임베딩(384) 코사인 유사도 상위 N개 청크 조회';

-- 색인 현황 조회 — 관리자 화면이 "지금 무엇이 색인돼 있나" 를 묻는 곳.
--
-- PostgREST 로는 group by 를 표현할 수 없어 함수로 감싼다. 화면이 178행을 다 받아
-- 브라우저에서 세는 방법도 있지만, 그러면 청크 원문 353KB 가 통째로 나간다.
create or replace function doc_chunk_stats()
returns table (source_doc text, chunk_count bigint, embed_method text, indexed_at timestamptz)
language sql stable
set search_path = public
as $$
  select c.source_doc,
         count(*)              as chunk_count,
         min(c.embed_method)   as embed_method,   -- 한 문서는 한 방식으로 색인된다
         max(c.indexed_at)     as indexed_at
  from doc_chunk c
  group by c.source_doc
  order by c.source_doc;
$$;

comment on function doc_chunk_stats is 'F27 문서별 색인 현황 — 관리자 화면용';
