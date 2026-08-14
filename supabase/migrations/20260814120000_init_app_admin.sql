-- app_admin — 관리자 명단.
-- 정본: docs/spec/30-데이터/테이블-정의서.md 4.10절 (버전업 때 추가).
--
-- F27 색인 운영 화면이 "누가 이 버튼을 눌러도 되는가" 를 판정할 근거다.
-- 저장소 전체에 관리자 개념이 0건이었다 (2026-08-14 실측:
--   grep -rniE "ADMIN_TOKEN|ADMIN_KEY|is_admin|X-Admin|role.*admin" \
--     --include="*.py" --include="*.js" --include="*.sql" app/ supabase/ scripts/  → 0건).
--
-- ## app_user 에 role 컬럼을 더하지 않은 이유 — 권한 상승 경로가 생긴다
--
-- app_user 에는 이미 본인 UPDATE 정책이 있다:
--   create policy "본인 프로필만 수정" on app_user for update using (auth.uid() = id)
--                                                       with check (auth.uid() = id);
--   (20260810120200_init_rls.sql:29~30)
-- 여기에 role 컬럼을 얹으면 **로그인한 사용자가 anon 키로 자기 행의 role 을 'admin'
-- 으로 UPDATE 할 수 있다.** 정책은 "어느 행" 만 보고 "어느 컬럼" 은 보지 않는다.
-- 막으려면 컬럼 단위 GRANT 를 따로 걸어야 하는데, 정책과 권한 두 층이 어긋나면
-- 나중에 정책만 읽고 안전하다고 판단하게 된다.
--
-- 별도 테이블은 **정책을 하나도 만들지 않는 것**으로 닫힌다. 20260810120200_init_rls.sql:9~10
-- 이 이미 세운 관용구다 — "정책을 만들지 않은 (테이블, 명령) 조합은 anon·authenticated
-- 양쪽에서 전부 막힌다. service_role 은 RLS 를 우회하므로 '서버 경유만' 은 정책 부재로
-- 표현된다." 읽기조차 막히므로 관리자 명단 자체가 밖으로 새지 않는다.

create table app_admin (
  -- app_user 가 아니라 auth.users 를 가리킨다. app_user 행은 저장이 처음 일어날 때
  -- 비로소 만들어지는데(clients/combination_repo.py:101 의 ignore_duplicates insert),
  -- 관리자는 아직 아무것도 저장한 적 없는 계정일 수 있다.
  user_id    uuid        primary key references auth.users (id) on delete cascade,
  note       text        null,
  granted_at timestamptz not null default now(),

  constraint ck_app_admin_note check (note is null or char_length(note) <= 200)
);

comment on table  app_admin is '관리자 명단 — 색인 운영 화면 접근 판정 (테이블-정의서 4.10)';
comment on column app_admin.note is '누구에게 왜 줬는지 사람이 읽을 메모';

alter table app_admin enable row level security;

-- ★ 정책을 만들지 않는다. 정책 부재가 곧 차단이다.
--   anon·authenticated 는 조회도 못 한다. service_role 을 쥔 FastAPI 서버만 읽는다.
--
-- 첫 관리자는 SQL 로 직접 넣는다 (Supabase 대시보드 SQL Editor):
--   insert into app_admin (user_id, note)
--   select id, '최초 관리자' from auth.users where email = '<이메일>';
-- 화면에서 관리자를 임명하는 경로는 두지 않았다 — 그 화면 자체가 관리자 권한을
-- 요구하므로 최초 1명은 어차피 DB 에서 만들어야 하고, 그 뒤로도 명단 변경은
-- 드물어서 화면을 유지할 값이 없다.
