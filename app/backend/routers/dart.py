"""DART 공시 기업 정보 — Controller.

[CN-065](../../../docs/spec/00-index/변경이력.md#cn-065) 분해 순서 ⑤~⑦. `main.py` 에서
갈라져 나온 라우터다. 경로 선언과 요청 검증만 하고, 판정·계산·그림은
`services/dart.py` 가 맡는다.

**경로 문자열은 옮기기 전과 한 글자도 다르지 않다.** 화면(`app/frontend/js/api.js`)이
그 경로를 부르고 있어서, 여기서 접두사를 붙이면 그대로 404 가 된다. 그래서
`APIRouter(prefix=...)` 를 쓰지 않고 절대 경로를 그대로 적는다 —
`routers/combination.py` 같은 신설 라우터와 다른 점이다.
"""

from __future__ import annotations

from fastapi import APIRouter
from pydantic import BaseModel, Field

try:
    from ..services import dart as service
except ImportError:  # `uvicorn main:app` 를 app/backend 에서 실행하는 경우
    from services import dart as service  # type: ignore

router = APIRouter()

class DartCompanySearchRequest(BaseModel):
    company_name: str = Field(default="삼성전자", min_length=1, max_length=80)
    limit: int = Field(default=10, ge=1, le=30)


class GroupNetworkRequest(BaseModel):
    group_name: str = Field(default="삼성", min_length=1, max_length=50)
    limit: int = Field(default=80, ge=1, le=100)


class DartCompanyListRequest(BaseModel):
    region: str = Field(default="서울특별시", max_length=30)
    emp_min: int | None = Field(default=None, ge=0, le=1_000_000)
    emp_max: int | None = Field(default=None, ge=0, le=1_000_000)
    bsns_year: str = Field(default="2024", pattern=r"^\d{4}$")
    limit: int = Field(default=50, ge=1, le=200)


class DartFinancialAnalysisRequest(BaseModel):
    corp_code:    str       = Field(min_length=8, max_length=8, description="DART 고유번호 (8자리)")
    bsns_year:    str       = Field(default="2023", pattern=r"^\d{4}$")
    reprt_code:   str       = Field(default="11011", pattern=r"^1101[1-4]$",
                                    description="11011=사업보고서 11012=반기 11013=1분기 11014=3분기")


@router.post("/api/dart/company-search")
def dart_company_search(req: DartCompanySearchRequest) -> dict[str, object]:
    return service.dart_company_search(company_name=req.company_name, limit=req.limit)


@router.post("/api/dart/group-network")
def dart_group_network(req: GroupNetworkRequest) -> dict[str, object]:
    """Search DART listed companies by group/conglomerate keyword and enrich"""
    return service.dart_group_network(group_name=req.group_name, limit=req.limit)


@router.post("/api/dart/company-list")
def dart_company_list(req: DartCompanyListRequest) -> dict[str, object]:
    """Search listed companies by region (address substring) and/or employee count."""
    return service.dart_company_list(region=req.region, emp_min=req.emp_min, emp_max=req.emp_max, bsns_year=req.bsns_year, limit=req.limit)


@router.post("/api/dart/financial-analysis")
def dart_financial_analysis(req: DartFinancialAnalysisRequest) -> dict:
    """Fetch DART financial statements and run AI-powered financial health analysis."""
    return service.dart_financial_analysis(corp_code=req.corp_code, bsns_year=req.bsns_year, reprt_code=req.reprt_code)
