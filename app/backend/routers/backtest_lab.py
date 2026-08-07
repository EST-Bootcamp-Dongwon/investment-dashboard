"""백테스트 실험실 API.

브라우저에서 종목·구간·비용을 바꿔가며 "2025년으로 학습 → 2026년 예측" 같은
워크포워드 검증을 반복 실행하기 위한 라우터입니다.

lean-hyundai/hd_core.py 를 **그대로 import** 합니다. LEAN 컨테이너가 쓰는 것과
같은 모듈이라, 여기서 나온 신호와 엔진이 집행하는 신호가 갈라지지 않습니다.
다만 이 라우터는 LEAN 엔진을 부르지 않고 벡터화 계산으로 성과를 근사합니다
(웹 요청 안에서 42.5GB 컨테이너를 띄울 수는 없습니다). 정본이 필요하면
`docker compose -f docker-compose.hd.yaml run --rm hd-backtest` 로 엔진을 돌리세요.
"""

from __future__ import annotations

import sys
from datetime import date, datetime, timedelta
from pathlib import Path
from threading import Lock
from time import monotonic

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field, field_validator

# lean-hyundai 는 패키지가 아니라 스크립트 폴더라 경로를 직접 얹습니다.
_ROOT = Path(__file__).resolve().parents[3]
_LEAN_HD = _ROOT / "lean-hyundai"
if str(_LEAN_HD) not in sys.path:
    sys.path.insert(0, str(_LEAN_HD))

try:
    import hd_core  # type: ignore
    import download_price_data  # type: ignore

    _IMPORT_ERROR = ""
except Exception as exc:  # pragma: no cover - 환경 문제를 화면에 그대로 알려줍니다.
    hd_core = None  # type: ignore
    download_price_data = None  # type: ignore
    _IMPORT_ERROR = f"{type(exc).__name__}: {exc}"

router = APIRouter(prefix="/api/backtest-lab", tags=["backtest-lab"])

GENERATED_DIR = _ROOT / "app" / "generated" / "backtest-lab"

# 프리셋. 사용자가 티커를 몰라도 바로 눌러볼 수 있게 합니다.
PRESETS = [
    {"ticker": "005380.KS", "name": "현대차"},
    {"ticker": "005930.KS", "name": "삼성전자"},
    {"ticker": "000660.KS", "name": "SK하이닉스"},
    {"ticker": "035420.KS", "name": "NAVER"},
    {"ticker": "051910.KS", "name": "LG화학"},
    {"ticker": "207940.KS", "name": "삼성바이오로직스"},
    {"ticker": "^KS11", "name": "코스피 지수"},
]

# 시세 캐시. 같은 조건을 반복 실행할 때 Yahoo 를 매번 두드리지 않기 위한 것으로,
# 요청 제한(429)에 걸리는 것도 막아줍니다.
_CACHE_TTL_SECONDS = 900
_price_cache: dict[tuple[str, str, str], tuple[float, list]] = {}
_cache_lock = Lock()


class RunRequest(BaseModel):
    ticker: str = Field(default="005380.KS", max_length=24)
    name: str = Field(default="현대차", max_length=40)
    train_start: str = Field(default="2025-01-01")
    train_end: str = Field(default="2025-12-31")
    test_start: str = Field(default="2026-01-01")
    test_end: str = Field(default="2026-06-30")
    initial_cash: float = Field(default=100_000_000, ge=1_000_000, le=1_000_000_000_000)
    commission_rate: float = Field(default=hd_core.DEFAULT_COMMISSION_RATE if hd_core else 0.00015, ge=0, le=0.02)
    sell_tax_rate: float = Field(default=hd_core.DEFAULT_SELL_TAX_RATE if hd_core else 0.0015, ge=0, le=0.02)
    slippage_rate: float = Field(default=hd_core.DEFAULT_SLIPPAGE_RATE if hd_core else 0.0005, ge=0, le=0.02)
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


def _require_core() -> None:
    if hd_core is None or download_price_data is None:
        raise HTTPException(
            status_code=503,
            detail=(
                "예측 모듈(lean-hyundai/hd_core.py)을 불러오지 못했습니다. "
                f"원인: {_IMPORT_ERROR or '경로에서 모듈을 찾지 못함'}. "
                "백엔드 이미지에 lean-hyundai/ 가 포함됐는지, numpy·pandas·scikit-learn 이 "
                "설치돼 있는지 확인하세요."
            ),
        )


def _check_period(payload: RunRequest) -> None:
    train_start = date.fromisoformat(payload.train_start)
    train_end = date.fromisoformat(payload.train_end)
    test_start = date.fromisoformat(payload.test_start)
    test_end = date.fromisoformat(payload.test_end)

    if train_start >= train_end:
        raise HTTPException(400, "학습 시작일이 학습 종료일보다 빠릅니다.")
    if test_start >= test_end:
        raise HTTPException(400, "검증 시작일이 검증 종료일보다 빠릅니다.")
    if test_start <= train_end:
        raise HTTPException(
            400,
            "검증 구간이 학습 구간과 겹칩니다. 겹치면 out-of-sample 검증이 아니라 "
            "그냥 학습 데이터를 다시 맞히는 것이 됩니다. 검증 시작일을 학습 종료일 뒤로 두세요.",
        )
    if test_end > date.today():
        raise HTTPException(
            400,
            f"검증 종료일({payload.test_end})이 오늘({date.today().isoformat()})보다 뒤입니다. "
            "아직 오지 않은 날은 실제값이 없어 비교할 수 없습니다.",
        )


