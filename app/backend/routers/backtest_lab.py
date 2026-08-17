"""백테스트 실험실 API — Controller.

브라우저에서 종목·구간·비용을 바꿔가며 "2025년으로 학습 → 2026년 예측" 같은
워크포워드 검증을 반복 실행하기 위한 라우터입니다.

**F03 · F04 · F05 에 이어 3계층을 네 번째로 적용한 대상입니다**(아키텍처 3절 ④).
이 파일은 경로 선언 · 요청 검증 · **도메인 예외를 HTTP 코드로 번역**하는 일만 합니다.
계산과 저장 규칙은 `services/backtest.py`, 시세는 `clients/lean_prices.py`,
DB 접근은 `clients/backtest_repo.py` 에 있습니다.

`lean-hyundai/hd_core.py` 를 **그대로 쓰는 것은 그대로입니다**(이제 서비스 계층이
import 합니다). LEAN 컨테이너가 쓰는 것과 같은 모듈이라, 여기서 나온 신호와 엔진이
집행하는 신호가 갈라지지 않습니다. 다만 이 라우터는 LEAN 엔진을 부르지 않고 벡터화
계산으로 성과를 근사합니다(웹 요청 안에서 42.5GB 컨테이너를 띄울 수는 없습니다).
정본이 필요하면 `docker compose -f docker-compose.hd.yaml run --rm hd-backtest` 로
엔진을 돌리세요.

## 앞의 셋과 다른 점 두 가지

**① 원본이 이미 라우터였습니다.** F03 은 프런트 JS 에서, F04 는 `main.py` 에서,
F05 는 `routers/quant.py` 에서 도메인을 꺼내 왔습니다. F28 은 이 파일 안의
`_run_pipeline` 이 원본이라, `main.py` 원문을 AST 로 읽어 상수를 대조할 필요가
없습니다(CN-106 ①). 대신 **더 강한 대조**를 합니다 — 리팩터 전 `/run` 출력 전체를
골든으로 떠 두고 지금 출력과 `==` 로 비교합니다(`scripts/verify_backtest_api.py`).

**② `/run` 을 남겨 두는 것이 아니라 지나가게 했습니다.** F04 는 `main.py` 의
엔드포인트를 건드리지 않고 저장 경로를 따로 냈지만, 여기서는 `/run`·`/report` 도
같은 서비스 계층을 지납니다. **두 경로가 다르게 깎으면 같은 요청이 저장 여부에 따라
다른 숫자를 내기 때문입니다**(정규화 이유는 `services/backtest.py` 머리말).
출력이 바뀌지 않았다는 것은 골든 대조가 확인합니다.

설계 정본: docs/spec/30-데이터/테이블-정의서.md 4.6절.
"""

from __future__ import annotations

from datetime import date, datetime

from fastapi import APIRouter, Header, HTTPException, Query
from pydantic import BaseModel, Field, field_validator

try:
    from .. import paths
    from ..clients import backtest_repo, lean_prices, supabase_client
    from ..services import backtest as service
    from . import owner
except ImportError:  # `uvicorn main:app` 를 app/backend 에서 실행하는 경우
    import paths  # type: ignore
    from clients import backtest_repo, lean_prices, supabase_client  # type: ignore
    from routers import owner  # type: ignore
    from services import backtest as service  # type: ignore

router = APIRouter(prefix="/api/backtest-lab", tags=["backtest-lab"])

# 경로 출처를 `paths` 로 옮겼다. 이 파일의 저장 코드는 원래부터 옳았고(요청 처리 중 ·
# `try/except OSError`), 바뀐 것은 **어디에 쓰느냐**뿐이다 — Vercel 에서는 `/tmp` 다.
# `_ROOT` 는 그러면서 쓸 자리가 없어졌다(경로 계산이 `paths.ROOT_DIR` 한 곳으로 모였다).
_GENERATED_SUBDIR = "backtest-lab"

_SAVE_FAILED = "백테스트 결과를 저장할 수 없습니다. 잠시 후 다시 시도해 주세요."
_READ_FAILED = "백테스트 이력을 불러올 수 없습니다. 잠시 후 다시 시도해 주세요."

# 프리셋은 도메인 상수라 서비스 계층에 있습니다. 이름만 다시 걸어 둡니다.
PRESETS = service.PRESETS


