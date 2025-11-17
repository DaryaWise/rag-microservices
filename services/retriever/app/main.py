from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from pathlib import Path
import logging, json
import numpy as np
import faiss
from sentence_transformers import SentenceTransformer, CrossEncoder
from pypdf import PdfReader
import docx

from .config import settings

app = FastAPI(title="retriever")

# ---------- ЛОГИ JSON ----------
logger = logging.getLogger("retriever")
logger.setLevel(logging.INFO)
if not logger.handlers:
    h = logging.StreamHandler()
    h.setFormatter(logging.Formatter('%(message)s'))
    logger.addHandler(h)

# ---------- Пути/параметры ----------
DATA_DIR: Path = settings.data_path()
VSTORE_DIR: Path = settings.vstore_path()
VSTORE_DIR.mkdir(parents=True, exist_ok=True)

INDEX_PATH = VSTORE_DIR / "index.faiss"
META_PATH  = VSTORE_DIR / "meta.json"

CHUNK_SIZE     = settings.CHUNK_SIZE
CHUNK_OVERLAP  = settings.CHUNK_OVERLAP
DEFAULT_TOP_K  = settings.DEFAULT_TOP_K
RERANK_ENABLED = settings.RERANK_ENABLED
RERANK_TOP_N   = settings.RERANK_TOP_N

# ---------- Модели ----------
embed_model = SentenceTransformer("sentence-transformers/all-MiniLM-L6-v2")
cross_encoder = None  # ленивое создание при первом запросе, если включён реранк

class RetrieveRequest(BaseModel):
    query: str
    top_k: int = DEFAULT_TOP_K

@app.get("/healthz")
def healthz():
    return {"status": "ok"}

# ---------- Чтение файлов ----------
def read_pdf(path: Path) -> str:
    out = []
    with open(path, "rb") as f:
        pdf = PdfReader(f)
        for p in pdf.pages:
            out.append(p.extract_text() or "")
    return "\n".join(out)

def read_docx(path: Path) -> str:
    d = docx.Document(str(path))
    return "\n".join(p.text for p in d.paragraphs)

def read_plain(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="ignore")

def read_file(path: Path) -> str:
    ext = path.suffix.lower()
    if ext == ".pdf":  return read_pdf(path)
    if ext == ".docx": return read_docx(path)
    if ext in {".txt", ".md"}: return read_plain(path)
    return ""

# ---------- Чанкование ----------
def chunk_text(text: str, size: int = CHUNK_SIZE, overlap: int = CHUNK_OVERLAP):
    text = text.replace("\r", " ")
    chunks, i, n = [], 0, len(text)
    step = max(size - overlap, 1)
    while i < n:
        ch = text[i:i+size]
        if ch.strip():
            chunks.append(ch)
        i += step
    return chunks

# ---------- Построение индекса ----------
def build_index():
    import json as _json

    docs_meta, all_chunks = [], []

    for path in sorted(DATA_DIR.glob("**/*")):
        if path.is_dir(): continue
        content = read_file(path)
        if not content:  continue
        chunks = chunk_text(content)
        for j, ch in enumerate(chunks):
            docs_meta.append({"source": str(path), "chunk_id": j, "text": ch})
            all_chunks.append(ch)

    if not all_chunks:
        raise RuntimeError("В папке data/ нет поддерживаемых документов")

    emb = embed_model.encode(
        all_chunks, batch_size=32, show_progress_bar=False,
        convert_to_numpy=True, normalize_embeddings=True
    ).astype(np.float32)
    dim = emb.shape[1]
    index = faiss.IndexFlatIP(dim)   # косинус через нормированные вектора
    index.add(emb)

    faiss.write_index(index, str(INDEX_PATH))
    META_PATH.write_text(_json.dumps(docs_meta, ensure_ascii=False), encoding="utf-8")

    logger.info(json.dumps({
        "event": "index_built",
        "docs": len({m['source'] for m in docs_meta}),
        "chunks": len(all_chunks)
    }, ensure_ascii=False))

@app.post("/index")
def index_endpoint():
    try:
        build_index()
        return {"status": "indexed", "documents_indexed": True}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)) from e

# ---------- Загрузка индекса ----------
def load_index():
    import json as _json
    if not INDEX_PATH.exists() or not META_PATH.exists():
        raise RuntimeError("Индекс не найден. Сначала вызовите /index")
    index = faiss.read_index(str(INDEX_PATH))
    meta  = _json.loads(META_PATH.read_text(encoding="utf-8"))
    return index, meta

# ---------- Реранк ----------
def maybe_init_cross_encoder():
    global cross_encoder
    if cross_encoder is None:
        # лёгкая и быстрая модель для реранка
        cross_encoder = CrossEncoder("cross-encoder/ms-marco-MiniLM-L-6-v2")
    return cross_encoder

def rerank(query: str, results: list[dict], top_k: int) -> list[dict]:
    ce = maybe_init_cross_encoder()
    pairs = [(query, r["text"]) for r in results]
    scores = ce.predict(pairs).tolist()  # чем выше, тем релевантнее
    for r, s in zip(results, scores):
        r["rerank_score"] = float(s)
    results.sort(key=lambda x: x["rerank_score"], reverse=True)
    return results[:top_k]

# ---------- Поиск ----------
@app.post("/retrieve")
def retrieve(req: RetrieveRequest):
    try:
        index, meta = load_index()
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e)) from e

    q = embed_model.encode([req.query], convert_to_numpy=True, normalize_embeddings=True).astype(np.float32)

    # сначала берем побольше кандидатов из FAISS (для реранка), потом топ-k
    initial_k = max(req.top_k, min(RERANK_TOP_N, len(meta)) if RERANK_ENABLED else req.top_k)
    initial_k = max(1, min(initial_k, len(meta)))

    scores, idxs = index.search(q, initial_k)  # (1, initial_k)
    idxs = idxs[0].tolist()
    scores = scores[0].tolist()

    prelim = []
    for rank, (i, s) in enumerate(zip(idxs, scores), start=1):
        m = meta[i]
        prelim.append({
            "rank": rank,
            "text": m["text"],
            "source": m["source"],
            "chunk_id": m["chunk_id"],
            "score": float(s),   # косинус
        })

    if RERANK_ENABLED and prelim:
        final = rerank(req.query, prelim, req.top_k)
    else:
        # без реранка просто топ-k по FAISS
        final = sorted(prelim, key=lambda x: x["score"], reverse=True)[:req.top_k]

    for i, r in enumerate(final, start=1):
        r["rank"] = i

    return {"query": req.query, "results": final}
