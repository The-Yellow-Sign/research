# Основные команды

```bash
# 1. Поднять инфраструктуру
docker compose up -d

# 2. Установить зависимости
uv sync

# 3. Индексация документов
uv run python -m src.interfaces.cli.commands.ingest

# 4. Запустить CLI бота
uv run python main.py
```

---

## 1. Инфраструктура

```bash
docker compose up -d
```

Проверка: `docker compose ps` — статусы `healthy`.

| Сервис | Порт | Описание |
|--------|------|----------|
| **Milvus** | `19530` | Векторная база данных |
| **OpenSearch** | `9200` | Полнотекстовый поиск + хранилище |

---

## 2. Настройка LLM

### Вариант А: Local LLM (рекомендуется для dev)
1. **LM Studio**: Загрузить `qwen2.5-7b-instruct`, запустить сервер на `localhost:1234`.
2. **Ollama**: `ollama serve` + `ollama run qwen2.5:7b`.

### Вариант Б: OpenRouter (для evaluation)
Добавить в `.env`:
```bash
OPENROUTER_API_KEY=sk-or-v1-...
EVAL_JUDGE_MODEL=openai/gpt-4o-mini
```

---

## 3. Режимы запуска

### 🤖 CLI Чат-бот (Terminal UI)
Основной режим для тестирования RAG.
```bash
uv run python main.py
# или
uv run python -m src.interfaces.cli.terminal_ui
```

### 🌐 API Сервер (FastAPI)
REST API для интеграции с фронтендом.
```bash
uv run uvicorn src.interfaces.api.app:app --host 0.0.0.0 --port 8000 --reload
```
- Swagger UI: [http://localhost:8000/docs](http://localhost:8000/docs)
- Health Check: [http://localhost:8000/health/ready](http://localhost:8000/health/ready)

### 📊 Оценка качества (Evaluation)
Запуск прогона по Golden Dataset с LLM-судьей.
```bash
# Запустить оценку (требуется OpenRouter)
uv run python -m src.evaluation.run_evaluation --limit 10

# Только RAG (без судьи)
uv run python -m src.evaluation.run_evaluation --skip-judge
```

---

## 4. Индексация данных

Положите `.md` файлы в `devops-playbooks/`.

**Инкрементальная индексация** (только новые/изменённые файлы):
```bash
uv run python -m src.interfaces.cli.commands.ingest
```

**Полная переиндексация** (удалит старые индексы):
```bash
uv run python -m src.interfaces.cli.commands.ingest --force
```
---