class RunRequest(BaseModel):
    ticker: str = Field(default="005380.KS", max_length=24)
    name: str = Field(default="현대차", max_length=40)
    train_start: str = Field(default="2025-01-01")
    train_end: str = Field(default="2025-12-31")
    test_start: str = Field(default="2026-01-01")
    test_end: str = Field(default="2026-06-30")
    initial_cash: float = Field(default=100_000_000, ge=1_000_000, le=1_000_000_000_000)
    commission_rate: float = Field(default=service.DEFAULT_COMMISSION_RATE, ge=0, le=0.02)
    sell_tax_rate: float = Field(default=service.DEFAULT_SELL_TAX_RATE, ge=0, le=0.02)
    slippage_rate: float = Field(default=service.DEFAULT_SLIPPAGE_RATE, ge=0, le=0.02)
    # 피처 워밍업용 여유 일수. SMA20·RSI14 가 학습 첫날부터 값을 갖게 합니다.
    warmup_days: int = Field(default=120, ge=30, le=750)

    @field_validator("train_start", "train_end", "test_start", "test_end")
    @classmethod
    def _valid_date(cls, value: str) -> str:
        try:
            date.fromisoformat(value)
        except ValueError:
            raise ValueError(f"날짜 형식이 올바르지 않습니다(YYYY-MM-DD): {value}")
        return value

    @field_validator("ticker")
    @classmethod
    def _valid_ticker(cls, value: str) -> str:
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("티커를 입력하세요.")
        # Yahoo 티커에 쓰이는 문자만 허용합니다(경로 주입·명령 주입 방지).
        allowed = set("ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789.-^=")
        if not set(cleaned) <= allowed:
            raise ValueError(f"티커에 허용되지 않는 문자가 있습니다: {value}")
        return cleaned


class SaveRequest(RunRequest):
    anon_id: str | None = Field(default=None, **owner.ANON_ID)  # type: ignore[arg-type]


def _params(req: RunRequest) -> service.RunParams:
    """요청을 **정규화된** 도메인 입력으로 옮깁니다. 저장 여부와 무관하게 같은 값입니다."""
    return service.RunParams.normalized(
        ticker=req.ticker,
        name=req.name,
        train_start=req.train_start,
        train_end=req.train_end,
        test_start=req.test_start,
        test_end=req.test_end,
        initial_cash=req.initial_cash,
        commission_rate=req.commission_rate,
        sell_tax_rate=req.sell_tax_rate,
        slippage_rate=req.slippage_rate,
        warmup_days=req.warmup_days,
    )


def _run(params: service.RunParams) -> dict:
    """도메인 계층을 부르고 **예외만 HTTP 코드로 번역합니다.**

    네 가지를 다른 코드로 냅니다. 리팩터 전(`_run_pipeline`)과 코드도 문구도 같습니다.
    하나로 뭉뚱그리지 않는 이유는 사용자가 할 일이 각각 다르기 때문입니다 —
    503 은 서버 설치 문제, 400 은 구간을 고쳐라, 502 는 잠시 후 다시,
    404 는 티커·기간을 고쳐라 입니다.
    """
    try:
        return service.run(params)
    except service.BacktestUnavailable as exc:
        raise HTTPException(
            status_code=503,
            detail=(
                "예측 모듈(lean-hyundai/hd_core.py)을 불러오지 못했습니다. "
                f"원인: {exc}. "
                "백엔드 이미지에 lean-hyundai/ 가 포함됐는지, numpy·pandas·scikit-learn 이 "
                "설치돼 있는지 확인하세요."
            ),
        ) from exc
    except service.BacktestInputError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except lean_prices.PriceDownloadError as exc:
        # 원인 예외의 타입 이름을 그대로 보여 줍니다. `raise … from exc` 로 올라오므로
        # `__cause__` 에 원본이 있습니다 — 이름을 따로 들고 다니지 않아도 됩니다.
        cause = type(exc.__cause__).__name__ if exc.__cause__ else "ImportError"
        raise HTTPException(
            status_code=502,
            detail=(
                f"Yahoo Finance 에서 {params.ticker} 시세를 받지 못했습니다 ({cause}). "
                "비공식 엔드포인트라 요청이 제한(429)되거나 티커가 잘못됐을 수 있습니다. "
                "잠시 후 다시 시도하거나 티커를 확인하세요."
            ),
        ) from exc
    except lean_prices.PriceEmptyError as exc:
        raise HTTPException(status_code=404, detail=f"{exc} 티커와 기간을 확인하세요.") from exc


