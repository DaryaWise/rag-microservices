# \# RAG Microservices (gateway · retriever · reasoner)

# 

# Микросервисная архитектура для исполнения моделей по сценарию RAG:

# \- \*\*retriever\*\* — индексация локальных документов (PDF/DOCX/TXT), поиск в FAISS, опциональный реранк Cross-Encoder.

# \- \*\*reasoner\*\* — генерация ответа на основе переданных контекстов (по умолчанию — простой ответ; при наличии Ollama — LLM).

# \- \*\*gateway\*\* — оркестратор: принимает запрос, вызывает retriever и reasoner, агрегирует результат.

# 

# Порты по умолчанию: gateway `8000`, retriever `8001`, reasoner `8002`.  

# Документы для индексации кладутся в `./data/`.

# 

# ---

# 

# \## Быстрый старт (Docker, единая команда)

# 

# ```bash

# docker compose up -d --build

# docker compose exec ollama ollama pull mistral        # один раз, чтобы подтянуть модель

# curl -X POST http://localhost:8001/index              # индексация ./data

# curl -H "Content-Type: application/json" \\

# &nbsp; -d '{"query":"о чём эти документы?","top\_k":2}' \\

# &nbsp; http://localhost:8000/query                         # сквозной запрос через gateway

# ````

# 

# Откройте Swagger:

# 

# \* retriever: \[http://localhost:8001/docs](http://localhost:8001/docs)

# \* reasoner:  \[http://localhost:8002/docs](http://localhost:8002/docs)

# \* gateway:   \[http://localhost:8000/docs](http://localhost:8000/docs)

# 

# ---

# 

# \## Быстрый старт (Dev, локально в 3 окнах, Ubuntu/WSL)

# 

# ```bash

# python3 -m venv .venv \&\& source .venv/bin/activate

# pip install -r requirements.txt

# ```

# 

# Окно 1 — retriever:

# 

# ```bash

# uvicorn services.retriever.app.main:app --port 8001

# ```

# 

# Окно 2 — reasoner:

# 

# ```bash

# uvicorn services.reasoner.app.main:app --port 8002

# ```

# 

# Окно 3 — gateway:

# 

# ```bash

# uvicorn services.gateway.app.main:app --port 8000

# ```

# 

# Проверка:

# 

# ```bash

# curl -X POST http://localhost:8001/index

# curl -H "Content-Type: application/json" \\

# &nbsp; -d '{"query":"о чём эти документы?","top\_k":2}' \\

# &nbsp; http://localhost:8000/query

# ```

# 

# > Для удобного дев-запуска без «трёх окон» можно сделать скрипт `scripts/dev.sh`, который стартует три uvicorn-процесса и гасит их по `Ctrl+C`.

# 

# ---

# 

# \## Структура репозитория

# 

# ```

# .

# ├─ services/

# │  ├─ gateway/

# │  │  ├─ app/main.py         # /query

# │  │  └─ Dockerfile

# │  ├─ retriever/

# │  │  ├─ app/main.py         # /index, /retrieve (FAISS + CrossEncoder)

# │  │  └─ Dockerfile

# │  └─ reasoner/

# │     ├─ app/main.py         # /answer (LLM через Ollama при наличии)

# │     └─ Dockerfile

# ├─ data/                     # локальные документы (PDF/DOCX/TXT)

# ├─ vectorstore/              # индекс FAISS (создаётся после /index)

# ├─ models/                   # кэш моделей (volume)

# ├─ docker-compose.yml

# ├─ requirements.txt

# ├─ .env.example              # примеры переменных

# └─ README.md

# ```

# 

# ---

# 

# \## API (контракты)

# 

# \### retriever

# 

# \* `POST /index` — индексация `./data` (PDF/DOCX/TXT → чанк → эмбеддинги → FAISS).

# \* `POST /retrieve` — тело:

# 

# &nbsp; ```json

# &nbsp; {"query": "текст запроса", "top\_k": 3}

# &nbsp; ```

# 

# &nbsp; ответ:

# 

# &nbsp; ```json

# &nbsp; {

# &nbsp;   "query": "...",

# &nbsp;   "results": \[

# &nbsp;     {"rank":1, "text":"...", "source":"data/..", "chunk\_id":0, "score":0.15, "rerank\_score":-10.07}

# &nbsp;   ]

# &nbsp; }

# &nbsp; ```

# 

# \### reasoner

# 

# \* `POST /answer` — тело:

# 

# &nbsp; ```json

# &nbsp; {"question":"...", "contexts":\["фрагмент 1", "фрагмент 2"]}

# &nbsp; ```

# 

# &nbsp; ответ:

# 

# &nbsp; ```json

# &nbsp; {"answer":"..."}

# &nbsp; ```

# 

# \### gateway

# 

# \* `POST /query` — тело:

# 

# &nbsp; ```json

# &nbsp; {"query":"...", "top\_k":3}

# &nbsp; ```

# 

# &nbsp; ответ:

# 

# &nbsp; ```json

# &nbsp; {

# &nbsp;   "question":"...",

# &nbsp;   "retriever\_docs":\[ ... ],

# &nbsp;   "final\_answer":"...",

# &nbsp;   "latency\_ms": 1234

# &nbsp; }

# &nbsp; ```

# 

# У всех сервисов есть `GET /healthz` и Swagger `/docs`.

# 

# ---

# 

# \## Переменные окружения

# 

# Скопируйте шаблон:

# 

# ```bash

# cp .env.example .env

# ```

# 

# Примеры (см. `.env.example`):

# 

# ```

# \# retriever

# RETRIEVER\_RERANK\_ENABLED=true

# RETRIEVER\_RERANK\_TOP\_N=20

# 

# \# reasoner (для Docker-стека с Ollama)

# REASONER\_OLLAMA\_HOST=http://ollama:11434

# REASONER\_OLLAMA\_MODEL=mistral

# ```

# 

# `.env` хранить в git не нужно.

# 

# ---

# 

# \## Реализация поиска

# 

# \* Эмбеддинги: `sentence-transformers/all-MiniLM-L6-v2` (локально).

# \* Векторное хранилище: FAISS (IndexFlatIP, косинус через нормированные вектора).

# \* Реранк (опционально): `cross-encoder/ms-marco-MiniLM-L-6-v2` поверх top-N кандидатов FAISS.

# 

# ---

# 

# \## Советы и диагностика

# 

# \* Порты 8000/8001/8002/11434 должны быть свободны.

# \* В Docker-стеке модель для LLM нужно подтянуть один раз:

# 

# &nbsp; ```

# &nbsp; docker compose exec ollama ollama pull mistral

# &nbsp; ```

# \* Пустые результаты `/retrieve` → положите файлы в `./data` и снова вызовите `/index`.

# \* Проверка здоровья:

# 

# &nbsp; ```

# &nbsp; curl http://localhost:8001/healthz

# &nbsp; curl http://localhost:8002/healthz

# &nbsp; curl http://localhost:8000/healthz

# &nbsp; ```

# 

# ---

# 

# \## Лицензия

# 

# MIT

# 

# ````

# 

# После вставки сделай:

# ```bash

# git add README.md

# git commit -m "Docs: concise README with Docker \& Dev quick start"

# git push

# ````



