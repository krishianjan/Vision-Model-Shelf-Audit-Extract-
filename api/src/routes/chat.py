"""
Phase 11 — RAG bot scoped to rep activities.

POST /chat  → natural language query about the rep's own audits + stores.
Uses Groq Llama-3.3-70B as the LLM. 
"""
from __future__ import annotations

import json
import os
import re
from typing import Any

import httpx
from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel

from src.auth import AuthUser, get_current_user

router = APIRouter(prefix="/chat", tags=["chat"])

_SYSTEM = """You are a SQL agent for shelf audit data.

AVAILABLE TABLES:
- accounts(id, name, chain, channel_type, address, org_id)
- shelf_audits(id, account_id, captured_at, status, fixture_type, org_id, captured_by)
- audit_observations(id, audit_id, brand_read, size_read, facings, shelf_position, price_value, status, matched_sku_id, org_id)
- products(id, brand, product_name, size_ml)
- guardrail_rejections(id, account_id, org_id, captured_by, category, reason)

CURRENT USER CONTEXT (use these literal values in WHERE clauses):
  org_id = '{org_id}'
  captured_by = '{user_id}'

STRICT RULES:
1. Output ONE single SELECT query only. NO semicolons. NO multiple queries.
2. NEVER use $1, $2 or any parameter placeholders. Use literal values.
3. ALWAYS filter by org_id = '{org_id}' for org-scoped tables.
4. ONLY SELECT. No INSERT, UPDATE, DELETE, DROP, ALTER, TRUNCATE.
5. Do NOT wrap SQL in markdown code blocks.

CORRECT EXAMPLE:
  SELECT COUNT(*) FROM shelf_audits WHERE org_id = '{org_id}'

WRONG (will be rejected):
  WHERE org_id = $1
  WHERE org_id = 'your_org_id'

Output ONLY raw JSON (no code blocks):
{{
  "answer": "brief natural language answer",
  "sql_used": "the SELECT query or null",
  "tables_touched": ["table names"]
}}"""

class ChatRequest(BaseModel):
    question: str

class ChatResponse(BaseModel):
    answer: str
    sql_used: str | None = None
    tables_touched: list[str] = []

async def _call_groq(messages: list[dict]) -> dict:
    api_key = os.environ.get("GROQ_API_KEY", "")
    if not api_key:
        raise RuntimeError("GROQ_API_KEY not set")
    async with httpx.AsyncClient(timeout=30.0) as client:
        resp = await client.post(
            "https://api.groq.com/openai/v1/chat/completions",
            headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
            json={
                "model": "llama-3.3-70b-versatile",
                "messages": messages,
                "max_tokens": 1024,
                "temperature": 0.0,
                "response_format": {"type": "json_object"},
            },
        )
        resp.raise_for_status()
    raw = resp.json()["choices"][0]["message"]["content"].strip()
    return json.loads(raw)

@router.post("", response_model=ChatResponse)
async def chat(
    body: ChatRequest,
    request: Request,
    user: AuthUser = Depends(get_current_user),
):
    if len(body.question) > 500:
        raise HTTPException(400, "Message too long (max 500 chars)")

    # Pass 1: Ask LLM for the SQL
    system_prompt = _SYSTEM.format(
        org_id=str(user.org_id),
        user_id=str(user.user_id),
    )
    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": body.question}
    ]

    try:
        parsed = await _call_groq(messages)
    except Exception as e:
        return ChatResponse(answer=f"LLM unavailable: {e}")

    sql = parsed.get("sql_used")
    answer = parsed.get("answer", "")
    tables = parsed.get("tables_touched", [])

    if not sql:
        return ChatResponse(answer=answer, sql_used=sql, tables_touched=tables)

    # Validate against modifications or non-SELECTs
    if not sql.strip().upper().startswith("SELECT") or re.search(r'\b(UPDATE|DELETE|DROP|INSERT|ALTER|TRUNCATE)\b', sql, re.IGNORECASE):
        return ChatResponse(answer="I am not allowed to execute destructive queries.", sql_used=sql, tables_touched=tables)

    # BLOCK: SQL with parameters ($1, $2, etc) - we require literal values ONLY
    if re.search(r'\$\d+', sql):
        return ChatResponse(
            answer="Query rejected: Parameters like $1 are not allowed. Use literal values instead.", 
            sql_used=sql, 
            tables_touched=tables
        )

    # BLOCK: Multiple queries (semicolons) — only one SELECT allowed
    if ';' in sql.rstrip().rstrip(';'):
        return ChatResponse(
            answer="Query rejected: Only one query at a time is allowed. Please ask a single question.",
            sql_used=sql,
            tables_touched=tables,
        )

    # Strip trailing semicolon if present
    sql = sql.rstrip().rstrip(';').strip()

    # Pass 2: Execute SQL securely
    db = request.app.state.db
    rows_data = []
    error_msg = None

    try:
        async with db.acquire() as conn:
            async with conn.transaction():
                # Enforce RLS by passing SET LOCAL request.jwt.claims
                jwt_claims = json.dumps({"sub": str(user.user_id), "org_id": str(user.org_id)})
                await conn.execute("SET LOCAL request.jwt.claims = $1", jwt_claims)
                # Ensure read-only role/transaction
                await conn.execute("SET LOCAL transaction_read_only = 'on'")
                
                rows = await conn.fetch(sql)
                rows_data = [dict(r) for r in rows]
    except Exception as e:
        error_msg = str(e)

    # Pass 3: Give results back to LLM to formulate final answer if we got rows
    if error_msg:
        final_answer = f"Error executing query: {error_msg}"
    elif rows_data:
        messages.append({"role": "assistant", "content": json.dumps(parsed)})
        messages.append({
            "role": "user", 
            "content": f"The database returned these rows:\n{json.dumps(rows_data, default=str)}\nProvide a natural language summary of this data to answer my original question. Output JSON with 'answer' only."
        })
        try:
            final_parsed = await _call_groq(messages)
            final_answer = final_parsed.get("answer", answer)
        except Exception:
            final_answer = f"Data retrieved: {json.dumps(rows_data, default=str)}"
    else:
        final_answer = "No results found for your query."

    return ChatResponse(
        answer=final_answer,
        sql_used=sql,
        tables_touched=tables,
    )
