-- macro_series / macro_observation — 거시지표 참조 데이터.
-- 정본: docs/spec/30-데이터/테이블-정의서.md 4.8절 (CN-044).
--
-- 이 파일만 데이터를 함께 넣는다. macro_series 4행은 스키마가 아니라 참조 데이터이고,
-- 없으면 배치가 돌 대상이 없다.

create table macro_series (
  id             smallint    primary key generated always as identity,
  code           text        not null unique,
  name_ko        text        not null,
  source         macro_source    not null,
  source_table   text        not null,
  source_item    text        null,
  frequency      macro_frequency not null,
  unit           text        not null,
  available_from date        not null,
  is_active      boolean     not null default true,
  updated_at     timestamptz not null default now(),

  -- code 만 UNIQUE 로 두면 같은 ECOS 통계표를 내부 코드만 바꿔 두 번 등록할 수 있고,
  -- 배치가 같은 값을 두 계열에 쌓는다.
  -- 주의: source_item 이 NULL 인 행(FRED)은 Postgres 기본 동작에서 서로 중복으로
  -- 잡히지 않는다. FRED 계열이 늘어나면 nulls not distinct 가 필요하다.
  constraint uq_macro_series_source unique (source, source_table, source_item),
  constraint ck_macro_series_code   check (char_length(code)         <= 40),
  constraint ck_macro_series_name   check (char_length(name_ko)      <= 40),
  constraint ck_macro_series_table  check (char_length(source_table) <= 20),
  constraint ck_macro_series_item   check (source_item is null or char_length(source_item) <= 20),
  constraint ck_macro_series_unit   check (char_length(unit)         <= 20)
);

comment on column macro_series.available_from is
  '출처가 제공하는 최초 관측일. 우리가 적재하는 시작일(2000-01-01)이 아니다';
comment on column macro_series.updated_at is
  '마지막 배치 성공 시각. 배치가 조용히 멈추면 이 값이 늙는다 — 감시 지표';

create table macro_observation (
  series_id   smallint      not null references macro_series (id) on delete cascade,
  obs_date    date          not null,
  value       numeric(18,6) not null,
  ingested_at timestamptz   not null default now(),

  -- 1절 명명 규칙의 "기본키는 id" 를 여기서만 어긴다 — 의도한 예외다.
  -- (series_id, obs_date) 가 자연키이고, 이 테이블에 필요한 유일한 무결성 규칙이
  -- "한 지표의 한 날짜에 값은 하나" 다. 대리키를 두면 인덱스가 하나 늘 뿐이다.
  constraint pk_macro_observation primary key (series_id, obs_date)
);

-- 월·분기 지표의 obs_date 는 해당 기간의 1일로 고정한다. CPI 202607 은 2026-07-01.
-- 말일로 적으면 "7월 지표" 와 "7월 31일 값" 이 섞이고 주기가 다른 지표를 한 축에
-- 그릴 때 정렬이 틀어진다. FRED 가 이미 이 규약을 쓴다.
comment on column macro_observation.obs_date is '관측일. 월·분기 지표는 해당 기간의 1일';

-- 여러 지표를 한 날짜로 가로 조회 — F14 GBM 시작값 초기화.
-- PK 의 선두 컬럼이 series_id 라 PK 만으로는 이 질의를 못 탄다.
create index idx_macro_observation_date on macro_observation (obs_date);

-- ── 초기 4행 ────────────────────────────────────────────────────────────────
-- 통계표·항목 코드는 API 실호출로 확인한 값이다 (2026-08-10 실측,
-- docs/spec/20-기능명세/04-거시경제.md 4.2~4.3절).
--
-- KOSIS 행은 비워 둔다. CN-044 는 키가 살아 있다는 것까지만 확인했고 어느 통계표를
-- 쓸지는 정하지 않았다. macro_source enum 에 kosis 를 미리 넣어 두어 스키마 변경
-- 없이 나중에 추가된다.
insert into macro_series (code, name_ko, source, source_table, source_item, frequency, unit, available_from)
values
  ('KR_BASE_RATE', '한국은행 기준금리',      'ecos', '722Y001', '0101000', 'daily',   '연%',  '1999-05-06'),
  ('KR_USD_KRW',   '원/미국달러 매매기준율', 'ecos', '731Y001', '0000001', 'daily',   '원',   '1964-05-04'),
  ('KR_CPI',       '소비자물가지수 (총지수)', 'ecos', '901Y009', '0',       'monthly', '지수', '1965-01-01'),
  ('US_FED_FUNDS', '미국 연방기금금리',      'fred', 'FEDFUNDS', null,     'monthly', '연%',  '1954-07-01');
