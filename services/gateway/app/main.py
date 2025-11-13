from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
import httpx
import json
import logging
import time

from .config import settings

# Настройка логгера JSON
logger = logging.getLogger("gateway")
logger.setLevel(logging.INFO)
if not logger.handlers:
    h = logging.StreamHandler()
    h.setFormatter(logging.Formatter('%(message)s'))
    logger.addHandler(h)

app = FastAPI(title="gateway")

class QueryRequest(BaseModel):
    query: str
    top_k: int = 2

@app.get("/healthz")
def healthz():
    return {"status": "ok"}

async def _post_json(url: str, payload: dict):
    # простой ретрай по сетевым ошибкам/5xx
    last_err = None
    for attempt in range(settings.RETRIES + 1):
        try:
            async with httpx.AsyncClient(timeout=settings.HTTP_TIMEOUT_SEC) as client:
                r = await client.post(url, json=payload)
            r.raise_for_status()
            return r.json()
        except httpx.HTTPError as e:
            last_err = e
            if attempt < settings.RETRIES:
                time.sleep(0.3 * (attempt + 1))  # backoff
            else:
                break
    raise HTTPException(status_code=502, detail=f"upstream error: {last_err}")

@app.post("/query")
async def query(req: QueryRequest):
    t0 = time.perf_counter()

    retr_payload = {"query": req.query, "top_k": req.top_k}
    retr_url = f"{settings.RETRIEVER_URL}/retrieve"
    retr_data = await _post_json(retr_url, retr_payload)

    contexts = [d["text"] for d in retr_data.get("results", [])]
    reason_payload = {"question": req.query, "contexts": contexts}
    reason_url = f"{settings.REASONER_URL}/answer"
    reason_data = await _post_json(reason_url, reason_payload)

    latency_ms = round((time.perf_counter() - t0) * 1000)

    # Лог JSON одной строкой
    logger.info(json.dumps({
        "event": "query",
        "top_k": req.top_k,
        "latency_ms": latency_ms,
        "results": len(contexts)
    }, ensure_ascii=False))

    return {
        "question": req.query,
        "retriever_docs": retr_data.get("results", []),
        "final_answer": reason_data.get("answer", ""),
        "latency_ms": latency_ms
    }
