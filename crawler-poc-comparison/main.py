"""FastAPI 入口(柬埔寨双源对照 PoC)。

启动:uvicorn main:app --reload --port 8004
访问:http://localhost:8004/
"""
from __future__ import annotations

from fastapi import FastAPI, HTTPException
from fastapi.staticfiles import StaticFiles

from schemas import ComparisonResponse
from service import compare_company

app = FastAPI(title="柬埔寨双源对照 PoC")


@app.post("/api/poc/compare", response_model=ComparisonResponse)
async def compare(payload: dict) -> ComparisonResponse:
    """payload: {company_name: str, force_refresh: bool}"""
    company_name = (payload.get("company_name") or "").strip()
    force_refresh = bool(payload.get("force_refresh", False))
    if not company_name:
        raise HTTPException(400, "company_name 不能为空")
    return await compare_company(company_name, force_refresh)


app.mount("/", StaticFiles(directory="static", html=True), name="static")
