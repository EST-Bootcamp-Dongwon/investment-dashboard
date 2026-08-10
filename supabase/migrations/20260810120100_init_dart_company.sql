-- dart_company — DART 회사 마스터.
-- 정본: docs/spec/30-데이터/테이블-정의서.md 4.9절 (CN-084 로 확정 · D-12).
--
-- 이 파일에는 데이터를 넣지 않는다. macro_series 와 달리 3,981행은 마이그레이션에
-- 넣을 크기가 아니고, 배치가 처음 돌 때 채운다 (1회 3,982건 = 한도의 19.9%).
--
-- 컬럼명은 DART 응답 필드명을 그대로 쓴다. 1절 명명 규칙(snake_case)에 이미 맞고,
-- 이름을 바꾸면 main.py:488~497 의 매핑과 API 응답 필드가 한 번 더 갈라진다.
-- 필드 정의 출처: OpenDART 개발가이드 — 기업개황 (2026-08-10 확인)
-- https://opendart.fss.or.kr/guide/detail.do?apiGrpCd=DS001&apiId=2019002

create table dart_company (
  corp_code     text        primary key,
  corp_name     text        not null,
  corp_name_eng text        null,
  stock_name    text        null,
  stock_code    text        not null,
  corp_cls      text        not null,
  -- 대표자명은 복수면 ', ' 로 이어진다 — 실측 '전영현, 노태문'
  ceo_nm        text        null,
  jurir_no      text        null,
  bizr_no       text        null,
  adres         text        null,   -- F21 지역 필터의 대상 (main.py:550)
  hm_url        text        null,
  ir_url        text        null,
  phn_no        text        null,
  fax_no        text        null,
  induty_code   text        null,
  -- DART 는 '19690113' 문자열로 준다. 적재 시 date 로 변환한다.
  est_dt        date        null,
  acc_mt        text        null,
  modify_date   date        not null,  -- corpCode.xml 변경일 — 증분 배치의 기준
  is_listed     boolean     not null default true,
  synced_at     timestamptz not null default now(),

  -- text + CHECK 를 char(n) 대신 쓴다. char(n) 은 값을 공백으로 채워
  -- '005930 ' 같은 비교 사고를 낸다.
  constraint ck_dart_company_corp_code  check (char_length(corp_code)  = 8),
  constraint ck_dart_company_stock_code check (char_length(stock_code) = 6),
  constraint ck_dart_company_corp_cls   check (corp_cls in ('Y', 'K', 'N', 'E')),
  constraint ck_dart_company_jurir_no   check (jurir_no is null or char_length(jurir_no) = 13),
  constraint ck_dart_company_bizr_no    check (bizr_no  is null or char_length(bizr_no)  = 10),
  constraint ck_dart_company_corp_name  check (char_length(corp_name)   <= 100),
  constraint ck_dart_company_induty     check (induty_code is null or char_length(induty_code) <= 10),
  constraint ck_dart_company_acc_mt     check (acc_mt is null or char_length(acc_mt) = 2)
);

comment on table  dart_company is 'DART 상장사 마스터. 배치가 하루 1회 갱신 (테이블-정의서 4.9)';
comment on column dart_company.corp_cls  is 'Y(유가)·K(코스닥)·N(코넥스)·E(기타)';
comment on column dart_company.synced_at is
  '배치가 이 행을 확인한 시각. 변경된 행만이 아니라 확인된 행 전부에 찍는다 —
   그래야 max(synced_at) 이 "배치가 마지막으로 성공한 시각" 이 된다';

-- 상장 중인 행에서만 종목코드가 유일하다.
-- 전체 UNIQUE 였다면 KRX 가 폐지 종목코드를 다른 회사에 재배정할 때 배치가 막힌다.
-- 재배정이 실제로 일어나는지는 확인하지 않았다 — 확인 전까지 막히지 않는 쪽을 고른다.
create unique index uq_dart_company_stock_code
  on dart_company (stock_code) where is_listed;

-- 회사명·주소 검색에는 인덱스를 걸지 않는다. F20·F22 는 회사명 부분일치, F21 은
-- 주소 부분일치인데 %키워드% 는 btree 를 타지 않는다. 3,981행 × 약 280 B ≈ 1.1 MB 는
-- 통째로 메모리에 올라가는 크기라 순차 스캔이 충분하다.
