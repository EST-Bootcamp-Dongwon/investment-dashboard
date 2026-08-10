-- combination_query — F04 조합 조회 이력.
-- 정본: docs/spec/30-데이터/테이블-정의서.md 4.4절.
-- 응답 필드 출처: app/backend/main.py:1234~1243.

create table combination_query (
  id             bigint      primary key generated always as identity,
  user_id        uuid        null references app_user (id) on delete set null,
  anon_id        text        null,
  ticker_a       text        not null,
  ticker_b       text        not null,
  period         combination_period not null,
  signal         text        not null,
  summary        text        not null,
  portfolio_hint text        null,
  latest_data_at timestamptz null,
  created_at     timestamptz not null default now(),

  constraint ck_combination_query_owner
    check (user_id is not null or anon_id is not null),
  constraint ck_combination_query_anon_id
    check (anon_id is null or char_length(anon_id) <= 64),
  constraint ck_combination_query_ticker_a
    check (char_length(ticker_a) between 1 and 20),
  constraint ck_combination_query_ticker_b
    check (char_length(ticker_b) between 1 and 20),
  constraint ck_combination_query_signal
    check (char_length(signal) <= 20),
  constraint ck_combination_query_summary
    check (char_length(summary) <= 500),
  constraint ck_combination_query_hint
    check (portfolio_hint is null or char_length(portfolio_hint) <= 500)
);

-- chart_points 는 저장하지 않는다. 시세 파생물이고 행 수가 크다 (제약 C-04).
-- (ticker_a, ticker_b, period) 로 언제든 다시 계산된다.
-- latest_data_at 은 남긴다 — 같은 입력이라도 시세가 갱신되면 결과가 달라지므로
-- "이 판정은 어느 시점 데이터였나" 가 증거로 필요하다.
comment on table combination_query is 'F04 조합 조회 이력 (테이블-정의서 4.4)';

create index idx_combination_query_user_created on combination_query (user_id, created_at desc);
create index idx_combination_query_anon_created on combination_query (anon_id, created_at desc);
create index idx_combination_query_tickers      on combination_query (ticker_a, ticker_b);
