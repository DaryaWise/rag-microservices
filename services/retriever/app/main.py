# path: services/retriever/app/main.py
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from pathlib import Path
import logging, json

import faiss
import numpy as np
from sentence_transformers import SentenceTransformer
from pypdf import PdfReader
import docx

from .config import settings

app = FastAPI(title="retriever")

# ---------- ЛОГИРОВАНИЕ JSON ----------
logger = logging.getLogger("retriever")
logger.setLevel(logging.INFO)
if not logger.handlers:
    h = logging.StreamHandler()
    h.setFormatter(logging.Formatter('%(message)s'))
    logger.addHandler(h)

# ---------- ПУТИ И ПАРАМЕТРЫ ИЗ КОНФИГА ----------
DATA_DIR: Path = settings.data_path()
VSTORE_DIR: Path = settings.vstore_path()
VSTORE_DIR.mkdir(parents=True, exist_ok=True)

INDEX_PATH = VSTORE_DIR / "index.faiss"
META_PATH  = VSTORE_DIR / "meta.json"

CHUNK_SIZE = settings.CHUNK_SIZE
CHUNK_OVERLAP = settings.CHUNK_OVERLAP

# ---------- МОДЕЛЬ ЭМБЕДДИНГОВ ----------
# скачается при первом запуске и закешируется в ~/.cache
model = SentenceTransformer("sentence-transformers/all-MiniLM-L6-v2")

class RetrieveRequest(BaseModel):
    query: str
    top_k: int = 5

@app.get("/healthz")
def healthz():
    return {"status": "ok"}

# ---------- ЧТЕНИЕ ФАЙЛОВ ----------
def read_pdf(path: Path) -> str:
    text = []
    with open(path, "rb") as f:
        pdf = PdfReader(f)
        for page in pdf.pages:
            text.append(page.extract_text() or "")
    return "\n".join(text)

def read_docx(path: Path) -> str:
    d = docx.Document(str(path))
    return "\n".join(p.text for p in d.paragraphs)

def read_plain(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="ignore")

def read_file(path: Path) -> str:
    ext = path.suffix.lower()
    if ext == ".pdf":
        return read_pdf(path)
    if ext == ".docx":
        return read_docx(path)
    if ext in {".txt", ".md"}:
        return read_plain(path)
    return ""  # неподдерживаемые форматы пропускаем

# ---------- ЧАНКОВАНИЕ ----------
def chunk_text(text: str, size: int = CHUNK_SIZE, overlap: int = CHUNK_OVERLAP):
    text = text.replace("\r", " ")
    chunks = []
    i = 0
    n = len(text)
    step = max(size - overlap, 1)
    while i < n:
        chunk = text[i : i + size]
        if chunk.strip():
            chunks.append(chunk)
        i += step
    return chunks

# ---------- ПОСТРОЕНИЕ ИНДЕКСА ----------
def build_index():
    docs_meta = []   # [{source, chunk_id, text}]
    all_chunks = []  # список строк для эмбеддинга

    for path in sorted(DATA_DIR.glob("**/*")):
        if path.is_dir():
            continue
        content = read_file(path)
        if not content:
            continue
        chunks = chunk_text(content)
        for j, chunk in enumerate(chunks):
            docs_meta.append({
                "source": str(path),
                "chunk_id": j,
                "text": chunk
            })
            all_chunks.append(chunk)

    if not all_chunks:
        raise RuntimeError("В папке data/ не найдено поддерживаемых документов")

    embeddings = model.encode(
        all_chunks,
        batch_size=32,
        show_progress_bar=False,
        convert_to_numpy=True,
        normalize_embeddings=True
    )
    dim = embeddings.shape[1]

    index = faiss.IndexFlatIP(dim)  # косинусная близость через нормированные вектора
    index.add(embeddings.astype(np.float32))

    faiss.write_index(index, str(INDEX_PATH))
    META_PATH.write_text(json.dumps(docs_meta, ensure_ascii=False), encoding="utf-8")

    # Лог события индексации
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

# ---------- ЗАГРУЗКА ИНДЕКСА ----------
def load_index():
    if not INDEX_PATH.exists() or not META_PATH.exists():
        raise RuntimeError("Индекс не найден. Сначала вызовите /index")
    index = faiss.read_index(str(INDEX_PATH))
    meta = json.loads(META_PATH.read_text(encoding="utf-8"))
    return index, meta

# ---------- ПОИСК ----------
@app.post("/retrieve")
def retrieve(req: RetrieveRequest):
    try:
        index, meta = load_index()
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e)) from e

    q = model.encode([req.query], convert_to_numpy=True, normalize_embeddings=True)
    q = q.astype(np.float32)

    k = max(1, min(req.top_k, len(meta)))
    scores, idxs = index.search(q, k)
    idxs = idxs[0].tolist()
    scores = scores[0].tolist()

    results = []
    for rank, (i, s) in enumerate(zip(idxs, scores), start=1):
        m = meta[i]
        results.append({
            "rank": rank,
            "text": m["text"],
            "source": m["source"],
            "chunk_id": m["chunk_id"],
            "score": float(s),
        })

    return {"query": req.query, "results": results}
