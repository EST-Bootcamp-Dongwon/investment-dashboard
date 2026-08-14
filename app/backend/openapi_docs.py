"""OpenAPI metadata used by the interactive Swagger UI.

Keeping this separately from the route handlers makes the API guide readable
without changing the response payloads consumed by the frontend.
"""

from __future__ import annotations

from fastapi.openapi.utils import get_openapi


TAG_DESCRIPTIONS = [
    {"name": "시스템", "description": "서비스 상태와 접속 현황 조회 API입니다."},
    {"name": "DART·기업", "description": "OpenDART 공시와 시장 데이터로 기업을 찾고 재무를 분석합니다. DART 키가 필요한 API는 키가 없으면 503을 반환합니다."},
    {"name": "산업·시장", "description": "산업 경쟁 구조와 실시간 시장·거시 지표를 분석하거나 시뮬레이션합니다."},
    {"name": "추천", "description": "설문 3문항으로 학습용 자산배분 예시를 판정하고, 그 결과를 저장·재현합니다. 개인별 투자 조언이 아니며 특정 상품을 지목하지 않습니다."},
    {"name": "퀀트", "description": "교육 목적의 백테스트, 포트폴리오, 리스크 및 분석 파이프라인 API입니다. 투자 권유나 실제 주문 기능은 제공하지 않습니다."},
    {"name": "머신러닝", "description": "합성 데이터 기반의 ML/DL·NLP 실습 결과와 시각화 데이터를 반환합니다."},
    {"name": "세무", "description": "거래내역 파일을 읽고 교육용 세금·회계 시뮬레이션을 수행합니다. 실제 신고 금액으로 사용하면 안 됩니다."},
    {"name": "RAG", "description": "Supabase pgvector에 색인된 학습 문서의 유사도 검색 API입니다. 기본 답변은 검색 문서만 정리하며, 선택적으로 외부 AI가 같은 검색 원문만 문장 다듬기에 사용합니다. 답변은 교육용이며 개인별 투자 조언이 아닙니다."},
    {"name": "관리자", "description": "학습 문서 색인을 운영합니다. `app_admin`에 등록된 계정의 액세스 토큰이 필요하며, 명단을 확인할 수 없으면 통과시키지 않고 503을 반환합니다."},
    {"name": "파일", "description": "서버가 생성한 실습 산출물을 내려받습니다."},
]

# Swagger UI는 외부 개발자용 전체 서버 기능 목록이 아니라, 이 웹앱 화면이
# 실제 호출하는 API만 안내합니다. 운영·관리 스크립트용 또는 아직 화면에 연결되지
# 않은 엔드포인트는 서버에 유지하되 OpenAPI 문서에서는 노출하지 않습니다.
FRONTEND_API_PATHS = frozenset({
    "/api/health",
    "/api/system/resources",
    "/api/visitors/heartbeat",
    "/api/recommendation/preview",
    "/api/recommendation/create",
    "/api/recommendation/history",
    "/api/recommendation/detail",
    "/api/rag/ask",
    "/api/rag/status",
    "/api/admin/rag/documents",
    "/api/admin/rag/reindex",
    "/api/admin/rag/documents/{source_doc}",
    "/api/dart/company-search",
    "/api/dart/group-network",
    "/api/dart/company-list",
    "/api/dart/financial-analysis",
    "/api/finance/company-financials",
    "/api/industry/porter",
    "/api/industry/sector",
    "/api/industry/peer",
    "/api/industry/lifecycle",
    "/api/market/snapshot",
    "/api/market/volume-cloud",
    "/api/macro/realtime",
    "/api/macro/kospi-ex",
    "/api/macro/kospi-ex/meta",
    "/api/macro/simulation",
    "/api/home/market-candle",
    "/api/quant/backtest",
    "/api/quant/portfolio",
    "/api/quant/risk",
    "/api/quant/pipeline",
    "/api/ml/cross-validation",
    "/api/ml/decision-boundary",
    "/api/ml/random-forest",
    "/api/cv/circle-animation",
    "/api/ml/kmeans",
    "/api/ml/svm",
    "/api/ml/mlp",
    "/api/ml/linear-regression",
    "/api/nlp/text-classify",
    "/api/genai/text-to-image",
    "/api/dl/cnn-timeseries",
    "/api/dl/lstm-predictor",
    "/api/dl/transformer-timeseries",
    "/files/{file_name}",
    "/api/tax/upload",
    "/api/tax/sample",
    "/api/tax/simulate",
    "/api/backtest-lab/config",
    "/api/backtest-lab/run",
    "/api/backtest-lab/report",
})


