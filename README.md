# \# RAG Microservices (gateway + retriever + reasoner)

# 

# \## Быстрый старт

# 1\) Ubuntu/WSL:

# &nbsp;  python3 -m venv .venv \&\& source .venv/bin/activate

# &nbsp;  pip install -r requirements.txt

# 2\) Запусти 3 сервиса (в 3 окнах):

# &nbsp;  uvicorn services.retriever.app.main:app --port 8001

# &nbsp;  uvicorn services.reasoner.app.main:app --port 8002

# &nbsp;  uvicorn services.gateway.app.main:app --port 8000

# 3\) Индексация: POST http://localhost:8001/index

# 4\) Запрос: POST http://localhost:8000/query {"query":"...", "top\_k":3}

# 

# \## Документы

# Складывать в ./data (PDF/DOCX/TXT). Индексация — через /index.

# 

# \## Переменные окружения

# См. .env.example (реранкер, пути, позже — OLLAMA\_HOST/OLLAMA\_MODEL).



