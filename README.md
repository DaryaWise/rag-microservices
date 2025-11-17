# RAG Microservices (gateway · retriever · reasoner)

Три микросервиса для RAG на локальных документах.
`retriever` — индексирует PDF/DOCX/TXT и ищет по FAISS с опциональным реранком.
`reasoner` — формирует ответ на основе переданных фрагментов.
`gateway` — оркестрирует: вызывает два сервиса и возвращает итог.

Порты: gateway 8000 · retriever 8001 · reasoner 8002
Документы для индексации: папка `./data/`.

---

## Что понадобится

* Ubuntu/WSL с Python 3.10+
* В этой папке выполните настройку окружения один раз:
  `python3 -m venv .venv`
  `source .venv/bin/activate`
  `pip install -r requirements.txt`

---

## Запуск (локально, в 3 отдельных окнах)

Окно 1 — retriever (порт 8001):
`uvicorn services.retriever.app.main:app --port 8001`

Окно 2 — reasoner (порт 8002):
`uvicorn services.reasoner.app.main:app --port 8002`

Окно 3 — gateway (порт 8000):
`uvicorn services.gateway.app.main:app --port 8000`

Проверка здоровья (в браузере):
`http://localhost:8001/healthz` · `http://localhost:8002/healthz` · `http://localhost:8000/healthz`

---

## Индексация и сквозной запрос

1. Скопируйте ваши файлы в папку `./data/`.
2. Запустите индексацию (retriever): отправьте POST на `http://localhost:8001/index`.
   Быстро через curl: `curl -X POST http://localhost:8001/index`
3. Отправьте запрос в gateway:
   `curl -H "Content-Type: application/json" -d '{"query":"о чём эти документы?","top_k":2}' http://localhost:8000/query`

Результат содержит: исходный вопрос, найденные фрагменты (`retriever_docs`) и финальный ответ (`final_answer`).

---

## Где смотреть Swagger

* retriever: `http://localhost:8001/docs`
* reasoner:  `http://localhost:8002/docs`
* gateway:   `http://localhost:8000/docs`

---

## Эндпоинты (кратко)

retriever

* `POST /index` — индексирует файлы из `./data` (PDF/DOCX/TXT → чанк → эмбеддинги → FAISS)
* `POST /retrieve` — тело: `{"query":"...", "top_k":3}` → топ-фрагменты
* `GET /healthz` — здоровье сервиса

reasoner

* `POST /answer` — тело: `{"question":"...", "contexts":["фрагмент1","фрагмент2"]}` → ответ
* `GET /healthz`

gateway

* `POST /query` — тело: `{"query":"...", "top_k":3}` → оркестрация (поиск + ответ)
* `GET /healthz`

---

## Переменные окружения

Скопируйте шаблон: `cp .env.example .env`
Полезные параметры:

* `RETRIEVER_RERANK_ENABLED=true` — включить реранк
* `RETRIEVER_RERANK_TOP_N=20` — сколько кандидатов реранкеру
  Если позже подключите локальную LLM через Ollama:
* `REASONER_OLLAMA_HOST=http://127.0.0.1:11434`
* `REASONER_OLLAMA_MODEL=mistral`

Файл `.env` в репозиторий не добавляйте.

---

## Структура

```
.
├─ services/
│  ├─ gateway/   (main.py — /query)
│  ├─ retriever/ (main.py — /index, /retrieve; FAISS + CrossEncoder)
│  └─ reasoner/  (main.py — /answer)
├─ data/         (ваши PDF/DOCX/TXT)
├─ vectorstore/  (индекс FAISS создаётся после /index)
├─ models/       (кэш моделей)
├─ requirements.txt
├─ .env.example
└─ README.md
```

---

## Если что-то не работает

* Пустой ответ из retriever → убедитесь, что файлы лежат в `./data/`, затем заново вызовите `POST /index`.
* Сообщение «Connection refused» → соответствующий сервис не запущен или порт занят.
* Чтобы перезапустить быстро: остановите окно с сервером `Ctrl+C` и снова выполните команду запуска для этого сервиса.

---
