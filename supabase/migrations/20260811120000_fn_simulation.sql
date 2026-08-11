-- create_simulation / list_simulation — F05 저장·조회 RPC.
-- 정본: docs/spec/30-데이터/테이블-정의서.md 4.5절.
--
-- 테이블은 20260809120400_init_simulation.sql 이 이미 만들었다. 이 파일은 그 위에
-- 저장·조회 경로만 얹는다. F03 의 create_recommendation / list_recommendation
-- (20260809120200_init_recommendation.sql) 과 같은 구조·같은 이유다.

-- ── 저장 RPC ────────────────────────────────────────────────────────────────
--
-- 왜 함수인가. PostgREST 로 실행 1행과 곡선 years+1 행을 넣으면 요청이 두 번이라
-- 트랜잭션이 갈라진다. 곡선 삽입이 실패하면 곡선 없는 고아 실행 행이 남고, 그 행은
-- 화면에 "결과 없음" 으로 보이면서 이력에는 남는 최악의 상태가 된다.
--
-- security invoker(기본)를 그대로 둔다. 서버는 service_role 키로 부르므로 RLS 를
-- 우회하고, anon 키로 직접 부르면 simulation_run 의 INSERT 정책에 막힌다.
-- 즉 "쓰기는 서버 경유만" 이 이 함수에서도 유지된다.
create or replace function create_simulation(
  p_user_id        uuid,
  p_anon_id        text,
  p_profile        portfolio_profile,
  p_profile_label  text,
  p_initial_amount bigint,
  p_monthly_amount bigint,
  p_years          smallint,
  p_total_paid     bigint,
  p_final_cautious bigint,
  p_final_middle   bigint,
  p_final_positive bigint,
  p_rng_seed       integer,
  p_paths          integer,
  p_points         jsonb
)
returns table (simulation_id bigint, created_at timestamptz)
language plpgsql
set search_path = public
as $$
declare
  v_id bigint;
  v_created_at timestamptz;
begin
  -- 로그인 사용자인데 app_user 행이 아직 없으면 FK 가 터진다.
  -- auth.users 행은 토큰 검증으로 이미 존재가 확인된 상태이므로 1:1 행을 만들어 준다.
  if p_user_id is not null then
    insert into app_user (id) values (p_user_id)
    on conflict (id) do nothing;
  end if;

  insert into simulation_run (
    user_id, anon_id, profile, profile_label,
    initial_amount, monthly_amount, years, total_paid,
    final_cautious, final_middle, final_positive, rng_seed, paths
  )
  values (
    p_user_id, p_anon_id, p_profile, p_profile_label,
    p_initial_amount, p_monthly_amount, p_years, p_total_paid,
    p_final_cautious, p_final_middle, p_final_positive, p_rng_seed, p_paths
  )
  returning simulation_run.id, simulation_run.created_at into v_id, v_created_at;

  -- 별칭이 pt 인 것은 취향이다. point 는 Postgres 기하 타입 이름이지만 예약어가 아니라
  -- `as point` 로 써도 정상 동작한다 (2026-08-11 원격 Postgres 17.6 실측).
  -- 타입과 같은 이름이 읽는 사람을 멈칫하게 해서 두 글자로 피했을 뿐, 필요해서가 아니다.
  insert into simulation_point (simulation_run_id, year, cautious, middle, positive)
  select v_id,
         (pt ->> 'year')::smallint,
         (pt ->> 'cautious')::bigint,
         (pt ->> 'middle')::bigint,
         (pt ->> 'positive')::bigint
  from jsonb_array_elements(p_points) as pt;

  return query select v_id, v_created_at;
end;
$$;

comment on function create_simulation is
  'F05 시뮬레이션 1건과 연 단위 곡선을 한 트랜잭션으로 저장한다 (테이블-정의서 4.5)';

-- ── 이력 조회 RPC ───────────────────────────────────────────────────────────
--
-- 왜 함수인가. 목록에는 곡선 대신 point_count 만 필요하다. 그 집계를 PostgREST 로
-- 하려면 자식 행을 통째로 받아 세야 하고, 30년 실행 20건이면 620행을 매번 실어
-- 나르게 된다. 함수로 감싸면 집계가 DB 안에서 끝나고 uq_simulation_point_year 의
-- 인덱스(선두 컬럼이 simulation_run_id)를 그대로 탄다.
--
-- 토큰이 있으면 user_id 기준, 없으면 anon_id 기준이다. 둘을 OR 로 합치지 않는다 —
-- 비로그인 이력이 로그인 계정에 자동 병합되면 소유 관계가 흐려진다.
create or replace function list_simulation(
  p_user_id uuid,
  p_anon_id text,
  p_limit   int default 20
)
returns table (
  simulation_id  bigint,
  profile        portfolio_profile,
  profile_label  text,
  initial_amount bigint,
  monthly_amount bigint,
  years          smallint,
  total_paid     bigint,
  final_cautious bigint,
  final_middle   bigint,
  final_positive bigint,
  point_count    bigint,
  created_at     timestamptz
)
language sql stable
set search_path = public
as $$
  select s.id, s.profile, s.profile_label, s.initial_amount, s.monthly_amount,
         s.years, s.total_paid, s.final_cautious, s.final_middle, s.final_positive,
         (select count(*) from simulation_point p where p.simulation_run_id = s.id),
         s.created_at
  from simulation_run s
  where case
          when p_user_id is not null then s.user_id = p_user_id
          else s.anon_id = p_anon_id
        end
  order by s.created_at desc
  limit least(greatest(p_limit, 1), 100);
$$;

comment on function list_simulation is
  'F05 시뮬레이션 이력 목록. 소유자 기준 하나만 쓴다 (테이블-정의서 4.5)';
