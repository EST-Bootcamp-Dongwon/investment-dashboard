-- backtest_summary — F28 백테스트 요약.
-- 정본: docs/spec/30-데이터/테이블-정의서.md 4.6절.
-- 요청 출처 app/backend/routers/backtest_lab.py:62~74, 응답 출처 backtest_lab.py:205~228.

create table backtest_summary (
  id                 bigint       primary key generated always as identity,
  user_id            uuid         null references app_user (id) on delete set null,
  anon_id            text         null,
  ticker             text         not null,
  name               text         not null,
  train_start        date         not null,
  train_end          date         not null,
  test_start         date         not null,
  test_end           date         not null,
  initial_cash       bigint       not null,
  -- 수수료·세율은 0.00015 같은 값이고 성과 계산에서 누적 곱셈에 들어간다.
  -- float 의 이진 오차가 재현 검증을 방해할 수 있어 정확한 10진 저장을 쓴다.
  commission_rate    numeric(6,5) not null,
  sell_tax_rate      numeric(6,5) not null,
  slippage_rate      numeric(6,5) not null,
  warmup_days        smallint     not null,
  model_name         text         not null,
  strategy_stats     jsonb        not null,
  benchmark_stats    jsonb        not null,
  prediction_metrics jsonb        not null,
  price_rows         integer      not null,
  price_first        date         not null,
  price_last         date         not null,
  engine_note        text         not null,
  created_at         timestamptz  not null default now(),

  constraint ck_backtest_summary_owner
    check (user_id is not null or anon_id is not null),
  constraint ck_backtest_summary_anon_id
    check (anon_id is null or char_length(anon_id) <= 64),
  constraint ck_backtest_summary_ticker  check (char_length(ticker) <= 24),
  constraint ck_backtest_summary_name    check (char_length(name)   <= 40),
  constraint ck_backtest_summary_cash    check (initial_cash between 1000000 and 1000000000000),
  constraint ck_backtest_summary_comm    check (commission_rate between 0 and 0.02),
  constraint ck_backtest_summary_tax     check (sell_tax_rate   between 0 and 0.02),
  constraint ck_backtest_summary_slip    check (slippage_rate   between 0 and 0.02),
  constraint ck_backtest_summary_warmup  check (warmup_days between 30 and 750),
  constraint ck_backtest_summary_rows    check (price_rows >= 0)
);

-- jsonb 3개만 예외적으로 허용한다. BacktestStats 12필드 × (전략·벤치마크) +
-- PredictionMetrics 15필드를 컬럼으로 펼치면 지표 하나 추가할 때마다 마이그레이션이
-- 필요하다. F28 은 B등급이고 실험 성격이라 JSONB 로 둔다.
-- 대신 자주 정렬·필터할 지표만 생성 컬럼으로 승격한다.
alter table backtest_summary
  add column strategy_total_return_pct numeric
    generated always as ((strategy_stats->>'total_return_pct')::numeric) stored,
  add column strategy_max_drawdown_pct numeric
    generated always as ((strategy_stats->>'max_drawdown_pct')::numeric) stored;

-- rows(일별 예측)·curve(일별 자산곡선)는 저장하지 않는다. 제약 C-04.
-- 입력 11개가 남아 있으므로 재실행으로 복원한다.
comment on table backtest_summary is 'F28 워크포워드 검증 요약 (테이블-정의서 4.6)';

create index idx_backtest_summary_user_created on backtest_summary (user_id, created_at desc);
create index idx_backtest_summary_anon_created on backtest_summary (anon_id, created_at desc);
