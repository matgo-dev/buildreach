"""信用评估接口本地烟雾测试(工单 Step 15)。

依赖:
- backend dev server 已启动(uvicorn app.main:app --reload --port 8000)
- SEED_DEMO_ACCOUNTS=true 启动过一次,4 家 demo 企业已 seed
- demo BUYER 账号:buyer@cscec3b.local / Aa123456789

可选:DASHSCOPE_API_KEY 配了才能测 AI 流式接口,否则会跳过该步骤。

跑法:
    python backend/scripts/credit_smoke_test.py

完成后输出每步状态,失败 → exit code 1。
"""
from __future__ import annotations

import os
import sys

import httpx


BASE = os.environ.get("CREDIT_SMOKE_BASE_URL", "http://localhost:8000")
EMAIL = os.environ.get("CREDIT_SMOKE_EMAIL", "buyer@cscec3b.local")
PASSWORD = os.environ.get("CREDIT_SMOKE_PASSWORD", "Aa123456789")


def step(name: str) -> None:
    print(f"\n=== {name} ===", flush=True)


def expect(cond: bool, msg: str) -> None:
    if not cond:
        print(f"  ❌ {msg}", flush=True)
        sys.exit(1)
    print(f"  ✓ {msg}", flush=True)


def main() -> None:
    with httpx.Client(base_url=BASE, timeout=30.0) as client:
        # 1. 登录拿 access token
        step("登录")
        r = client.post(
            "/api/v1/auth/login",
            json={"identifier": EMAIL, "password": PASSWORD},
        )
        expect(r.status_code == 200, f"POST /auth/login → {r.status_code}")
        access_token = r.json()["data"]["access_token"]
        client.headers["Authorization"] = f"Bearer {access_token}"

        # 2. 搜索:沙特 / 关键词 Al
        step("搜索 country=SA q=Al")
        r = client.get("/api/v1/credit/companies/search", params={"country": "SA", "q": "Al"})
        expect(r.status_code == 200, f"GET /credit/companies/search → {r.status_code}")
        items = r.json()["data"]
        expect(len(items) >= 1, f"返回 {len(items)} 条结果(期望 ≥ 1)")
        first = items[0]
        expect(first["grade"] == "A", f"第一条 grade={first['grade']}(期望 A)")
        company_id = first["id"]

        # 3. 详情(首访可能触发 ai_summary 生成)
        step(f"详情 company_id={company_id}")
        r = client.get(f"/api/v1/credit/companies/{company_id}")
        expect(r.status_code == 200, f"GET /credit/companies/{company_id} → {r.status_code}")
        data = r.json()["data"]
        expect(data["snapshot"] is not None, "snapshot 非空")
        expect(len(data["dimensions"]) == 4, f"4 个维度(实际 {len(data['dimensions'])})")
        expect(len(data["details"]) == 12, f"12 条 detail(实际 {len(data['details'])})")
        expect(len(data["certifications"]) >= 1, "至少 1 张证书")
        if data["snapshot"]["ai_summary"]:
            expect(True, "ai_summary 已生成")
        else:
            print("  ℹ️ ai_summary 为空(可能 DASHSCOPE_API_KEY 未配置)")

        # 4. 重算
        step("重算")
        r = client.post(f"/api/v1/credit/companies/{company_id}/recompute")
        if r.status_code == 403:
            print("  ℹ️ 当前账号(BUYER)无 credit:recompute 权限,跳过重算测试")
        else:
            expect(r.status_code == 200, f"POST .../recompute → {r.status_code}")
            new_snap = r.json()["data"]
            expect(new_snap["is_current"] is True, "新快照 is_current=true")

        # 5. 历史
        step("搜索历史")
        r = client.get("/api/v1/credit/search-history")
        expect(r.status_code == 200, f"GET /credit/search-history → {r.status_code}")
        hist = r.json()["data"]
        expect(any(h["company_id"] == company_id for h in hist), "历史包含刚才查的 company")

        # 6. AI 会话 + 流式消息(如果 DASHSCOPE_API_KEY 没配,会返 SSE error)
        step("AI 会话创建")
        r = client.post("/api/v1/credit/ai/conversations", json={"company_id": company_id})
        expect(r.status_code == 200, f"POST /credit/ai/conversations → {r.status_code}")
        conv_id = r.json()["data"]["id"]

        step(f"AI 流式消息 conv={conv_id}")
        with client.stream(
            "POST",
            f"/api/v1/credit/ai/conversations/{conv_id}/messages",
            json={"content": "请用一句话总结风险点"},
        ) as resp:
            expect(resp.status_code == 200, f"SSE → {resp.status_code}")
            chunks = []
            saw_done = False
            for line in resp.iter_lines():
                if not line:
                    continue
                if line.startswith("data: "):
                    payload = line[6:]
                    if payload == "[DONE]":
                        saw_done = True
                        break
                    chunks.append(payload)
                if line.startswith("event: error"):
                    print(f"  ⚠️ SSE 错误事件(可能 DASHSCOPE_API_KEY 未配)")
                    saw_done = True
                    break
            expect(saw_done or chunks, f"SSE 接收到 {len(chunks)} 段 / done={saw_done}")
            if chunks:
                preview = "".join(chunks)[:80]
                print(f"  ℹ️ 流式内容预览: {preview!r}")

    print("\n✅ smoke test 全部通过", flush=True)


if __name__ == "__main__":
    main()
