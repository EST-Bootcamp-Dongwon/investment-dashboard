-- RLS (행 수준 보안) 정책 일괄.
-- 정본: docs/spec/30-데이터/테이블-정의서.md 6절.
--
-- ★ 이 파일은 반드시 마지막이다. 모든 테이블이 존재한 뒤에 정책을 걸어야 한다.
--
-- Supabase 는 RLS 를 켜지 않으면 anon 키로 테이블 전체가 읽힌다. 공개 배포(CN-019)가
-- 전제이므로 필수다.
--
-- 정책을 만들지 않은 (테이블, 명령) 조합은 anon·authenticated 양쪽에서 전부 막힌다.
-- service_role 은 RLS 를 우회하므로 "서버 경유만" · "배치만" 은 정책 부재로 표현된다.

alter table app_user            enable row level security;
alter table recommendation      enable row level security;
alter table recommendation_item enable row level security;
alter table combination_query   enable row level security;
alter table simulation_run      enable row level security;
alter table simulation_point    enable row level security;
alter table backtest_summary    enable row level security;
alter table doc_chunk           enable row level security;
alter table macro_series        enable row level security;
alter table macro_observation   enable row level security;
alter table dart_company        enable row level security;

-- ── app_user — 전부 본인만 ──────────────────────────────────────────────────

create policy "본인 프로필만 조회" on app_user for select using (auth.uid() = id);
create policy "본인 프로필만 생성" on app_user for insert with check (auth.uid() = id);
create policy "본인 프로필만 수정" on app_user for update using (auth.uid() = id)
                                                    with check (auth.uid() = id);
create policy "본인 프로필만 삭제" on app_user for delete using (auth.uid() = id);

-- ── 이력 4종 — 본인 행만 ────────────────────────────────────────────────────
--
-- 비로그인 이력(anon_id)은 여기서 막지 못한다. anon_id 는 브라우저가 보내는 값이라
-- 정책 조건으로 쓰면 아무나 남의 anon_id 를 넣어 조회할 수 있다. 6.2절이 정면으로
-- 인정한 한계이고, 대응은 "FastAPI 서버가 service_role 키로 대신 조회한다" 이다.

create policy "본인 추천만 조회" on recommendation for select using (auth.uid() = user_id);
create policy "본인 추천만 생성" on recommendation for insert with check (auth.uid() = user_id);
create policy "본인 추천만 수정" on recommendation for update using (auth.uid() = user_id)
                                                       with check (auth.uid() = user_id);
create policy "본인 추천만 삭제" on recommendation for delete using (auth.uid() = user_id);

create policy "본인 조합이력만 조회" on combination_query for select using (auth.uid() = user_id);
create policy "본인 조합이력만 생성" on combination_query for insert with check (auth.uid() = user_id);
create policy "본인 조합이력만 수정" on combination_query for update using (auth.uid() = user_id)
                                                            with check (auth.uid() = user_id);
create policy "본인 조합이력만 삭제" on combination_query for delete using (auth.uid() = user_id);

create policy "본인 시뮬레이션만 조회" on simulation_run for select using (auth.uid() = user_id);
create policy "본인 시뮬레이션만 생성" on simulation_run for insert with check (auth.uid() = user_id);
create policy "본인 시뮬레이션만 수정" on simulation_run for update using (auth.uid() = user_id)
                                                           with check (auth.uid() = user_id);
create policy "본인 시뮬레이션만 삭제" on simulation_run for delete using (auth.uid() = user_id);

create policy "본인 백테스트만 조회" on backtest_summary for select using (auth.uid() = user_id);
create policy "본인 백테스트만 생성" on backtest_summary for insert with check (auth.uid() = user_id);
create policy "본인 백테스트만 수정" on backtest_summary for update using (auth.uid() = user_id)
                                                           with check (auth.uid() = user_id);
create policy "본인 백테스트만 삭제" on backtest_summary for delete using (auth.uid() = user_id);

-- ── 자식 2종 — 부모 행이 보이면 보인다. 쓰기는 서버 경유만 ──────────────────

create policy "부모가 보이는 배분만 조회" on recommendation_item for select using (
  exists (
    select 1 from recommendation r
    where r.id = recommendation_item.recommendation_id
      and auth.uid() = r.user_id
  )
);

create policy "부모가 보이는 시점만 조회" on simulation_point for select using (
  exists (
    select 1 from simulation_run s
    where s.id = simulation_point.simulation_run_id
      and auth.uid() = s.user_id
  )
);

-- ── 참조 데이터 3종 — 누구나 SELECT · 쓰기는 서버·배치 경유만 ────────────────
--
-- 사용자 데이터가 아니라 공개 통계·문서·공시정보이고 숨겨서 얻을 것이 없다.
-- dart_company 의 bizr_no·adres·phn_no 까지 DART 기업개황에서 누구나 조회할 수 있는
-- 법인 공시정보이고 개인정보가 아니다 (4.9절).

create policy "문서 청크 공개 조회"   on doc_chunk         for select using (true);
create policy "거시지표 공개 조회"     on macro_series      for select using (true);
create policy "거시관측치 공개 조회"   on macro_observation for select using (true);
create policy "회사 마스터 공개 조회" on dart_company      for select using (true);
