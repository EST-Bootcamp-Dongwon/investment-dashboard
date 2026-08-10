-- simulation_run / simulation_point — F05 시뮬레이션.
-- 정본: docs/spec/30-데이터/테이블-정의서.md 4.5절.
-- 요청 출처 app/backend/routers/quant.py:50~55, 응답 출처 quant.py:93~101.

create table simulation_run (
  id             bigint      primary key generated always as identity,
  user_id        uuid        null references app_user (id) on delete set null,
  anon_id        text        null,
  profile        portfolio_profile not null,
  profile_label  text        not null,
  initial_amount bigint      not null,
  monthly_amount bigint      not null,
  years          smallint    not null,
  total_paid     bigint      not null,
  final_cautious bigint      not null,
  final_middle   bigint      not null,
  final_positive bigint      not null,
  rng_seed       integer     not null default 20260806,
  paths          integer     not null default 5000,
  created_at     timestamptz not null default now(),

  constraint ck_simulation_run_owner
    check (user_id is not null or anon_id is not null),
  constraint ck_simulation_run_anon_id
    check (anon_id is null or char_length(anon_id) <= 64),
  constraint ck_simulation_run_profile_label
    check (char_length(profile_label) <= 20),
  constraint ck_simulation_run_initial   check (initial_amount between 0 and 1000000000),
  constraint ck_simulation_run_monthly   check (monthly_amount between 0 and 100000000),
  constraint ck_simulation_run_years     check (years between 1 and 30),
  constraint ck_simulation_run_paid      check (total_paid >= 0),
  constraint ck_simulation_run_cautious  check (final_cautious >= 0),
  constraint ck_simulation_run_middle    check (final_middle   >= 0),
  constraint ck_simulation_run_positive  check (final_positive >= 0),

  -- p10 ≤ p50 ≤ p90 은 백분위의 정의다. 계산 오류가 DB 에 들어오는 것을 막는다.
  constraint ck_simulation_run_percentile check (final_cautious <= final_middle
                                             and final_middle  <= final_positive)
);

-- rng_seed 와 paths 를 컬럼으로 둔 이유. 지금은 코드에 하드코딩된 상수지만
-- 이 두 값이 바뀌면 같은 입력이 다른 결과를 낸다. 재현의 전제라 결과와 함께 박아 둔다.
comment on table simulation_run is 'F05 시뮬레이션 실행 1건 (테이블-정의서 4.5)';

create index idx_simulation_run_user_created on simulation_run (user_id, created_at desc);
create index idx_simulation_run_anon_created on simulation_run (anon_id, created_at desc);

create table simulation_point (
  id                bigint   primary key generated always as identity,
  simulation_run_id bigint   not null references simulation_run (id) on delete cascade,
  year              smallint not null,
  cautious          bigint   not null,
  middle            bigint   not null,
  positive          bigint   not null,

  constraint uq_simulation_point_year unique (simulation_run_id, year),
  constraint ck_simulation_point_year     check (year between 0 and 30),
  constraint ck_simulation_point_cautious check (cautious >= 0),
  constraint ck_simulation_point_middle   check (middle   >= 0),
  constraint ck_simulation_point_positive check (positive >= 0)
);

comment on column simulation_point.year is '0 = 시작 시점 (quant.py:77)';
