"""F04 포트폴리오 조합 API — Controller.

`POST /api/market/portfolio-combination`(`main.py:1173`)은 판정을 내려 보여 주기만
하고 **남기지 않는다.** 같은 두 종목을 한 달 뒤에 다시 물으면 지난번에 뭐라고
나왔는지 알 길이 없다. 이 라우터가 그 저장 경로를 낸다.

**F03 · F05 에 이어 3계층을 세 번째로 적용한 대상이다** (아키텍처 3절 ④ · CN-039).
이 파일은 경로 선언 · 요청 검증 · **도메인 예외를 HTTP 코드로 번역**하는 일만 한다.
판정과 상수는 `services/combination.py`, 시세는 `clients/yahoo_prices.py`,
DB 접근은 `clients/combination_repo.py` 에 있다.

**기존 `main.py` 엔드포인트를 대체하지 않는다.** 화면(`api.js:57` →
`portfolioCombination.js`)이 지금 그것을 부르고 있고, 저장 기능을 붙이면서 동작하던
화면이 나빠질 이유가 없다.

## 앞의 둘과 다른 점 두 가지

**① `detail` 이 `create` 를 완전히 되살리지 못한다.** `chart_points` 를 저장하지
않기로 했기 때문이다(제약 C-04). F05 는 *"되살릴 수 없는 값이 없다"* 였는데 F04 는
아니다. 그림을 지금 다시 그려서 채우지 않는다 — 그러면 **저장된 판정에 다른 창의
그림**이 붙어, 사용자는 그 그림을 보고 그 판정이 내려졌다고 읽는다.
차이는 숨기지 않고 필드를 빼서 드러낸다.

**② `latest_data_at` 하나로는 되짚을 수 없었다.** 테이블-정의서 4.4절은 그 컬럼
하나면 *"이 판정은 어느 시점 데이터였나"* 가 증거로 남는다고 적었지만, 저장 경로를
붙이면서 보니 창의 **끝**만 있고 **시작·관측 수·상관계수 자체**가 없다. 셋을
컬럼으로 더했다(마이그레이션 20260811130000). 다만 **응답에는 싣지 않는다** —
`main.py:1208` 이 정한 "화면에는 수식 대신 신호와 문장만" 을 저장 경로가 뒤집지 않는다.

설계 정본: docs/spec/30-데이터/테이블-정의서.md 4.4절.
"""

from __future__ import annotations

from fastapi import APIRouter, Header, HTTPException, Query
from pydantic import BaseModel, Field

try:
    from ..clients import combination_repo, supabase_client
    from ..services import combination as service
    from . import owner
except ImportError:  # `uvicorn main:app` 를 app/backend 에서 실행하는 경우
    from clients import combination_repo, supabase_client  # type: ignore
    from routers import owner  # type: ignore
    from services import combination as service  # type: ignore

router = APIRouter(prefix="/api/combination", tags=["조합"])

_SAVE_FAILED = "조합 판정을 저장할 수 없습니다. 잠시 후 다시 시도해 주세요."
_READ_FAILED = "조합 조회 이력을 불러올 수 없습니다. 잠시 후 다시 시도해 주세요."
_CALC_BROKEN = "조합 판정 결과가 올바르지 않습니다."


class PreviewRequest(BaseModel):
    """제약은 `PortfolioCombinationRequest`(`main.py:1109~1112`)와 같은 값이다.

    기본값까지 같게 둔다. 두 경로가 같은 요청을 같은 뜻으로 읽어야 대조가 성립한다.
    티커의 **문자 검사는 여기서 하지 않는다** — 정규화(공백 제거·대문자)가 먼저라
    `services.clean_ticker` 가 맡는다. `main.py` 도 같은 순서다.
    """

    ticker_a: str = Field(default="AAPL", min_length=1, max_length=20)
    ticker_b: str = Field(default="JNJ", min_length=1, max_length=20)
    period: str = Field(default="1y", pattern=r"^(3mo|6mo|1y|2y)$")


class CreateRequest(PreviewRequest):
    anon_id: str | None = Field(default=None, **owner.ANON_ID)  # type: ignore[arg-type]


def _build(req: PreviewRequest) -> dict:
    try:
        return service.analyze(req.ticker_a, req.ticker_b, req.period)  # type: ignore[arg-type]
    except service.CombinationInputError as exc:
        # 사용자가 고칠 수 있는 문제다(종목 형식 · 같은 종목 · 데이터 부족).
        # `main.py` 가 이 네 가지를 전부 422 로 내므로 코드를 맞춘다.
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except service.CombinationDataError as exc:
        # 계산이 깨진 경우다. 사용자가 고칠 수 없으므로 500 이고, 503 이면 안 된다 —
        # 다시 시도해도 같은 값이 나온다 (`routers/simulation.py:63` 과 같은 판단).
        raise HTTPException(status_code=500, detail=_CALC_BROKEN) from exc


@router.post("/preview")
def preview_combination(req: PreviewRequest) -> dict:
    """판정만 하고 저장하지 않는다. DB 를 전혀 건드리지 않는다.

    따로 두는 이유는 F03·F05 와 같다 — ⓐ 화면을 열어 보기만 해도 행이 쌓이는 것을
    막고, ⓑ **Supabase 가 죽어도 조합 화면은 동작한다.**
    """
    return service.to_response(_build(req))


