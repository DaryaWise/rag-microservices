from fastapi import FastAPI
from pydantic import BaseModel

app = FastAPI(title="reasoner")

class ReasonRequest(BaseModel):
    question: str
    contexts: list[str]

@app.get("/healthz")
def healthz():
    return {"status": "ok"}

@app.post("/answer")
def answer(req: ReasonRequest):
    # Пока просто собираем "ответ" на основе контекста
    combined = " ".join(req.contexts)
    return {
        "answer": f"Похоже, документы говорят о следующем: {combined[:100]}..."
    }
