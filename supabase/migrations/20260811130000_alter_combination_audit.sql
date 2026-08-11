-- combination_query 감사 컬럼 3종 — F04 저장 경로의 전제.
-- 정본: docs/spec/30-데이터/테이블-정의서.md 4.4절 (문서 반영은 버전업 때 · CN-105).
--
-- 테이블은 20260809120300_init_combination.sql 이 이미 만들었다. 이 파일은 그 위에
-- **"이 판정은 무엇을 보고 내렸나" 를 되짚을 수 있게 하는 컬럼만** 더한다.
-- 새 테이블도, 새 인덱스도, 새 함수도 만들지 않는다.
--
-- ── 왜 필요한가 ─────────────────────────────────────────────────────────────
--
-- 4.4절은 `latest_data_at` 하나로 *"이 판정은 어느 시점 데이터였나"* 가 증거로
-- 남는다고 적었다. 저장 경로를 실제로 붙이면서 그 문장을 검사해 보니 **되짚을 수 없다.**
--
--   ① **창의 끝만 있고 시작이 없다.** `latest_data_at` 은 두 종목이 겹치는 거래일의
--      마지막 날이다(`main.py:1229`). 창의 시작은 yfinance 의 `period` 가 *호출한
--      순간* 을 기준으로 잡으므로(`main.py:1194`), `latest_data_at` 에서 역산되지
--      않는다. 3개월 뒤에 같은 `period` 로 다시 부르면 다른 창이 된다.
--   ② **관측 수가 없다.** 20거래일짜리 상관계수와 500거래일짜리 상관계수는 신뢰도가
--      전혀 다른데, 저장된 행만 봐서는 어느 쪽인지 구분되지 않는다.
--   ③ **판정의 근거가 되는 수 자체가 없다.** `signal` 은 연속값을 세 칸으로 나눈
--      결과다(`main.py:1215~1226`). 저장된 `'yellow'` 가 0.31 이었는지 0.69 였는지
--      알 수 없고, 임계값(0.30 · 0.70)을 나중에 손대는 순간 **이미 저장된 signal 은
--      전부 해석 불가**가 된다. 이력이 남았는데 무슨 뜻인지 모르는 상태다.
--
-- ①②③ 을 `observed_from` · `observation_count` · `relationship` 이 각각 메운다.
--
-- ── 그래도 chart_points 는 여전히 저장하지 않는다 ───────────────────────────
--
-- 제약 C-04 는 그대로다. 위 셋은 행당 고정 3개이지만 chart_points 는 거래일 수만큼
-- (2y 면 약 500행) 늘어난다. 되짚기에 필요한 것은 *창과 판정 근거* 이지 그림이 아니다.

alter table combination_query
  add column relationship      numeric(6,5) not null,
  add column observed_from     timestamptz  not null,
  add column observation_count integer      not null;

-- `latest_data_at` 을 NOT NULL 로 조인다. 저장 경로가 이 값을 항상 계산하고
-- (`main.py:1229` 는 분기 없이 실행된다), 없으면 위 ①②③ 을 메운 의미가 사라진다.
-- 지금 이 테이블은 **0행**이라(2026-08-11 원격 `Prefer: count=exact` 로 확인) 조여도
-- 되돌릴 데이터가 없다. 창을 나타내는 네 컬럼이 전부 NOT NULL 로 맞춰진다.
alter table combination_query
  alter column latest_data_at set not null;

alter table combination_query
  -- 피어슨 상관계수의 정의역이다. 계산이 깨지면 여기서 걸린다.
  add constraint ck_combination_query_relationship
    check (relationship between -1 and 1),
  -- services/combination.py 의 MIN_OVERLAP 과 같은 값이다(`main.py:1211`).
  -- 도메인 계층이 먼저 걸러 422 를 내므로 여기 걸리는 일은 없어야 한다 — 이것은
  -- 백스톱이다. MIN_OVERLAP 을 바꾸면 이 제약도 함께 바꿔야 한다.
  add constraint ck_combination_query_observations
    check (observation_count >= 20),
  -- 창의 시작이 끝보다 뒤일 수 없다. 같은 날일 수는 있다(단일 거래일 창).
  add constraint ck_combination_query_window
    check (observed_from <= latest_data_at);

comment on column combination_query.relationship is
  '두 종목 일간 변화율의 피어슨 상관계수. 소수점 5자리로 반올림해 저장한다 (main.py:1213)';
comment on column combination_query.observed_from is
  '상관계수를 계산한 창의 첫 거래일. latest_data_at 이 끝이고 이 값이 시작이다';
comment on column combination_query.observation_count is
  '창에 들어간 겹치는 거래일 수. 같은 signal 이라도 20일과 500일은 신뢰도가 다르다';
comment on column combination_query.latest_data_at is
  '상관계수를 계산한 창의 마지막 거래일 (main.py:1229). 값은 날짜라 시각은 자정이다';

-- ── 응답에 싣지 않는다 ──────────────────────────────────────────────────────
--
-- `relationship` 은 저장만 하고 API 응답에는 넣지 않는다. `main.py:1208` 이
-- *"화면에는 수식 대신 신호와 문장만 노출한다"* 로 정한 것을 저장 경로가 뒤집을
-- 이유가 없다. 되짚기는 **DB 를 직접 보는 사람**(운영·검증)을 위한 것이고,
-- 화면 계약은 그대로 둔다.
