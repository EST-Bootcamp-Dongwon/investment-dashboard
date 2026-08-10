-- 로컬 개발용 표본 데이터.
-- 정본: docs/spec/30-데이터/테이블-정의서.md 5.2절.
--
-- `supabase db reset` 이 마이그레이션을 전부 적용한 뒤 이 파일을 실행한다.
-- 원격(운영) 프로젝트에는 적용하지 않는다.
--
-- auth.users 에 의존하는 행은 넣지 않는다. 로컬 스택에서 사용자를 만들려면
-- Auth API 를 거쳐야 하고, 그러면 seed 가 실행 순서에 묶인다.
-- 따라서 표본은 전부 비로그인(anon_id) 이력이다.

-- F03 추천 3건 — 세 프로필이 한 번씩 나오는 조합을 골랐다.
-- 판정 규칙은 docs/spec/20-기능명세/02-포트폴리오.md 1.4절(CN-029 점수제)이고,
-- 배분표는 app/backend/services/recommendation.py 의 PROFILES 상수와 같은 값이다.

select create_recommendation(
  null, 'seed-anon-0000000001',
  'protect', 'short', 'low', 'stable', '안정 중심 구성',
  '[
    {"sort_order": 0, "asset_name": "현금성 자산",       "weight_pct": 35, "explanation": "급한 상황이나 기회를 위한 여유 자금"},
    {"sort_order": 1, "asset_name": "채권·안정형 자산",  "weight_pct": 35, "explanation": "포트폴리오의 흔들림을 완화하는 역할"},
    {"sort_order": 2, "asset_name": "글로벌 주식",       "weight_pct": 20, "explanation": "장기 성장 기회를 위한 부분"},
    {"sort_order": 3, "asset_name": "배당·방어형 주식",  "weight_pct": 10, "explanation": "상대적으로 안정적인 현금흐름을 기대하는 부분"}
  ]'::jsonb
);

select create_recommendation(
  null, 'seed-anon-0000000002',
  'balance', 'medium', 'medium', 'balanced', '균형 중심 구성',
  '[
    {"sort_order": 0, "asset_name": "글로벌 주식",      "weight_pct": 45, "explanation": "여러 국가와 업종의 성장 기회"},
    {"sort_order": 1, "asset_name": "채권·안정형 자산", "weight_pct": 25, "explanation": "시장 변동을 완화하는 완충 역할"},
    {"sort_order": 2, "asset_name": "국내 주식",        "weight_pct": 15, "explanation": "익숙한 시장의 성장 기회"},
    {"sort_order": 3, "asset_name": "현금성 자산",      "weight_pct": 10, "explanation": "예상치 못한 지출과 추가 투자 여유"},
    {"sort_order": 4, "asset_name": "대체 자산",        "weight_pct":  5, "explanation": "금 등 다른 성격의 자산을 소량 활용"}
  ]'::jsonb
);

select create_recommendation(
  null, 'seed-anon-0000000003',
  'growth', 'long', 'high', 'growth', '성장 중심 구성',
  '[
    {"sort_order": 0, "asset_name": "글로벌 주식",      "weight_pct": 60, "explanation": "폭넓은 성장 기회를 중심으로 구성"},
    {"sort_order": 1, "asset_name": "국내 주식",        "weight_pct": 20, "explanation": "국내 시장과 관심 산업에 참여하는 부분"},
    {"sort_order": 2, "asset_name": "테마·성장 자산",   "weight_pct": 10, "explanation": "높은 변동성을 감수하는 작은 비중"},
    {"sort_order": 3, "asset_name": "채권·안정형 자산", "weight_pct":  5, "explanation": "급격한 변동에 대비하는 완충 역할"},
    {"sort_order": 4, "asset_name": "현금성 자산",      "weight_pct":  5, "explanation": "기본적인 유동성 확보"}
  ]'::jsonb
);

-- 배분 합계가 전부 100 인지 확인한다. 이 뷰가 행을 돌려주면 seed 가 잘못된 것이다.
-- select * from v_recommendation_weight_check;