# (tag, Korean title, implementation/response contract).  Request models already
# expose type, defaults and validation limits; these notes explain why to call
# each endpoint and how to interpret its returned data.
OPERATION_DOCS: dict[str, tuple[str, str, str]] = {
    "/api/health": ("시스템", "서비스 상태 확인", "서버가 요청을 처리할 수 있는지 확인합니다. `status: ok`면 정상입니다."),
    "/api/system/resources": ("시스템", "서버 리소스 사용량", "서버의 CPU, 메모리, 루트 디스크 사용률과 바이트 단위 사용량을 반환합니다. 운영 상태를 살피는 용도이며 컨테이너·호스트 환경에 따라 관측 범위가 달라질 수 있습니다."),
    "/api/visitors/heartbeat": ("시스템", "활성 브라우저 하트비트", "익명 브라우저 식별자를 갱신하고 최근 90초 안에 신호를 보낸 활성 브라우저 수를 반환합니다. 분석용 방문 이력을 저장하지 않습니다."),
    "/api/recommendation/preview": ("추천", "포트폴리오 추천 미리보기", "투자 목적·기간·하락 반응 3문항으로 안정/균형/성장 중 하나를 판정하고, 그 프로필의 자산 배분(자산명·비중·역할 설명)과 유의사항을 반환합니다. 저장하지 않으므로 DB 상태와 무관하게 동작합니다. 비중 합계는 항상 100입니다. 색상은 반환하지 않으며 화면이 자산명으로 매핑합니다."),
    "/api/recommendation/create": ("추천", "포트폴리오 추천 저장", "`preview`와 같은 판정을 수행한 뒤 결과를 이력에 남기고 `recommendation_id`와 저장 시각(ISO 8601 UTC)을 함께 반환합니다. 추천 1건과 배분 라인이 한 트랜잭션으로 저장됩니다. 로그인 토큰이 없으면 브라우저 식별자 `anon_id`가 필요하며, 둘 다 없으면 400입니다. 저장에 실패하면 503이며 결과를 200으로 돌려주지 않습니다."),
    "/api/recommendation/history": ("추천", "내 추천 이력 목록", "최근 추천을 저장 시각 내림차순으로 반환합니다. 토큰이 있으면 로그인 사용자 기준, 없으면 `anon_id` 기준이며 두 기준을 합치지 않습니다(`owner_type`으로 무엇을 썼는지 알려줍니다). 배분 상세는 담지 않고 개수(`item_count`)만 주므로, 상세는 `detail`로 조회합니다. 결과 0건은 오류가 아니라 빈 목록입니다."),
    "/api/recommendation/detail": ("추천", "추천 단건 재현", "저장된 스냅샷을 `create`와 완전히 같은 형태로 되살립니다. `items[].explanation`은 저장 당시의 문구지만 `badge`·`intro`·`note`는 저장 컬럼이 없어 현재 서버 상수에서 다시 꺼낸 값입니다. `total_weight_pct`는 저장된 행의 실제 합이라 100이 아닐 수 있습니다. 남의 추천이면 403, 없는 id면 404입니다."),
    "/api/dart/company-search": ("DART·기업", "DART 기업명 검색", "회사명 일부를 기준으로 DART 기업코드 목록을 검색합니다. 결과의 `corp_code`는 재무분석 요청에 사용합니다."),
    "/api/dart/group-network": ("DART·기업", "그룹사 관계망 조회", "그룹명으로 DART 기업을 찾아 관계망 표현에 사용할 기업 목록과 연결 정보를 반환합니다."),
    "/api/dart/company-list": ("DART·기업", "지역·고용조건 기업 검색", "본사 지역, 임직원 수 범위, 사업연도 조건으로 DART 기업을 조회합니다. 외부 공시 데이터 상태에 따라 일부 정보가 비어 있을 수 있습니다."),
    "/api/dart/financial-analysis": ("DART·기업", "DART 재무제표 분석", "DART 고유번호와 보고서 코드를 사용해 핵심 재무 항목, 비율 및 차트를 계산합니다. `corp_code`는 8자리여야 합니다."),
    "/api/finance/company-financials": ("DART·기업", "상장사 재무정보 조회", "Yahoo Finance 기준 종목의 손익·재무상태·현금흐름 데이터를 연간 또는 분기별로 정리합니다. 지원되지 않는 티커 또는 공급자 오류는 502/404가 될 수 있습니다."),
    "/api/industry/porter": ("산업·시장", "포터의 5가지 경쟁요인 분석", "산업명과 5개 경쟁요인 점수(0~10)를 받아 레이더 차트와 해석에 사용할 데이터를 반환합니다. 점수는 서버에서 0~10 범위로 보정됩니다."),
    "/api/industry/sector": ("산업·시장", "섹터 수익률 비교", "ETF/지수 티커와 기간을 기준으로 수익률 비교 데이터를 조회하고 시각화 이미지를 반환합니다."),
    "/api/industry/peer": ("산업·시장", "동종기업 비교", "표시명과 티커의 매핑을 받아 경쟁사 가격·수익률 비교 결과를 반환합니다."),
    "/api/industry/lifecycle": ("산업·시장", "산업 수명주기 분석", "산업명과 도입기·성장기·성숙기·쇠퇴기 중 하나를 입력하면 특성, 전략과 차트를 반환합니다."),
    "/api/market/snapshot": ("산업·시장", "시장 스냅샷", "지정한 지수·환율 티커의 최신 가격, 변동률과 조회 시각을 반환합니다. 시장이 닫혀 있으면 마지막 거래 기준일 수 있습니다."),
    "/api/market/volume-cloud": ("산업·시장", "거래량 클라우드", "미국 또는 한국 대표 종목의 최근 거래량, 20거래일 평균 대비 거래량, 가격과 전일 대비를 반환합니다. 시장마다 거래량 단위가 달라 국가별로 분리해 해석해야 합니다."),
    "/api/macro/realtime": ("산업·시장", "거시지표 시계열 조회", "금리·원유·주가지수 등 티커의 지정 기간 시계열과 비교 차트를 반환합니다. 외부 시세 공급자 지연이 반영될 수 있습니다."),
    "/api/macro/kospi-ex": ("산업·시장", "제외 종목 KOSPI 분석", "제외할 종목·섹터와 기간을 입력하면 남은 구성종목 기반 KOSPI 비교 분석 결과를 반환합니다."),
    "/api/macro/kospi-ex/meta": ("산업·시장", "KOSPI 제외 분석 메타데이터", "제외 분석 UI에 필요한 사용 가능 섹터와 구성종목·가중치를 반환합니다."),
    "/api/macro/simulation": ("산업·시장", "거시경제 GBM 시뮬레이션", "난수 시드와 거래일 수를 바탕으로 교육용 거시 시계열을 생성합니다. 같은 시드를 사용하면 같은 결과를 재현할 수 있습니다."),
    "/api/home/market-candle": ("산업·시장", "홈 화면 시장 캔들", "홈 대시보드에 표시할 대표 시장의 OHLCV 캔들 데이터를 반환합니다."),
    "/api/home/kospi-candle": ("산업·시장", "KOSPI 캔들", "KOSPI 지수의 홈 화면용 OHLCV 캔들 데이터를 반환합니다."),
    "/api/home/box-range": ("산업·시장", "가격 박스권 데이터", "홈 화면 기술적 분석 예시에 사용할 가격 범위·OHLCV·현재 위치 데이터를 반환합니다. 실제 매매 신호가 아닙니다."),
    "/api/backtest-lab/config": ("퀀트", "백테스트 실험실 기본값", "실험 화면이 처음 뜰 때 쓰는 종목 프리셋, 기본 구간·비용, 오늘 날짜를 반환합니다. `available: false`면 예측 모듈을 불러오지 못한 상태이고 `import_error`에 원인이 담깁니다."),
    "/api/backtest-lab/run": ("퀀트", "워크포워드 예측 검증", "학습 구간으로 모델을 적합해 검증 구간을 out-of-sample 로 예측하고, 예측 정확도(방향 적중률·MAE·랜덤워크 대비 R²)와 그 신호로 매매했을 때의 성과를 함께 반환합니다. 검증 구간은 학습 구간보다 뒤이면서 오늘 이전이어야 하며, 아니면 400을 반환합니다. 성과는 벡터화 근사치이고 정본은 LEAN 엔진 실행 결과입니다."),
    "/api/backtest-lab/report": ("퀀트", "검증 리포트 HTML 생성", "`/api/backtest-lab/run`과 같은 계산을 수행한 뒤 결과를 자체완결 HTML 리포트로 만들어 본문째 반환합니다. 외부 리소스를 참조하지 않으므로 파일 하나만으로 열립니다. 서버의 `app/generated/backtest-lab/`에도 사본을 남깁니다."),
    "/api/quant/backtest": ("퀀트", "이동평균 전략 백테스트", "합성 가격 시계열에서 단기·장기 이동평균 교차 전략을 실행합니다. 수익률, Sharpe, MDD, 거래 수와 base64 차트를 반환하며 실투자 성과를 보장하지 않습니다."),
    "/api/quant/portfolio": ("퀀트", "몬테카를로 포트폴리오", "무작위 비중 포트폴리오를 생성해 수익률·변동성·Sharpe 기준의 효율적 조합과 차트를 반환합니다."),
    "/api/quant/financial-knowledge": ("퀀트", "금융지식 포트폴리오 실습", "학습 초점에 맞춘 자산배분·상품 설명과 몬테카를로 결과를 반환합니다."),
    "/api/quant/risk": ("퀀트", "포트폴리오 리스크 시뮬레이션", "신뢰수준과 시나리오 수를 사용해 VaR·CVaR 등 손실 위험을 교육용 난수 시뮬레이션으로 계산합니다."),
    "/api/quant/pipeline": ("퀀트", "퀀트 분석 파이프라인", "티커와 이동평균 기간을 받아 가격 조회부터 신호·성과 계산까지의 간단한 분석 흐름을 실행합니다."),
    "/api/ml/cross-validation": ("머신러닝", "교차검증 실습", "합성 분류 데이터를 만들고 로지스틱 회귀의 폴드별 정확도, 평균과 표준편차를 반환합니다."),
    "/api/ml/decision-boundary": ("머신러닝", "결정경계 시각화", "고정 합성 데이터로 학습한 분류기의 결정경계를 PNG base64 문자열로 반환합니다."),
    "/api/ml/random-forest": ("머신러닝", "랜덤포레스트 분류 실습", "예제 이탈 데이터로 랜덤포레스트를 학습하고 정확도와 클래스별 정밀도·재현율 보고서를 반환합니다."),
    "/api/cv/circle-animation": ("머신러닝", "OpenCV 원 애니메이션 생성", "해상도와 FPS로 원 애니메이션 MP4를 생성합니다. 응답의 `video_url`을 `GET /files/{file_name}`으로 요청해 내려받을 수 있습니다."),
    "/api/ml/kmeans": ("머신러닝", "K-Means 군집화 실습", "합성 군집 데이터의 레이블, 중심점, 실루엣 점수와 엘보 데이터를 반환하고 시각화 이미지를 포함합니다."),
    "/api/ml/svm": ("머신러닝", "SVM 분류 실습", "커널과 규제계수 C로 SVM을 학습해 정확도·예측 결과·결정경계 이미지를 반환합니다."),
    "/api/ml/mlp": ("머신러닝", "다층퍼셉트론 실습", "은닉층 구성과 반복 횟수로 MLP 분류기를 학습해 손실 곡선 및 평가 지표를 반환합니다."),
    "/api/ml/linear-regression": ("머신러닝", "다항 선형회귀 실습", "다항 차수, 표본 수와 노이즈로 합성 데이터를 만들고 회귀 계수·오차·시각화 결과를 반환합니다."),
    "/api/nlp/text-classify": ("머신러닝", "텍스트 분류 실습", "입력 문장에 TF-IDF 기반 예제 분류기를 적용하여 예측 레이블과 확률을 반환합니다."),
    "/api/genai/text-to-image": ("머신러닝", "텍스트-이미지 생성", "프롬프트와 이미지 크기를 받아 Diffusers 모델로 이미지를 생성합니다. 모델 다운로드·GPU 상태에 따라 오래 걸리거나 503/500이 발생할 수 있습니다."),
    "/api/dl/cnn-timeseries": ("머신러닝", "CNN 시계열 예측 실습", "입력 창, 표본 수와 에폭으로 합성 시계열 CNN을 학습하고 평가 지표·예측 차트를 반환합니다."),
    "/api/dl/lstm-predictor": ("머신러닝", "LSTM 시계열 예측 실습", "LSTM 은닉 유닛과 시퀀스 길이로 합성 시계열 예측기를 학습해 예측 결과를 반환합니다."),
    "/api/dl/transformer-timeseries": ("머신러닝", "Transformer 시계열 예측 실습", "인코더 길이·예측 구간·d_model·에폭을 사용해 Transformer 시계열 실습 결과를 반환합니다."),
    "/files/{file_name}": ("파일", "생성 파일 다운로드", "서버가 `app/generated`에 생성한 파일을 제공합니다. 허용되지 않거나 존재하지 않는 파일명은 404입니다."),
    "/api/tax/upload": ("세무", "거래내역 파일 업로드", "CSV 또는 Excel 은행거래 파일을 multipart/form-data `file`로 업로드하면 컬럼을 추정해 표준 거래내역으로 변환합니다. 최대 500건을 반환합니다."),
    "/api/tax/sample": ("세무", "세무 시뮬레이션 예제 거래", "세무 시뮬레이션을 시험할 수 있도록 재현 가능한 가상 거래내역을 반환합니다."),
    "/api/tax/simulate": ("세무", "세금·회계 시뮬레이션", "거래내역을 수입·비용으로 분류하고 소득세/법인세, 부가세 및 월별 집계를 계산합니다. 교육용 단순화 계산이므로 실제 세무 신고에 사용하면 안 됩니다."),
    "/api/rag/ask": ("RAG", "관련 학습 문서 찾기", "질문을 해시 임베딩(384차원)으로 바꿔 Supabase pgvector에서 관련 청크를 찾고, 검색된 원문만 정리해 답변합니다. `provider=openai_compatible`을 선택하면 설정된 외부 AI가 같은 원문만 문장 다듬기에 사용합니다. 근거가 0건이면 외부 AI를 부르지 않습니다. 응답에는 교육용이며 개인별 투자 조언이 아니라는 `disclaimer`가 항상 함께 나갑니다. 응답의 `followups`에는 검색된 원문의 제목·질문문장에서 규칙으로 뽑은 확인 질문이 최대 3개 실립니다. 질의와 어휘가 겹치는 것만 고르므로 겹치는 것이 없으면 빈 배열이고, 외부 AI 사용 여부와 무관하게 같은 규칙으로 계산됩니다. 색인이 비어 있으면 503입니다."),
    "/api/rag/status": ("RAG", "문서 저장소 상태", "Supabase pgvector 연결 여부, 색인 여부, 총 청크 수, 문서별 색인 현황을 반환합니다. 저장소가 죽어도 200으로 상태를 알립니다."),
    "/api/admin/rag/documents": ("관리자", "문서 색인 현황", "저장소의 `docs/*.md`와 DB 색인을 대조해 문서별 상태(indexed·missing·orphan)를 반환합니다. `app_admin`에 등록된 계정만 사용할 수 있습니다."),
    "/api/admin/rag/reindex": ("관리자", "문서 재색인", "문서를 다시 잘라 임베딩하고 색인을 갈아 끼웁니다. `source_doc`을 주면 그 문서만, 비우면 전부입니다. 문서 단위로 지우고 다시 넣으므로 짧아진 문서의 옛 청크가 남지 않습니다."),
    "/api/admin/rag/documents/{source_doc}": ("관리자", "문서 색인 삭제", "색인에서 문서 한 편을 지웁니다. 저장소의 문서 파일은 지우지 않습니다. 파일이 없어진 뒤 남은 색인(orphan)을 정리하는 용도입니다."),
}


