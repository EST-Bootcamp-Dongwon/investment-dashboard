-- recommendation / recommendation_item — F03 포트폴리오 추천 결과.
-- 정본: docs/spec/30-데이터/테이블-정의서.md 4.2절 · 4.3절.
--
-- F03 을 백엔드화하면서 생기는 테이블이다 (CN-011 해소 · CN-039 설계).

-- ── 4.2 recommendation ──────────────────────────────────────────────────────

create table recommendation (
  id            bigint      primary key generated always as identity,
  user_id       uuid        null references app_user (id) on delete set null,
  anon_id       text        null,
  goal          invest_goal    not null,
  horizon       invest_horizon not null,
  risk          risk_appetite  not null,
  profile       portfolio_profile not null,
  profile_label text        not null,
  created_at    timestamptz not null default now(),

  -- 로그인이든 비로그인이든 소유자를 알 수 없는 행은 만들지 않는다.
  constraint ck_recommendation_owner
    check (user_id is not null or anon_id is not null),
  constraint ck_recommendation_anon_id
    check (anon_id is null or char_length(anon_id) <= 64),
  constraint ck_recommendation_profile_label
    check (char_length(profile_label) <= 40)
);

comment on table  recommendation is 'F03 추천 1건. 설문 3문항과 판정 결과 (테이블-정의서 4.2)';
comment on column recommendation.anon_id is '비로그인 브라우저 식별자. app.js visitorId() 재사용';

create index idx_recommendation_user_created on recommendation (user_id, created_at desc);
create index idx_recommendation_anon_created on recommendation (anon_id, created_at desc);

-- ── 4.3 recommendation_item ─────────────────────────────────────────────────
--
-- PROFILES[*].items (portfolioGuide.js:5~10,17~23,29~35) 를 그 시점 값으로
-- 스냅샷 저장한다. explanation 은 같은 자산이라도 프로필마다 문구가 달라
-- asset_name 만으로 복원할 수 없으므로 반드시 저장한다.
--
-- 색상(#22c55e 등)은 저장하지 않는다. items 배열의 3번째 원소이지만 UI 테마의
-- 관심사이고, 자산명 → 색상이 세 프로필에 걸쳐 모순 없는 함수라 프론트가
-- asset_name 으로 되찾을 수 있다.

create table recommendation_item (
  id                bigint   primary key generated always as identity,
  recommendation_id bigint   not null references recommendation (id) on delete cascade,
  sort_order        smallint not null,
  asset_name        text     not null,
  weight_pct        smallint not null,
  explanation       text     not null,

  constraint uq_recommendation_item_order unique (recommendation_id, sort_order),
  constraint ck_recommendation_item_weight check (weight_pct between 0 and 100),
  constraint ck_recommendation_item_sort   check (sort_order >= 0),
  constraint ck_recommendation_item_asset  check (char_length(asset_name)  <= 40),
  constraint ck_recommendation_item_expl   check (char_length(explanation) <= 200)
);

comment on table recommendation_item is 'F03 자산 배분 라인 스냅샷 (테이블-정의서 4.3)';

-- 비중 합계 100 은 행 단위 CHECK 로 보장할 수 없다. 서버 계층에서 검증한 뒤
-- 아래 create_recommendation() 한 트랜잭션으로 넣고, 이 뷰로 사후 감시한다.
-- security_invoker 를 켠다. 끄면(기본) 뷰가 소유자 권한으로 돌아 RLS 를 우회하고,
-- anon 키로 이 뷰를 읽어 남의 추천 id 를 열거할 수 있다.
create view v_recommendation_weight_check with (security_invoker = true) as
select recommendation_id, sum(weight_pct) as total
from recommendation_item
group by recommendation_id
having sum(weight_pct) <> 100;

comment on view v_recommendation_weight_check is '비중 합계가 100 이 아닌 추천을 찾는 점검용 뷰';

-- ── 저장 RPC ────────────────────────────────────────────────────────────────
--
-- 왜 함수인가. PostgREST 로 부모 1행과 자식 3~5행을 넣으면 요청이 두 번이라
-- 트랜잭션이 갈라진다. 자식 삽입이 실패하면 부모만 남은 고아 행이 생긴다.
-- 4.3절이 채택한 "한 트랜잭션 삽입" 은 함수 한 번 호출로만 성립한다.
-- 4.7절 match_doc_chunk() 가 이미 같은 이유로 RPC 를 쓴다 (SQL 을 밖에 노출하지 않음).
--
-- security invoker(기본)를 그대로 둔다. 서버는 service_role 키로 부르므로 RLS 를
-- 우회하고, anon 키로 직접 부르면 recommendation 의 INSERT 정책에 막힌다.
-- 즉 "쓰기는 서버 경유만" 이 이 함수에서도 유지된다.
create or replace function create_recommendation(
  p_user_id       uuid,
  p_anon_id       text,
  p_goal          invest_goal,
  p_horizon       invest_horizon,
  p_risk          risk_appetite,
  p_profile       portfolio_profile,
  p_profile_label text,
  p_items         jsonb
)
returns table (recommendation_id bigint, created_at timestamptz)
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

  insert into recommendation (user_id, anon_id, goal, horizon, risk, profile, profile_label)
  values (p_user_id, p_anon_id, p_goal, p_horizon, p_risk, p_profile, p_profile_label)
  returning recommendation.id, recommendation.created_at into v_id, v_created_at;

  insert into recommendation_item (recommendation_id, sort_order, asset_name, weight_pct, explanation)
  select v_id,
         (item ->> 'sort_order')::smallint,
         item ->> 'asset_name',
         (item ->> 'weight_pct')::smallint,
         item ->> 'explanation'
  from jsonb_array_elements(p_items) as item;

  return query select v_id, v_created_at;
end;
$$;

comment on function create_recommendation is
  'F03 추천 1건과 배분 라인을 한 트랜잭션으로 저장한다 (API-상세명세 2.4)';

-- ── 이력 조회 RPC ───────────────────────────────────────────────────────────
--
-- 왜 함수인가. 목록에는 배분 상세 대신 item_count 만 필요한데(API-상세명세 2.5),
-- 그 집계를 PostgREST 로 하려면 임베디드 aggregate 문법에 기대야 한다. 대신 자식
-- 행을 통째로 받아 세면 20건 × 5행 = 100행을 매번 실어 나르게 된다. 함수로 감싸면
-- 집계가 DB 안에서 끝나고, 아래 두 인덱스를 그대로 탄다.
--
-- 토큰이 있으면 user_id 기준, 없으면 anon_id 기준이다. 둘을 OR 로 합치지 않는다 —
-- 비로그인 이력이 로그인 계정에 자동 병합되면 소유 관계가 흐려진다.
create or replace function list_recommendation(
  p_user_id uuid,
  p_anon_id text,
  p_limit   int default 20
)
returns table (
  recommendation_id bigint,
  goal              invest_goal,
  horizon           invest_horizon,
  risk              risk_appetite,
  profile           portfolio_profile,
  profile_label     text,
  item_count        bigint,
  created_at        timestamptz
)
language sql stable
set search_path = public
as $$
  select r.id, r.goal, r.horizon, r.risk, r.profile, r.profile_label,
         (select count(*) from recommendation_item i where i.recommendation_id = r.id),
         r.created_at
  from recommendation r
  where case
          when p_user_id is not null then r.user_id = p_user_id
          else r.anon_id = p_anon_id
        end
  order by r.created_at desc
  limit least(greatest(p_limit, 1), 100);
$$;

comment on function list_recommendation is
  'F03 추천 이력 목록. 소유자 기준 하나만 쓴다 (API-상세명세 2.5)';
