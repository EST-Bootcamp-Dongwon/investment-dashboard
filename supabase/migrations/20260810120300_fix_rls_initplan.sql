-- RLS 정책의 auth.uid() 를 (select auth.uid()) 로 감싼다.
-- 정본: docs/spec/30-데이터/테이블-정의서.md 6절.
--
-- 왜 고치는가. 원격 적용 직후 Supabase 성능 린터가 `auth_rls_initplan` 을 22건
-- 올렸다 (2026-08-10 get_advisors 실측). 정책 조건에 맨몸으로 쓴 auth.uid() 는
-- 플래너가 상수로 접지 못해 **행마다 다시 평가된다.** (select auth.uid()) 로 감싸면
-- InitPlan 으로 한 번만 평가되고 결과가 재사용된다.
-- 출처: https://supabase.com/docs/guides/database/postgres/row-level-security#call-functions-with-select
--
-- 판정 결과는 바뀌지 않는다. auth.uid() 는 요청 단위로 고정된 값이라 한 번 읽든
-- 행마다 읽든 같은 값이고, 이 마이그레이션은 성능만 건드린다.
--
-- 20260810120200_init_rls.sql 을 고치지 않고 새 파일로 만든다 — 5.3절 규칙.
-- 이름을 유지해야 하므로 drop/create 가 아니라 alter 로 조건만 바꾼다.
-- 공개 조회 정책 4종(using (true))은 auth 함수를 부르지 않아 대상이 아니다.

-- ── app_user ────────────────────────────────────────────────────────────────

alter policy "본인 프로필만 조회" on app_user using ((select auth.uid()) = id);
alter policy "본인 프로필만 생성" on app_user with check ((select auth.uid()) = id);
alter policy "본인 프로필만 수정" on app_user using ((select auth.uid()) = id)
                                            with check ((select auth.uid()) = id);
alter policy "본인 프로필만 삭제" on app_user using ((select auth.uid()) = id);

-- ── 이력 4종 ────────────────────────────────────────────────────────────────

alter policy "본인 추천만 조회" on recommendation using ((select auth.uid()) = user_id);
alter policy "본인 추천만 생성" on recommendation with check ((select auth.uid()) = user_id);
alter policy "본인 추천만 수정" on recommendation using ((select auth.uid()) = user_id)
                                               with check ((select auth.uid()) = user_id);
alter policy "본인 추천만 삭제" on recommendation using ((select auth.uid()) = user_id);

alter policy "본인 조합이력만 조회" on combination_query using ((select auth.uid()) = user_id);
alter policy "본인 조합이력만 생성" on combination_query with check ((select auth.uid()) = user_id);
alter policy "본인 조합이력만 수정" on combination_query using ((select auth.uid()) = user_id)
                                                    with check ((select auth.uid()) = user_id);
alter policy "본인 조합이력만 삭제" on combination_query using ((select auth.uid()) = user_id);

alter policy "본인 시뮬레이션만 조회" on simulation_run using ((select auth.uid()) = user_id);
alter policy "본인 시뮬레이션만 생성" on simulation_run with check ((select auth.uid()) = user_id);
alter policy "본인 시뮬레이션만 수정" on simulation_run using ((select auth.uid()) = user_id)
                                                   with check ((select auth.uid()) = user_id);
alter policy "본인 시뮬레이션만 삭제" on simulation_run using ((select auth.uid()) = user_id);

alter policy "본인 백테스트만 조회" on backtest_summary using ((select auth.uid()) = user_id);
alter policy "본인 백테스트만 생성" on backtest_summary with check ((select auth.uid()) = user_id);
alter policy "본인 백테스트만 수정" on backtest_summary using ((select auth.uid()) = user_id)
                                                   with check ((select auth.uid()) = user_id);
alter policy "본인 백테스트만 삭제" on backtest_summary using ((select auth.uid()) = user_id);

-- ── 자식 2종 ────────────────────────────────────────────────────────────────

alter policy "부모가 보이는 배분만 조회" on recommendation_item using (
  exists (
    select 1 from recommendation r
    where r.id = recommendation_item.recommendation_id
      and (select auth.uid()) = r.user_id
  )
);

alter policy "부모가 보이는 시점만 조회" on simulation_point using (
  exists (
    select 1 from simulation_run s
    where s.id = simulation_point.simulation_run_id
      and (select auth.uid()) = s.user_id
  )
);