@router.post("/create")
def create_combination(
    req: CreateRequest,
    authorization: str | None = Header(default=None),
) -> dict:
    """판정하고 저장한다. 저장하는 것은 판정과 창이고, 차트는 저장하지 않는다."""
    user_id, anon_id = owner.resolve_owner(
        authorization, req.anon_id, unavailable_detail=_READ_FAILED
    )
    payload = _build(req)

    try:
        saved = combination_repo.insert_combination(
            user_id=user_id,
            anon_id=anon_id,
            ticker_a=payload["ticker_a"],
            ticker_b=payload["ticker_b"],
            period=payload["period"],
            signal=payload["signal"],
            summary=payload["summary"],
            portfolio_hint=payload["portfolio_hint"],
            latest_data_at=payload["latest_data_at"],
            relationship=payload["relationship"],
            observed_from=payload["observed_from"],
            observation_count=payload["observation_count"],
        )
    except supabase_client.SupabaseError as exc:
        # 저장 실패를 200 으로 눙치지 않는다. 이 엔드포인트가 존재하는 이유가 저장이라,
        # 저장이 실패했는데 200 을 주면 사용자는 이력에 남았다고 믿는다.
        raise HTTPException(status_code=503, detail=_SAVE_FAILED) from exc

    return {
        **service.to_response(payload),
        "combination_id": saved["id"],
        "created_at": saved["created_at"],
    }


@router.get("/history")
def combination_history(
    anon_id: str | None = Query(default=None, **owner.ANON_ID),  # type: ignore[arg-type]
    limit: int = Query(default=20, ge=1, le=100),
    authorization: str | None = Header(default=None),
) -> dict:
    """내 조합 조회 이력 목록.

    F05 의 `history` 는 곡선을 뺐지만 여기서는 뺄 것이 없다. 저장한 값이 이미
    판정 문장 두 개뿐이고, 목록에서 신호등만 보여 주면 **왜 그 색인지** 를 알 수
    없어 목록의 쓸모가 사라진다.
    """
    user_id, owner_anon = owner.resolve_owner(
        authorization, anon_id, unavailable_detail=_READ_FAILED
    )

    try:
        rows = combination_repo.list_combinations(
            user_id=user_id, anon_id=owner_anon, limit=limit
        )
    except supabase_client.SupabaseError as exc:
        raise HTTPException(status_code=503, detail=_READ_FAILED) from exc

    items = [_present(row) for row in rows]
    # 결과 0건은 에러가 아니다. total 0 · items [] 로 200 을 준다.
    return {
        "total": len(items),
        "limit": limit,
        "owner_type": "user" if user_id else "anon",
        "items": items,
    }


@router.get("/detail")
def combination_detail(
    id: int = Query(ge=1),
    anon_id: str | None = Query(default=None, **owner.ANON_ID),  # type: ignore[arg-type]
    authorization: str | None = Header(default=None),
) -> dict:
    """저장된 판정을 되살린다. **`chart_points` 만 빠진 `create` 의 응답이다.**

    빠지는 필드가 정확히 하나라는 것은 `scripts/verify_combination_api.py` 가
    두 응답의 키 집합을 빼서 확인한다 — 문서로 적어 두면 나중에 하나 더 빠져도
    아무도 모르지만, 실측으로 고정해 두면 다음 사람이 알게 된다.
    """
    user_id, owner_anon = owner.resolve_owner(
        authorization, anon_id, unavailable_detail=_READ_FAILED
    )

    try:
        row = combination_repo.fetch_combination(id)
    except supabase_client.SupabaseError as exc:
        raise HTTPException(status_code=503, detail=_READ_FAILED) from exc

    if row is None:
        raise HTTPException(status_code=404, detail="해당 조합 조회 결과를 찾을 수 없습니다.")

    # 403 과 404 를 분리한다. 분리하면 "그 id 는 존재한다" 가 새어 나가고 id 가 순번
    # 정수라 열거가 쉽지만, 학습용 데이터라 민감도가 낮다 (`simulation.py:190` 과 같은 판단).
    owned = (row.get("user_id") == user_id) if user_id else (row.get("anon_id") == owner_anon)
    if not owned:
        raise HTTPException(status_code=403, detail="다른 사용자의 조합 조회 결과입니다.")

    return _present(row)


def _present(row: dict) -> dict:
    """저장된 행 하나를 응답 형태로 옮긴다. `history` 와 `detail` 이 함께 쓴다.

    한 함수로 묶는 이유는 **목록에서 누른 항목의 상세가 같은 모양이어야** 하기
    때문이다. 따로 적으면 한쪽에만 필드가 붙는 날이 온다.

    `period_label` 은 저장하지 않고 `period` 에서 되찾는다. 라벨은 표시 문자열이라
    바뀔 수 있고, 바뀌었을 때 **옛 행만 옛 라벨을 들고 있으면 안 되기** 때문이다
    (F05 가 `profile_label` 을 저장한 것과 반대 판단인데, 그쪽은 테이블-정의서 4.5절이
    이미 컬럼으로 못박아 둔 것이라 따랐다. 4.4절에는 그 컬럼이 없다).
    """
    return {
        "ticker_a": row["ticker_a"],
        "ticker_b": row["ticker_b"],
        "period": row["period"],
        "period_label": service.PERIOD_LABELS[row["period"]],
        "signal": row["signal"],
        "summary": row["summary"],
        "portfolio_hint": row["portfolio_hint"],
        "latest_data_at": row["latest_data_at"],
        "combination_id": row["id"],
        "created_at": row["created_at"],
    }
