-- app_user — 사용자 프로필.
-- 정본: docs/spec/30-데이터/테이블-정의서.md 4.1절.
--
-- Supabase Auth 의 auth.users 를 대체하지 않고 확장한다.
-- 이메일·비밀번호·세션은 전부 auth.users 가 관리한다.
-- 이메일을 복사해 두지 않는다 — auth.users.email 이 정본이고 사본은 어긋난다.

create table app_user (
  id              uuid        primary key references auth.users (id) on delete cascade,
  display_name    text        null,
  default_profile portfolio_profile null,
  created_at      timestamptz not null default now(),
  updated_at      timestamptz not null default now(),

  constraint ck_app_user_display_name check (
    display_name is null or char_length(display_name) <= 40
  )
);

comment on table  app_user is 'Supabase Auth 사용자의 화면용 프로필 확장 (테이블-정의서 4.1)';
comment on column app_user.default_profile is '마지막 추천 결과를 기본값으로 기억';

-- updated_at 은 트리거로 갱신한다 (4.1절 "트리거로 갱신").
-- search_path 를 고정하지 않으면 함수가 호출자의 search_path 를 따라가므로 명시한다.
create or replace function set_updated_at()
returns trigger
language plpgsql
set search_path = public
as $$
begin
  new.updated_at := now();
  return new;
end;
$$;

create trigger trg_app_user_updated_at
  before update on app_user
  for each row execute function set_updated_at();