@router.get("/config")
def get_config() -> dict:
    """화면이 처음 뜰 때 필요한 기본값·프리셋·제약.

    `available` 이 **시세 모듈까지 함께 봅니다.** 리팩터 전에는 `hd_core is not None`
    만 봐서, 시세 모듈만 없는 환경에서 화면은 "쓸 수 있다" 로 뜨는데 `/run` 은 503 을
    내는 상태가 가능했습니다(`_require_core` 는 둘 다 봤습니다). 둘을 맞췄습니다.
    """
    defaults = RunRequest()
    return {
        "available": service.engine_available(),
        "import_error": service.import_error(),
        "presets": service.PRESETS,
        "defaults": defaults.model_dump(),
        "today": date.today().isoformat(),
        "features": service.hd_core.FEATURE_COLUMNS if service.hd_core else [],
        "notes": [
            "검증 구간은 학습 구간보다 뒤여야 하고, 오늘 이전이어야 합니다.",
            "이 화면의 성과는 벡터화 근사치입니다. 정본은 LEAN 엔진 실행 결과입니다.",
            "체결은 신호 확정일 종가로 가정합니다. 실제로는 그 가격에 살 수 없습니다.",
        ],
    }


@router.post("/run")
def run_experiment(payload: RunRequest) -> dict:
    """예측 + 간이 백테스트를 실행하고 화면이 쓸 데이터를 통째로 돌려줍니다.

    **저장하지 않습니다.** 따로 두는 이유는 F03·F04·F05 와 같습니다 — ⓐ 화면을 열어
    돌려 보기만 해도 행이 쌓이는 것을 막고, ⓑ **Supabase 가 죽어도 실험실은 동작합니다.**
    """
    return _run(_params(payload))


@router.post("/save")
def save_experiment(
    payload: SaveRequest,
    authorization: str | None = Header(default=None),
) -> dict:
    """실행하고 저장합니다. `/run` 의 응답에 `inputs` · 식별자 · 저장 시각이 붙습니다.

    **요청에 담긴 성과 수치를 받지 않고 여기서 다시 계산합니다.** 클라이언트가 계산한
    값을 그대로 저장하면 누구든 자기 이력에 원하는 수익률을 적어 넣을 수 있습니다.
    F03·F04·F05 의 `create` 가 전부 다시 계산하는 것과 같은 이유입니다.

    저장하는 것은 입력 11개 · 지표 3덩이 · 시세 창 3개이고, **일별 예측표와
    자산곡선은 저장하지 않습니다**(제약 C-04). 무엇이 빠지는지는
    `services/backtest.UNSAVED_*` 에 이름으로 박혀 있고, 검증이 그 목록과 실제
    응답의 차집합을 대조합니다.
    """
    user_id, anon_id = owner.resolve_owner(
        authorization, payload.anon_id, unavailable_detail=_READ_FAILED
    )
    params = _params(payload)
    result = _run(params)

    try:
        saved = backtest_repo.insert_backtest_summary(
            service.to_row(params, result, user_id=user_id, anon_id=anon_id)
        )
    except supabase_client.SupabaseError as exc:
        # 저장 실패를 200 으로 눙치지 않습니다. 이 엔드포인트가 존재하는 이유가
        # 저장이라, 저장이 실패했는데 200 을 주면 사용자는 이력에 남았다고 믿습니다.
        raise HTTPException(status_code=503, detail=_SAVE_FAILED) from exc

    return {
        **result,
        "inputs": params.as_inputs(),
        "backtest_id": saved["id"],
        "created_at": saved["created_at"],
    }


@router.get("/history")
def backtest_history(
    anon_id: str | None = Query(default=None, **owner.ANON_ID),  # type: ignore[arg-type]
    limit: int = Query(default=20, ge=1, le=100),
    authorization: str | None = Header(default=None),
) -> dict:
    """내 백테스트 이력 목록. **지표 3덩이는 담지 않습니다**(이유는 `to_list_item`)."""
    user_id, owner_anon = owner.resolve_owner(
        authorization, anon_id, unavailable_detail=_READ_FAILED
    )

    try:
        rows = backtest_repo.list_backtest_summaries(
            user_id=user_id, anon_id=owner_anon, limit=limit
        )
    except supabase_client.SupabaseError as exc:
        raise HTTPException(status_code=503, detail=_READ_FAILED) from exc

    items = [service.to_list_item(row) for row in rows]
    # 결과 0건은 에러가 아닙니다. total 0 · items [] 로 200 을 줍니다.
    return {
        "total": len(items),
        "limit": limit,
        "owner_type": "user" if user_id else "anon",
        "items": items,
    }


