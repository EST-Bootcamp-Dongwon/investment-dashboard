-- doc_chunk — F27 RAG 벡터 (pgvector).
-- 정본: docs/spec/30-데이터/테이블-정의서.md 4.7절.
-- Qdrant 컬렉션 investment_docs (rag.py:17) 를 대체한다 (CN-021 · D-08).

create table doc_chunk (
  id             bigint      primary key generated always as identity,
  source_doc     text        not null,
  chunk_index    integer     not null,
  content        text        not null,
  -- 벡터 컬럼이 둘인 이유: 차원이 768 과 384 로 다르다. vector(n) 은 차원이 타입의
  -- 일부라 한 컬럼에 섞을 수 없다.
  embedding      extensions.vector(768) null,  -- gemini-embedding-001 절단·정규화
  embedding_hash extensions.vector(384) null,  -- 폴백용 _hash_embed (rag.py:52)
  embed_method   text        not null,
  token_count    integer     null,             -- 2,048 토큰 상한 감시용
  indexed_at     timestamptz not null default now(),

  constraint uq_doc_chunk unique (source_doc, chunk_index),
  constraint ck_doc_chunk_index  check (chunk_index >= 0),
  constraint ck_doc_chunk_method check (embed_method in ('gemini', 'hash')),
  constraint ck_doc_chunk_embedding check (
    (embed_method = 'gemini' and embedding      is not null) or
    (embed_method = 'hash'   and embedding_hash is not null)
  )
);

comment on table doc_chunk is 'F27 RAG 문서 청크와 임베딩 (테이블-정의서 4.7)';

-- 코사인 거리 기준 근사 최근접 탐색.
-- pgvector 인덱스는 2,000 차원까지라 768 은 안전하다 (Gemini 기본 3072 는 불가).
-- 178행이면 순차 스캔으로 충분하고, 이 인덱스는 성능이 아니라 설계 정합성 목적이다.
create index idx_doc_chunk_embedding on doc_chunk
  using hnsw (embedding extensions.vector_cosine_ops);

-- 검색 함수 — 프론트에 SQL 을 노출하지 않기 위해 RPC 로 감싼다.
-- 벡터 연산자(<=>)가 extensions 스키마에 있으므로 search_path 에 함께 넣는다.
create or replace function match_doc_chunk(
  query_embedding extensions.vector(768),
  match_count int default 5,
  score_threshold float default 0.0
)
returns table (id bigint, source_doc text, chunk_index int, content text, score float)
language sql stable
set search_path = public, extensions
as $$
  select c.id, c.source_doc, c.chunk_index, c.content,
         1 - (c.embedding <=> query_embedding) as score
  from doc_chunk c
  where c.embedding is not null
    and 1 - (c.embedding <=> query_embedding) >= score_threshold
  order by c.embedding <=> query_embedding
  limit match_count;
$$;

-- 반환 필드는 현행 rag.py:86~91 의 {score, source_doc, chunk_index, text} 와 이름을
-- 맞췄다(text → content 만 다름). 응답 직렬화 단계에서 content → text 로 되돌린다.
comment on function match_doc_chunk is 'F27 코사인 유사도 상위 N개 청크 조회';