def install_openapi(app) -> None:
    """Install a cached OpenAPI factory after all routers have been registered."""
    def custom_openapi():
        if app.openapi_schema:
            return app.openapi_schema

        schema = get_openapi(
            title="Investment Analysis Learning API",
            version="2.0.0",
            summary="투자·금융 학습용 API",
            description=(
                "## 사용 안내\n\n"
                "투자 분석과 AI/데이터 실습을 위한 교육용 API입니다. 모든 시간·시세 데이터는 외부 공급자 상태에 따라 지연되거나 달라질 수 있으며, "
                "분석 결과는 투자·세무 의사결정의 근거가 아닙니다.\n\n"
                "### 공통 규칙\n\n"
                "- 요청 본문의 필수 여부, 기본값, 범위와 정규식은 각 Schema에서 확인합니다.\n"
                "- 검증에 실패하면 `422`와 필드별 오류가 반환됩니다. 외부 데이터·저장소 의존 API는 연결 실패 시 주로 `502` 또는 `503`을 반환합니다.\n"
                "- 차트는 `data:image/png;base64,...` 또는 base64 문자열로 반환될 수 있습니다. 프런트엔드에서는 이미지 `src`에 그대로 넣어 표시합니다.\n"
                "- 별도 인증은 현재 요구되지 않습니다."
            ),
            routes=app.routes,
            tags=TAG_DESCRIPTIONS,
        )
        schema["paths"] = {
            path: operations
            for path, operations in schema.get("paths", {}).items()
            if path in FRONTEND_API_PATHS
        }
        for path, operations in schema.get("paths", {}).items():
            metadata = OPERATION_DOCS.get(path)
            if not metadata:
                continue
            tag, summary, description = metadata
            for method, operation in operations.items():
                if method not in {"get", "post", "put", "patch", "delete"}:
                    continue
                operation["tags"] = [tag]
                operation["summary"] = summary
                operation["description"] = description + "\n\n**공통 오류:** 요청값 검증 실패 시 `422`입니다."
                operation.setdefault("responses", {}).setdefault(
                    "503", {"description": "필요한 외부 서비스 또는 서버 설정을 사용할 수 없습니다."}
                )
        used_tags = {
            tag
            for operations in schema["paths"].values()
            for operation in operations.values()
            for tag in operation.get("tags", [])
        }
        schema["tags"] = [tag for tag in TAG_DESCRIPTIONS if tag["name"] in used_tags]
        app.openapi_schema = schema
        return app.openapi_schema

    app.openapi = custom_openapi
