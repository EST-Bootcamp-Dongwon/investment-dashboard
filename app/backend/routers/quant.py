from __future__ import annotations

# 원본에는 네 이름(base64·io·configure_matplotlib_korean_font·_calc_rsi)의 import 가
# 없어서 quant 라우터의 6개 엔드포인트 중 5개가 호출 즉시 NameError 로 500 을 냈다
# (경위는 NOTICE.md). v1.0 에서 여기에 import 를 더해 고쳤고, **v2.0 에서 그 네 이름이
# 차트 본문과 함께 `services/quant_charts.py` 로 옮겨 갔다**(CN-065 분해 순서 ⑤).
# 이 파일에는 이제 쓸 자리가 없다.

from fastapi import APIRouter
from pydantic import BaseModel, Field

try:
    from ..services import quant_charts
except ImportError:  # `uvicorn main:app` 를 app/backend 에서 실행하는 경우
    from services import quant_charts  # type: ignore

router = APIRouter()


class BacktestRequest(BaseModel):
    fast_ma: int = Field(default=20, ge=5, le=60)
    slow_ma: int = Field(default=60, ge=20, le=200)
    n_days: int = Field(default=1260, ge=252, le=5040)


class PortfolioRequest(BaseModel):
    n_simulations: int = Field(default=3000, ge=500, le=10000)
    risk_free: float = Field(default=0.03, ge=0.0, le=0.1)


class RiskRequest(BaseModel):
    confidence: float = Field(default=0.95, ge=0.90, le=0.99)
    n_scenarios: int = Field(default=10000, ge=1000, le=100000)
    portfolio_value: float = Field(default=100_000_000, ge=1_000_000)


class PipelineRequest(BaseModel):
    ticker: str = Field(default="SPY")
    fast_ma: int = Field(default=20, ge=5, le=60)
    slow_ma: int = Field(default=60, ge=20, le=200)


class FinancialKnowledgeRequest(BaseModel):
    focus: str = Field(default="balanced", pattern="^(balanced|products|allocation)$")
    n_simulations: int = Field(default=3000, ge=500, le=10000)
    risk_free: float = Field(default=0.03, ge=0.0, le=0.1)


class PortfolioScenarioRequest(BaseModel):
    profile: str = Field(default="balanced", pattern="^(stable|balanced|growth)$")
    initial_amount: int = Field(default=10_000_000, ge=0, le=1_000_000_000)
    monthly_amount: int = Field(default=500_000, ge=0, le=100_000_000)
    years: int = Field(default=10, ge=1, le=30)


# ─── Quant Endpoints ──────────────────────────────────────────────────────────

@router.post("/api/quant/portfolio-scenario")
def portfolio_scenario(req: PortfolioScenarioRequest) -> dict[str, object]:
    """Educational Monte Carlo projection for a simple portfolio profile."""
    import numpy as np

    # These are illustrative assumptions, not forecasts or investable expected returns.
    profiles = {
        "stable": {"label": "안정 중심", "return": 0.045, "volatility": 0.07},
        "balanced": {"label": "균형 중심", "return": 0.065, "volatility": 0.12},
        "growth": {"label": "성장 중심", "return": 0.085, "volatility": 0.18},
    }
    config = profiles[req.profile]
    rng = np.random.default_rng(20260806)
    paths = 5_000
    balances = np.full(paths, float(req.initial_amount))
    monthly_return = (1 + config["return"]) ** (1 / 12) - 1
    monthly_volatility = config["volatility"] / np.sqrt(12)
    points = [{"year": 0, "cautious": int(req.initial_amount), "middle": int(req.initial_amount), "positive": int(req.initial_amount)}]

    for month in range(1, req.years * 12 + 1):
        changes = rng.normal(monthly_return, monthly_volatility, paths)
        balances = np.maximum(0, (balances + req.monthly_amount) * (1 + changes))
        if month % 12 == 0:
            cautious, middle, positive = np.percentile(balances, [10, 50, 90])
            points.append({
                "year": month // 12,
                "cautious": int(round(cautious)),
                "middle": int(round(middle)),
                "positive": int(round(positive)),
            })

    total_paid = req.initial_amount + req.monthly_amount * req.years * 12
    final = points[-1]
    return {
        "profile_label": config["label"],
        "years": req.years,
        "total_paid": int(total_paid),
        "points": points,
        "summary": {
            "cautious": final["cautious"],
            "middle": final["middle"],
            "positive": final["positive"],
        },
        "explanation": "같은 구성이라도 시장 흐름에 따라 결과가 달라질 수 있음을 보여주는 학습용 가상 시나리오입니다.",
    }

@router.post("/api/quant/backtest")
def quant_backtest(req: BacktestRequest) -> dict[str, object]:
    """MA 크로스오버 전략 백테스트 (Day041·57 대응)"""
    return quant_charts.backtest(
        fast_ma=req.fast_ma,
        slow_ma=req.slow_ma,
        n_days=req.n_days,
    )


@router.post("/api/quant/portfolio")
def quant_portfolio(req: PortfolioRequest) -> dict[str, object]:
    """포트폴리오 최적화 — 효율적 프론티어 + Sharpe 극대화 (Day57·76·77 대응)"""
    return quant_charts.portfolio(
        n_simulations=req.n_simulations,
        risk_free=req.risk_free,
    )


@router.post("/api/quant/financial-knowledge")
def quant_financial_knowledge(req: FinancialKnowledgeRequest) -> dict[str, object]:
    """모듈 8 — 금융상품 이해와 자산배분방법론 5일 커리큘럼 점검/실습.

    `req.focus` 는 넘기지 않는다. 본문이 원래부터 그 값을 읽지 않았고 화면도 보내지
    않는다 — 자세한 사정은 `services/quant_charts.financial_knowledge` 의 주석에 있다.
    """
    return quant_charts.financial_knowledge(
        n_simulations=req.n_simulations,
        risk_free=req.risk_free,
    )


@router.post("/api/quant/risk")
def quant_risk(req: RiskRequest) -> dict[str, object]:
    """VaR / CVaR 리스크 분석 (Day39·55 대응)"""
    return quant_charts.risk(
        confidence=req.confidence,
        n_scenarios=req.n_scenarios,
        portfolio_value=req.portfolio_value,
    )


@router.post("/api/quant/pipeline")
def quant_pipeline(req: PipelineRequest) -> dict[str, object]:
    """퀀트 실전 4단계 파이프라인 시각화 (Day43·61 대응)"""
    return quant_charts.pipeline(
        ticker=req.ticker,
        fast_ma=req.fast_ma,
        slow_ma=req.slow_ma,
    )