def _fetch_prices(ticker: str, start: str, end: str) -> list:
    key = (ticker, start, end)
    now = monotonic()
    with _cache_lock:
        hit = _price_cache.get(key)
        if hit and now - hit[0] < _CACHE_TTL_SECONDS:
            return hit[1]

    try:
        rows = download_price_data.download(ticker, start, end)
    except Exception as exc:
        raise HTTPException(
            status_code=502,
            detail=(
                f"Yahoo Finance 에서 {ticker} 시세를 받지 못했습니다 ({type(exc).__name__}). "
                "비공식 엔드포인트라 요청이 제한(429)되거나 티커가 잘못됐을 수 있습니다. "
                "잠시 후 다시 시도하거나 티커를 확인하세요."
            ),
        ) from exc

    if not rows:
        raise HTTPException(
            status_code=404,
            detail=f"{ticker} 의 {start}~{end} 구간에서 받은 유효한 일봉이 0건입니다. 티커와 기간을 확인하세요.",
        )

    with _cache_lock:
        _price_cache[key] = (now, rows)
        # 캐시가 무한정 자라지 않게 오래된 항목을 정리합니다.
        for stale in [k for k, (ts, _) in _price_cache.items() if now - ts > _CACHE_TTL_SECONDS]:
            _price_cache.pop(stale, None)
    return rows


def _run_pipeline(payload: RunRequest) -> dict:
    """시세 수집 → 피처 → 학습·예측 → 평가 → 간이 백테스트."""
    import pandas as pd

    _require_core()
    _check_period(payload)

    data_start = (
        date.fromisoformat(payload.train_start) - timedelta(days=payload.warmup_days)
    ).isoformat()
    rows = _fetch_prices(payload.ticker, data_start, payload.test_end)

    prices = pd.DataFrame(rows, columns=["Date", "Open", "High", "Low", "Close", "Volume"])
    prices["Date"] = pd.to_datetime(prices["Date"])
    prices = prices.sort_values("Date").drop_duplicates("Date").reset_index(drop=True)

    featured = hd_core.build_features(prices)
    try:
        run = hd_core.train_and_predict(
            featured,
            payload.train_start,
            payload.train_end,
            payload.test_start,
            payload.test_end,
        )
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc

    backtest = hd_core.simple_backtest(
        run.rows,
        initial_cash=payload.initial_cash,
        commission_rate=payload.commission_rate,
        sell_tax_rate=payload.sell_tax_rate,
        slippage_rate=payload.slippage_rate,
    )

    return {
        "meta": {
            "ticker": payload.ticker,
            "name": payload.name or payload.ticker,
            "train_start": payload.train_start,
            "train_end": payload.train_end,
            "test_start": payload.test_start,
            "test_end": payload.test_end,
            "train_samples": run.train_size,
            "test_samples": len(run.rows),
            "model": "sklearn HistGradientBoostingRegressor",
            "features": hd_core.FEATURE_COLUMNS,
            "price_rows": int(len(prices)),
            "price_first": prices["Date"].iloc[0].date().isoformat(),
            "price_last": prices["Date"].iloc[-1].date().isoformat(),
            "engine": "간이(벡터화) 계산 — 정본은 LEAN 엔진 실행 결과입니다.",
        },
        "regime": hd_core.regime_summary(
            featured, payload.train_start, payload.train_end, payload.test_start, payload.test_end
        ),
        "prediction_metrics": run.metrics.to_dict(),
        "feature_importance": run.feature_importance,
        "rows": run.rows,
        "simple_backtest": backtest,
    }


@router.get("/config")
def get_config() -> dict:
    """화면이 처음 뜰 때 필요한 기본값·프리셋·제약."""
    defaults = RunRequest()
    return {
        "available": hd_core is not None,
        "import_error": _IMPORT_ERROR,
        "presets": PRESETS,
        "defaults": defaults.model_dump(),
        "today": date.today().isoformat(),
        "features": hd_core.FEATURE_COLUMNS if hd_core else [],
        "notes": [
            "검증 구간은 학습 구간보다 뒤여야 하고, 오늘 이전이어야 합니다.",
            "이 화면의 성과는 벡터화 근사치입니다. 정본은 LEAN 엔진 실행 결과입니다.",
            "체결은 신호 확정일 종가로 가정합니다. 실제로는 그 가격에 살 수 없습니다.",
        ],
    }


@router.post("/run")
def run_experiment(payload: RunRequest) -> dict:
    """예측 + 간이 백테스트를 실행하고 화면이 쓸 데이터를 통째로 돌려줍니다."""
    return _run_pipeline(payload)


@router.post("/report")
def build_report(payload: RunRequest) -> dict:
    """같은 실행 결과를 자체완결 HTML 리포트로 만들어 돌려줍니다.

    HTML 본문을 응답에 담아 브라우저가 바로 내려받을 수 있게 하고,
    서버 쪽에도 사본을 남깁니다.
    """
    _require_core()

    try:
        import make_report  # type: ignore
    except Exception as exc:
        raise HTTPException(503, f"리포트 생성기를 불러오지 못했습니다: {type(exc).__name__}: {exc}") from exc

    result = _run_pipeline(payload)
    empty_lean = {"available": False, "statistics": {}, "equity": [], "orders": [], "runtime": {}}
    html = make_report.build_report(result, empty_lean)

    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    safe_ticker = payload.ticker.replace("^", "").replace(".", "_")
    filename = f"{safe_ticker}-{payload.test_start}_{payload.test_end}-{stamp}.html"

    saved = ""
    try:
        GENERATED_DIR.mkdir(parents=True, exist_ok=True)
        target = GENERATED_DIR / filename
        target.write_text(html, encoding="utf-8")
        saved = str(target.relative_to(_ROOT))
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