@router.get("/detail")
def backtest_detail(
    id: int = Query(ge=1),
    anon_id: str | None = Query(default=None, **owner.ANON_ID),  # type: ignore[arg-type]
    authorization: str | None = Header(default=None),
) -> dict:
    """저장된 실행을 되살립니다. **`/save` 응답에서 되살릴 수 없는 것만 빠진 모양**입니다.

    빠지는 것이 정확히 무엇인지(`rows` · `regime` · `feature_importance` ·
    `simple_backtest.curve` · `meta` 3개)는 `scripts/verify_backtest_api.py` 가 두
    응답의 키 집합을 빼서 확인합니다 — 문서로 적어 두면 나중에 하나 더 빠져도 아무도
    모르지만, 실측으로 고정해 두면 다음 사람이 알게 됩니다(F04 에서 온 방식).

    빠진 것을 지금 다시 계산해서 채우지 않습니다. 그러면 **저장된 지표에 다른 실행의
    곡선**이 붙고, 사용자는 그 곡선을 보고 그 지표가 나왔다고 읽습니다(CN-108).
    대신 `inputs` 를 실어, 같은 값을 원하면 `/run` 으로 다시 돌릴 수 있게 합니다.
    """
    user_id, owner_anon = owner.resolve_owner(
        authorization, anon_id, unavailable_detail=_READ_FAILED
    )

    try:
        row = backtest_repo.fetch_backtest_summary(id)
    except supabase_client.SupabaseError as exc:
        raise HTTPException(status_code=503, detail=_READ_FAILED) from exc

    if row is None:
        raise HTTPException(status_code=404, detail="해당 백테스트 결과를 찾을 수 없습니다.")

    # 403 과 404 를 분리합니다. 분리하면 "그 id 는 존재한다" 가 새어 나가고 id 가 순번
    # 정수라 열거가 쉽지만, 학습용 데이터라 민감도가 낮습니다(`combination.py:190` 과
    # 같은 판단).
    owned = (row.get("user_id") == user_id) if user_id else (row.get("anon_id") == owner_anon)
    if not owned:
        raise HTTPException(status_code=403, detail="다른 사용자의 백테스트 결과입니다.")

    return service.to_detail(row)


@router.post("/report")
def build_report(payload: RunRequest) -> dict:
    """같은 실행 결과를 자체완결 HTML 리포트로 만들어 돌려줍니다.

    HTML 본문을 응답에 담아 브라우저가 바로 내려받을 수 있게 하고,
    서버 쪽에도 사본을 남깁니다.

    **저장 경로와 무관합니다.** 리포트는 파일이고 이력은 행이라, 하나가 실패해도
    다른 하나는 되어야 합니다.
    """
    if not service.engine_available():
        raise HTTPException(
            status_code=503,
            detail=(
                "예측 모듈(lean-hyundai/hd_core.py)을 불러오지 못했습니다. "
                f"원인: {service.import_error() or '경로에서 모듈을 찾지 못함'}. "
                "백엔드 이미지에 lean-hyundai/ 가 포함됐는지, numpy·pandas·scikit-learn 이 "
                "설치돼 있는지 확인하세요."
            ),
        )

    try:
        import make_report  # type: ignore
    except Exception as exc:
        raise HTTPException(503, f"리포트 생성기를 불러오지 못했습니다: {type(exc).__name__}: {exc}") from exc

    params = _params(payload)
    result = _run(params)
    empty_lean = {"available": False, "statistics": {}, "equity": [], "orders": [], "runtime": {}}
    html = make_report.build_report(result, empty_lean)

    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    safe_ticker = params.ticker.replace("^", "").replace(".", "_")
    filename = f"{safe_ticker}-{params.test_start}_{params.test_end}-{stamp}.html"

    saved = ""
    try:
        target = paths.ensure(_GENERATED_SUBDIR) / filename
        target.write_text(html, encoding="utf-8")
        # `relative_to(_ROOT)` 를 직접 쓰지 않습니다 — 경로가 `/tmp` 로 옮겨지면
        # `ValueError` 가 나고, 그건 아래 `OSError` 가드를 그냥 지나쳐 500 이 됩니다.
        saved = paths.describe(target)
    except OSError:
        # 저장에 실패해도 브라우저 다운로드는 되도록 응답은 그대로 돌려줍니다.
        saved = ""

    return {
        "filename": filename,
        "saved_path": saved,
        "bytes": len(html.encode("utf-8")),
        "html": html,
        "summary": {
            "direction_accuracy": result["prediction_metrics"]["direction_accuracy"],
            "naive_direction_accuracy": result["prediction_metrics"]["naive_direction_accuracy"],
            "strategy_return_pct": result["simple_backtest"]["strategy"]["total_return_pct"],
            "benchmark_return_pct": result["simple_backtest"]["benchmark"]["total_return_pct"],
        },
    }
