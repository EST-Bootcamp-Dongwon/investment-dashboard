-- 공용 타입과 확장.
-- 정본: docs/spec/30-데이터/테이블-정의서.md 2절(공용 타입) · 3절(확장).
--
-- 이 파일이 가장 먼저 적용되어야 한다. 뒤의 모든 테이블이 여기 enum 을 참조한다.

-- ── 3절 확장 ────────────────────────────────────────────────────────────────
-- pgvector. doc_chunk 의 embedding 컬럼이 쓴다.
-- 출처: https://supabase.com/docs/guides/ai/vector-columns (2026-08-09 확인)
create extension if not exists vector with schema extensions;

-- ── 2절 공용 타입 ───────────────────────────────────────────────────────────

-- 투자 성향 프로필. F03(추천 결과)과 F05(시뮬레이션 입력)가 같은 어휘를 쓴다.
--   F03: app/frontend/js/views/portfolioGuide.js:2,13,25
--   F05: app/backend/routers/quant.py:67~69, 검증 패턴 quant.py:51
create type portfolio_profile as enum ('stable', 'balanced', 'growth');

-- F03 설문 3문항. 값은 portfolioGuide.js:95~97 의 <option value> 실측이다.
--
-- 주의: invest_goal 의 'balance' 는 오타가 아니다. 프로필 쪽(portfolio_profile)은
-- 'balanced' 이고 두 어휘가 실제로 다르다. 통일하려면 프론트 <option value> 를
-- 먼저 고쳐야 하며 그건 스펙 변경이라 CN-022 로 올라가 있다.
create type invest_goal    as enum ('growth', 'balance', 'protect');
create type invest_horizon as enum ('short', 'medium', 'long');
create type risk_appetite  as enum ('low', 'medium', 'high');

-- F04 비교 기간. 검증 패턴 app/backend/main.py:1106
create type combination_period as enum ('3mo', '6mo', '1y', '2y');

-- 거시지표 출처·주기. macro_series 가 쓴다 (CN-044).
--   kosis 는 통계표가 아직 미정이지만, 나중에 ALTER TYPE 을 하지 않으려고 미리 넣는다.
create type macro_source    as enum ('ecos', 'kosis', 'fred');
create type macro_frequency as enum ('daily', 'monthly', 'quarterly', 'annual');
